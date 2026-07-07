import bcrypt
import secrets
import string
from datetime import datetime, timedelta
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import func, String, Integer, Date, ForeignKey, DateTime
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Candidate, CandidateLogin, DCRemark
from backend.utils.exporter import generate_csv_export
from backend.utils.email_utils import send_approval_email, send_rejection_email

from backend.routers.auth import get_current_user

router = APIRouter(prefix="/selection", tags=["selection"], dependencies=[Depends(get_current_user)])

class CandidateApproveRequest(BaseModel):
    username: str | None = None
    password: str | None = None
    remark: str | None = None
    by_user_id: int
    force_without_email: bool = False

class CandidateRejectRequest(BaseModel):
    remark: str
    by_user_id: int
    force_without_email: bool = False

@router.get("/candidates")
def get_dc_candidates(district_code: str | None = None, db: Session = Depends(get_db)):
    try:
        query = db.query(Candidate)
        if district_code and district_code != "all":
            query = query.filter(Candidate.district == district_code)
        candidates = query.order_by(func.coalesce(Candidate.updated_at, Candidate.created_at).desc()).all()
        
        result = []
        for c in candidates:
            district_name = c.district_rel.district_name if c.district_rel else "Unknown"
            remarks = db.query(DCRemark).filter(DCRemark.r_id == c.r_id).order_by(DCRemark.time.asc()).all()

            remarks_history = [
                {
                    "id": r.id,
                    "remark": r.remark,
                    "created_at": r.time.strftime("%Y-%m-%d %H:%M:%S"),
                    "sender_role": r.author.role.role if r.author and r.author.role else "Admin",
                    "sender_username": r.author.username if r.author else "System"
                } for r in remarks
            ]
            
            login_id = ""
            password_raw = ""
            if c.status == "Approved" and c.login:
                login_id = c.login.user_id
                password_raw = "Test@123"
                
            result.append({
                "r_id": c.r_id,
                "request_code": c.request_code,
                "name": c.name,
                "mobile": c.mobile,
                "email": c.email,
                "district_code": c.district,
                "district_name": district_name,
                "qualification": c.qualification,
                "lms_id": c.lms_id or "",
                "nseit_id": c.nseit_id or "",
                "exam_unique_code": c.exam_unique_code or "",
                "dob": c.dob.strftime("%Y-%m-%d") if c.dob else "",
                "aadhaar": c.aadhaar,
                "address": c.address or "",
                "pincode": c.pincode or "",
                "is_existing_operator": c.is_existing_operator,
                "photo_upload": c.photo_upload or "",
                "marksheet_upload": c.marksheet_upload,
                "tenth_marksheet_upload": c.tenth_marksheet_upload or "",
                "status": c.status,
                "generated_login_id": login_id,
                "generated_password_raw": password_raw,
                "remarks_history": remarks_history,
                "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "",
                "updated_at": c.updated_at.strftime("%Y-%m-%d %H:%M:%S") if c.updated_at else (c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "")
            })
        return result
    except Exception as e:
        import traceback
        with open("api_error.log", "w") as f:
            f.write(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export-excel")
def export_candidates_excel(ids: str = None, db: Session = Depends(get_db)):
    query = db.query(Candidate)
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.isdigit()]
        query = query.filter(Candidate.r_id.in_(id_list))
    candidates = query.all()

    export_data = []
    for idx, c in enumerate(candidates):
        district_name = c.district_rel.district_name if c.district_rel else "Unknown"

        login_id = ""
        password_raw = ""
        if c.status == "Approved" and c.login:
            login_id = c.login.user_id
            password_raw = "Test@123"

        # Fetch the latest remark from DC for this candidate
        latest_remark = (
            db.query(DCRemark)
            .filter(DCRemark.r_id == c.r_id)
            .order_by(DCRemark.time.desc())
            .first()
        )
        dc_remark = latest_remark.remark if latest_remark else ""

        export_data.append({
            "s_no": idx + 1,
            "request_code": c.request_code,
            "district_name": district_name,
            "name": c.name,
            "mobile": c.mobile,
            "email": c.email,
            "qualification": c.qualification,
            "dob": c.dob.strftime("%Y-%m-%d") if c.dob else "",
            "aadhaar": c.aadhaar or "",
            "address": c.address or "",
            "pincode": c.pincode or "",
            "is_existing_operator": "Yes" if c.is_existing_operator else "No",
            "lms_id": c.lms_id or "",
            "nseit_id": c.nseit_id or "",
            "status": c.status,
            "dc_remark": dc_remark,
            "submitted_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "",
            "updated_at": (c.updated_at or c.created_at).strftime("%Y-%m-%d %H:%M:%S") if (c.updated_at or c.created_at) else "",
        })

    column_mappings = {
        "s_no": "S.No",
        "request_code": "Request Code",
        "district_name": "District",
        "name": "Candidate Name",
        "mobile": "Mobile No",
        "email": "Email ID",
        "qualification": "Qualification",
        "dob": "Date of Birth",
        "aadhaar": "Aadhaar Number",
        "address": "Address",
        "pincode": "Pincode",
        "is_existing_operator": "Is Existing Operator",
        "lms_id": "LMS ID",
        "nseit_id": "NSEIT ID",
        "status": "Status",
        "dc_remark": "DC Remark (Approve/Reject Reason)",
        "submitted_at": "Submitted At",
        "updated_at": "Updated At",
    }

    return generate_csv_export(export_data, column_mappings, "candidate_requests")

