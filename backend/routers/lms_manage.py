from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Candidate, LMS, LMSRemark, UserLogin, MasterUserRole
from backend.models.base import StatusEnum, get_ist_now
from backend.utils.exporter import generate_csv_export

from backend.routers.auth import get_current_user

router = APIRouter(prefix="/lms_manage", tags=["lms_manage"], dependencies=[Depends(get_current_user)])

class LMSActionRequest(BaseModel):
    remark: str 
    by_user_id: int
    force_without_email: bool = False

@router.get("/candidates")
def get_lms_requests(district_code: str | None = None, db: Session = Depends(get_db)):
    query = db.query(LMS).join(Candidate, LMS.request_id == Candidate.id)
    if district_code and district_code != "all":
        query = query.filter(Candidate.district == district_code)
    lms_requests = query.order_by(func.coalesce(LMS.updated_at, LMS.created_at).desc()).all()
    result = []
    for l in lms_requests:
        c = l.candidate
        district_name = c.district_rel.district_name if c.district_rel else "Unknown"
        
        remarks = db.query(LMSRemark).filter(LMSRemark.request_id == l.id).order_by(LMSRemark.time.asc()).all()
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
            "lms_id": l.id,
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
            "nseit_id": c.nseit_id or "",
            "lms_status": l.status,
            "lms_credential_id": c.lms_id or "",
            "remarks_history": remarks_history,
            "created_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else "",
            "updated_at": l.updated_at.strftime("%Y-%m-%d %H:%M:%S") if l.updated_at else (l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else "")
        })
    return result

@router.post("/forward/{r_id}")
def forward_lms_request(r_id: int, payload: LMSActionRequest, db: Session = Depends(get_db)):
    
    clean_remark = payload.remark.strip()
    if not clean_remark:
        raise HTTPException(status_code=400, detail="Forward remarks are mandatory.")
    lms = db.query(LMS).filter(LMS.request_id == r_id).first()
    if not lms:
        raise HTTPException(status_code=404, detail="LMS Request not found")
        
    # Check if this request has any remarks from CHiPS (Admin role) in its history
    from backend.models.candidate import CandidateLogin
    import sqlalchemy as sa
    has_chips_remark = db.query(LMSRemark).join(
        LMS, LMSRemark.request_id == LMS.id
    ).join(
        Candidate, LMS.request_id == Candidate.id
    ).join(
        CandidateLogin, Candidate.id == CandidateLogin.request_id
    ).join(
        UserLogin, LMSRemark.sender_id == UserLogin.id
    ).join(
        MasterUserRole, UserLogin.roleid == MasterUserRole.id
    ).filter(
        LMSRemark.request_id == lms.id,
        MasterUserRole.role == "Admin",
        LMSRemark.sender_id != CandidateLogin.id
    ).first() is not None

    if lms.status_id == StatusEnum.REAPPLIED.value and has_chips_remark:
        lms.status_id = StatusEnum.FORWARDED_AGAIN.value
    else:
        lms.status_id = StatusEnum.FORWARDED.value
    lms.updated_at = get_ist_now()
    
    chips_user = db.query(UserLogin).join(MasterUserRole).filter(MasterUserRole.role == "Admin").first()
    new_remark = LMSRemark(
        request_id=lms.id,
        remark=clean_remark or "LMS request verified and forwarded to CHiPS by District Coordinator.",
        sender_id=payload.by_user_id,
        receiver_id=chips_user.id if chips_user else None,
        is_public=1,
        status_after_id=lms.status_id
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "LMS Request forwarded to CHiPS successfully."}

@router.post("/approve/{r_id}")
def approve_lms_request(r_id: int, payload: LMSActionRequest, db: Session = Depends(get_db)):
    lms = db.query(LMS).filter(LMS.request_id == r_id).first()
    if not lms:
        raise HTTPException(status_code=404, detail="LMS Request not found")
        
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    lms.status_id = StatusEnum.APPROVED.value
    lms.updated_at = get_ist_now()
    
    candidate_login_id = None
    if lms.candidate and lms.candidate.login:
        candidate_login_id = lms.candidate.login.id

    new_remark = LMSRemark(
        request_id=lms.id,
        remark=payload.remark or "LMS request verified and approved.",
        sender_id=payload.by_user_id,
        receiver_id=candidate_login_id,
        is_public=1,
        status_after_id=lms.status_id
    )
    db.add(new_remark)
    
    # Try sending email synchronously before committing
    if candidate.email:
        try:
            import asyncio
            from backend.utils.email_utils import send_lms_approval_email
            
            lms_username = candidate.email or ""
            lms_password = "Test@123"
            lms_link = "https://lms.gov.in"
            
            asyncio.run(send_lms_approval_email(
                email_to=candidate.email,
                name=candidate.name,
                username=lms_username,
                raw_password=lms_password,
                lms_link=lms_link
            ))
        except Exception as e:
            if not payload.force_without_email:
                db.rollback()
                return {"success": False, "email_failed": True, "detail": f"Failed to send email: {str(e)}"}
                
    db.commit()
    return {"success": True, "detail": "LMS Request successfully approved."}

