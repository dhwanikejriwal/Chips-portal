from typing import Optional
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, Query
from fastapi.responses import Response, FileResponse
from sqlalchemy.orm import Session
import pandas as pd
import io
import os
import uuid
from datetime import datetime
from backend.database import get_db
from backend.models.report import ReportHistory
from backend.utils.district_mapper import normalize_district_name

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
            desired = ['Total Pending', 'Total Rejected', 'Total Approved']
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
                'Total Student',
                'Total Students AADHAAR Provided',
                'AADHAAR Verified-Passed(Yes)',
                'AADHAAR Verified-Failed(No)',
                'AADHAAR Verified-To be Done',
                'MBU Pending (Age 5-15)', 
                'MBU Pending (Age 15 and above)',
                'MBU Not Required',
                'MBU Not Applicable',
                'Status Check to be done'
            ]
            matched = []
            for col in df.columns:
                col_clean = str(col).strip().lower()
                for d in desired:
                    d_clean = d.lower()
                    if col_clean == d_clean or (d_clean == 'total student' and col_clean in ['total student', 'total students']):
                        matched.append(col)
                        break
            if not matched:
                raise Exception(f"Invalid dataset uploaded for MBU District Wise. Please ensure you uploaded the correct dataset.")
            df = df[keep_cols + matched]
            
        elif report_type == 'cenetarian_district_report':
            desired = ['Pending Total', 'Not verifiable Total', 'Deceased Total', 'Alive Total']
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
            if 'MBU Pending (Age 5-15)' in df.columns and 'MBU Pending (Age 15 and above)' in df.columns:
                df['Total Pending'] = df['MBU Pending (Age 5-15)'] + df['MBU Pending (Age 15 and above)']
            else:
                df['Total Pending'] = df[numeric_cols].sum(axis=1)
            numeric_cols.append('Total Pending')

        if report_type == 'cenetarian_district_report' and numeric_cols:
            total_reqs = pd.Series(0, index=df.index)
            for c in df.columns:
                if str(c).strip().lower() in [d.lower() for d in ['Pending Total', 'Not verifiable Total', 'Deceased Total', 'Alive Total']]:
                    total_reqs += df[c].fillna(0)
            df['Total Requests'] = total_reqs
            numeric_cols.append('Total Requests')

        if report_type == '18_plus_pendency' and numeric_cols:
            total_reqs_18 = pd.Series(0, index=df.index)
            for c in df.columns:
                if str(c).strip().lower() in [d.lower() for d in ['Total Pending', 'Total Rejected', 'Total Approved']]:
                    total_reqs_18 += df[c].fillna(0)
            df['Total Requests'] = total_reqs_18
            numeric_cols.append('Total Requests')

        df = df[~df[dist_col].astype(str).str.strip().isin(['(1)', '1', 'Total', 'TOTAL', ''])]
        df[dist_col] = df[dist_col].apply(normalize_district_name)

        if district:
            df = df[df[dist_col].astype(str).str.lower() == normalize_district_name(district).lower()]

        # Write to multi-sheet excel
        with pd.ExcelWriter(output_filepath, engine='openpyxl') as writer:
            
            def add_derived_cols(summary_df):
                if report_type == 'mbu_district_wise' and 'Total Pending' in summary_df.columns:
                    passed_yes_col = next((c for c in summary_df.columns if 'passed(yes)' in str(c).lower() or 'verified-passed' in str(c).lower()), None)
                    not_app_col = next((c for c in summary_df.columns if 'not applicable' in str(c).lower()), None)
                    if passed_yes_col:
                        denom = summary_df[passed_yes_col] - (summary_df[not_app_col] if not_app_col else 0)
                    elif 'Total Students AADHAAR Provided' in summary_df.columns:
                        denom = summary_df['Total Students AADHAAR Provided']
                    else:
                        denom = 1
                    summary_df['MBU Pendency %'] = ((summary_df['Total Pending'] / denom.replace(0, 1)) * 100).round(2).astype(str) + '%'
                elif report_type == 'cenetarian_district_report':
                    pending_col = next((c for c in summary_df.columns if str(c).strip().lower() == 'pending total'), None)
                    if 'Total Requests' in summary_df.columns and pending_col:
                        summary_df['Pending %'] = ((summary_df[pending_col] / summary_df['Total Requests'].replace(0, 1)) * 100).round(2).astype(str) + '%'
                elif report_type == '18_plus_pendency':
                    pending_col = next((c for c in summary_df.columns if str(c).strip().lower() == 'total pending'), None)
                    if 'Total Requests' in summary_df.columns and pending_col:
                        summary_df['Pendency %'] = ((summary_df[pending_col] / summary_df['Total Requests'].replace(0, 1)) * 100).round(2).astype(str) + '%'
                return summary_df

            # Combined Sheet
            combined_df = df.groupby(dist_col)[numeric_cols].sum().reset_index()
            
            # Ensure all master districts from DB appear in Combined sheet
            from backend.models.district import District
            master_districts = [normalize_district_name(d.district_name) for d in db.query(District).order_by(District.district_name.asc()).all() if d.district_name]
            master_districts = list(dict.fromkeys(master_districts))
            existing_dists = combined_df[dist_col].astype(str).str.strip().tolist()
            missing_rows = []
            for md in master_districts:
                if md not in existing_dists:
                    row_dict = {dist_col: md}
                    for nc in numeric_cols:
                        row_dict[nc] = 0
                    missing_rows.append(row_dict)
            if missing_rows:
                missing_df = pd.DataFrame(missing_rows)
                combined_df = pd.concat([combined_df, missing_df], ignore_index=True)
                combined_df = combined_df.sort_values(by=[dist_col]).reset_index(drop=True)

            combined_df = add_derived_cols(combined_df)
            combined_df.insert(0, 'S.No', range(1, len(combined_df) + 1))

            def filter_mbu_cols(summary_df, main_col_name):
                if report_type != 'mbu_district_wise':
                    return summary_df
                target_order = [
                    'S.No',
                    main_col_name,
                    'Total Student',
                    'Total Students AADHAAR Provided',
                    'MBU Pending (Age 5-15)',
                    'MBU Pending (Age 15 and above)',
                    'Total Pending',
                    'MBU Pendency %'
                ]
                avail = list(summary_df.columns)
                final_cols = []
                for t in target_order:
                    for c in avail:
                        c_clean = str(c).strip().lower()
                        t_clean = str(t).strip().lower()
                        if c_clean == t_clean or (t_clean == 'total student' and c_clean in ['total student', 'total students']):
                            final_cols.append(c)
                            break
                return summary_df[final_cols]

            combined_export = filter_mbu_cols(combined_df, dist_col)
            combined_export.to_excel(writer, index=False, sheet_name='Combined')
            
            # LWE and Division Sheets (matching Kit Tracker tabs: Combined, LWE, Bilaspur Div, Raipur Div, Durg Div, Bastar Div, Surguja Div)
            if report_type in ['mbu_district_wise', 'cenetarian_district_report', '18_plus_pendency']:
                lwe_mask = df[dist_col].apply(lambda d: is_lwe_district(d) == "Yes")
                lwe_df = df[lwe_mask]
                if not lwe_df.empty:
                    lwe_summary = lwe_df.groupby(dist_col)[numeric_cols].sum().reset_index()
                    lwe_summary = add_derived_cols(lwe_summary)
                    lwe_summary.insert(0, 'S.No', range(1, len(lwe_summary) + 1))
                    lwe_export = filter_mbu_cols(lwe_summary, dist_col)
                    lwe_export.to_excel(writer, index=False, sheet_name='LWE')
                else:
                    pd.DataFrame(columns=['S.No', dist_col] + numeric_cols).to_excel(writer, index=False, sheet_name='LWE')

                DIVISIONS_TABS = {
                    "Bilaspur Div": ["bilaspur", "gaurella-pendra-marwahi", "gaurela-pendra-marwahi", "gpm", "janjgir-champa", "janjgir", "champa", "korba", "mungeli", "raigarh", "sakti", "sarangarh-bilaigarh", "sarangarh"],
                    "Raipur Div": ["baloda bazar-bhatapara", "balodabazar", "baloda bazar", "dhamtari", "gariaband", "gariyaband", "mahasamund", "raipur"],
                    "Durg Div": ["balod", "bemetara", "durg", "kabirdham (kawardha)", "kabirdham", "kawardha", "kabeerdham", "khairagarh-chhuikhadan-gandai", "khairagarh", "mohla-manpur-chowki", "mohla-manpur-ambagarh chowki", "mohla-manpur-ambagarh chouki", "mohla", "rajnandgaon"],
                    "Bastar Div": ["bastar", "baster", "bijapur", "dakshin bastar (dantewada)", "dantewada", "uttar bastar (kanker)", "kanker", "kondagaon", "narayanpur", "sukma"],
                    "Surguja Div": ["balrampur-ramanujganj", "balrampur", "jashpur", "koriya", "korea", "manendragarh-chirmiri-bharatpur", "manendragarh", "surajpur", "surguja"]
                }

                for div_name, allowed in DIVISIONS_TABS.items():
                    div_mask = df[dist_col].apply(lambda d: any(a in str(d).lower().strip() or str(d).lower().strip() in a for a in allowed))
                    div_df = df[div_mask]
                    if not div_df.empty:
                        div_summary = div_df.groupby(dist_col)[numeric_cols].sum().reset_index()
                        div_summary = add_derived_cols(div_summary)
                        div_summary.insert(0, 'S.No', range(1, len(div_summary) + 1))
                        div_export = filter_mbu_cols(div_summary, dist_col)
                        div_export.to_excel(writer, index=False, sheet_name=div_name)
            
            # Sheet per Academic Year
            if 'Academic Year' in df.columns:
                for year in df['Academic Year'].unique():
                    if pd.notna(year):
                        year_df = df[df['Academic Year'] == year]
                        year_summary = year_df.groupby(dist_col)[numeric_cols].sum().reset_index()
                        year_summary = add_derived_cols(year_summary)
                        year_summary.insert(0, 'S.No', range(1, len(year_summary) + 1))
                        year_export = filter_mbu_cols(year_summary, dist_col)
                        safe_sheet_name = str(year).replace('/', '-').replace('*', '')[:31]
                        year_export.to_excel(writer, index=False, sheet_name=safe_sheet_name)

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

