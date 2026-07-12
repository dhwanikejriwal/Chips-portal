from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Candidate, NSEITRequest, NSEITRemark, UserLogin, MasterUserRole
from backend.models.base import StatusEnum, get_ist_now
from backend.utils.exporter import generate_csv_export

from backend.routers.auth import get_current_user

router = APIRouter(prefix="/nseit_manage", tags=["nseit_manage"], dependencies=[Depends(get_current_user)])

class NSEITActionRequest(BaseModel):
    remark: str 
    by_user_id: int

@router.get("/candidates")
def get_nseit_requests(district_code: str | None = None, db: Session = Depends(get_db)):
    query = db.query(NSEITRequest).join(Candidate, NSEITRequest.request_id == Candidate.id)
    if district_code and district_code != "all":
        query = query.filter(Candidate.district == district_code)
    nseit_requests = query.order_by(func.coalesce(NSEITRequest.updated_at, NSEITRequest.created_at).desc()).all()
    result = []
    for n in nseit_requests:
        c = n.candidate
        district_name = c.district_rel.district_name if c.district_rel else "Unknown"
        
        remarks = db.query(NSEITRemark).filter(NSEITRemark.request_id == n.id).order_by(NSEITRemark.time.asc()).all()
        remarks_history = []
        for r in remarks:
            sender_role = "Candidate"
            if r.admin_by_id:
                if r.admin_author and r.admin_author.role:
                    role_name = r.admin_author.role.role
                    if role_name == "Admin":
                        sender_role = "CHIPS"
                    elif role_name == "DC":
                        sender_role = "DC"
                    elif role_name == "EDM":
                        sender_role = "EDM"
                    else:
                        sender_role = "CHIPS"
                else:
                    sender_role = "CHIPS"
            
            remarks_history.append({
                "id": r.id,
                "remark": r.remark,
                "created_at": r.time.strftime("%Y-%m-%d %H:%M:%S"),
                "sender_role": sender_role,
                "sender_username": r.admin_author.username if r.admin_author else "Candidate",
                "status_after": r.status_after
            })
        
        result.append({
            "nseit_request_id": n.id,
            "r_id": c.id,
            "request_code": c.request_code,
            "name": c.name,
            "mobile": c.mobile,
            "email": c.email,
            "district_code": c.district,
            "district_name": district_name,
            "qualification": c.qualification,
            "dob": c.dob.strftime("%Y-%m-%d") if c.dob else "",
            "aadhaar": c.aadhaar or "",
            "address": c.address or "",
            "pincode": c.pincode or "",
            "is_existing_operator": c.is_existing_operator,
            "photo_upload": c.photo_upload or "",
            "marksheet_upload": c.marksheet_upload,
            "tenth_marksheet_upload": c.tenth_marksheet_upload or "",
            "lms_id": c.lms_id or "",
            "exam_unique_code": c.exam_unique_code or "",
            "nseit_status": n.status,
            "nseit_certificate_id": c.nseit_id or "",
            "remarks_history": remarks_history,
            "created_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else "",
            "updated_at": n.updated_at.strftime("%Y-%m-%d %H:%M:%S") if n.updated_at else (n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else "")
        })
    return result

@router.post("/forward/{r_id}")
def forward_nseit_request(r_id: int, payload: NSEITActionRequest, db: Session = Depends(get_db)):
    
    clean_remark = payload.remark.strip()
    if not clean_remark:
        raise HTTPException(status_code=400, detail="Forward remarks are mandatory.")
    
    nseit = db.query(NSEITRequest).filter(NSEITRequest.request_id == r_id).first()
    if not nseit:
        raise HTTPException(status_code=404, detail="NSEIT Request not found")
        
    # Check if this request has any remarks from CHiPS (Admin role) in its history
    from backend.models.candidate import CandidateLogin
    import sqlalchemy as sa
    has_chips_remark = db.query(NSEITRemark).join(
        NSEITRequest, NSEITRemark.request_id == NSEITRequest.id
    ).join(
        Candidate, NSEITRequest.request_id == Candidate.id
    ).join(
        CandidateLogin, Candidate.id == CandidateLogin.request_id
    ).join(
        UserLogin, NSEITRemark.sender_id == UserLogin.id
    ).join(
        MasterUserRole, UserLogin.roleid == MasterUserRole.id
    ).filter(
        NSEITRemark.request_id == nseit.id,
        MasterUserRole.role == "Admin",
        NSEITRemark.sender_id != CandidateLogin.id
    ).first() is not None

    if nseit.status_id == StatusEnum.REAPPLIED.value and has_chips_remark:
        nseit.status_id = StatusEnum.FORWARDED_AGAIN.value
    else:
        nseit.status_id = StatusEnum.FORWARDED.value
    nseit.updated_at = get_ist_now()
    
    chips_user = db.query(UserLogin).join(MasterUserRole).filter(MasterUserRole.role == "Admin").first()
    new_remark = NSEITRemark(
        request_id=nseit.id,
        remark=clean_remark or "NSEIT request verified and forwarded to CHiPS by District Coordinator.",
        sender_id=payload.by_user_id,
        receiver_id=chips_user.id if chips_user else None,
        is_public=1,
        status_after_id=nseit.status_id
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "NSEIT Request forwarded to CHiPS successfully."}

