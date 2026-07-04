# backend/routers/reactivation.py
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd
import io
import os
import json
import shutil
import mimetypes
from fastapi.responses import FileResponse
from datetime import date
from fastapi.responses import StreamingResponse
from backend.utils.exporter import generate_excel_export,generate_csv_export
from backend.database import SessionLocal
from backend.routers.auth import get_current_user
from backend.models import User, District
from backend.models.base import to_name

# 🌟 CONNECTED: Pulling from your exact, unchanged model class baseline definitions
from backend.models.reactivation import (
    OperatorReactivationRequest, 
    ReactivationDocument, 
    ReactivationOperator, 
    ReactivationRemarkHistory
)

router = APIRouter()

def get_user_role_str(current_user) -> str:
    if hasattr(current_user.role, "role"):
        return str(current_user.role.role).lower()
    elif hasattr(current_user.role, "value"):
        return str(current_user.role.value).lower()
    elif hasattr(current_user.role, "name"):
        return str(current_user.role.name).lower()
    return str(current_user.role).split(".")[-1].lower()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Directory to store uploaded files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "reactivation_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def generate_dynamic_request_code(db: Session, district_id: str, district_name: str) -> str:
    name_clean = district_name.strip().lower()
    district_map = {"raipur": "RP", "bilaspur": "BP", "durg": "DG"}
    prefix = district_map.get(name_clean, "".join([c for c in name_clean if c.isalnum()])[:2].upper())
    if len(prefix) != 2: prefix = "XX"
    
    last_req = db.query(OperatorReactivationRequest).filter(
        OperatorReactivationRequest.district_id == district_id
    ).order_by(OperatorReactivationRequest.id.desc()).first()
    
    next_num = 1
    if last_req and last_req.request_code and "-R" in last_req.request_code:
        try:
            next_num = int(last_req.request_code.split("-R")[1]) + 1
        except ValueError:
            next_num = db.query(OperatorReactivationRequest).filter(
                OperatorReactivationRequest.district_id == district_id
            ).count() + 1
    else:
        next_num = db.query(OperatorReactivationRequest).filter(
            OperatorReactivationRequest.district_id == district_id
        ).count() + 1

    return f"{prefix}-R{next_num:04d}"


