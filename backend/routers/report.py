from typing import Optional
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends
from fastapi.responses import Response, FileResponse
from sqlalchemy.orm import Session
import pandas as pd
import io
import os
import uuid
from datetime import datetime
from backend.database import get_db
from backend.models.report import ReportHistory

router = APIRouter(tags=["Reports"])
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

def clean_mobile_val(val):
    if val is None or pd.isna(val) or val == "":
        return ""
    val_str = str(val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]
    try:
        if isinstance(val, float):
            return str(int(val))
    except Exception:
        pass
    return val_str

def clean_dataframe_mobile_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        for col in df.columns:
            col_name = " ".join([str(c) for c in col]).lower()
            if any(k in col_name for k in ['mobile', 'phone', 'contact']):
                df[col] = df[col].apply(clean_mobile_val)
    else:
        for col in df.columns:
            col_name = str(col).lower()
            if any(k in col_name for k in ['mobile', 'phone', 'contact']):
                df[col] = df[col].apply(clean_mobile_val)
    return df

@router.post("/generate")
async def generate_report(
    report_type: str = Form(...),
    file: UploadFile = File(...),
    district: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported.")
    
    try:
        contents = await file.read()
        
        # Save to disk first
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        output_filename = f"report_{report_type}_{timestamp}_{unique_id}.xlsx"
        output_filepath = os.path.join(REPORTS_DIR, output_filename)
        
        # Auto-detect header row
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents), header=None)
            
            # Find the row containing 'District Name' or 'District' to use as header
            header_row = 0
            for i in range(min(15, len(df))):
                row_vals = [str(x).strip().lower() for x in df.iloc[i].values if pd.notna(x)]
                # Check if any value contains 'district' and either 'name' or just 'district'
                if any('district' in v and ('name' in v or v == 'district') for v in row_vals):
                    header_row = i
                    break
                    
            df = pd.read_excel(io.BytesIO(contents), header=header_row)

        # Standardize the district column name for internal processing
        dist_col = None
        for col in df.columns:
            c = str(col).strip().lower()
            if 'district' in c and ('name' in c or c == 'district'):
                dist_col = col
                break
        
        if not dist_col:
            raise Exception("District Name column not found in dataset")

        # Clean up the dataset (remove metadata rows usually starting with '(3)')
        if 'Academic Year' in df.columns:
            df = df[df['Academic Year'] != '(3)']

        # Define columns to keep
        keep_cols = [dist_col]
        if 'Academic Year' in df.columns:
            keep_cols.append('Academic Year')
            
        # Filter specific columns based on report type
        if report_type == '18_plus_pendency':
            desired = ['Total Pending', 'Pending at SubDistrict', 'Pending at District']
            matched = []
            for d in desired:
                for c in df.columns:
                    if str(c).strip().lower() == d.lower():
                        matched.append(c)
                        break
            if len(matched) < len(desired):
                raise Exception(f"Invalid dataset uploaded for 18 Plus Pendency. Please ensure you uploaded the correct dataset.")
            df = df[keep_cols + matched]
            
        elif report_type == 'mbu_district_wise':
            desired = [
                'MBU Pending (Age 5-15)', 
                'MBU Pending (Age 15 and above)',
                'Status Check to be done',
                'MBU Not Required',
                'Total Student'
            ]
            matched = []
            for d in desired:
                for c in df.columns:
                    c_clean = str(c).strip().lower()
                    d_clean = d.lower()
                    if c_clean == d_clean or (d_clean == 'total student' and c_clean == 'total students'):
                        matched.append(c)
                        break
            if len(matched) < len(desired):
                raise Exception(f"Invalid dataset uploaded for MBU District Wise. Please ensure you uploaded the correct dataset.")
            df = df[keep_cols + matched]
            
        elif report_type == 'cenetarian_district_report':
            desired = ['Pending Total', 'Pending Sub District', 'Pending District']
            matched = []
            for d in desired:
                for c in df.columns:
                    if str(c).strip().lower() == d.lower():
                        matched.append(c)
                        break
            if len(matched) < len(desired):
                raise Exception(f"Invalid dataset uploaded for Cenetarian District Report. Please ensure you uploaded the correct dataset.")
            df = df[keep_cols + matched]

            
        # Identify numeric columns for aggregation
        numeric_cols = []
        for col in df.columns:
            if col not in keep_cols:
                # Attempt to convert to numeric
                converted = pd.to_numeric(df[col], errors='coerce')
                # Only keep columns that have at least one valid number
                if not converted.isna().all():
                    df[col] = converted.fillna(0).astype(int)
                    numeric_cols.append(col)
                    keep_cols.append(col)
                    
        df = df[keep_cols].dropna(subset=[dist_col])

        if report_type == 'mbu_district_wise' and numeric_cols:
            df['Total Pending'] = df[numeric_cols].sum(axis=1)
            numeric_cols.append('Total Pending')

        if district:
            df = df[df[dist_col].astype(str).str.lower() == district.lower()]

        # Write to multi-sheet excel
        with pd.ExcelWriter(output_filepath, engine='openpyxl') as writer:
            # Combined Sheet
            combined_df = df.groupby(dist_col)[numeric_cols].sum().reset_index()
            
            # Ensure all master districts from DB appear in Combined sheet
            from backend.models.district import District
            master_districts = [d.district_name for d in db.query(District).order_by(District.district_name.asc()).all() if d.district_name]
            existing_dists = combined_df[dist_col].astype(str).str.strip().str.lower().tolist()
            missing_rows = []
            for md in master_districts:
                if md.strip().lower() not in existing_dists:
                    row_dict = {dist_col: md}
                    for nc in numeric_cols:
                        row_dict[nc] = 0
                    missing_rows.append(row_dict)
            if missing_rows:
                missing_df = pd.DataFrame(missing_rows)
                combined_df = pd.concat([combined_df, missing_df], ignore_index=True)
                combined_df = combined_df.sort_values(by=[dist_col]).reset_index(drop=True)

            combined_df.insert(0, 'S.No', range(1, len(combined_df) + 1))
            combined_df.to_excel(writer, index=False, sheet_name='Combined')
            
            # LWE Sheet
            lwe_districts = ["dantewada", "bastar", "baster", "sukma", "narayanpur", "mohla-manpur-chowki", "mohla manpur ambagarh chowki", "mohla-manpur-ambagarh chouki", "bijapur", "kanker", "mohla-manpur", "mohla manpur"]
            
            # Helper to check if a string is LWE
            def is_lwe(d_name):
                d_str = str(d_name).lower().strip()
                return any(lwe in d_str for lwe in lwe_districts)
                
            lwe_mask = df[dist_col].apply(is_lwe)
            lwe_df = df[lwe_mask]
            if not lwe_df.empty:
                lwe_summary = lwe_df.groupby(dist_col)[numeric_cols].sum().reset_index()
                lwe_summary.insert(0, 'S.No', range(1, len(lwe_summary) + 1))
                lwe_summary.to_excel(writer, index=False, sheet_name='LWE')
            else:
                pd.DataFrame(columns=['S.No', dist_col] + numeric_cols).to_excel(writer, index=False, sheet_name='LWE')
            
            # Sheet per Academic Year
            if 'Academic Year' in df.columns:
                for year in df['Academic Year'].unique():
                    if pd.notna(year):
                        year_df = df[df['Academic Year'] == year]
                        year_summary = year_df.groupby(dist_col)[numeric_cols].sum().reset_index()
                        year_summary.insert(0, 'S.No', range(1, len(year_summary) + 1))
                        safe_sheet_name = str(year).replace('/', '-').replace('*', '')[:31]
                        year_summary.to_excel(writer, index=False, sheet_name=safe_sheet_name)

        # Log to DB
        report_record = ReportHistory(
            report_type=report_type,
            filename=output_filename,
            original_filename=file.filename,
            file_path=output_filepath
        )
        db.add(report_record)
        db.commit()
        db.refresh(report_record)
        
        return {
            "success": True,
            "report_id": report_record.id,
            "filename": output_filename
        }
        
    except Exception as e:
        error_str = str(e).lower()
        if "excel file format cannot be determined" in error_str or "file is not a zip file" in error_str or "no engine for file type" in error_str or "invalid file" in error_str or "token" in error_str:
            friendly_msg = "Not a valid format. Please upload a proper CSV or Excel dataset."
            raise HTTPException(status_code=400, detail=friendly_msg)
        elif "are in the [columns]" in error_str or "keyerror" in error_str or "district name" in error_str:
            friendly_msg = "The uploaded dataset is missing required columns (like 'District Name'). Please ensure your file has the correct headers."
            raise HTTPException(status_code=400, detail=friendly_msg)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