@router.post("/approve/{r_id}")
def approve_nseit_request(r_id: int, payload: NSEITActionRequest, db: Session = Depends(get_db)):
    nseit = db.query(NSEITRequest).filter(NSEITRequest.request_id == r_id).first()
    if not nseit:
        raise HTTPException(status_code=404, detail="NSEIT Request not found")
        
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    nseit.status_id = StatusEnum.APPROVED.value
    nseit.updated_at = get_ist_now()
    candidate_login_id = None
    if candidate.login:
        candidate_login_id = candidate.login.id

    new_remark = NSEITRemark(
        request_id=nseit.id,
        remark=payload.remark or "NSEIT request verified and approved.",
        sender_id=payload.by_user_id,
        receiver_id=candidate_login_id,
        is_public=1,
        status_after_id=nseit.status_id
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "NSEIT Request successfully approved."}

@router.post("/revert/{r_id}")
def revert_nseit_request(r_id: int, payload: NSEITActionRequest, db: Session = Depends(get_db)):
    nseit = db.query(NSEITRequest).filter(NSEITRequest.request_id == r_id).first()
    if not nseit:
        raise HTTPException(status_code=404, detail="NSEIT Request not found")
        
    # Check if the reverting user has Admin (CHiPS) role
    user = db.query(UserLogin).filter(UserLogin.id == payload.by_user_id).first()
    if user and user.role and user.role.role == "Admin":
        nseit.status_id = StatusEnum.REVERTED_BY_CHIPS.value
    else:
        nseit.status_id = StatusEnum.REVERTED.value
    nseit.updated_at = get_ist_now()
    
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    candidate_login_id = None
    if candidate and candidate.login:
        candidate_login_id = candidate.login.id

    new_remark = NSEITRemark(
        request_id=nseit.id,
        remark=payload.remark or "NSEIT request reverted.",
        sender_id=payload.by_user_id,
        receiver_id=candidate_login_id,
        is_public=1,
        status_after_id=nseit.status_id
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "NSEIT Request reverted."}

@router.get("/export-excel")
def export_nseit_excel(ids: str = None, table_id: str = None, db: Session = Depends(get_db)):
    """
    🌟 FIXED: Fetches comprehensive profile field values directly from the database context
    and streams them as a fully itemized, un-truncated CSV report.
    """
    # Join Candidate to pull all related columns
    query = db.query(NSEITRequest).join(Candidate, NSEITRequest.request_id == Candidate.id)
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.isdigit()]
        query = query.filter(NSEITRequest.request_id.in_(id_list))
        
    nseit_records = query.order_by(Candidate.request_code.asc()).all()

    export_data = []
    for idx, n in enumerate(nseit_records):
        c = n.candidate
        if not c:
            continue
            
        district_name = c.district_rel.district_name if c.district_rel else "Unknown"
        
        status_upper = n.status.upper() if n.status else ""
        if status_upper in ["APPROVED", "APPROVED_LEGACY"]:
            is_pending = False
            nseit_status_str = "Approved"
        elif status_upper == "REVERTED_BY_CHIPS":
            is_pending = False
            nseit_status_str = "Reverted by CHiPS"
        elif status_upper == "REVERTED":
            is_pending = False
            nseit_status_str = "Reverted"
        elif status_upper == "SKIPPED":
            is_pending = False
            nseit_status_str = "Skipped"
        elif status_upper in ["FORWARDED", "PENDING"]:
            if table_id == "admin-chips-table":
                is_pending = False
                nseit_status_str = "Forwarded"
            else:
                is_pending = True
                nseit_status_str = "Pending"
        else:
            is_pending = False
            if table_id == "admin-chips-table":
                nseit_status_str = "Forwarded Again"
            else:
                nseit_status_str = "Reapplied"

        export_data.append({
            "s_no": idx + 1,
            "request_code": c.request_code,
            "district_name": district_name,
            "name": c.name,
            "mobile": c.mobile,
            "email": c.email,
            "dob": c.dob.strftime("%Y-%m-%d") if c.dob else "",
            "aadhaar": f"{c.aadhaar}" if c.aadhaar else "",  # Added apostrophe to keep Excel from altering string truncation bounds
            "qualification": c.qualification,
            "address": c.address or "",
            "pincode": c.pincode or "",
            "is_existing_operator": "Yes" if c.is_existing_operator else "No",
            "lms_id": c.lms_id or "None",
            "exam_unique_code": c.exam_unique_code or "None",
            "nseit_certificate_id": c.nseit_id or "None",
            "nseit_status": nseit_status_str,
            "submitted_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else "",
            "updated_at": (n.updated_at.strftime("%Y-%m-%d %H:%M:%S") if n.updated_at else "") if not is_pending else ""
        })

    # 🌟 Full column profile headers layout dictionary map
    column_mappings = {
        "s_no": "S.No",

        "request_code": "Request Code",
        "district_name": "District Name",
   
        "name": "Candidate Name",
        "mobile": "Mobile Number",
        "email": "Email ID",
        "dob": "Date of Birth",
        "aadhaar": "Aadhaar Card Number",
        "qualification": "Educational Qualification",
        "address": "Full Permanent Address",
        "pincode": "Postal Pincode",
        "is_existing_operator": "Existing Aadhaar Operator Status",
        "lms_id": "LMS ID",
        "exam_unique_code": "Exam Unique Code",
        "nseit_certificate_id": "NSEIT Certificate ID",
        "nseit_status": "Current Status",
   
        "submitted_at": "Submitted at",
        "updated_at": "Updated at"
    }

    # Pass directly into your central exporter utility for streaming output
    return generate_csv_export(export_data, column_mappings, "nseit_complete_report")