@router.post("/submit", status_code=status.HTTP_201_CREATED)
async def submit_operator_reactivation(
    training_date: str = Form(...),
    training_photo: Optional[UploadFile] = File(None),
    nodal_letter: Optional[UploadFile] = File(None),
    om_letter: Optional[UploadFile] = File(None),
    attendance_list: Optional[UploadFile] = File(None),
    manual_operators: str = Form(...), 
    reapply_request_code: str = Form(None),
    dc_remark: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user_role_str = get_user_role_str(current_user)
        if user_role_str != "dc": 
            raise HTTPException(status_code=403, detail="Access Denied. Only DC can submit requests.")
        if not current_user.district_id: 
            raise HTTPException(status_code=400, detail="Missing user district layout configuration mapping.")

        try:
            operator_rows = json.loads(manual_operators)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid operator rows payload JSON data structure matrix.")

        if len(operator_rows) == 0:
            raise HTTPException(status_code=400, detail="The operator log datagrid cannot be processed with zero rows.")

        if reapply_request_code:
            req = db.query(OperatorReactivationRequest).filter(
                OperatorReactivationRequest.request_code == reapply_request_code,
                OperatorReactivationRequest.dc_id == current_user.id
            ).first()
            if not req:
                raise HTTPException(status_code=404, detail="Original request not found or access denied.")
            
            req_code = reapply_request_code
            req.operator_count = len(operator_rows)
            req.training_date = date.fromisoformat(training_date.strip())
            req.status = "REAPPLIED"
            
            # Delete old operators (Documents are handled selectively below)
            db.query(ReactivationOperator).filter(ReactivationOperator.request_code == req_code).delete()
        else:
            # 🌟 CONNECTED: Queries target district_table configuration formats dynamically
            district = db.query(District).filter(District.district_code == str(current_user.district_id)).first()
            district_name = district.district_name if district else "Unknown"
            req_code = generate_dynamic_request_code(db, str(current_user.district_id), district_name)
    
            new_request = OperatorReactivationRequest(
                request_code=req_code,
                dc_id=current_user.id,
                district_id=str(current_user.district_id),
                operator_count=len(operator_rows),
                training_date=date.fromisoformat(training_date.strip()),
                status="PENDING"
            )
            db.add(new_request)

        request_folder = os.path.join(UPLOAD_DIR, req_code)
        os.makedirs(request_folder, exist_ok=True)
        document_files = {"training_photo": training_photo, "nodal_letter": nodal_letter, "om_letter": om_letter, "attendance_list": attendance_list}

        for doc_type, uploaded_file in document_files.items():
            if not uploaded_file or uploaded_file.filename == '':
                continue  # No new file uploaded, retain the existing one
                
            # If replacing an existing document during reapply, delete the old record for this doc_type
            if reapply_request_code:
                db.query(ReactivationDocument).filter(ReactivationDocument.request_code == req_code, ReactivationDocument.doc_type == doc_type).delete()
                
            uploaded_file.file.seek(0, 2)
            bytes_size = uploaded_file.file.tell()
            uploaded_file.file.seek(0)
            file_save_path = os.path.join(request_folder, f"{doc_type}_{uploaded_file.filename}")
            with open(file_save_path, "wb") as buffer:
                shutil.copyfileobj(uploaded_file.file, buffer)
            db.add(ReactivationDocument(request_code=req_code, doc_type=doc_type, path=file_save_path, original_filename=uploaded_file.filename, file_size=bytes_size))

        for op in operator_rows:
            parsed_cert_date = date.fromisoformat(op['certDate']) if op.get('certDate') else None
            db.add(ReactivationOperator(
                request_code=req_code,
                role=op.get('role', '').strip(),
                operator_name=str(op.get('name', '')).strip(),
                registrar_code=op.get('reg', '').strip(),
                ea_code=op.get('ea', '').strip(),
                user_code=op.get('user', '').strip(),
                certificate_number=op.get('cert', '').strip(),
                lms_certificate_id=op.get('lmsId', '').strip(),
                operator_mobile=str(op.get('mobile', '')).strip(),
                email_id=op.get('email', '').strip(),
                aadhaar_number=str(op.get('aadhar', '')).strip(),
                certification_date=parsed_cert_date,
                remarks=op.get('remarks', '').strip(),
                model_type=op.get('model', '').strip(),      
                status="PENDING"
            ))
        if reapply_request_code:
            db.add(ReactivationRemarkHistory(
                request_code=req_code,
                remark_history=dc_remark or "Reapplied by DC",
                sender_role="DC",
                status_after="REAPPLIED"
            ))
        else:
            db.add(ReactivationRemarkHistory(
                request_code=req_code,
                remark_history="Submitted by DC",
                sender_role="DC",
                status_after="PENDING"
            ))
            
        db.commit()
        return {"success": True, "request_code": req_code}
    except Exception as e:
        import traceback
        error_msg = f"FastAPI internal error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/requests")