def get_report_history(db: Session = Depends(get_db)):
    reports = db.query(ReportHistory).order_by(ReportHistory.report_type.asc(), ReportHistory.created_at.desc()).all()
    return reports

@router.get("/preview/{report_id}")
def preview_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(ReportHistory).filter(ReportHistory.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="Report file missing on server")
        
    try:
        dfs = pd.read_excel(report.file_path, sheet_name=None, engine='openpyxl')
        html_sheets = {}
        for sheet_name, df in dfs.items():
            df = clean_dataframe_mobile_cols(df)
            html_sheets[sheet_name] = df.to_html(classes='preview-table', index=False, border=0, na_rep='', float_format='{:.0f}'.format)
        return {"html_sheets": html_sheets, "multi_sheet": len(dfs) > 1, "html": html_sheets[list(dfs.keys())[0]]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate preview: {str(e)}")

@router.get("/download/{report_id}")
def download_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(ReportHistory).filter(ReportHistory.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="Report file missing on server")
        
    return FileResponse(
        path=report.file_path, 
        filename=report.filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@router.delete("/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(ReportHistory).filter(ReportHistory.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    # Attempt to delete file from disk
    if os.path.exists(report.file_path):
        try:
            os.remove(report.file_path)
        except:
            pass # We still want to delete DB record even if file deletion fails
            
    db.delete(report)
    db.commit()
    return {"success": True, "message": "Report deleted successfully"}

def is_lwe_district(district_name):
    if not district_name:
        return "No"
    
    d = str(district_name).lower().strip()
    lwe_aliases = [
        "bastar", "baster",
        "bijapur",
        "dantewada", "dakshin bastar", "dakshin bastar dantewada",
        "kanker", "uttar bastar", "uttar bastar kanker",
        "narayanpur",
        "sukma",
        "mohla-manpur-chowki", "mohla manpur ambagarh chowki", "mohla manpur", "mohla-manpur-ambagarh chouki"
    ]
    
    for alias in lwe_aliases:
        if alias in d:
            return "Yes"
    return "No"

def calculate_pending_days(start_date):
    if not start_date:
        return ""
    from datetime import date, datetime
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    delta = date.today() - start_date
    return f"{delta.days} Days pending"

def get_status_name(status_id, statuses_dict):
    return statuses_dict.get(status_id, "Pending")

@router.get("/system/district_wise_kit_count/details/{district_name}")
def preview_district_station_details(district_name: str, db: Session = Depends(get_db)):
    try:
        from backend.models.kit_registration import KitRegistration
        from backend.models.operator import Operator
        from backend.models.operator_station_mapping import OperatorStationMapping
        from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
        from backend.models.master_status import MasterStatus
        
        statuses = {s.id: s.name for s in db.query(MasterStatus).all()}
        
        d_kits = db.query(KitRegistration).filter(KitRegistration.district.ilike(district_name)).all()
        mappings = db.query(OperatorStationMapping).all()
        operators = db.query(Operator).all()
        onboardings = db.query(OperatorOnboardingDetail).all()
        
        mapping_dict = {m.station_id: m for m in mappings}
        op_dict = {o.id: o for o in operators}
        onb_dict = {o.station_id: o for o in onboardings}
        
        station_data = []
        analytics = {
            "pending_l1": 0,
            "pending_l2": 0,
            "pending_sd": 0,
            "inactive_op": 0,
            "inactive_st": 0
        }
        
        for i, k in enumerate(d_kits, 1):
            mapping = mapping_dict.get(k.station_id)
            op = op_dict.get(mapping.operator_id) if mapping and mapping.operator_id else None
            onb = onb_dict.get(k.station_id)
            
            l1_status = "L1 Done" if k.l1_status_id in [19, 2] or (l1_status and l1_status.lower() in ['done', 'approved', 'l1 done', 'l1_done']) else l1_status
            l2_status = "L2 Done" if k.l2_status_id in [2, 19] or (l2_status and l2_status.lower() in ['done', 'approved', 'l2 done', 'l2_done']) else l2_status
            
            op_name = op.name if op else ""
            sd_status = op.security_deposit_status if op else ""
            op_status = op.status if op else ""
            st_status = k.station_status or ""
            onb_status = onb.onboarding_status if onb else ""
            
            # Analytics Counting
            if str(l1_status).lower() not in ['done', 'yes', 'approved', 'l1 done', 'l1_done']: analytics["pending_l1"] += 1
            if str(l2_status).lower() not in ['done', 'yes', 'approved', 'l2 done', 'l2_done']: analytics["pending_l2"] += 1
            if not sd_status or sd_status.lower() not in ['yes', 'camp']: analytics["pending_sd"] += 1
            if not op_status or op_status.lower() != 'active': analytics["inactive_op"] += 1
            if not st_status or st_status.lower() != 'active': analytics["inactive_st"] += 1
            
            def fmt_st(st):
                return st.replace('_', ' ').title() if st else ""

            station_data.append({
                "S.No": i,
                "Station ID": k.station_id or "Not Allotted",
                "Operator Name": op_name,
                "L1 Status": l1_status if l1_status == "L1 Done" else fmt_st(l1_status),
                "L2 Status": l2_status if l2_status == "L2 Done" else fmt_st(l2_status),
                "Security Deposit": fmt_st(sd_status),
                "Station Status": fmt_st(st_status),
                "Operator Status": fmt_st(op_status),
                "Onboarding Status": fmt_st(onb_status)
            })
            
        import pandas as pd
        if not station_data:
            df = pd.DataFrame(columns=["S.No", "Station ID", "Operator Name", "L1 Status", "L2 Status", "Security Deposit", "Station Status", "Operator Status", "Onboarding Status"])
        else:
            df = pd.DataFrame(station_data)
            
        html_table = generate_clean_multiindex_html(df)
        return {"html": html_table, "count": len(d_kits), "analytics": analytics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch district details: {str(e)}")

@router.get("/system/lms_summary/details/{district_name}")
def preview_lms_district_details(district_name: str, db: Session = Depends(get_db)):
    try:
        from backend.models.lms import LMS
        from backend.models.candidate import Candidate
        
        lms_reqs = db.query(LMS).join(Candidate).filter(Candidate.district == district_name).all()
        
        station_data = []
        analytics = {
            "total": len(lms_reqs),
            "approved": 0,
            "pending": 0,
            "rejected": 0
        }
        
        for i, r in enumerate(lms_reqs, 1):
            st = (r.status or "").upper()
            if st == "APPROVED": analytics["approved"] += 1
            elif st == "PENDING": analytics["pending"] += 1
            elif st == "REJECTED": analytics["rejected"] += 1
            
            st_display = (r.status or "Pending").replace('_', ' ').title()
            
            station_data.append({
                "S.No": i,
                "Candidate ID": r.candidate.request_code if r.candidate else "",
                "Candidate Name": r.candidate.name if r.candidate else "",
                "Status": st_display,
                "Submitted At": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""
            })
            
        import pandas as pd
        if not station_data:
            df = pd.DataFrame(columns=["S.No", "Candidate ID", "Candidate Name", "Status", "Submitted At"])
        else:
            df = pd.DataFrame(station_data)
            
        html_table = generate_clean_multiindex_html(df)
        return {"html": html_table, "analytics": analytics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch LMS details: {str(e)}")

@router.get("/system/nseit_summary/details/{district_name}")
def preview_nseit_district_details(district_name: str, db: Session = Depends(get_db)):
    try:
        from backend.models.nseit import NSEITRequest
        from backend.models.candidate import Candidate
        
        nseit_reqs = db.query(NSEITRequest).join(Candidate).filter(Candidate.district == district_name).all()
        
        station_data = []
        analytics = {
            "total": len(nseit_reqs),
            "approved": 0,
            "pending": 0,
            "rejected": 0
        }
        
        for i, r in enumerate(nseit_reqs, 1):
            st = (r.status or "").upper()
            if st == "APPROVED": analytics["approved"] += 1
            elif st == "PENDING": analytics["pending"] += 1
            elif st == "REJECTED": analytics["rejected"] += 1
            
            st_display = (r.status or "Pending").replace('_', ' ').title()
            
            station_data.append({
                "S.No": i,
                "Candidate ID": r.candidate.request_code if r.candidate else "",
                "Candidate Name": r.candidate.name if r.candidate else "",
                "Status": st_display,
                "Submitted At": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""
            })
            
        import pandas as pd
        if not station_data:
            df = pd.DataFrame(columns=["S.No", "Candidate ID", "Candidate Name", "Status", "Submitted At"])
        else:
            df = pd.DataFrame(station_data)
            
        html_table = generate_clean_multiindex_html(df)
        return {"html": html_table, "analytics": analytics}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch NSEIT details: {str(e)}")

def get_system_report_dataframe(report_name: str, db: Session) -> pd.DataFrame:
    from backend.models.district import District
    from backend.models.candidate import Candidate
    from backend.models.lms import LMS
    from backend.models.nseit import NSEITRequest
    from backend.models.operator import Operator
    from backend.models.station_id import StationIDRequest
    from backend.models.l1_registration import L1RegistrationRequest
    from backend.models.kit_registration import KitRegistration
    from backend.models.operator_station_mapping import OperatorStationMapping
    from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
    from backend.models.master_status import MasterStatus
    from datetime import date, datetime
    
    if report_name == "lms_summary":
        districts = db.query(District).all()
        data = []
        for d in districts:
            lms_reqs = db.query(LMS).join(Candidate).filter(Candidate.district == d.district_code).all()
            data.append({
                "District Code": d.district_code,
                "District Name": d.district_name,
                "Total LMS Requests": len(lms_reqs),
                "Approved LMS": sum(1 for r in lms_reqs if r.status and r.status.upper() == "APPROVED"),
                "Pending LMS": sum(1 for r in lms_reqs if r.status and r.status.upper() == "PENDING"),
                "Rejected LMS": sum(1 for r in lms_reqs if r.status and r.status.upper() == "REJECTED")
            })
        if not data:
            columns = ["District Code", "District Name", "Total LMS Requests", "Approved LMS", "Pending LMS", "Rejected LMS"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(data)

    elif report_name == "nseit_summary":
        districts = db.query(District).all()
        data = []
        for d in districts:
            nseit_reqs = db.query(NSEITRequest).join(Candidate).filter(Candidate.district == d.district_code).all()
            data.append({
                "District Code": d.district_code,
                "District Name": d.district_name,
                "Total NSEIT Requests": len(nseit_reqs),
                "Approved NSEIT": sum(1 for r in nseit_reqs if r.status and r.status.upper() == "APPROVED"),
                "Pending NSEIT": sum(1 for r in nseit_reqs if r.status and r.status.upper() == "PENDING"),
                "Rejected NSEIT": sum(1 for r in nseit_reqs if r.status and r.status.upper() == "REJECTED")
            })
        if not data:
            columns = ["District Code", "District Name", "Total NSEIT Requests", "Approved NSEIT", "Pending NSEIT", "Rejected NSEIT"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(data)
        
    elif report_name == "operator_onboarding_status":
        onboardings = db.query(OperatorOnboardingDetail).join(Operator).all()
        data = []
        for ob in onboardings:
            op = ob.operator
            d = db.query(District).filter(District.district_code == op.district_id).first()
            d_name = d.district_name if d else str(op.district_id)
            
            data.append({
                "Operator Code": op.user_code,
                "Operator Name": op.name,
                "Mobile": clean_mobile_val(op.mobile),
                "Email": op.email,
                "District": d_name,
                "Station ID": ob.station_id,
                "Onboarding Status": ob.onboarding_status,
                "Kit Working Status": ob.ask_kit_working_status,
                "Permitted 18+": ob.permitted_18_plus,
                "Created At": ob.created_at.strftime("%Y-%m-%d %H:%M:%S") if ob.created_at else ""
            })
        if not data:
            columns = ["Operator Code", "Operator Name", "Mobile", "Email", "District", "Station ID", "Onboarding Status", "Kit Working Status", "Permitted 18+", "Created At"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(data)
        
    elif report_name == "station_kit_log":
        requests = db.query(StationIDRequest).all()
        data = []
        for req in requests:
            d = db.query(District).filter(District.district_code == req.district_id).first()
            d_name = d.district_name if d else str(req.district_id)
            
            l1 = None
            if req.station_id_inserted:
                l1 = db.query(L1RegistrationRequest).filter(L1RegistrationRequest.station_id == req.station_id_inserted).first()
                
            data.append({
                "Request No": req.request_no,
                "DC Name": req.dc.username if req.dc else "",
                "District": d_name,
                "Model": req.model,
                "Number of Kits": req.number_of_kits,
                "Station ID Request Status": req.status,
                "Station ID Assigned": req.station_id_inserted or "Not Assigned",
                "Machine ID (L1)": l1.machine_id if l1 else "N/A",
                "L1 Status": l1.status if l1 else "N/A",
                "Submitted At": req.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if req.submitted_at else ""
            })
        if not data:
            columns = ["Request No", "DC Name", "District", "Model", "Number of Kits", "Station ID Request Status", "Station ID Assigned", "Machine ID (L1)", "L1 Status", "Submitted At"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(data)
        
    elif report_name == "l1_pending_list":
        statuses = {s.id: s.name for s in db.query(MasterStatus).all()}
        kits = db.query(KitRegistration).all()
        l1_data = []
        sr_no = 1
        for k in kits:
            status_name = get_status_name(k.l1_status_id, statuses)
            if status_name.lower() not in ['done', 'approved', 'yes']:
                l1_data.append({
                    "SR No.": sr_no,
                    "District": k.district,
                    "Is LWE District": is_lwe_district(k.district),
                    "Kit Slot": k.category,
                    "Station ID": k.station_id,
                    "Station ID Provided Date": k.station_id_provided_date,
                    "L1 Status": "No",
                    "L1 Status Date /(Pending days)": calculate_pending_days(k.station_id_provided_date)
                })
                sr_no += 1
        if not l1_data:
            columns = ["SR No.", "District", "Is LWE District", "Kit Slot", "Station ID", "Station ID Provided Date", "L1 Status", "L1 Status Date /(Pending days)"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(l1_data)
        
    elif report_name == "l2_pending_list":
        statuses = {s.id: s.name for s in db.query(MasterStatus).all()}
        kits = db.query(KitRegistration).all()
        l2_data = []
        sr_no = 1
        for k in kits:
            l1_name = get_status_name(k.l1_status_id, statuses)
            l2_name = get_status_name(k.l2_status_id, statuses)
            if l1_name.lower() in ['done', 'approved', 'yes'] and l2_name.lower() not in ['done', 'approved', 'yes']:
                l2_data.append({
                    "SR No.": sr_no,
                    "District": k.district,
                    "Is LWE District": is_lwe_district(k.district),
                    "Kit Slot": k.category,
                    "Station Id": k.station_id,
                    "Machine Id": k.machine_id,
                    "Laptop Serial No.": k.laptop_serial_no,
                    "Laptop Name": k.laptop_name,
                    "Station ID Provided Date": k.station_id_provided_date,
                    "L1 Status": "Yes",
                    "L1 Done Date": k.l1_done_date,
                    "L2 Status": l2_name,
                    "L2 Done Date /(Pending days)": calculate_pending_days(k.l1_done_date),
                    "Current Stay Status": l2_name
                })
                sr_no += 1
        if not l2_data:
            columns = ["SR No.", "District", "Is LWE District", "Kit Slot", "Station Id", "Machine Id", "Laptop Serial No.", "Laptop Name", "Station ID Provided Date", "L1 Status", "L1 Done Date", "L2 Status", "L2 Done Date /(Pending days)", "Current Stay Status"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(l2_data)

    elif report_name == "operator_list":
        kits = db.query(KitRegistration).all()
        operators = db.query(Operator).all()
        mappings = db.query(OperatorStationMapping).all()
        districts_list = db.query(District).all()
        dist_dict = {d.district_code: d.district_name for d in districts_list}
        op_data = []
        sr_no = 1
        for o in operators:
            op_mapping = [m for m in mappings if m.operator_id == o.id]
            kit = next((k for k in kits if op_mapping and k.station_id == op_mapping[0].station_id), None)
            dist_name = kit.district if kit else dist_dict.get(o.district_id, "")
            
            op_data.append({
                "SR No.": sr_no,
                "District": dist_name,
                "Is LWE District": is_lwe_district(dist_name),
                "Operator Name": o.name,
                "Operator Id": o.user_code,
                "Operator Mobile": clean_mobile_val(o.mobile),
                "SD Status": o.security_deposit_status,
                "Security Deposit Date": o.security_deposit_date,
                "Block": kit.block if kit else "",
                "Location Category": kit.category if kit else "",
                "Locality": kit.locality if kit else "",
                "ASK (Aadhaar Sewa Kendra) Address": kit.ask_address if kit else "",
                "Operator Activation Status (User Credentials Created)": o.status,
                "Operator In-active Reason": o.inactive_reason,
                "Operator In-active Date": o.inactive_date,
                "NSEIT Certificate No": o.nseit_certificate_number,
                "Certificate Issue Date": o.nseit_certification_date,
                "Certificate Validity": o.nseit_certificate_expiry_date,
                "Create Date": o.created_at,
                "Update Date": o.updated_at
            })
            sr_no += 1
        if not op_data:
            columns = ["SR No.", "District", "Is LWE District", "Operator Name", "Operator Id", "Operator Mobile", "SD Status", "Security Deposit Date", "Block", "Location Category", "Locality", "ASK (Aadhaar Sewa Kendra) Address", "Operator Activation Status (User Credentials Created)", "Operator In-active Reason", "Operator In-active Date", "NSEIT Certificate No", "Certificate Issue Date", "Certificate Validity", "Create Date", "Update Date"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(op_data)

    elif report_name == "onboard_pending_list":
        statuses = {s.id: s.name for s in db.query(MasterStatus).all()}
        kits = db.query(KitRegistration).all()
        onboardings = db.query(OperatorOnboardingDetail).all()
        onb_dict = {o.station_id: o for o in onboardings}
        onb_data = []
        sr_no = 1
        for k in kits:
            l2_name = get_status_name(k.l2_status_id, statuses)
            if l2_name.lower() in ['done', 'approved', 'yes']:
                onb = onb_dict.get(k.station_id)
                status_onb = onb.onboarding_status if onb else "Pending"
                if status_onb.lower() not in ['done', 'active', 'yes']:
                    onb_data.append({
                        "SR No.": sr_no,
                        "District": k.district,
                        "Is LWE District": is_lwe_district(k.district),
                        "Kit Slot": k.category,
                        "Station Id": k.station_id,
                        "Machine Id": k.machine_id,
                        "Laptop Serial No.": k.laptop_serial_no,
                        "Laptop Name": k.laptop_name,
                        "Station ID Provided Date": k.station_id_provided_date,
                        "L1 Status": "Yes",
                        "L1 Done Date": k.l1_done_date,
                        "L2 Status": "Yes",
                        "L2 Done Date": k.l2_done_date,
                        "On-Boarding Status": status_onb,
                        "On-Boarding Date /(Pending days)": calculate_pending_days(k.l2_done_date)
                    })
                    sr_no += 1
        if not onb_data:
            columns = ["SR No.", "District", "Is LWE District", "Kit Slot", "Station Id", "Machine Id", "Laptop Serial No.", "Laptop Name", "Station ID Provided Date", "L1 Status", "L1 Done Date", "L2 Status", "L2 Done Date", "On-Boarding Status", "On-Boarding Date /(Pending days)"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(onb_data)

    elif report_name == "district_wise_kit_count":
        statuses = {s.id: s.name for s in db.query(MasterStatus).all()}
        kits = db.query(KitRegistration).all()
        operators = db.query(Operator).all()
        mappings = db.query(OperatorStationMapping).all()
        onboardings = db.query(OperatorOnboardingDetail).all()
        
        mapping_dict = {m.station_id: m for m in mappings}
        op_dict = {o.id: o for o in operators}
        onb_dict = {o.station_id: o for o in onboardings}
        
        # Include all master districts from DB
        master_districts = db.query(District).order_by(District.district_name.asc()).all()
        all_d_names = [d.district_name for d in master_districts if d.district_name]
        
        # Include any extra kit districts if not in master list
        kit_d_names = list(set([k.district for k in kits if k.district]))
        for kd in kit_d_names:
            if not any(kd.strip().lower() == md.strip().lower() for md in all_d_names):
                all_d_names.append(kd)

        dist_data = []
        sr_no = 1
        for d in all_d_names:
            d_kits = [k for k in kits if k.district and str(k.district).strip().lower() == str(d).strip().lower()]
            
            sd_yes = 0; sd_pending = 0; sd_camp = 0
            l1_yes = 0; l1_no = 0; l2_yes = 0; l2_no = 0; l2_chips = 0; l2_uidai = 0
            op_active = 0; op_inactive = 0; onb_active = 0; onb_inactive = 0
            st_active = 0; st_inactive = 0; ask_active = 0; ask_inactive = 0
            
            for k in d_kits:
                l1_name = get_status_name(k.l1_status_id, statuses).lower()
                if l1_name in ['done', 'yes', 'approved']: l1_yes += 1
                else: l1_no += 1
                
                l2_name = get_status_name(k.l2_status_id, statuses).lower()
                if l2_name in ['done', 'yes', 'approved']: l2_yes += 1
                elif 'chips' in l2_name: l2_chips += 1
                elif 'uidai' in l2_name: l2_uidai += 1
                else: l2_no += 1
                
                if (k.station_status or '').lower() == 'active': st_active += 1
                else: st_inactive += 1
                
                mapping = mapping_dict.get(k.station_id)
                if mapping and mapping.operator_id:
                    op = op_dict.get(mapping.operator_id)
                    if op:
                        if op.security_deposit_status == 'Yes': sd_yes += 1
                        elif op.security_deposit_status == 'Camp': sd_camp += 1
                        else: sd_pending += 1
                        
                        if (op.status or '').lower() == 'active': op_active += 1
                        else: op_inactive += 1
                    else:
                        sd_pending += 1
                        op_inactive += 1
                else:
                    sd_pending += 1
                    op_inactive += 1

                onb = onb_dict.get(k.station_id)
                if onb:
                    if (onb.onboarding_status or '').lower() in ['active', 'yes', 'done', 'approved']: onb_active += 1
                    else: onb_inactive += 1
                    
                    if (onb.ask_kit_working_status or '').lower() in ['active', 'yes', 'done', 'working']: ask_active += 1
                    else: ask_inactive += 1
                else:
                    onb_inactive += 1
                    ask_inactive += 1
                    
            allotted_kits = [k for k in d_kits if k.station_id and str(k.station_id).strip() and str(k.station_id).lower() not in ['none', 'null', '']]
            dist_data.append({
                "S.No": sr_no,
                "District": d,
                "Is LWE District": is_lwe_district(d),
                "Total Machine": len(d_kits),
                "Alloted Station Id": len(allotted_kits),
                "Security Deposit (Camp)": sd_camp,
                "Security Deposit (Yes)": sd_yes,
                "Security Deposit (Pending)": sd_pending,
                "L1 Status (Yes)": l1_yes,
                "L1 Status (No)": l1_no,
                "L2 Status (Yes)": l2_yes,
                "L2 Status (No)": l2_no,
                "L2 Status (Send to CHiPS)": l2_chips,
                "L2 Status (Send to UIDAI)": l2_uidai,
                "Operator Activation (Active)": op_active,
                "Operator Activation (Inactive SentToChips)": op_inactive,
                "Operator Onboarding (Active)": onb_active,
                "Operator Onboarding (Inactive)": onb_inactive,
                "Station ID Status (Active)": st_active,
                "Station ID Status (Inactive)": st_inactive,
                "ASK Kit Working Status (Active)": ask_active,
                "ASK Kit Working Status (Inactive)": ask_inactive,
            })
            sr_no += 1
            
        cols = pd.MultiIndex.from_tuples([
            ('S.No', ''),
            ('District', ''),
            ('Is LWE District', ''),
            ('Total Machine', ''),
            ('Alloted Station Id', ''),
            ('Security Deposit', 'Camp'),
            ('Security Deposit', 'Yes'),
            ('Security Deposit', 'Pending'),
            ('L1 Status', 'Yes'),
            ('L1 Status', 'No'),
            ('L2 Status', 'Yes'),
            ('L2 Status', 'No'),
            ('L2 Status', 'Send to CHiPS'),
            ('L2 Status', 'Send to UIDAI'),
            ('Operator Activation Status (User Credentials Created)', 'Active'),
            ('Operator Activation Status (User Credentials Created)', 'Inactive SentToChips'),
            ('Operator Onboarding Status (After L2 Activation)', 'Active'),
            ('Operator Onboarding Status (After L2 Activation)', 'Inactive'),
            ('Station ID Status', 'Active'),
            ('Station ID Status', 'Inactive'),
            ('ASK Kit Working Status', 'Active'),
            ('ASK Kit Working Status', 'Inactive')
        ])
        
        raw_cols = ["S.No", "District", "Is LWE District", "Total Machine", "Alloted Station Id", "Security Deposit (Camp)", "Security Deposit (Yes)", "Security Deposit (Pending)", "L1 Status (Yes)", "L1 Status (No)", "L2 Status (Yes)", "L2 Status (No)", "L2 Status (Send to CHiPS)", "L2 Status (Send to UIDAI)", "Operator Activation (Active)", "Operator Activation (Inactive SentToChips)", "Operator Onboarding (Active)", "Operator Onboarding (Inactive)", "Station ID Status (Active)", "Station ID Status (Inactive)", "ASK Kit Working Status (Active)", "ASK Kit Working Status (Inactive)"]

        if not dist_data:
            df = pd.DataFrame(columns=raw_cols)
        else:
            df = pd.DataFrame(dist_data)
            df = df.reindex(columns=raw_cols)
            
        df.columns = cols
        return df

    elif report_name == "kit_tracker":
        statuses = {s.id: s.name for s in db.query(MasterStatus).all()}
        kits = db.query(KitRegistration).all()
        operators = db.query(Operator).all()
        mappings = db.query(OperatorStationMapping).all()
        onboardings = db.query(OperatorOnboardingDetail).all()
        
        mapping_dict = {m.station_id: m for m in mappings}
        op_dict = {o.id: o for o in operators}
        onb_dict = {o.station_id: o for o in onboardings}
        
        data = []
        sr_no = 1
        for k in kits:
            op = None
            onb = None
            mapping = mapping_dict.get(k.station_id)
            if mapping:
                op = op_dict.get(mapping.operator_id)
                onb = onb_dict.get(k.station_id)
                
            l1_status_name = get_status_name(k.l1_status_id, statuses)
            l2_status_name = get_status_name(k.l2_status_id, statuses)
            
            data.append({
                "SR No.": sr_no,
                "District": k.district,
                "Is LWE District": is_lwe_district(k.district),
                "Kit Slot": k.category,
                "Station ID": k.station_id,
                "Station ID Allotted Date": k.station_id_provided_date,
                "Machine ID": k.machine_id,
                "Laptop Serial No.": k.laptop_serial_no,
                "Laptop Name": k.laptop_name,
                "Operator Name": op.name if op else "",
                "Operator Id": op.user_code if op else "",
                "Operator Mobile": clean_mobile_val(op.mobile if op else ""),
                "Security Deposit Status": op.security_deposit_status if op else "",
                "Security Deposit Date": op.security_deposit_date if op else "",
                "L1 Status": l1_status_name,
                "L1 Date": k.l1_done_date,
                "L2 Status": l2_status_name,
                "L2 Date": k.l2_done_date,
                "Block": k.block,
                "Category": k.category,
                "Locality": k.locality,
                "ASK Address": k.ask_address,
                "Operator Status": op.status if op else "",
                "Inactive Reason": op.inactive_reason if op else "",
                "Inactive Date": op.inactive_date if op else "",
                "18+ Permit": onb.permitted_18_plus if onb else "",
                "Station Status": k.station_status,
                "Onboarding Status": onb.onboarding_status if onb else "",
                "Onboard Date": onb.onboard_date if onb else "",
                "Kit Working": onb.ask_kit_working_status if onb else "",
                "Visit Status": onb.visit_status if onb else "",
                "Visit Date": onb.visit_date if onb else "",
                "Remark": onb.remark if onb else ""
            })
            sr_no += 1
            
        if not data:
            columns = [
                "SR No.", "District", "Is LWE District", "Kit Slot", "Station ID", "Station ID Allotted Date", 
                "Machine ID", "Laptop Serial No.", "Laptop Name", "Operator Name", "Operator Id", 
                "Operator Mobile", "Security Deposit Status", "Security Deposit Date", "L1 Status", 
                "L1 Date", "L2 Status", "L2 Date", "Block", "Category", "Locality", "ASK Address", 
                "Operator Status", "Inactive Reason", "Inactive Date", "18+ Permit", "Station Status", 
                "Onboarding Status", "Onboard Date", "Kit Working", "Visit Status", "Visit Date", "Remark"
            ]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(data)
        
    else:
        raise ValueError("Invalid report name")

def _get_df_col(df, name):
    if name in df.columns:
        return name
    for col in df.columns:
        if isinstance(col, tuple) and col[0] == name:
            return col
    return None

def add_total_row(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    total_row = {}
    is_multi = isinstance(df.columns, pd.MultiIndex)

    for idx, col in enumerate(df.columns):
        col_name = str(col[0] if is_multi else col).strip().lower()
        if idx == 0 or 's.no' in col_name or 'sr' in col_name:
            total_row[col] = "Total"
        elif 'district' in col_name or 'name' in col_name or 'lwe' in col_name:
            total_row[col] = ""
        else:
            try:
                numeric_vals = pd.to_numeric(df[col], errors='coerce').fillna(0)
                total_row[col] = int(numeric_vals.sum())
            except Exception:
                total_row[col] = ""

    total_df = pd.DataFrame([total_row])
    if is_multi:
        total_df.columns = df.columns
    return pd.concat([df, total_df], ignore_index=True)

def generate_clean_multiindex_html(df, table_class='preview-table'):
    if not isinstance(df.columns, pd.MultiIndex):
        return df.to_html(classes=table_class, index=False, border=0)
        
    headers = list(df.columns)
    
    row1_html = "<tr>"
    row2_html = "<tr>"
    
    i = 0
    while i < len(headers):
        top, sub = headers[i]
        if sub == '':
            row1_html += f'<th rowspan="2" style="vertical-align: middle; text-align: center; background: #0f172a; color: white; font-weight: 700; border-right: 1px solid #334155; padding: 10px 14px;">{top}</th>'
            i += 1
        else:
            count = 0
            sub_cells = []
            while i + count < len(headers) and headers[i + count][0] == top:
                sub_cells.append(headers[i + count][1])
                count += 1
                
            # Clean up long top header titles for crisp display
            display_top = top
            if "(" in top:
                parts = top.split("(", 1)
                display_top = f'<div>{parts[0].strip()}</div><div style="font-size: 10px; font-weight: 400; opacity: 0.85;">({parts[1]}</div>'
                
            row1_html += f'<th colspan="{count}" style="text-align: center; background: #0f172a; color: white; font-weight: 700; border-right: 1px solid #334155; border-bottom: 1px solid #334155; padding: 8px 12px;">{display_top}</th>'
            
            for sc in sub_cells:
                display_sc = sc
                if sc == "Inactive SentToChips":
                    display_sc = "Inactive (Sent to CHiPS)"
                row2_html += f'<th style="text-align: center; background: #f1f5f9; color: #334155; font-weight: 600; font-size: 11px; border-right: 1px solid #cbd5e1; border-bottom: 2px solid #cbd5e1; padding: 6px 10px;">{display_sc}</th>'
            i += count
            
    row1_html += "</tr>"
    row2_html += "</tr>"
    
    tbody_html = "<tbody>\n"
    for row_idx, row in df.iterrows():
        is_total = (str(row.iloc[0]).strip().lower() == "total" or str(row.iloc[1]).strip().lower() == "total")
        row_cls = ' class="total-row"' if is_total else ''
        bg_color = "#e2e8f0" if is_total else ("#ffffff" if row_idx % 2 == 0 else "#f8fafc")
        border_style = "border-top: 2px solid #64748b; border-bottom: 2px solid #64748b;" if is_total else "border-bottom: 1px solid #e2e8f0;"
        tbody_html += f'  <tr{row_cls} style="background: {bg_color}; font-weight: {"700" if is_total else "normal"};">\n'
        for col_idx, val in enumerate(row):
            align = "left" if (col_idx in [0, 1] and not is_total) else ("left" if is_total and col_idx == 0 else "center")
            font_wt = "700" if (is_total or col_idx == 1) else "400"
            td_bg = "background: #e2e8f0;" if is_total else ""
            tbody_html += f'    <td style="text-align: {align}; font-weight: {font_wt}; padding: 10px 14px; {border_style} border-right: 1px solid #cbd5e1; color: #0f172a; {td_bg}">{val}</td>\n'
        tbody_html += "  </tr>\n"
    tbody_html += "</tbody>"
    
    return f'''<table class="{table_class}" style="width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; font-family: inherit;">
  <thead>
    {row1_html}
    {row2_html}
  </thead>
  {tbody_html}
</table>'''

DIVISIONS = {
    "bilaspur": ["bilaspur", "gaurella-pendra-marwahi", "gaurela-pendra-marwahi", "janjgir-champa", "janjgir", "korba", "mungeli", "raigarh", "sakti", "sarangarh-bilaigarh", "sarangarh"],
    "raipur": ["baloda bazar-bhatapara", "balodabazar", "baloda bazar", "dhamtari", "gariaband", "gariyaband", "mahasamund", "raipur"],
    "durg": ["balod", "bemetara", "durg", "kabirdham (kawardha)", "kabirdham", "kawardha", "khairagarh-chhuikhadan-gandai", "khairagarh", "mohla-manpur-ambagarh chowki", "mohla", "rajnandgaon"],
    "bastar": ["bastar", "bijapur", "dakshin bastar (dantewada)", "dantewada", "uttar bastar (kanker)", "kanker", "kondagaon", "narayanpur", "sukma"],
    "surguja": ["balrampur-ramanujganj", "balrampur", "jashpur", "koriya", "manendragarh-chirmiri-bharatpur", "manendragarh", "surajpur", "surguja"]
}

def apply_system_filters(df, lwe: bool, division: Optional[str], district: Optional[str]):
    dist_col = _get_df_col(df, "District") or _get_df_col(df, "District Name")
    if district and dist_col:
        df = df[df[dist_col].astype(str).str.strip().str.lower() == str(district).strip().lower()]
        
    if division and dist_col:
        div_key = division.lower()
        if div_key in DIVISIONS:
            allowed = DIVISIONS[div_key]
            def match_div(d_name):
                d_name_lower = str(d_name).strip().lower()
                for a in allowed:
                    if a in d_name_lower or d_name_lower in a:
                        return True
                return False
            df = df[df[dist_col].apply(match_div)]

    lwe_col = _get_df_col(df, "Is LWE District")
    if lwe and lwe_col:
        df = df[df[lwe_col] == "Yes"]
        
    if district or division or lwe:
        df = df.reset_index(drop=True)
        sno_col = _get_df_col(df, "SR No.") or _get_df_col(df, "S.No")
        if sno_col:
            df[sno_col] = range(1, len(df) + 1)
            
    if lwe_col:
        df = df.drop(columns=[lwe_col])
        
    return df

@router.get("/system/{report_name}/preview")
def preview_system_report(report_name: str, lwe: bool = False, division: Optional[str] = None, district: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        df = get_system_report_dataframe(report_name, db)
        df = apply_system_filters(df, lwe, division, district)
        df = clean_dataframe_mobile_cols(df)
        df = df.fillna("")
        if report_name in ["district_wise_kit_count", "lms_summary", "nseit_summary"]:
            df = add_total_row(df)
        html_table = generate_clean_multiindex_html(df)
        return {"html": html_table}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate preview: {str(e)}")

@router.get("/system/{report_name}/download")
def download_system_report(report_name: str, lwe: bool = False, division: Optional[str] = None, district: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        df = get_system_report_dataframe(report_name, db)
        df = apply_system_filters(df, lwe, division, district)
        df = clean_dataframe_mobile_cols(df)
        df = df.fillna("")
        if report_name in ["district_wise_kit_count", "lms_summary", "nseit_summary"]:
            df = add_total_row(df)
            
        output = io.BytesIO()
        sheet_name = 'Kit Status' if report_name == 'district_wise_kit_count' else 'System Report'
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if isinstance(df.columns, pd.MultiIndex):
                first_col = df.columns[0]
                df_export = df.set_index(first_col)
                df_export.to_excel(writer, index=True, sheet_name=sheet_name)
                
                ws = writer.sheets[sheet_name]
                ws.cell(row=1, column=1, value='S.No')
                if not ws.cell(row=1, column=2).value:
                    ws.cell(row=1, column=2, value='District')
                    
                val_row3 = str(ws.cell(row=3, column=1).value or '')
                if 'S.No' in val_row3 or 'tuple' in val_row3 or val_row3.startswith('('):
                    ws.delete_rows(3)
            else:
                df.to_excel(writer, index=False, sheet_name=sheet_name)
            
        output.seek(0)
        from fastapi.responses import Response
        headers = {
            'Content-Disposition': f'attachment; filename="system_{report_name}.xlsx"'
        }
        return Response(content=output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")
