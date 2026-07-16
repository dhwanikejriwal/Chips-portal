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

@router.post("/generate")
async def generate_report(
    report_type: str = Form(...),
    file: UploadFile = File(...),
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
        
        if report_type == "mbu_district_wise":
            # Auto-detect header row
            if file.filename.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(contents))
            else:
                df = pd.read_excel(io.BytesIO(contents), header=None)
                
                # Find the row containing 'District Name' to use as header
                header_row = 0
                for i in range(min(10, len(df))):
                    row_vals = [str(x).strip().lower() for x in df.iloc[i].values if pd.notna(x)]
                    if 'district name' in row_vals or 'district_name' in row_vals:
                        header_row = i
                        break
                        
                df = pd.read_excel(io.BytesIO(contents), header=header_row)
            
            # Clean up the dataset (remove metadata rows usually starting with '(3)')
            if 'Academic Year' in df.columns:
                df = df[df['Academic Year'] != '(3)']
                
            # Focus on pending columns
            pending_cols = [
                'MBU Pending (Age 5-15)', 
                'MBU Pending (Age 15 and above)'
            ]
            
            # Keep only available pending columns + District Name + Academic Year
            keep_cols = ['District Name']
            if 'Academic Year' in df.columns:
                keep_cols.append('Academic Year')
                
            for col in pending_cols:
                if col in df.columns:
                    keep_cols.append(col)
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                    
            df = df[keep_cols].dropna(subset=['District Name'])
            
            # Write to multi-sheet excel
            with pd.ExcelWriter(output_filepath, engine='openpyxl') as writer:
                # Combined Sheet
                combined_df = df.groupby('District Name')[keep_cols[2:] if 'Academic Year' in df.columns else keep_cols[1:]].sum().reset_index()
                combined_df.to_excel(writer, index=False, sheet_name='Combined')
                
                # LWE Sheet
                lwe_districts = ["dantewada", "baster", "sukma", "narayanpur", "mohla-manpur-chowki", "bijapur", "kanker"]
                lwe_mask = df['District Name'].str.lower().str.strip().isin(lwe_districts)
                lwe_df = df[lwe_mask]
                if not lwe_df.empty:
                    lwe_summary = lwe_df.groupby('District Name')[keep_cols[2:] if 'Academic Year' in df.columns else keep_cols[1:]].sum().reset_index()
                    lwe_summary.to_excel(writer, index=False, sheet_name='LWE')
                
                # Sheet per Academic Year
                if 'Academic Year' in df.columns:
                    for year in df['Academic Year'].unique():
                        if pd.notna(year):
                            year_df = df[df['Academic Year'] == year]
                            year_summary = year_df.groupby('District Name')[keep_cols[2:]].sum().reset_index()
                            # Excel sheet names have max 31 chars and no special chars like []/\?*
                            safe_sheet_name = str(year).replace('/', '-').replace('*', '')[:31]
                            year_summary.to_excel(writer, index=False, sheet_name=safe_sheet_name)
        else:
            if file.filename.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(contents))
            else:
                df = pd.read_excel(io.BytesIO(contents))
            summary_df = df.describe(include='all')
            with pd.ExcelWriter(output_filepath, engine='openpyxl') as writer:
                summary_df.to_excel(writer, index=False, sheet_name='Report')

        # Log to DB
        report_record = ReportHistory(
            report_type=report_type,
            filename=output_filename,
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
    reports = db.query(ReportHistory).order_by(ReportHistory.created_at.desc()).all()
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
            html_sheets[sheet_name] = df.head(100).to_html(classes='preview-table', index=False, border=0)
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

def get_system_report_dataframe(report_name: str, db: Session) -> pd.DataFrame:
    from backend.models.district import District
    from backend.models.candidate import Candidate
    from backend.models.lms import LMS
    from backend.models.nseit import NSEITRequest
    from backend.models.operator import Operator
    from backend.models.operator_onboarding import OperatorOnboarding
    from backend.models.station_id import StationIDRequest
    from backend.models.l1_registration import L1RegistrationRequest
    
    if report_name == "candidate_summary":
        districts = db.query(District).all()
        data = []
        for d in districts:
            lms_reqs = db.query(LMS).join(Candidate).filter(Candidate.district == d.district_code).all()
            nseit_reqs = db.query(NSEITRequest).join(Candidate).filter(Candidate.district == d.district_code).all()
            
            data.append({
                "District Code": d.district_code,
                "District Name": d.district_name,
                "Total LMS Requests": len(lms_reqs),
                "Approved LMS": len([r for r in lms_reqs if r.status == "Approved"]),
                "Pending LMS": len([r for r in lms_reqs if r.status == "Pending"]),
                "Rejected LMS": len([r for r in lms_reqs if r.status == "Rejected"]),
                "Total NSEIT Requests": len(nseit_reqs),
                "Approved NSEIT": len([r for r in nseit_reqs if r.status == "Approved"]),
                "Pending NSEIT": len([r for r in nseit_reqs if r.status == "Pending"]),
                "Rejected NSEIT": len([r for r in nseit_reqs if r.status == "Rejected"]),
            })
        if not data:
            columns = ["District Code", "District Name", "Total LMS Requests", "Approved LMS", "Pending LMS", "Rejected LMS", "Total NSEIT Requests", "Approved NSEIT", "Pending NSEIT", "Rejected NSEIT"]
            return pd.DataFrame(columns=columns)
        return pd.DataFrame(data)
        
    elif report_name == "operator_onboarding_status":
        onboardings = db.query(OperatorOnboarding).join(Operator).all()
        data = []
        for ob in onboardings:
            op = ob.operator
            d = db.query(District).filter(District.district_code == op.district_id).first()
            d_name = d.district_name if d else str(op.district_id)
            
            data.append({
                "Operator Code": op.user_code,
                "Operator Name": op.name,
                "Mobile": op.mobile,
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
        
    else:
        raise ValueError("Invalid report name")

@router.get("/system/{report_name}/preview")
def preview_system_report(report_name: str, db: Session = Depends(get_db)):
    try:
        df = get_system_report_dataframe(report_name, db)
        html_table = df.to_html(classes='preview-table', index=False, border=0)
        return {"html": html_table}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate preview: {str(e)}")

@router.get("/system/{report_name}/download")
def download_system_report(report_name: str, db: Session = Depends(get_db)):
    try:
        df = get_system_report_dataframe(report_name, db)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='System Report')
            
        output.seek(0)
        from fastapi.responses import Response
        headers = {
            'Content-Disposition': f'attachment; filename="system_{report_name}.xlsx"'
        }
        return Response(content=output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")