LWE_MASTER_DISTRICTS = {
    "Bastar",
    "Bijapur",
    "Dakshin Bastar Dantewada",
    "Mohla-Manpur-Ambagarh Chouki",
    "Narayanpur",
    "Sukma",
    "Uttar Bastar Kanker"
}

def is_lwe_district(district_name: str) -> str:
    if not district_name:
        return "No"
    norm = normalize_district_name(str(district_name))
    return "Yes" if norm in LWE_MASTER_DISTRICTS else "No"

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
def preview_district_station_details(
    district_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    search: Optional[str] = None,
    station_search: Optional[str] = None,
    operator_search: Optional[str] = None,
    l1: Optional[str] = None,
    l2: Optional[str] = None,
    sd: Optional[str] = None,
    op: Optional[str] = None,
    st: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        from backend.models.kit_registration import KitRegistration
        from backend.models.operator import Operator
        from backend.models.operator_station_mapping import OperatorStationMapping
        from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
        from backend.models.master_status import MasterStatus
        import math
        import pandas as pd
        
        statuses = {s.id: s.name for s in db.query(MasterStatus).all() if s.id is not None}
        
        d_kits = db.query(KitRegistration).filter(KitRegistration.district.ilike(district_name.strip())).all()
        mappings = db.query(OperatorStationMapping).all()
        operators = db.query(Operator).all()
        onboardings = db.query(OperatorOnboardingDetail).all()
        
        mapping_dict = {m.station_id: m for m in mappings if m.station_id}
        op_dict = {o.id: o for o in operators if o.id}
        onb_dict = {o.station_id: o for o in onboardings if o.station_id}
        
        station_data = []
        analytics = {
            "pending_l1": 0,
            "pending_l2": 0,
            "pending_sd": 0,
            "inactive_op": 0,
            "inactive_st": 0
        }
        
        for i, k in enumerate(d_kits, 1):
            mapping = mapping_dict.get(k.station_id) if k.station_id else None
            op_obj = op_dict.get(mapping.operator_id) if (mapping and mapping.operator_id) else None
            onb = onb_dict.get(k.station_id) if k.station_id else None
            
            raw_l1 = statuses.get(k.l1_status_id) if k.l1_status_id else "Pending"
            if not raw_l1: raw_l1 = "Pending"
            
            raw_l2 = statuses.get(k.l2_status_id) if k.l2_status_id else "Pending"
            if not raw_l2: raw_l2 = "Pending"
            
            l1_status = "L1 Done" if (k.l1_status_id in [19, 2]) or (raw_l1 and str(raw_l1).lower() in ['done', 'approved', 'l1 done', 'l1_done']) else str(raw_l1)
            l2_status = "L2 Done" if (k.l2_status_id in [2, 19]) or (raw_l2 and str(raw_l2).lower() in ['done', 'approved', 'l2 done', 'l2_done']) else str(raw_l2)
            
            op_name = str(op_obj.name) if (op_obj and op_obj.name) else ""
            sd_status = str(op_obj.security_deposit_status) if (op_obj and op_obj.security_deposit_status) else ""
            op_status = str(op_obj.status) if (op_obj and op_obj.status) else ""
            st_status = str(k.station_status) if k.station_status else ""
            onb_status = str(onb.onboarding_status) if (onb and onb.onboarding_status) else ""
            
            # Analytics Counting
            if str(l1_status).lower() not in ['done', 'yes', 'approved', 'l1 done', 'l1_done']: analytics["pending_l1"] += 1
            if str(l2_status).lower() not in ['done', 'yes', 'approved', 'l2 done', 'l2_done']: analytics["pending_l2"] += 1
            if not sd_status or str(sd_status).lower() not in ['yes', 'camp']: analytics["pending_sd"] += 1
            if not op_status or str(op_status).lower() != 'active': analytics["inactive_op"] += 1
            if not st_status or str(st_status).lower() != 'active': analytics["inactive_st"] += 1
            
            def fmt_st_val(val_str):
                if not val_str: return ""
                return str(val_str).replace('_', ' ').title()

            station_data.append({
                "S.No": i,
                "Station ID": k.station_id or "Not Allotted",
                "Operator Name": op_name,
                "L1 Status": l1_status if l1_status == "L1 Done" else fmt_st_val(l1_status),
                "L2 Status": l2_status if l2_status == "L2 Done" else fmt_st_val(l2_status),
                "Security Deposit": fmt_st_val(sd_status),
                "Station Status": fmt_st_val(st_status),
                "Operator Status": fmt_st_val(op_status),
                "Onboarding Status": fmt_st_val(onb_status)
            })
            
        if not station_data:
            df = pd.DataFrame(columns=["S.No", "Station ID", "Operator Name", "L1 Status", "L2 Status", "Security Deposit", "Station Status", "Operator Status", "Onboarding Status"])
        else:
            df = pd.DataFrame(station_data)
            
        df = df.fillna("")
        total_unfiltered = len(df)
        
        # Apply filters safely
        if l1 and "L1 Status" in df.columns:
            l1_val = l1.lower().strip()
            if l1_val == "done":
                df = df[df["L1 Status"].astype(str).str.lower().isin(["l1 done", "done", "approved", "yes"])]
            elif l1_val == "pending":
                df = df[~df["L1 Status"].astype(str).str.lower().isin(["l1 done", "done", "approved", "yes"])]
            elif l1_val == "reverted":
                df = df[df["L1 Status"].astype(str).str.lower().str.contains("revert", regex=False, na=False)]

        if l2 and "L2 Status" in df.columns:
            l2_val = l2.lower().strip()
            if l2_val == "done":
                df = df[df["L2 Status"].astype(str).str.lower().isin(["l2 done", "done", "approved", "yes"])]
            elif l2_val == "pending":
                df = df[~df["L2 Status"].astype(str).str.lower().isin(["l2 done", "done", "approved", "yes"])]
            elif "chips" in l2_val:
                df = df[df["L2 Status"].astype(str).str.lower().str.contains("chips", regex=False, na=False)]
            elif "uidai" in l2_val:
                df = df[df["L2 Status"].astype(str).str.lower().str.contains("uidai", regex=False, na=False)]
            elif l2_val == "reverted":
                df = df[df["L2 Status"].astype(str).str.lower().str.contains("revert", regex=False, na=False)]

        if sd and "Security Deposit" in df.columns:
            sd_val = sd.lower().strip()
            if sd_val == "yes":
                df = df[df["Security Deposit"].astype(str).str.lower().isin(["yes", "camp mode", "camp"])]
            elif sd_val == "pending":
                df = df[~df["Security Deposit"].astype(str).str.lower().isin(["yes", "camp mode", "camp"])]

        if op and "Operator Status" in df.columns:
            op_val = op.lower().strip()
            if op_val == "active":
                df = df[df["Operator Status"].astype(str).str.lower() == "active"]
            elif op_val == "inactive":
                df = df[df["Operator Status"].astype(str).str.lower() != "active"]

        if st and "Station Status" in df.columns:
            st_val = st.lower().strip()
            if st_val == "active":
                df = df[df["Station Status"].astype(str).str.lower() == "active"]
            elif st_val == "inactive":
                df = df[df["Station Status"].astype(str).str.lower() != "active"]

        search_term = search or station_search or operator_search
        if search_term:
            search_val = str(search_term).strip().lower()
            if search_val not in ["search...", "search ...", "search", "none", "null", "undefined", ""]:
                mask = df.astype(str).apply(lambda row: row.str.lower().str.contains(search_val, regex=False, na=False).any(), axis=1)
                df = df[mask]

        df = df.reset_index(drop=True)
        total_rows = len(df)
        total_pages = math.ceil(total_rows / page_size) if total_rows > 0 else 1
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_rows)
        df_page = df.iloc[start_idx:end_idx].copy()
        df_page = df_page.fillna("")
        
        sno_col = _get_df_col(df_page, "S.No") or _get_df_col(df_page, "SR No.")
        if sno_col and not df_page.empty:
            df_page[sno_col] = list(range(start_idx + 1, end_idx + 1))
        
        html_table = generate_clean_multiindex_html(df_page)
        return {
            "html": html_table, 
            "count": total_unfiltered, 
            "analytics": analytics,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_rows,
                "total_unfiltered": total_unfiltered,
                "pages": total_pages,
                "start": start_idx + 1 if total_rows > 0 else 0,
                "end": end_idx
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch district details: {str(e)}")

@router.get("/system/district_wise_kit_count/details/{district_name}/download")
def download_district_station_details(
    district_name: str,
    search: Optional[str] = None,
    station_search: Optional[str] = None,
    operator_search: Optional[str] = None,
    l1: Optional[str] = None,
    l2: Optional[str] = None,
    sd: Optional[str] = None,
    op: Optional[str] = None,
    st: Optional[str] = None,
    db: Session = Depends(get_db)
):
    from backend.models.kit_registration import KitRegistration
    from backend.models.operator import Operator
    from backend.models.operator_station_mapping import OperatorStationMapping
    from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
    from backend.models.master_status import MasterStatus
    import pandas as pd
    import io

    statuses = {s.id: s.name for s in db.query(MasterStatus).all() if s.id is not None}
    d_kits = db.query(KitRegistration).filter(KitRegistration.district.ilike(district_name.strip())).all()
    mappings = db.query(OperatorStationMapping).all()
    operators = db.query(Operator).all()
    onboardings = db.query(OperatorOnboardingDetail).all()
    
    mapping_dict = {m.station_id: m for m in mappings if m.station_id}
    op_dict = {o.id: o for o in operators if o.id}
    onb_dict = {o.station_id: o for o in onboardings if o.station_id}
    
    station_data = []
    for i, k in enumerate(d_kits, 1):
        mapping = mapping_dict.get(k.station_id) if k.station_id else None
        op_obj = op_dict.get(mapping.operator_id) if (mapping and mapping.operator_id) else None
        onb = onb_dict.get(k.station_id) if k.station_id else None
        
        raw_l1 = statuses.get(k.l1_status_id) if k.l1_status_id else "Pending"
        if not raw_l1: raw_l1 = "Pending"
        raw_l2 = statuses.get(k.l2_status_id) if k.l2_status_id else "Pending"
        if not raw_l2: raw_l2 = "Pending"
        
        l1_status = "L1 Done" if (k.l1_status_id in [19, 2]) or (raw_l1 and str(raw_l1).lower() in ['done', 'approved', 'l1 done', 'l1_done']) else str(raw_l1)
        l2_status = "L2 Done" if (k.l2_status_id in [2, 19]) or (raw_l2 and str(raw_l2).lower() in ['done', 'approved', 'l2 done', 'l2_done']) else str(raw_l2)
        
        op_name = str(op_obj.name) if (op_obj and op_obj.name) else ""
        sd_status = str(op_obj.security_deposit_status) if (op_obj and op_obj.security_deposit_status) else ""
        op_status = str(op_obj.status) if (op_obj and op_obj.status) else ""
        st_status = str(k.station_status) if k.station_status else ""
        onb_status = str(onb.onboarding_status) if (onb and onb.onboarding_status) else ""
        
        def fmt_st_val(val_str):
            if not val_str: return ""
            return str(val_str).replace('_', ' ').title()

        station_data.append({
            "S.No": i,
            "Station ID": k.station_id or "Not Allotted",
            "Operator Name": op_name,
            "L1 Status": l1_status if l1_status == "L1 Done" else fmt_st_val(l1_status),
            "L2 Status": l2_status if l2_status == "L2 Done" else fmt_st_val(l2_status),
            "Security Deposit": fmt_st_val(sd_status),
            "Station Status": fmt_st_val(st_status),
            "Operator Status": fmt_st_val(op_status),
            "Onboarding Status": fmt_st_val(onb_status)
        })
        
    df = pd.DataFrame(station_data) if station_data else pd.DataFrame(columns=["S.No", "Station ID", "Operator Name", "L1 Status", "L2 Status", "Security Deposit", "Station Status", "Operator Status", "Onboarding Status"])
    df = df.fillna("")
    
    if l1:
        l1_val = l1.lower().strip()
        if l1_val == "done": df = df[df["L1 Status"].astype(str).str.lower().isin(["l1 done", "done", "approved", "yes"])]
        elif l1_val == "pending": df = df[~df["L1 Status"].astype(str).str.lower().isin(["l1 done", "done", "approved", "yes"])]
        elif l1_val == "reverted": df = df[df["L1 Status"].astype(str).str.lower().str.contains("revert", regex=False, na=False)]
    if l2:
        l2_val = l2.lower().strip()
        if l2_val == "done": df = df[df["L2 Status"].astype(str).str.lower().isin(["l2 done", "done", "approved", "yes"])]
        elif l2_val == "pending": df = df[~df["L2 Status"].astype(str).str.lower().isin(["l2 done", "done", "approved", "yes"])]
        elif "chips" in l2_val: df = df[df["L2 Status"].astype(str).str.lower().str.contains("chips", regex=False, na=False)]
        elif "uidai" in l2_val: df = df[df["L2 Status"].astype(str).str.lower().str.contains("uidai", regex=False, na=False)]
        elif l2_val == "reverted": df = df[df["L2 Status"].astype(str).str.lower().str.contains("revert", regex=False, na=False)]
    if sd:
        sd_val = sd.lower().strip()
        if sd_val == "yes": df = df[df["Security Deposit"].astype(str).str.lower().isin(["yes", "camp mode", "camp"])]
        elif sd_val == "pending": df = df[~df["Security Deposit"].astype(str).str.lower().isin(["yes", "camp mode", "camp"])]
    if op:
        op_val = op.lower().strip()
        if op_val == "active": df = df[df["Operator Status"].astype(str).str.lower() == "active"]
        elif op_val == "inactive": df = df[df["Operator Status"].astype(str).str.lower() != "active"]
    if st:
        st_val = st.lower().strip()
        if st_val == "active": df = df[df["Station Status"].astype(str).str.lower() == "active"]
        elif st_val == "inactive": df = df[df["Station Status"].astype(str).str.lower() != "active"]

    search_term = search or station_search or operator_search
    if search_term:
        search_val = str(search_term).strip().lower()
        if search_val not in ["search...", "search ...", "search", "none", "null", "undefined", ""]:
            mask = df.astype(str).apply(lambda row: row.str.lower().str.contains(search_val, regex=False, na=False).any(), axis=1)
            df = df[mask]

    df = df.reset_index(drop=True)
    if not df.empty:
        df["S.No"] = range(1, len(df) + 1)
        
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=district_name[:31])
    output.seek(0)
    
    filename = f"Station_Details_{district_name.replace(' ', '_')}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/system/lms_summary/details/{district_name}")