async def get_reactivation_requests(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    user_role_str = get_user_role_str(current_user)
    
    query = db.query(OperatorReactivationRequest, District.district_name)\
              .outerjoin(District, OperatorReactivationRequest.district_id == District.district_code)
    if user_role_str == "dc":
        query = query.filter(OperatorReactivationRequest.district_id == str(current_user.district_id))
    
    requests = query.order_by(OperatorReactivationRequest.created_at.desc()).all()
        
    compiled_list = []
    for req, dist_name in requests:
        compiled_list.append({
            "id": req.id,
            "request_code": req.request_code,
            "operator_count": req.operator_count,
            "training_date": str(req.training_date) if req.training_date else "",
            "status": to_name(req.status_code, casing="upper").replace(" ", "_").strip(),
            "submitted_at": str(req.created_at)[:19] if req.created_at else "",
            "district_name": dist_name or "Raipur",
            "revert_reason": req.reject_reason or ""
        })
    return compiled_list


@router.get("/requests-with-operators")
async def get_reactivation_requests_with_operators(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    user_role_str = get_user_role_str(current_user)
    
    query = db.query(OperatorReactivationRequest, District.district_name)\
              .outerjoin(District, OperatorReactivationRequest.district_id == District.district_code)
    if user_role_str == "dc":
        query = query.filter(OperatorReactivationRequest.district_id == str(current_user.district_id))
    
    requests = query.order_by(OperatorReactivationRequest.created_at.desc()).all()
        
    compiled_list = []
    for req, dist_name in requests:
        operators = db.query(ReactivationOperator).filter(ReactivationOperator.request_code == req.request_code).all()
        ops_data = [
            {
                "id": op.id,
                "operator_name": op.operator_name,
                "operator_mobile": op.operator_mobile,
                "status": str(op.status).upper().replace(" ", "_"),
                "role": op.role or "Operator",
                "email_id": op.email_id or "",
                "registrar_code": op.registrar_code or "986",
                "ea_code": op.ea_code or "",
                "user_code": op.user_code or "",
                "model_type": op.model_type or "",
                "lms_certificate_id": op.lms_certificate_id or "",
                "certificate_number": op.certificate_number or "",
                "aadhaar_number": op.aadhaar_number or "",
                "certification_date": str(op.certification_date) if op.certification_date else "",
                "remarks": op.remarks or "",
                "reject_reason": op.reject_reason or ""
            }
            for op in operators
        ]
        
        # 🌟 CONNECTED: Order matching your model 'timestamp' attribute mapping definitions
        remarks_hist = db.query(ReactivationRemarkHistory).filter(ReactivationRemarkHistory.request_code == req.request_code).order_by(ReactivationRemarkHistory.timestamp.desc()).all()
        timeline_logs = [
            {
                "id": rm.id,
                "message": rm.remark_history,
                "sender_role": rm.sender_role,
                "timestamp": str(rm.timestamp)[:19] if rm.timestamp else "",
                "status_after": rm.status_after,
            }
            for rm in remarks_hist
        ]
        
        compiled_list.append({
            "id": req.id,
            "request_code": req.request_code,
            "operator_count": req.operator_count,
            "training_date": str(req.training_date) if req.training_date else "",
            "status": to_name(req.status_code, casing="upper").replace(" ", "_").strip(),
            "submitted_at": str(req.created_at)[:19] if req.created_at else "",
            "updated_at": str(req.updated_at)[:19] if req.updated_at else "",
            "district_name": dist_name or "Raipur",
            "revert_reason": req.reject_reason or "",
            "operators": ops_data,
            "timeline_logs": timeline_logs
        })
    return compiled_list


@router.get("/operators/{request_code}")
async def get_individual_operators_by_batch(request_code: str, db: Session = Depends(get_db)):
    operators = db.query(ReactivationOperator).filter(ReactivationOperator.request_code == request_code).all()
    ops_data = [
        {
            "id": op.id,
            "operator_name": op.operator_name,
            "operator_mobile": op.operator_mobile,
            "status": str(op.status).upper().replace(" ", "_"),
            "role": op.role or "Operator",
            "email_id": op.email_id or "",
            "registrar_code": op.registrar_code or "986",
            "ea_code": op.ea_code or "",
            "user_code": op.user_code or "",
            "model_type": op.model_type or "",
            "lms_certificate_id": op.lms_certificate_id or "",
            "certificate_number": op.certificate_number or "",
            "aadhaar_number": op.aadhaar_number or "",
            "certification_date": str(op.certification_date) if op.certification_date else "",
            "remarks": op.remarks or "",
            "reject_reason": op.reject_reason or ""
        }
        for op in operators
    ]
    
    remarks_hist = db.query(ReactivationRemarkHistory).filter(ReactivationRemarkHistory.request_code == request_code).order_by(ReactivationRemarkHistory.timestamp.desc()).all()
    timeline_logs = [
        {
            "id": rm.id,
            "message": rm.remark_history,
            "sender_role": rm.sender_role,
            "timestamp": str(rm.timestamp)[:19] if rm.timestamp else "",
            "status_after": rm.status_after,
        }
        for rm in remarks_hist
    ]
    
    return {
        "operators": ops_data,
        "timeline_logs": timeline_logs
    }


@router.post("/operator/{operator_id}/activate")
async def activate_individual_operator(operator_id: int, reason: Optional[str] = Form(None), db: Session = Depends(get_db)):
    op = db.query(ReactivationOperator).filter(ReactivationOperator.id == operator_id).first()
    if op: 
        op.status = "ACTIVATED"
        if reason:
            op.reject_reason = reason  # Optional: store activate remarks in reject_reason or remarks
        remark_text = f"Operator '{op.operator_name}' Activated."
        if reason:
            remark_text += f" Remarks: {reason}"
        db.add(ReactivationRemarkHistory(
            request_code=op.request_code,
            remark_history=remark_text,
            sender_role="CHIPS_ADMIN",
            status_after=op.status
        ))
        db.commit()
    return {"success": True}


@router.post("/operator/{operator_id}/send-to-uidai")
async def send_to_uidai_individual_operator(operator_id: int, remarks: Optional[str] = Form(None), db: Session = Depends(get_db)):
    op = db.query(ReactivationOperator).filter(ReactivationOperator.id == operator_id).first()
    if op: 
        op.status = "SENT_TO_UIDAI"
        remark_text = f"Sent to UIDAI. Remarks: {remarks.strip()}" if remarks and remarks.strip() else "Sent to UIDAI"
        db.add(ReactivationRemarkHistory(
            request_code=op.request_code,
            remark_history=f"Operator '{op.operator_name}' {remark_text}",
            sender_role="CHIPS_ADMIN",
            status_after=op.status
        ))
        db.commit()
    return {"success": True}

@router.post("/operator/{operator_id}/revert")
async def revert_individual_operator(operator_id: int, reason: str = Form(...), db: Session = Depends(get_db)):
    op = db.query(ReactivationOperator).filter(ReactivationOperator.id == operator_id).first()
    if op: 
        op.status = "REVERTED"
        op.reject_reason = reason
        db.add(ReactivationRemarkHistory(
            request_code=op.request_code,
            remark_history=f"Operator '{op.operator_name}' Reverted. Reason: {reason}",
            sender_role="CHIPS_ADMIN",
            status_after=op.status
        ))
        db.commit()
    return {"success": True}

@router.post("/operator/{operator_id}/reject")
async def reject_individual_operator(operator_id: int, reason: str = Form(...), db: Session = Depends(get_db)):
    op = db.query(ReactivationOperator).filter(ReactivationOperator.id == operator_id).first()
    if op: 
        op.status = "REJECTED"
        op.reject_reason = reason
        db.add(ReactivationRemarkHistory(
            request_code=op.request_code,
            remark_history=f"Operator '{op.operator_name}' Rejected. Reason: {reason}",
            sender_role="CHIPS_ADMIN",
            status_after=op.status
        ))
        db.commit()
    return {"success": True}


@router.post("/operator/{operator_id}/update_reapply")
async def update_and_reapply_operator(
    operator_id: int,
    operator_name: str = Form(None),
    operator_mobile: str = Form(None),
    email_id: str = Form(None),
    model_type: str = Form(None),
    lms_certificate_id: str = Form(None),
    certificate_number: str = Form(None),
    aadhaar_number: str = Form(None),
    role: str = Form(None),
    registrar_code: str = Form(None),
    ea_code: str = Form(None),
    user_code: str = Form(None),
    db: Session = Depends(get_db)
):
    op = db.query(ReactivationOperator).filter(ReactivationOperator.id == operator_id).first()
    if not op:
        raise HTTPException(status_code=404, detail="Operator not found")
    
    if operator_name: op.operator_name = operator_name
    if operator_mobile: op.operator_mobile = operator_mobile
    if email_id: op.email_id = email_id
    if model_type: op.model_type = model_type
    if lms_certificate_id: op.lms_certificate_id = lms_certificate_id
    if certificate_number: op.certificate_number = certificate_number
    if aadhaar_number: op.aadhaar_number = aadhaar_number
    if role: op.role = role
    if registrar_code: op.registrar_code = registrar_code
    if ea_code: op.ea_code = ea_code
    if user_code: op.user_code = user_code
    
    op.status = "REAPPLIED"
    
    # Also update the batch status back to REAPPLIED if it was REVERTED
    req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.request_code == op.request_code).first()
    if req and req.status == "REVERTED":
        req.status = "REAPPLIED"

    db.add(ReactivationRemarkHistory(
        request_code=op.request_code,
        remark_history=f"Operator '{op.operator_name}' Reapplied and Details Updated",
        sender_role="DC",
        status_after=req.status if req else "REAPPLIED"
    ))

    db.commit()
    return {"success": True}


@router.post("/requests/{request_code}/finalize")
async def finalize_batch_request(request_code: str, db: Session = Depends(get_db)):
    try:
        req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.request_code == request_code).first()
        if req: 
            operators = db.query(ReactivationOperator).filter(
                ReactivationOperator.request_code == request_code
            ).all()
            statuses = [op.status for op in operators]
            
            if req.status in ["PENDING", "REAPPLIED"]:
                if "SENT_TO_UIDAI" in statuses:
                    req.status = "SENT_TO_UIDAI"
                else:
                    req.status = "REVERTED"
            elif req.status == "SENT_TO_UIDAI":
                req.status = "REVIEWED"
            else:
                if "REVERTED" in statuses and "ACTIVATED" not in statuses:
                    req.status = "REVERTED"
                else:
                    req.status = "REVIEWED"
                    
            db.add(ReactivationRemarkHistory(
                request_code=request_code, 
                remark_history=f"Batch Finalized. New Status: {req.status}", 
                sender_role="CHIPS_ADMIN", 
                status_after=req.status
            ))
            db.commit()
        return {"success": True}
    except Exception as e:
        import traceback
        error_msg = f"FastAPI internal error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return {"success": False, "error": str(e)}


