from fastapi import APIRouter, Depends, HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session, joinedload
from backend.database import get_db
from backend.models import Candidate, LMS, LMSRemark, NSEITRequest, NSEITRemark, District, UserLogin, MasterUserRole
from backend.models.base import StatusEnum
from backend.utils.exporter import generate_csv_export
router = APIRouter(prefix="/candidate", tags=["candidate"])

@router.get("/status/{r_id}")
def get_candidate_status(r_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    lms = db.query(LMS).filter(LMS.request_id == r_id).first()
    nseit = db.query(NSEITRequest).filter(NSEITRequest.request_id == r_id).first()
    
    lms_status = lms.status if lms else "Not Initiated"
    nseit_status = nseit.status if nseit else "Not Initiated"
    
    # Remarks logic
    lms_remarks = []
    if lms:
        remarks = db.query(LMSRemark).filter(LMSRemark.request_id == lms.id).order_by(LMSRemark.time.asc()).all()
        for r in remarks:
            sender_role = "Candidate"
            if r.admin_by_id:
                if r.admin_author and r.admin_author.role:
                    role_name = r.admin_author.role.role
                    sender_role = "CHIPS" if role_name == "Admin" else role_name
                else:
                    sender_role = "CHIPS"
            lms_remarks.append({
                "remark": r.remark,
                "created_at": r.time.strftime("%Y-%m-%d %H:%M:%S"),
                "sender_role": sender_role,
                "status_after": r.status_after
            })
        
    nseit_remarks = []
    if nseit:
        remarks = db.query(NSEITRemark).filter(NSEITRemark.request_id == nseit.id).order_by(NSEITRemark.time.asc()).all()
        for r in remarks:
            sender_role = "Candidate"
            if r.admin_by_id:
                if r.admin_author and r.admin_author.role:
                    role_name = r.admin_author.role.role
                    sender_role = "CHIPS" if role_name == "Admin" else role_name
                else:
                    sender_role = "CHIPS"
            nseit_remarks.append({
                "remark": r.remark,
                "created_at": r.time.strftime("%Y-%m-%d %H:%M:%S"),
                "sender_role": sender_role,
                "status_after": r.status_after
            })

    return {
        "id": candidate.id,
        "name": candidate.name,
        "email": candidate.email,
        "mobile": candidate.mobile,
        "qualification": candidate.qualification,
        "dob": candidate.dob.strftime("%Y-%m-%d") if candidate.dob else "",
        "aadhaar": candidate.aadhaar,
        "address": candidate.address or "",
        "pincode": candidate.pincode or "",
        "district": candidate.district,
        "district_name": candidate.district_rel.district_name if candidate.district_rel else "",
        "is_existing_operator": candidate.is_existing_operator,
        "photo_upload": candidate.photo_upload or "",
        "tenth_marksheet_upload": candidate.tenth_marksheet_upload or "",
        "marksheet_upload": candidate.marksheet_upload or "",
        "status": candidate.status,
        "lms_status": lms_status,
        "nseit_status": nseit_status,
        "lms_id": candidate.lms_id,
        "nseit_id": candidate.nseit_id,
        "exam_unique_code": candidate.exam_unique_code,
        "lms_remarks": lms_remarks,
        "nseit_remarks": nseit_remarks
    }

@router.post("/submit-lms/{r_id}")
def submit_lms_request(r_id: int, remark: str | None = None, login_id: int | None = None,
                       name: str | None = None, exam_unique_code: str | None = None,
                       db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    # Update candidate fields if provided
    if name:
        candidate.name = name
    if exam_unique_code:
        candidate.exam_unique_code = exam_unique_code
        
    lms = db.query(LMS).filter(LMS.request_id == r_id).first()
    if lms:
        if lms.status_id in [StatusEnum.PENDING.value, StatusEnum.REAPPLIED.value]:
            raise HTTPException(status_code=400, detail="LMS request is already pending review.")
        if lms.status_id in [StatusEnum.REVERTED.value, StatusEnum.REVERTED_BY_CHIPS.value]:
            lms.status_id = StatusEnum.REAPPLIED.value
        else:
            lms.status_id = StatusEnum.PENDING.value
    else:
        lms = LMS(request_id=r_id, status="Pending")
        db.add(lms)
        db.flush()
        
    # Fetch DC of this district to receive the remark
    dc_user = db.query(UserLogin).join(MasterUserRole).filter(
        UserLogin.district_id == candidate.district,
        MasterUserRole.role == "DC"
    ).first()
    dc_user_id = dc_user.id if dc_user else None

    # Add initial remark
    remark_text = remark
    if not remark_text or remark_text.strip() == "" or remark_text.lower() == "none":
        remark_text = "LMS request submitted by candidate."

    new_remark = LMSRemark(
        request_id=lms.id,
        remark=remark_text,
        sender_id=login_id,
        receiver_id=dc_user_id,
        is_public=1,
        status_after_id=lms.status_id
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "LMS request submitted successfully."}


@router.post("/submit-nseit/{r_id}")
def submit_nseit_request(r_id: int, remark: str | None = None, login_id: int | None = None,
                         name: str | None = None, exam_unique_code: str | None = None, lms_id: str | None = None,
                         db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Update candidate fields if provided
    if name:
        candidate.name = name
    if exam_unique_code:
        candidate.exam_unique_code = exam_unique_code
    if lms_id:
        candidate.lms_id = lms_id

    nseit = db.query(NSEITRequest).filter(NSEITRequest.request_id == r_id).first()
    if nseit:
        if nseit.status_id in [StatusEnum.PENDING.value, StatusEnum.REAPPLIED.value]:
            raise HTTPException(status_code=400, detail="NSEIT request is already pending review.")
        if nseit.status_id in [StatusEnum.REVERTED.value, StatusEnum.REVERTED_BY_CHIPS.value]:
            nseit.status_id = StatusEnum.REAPPLIED.value
        else:
            nseit.status_id = StatusEnum.PENDING.value
    else:
        nseit = NSEITRequest(request_id=r_id, status="Pending")
        db.add(nseit)
        db.flush()

    # Fetch DC of this district to receive the remark
    dc_user = db.query(UserLogin).join(MasterUserRole).filter(
        UserLogin.district_id == candidate.district,
        MasterUserRole.role == "DC"
    ).first()
    dc_user_id = dc_user.id if dc_user else None
        
    new_remark = NSEITRemark(
        request_id=nseit.id,
        remark=remark or "NSEIT request submitted by candidate.",
        sender_id=login_id,
        receiver_id=dc_user_id,
        is_public=1,
        status_after_id=nseit.status_id
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "NSEIT request submitted successfully."}

@router.post("/skip-lms/{r_id}")
def skip_lms_request(r_id: int, lms_id: str, login_id: int | None = None, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    candidate.lms_id = lms_id
    
    lms = db.query(LMS).filter(LMS.request_id == r_id).first()
    if lms:
        lms.status_id = StatusEnum.SKIPPED.value
    else:
        lms = LMS(request_id=r_id, status="Skipped")
        db.add(lms)
        db.flush()
        
    # Fetch DC of this district to receive the remark
    dc_user = db.query(UserLogin).join(MasterUserRole).filter(
        UserLogin.district_id == candidate.district,
        MasterUserRole.role == "DC"
    ).first()
    dc_user_id = dc_user.id if dc_user else None

    new_remark = LMSRemark(
        request_id=lms.id,
        remark=f"Request skipped. Candidate provided existing LMS ID: {lms_id}",
        sender_id=login_id,
        receiver_id=dc_user_id,
        is_public=1,
        status_after="Skipped"
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "LMS request skipped and ID recorded."}

@router.post("/skip-nseit/{r_id}")
def skip_nseit_request(r_id: int, nseit_id: str, login_id: int | None = None, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    candidate.nseit_id = nseit_id
    
    nseit = db.query(NSEITRequest).filter(NSEITRequest.request_id == r_id).first()
    if nseit:
        nseit.status_id = StatusEnum.SKIPPED.value
    else:
        nseit = NSEITRequest(request_id=r_id, status="Skipped")
        db.add(nseit)
        db.flush()
        
    # Fetch DC of this district to receive the remark
    dc_user = db.query(UserLogin).join(MasterUserRole).filter(
        UserLogin.district_id == candidate.district,
        MasterUserRole.role == "DC"
    ).first()
    dc_user_id = dc_user.id if dc_user else None

    new_remark = NSEITRemark(
        request_id=nseit.id,
        remark=f"Request skipped. Candidate provided existing NSEIT Certificate ID: {nseit_id}",
        sender_id=login_id,
        receiver_id=dc_user_id,
        is_public=1,
        status_after="Skipped"
    )
    db.add(new_remark)
    db.commit()
    return {"success": True, "detail": "NSEIT request skipped and ID recorded."}


@router.post("/update-lms-id/{r_id}")
def update_lms_id(r_id: int, lms_id: str, login_id: int | None = None, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate.lms_id = lms_id
    
    db.commit()
    return {"success": True, "detail": "LMS ID updated successfully."}


@router.post("/update-nseit-id/{r_id}")
def update_nseit_id(r_id: int, nseit_id: str, login_id: int | None = None, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    candidate.nseit_id = nseit_id
    
    db.commit()
    return {"success": True, "detail": "NSEIT ID updated successfully."}

# =========================================================================
# 🌟 REPLACE THIS SINGLE FUNCTION AT THE BOTTOM OF backend/routers/candidate.py
# =========================================================================
@router.get("/export-download/candidate-requests")
def export_candidate_requests_backend(db: Session = Depends(get_db)):
    """
    Fetches all candidate records and exports them using a bulletproof string-conversion loop.
    """
    # 1. Fetch complete data rows safely
    records = db.query(Candidate).all()
    
    # 2. Extract into plain dictionaries using aggressive string-casting logic
    serialized_records = []
    for c in records:
        row = {
            "r_id": str(c.id) if c.id is not None else "—",
            "request_code": str(c.request_code) if c.request_code else "—",
            "district_name": str(c.district_rel.district_name) if (c.district_rel and hasattr(c.district_rel, 'district_name') and c.district_rel.district_name) else (str(c.district) if c.district else "—"),
            "name": str(c.name) if c.name else "—",
            "mobile": str(c.mobile) if c.mobile else "—",
            "email": str(c.email) if c.email else "—",
            "dob": c.dob.strftime("%Y-%m-%d") if (c.dob and hasattr(c.dob, "strftime")) else (str(c.dob) if c.dob else "—"),
            "aadhaar": str(c.aadhaar) if c.aadhaar else "—",
            "qualification": str(c.qualification) if c.qualification else "—",
            "address": str(c.address) if c.address else "—",
            "pincode": str(c.pincode) if c.pincode else "—",
            "is_existing_operator": "Yes" if c.is_existing_operator else "No",
            "lms_id": str(c.lms_id) if c.lms_id else "—",
            "nseit_id": str(c.nseit_id) if c.nseit_id else "—",
            "status": str(c.status) if hasattr(c, 'status') and c.status else "Pending"
        }
        serialized_records.append(row)
    
    # 3. Explicit column mapping configurations
    column_mappings = {
        "r_id": "Database Serial ID",
        "request_code": "Request Code/ID",
        "district_name": "Operational District",
        "name": "Candidate Full Name",
        "mobile": "Mobile Number",
        "email": "Email Address ID",
        "dob": "Date of Birth (DOB)",
        "aadhaar": "Aadhaar Card Number",
        "qualification": "Highest Qualification Degree",
        "address": "Full Communication Address",
        "pincode": "Postal Pincode",
        "is_existing_operator": "Existing Aadhaar Operator?",
        "lms_id": "Allocated LMS ID",
        "nseit_id": "Allocated NSEIT ID",
        "status": "Current Evaluation Status"
    }
    
    return generate_csv_export(serialized_records, column_mappings, "candidate_onboarding_requests")