def preview_lms_district_details(
    district_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    search: Optional[str] = None,
    station_search: Optional[str] = None,
    operator_search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        from backend.models.lms import LMS
        from backend.models.candidate import Candidate
        import math
        import pandas as pd
        
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
            
        if not station_data:
            df = pd.DataFrame(columns=["S.No", "Candidate ID", "Candidate Name", "Status", "Submitted At"])
        else:
            df = pd.DataFrame(station_data)
            
        df = df.fillna("")
        total_unfiltered = len(df)

        search_term = search or station_search or operator_search
        if search_term:
            search_val = str(search_term).strip().lower()
            mask = df.astype(str).apply(lambda row: row.str.lower().str.contains(search_val, regex=False, na=False).any(), axis=1)
            df = df[mask]

        df = df.reset_index(drop=True)
        total_rows = len(df)
        total_pages = math.ceil(total_rows / page_size) if total_rows > 0 else 1
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        df_page = df.iloc[start_idx:end_idx].copy()
        df_page = df_page.fillna("")

        html_table = generate_clean_multiindex_html(df_page)
        return {
            "html": html_table,
            "analytics": analytics,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_rows,
                "total_unfiltered": total_unfiltered,
                "pages": total_pages,
                "start": start_idx + 1 if total_rows > 0 else 0,
                "end": min(end_idx, total_rows)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch LMS details: {str(e)}")

@router.get("/system/nseit_summary/details/{district_name}")
def preview_nseit_district_details(
    district_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    search: Optional[str] = None,
    station_search: Optional[str] = None,
    operator_search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        from backend.models.nseit import NSEITRequest
        from backend.models.candidate import Candidate
        import math
        import pandas as pd
        
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
            
        if not station_data:
            df = pd.DataFrame(columns=["S.No", "Candidate ID", "Candidate Name", "Status", "Submitted At"])
        else:
            df = pd.DataFrame(station_data)
            
        df = df.fillna("")
        total_unfiltered = len(df)

        search_term = search or station_search or operator_search
        if search_term:
            search_val = str(search_term).strip().lower()
            mask = df.astype(str).apply(lambda row: row.str.lower().str.contains(search_val, regex=False, na=False).any(), axis=1)
            df = df[mask]

        df = df.reset_index(drop=True)
        total_rows = len(df)
        total_pages = math.ceil(total_rows / page_size) if total_rows > 0 else 1
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        df_page = df.iloc[start_idx:end_idx].copy()
        df_page = df_page.fillna("")

        html_table = generate_clean_multiindex_html(df_page)
        return {
            "html": html_table,
            "analytics": analytics,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_rows,
                "total_unfiltered": total_unfiltered,
                "pages": total_pages,
                "start": start_idx + 1 if total_rows > 0 else 0,
                "end": min(end_idx, total_rows)
            }
        }
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
        districts = db.query(District).order_by(District.district_name.asc()).all()
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
        districts = db.query(District).order_by(District.district_name.asc()).all()
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
        kits = db.query(KitRegistration).all()
        kit_dict = {k.station_id: k.station_status for k in kits if k.station_id}
        data = []
        for ob in onboardings:
            op = ob.operator
            d = db.query(District).filter(District.district_code == op.district_id).first()
            d_name = d.district_name if d else str(op.district_id)
            st_status = kit_dict.get(ob.station_id, "")
            
            data.append({
                "Operator Name": op.name,
                "Operator Id": op.user_code,
                "Operator Mobile": clean_mobile_val(op.mobile),
                "District": d_name,
                "Station Id": ob.station_id,
                "Station Status": st_status,
                "Onboarding Status": ob.onboarding_status,
                "Visit Status": ob.visit_status or "",
                "Visit Date": ob.visit_date.strftime("%Y-%m-%d") if ob.visit_date else "",
                "Onboard Date": ob.onboard_date.strftime("%Y-%m-%d") if ob.onboard_date else "",
                "Permitted 18+": ob.permitted_18_plus,
                "ASK Kit Working Status": ob.ask_kit_working_status,
                "Remark": ob.remark or ""
            })
        if not data:
            columns = ["Operator Name", "Operator Id", "Operator Mobile", "District", "Station Id", "Station Status", "Onboarding Status", "Visit Status", "Visit Date", "Onboard Date", "Permitted 18+", "ASK Kit Working Status", "Remark"]
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
                "Station ID Assigned": req.station_id_inserted or "",
                "Machine ID (L1)": l1.machine_id if l1 else "",
                "L1 Status": l1.status if l1 else "",
                "Submitted At": req.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if req.submitted_at else ""
            })
        if not data:
            columns = ["Request No", "DC Name", "District", "Model", "Number of Kits", "Station ID Request Status", "Station ID Assigned", "Machine ID (L1)", "L1 Status", "Submitted At"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(data)
        
    elif report_name == "l1_pending_list":
        statuses = {s.id: s.name for s in db.query(MasterStatus).all()}
        kits = db.query(KitRegistration).all()
        operators = db.query(Operator).all()
        mappings = db.query(OperatorStationMapping).all()
        mapping_dict = {m.station_id: m for m in mappings if m.station_id}
        op_dict = {o.id: o for o in operators if o.id}

        l1_data = []
        sr_no = 1
        for k in kits:
            raw_l1 = statuses.get(k.l1_status_id, "Pending")
            is_l1_done = (k.l1_status_id in [19, 2]) or (raw_l1 and str(raw_l1).lower() in ['done', 'approved', 'l1 done', 'l1_done', 'yes'])
            if not is_l1_done:
                mapping = mapping_dict.get(k.station_id) if k.station_id else None
                op = op_dict.get(mapping.operator_id) if (mapping and mapping.operator_id) else None
                op_name = op.name if op else ""
                op_id = op.user_code if op else ""

                l1_data.append({
                    "SR No.": sr_no,
                    "District": k.district,
                    "Is LWE District": is_lwe_district(k.district),
                    "Kit Slot": k.category,
                    "Station ID": k.station_id,
                    "Operator Name": op_name,
                    "Operator ID": op_id,
                    "Station ID Provided Date": k.station_id_provided_date.strftime("%Y-%m-%d") if k.station_id_provided_date else "",
                    "L1 Status": "No",
                    "L1 Status Date /(Pending days)": calculate_pending_days(k.station_id_provided_date)
                })
                sr_no += 1
        if not l1_data:
            columns = ["SR No.", "District", "Is LWE District", "Kit Slot", "Station ID", "Operator Name", "Operator ID", "Station ID Provided Date", "L1 Status", "L1 Status Date /(Pending days)"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(l1_data)
        
    elif report_name == "l2_pending_list":
        statuses = {s.id: s.name for s in db.query(MasterStatus).all()}
        kits = db.query(KitRegistration).all()
        operators = db.query(Operator).all()
        mappings = db.query(OperatorStationMapping).all()
        mapping_dict = {m.station_id: m for m in mappings if m.station_id}
        op_dict = {o.id: o for o in operators if o.id}

        l2_data = []
        sr_no = 1
        for k in kits:
            raw_l1 = statuses.get(k.l1_status_id, "Pending")
            raw_l2 = statuses.get(k.l2_status_id, "Pending")
            is_l1_done = (k.l1_status_id in [19, 2]) or (raw_l1 and str(raw_l1).lower() in ['done', 'approved', 'l1 done', 'l1_done', 'yes'])
            is_l2_done = (k.l2_status_id in [2, 19]) or (raw_l2 and str(raw_l2).lower() in ['done', 'approved', 'l2 done', 'l2_done', 'yes'])
            
            if is_l1_done and not is_l2_done:
                mapping = mapping_dict.get(k.station_id) if k.station_id else None
                op = op_dict.get(mapping.operator_id) if (mapping and mapping.operator_id) else None
                op_name = op.name if op else ""
                op_id = op.user_code if op else ""
                l2_name = raw_l2 if raw_l2 else "Pending"

                l2_data.append({
                    "SR No.": sr_no,
                    "District": k.district,
                    "Is LWE District": is_lwe_district(k.district),
                    "Kit Slot": k.category,
                    "Station Id": k.station_id,
                    "Operator Name": op_name,
                    "Operator ID": op_id,
                    "Machine Id": k.machine_id,
                    "Laptop Serial No.": k.laptop_serial_no,
                    "Laptop Name": k.laptop_name,
                    "Station ID Provided Date": k.station_id_provided_date.strftime("%Y-%m-%d") if k.station_id_provided_date else "",
                    "L1 Status": "Yes",
                    "L1 Done Date": k.l1_done_date.strftime("%Y-%m-%d") if k.l1_done_date else "",
                    "L2 Status": l2_name,
                    "L2 Done Date /(Pending days)": calculate_pending_days(k.l1_done_date),
                    "Current Stay Status": l2_name
                })
                sr_no += 1
        if not l2_data:
            columns = ["SR No.", "District", "Is LWE District", "Kit Slot", "Station Id", "Operator Name", "Operator ID", "Machine Id", "Laptop Serial No.", "Laptop Name", "Station ID Provided Date", "L1 Status", "L1 Done Date", "L2 Status", "L2 Done Date /(Pending days)", "Current Stay Status"]
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
            
            mobile_str = str(o.mobile).strip() if o.mobile else ""
            if mobile_str.endswith(".0"):
                mobile_str = mobile_str[:-2]
            
            op_data.append({
                "SR No.": sr_no,
                "District": dist_name,
                "Is LWE District": is_lwe_district(dist_name),
                "Operator Name": o.name,
                "Operator Id": o.user_code,
                "Operator Mobile": clean_mobile_val(o.mobile),
                "SD Status": o.security_deposit_status or "",
                "Security Deposit Date": o.security_deposit_date.strftime("%Y-%m-%d") if o.security_deposit_date else "",
                "Block": kit.block if kit else "",
                "Location Category": kit.category if kit else "",
                "Locality": kit.locality if kit else "",
                "ASK (Aadhaar Sewa Kendra) Address": kit.ask_address if kit else "",
                "Operator Activation Status (User Credentials Created)": o.status or "",
                "Operator In-active Reason": o.inactive_reason or "",
                "Operator In-active Date": o.inactive_date.strftime("%Y-%m-%d") if o.inactive_date else "",
                "NSEIT Certificate No": o.nseit_certificate_number or "",
                "Certificate Issue Date": o.nseit_certification_date.strftime("%Y-%m-%d") if o.nseit_certification_date else "",
                "Certificate Validity": o.nseit_certificate_expiry_date.strftime("%Y-%m-%d") if o.nseit_certificate_expiry_date else "",
                "Create Date": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "",
                "Update Date": o.updated_at.strftime("%Y-%m-%d %H:%M:%S") if o.updated_at else ""
            })
            sr_no += 1
        if not op_data:
            columns = ["SR No.", "District", "Is LWE District", "Operator Name", "Operator Id", "Operator Mobile", "SD Status", "Security Deposit Date", "Block", "Location Category", "Locality", "ASK (Aadhaar Sewa Kendra) Address", "Operator Activation Status (User Credentials Created)", "Operator In-active Reason", "Operator In-active Date", "NSEIT Certificate No", "Certificate Issue Date", "Certificate Validity", "Create Date", "Update Date"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(op_data)

    elif report_name == "onboard_pending_list":
        statuses = {s.id: s.name for s in db.query(MasterStatus).all()}
        kits = db.query(KitRegistration).all()
        operators = db.query(Operator).all()
        mappings = db.query(OperatorStationMapping).all()
        onboardings = db.query(OperatorOnboardingDetail).all()
        mapping_dict = {m.station_id: m for m in mappings if m.station_id}
        op_dict = {o.id: o for o in operators if o.id}
        onb_dict = {o.station_id: o for o in onboardings if o.station_id}

        onb_data = []
        sr_no = 1
        for k in kits:
            raw_l2 = statuses.get(k.l2_status_id, "Pending")
            is_l2_done = (k.l2_status_id in [2, 19]) or (raw_l2 and str(raw_l2).lower() in ['done', 'approved', 'l2 done', 'l2_done', 'yes'])
            if is_l2_done:
                onb = onb_dict.get(k.station_id)
                status_onb = onb.onboarding_status if onb else "Pending"
                if not status_onb or str(status_onb).lower() not in ['done', 'active', 'yes', 'onboarded']:
                    mapping = mapping_dict.get(k.station_id) if k.station_id else None
                    op = op_dict.get(mapping.operator_id) if (mapping and mapping.operator_id) else None
                    op_name = op.name if op else ""
                    op_id = op.user_code if op else ""

                    onb_data.append({
                        "SR No.": sr_no,
                        "District": k.district,
                        "Is LWE District": is_lwe_district(k.district),
                        "Kit Slot": k.category,
                        "Station Id": k.station_id,
                        "Operator Name": op_name,
                        "Operator ID": op_id,
                        "Machine Id": k.machine_id,
                        "Laptop Serial No.": k.laptop_serial_no,
                        "Laptop Name": k.laptop_name,
                        "Station ID Provided Date": k.station_id_provided_date.strftime("%Y-%m-%d") if k.station_id_provided_date else "",
                        "L1 Status": "Yes",
                        "L1 Done Date": k.l1_done_date.strftime("%Y-%m-%d") if k.l1_done_date else "",
                        "L2 Status": "Yes",
                        "L2 Done Date": k.l2_done_date.strftime("%Y-%m-%d") if k.l2_done_date else "",
                        "On-Boarding Status": status_onb,
                        "On-Boarding Date /(Pending days)": calculate_pending_days(k.l2_done_date)
                    })
                    sr_no += 1
        if not onb_data:
            columns = ["SR No.", "District", "Is LWE District", "Kit Slot", "Station Id", "Operator Name", "Operator ID", "Machine Id", "Laptop Serial No.", "Laptop Name", "Station ID Provided Date", "L1 Status", "L1 Done Date", "L2 Status", "L2 Done Date", "On-Boarding Status", "On-Boarding Date /(Pending days)"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(onb_data)

    elif report_name == "district_wise_kit_count":
        statuses = {s.id: s.name for s in db.query(MasterStatus).all()}
        kits = db.query(KitRegistration).all()
        operators = db.query(Operator).all()
        mappings = db.query(OperatorStationMapping).all()
        onboardings = db.query(OperatorOnboardingDetail).all()
        
        mapping_dict = {m.station_id: m for m in mappings if m.station_id}
        op_dict = {o.id: o for o in operators if o.id}
        onb_dict = {o.station_id: o for o in onboardings if o.station_id}
        
        districts = db.query(District).order_by(District.district_name.asc()).all()
        data = []
        
        for d in districts:
            norm_d = normalize_district_name(d.district_name)
            d_kits = [k for k in kits if k.district and normalize_district_name(k.district) == norm_d]
            if not d_kits:
                d_kits = [k for k in kits if k.district and normalize_district_name(k.district) == normalize_district_name(d.district_code)]
            
            sd_camp = 0; sd_yes = 0; sd_pending = 0
            l1_yes = 0; l1_no = 0
            l2_yes = 0; l2_no = 0; l2_chips = 0; l2_uidai = 0
            op_active = 0; op_inactive = 0
            onb_active = 0; onb_inactive = 0
            st_active = 0; st_inactive = 0
            ask_active = 0; ask_inactive = 0
            allotted_kits_count = 0
            
            for k in d_kits:
                if k.station_id and str(k.station_id).strip() and str(k.station_id).lower() not in ['none', 'null', '']:
                    allotted_kits_count += 1
                    
                mapping = mapping_dict.get(k.station_id) if k.station_id else None
                op_obj = op_dict.get(mapping.operator_id) if (mapping and mapping.operator_id) else None
                onb = onb_dict.get(k.station_id) if k.station_id else None
                
                raw_l1 = statuses.get(k.l1_status_id, "Pending")
                raw_l2 = statuses.get(k.l2_status_id, "Pending")
                
                is_l1_done = (k.l1_status_id in [19, 2]) or (raw_l1 and str(raw_l1).lower() in ['done', 'approved', 'l1 done', 'l1_done', 'yes'])
                l2_lower = str(raw_l2).lower() if raw_l2 else ""
                is_l2_done = (k.l2_status_id in [2, 19]) or (l2_lower in ['done', 'approved', 'l2 done', 'l2_done', 'yes'])
                
                # L1
                if is_l1_done: l1_yes += 1
                else: l1_no += 1
                
                # L2
                if is_l2_done: l2_yes += 1
                elif 'chips' in l2_lower: l2_chips += 1
                elif 'uidai' in l2_lower: l2_uidai += 1
                else: l2_no += 1
                
                # SD
                sd_st = str(op_obj.security_deposit_status).lower() if (op_obj and op_obj.security_deposit_status) else ""
                if sd_st == 'camp': sd_camp += 1
                elif sd_st == 'yes': sd_yes += 1
                else: sd_pending += 1
                
                # Operator Activation
                op_st = str(op_obj.status).lower() if (op_obj and op_obj.status) else ""
                if op_st == 'active': op_active += 1
                else: op_inactive += 1
                
                # Operator Onboarding
                onb_st = str(onb.onboarding_status).lower() if (onb and onb.onboarding_status) else ""
                if onb_st in ['active', 'yes', 'done', 'approved', 'onboarded']: onb_active += 1
                else: onb_inactive += 1
                
                # Station ID Status
                st_st = str(k.station_status).lower() if k.station_status else ""
                if st_st == 'active': st_active += 1
                else: st_inactive += 1
                
                # ASK Kit Working
                kit_st = str(onb.ask_kit_working_status).lower() if (onb and onb.ask_kit_working_status) else ""
                if kit_st in ['active', 'yes', 'done', 'working']: ask_active += 1
                else: ask_inactive += 1
                
            data.append({
                ("S.No", ""): len(data) + 1,
                ("District", ""): d.district_name,
                ("Is LWE District", ""): is_lwe_district(d.district_name),
                ("Total Machine", ""): len(d_kits),
                ("Alloted Station Id", ""): allotted_kits_count,
                ("Security Deposit", "Camp"): sd_camp,
                ("Security Deposit", "Yes"): sd_yes,
                ("Security Deposit", "Pending"): sd_pending,
                ("L1 Status", "Yes"): l1_yes,
                ("L1 Status", "No"): l1_no,
                ("L2 Status", "Yes"): l2_yes,
                ("L2 Status", "No"): l2_no,
                ("L2 Status", "Send to CHiPS"): l2_chips,
                ("L2 Status", "Send to UIDAI"): l2_uidai,
                ("Operator Activation Status (User Credentials Created)", "Active"): op_active,
                ("Operator Activation Status (User Credentials Created)", "Inactive SentToChips"): op_inactive,
                ("Operator Onboarding Status (After L2 Activation)", "Active"): onb_active,
                ("Operator Onboarding Status (After L2 Activation)", "Inactive"): onb_inactive,
                ("Station ID Status", "Active"): st_active,
                ("Station ID Status", "Inactive"): st_inactive,
                ("ASK Kit Working Status", "Active"): ask_active,
                ("ASK Kit Working Status", "Inactive"): ask_inactive
            })
            
        columns = [
            ("S.No", ""), ("District", ""), ("Is LWE District", ""),
            ("Total Machine", ""), ("Alloted Station Id", ""),
            ("Security Deposit", "Camp"), ("Security Deposit", "Yes"), ("Security Deposit", "Pending"),
            ("L1 Status", "Yes"), ("L1 Status", "No"),
            ("L2 Status", "Yes"), ("L2 Status", "No"), ("L2 Status", "Send to CHiPS"), ("L2 Status", "Send to UIDAI"),
            ("Operator Activation Status (User Credentials Created)", "Active"),
            ("Operator Activation Status (User Credentials Created)", "Inactive SentToChips"),
            ("Operator Onboarding Status (After L2 Activation)", "Active"),
            ("Operator Onboarding Status (After L2 Activation)", "Inactive"),
            ("Station ID Status", "Active"), ("Station ID Status", "Inactive"),
            ("ASK Kit Working Status", "Active"), ("ASK Kit Working Status", "Inactive")
        ]
        
        if not data:
            return pd.DataFrame(columns=pd.MultiIndex.from_tuples(columns))
            
        df = pd.DataFrame(data)
        df.columns = pd.MultiIndex.from_tuples(columns)
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
            mapping = mapping_dict.get(k.station_id)
            op = None
            onb = None
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
                "Station ID Allotted Date": k.station_id_provided_date.strftime("%Y-%m-%d") if k.station_id_provided_date else "",
                "Machine ID": k.machine_id,
                "Laptop Serial No.": k.laptop_serial_no,
                "Laptop Name": k.laptop_name,
                "Operator Name": op.name if op else "",
                "Operator Id": op.user_code if op else "",
                "Operator Mobile": clean_mobile_val(op.mobile if op else ""),
                "Security Deposit Status": op.security_deposit_status if op else "",
                "Security Deposit Date": op.security_deposit_date.strftime("%Y-%m-%d") if (op and op.security_deposit_date) else "",
                "L1 Status": l1_status_name,
                "L1 Date": k.l1_done_date.strftime("%Y-%m-%d") if k.l1_done_date else "",
                "L2 Status": l2_status_name,
                "L2 Date": k.l2_done_date.strftime("%Y-%m-%d") if k.l2_done_date else "",
                "Block": k.block,
                "Category": k.category,
                "Locality": k.locality,
                "ASK Address": k.ask_address,
                "Operator Status": op.status if op else "",
                "Inactive Reason": op.inactive_reason if op else "",
                "Inactive Date": op.inactive_date.strftime("%Y-%m-%d") if (op and op.inactive_date) else "",
                "18+ Permit": onb.permitted_18_plus if onb else "",
                "Station Status": k.station_status,
                "Onboarding Status": onb.onboarding_status if onb else "",
                "Onboard Date": onb.onboard_date.strftime("%Y-%m-%d") if (onb and onb.onboard_date) else "",
                "Kit Working": onb.ask_kit_working_status if onb else "",
                "Visit Status": onb.visit_status if onb else "",
                "Visit Date": onb.visit_date.strftime("%Y-%m-%d") if (onb and onb.visit_date) else "",
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
        if isinstance(col, str) and col.lower() == name.lower():
            return col
        if isinstance(col, tuple) and col[0].lower() == name.lower():
            return col
    return None

def clean_mobile_val(val):
    if not val:
        return ""
    val_str = str(val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]
    return val_str

def clean_dataframe_mobile_cols(df):
    mob_cols = [col for col in df.columns if 'mobile' in str(col).lower() or 'phone' in str(col).lower()]
    for col in mob_cols:
        df[col] = df[col].apply(clean_mobile_val)
    return df



def calculate_pending_days(start_date):
    if not start_date:
        return ""
    from datetime import date
    if isinstance(start_date, datetime):
        start_date = start_date.date()
    days = (date.today() - start_date).days
    return f"{days} Days pending"

def get_status_name(status_id: int, statuses_dict: dict) -> str:
    if not status_id: return "Pending"
    return statuses_dict.get(status_id, "Pending")

def add_total_row(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    
    is_multi = isinstance(df.columns, pd.MultiIndex)
    total_row = {}
    
    for col in df.columns:
        col_str = str(col[0] if is_multi else col).lower()
        if col_str in ["s.no", "sr no.", "sr.no.", "index", "district", "is lwe district"]:
            if col_str in ["district", "is lwe district"] and not ("s.no" in str(df.columns[0]).lower() or "district" in str(df.columns[0]).lower()):
                total_row[col] = ""
            elif col == df.columns[0]:
                total_row[col] = "Total"
            else:
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
    df_clean = df.copy()

    def clean_cell_val(val):
        if val is None or pd.isna(val):
            return ""
        s = str(val).strip()
        if s.lower() in ["nat", "nan", "<nat>", "none", "null", "n/a", "not assigned"]:
            return ""
        return s

    if not isinstance(df_clean.columns, pd.MultiIndex):
        for col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(clean_cell_val)
            
        th_html = ""
        for col in df_clean.columns:
            th_html += f'<th style="text-align: center; background: #0f172a; color: white; font-weight: 700; border-right: 1px solid #334155; padding: 10px 14px;">{col}</th>'
            
        tbody_html = "<tbody>\n"
        for row_idx, row in df_clean.iterrows():
            is_total = (clean_cell_val(row.iloc[0]).lower() == "total" or (len(row) > 1 and clean_cell_val(row.iloc[1]).lower() == "total"))
            bg_color = "#e2e8f0" if is_total else ("#ffffff" if row_idx % 2 == 0 else "#f8fafc")
            border_style = "border-top: 2px solid #64748b; border-bottom: 2px solid #64748b;" if is_total else "border-bottom: 1px solid #e2e8f0;"
            tbody_html += f'  <tr style="background: {bg_color}; font-weight: {"700" if is_total else "normal"};">\n'
            for col_idx, val in enumerate(row):
                val_str = clean_cell_val(val)
                align = "left" if (col_idx in [0, 1] and not is_total) else ("left" if is_total and col_idx == 0 else "center")
                font_wt = "700" if (is_total or col_idx == 1) else "400"
                td_bg = "background: #e2e8f0;" if is_total else ""
                tbody_html += f'    <td style="text-align: {align}; font-weight: {font_wt}; padding: 10px 14px; {border_style} border-right: 1px solid #cbd5e1; color: #0f172a; {td_bg}">{val_str}</td>\n'
            tbody_html += "  </tr>\n"
        tbody_html += "</tbody>"

        return f'''<table class="{table_class}" style="width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; font-family: inherit;">
  <thead>
    <tr>{th_html}</tr>
  </thead>
  {tbody_html}
</table>'''

    headers = list(df_clean.columns)

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
    for row_idx, row in df_clean.iterrows():
        is_total = (clean_cell_val(row.iloc[0]).lower() == "total" or clean_cell_val(row.iloc[1]).lower() == "total")
        row_cls = ' class="total-row"' if is_total else ''
        bg_color = "#e2e8f0" if is_total else ("#ffffff" if row_idx % 2 == 0 else "#f8fafc")
        border_style = "border-top: 2px solid #64748b; border-bottom: 2px solid #64748b;" if is_total else "border-bottom: 1px solid #e2e8f0;"
        tbody_html += f'  <tr{row_cls} style="background: {bg_color}; font-weight: {"700" if is_total else "normal"};">\n'
        for col_idx, val in enumerate(row):
            val_str = clean_cell_val(val)
            align = "left" if (col_idx in [0, 1] and not is_total) else ("left" if is_total and col_idx == 0 else "center")
            font_wt = "700" if (is_total or col_idx == 1) else "400"
            td_bg = "background: #e2e8f0;" if is_total else ""
            tbody_html += f'    <td style="text-align: {align}; font-weight: {font_wt}; padding: 10px 14px; {border_style} border-right: 1px solid #cbd5e1; color: #0f172a; {td_bg}">{val_str}</td>\n'
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

def apply_system_filters(df, lwe: bool, division: Optional[str], district: Optional[str], search: Optional[str] = None, station_search: Optional[str] = None, operator_search: Optional[str] = None):
    dist_col = _get_df_col(df, "District") or _get_df_col(df, "District Name")
    if district and dist_col:
        norm_target = normalize_district_name(district)
        df = df[df[dist_col].astype(str).apply(normalize_district_name) == norm_target]
        
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

    search_term = search or station_search or operator_search
    if search_term:
        search_val = str(search_term).strip().lower()
        if search_val not in ["search...", "search ...", "search", "none", "null", "undefined", ""]:
            mask = df.astype(str).apply(lambda row: row.str.lower().str.contains(search_val, regex=False, na=False).any(), axis=1)
            df = df[mask]

    if district or division or lwe or search_term:
        df = df.reset_index(drop=True)
        sno_col = _get_df_col(df, "SR No.") or _get_df_col(df, "S.No")
        if sno_col:
            df[sno_col] = range(1, len(df) + 1)
            
    if lwe_col:
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = df.drop(columns=[lwe_col])
        except Exception:
            pass
        
    return df

@router.get("/system/{report_name}/preview")
def preview_system_report(
    report_name: str, 
    lwe: bool = False, 
    division: Optional[str] = None, 
    district: Optional[str] = None,
    search: Optional[str] = None,
    station_search: Optional[str] = None,
    operator_search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1),
    db: Session = Depends(get_db)
):
    try:
        df_raw = get_system_report_dataframe(report_name, db)
        total_unfiltered = len(df_raw)
        
        df = apply_system_filters(df_raw, lwe, division, district, search=search, station_search=station_search, operator_search=operator_search)
        df = df.fillna("")
        
        total_rows = len(df)
        import math
        total_pages = math.ceil(total_rows / page_size) if total_rows > 0 else 1
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        df_page = df.iloc[start_idx:end_idx].copy()
        
        if report_name in ["district_wise_kit_count", "lms_summary", "nseit_summary"]:
            df_page = add_total_row(df_page)
            
        html_table = generate_clean_multiindex_html(df_page)
        return {
            "html": html_table,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total_rows,
                "total_unfiltered": total_unfiltered,
                "pages": total_pages,
                "start": start_idx + 1 if total_rows > 0 else 0,
                "end": min(end_idx, total_rows)
            }
        }
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