@router.post("/requests/{request_code}/revert")
async def revert_batch_request(request_code: str, revert_reason: str = Form(...), db: Session = Depends(get_db)):
    req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.request_code == request_code).first()
    if req: 
        req.status = "REVERTED"
        req.reject_reason = revert_reason
        db.add(ReactivationRemarkHistory(
            request_code=req.request_code,
            remark_history=f"Batch Reverted. Reason: {revert_reason}",
            sender_role="CHIPS_ADMIN",
            status_after="REVERTED"
        ))
        db.commit()
    return {"success": True}


@router.post("/requests/{request_code}/send-to-uidai")
async def backend_batch_request_to_uidai(request_code: str, remarks: str = Form(...), db: Session = Depends(get_db)):
    req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.request_code == request_code).first()
    if req: 
        req.status = "SENT_TO_UIDAI"
    db.query(ReactivationOperator).filter(ReactivationOperator.request_code == request_code).update({"status": "SENT_TO_UIDAI"})
    db.add(ReactivationRemarkHistory(request_code=request_code, remark_history=remarks, sender_role="CHIPS", status_after="SENT_TO_UIDAI"))
    db.commit()
    return {"success": True}


@router.get("/export-excel/{request_code}")
def export_operators_to_excel_stream(request_code: str, db: Session = Depends(get_db)):