@router.post("/approve-candidate/{r_id}")
def approve_candidate(r_id: int, payload: CandidateApproveRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.r_id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    existing_login = db.query(CandidateLogin).filter(CandidateLogin.r_id == r_id).first()
    if existing_login:
        raise HTTPException(status_code=400, detail="Credentials already assigned to this candidate")
        
    # Auto-generate credentials if not provided
    username = candidate.email
    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))

    existing_user = db.query(CandidateLogin).filter(CandidateLogin.user_id == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail=f"Email ID {username} is already registered to another account.")

    salt = bcrypt.gensalt()
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    new_login = CandidateLogin(
        r_id=r_id,
        user_id=username,
        password=hashed_pw
    )
    db.add(new_login)
    
    candidate.status = "Approved"
    
    remark_text = payload.remark or "Application reviewed and approved."
    if payload.force_without_email:
        remark_text = f"[Email Failed] {remark_text}"

    new_remark = DCRemark(
        r_id=r_id,
        remark=remark_text,
        by=payload.by_user_id,
        status_after="Approved"
    )
    db.add(new_remark)
    
    # Try sending email synchronously before committing
    if candidate.email:
        try:
            asyncio.run(send_approval_email(
                email_to=candidate.email,
                name=candidate.name,
                username=username,
                raw_password=password
            ))
        except Exception as e:
            if not payload.force_without_email:
                db.rollback()
                return {"success": False, "email_failed": True, "detail": f"Failed to send email: {str(e)}"}
            # If forced, we ignore the error and proceed (the remark is already flagged)

    db.commit()
    
    return {"success": True, "detail": "Candidate successfully approved."}

@router.post("/reject-candidate/{r_id}")
def reject_candidate(r_id: int, payload: CandidateRejectRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.r_id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    candidate.status = "Rejected"
    
    remark_text = payload.remark
    if payload.force_without_email:
        remark_text = f"[Email Failed] {remark_text}"

    new_remark = DCRemark(
        r_id=r_id,
        remark=remark_text,
        by=payload.by_user_id,
        status_after="Rejected"
    )
    db.add(new_remark)
    
    if candidate.email:
        try:
            asyncio.run(send_rejection_email(
                email_to=candidate.email,
                name=candidate.name,
                reason=payload.remark
            ))
        except Exception as e:
            if not payload.force_without_email:
                db.rollback()
                return {"success": False, "email_failed": True, "detail": f"Failed to send email: {str(e)}"}
    
    db.commit()
    
    return {"success": True, "detail": "Candidate onboarding request rejected."}
