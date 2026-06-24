from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Candidate, NSEITRequest, NSEITRemark, UserLogin, MasterUserRole
from backend.utils.exporter import generate_excel_export

router = APIRouter(prefix="/nseit_manage", tags=["nseit_manage"])

class NSEITActionRequest(BaseModel):
    remark: str 
    by_user_id: int

@router.get("/candidates")
def get_nseit_requests(district_code: str | None = None, db: Session = Depends(get_db)):
    query = db.query(NSEITRequest).join(Candidate, NSEITRequest.r_id == Candidate.r_id)
    if district_code and district_code != "all":
        query = query.filter(Candidate.district == district_code)
    nseit_requests = query.order_by(func.coalesce(NSEITRequest.updated_at, NSEITRequest.created_at).desc()).all()
    
    # Exclude skipped NSEIT requests
    skipped_nseit_ids = {r.nseit_id for r in db.query(NSEITRemark.nseit_id).filter(NSEITRemark.remark.like("%skipped%")).all()}
    
    result = []
    for n in nseit_requests:
        if n.id in skipped_nseit_ids:
            continue
        c = n.candidate
        district_name = c.district_rel.district_name if c.district_rel else "Unknown"
        
        remarks = db.query(NSEITRemark).filter(NSEITRemark.nseit_id == n.id).order_by(NSEITRemark.time.asc()).all()
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
    
    nseit = db.query(NSEITRequest).filter(NSEITRequest.r_id == r_id).first()
    if not nseit:
        raise HTTPException(status_code=404, detail="NSEIT Request not found")
        
    # Check if this request has any remarks from CHiPS (Admin role) in its history
    has_chips_remark = db.query(NSEITRemark).join(
        UserLogin, NSEITRemark.admin_by_id == UserLogin.id
    ).join(
        MasterUserRole, UserLogin.roleid == MasterUserRole.id
    ).filter(
        NSEITRemark.nseit_id == nseit.id,
        MasterUserRole.role == "Admin"
    ).first() is not None

    if nseit.status == "Reapplied" and has_chips_remark:
        nseit.status = "Forwarded Again"
    else:
        nseit.status = "Forwarded"
    
    new_remark = NSEITRemark(
        nseit_id=nseit.id,
        remark=clean_remark or "NSEIT request verified and forwarded to CHiPS by District Coordinator.",
        admin_by_id=payload.by_user_id,
        status_after=nseit.status
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "NSEIT Request forwarded to CHiPS successfully."}

@router.post("/approve/{r_id}")
def approve_nseit_request(r_id: int, payload: NSEITActionRequest, db: Session = Depends(get_db)):
    nseit = db.query(NSEITRequest).filter(NSEITRequest.r_id == r_id).first()
    if not nseit:
        raise HTTPException(status_code=404, detail="NSEIT Request not found")
        
    candidate = db.query(Candidate).filter(Candidate.r_id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    nseit.status = "Approved"
    
    # Auto-generate NSEIT certificate ID if not already present
    if not candidate.nseit_id:
        candidate.nseit_id = f"NSEIT{r_id:05d}"
    
    new_remark = NSEITRemark(
        nseit_id=nseit.id,
        remark=payload.remark or "NSEIT request verified and approved.",
        admin_by_id=payload.by_user_id,
        status_after=nseit.status
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "NSEIT Request successfully approved."}

@router.post("/revert/{r_id}")
def revert_nseit_request(r_id: int, payload: NSEITActionRequest, db: Session = Depends(get_db)):
    nseit = db.query(NSEITRequest).filter(NSEITRequest.r_id == r_id).first()
    if not nseit:
        raise HTTPException(status_code=404, detail="NSEIT Request not found")
        
    # Check if the reverting user has Admin (CHiPS) role
    user = db.query(UserLogin).filter(UserLogin.id == payload.by_user_id).first()
    if user and user.role and user.role.role == "Admin":
        nseit.status = "Reverted by CHiPS"
    else:
        nseit.status = "Reverted"
    
    new_remark = NSEITRemark(
        nseit_id=nseit.id,
        remark=payload.remark or "NSEIT request reverted.",
        admin_by_id=payload.by_user_id,
        status_after=nseit.status
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "NSEIT Request reverted."}

@router.get("/export-excel")
def export_nseit_excel(ids: str = None, db: Session = Depends(get_db)):
    query = db.query(NSEITRequest)
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.isdigit()]
        query = query.filter(NSEITRequest.r_id.in_(id_list))
    nseit_records = query.all()

    export_data = []
    for idx, n in enumerate(nseit_records):
        c = n.candidate
        if not c:
            continue
        district_name = c.district_rel.district_name if c.district_rel else "Unknown"
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
            "exam_unique_code": c.exam_unique_code or "",
            "nseit_certificate_id": c.nseit_id or "",
            "nseit_status": n.status,
            "submitted_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else "",
            "updated_at": n.updated_at.strftime("%Y-%m-%d %H:%M:%S") if n.updated_at else (n.created_at.strftime("%Y-%m-%d %H:%M:%S") if n.created_at else ""),
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
        "exam_unique_code": "Exam Unique Code",
        "nseit_certificate_id": "NSEIT Certificate ID",
        "nseit_status": "NSEIT Status",
        "submitted_at": "Submitted At",
        "updated_at": "Updated At",
    }

    return generate_excel_export(export_data, column_mappings, "nseit_requests")