# --- FRIEND'S UPDATED CODE ---
    operators = db.query(ReactivationOperator).filter(
        ReactivationOperator.request_code == request_code,
        ReactivationOperator.status != "REJECTED"
    ).all()
    df = pd.DataFrame([{
        "S.No": i + 1,
        "Role": o.role,
        "Name As Per Aadhaar": o.operator_name,
        "Registrar Code": o.registrar_code,
        "EA Code": o.ea_code,
        "User Code": o.user_code,
        "NSEIT Certificate Number": o.certificate_number,
        "LMS Certificate ID": o.lms_certificate_id,
        "Mobile": o.operator_mobile,
        "Primary E-MAIL ID": o.email_id,
        "Status": o.status
    } for i, o in enumerate(operators)])
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer: 
        df.to_excel(writer, index=False)
    excel_buffer.seek(0)
    return StreamingResponse(excel_buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=List_{request_code}.xlsx"})
# --- YOUR LOCAL CODE ---
    operators = db.query(ReactivationOperator).filter(ReactivationOperator.request_code == request_code).all()
    export_data = [{
        "s_no": i + 1,
        "role": o.role,
        "operator_name": o.operator_name,
        "registrar_code": o.registrar_code,
        "ea_code": o.ea_code,
        "user_code": o.user_code,
        "certificate_number": o.certificate_number,
        "lms_certificate_id": o.lms_certificate_id,
        "operator_mobile": o.operator_mobile,
        "email_id": o.email_id,
        "status": o.status
    } for i, o in enumerate(operators)]
    
    column_mappings = {
        "s_no": "S.No", "role": "Role", "operator_name": "Name As Per Aadhaar",
        "registrar_code": "Registrar Code", "ea_code": "EA Code", "user_code": "User Code",
        "certificate_number": "NSEIT Certificate Number", "lms_certificate_id": "LMS Certificate ID",
        "operator_mobile": "Mobile", "email_id": "Primary E-MAIL ID", "status": "Status"
    }
    return generate_excel_export(export_data, column_mappings, f"List_{request_code}")

# ---------------------------



@router.get("/export-csv-all")
def export_all_operators_to_csv_stream(ids: str = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_role_str = get_user_role_str(current_user)
    
    query = db.query(ReactivationOperator, OperatorReactivationRequest, District.district_name).\
        join(OperatorReactivationRequest, ReactivationOperator.request_code == OperatorReactivationRequest.request_code).\
        outerjoin(District, OperatorReactivationRequest.district_id == District.district_code).\
        filter(ReactivationOperator.status.notin_(["REVERTED", "ACTIVATED", "REJECTED"]))
    
    if ids:
        batch_codes = [code.strip() for code in ids.split(",") if code.strip()]
        query = query.filter(OperatorReactivationRequest.request_code.in_(batch_codes))
    if user_role_str == "dc":
        query = query.filter(OperatorReactivationRequest.district_id == str(current_user.district_id))
        
    results = query.all()
    
    export_data = []
    for i, (o, req, dist_name) in enumerate(results):
        export_data.append({
            "s_no": i + 1,
            "request_code": o.request_code,
            "district_name": dist_name,
            "role": o.role,
            "operator_name": o.operator_name,
            "registrar_code": o.registrar_code,
            "ea_code": o.ea_code,
            "user_code": o.user_code,
            "certificate_number": o.certificate_number,
            "lms_certificate_id": o.lms_certificate_id,
            "operator_mobile": o.operator_mobile,
            "email_id": o.email_id,
            "status": o.status,
            "submitted_at": req.created_at.strftime("%Y-%m-%d %H:%M:%S") if req.created_at else "—"
        })
        
    column_mappings = {
        "s_no": "S.No", 
        "request_code": "Batch Request ID", 
        "district_name": "District Name",
        "role": "Role Profile", 
        "operator_name": "Name As Per Aadhaar", 
        "registrar_code": "Registrar Code",
        "ea_code": "EA Code", 
        "user_code": "User Code", 
        "certificate_number": "NSEIT Certificate Number",
        "lms_certificate_id": "LMS Certificate ID", 
        "operator_mobile": "Mobile Phone Number",
        "email_id": "Primary E-MAIL ID", 
        "status": "Current Audit Status", 
        "submitted_at": "Submission Date"
    }
    return generate_csv_export(export_data, column_mappings, "All_Pending_Reactivation_Operators")


@router.get("/export-csv-uidai")
def export_uidai_operators_to_csv_stream(ids: str = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_role_str = get_user_role_str(current_user)
    
    query = db.query(ReactivationOperator, OperatorReactivationRequest, District.district_name).\
        join(OperatorReactivationRequest, ReactivationOperator.request_code == OperatorReactivationRequest.request_code).\
        outerjoin(District, OperatorReactivationRequest.district_id == District.district_code).\
        filter(ReactivationOperator.status.in_(["SENT_TO_UIDAI", "SENT TO UIDAI"]))
    
    if ids:
        batch_codes = [code.strip() for code in ids.split(",") if code.strip()]
        query = query.filter(OperatorReactivationRequest.request_code.in_(batch_codes))
    if user_role_str == "dc":
        query = query.filter(OperatorReactivationRequest.district_id == str(current_user.district_id))
        
    results = query.all()
    
    export_data = []
    for i, (o, req, dist_name) in enumerate(results):
        export_data.append({
            "s_no": i + 1,
            "request_code": o.request_code,
            "district_name": dist_name,
            "role": o.role,
            "operator_name": o.operator_name,
            "registrar_code": o.registrar_code,
            "ea_code": o.ea_code,
            "user_code": o.user_code,
            "certificate_number": o.certificate_number,
            "lms_certificate_id": o.lms_certificate_id,
            "operator_mobile": o.operator_mobile,
            "email_id": o.email_id,
            "status": o.status,
            "submitted_at": req.created_at.strftime("%Y-%m-%d %H:%M:%S") if req.created_at else "—"
        })
        
    column_mappings = {
        "s_no": "S.No", 
        "request_code": "Batch Request ID", 
        "district_name": "District Name",
        "role": "Role Profile", 
        "operator_name": "Name As Per Aadhaar", 
        "registrar_code": "Registrar Code",
        "ea_code": "EA Code", 
        "user_code": "User Code", 
        "certificate_number": "NSEIT Certificate Number",
        "lms_certificate_id": "LMS Certificate ID", 
        "operator_mobile": "Mobile Phone Number",
        "email_id": "Primary E-MAIL ID", 
        "status": "Current Audit Status", 
        "submitted_at": "Submission Date"
    }
    return generate_csv_export(export_data, column_mappings, "UIDAI_Sent_Reactivation_Operators")

@router.get("/requests/{request_code}/files/{file_type}")
async def get_reactivation_file(request_code: str, file_type: str, db: Session = Depends(get_db)):
    doc = db.query(ReactivationDocument).filter(
        ReactivationDocument.request_code == request_code,
        ReactivationDocument.doc_type == file_type
    ).first()
    if not doc or not os.path.exists(doc.path):
        raise HTTPException(status_code=404, detail="File not found")
    
    mime_type, _ = mimetypes.guess_type(doc.path)
    if not mime_type:
        mime_type = "application/octet-stream"
        
    return FileResponse(
        path=doc.path,
        filename=doc.original_filename,
        media_type=mime_type,
        content_disposition_type="inline"
    )
