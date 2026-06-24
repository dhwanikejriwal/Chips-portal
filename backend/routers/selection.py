import bcrypt
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, String, Integer, Date, ForeignKey, DateTime
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Candidate, CandidateLogin, DCRemark
from backend.utils.exporter import generate_excel_export

router = APIRouter(prefix="/selection", tags=["selection"])

class CandidateApproveRequest(BaseModel):
    username: str | None = None
    password: str | None = None
    remark: str | None = None
    by_user_id: int

class CandidateRejectRequest(BaseModel):
    remark: str
    by_user_id: int

@router.get("/candidates")
def get_dc_candidates(district_code: str | None = None, db: Session = Depends(get_db)):
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
            "generated_login_id": login_id,
            "generated_password_raw": password_raw,
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
        "generated_login_id": "Generated Login ID",
        "generated_password_raw": "Generated Password",
        "submitted_at": "Submitted At",
        "updated_at": "Updated At",
    }

    return generate_excel_export(export_data, column_mappings, "candidate_requests")

@router.post("/approve-candidate/{r_id}")
def approve_candidate(r_id: int, payload: CandidateApproveRequest, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.r_id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    existing_login = db.query(CandidateLogin).filter(CandidateLogin.r_id == r_id).first()
    if existing_login:
        raise HTTPException(status_code=400, detail="Credentials already assigned to this candidate")
        
    # Auto-generate credentials if not provided
    username = payload.username.strip() if (payload.username and payload.username.strip()) else candidate.email
    password = payload.password.strip() if (payload.password and payload.password.strip()) else "Test@123"

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
    new_remark = DCRemark(
        r_id=r_id,
        remark=remark_text,
        by=payload.by_user_id,
        status_after="Approved"
    )
    db.add(new_remark)
    
    db.commit()
    return {"success": True, "detail": "Candidate successfully approved."}

@router.post("/reject-candidate/{r_id}")
def reject_candidate(r_id: int, payload: CandidateRejectRequest, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.r_id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    candidate.status = "Rejected"
    
    new_remark = DCRemark(
        r_id=r_id,
        remark=payload.remark,
        by=payload.by_user_id,
        status_after="Rejected"
    )
    db.add(new_remark)
    
    db.commit()
    return {"success": True, "detail": "Candidate onboarding request rejected."}
