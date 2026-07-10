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
from backend.models.base import to_name, get_ist_now, StatusEnum


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
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "reactivation")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def generate_dynamic_request_code(db: Session, district_id: str, district_name: str) -> str:
    district = db.query(District).filter(District.district_code == str(district_id)).first()
    prefix = district.district_short_name if district else None
    
    if not prefix:
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

        district = db.query(District).filter(District.district_code == str(current_user.district_id)).first()
        district_name = district.district_name if district else "Unknown"
        district_folder = district_name.strip().replace(" ", "_").upper()

        if reapply_request_code:
            req = db.query(OperatorReactivationRequest).filter(
                OperatorReactivationRequest.request_code == reapply_request_code,
                OperatorReactivationRequest.dc_id == current_user.id
            ).first()
            if not req:
                raise HTTPException(status_code=404, detail="Original request not found or access denied.")
            
            req_code = reapply_request_code
            
            # Count the untouched operators in the batch (e.g. APPROVED or SENT_TO_UIDAI)
            untouched_count = db.query(ReactivationOperator).filter(
                ReactivationOperator.request_id == req.id,
                ~ReactivationOperator.status_id.in_([StatusEnum.REVERTED.value, StatusEnum.REJECTED.value])
            ).count()
            req.operator_count = untouched_count + len(operator_rows)
            
            req.training_date = date.fromisoformat(training_date.strip())
            req.status_id = StatusEnum.REAPPLIED.value
            
            # Delete only the specific reverted/rejected operators that are being resubmitted
            submitted_ids = [op.get('id') for op in operator_rows if op.get('id')]
            if submitted_ids:
                db.query(ReactivationOperator).filter(
                    ReactivationOperator.request_id == req.id,
                    ReactivationOperator.id.in_(submitted_ids)
                ).delete()
            else:
                db.query(ReactivationOperator).filter(
                    ReactivationOperator.request_id == req.id,
                    ReactivationOperator.status_id.in_([StatusEnum.REVERTED.value, StatusEnum.REJECTED.value])
                ).delete()
        else:

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
            db.flush()  # To get new_request.id

        active_req_id = req.id if reapply_request_code else new_request.id
        request_folder = os.path.join(BASE_DIR, "uploads", "reactivation", district_folder, req_code)

        os.makedirs(request_folder, exist_ok=True)
        document_files = {"training_photo": training_photo, "nodal_letter": nodal_letter, "om_letter": om_letter, "attendance_list": attendance_list}

        for doc_type, uploaded_file in document_files.items():
            if not uploaded_file or uploaded_file.filename == '':
                continue  # No new file uploaded, retain the existing one
                
            # If replacing an existing document during reapply, delete the old record for this doc_type
            if reapply_request_code:
                db.query(ReactivationDocument).filter(ReactivationDocument.request_id == active_req_id, ReactivationDocument.doc_type == doc_type).delete()
                

            uploaded_file.file.seek(0, 2)
            bytes_size = uploaded_file.file.tell()
            uploaded_file.file.seek(0)
            file_save_path = os.path.join(request_folder, f"{doc_type}_{uploaded_file.filename}")
            with open(file_save_path, "wb") as buffer:
                shutil.copyfileobj(uploaded_file.file, buffer)
            db.add(ReactivationDocument(request_id=active_req_id, doc_type=doc_type, path=file_save_path, original_filename=uploaded_file.filename, file_size=bytes_size))

        operators_added = []
        for op in operator_rows:
            parsed_cert_date = date.fromisoformat(op['certDate']) if op.get('certDate') else None
            new_op = ReactivationOperator(
                request_id=active_req_id,

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
                status="REAPPLIED" if reapply_request_code else "PENDING"
            )
            db.add(new_op)
            operators_added.append(new_op)
            
        db.flush()
        
        for new_op in operators_added:
            msg = f"Operator '{new_op.operator_name}' {'is reapplied' if reapply_request_code else 'is submitted'} by DC"
            if reapply_request_code and dc_remark:
                msg += f". Remarks: {dc_remark.strip()}"
                
            db.add(ReactivationRemarkHistory(
                request_id=active_req_id,
                operator_id=new_op.id,
                author_id=current_user.id,
                remark_history=msg,
                sender_role="DC",
                status_after="REAPPLIED" if reapply_request_code else "PENDING"

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
    
    requests = query.order_by(OperatorReactivationRequest.updated_at.desc()).all()
        
    compiled_list = []
    for req, dist_name in requests:
        compiled_list.append({
            "id": req.id,
            "request_code": req.request_code,
            "operator_count": req.operator_count,
            "training_date": str(req.training_date) if req.training_date else "",
            "status": to_name(req.status_id).upper().replace(" ", "_").strip(),
            "submitted_at": str(req.created_at)[:19] if req.created_at else "",
            "district_name": dist_name or "Raipur",
            "revert_reason": next((r.remark_history for r in reversed(req.remarks) if r.status_after_id in [StatusEnum.REVERTED.value, StatusEnum.REJECTED.value]), "")

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
    
    requests = query.order_by(OperatorReactivationRequest.updated_at.desc()).all()
        
    compiled_list = []
    for req, dist_name in requests:
        operators = db.query(ReactivationOperator).filter(ReactivationOperator.request_id == req.id).all()

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
        remarks_hist = db.query(ReactivationRemarkHistory).filter(ReactivationRemarkHistory.request_id == req.id).order_by(ReactivationRemarkHistory.timestamp.asc()).all()

        timeline_logs = [
            {
                "id": rm.id,
                "message": rm.remark_history,
                "sender_role": rm.sender_role,
                "sender_username": rm.author.username if rm.author else "",
                "timestamp": str(rm.timestamp)[:19] if rm.timestamp else "",
                "status_after": rm.status_after,
                "operator_id": rm.operator_id,

            }
            for rm in remarks_hist
        ]
        
        compiled_list.append({
            "id": req.id,
            "request_code": req.request_code,
            "operator_count": req.operator_count,
            "training_date": str(req.training_date) if req.training_date else "",
            "status": to_name(req.status_id).upper().replace(" ", "_").strip(),
            "submitted_at": str(req.created_at)[:19] if req.created_at else "",
            "updated_at": str(req.updated_at)[:19] if req.updated_at else "",
            "district_name": dist_name or "Raipur",
            "revert_reason": next((r.remark_history for r in reversed(req.remarks) if r.status_after_id in [StatusEnum.REVERTED.value, StatusEnum.REJECTED.value]), ""),

            "operators": ops_data,
            "timeline_logs": timeline_logs
        })
    return compiled_list


@router.get("/operators/{request_code}")
async def get_individual_operators_by_batch(request_code: str, db: Session = Depends(get_db)):
    req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.request_code == request_code).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    operators = db.query(ReactivationOperator).filter(ReactivationOperator.request_id == req.id).all()

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
    req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.request_code == request_code).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    remarks_hist = db.query(ReactivationRemarkHistory).filter(ReactivationRemarkHistory.request_id == req.id).order_by(ReactivationRemarkHistory.timestamp.asc()).all()

    timeline_logs = [
        {
            "id": rm.id,
            "message": rm.remark_history,
            "sender_role": rm.sender_role,
            "sender_username": rm.author.username if rm.author else "",
            "timestamp": str(rm.timestamp)[:19] if rm.timestamp else "",
            "status_after": rm.status_after,
            "operator_id": rm.operator_id,

        }
        for rm in remarks_hist
    ]
    
    docs = db.query(ReactivationDocument).filter(ReactivationDocument.request_id == req.id).all()
    docs_data = {
        doc.doc_type: {
            "original_filename": doc.original_filename,
            "path": doc.path
        }
        for doc in docs
    }
    
    # Get batch revert/rejection reason
    latest_revert_log = db.query(ReactivationRemarkHistory).filter(
        ReactivationRemarkHistory.request_id == req.id,
        ReactivationRemarkHistory.status_after_id.in_([StatusEnum.REVERTED.value, StatusEnum.REJECTED.value])
    ).order_by(ReactivationRemarkHistory.timestamp.desc()).first()
    batch_revert_reason = latest_revert_log.remark_history if latest_revert_log else ""

    return {
        "operators": ops_data,
        "timeline_logs": timeline_logs,
        "documents": docs_data,
        "batch_status": req.status,
        "batch_revert_reason": batch_revert_reason

    }


@router.post("/operator/{operator_id}/activate")
async def activate_individual_operator(operator_id: int, reason: Optional[str] = Form(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    op = db.query(ReactivationOperator).filter(ReactivationOperator.id == operator_id).first()
    if op: 
        op.status_id = StatusEnum.APPROVED.value
        if reason:
            op.reject_reason = reason  # Optional: store activate remarks in reject_reason or remarks
        
        # Update parent's updated_at
        parent = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.id == op.request_id).first()
        if parent:
            parent.updated_at = get_ist_now()

        remark_text = reason.strip() if reason and reason.strip() else "Approved"
        db.add(ReactivationRemarkHistory(
            request_id=op.request_id,
            operator_id=op.id,
            author_id=current_user.id,
            remark_history=remark_text,
            sender_role="CHIPS_ADMIN",
            status_after_id=op.status_id

        ))
        db.commit()
    return {"success": True}


@router.post("/operator/{operator_id}/send-to-uidai")
async def send_to_uidai_individual_operator(operator_id: int, remarks: Optional[str] = Form(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    op = db.query(ReactivationOperator).filter(ReactivationOperator.id == operator_id).first()
    if op: 
        op.status_id = StatusEnum.SENT_TO_UIDAI.value
        
        # Update parent's updated_at
        parent = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.id == op.request_id).first()
        if parent:
            parent.updated_at = get_ist_now()

        remark_text = remarks.strip() if remarks and remarks.strip() else "Sent to UIDAI"
        db.add(ReactivationRemarkHistory(
            request_id=op.request_id,
            operator_id=op.id,
            author_id=current_user.id,
            remark_history=remark_text,
            sender_role="CHIPS_ADMIN",
            status_after_id=op.status_id

        ))
        db.commit()
    return {"success": True}

@router.post("/operator/{operator_id}/revert")
async def revert_individual_operator(operator_id: int, reason: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    op = db.query(ReactivationOperator).filter(ReactivationOperator.id == operator_id).first()
    if op: 
        op.status_id = StatusEnum.REVERTED.value
        op.reject_reason = reason
        
        # Update parent's updated_at
        parent = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.id == op.request_id).first()
        if parent:
            parent.updated_at = get_ist_now()

        db.add(ReactivationRemarkHistory(
            request_id=op.request_id,
            operator_id=op.id,
            author_id=current_user.id,
            remark_history=reason.strip(),
            sender_role="CHIPS_ADMIN",
            status_after_id=op.status_id
        ))
        db.commit()
    return {"success": True}

@router.post("/operator/{operator_id}/reject")
async def reject_individual_operator(operator_id: int, reason: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    op = db.query(ReactivationOperator).filter(ReactivationOperator.id == operator_id).first()
    if op: 
        op.status_id = StatusEnum.REJECTED.value
        op.reject_reason = reason
        
        # Update parent's updated_at
        parent = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.id == op.request_id).first()
        if parent:
            parent.updated_at = get_ist_now()

        db.add(ReactivationRemarkHistory(
            request_id=op.request_id,
            operator_id=op.id,
            author_id=current_user.id,
            remark_history=reason.strip(),
            sender_role="CHIPS_ADMIN",
            status_after_id=op.status_id

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)

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
    
    op.status_id = StatusEnum.REAPPLIED.value
    
    # Also update the batch status back to REAPPLIED if it was REVERTED
    req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.id == op.request_id).first()
    if req:
        req.updated_at = get_ist_now()
        if req.status_id == StatusEnum.REVERTED.value:
            req.status_id = StatusEnum.REAPPLIED.value

    db.add(ReactivationRemarkHistory(
        request_id=req.id,
        operator_id=op.id,
        author_id=current_user.id,
        remark_history=f"Operator '{op.operator_name}' Reapplied and Details Updated",
        sender_role="DC",
        status_after_id=req.status_id if req else StatusEnum.REAPPLIED.value

    ))

    db.commit()
    return {"success": True}


@router.post("/requests/{request_code}/finalize")
async def finalize_batch_request(request_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):

    try:
        req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.request_code == request_code).first()
        if req: 
            operators = db.query(ReactivationOperator).filter(
                ReactivationOperator.request_id == req.id
            ).all()
            statuses = [op.status_id for op in operators]
            
            if req.status_id in [StatusEnum.PENDING.value, StatusEnum.REAPPLIED.value]:
                if StatusEnum.SENT_TO_UIDAI.value in statuses:
                    req.status_id = StatusEnum.SENT_TO_UIDAI.value
                    req.reviewed_by = current_user.id
                else:
                    req.status_id = StatusEnum.REVERTED.value
                    req.reviewed_by = current_user.id
            elif req.status_id == StatusEnum.SENT_TO_UIDAI.value:
                req.status_id = StatusEnum.REVIEWED.value
                req.reviewed_by = current_user.id
            else:
                if StatusEnum.REVERTED.value in statuses and StatusEnum.APPROVED.value not in statuses:
                    req.status_id = StatusEnum.REVERTED.value
                    req.reviewed_by = current_user.id
                else:
                    req.status_id = StatusEnum.REVIEWED.value
                    req.reviewed_by = current_user.id
                    
            db.add(ReactivationRemarkHistory(
                request_id=req.id,
                author_id=current_user.id, 
                remark_history=f"Batch Finalized. New Status: {req.status}", 
                sender_role="CHIPS_ADMIN", 
                status_after_id=req.status_id
            ))

            db.commit()
        return {"success": True}
    except Exception as e:
        import traceback
        error_msg = f"FastAPI internal error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return {"success": False, "error": str(e)}


@router.post("/requests/{request_code}/revert")
async def revert_batch_request(request_code: str, revert_reason: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.request_code == request_code).first()
    if req: 
        req.status_id = StatusEnum.REVERTED.value
        req.reviewed_by = current_user.id
        req.updated_at = get_ist_now()
        
        operators = db.query(ReactivationOperator).filter(ReactivationOperator.request_id == req.id).all()
        for op in operators:
            op.status_id = StatusEnum.REVERTED.value
            op.reject_reason = revert_reason
            db.add(ReactivationRemarkHistory(
                request_id=req.id,
                operator_id=op.id,
                author_id=current_user.id,
                remark_history=revert_reason.strip(),
                sender_role="CHIPS",
                status_after_id=StatusEnum.REVERTED.value
            ))
            

        db.commit()
    return {"success": True}


@router.post("/requests/{request_code}/send-to-uidai")
async def backend_batch_request_to_uidai(request_code: str, remarks: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.request_code == request_code).first()
    if req: 
        req.status_id = StatusEnum.SENT_TO_UIDAI.value
        req.reviewed_by = current_user.id
        req.updated_at = get_ist_now()
        
        operators = db.query(ReactivationOperator).filter(
            ReactivationOperator.request_id == req.id,
            ReactivationOperator.status_id.in_([StatusEnum.PENDING.value, StatusEnum.REAPPLIED.value])
        ).all()
        for op in operators:
            op.status_id = StatusEnum.SENT_TO_UIDAI.value
            remark_text = remarks.strip() if remarks and remarks.strip() else "Sent to UIDAI"
            db.add(ReactivationRemarkHistory(
                request_id=req.id,
                operator_id=op.id,
                author_id=current_user.id,
                remark_history=remark_text,
                sender_role="CHIPS",
                status_after_id=StatusEnum.SENT_TO_UIDAI.value
            ))
            
        db.commit()
    return {"success": True}


@router.post("/requests/{request_code}/approve-all")
async def approve_all_operators_in_batch(request_code: str, reason: Optional[str] = Form(None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.request_code == request_code).first()
    if req:
        req.status_id = StatusEnum.REVIEWED.value
        req.reviewed_by = current_user.id
        req.updated_at = get_ist_now()
        
        operators = db.query(ReactivationOperator).filter(ReactivationOperator.request_id == req.id).all()
        for op in operators:
            op.status_id = StatusEnum.APPROVED.value
            if reason:
                op.reject_reason = reason
            
            remark_text = reason.strip() if reason and reason.strip() else "Approved"
            db.add(ReactivationRemarkHistory(
                request_id=req.id,
                operator_id=op.id,
                author_id=current_user.id,
                remark_history=remark_text,
                sender_role="CHIPS_ADMIN",
                status_after_id=StatusEnum.APPROVED.value
            ))
        
        db.commit()
    return {"success": True}


@router.post("/requests/{request_code}/reject-all")
async def reject_all_operators_in_batch(request_code: str, reason: str = Form(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.request_code == request_code).first()
    if req:
        req.status_id = StatusEnum.REVIEWED.value
        req.reviewed_by = current_user.id
        req.updated_at = get_ist_now()
        
        operators = db.query(ReactivationOperator).filter(ReactivationOperator.request_id == req.id).all()
        for op in operators:
            op.status_id = StatusEnum.REJECTED.value
            op.reject_reason = reason
            
            db.add(ReactivationRemarkHistory(
                request_id=req.id,
                operator_id=op.id,
                author_id=current_user.id,
                remark_history=reason.strip(),
                sender_role="CHIPS_ADMIN",
                status_after_id=StatusEnum.REJECTED.value
            ))
        
        db.commit()

    return {"success": True}


@router.get("/export-excel/{request_code}")
def export_operators_to_excel_stream(request_code: str, db: Session = Depends(get_db)):
    operators = db.query(ReactivationOperator).join(
        OperatorReactivationRequest, ReactivationOperator.request_id == OperatorReactivationRequest.id
    ).filter(
        OperatorReactivationRequest.request_code == request_code,
        ReactivationOperator.status_id != StatusEnum.REJECTED.value
    ).all()
    
    def get_display_status(status_str):
        s = str(status_str or '').upper().strip()
        return "APPROVED" if s in ["ACTIVE", "APPROVED"] else s

    df = pd.DataFrame([{
        "S.No": i + 1,
        "Role": o.role,
        "Name As Per Aadhaar": o.operator_name,
        "Aadhaar Number": o.aadhaar_number,

        "Registrar Code": o.registrar_code,
        "EA Code": o.ea_code,
        "User Code": o.user_code,
        "NSEIT Certificate Number": o.certificate_number,
        "LMS Certificate ID": o.lms_certificate_id,
        "Mobile": o.operator_mobile,
        "Primary E-MAIL ID": o.email_id,
        "Status": get_display_status(o.status)

    } for i, o in enumerate(operators)])
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer: 
        df.to_excel(writer, index=False)
    excel_buffer.seek(0)
    return StreamingResponse(excel_buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=List_{request_code}.xlsx"})


@router.get("/export-csv-all")
def export_all_operators_to_csv_stream(ids: str = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_role_str = get_user_role_str(current_user)
    
    query = db.query(ReactivationOperator, OperatorReactivationRequest, District.district_name).\
        join(OperatorReactivationRequest, ReactivationOperator.request_id == OperatorReactivationRequest.id).\
        outerjoin(District, OperatorReactivationRequest.district_id == District.district_code)
    
    if ids:
        id_tokens = [code.strip() for code in ids.split(",") if code.strip()]
        if id_tokens:
            if all(token.isdigit() for token in id_tokens):
                operator_ids = [int(token) for token in id_tokens]
                query = query.filter(ReactivationOperator.id.in_(operator_ids))
            else:
                query = query.filter(OperatorReactivationRequest.request_code.in_(id_tokens))
    else:
        query = query.filter(ReactivationOperator.status_id.notin_([StatusEnum.REVERTED.value, StatusEnum.APPROVED.value, StatusEnum.REJECTED.value]))
        

    if user_role_str == "dc":
        query = query.filter(OperatorReactivationRequest.district_id == str(current_user.district_id))
        
    results = query.all()
    
    export_data = []
    for i, (o, req, dist_name) in enumerate(results):
        status_upper = (o.status or '').upper().strip()
        if status_upper == 'PENDING':
            reviewed_time = ""
        else:
            reviewed_time = req.updated_at.strftime("%Y-%m-%d %H:%M:%S") if req.updated_at else "—"
        
        display_status = "APPROVED" if status_upper in ["ACTIVE", "APPROVED"] else status_upper

        export_data.append({
            "s_no": i + 1,
            "request_code": req.request_code,
            "district_name": dist_name,
            "role": o.role,
            "operator_name": o.operator_name,
            "aadhaar_number": o.aadhaar_number,
            "registrar_code": o.registrar_code,
            "ea_code": o.ea_code,
            "user_code": o.user_code,
            "certificate_number": o.certificate_number,
            "lms_certificate_id": o.lms_certificate_id,
            "operator_mobile": o.operator_mobile,
            "email_id": o.email_id,
            "status": display_status,
            "submitted_at": req.created_at.strftime("%Y-%m-%d %H:%M:%S") if req.created_at else "—",
            "reviewed_at": reviewed_time
        })
        
    column_mappings = {
        "s_no": "S.No", 
        "request_code": "Batch Request ID", 
        "district_name": "District Name",
        "role": "Role Profile", 
        "operator_name": "Name As Per Aadhaar", 
        "aadhaar_number": "Aadhaar Number",
        "registrar_code": "Registrar Code",
        "ea_code": "EA Code", 
        "user_code": "User Code", 
        "certificate_number": "NSEIT Certificate Number",
        "lms_certificate_id": "LMS Certificate ID", 
        "operator_mobile": "Mobile Phone Number",
        "email_id": "Primary E-MAIL ID", 
        "status": "Current Audit Status", 
        "submitted_at": "Submission Date",
        "reviewed_at": "Reviewed Time"
    }
    return generate_csv_export(export_data, column_mappings, "All_Pending_Reactivation_Operators")


@router.get("/export-csv-uidai")
def export_uidai_operators_to_csv_stream(ids: str = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_role_str = get_user_role_str(current_user)
    
    query = db.query(ReactivationOperator, OperatorReactivationRequest, District.district_name).\
        join(OperatorReactivationRequest, ReactivationOperator.request_id == OperatorReactivationRequest.id).\
        outerjoin(District, OperatorReactivationRequest.district_id == District.district_code)
    
    if ids:
        id_tokens = [code.strip() for code in ids.split(",") if code.strip()]
        if id_tokens:
            if all(token.isdigit() for token in id_tokens):
                operator_ids = [int(token) for token in id_tokens]
                query = query.filter(ReactivationOperator.id.in_(operator_ids))
            else:
                query = query.filter(OperatorReactivationRequest.request_code.in_(id_tokens))
    else:
        query = query.filter(ReactivationOperator.status_id == StatusEnum.SENT_TO_UIDAI.value)
        

    if user_role_str == "dc":
        query = query.filter(OperatorReactivationRequest.district_id == str(current_user.district_id))
        
    results = query.all()
    
    export_data = []
    for i, (o, req, dist_name) in enumerate(results):
        status_upper = (o.status or '').upper().strip()
        is_unreviewed = status_upper in ['PENDING', 'REAPPLIED']
        reviewed_time = "" if is_unreviewed else (req.updated_at.strftime("%Y-%m-%d %H:%M:%S") if req.updated_at else "—")
        
        display_status = "APPROVED" if status_upper in ["ACTIVE", "APPROVED"] else status_upper

        export_data.append({
            "s_no": i + 1,
            "request_code": req.request_code,
            "district_name": dist_name,
            "role": o.role,
            "operator_name": o.operator_name,
            "aadhaar_number": o.aadhaar_number,
            "registrar_code": o.registrar_code,
            "ea_code": o.ea_code,
            "user_code": o.user_code,
            "certificate_number": o.certificate_number,
            "lms_certificate_id": o.lms_certificate_id,
            "operator_mobile": o.operator_mobile,
            "email_id": o.email_id,
            "status": display_status,
            "submitted_at": req.created_at.strftime("%Y-%m-%d %H:%M:%S") if req.created_at else "—",
            "reviewed_at": reviewed_time
        })
        
    column_mappings = {
        "s_no": "S.No", 
        "request_code": "Batch Request ID", 
        "district_name": "District Name",
        "role": "Role Profile", 
        "operator_name": "Name As Per Aadhaar", 
        "aadhaar_number": "Aadhaar Number",
        "registrar_code": "Registrar Code",
        "ea_code": "EA Code", 
        "user_code": "User Code", 
        "certificate_number": "NSEIT Certificate Number",
        "lms_certificate_id": "LMS Certificate ID", 
        "operator_mobile": "Mobile Phone Number",
        "email_id": "Primary E-MAIL ID", 
        "status": "Current Audit Status", 
        "submitted_at": "Submission Date",
        "reviewed_at": "Reviewed Time"
    }
    return generate_csv_export(export_data, column_mappings, "UIDAI_Sent_Reactivation_Operators")

@router.get("/requests/{request_code}/files/{file_type}")
async def get_reactivation_file(request_code: str, file_type: str, db: Session = Depends(get_db)):
    req = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.request_code == request_code).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    doc = db.query(ReactivationDocument).filter(
        ReactivationDocument.request_id == req.id,

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

