from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Candidate, LMS, LMSRemark, UserLogin, MasterUserRole
from backend.utils.exporter import generate_csv_export

router = APIRouter(prefix="/lms_manage", tags=["lms_manage"])

class LMSActionRequest(BaseModel):
    remark: str 
    by_user_id: int

@router.get("/candidates")
def get_lms_requests(district_code: str | None = None, db: Session = Depends(get_db)):
    query = db.query(LMS).join(Candidate, LMS.r_id == Candidate.r_id)
    if district_code and district_code != "all":
        query = query.filter(Candidate.district == district_code)
    lms_requests = query.order_by(func.coalesce(LMS.updated_at, LMS.created_at).desc()).all()
    
    # Exclude skipped LMS requests
    skipped_lms_ids = {r.lms_id for r in db.query(LMSRemark.lms_id).filter(LMSRemark.remark.like("%skipped%")).all()}
    
    result = []
    for l in lms_requests:
        if l.id in skipped_lms_ids:
            continue
        c = l.candidate
        district_name = c.district_rel.district_name if c.district_rel else "Unknown"
        
        remarks = db.query(LMSRemark).filter(LMSRemark.lms_id == l.id).order_by(LMSRemark.time.asc()).all()
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
            "r_id": c.r_id,
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
    lms = db.query(LMS).filter(LMS.r_id == r_id).first()
    if not lms:
        raise HTTPException(status_code=404, detail="LMS Request not found")
        
    # Check if this request has any remarks from CHiPS (Admin role) in its history
    has_chips_remark = db.query(LMSRemark).join(
        UserLogin, LMSRemark.admin_by_id == UserLogin.id
    ).join(
        MasterUserRole, UserLogin.roleid == MasterUserRole.id
    ).filter(
        LMSRemark.lms_id == lms.id,
        MasterUserRole.role == "Admin"
    ).first() is not None

    if lms.status == "Reapplied" and has_chips_remark:
        lms.status = "Forwarded Again"
    else:
        lms.status = "Forwarded"
    
    new_remark = LMSRemark(
        lms_id=lms.id,
        remark=clean_remark or "LMS request verified and forwarded to CHiPS by District Coordinator.",
        admin_by_id=payload.by_user_id,
        status_after=lms.status
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "LMS Request forwarded to CHiPS successfully."}

@router.post("/approve/{r_id}")
def approve_lms_request(r_id: int, payload: LMSActionRequest, db: Session = Depends(get_db)):
    lms = db.query(LMS).filter(LMS.r_id == r_id).first()
    if not lms:
        raise HTTPException(status_code=404, detail="LMS Request not found")
        
    candidate = db.query(Candidate).filter(Candidate.r_id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    lms.status = "Approved"
    
    new_remark = LMSRemark(
        lms_id=lms.id,
        remark=payload.remark or "LMS request verified and approved.",
        admin_by_id=payload.by_user_id,
        status_after=lms.status
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "LMS Request successfully approved."}

@router.post("/revert/{r_id}")
def revert_lms_request(r_id: int, payload: LMSActionRequest, db: Session = Depends(get_db)):
    lms = db.query(LMS).filter(LMS.r_id == r_id).first()
    if not lms:
        raise HTTPException(status_code=404, detail="LMS Request not found")
        
    # Check if the reverting user has Admin (CHiPS) role
    user = db.query(UserLogin).filter(UserLogin.id == payload.by_user_id).first()
    if user and user.role and user.role.role == "Admin":
        lms.status = "Reverted by CHiPS"
    else:
        lms.status = "Reverted"
    
    new_remark = LMSRemark(
        lms_id=lms.id,
        remark=payload.remark or "LMS request reverted.",
        admin_by_id=payload.by_user_id,
        status_after=lms.status
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "LMS Request reverted."}

@router.get("/export-excel")
def export_lms_excel(ids: str = None, db: Session = Depends(get_db)):
    """
    🌟 FIXED: Exports all background information corresponding to the requested tracking entries
    using a centralized matrix map container forwarded to our universal CSV stream pipeline.
    """
    # Join Candidate table to guarantee retrieval of all profile attributes
    query = db.query(LMS).join(Candidate, LMS.r_id == Candidate.r_id)
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.isdigit()]
        # Filter matching database records against the target table IDs
        query = query.filter(LMS.id.in_(id_list))
        
    lms_records = query.order_by(Candidate.request_code.asc()).all()

    export_data = []
    for idx, l in enumerate(lms_records):
        c = l.candidate
        if not c:
            continue
            
        district_name = c.district_rel.district_name if c.district_rel else "Unknown"
        
        # 🌟 Map EVERY background metadata parameter to download all info safely
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
            "lms_status": l.status,
            "submitted_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S") if l.created_at else "N/A",
            "updated_at": l.updated_at.strftime("%Y-%m-%d %H:%M:%S") if l.updated_at else "N/A"
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
        "lms_credential_id": "Assigned LMS ID",
        "lms_status": "Current Verification Lifecycle Status",
        "submitted_at": "Request Creation Timestamp",
        "updated_at": "Last Audit Status Update Timestamp"
    }

    # Forward directly to your centralized exporter utility for a streaming CSV download
    return generate_csv_export(export_data, column_mappings, "lms_complete_report")