@router.post("/revert/{r_id}")
def revert_lms_request(r_id: int, payload: LMSActionRequest, db: Session = Depends(get_db)):
    lms = db.query(LMS).filter(LMS.request_id == r_id).first()
    if not lms:
        raise HTTPException(status_code=404, detail="LMS Request not found")
        
    # Check if the reverting user has Admin (CHiPS) role
    user = db.query(UserLogin).filter(UserLogin.id == payload.by_user_id).first()
    if user and user.role and user.role.role == "Admin":
        lms.status_id = StatusEnum.REVERTED_BY_CHIPS.value
    else:
        lms.status_id = StatusEnum.REVERTED.value
    lms.updated_at = get_ist_now()
    
    candidate_login_id = None
    if lms.candidate and lms.candidate.login:
        candidate_login_id = lms.candidate.login.id

    new_remark = LMSRemark(
        request_id=lms.id,
        remark=payload.remark or "LMS request reverted.",
        sender_id=payload.by_user_id,
        receiver_id=candidate_login_id,
        is_public=1,
        status_after_id=lms.status_id
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "LMS Request reverted."}

@router.get("/export-excel")
def export_lms_excel(ids: str = None, table_id: str = None, db: Session = Depends(get_db)):
    """
    🌟 FIXED: Exports all background information corresponding to the requested tracking entries
    using a centralized matrix map container forwarded to our universal CSV stream pipeline.
    """
    # Join Candidate table to guarantee retrieval of all profile attributes
    query = db.query(LMS).join(Candidate, LMS.request_id == Candidate.id)
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.isdigit()]
        # Filter matching database records against the target table IDs
        query = query.filter(LMS.request_id.in_(id_list))
        
    lms_records = query.order_by(Candidate.request_code.asc()).all()

    export_data = []
    for idx, l in enumerate(lms_records):
        c = l.candidate
        if not c:
            continue
            
        district_name = c.district_rel.district_name if c.district_rel else "Unknown"
        
        status_upper = l.status.upper() if l.status else ""
        if status_upper in ["APPROVED", "APPROVED_LEGACY"]:
            is_pending = False
            lms_status_str = "Approved"
        elif status_upper == "REVERTED_BY_CHIPS":
            is_pending = False
            lms_status_str = "Reverted by CHiPS"
        elif status_upper == "REVERTED":
            is_pending = False
            lms_status_str = "Reverted"
        elif status_upper == "SKIPPED":
            is_pending = False
            lms_status_str = "Skipped"
        elif status_upper in ["FORWARDED", "PENDING"]:
            if table_id == "admin-chips-table":
                is_pending = False
                lms_status_str = "Forwarded"
            else:
                is_pending = True
                lms_status_str = "Pending"
        else:
            is_pending = False
            if table_id == "admin-chips-table":
                lms_status_str = "Forwarded Again"
            else:
                lms_status_str = "Reapplied"

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
            "nseit_id": c.nseit_id or "None",
            "lms_credential_id": c.lms_id or "None",
            "lms_status": lms_status_str,
            "submitted_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else "",
            "updated_at": (l.updated_at.strftime("%Y-%m-%d %H:%M:%S") if l.updated_at else "") if not is_pending else ""
        })

    # 🌟 Centralized structural column headers dictionary
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
        "nseit_id": "NSEIT Certificate ID",
        "lms_credential_id": "LMS ID",
        "lms_status": "Current Status",
        "submitted_at": "Submitted at",
        "updated_at": "Updated at"
    }

    # Forward directly to your centralized exporter utility for a streaming CSV download
    return generate_csv_export(export_data, column_mappings, "lms_complete_report")
