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
from backend.models.base import StatusEnum
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
        from backend.models.hold_candidate import HoldCandidate
        from backend.models.base import get_ist_now
        
        # 1. Automatically place on hold if no action for 30 days
        limit_date = get_ist_now() - timedelta(days=30)
        old_pendings = db.query(Candidate).filter(
            Candidate.status_id == StatusEnum.PENDING.value,
            Candidate.created_at < limit_date
        ).all()
        if old_pendings:
            for cand in old_pendings:
                hold_cand = HoldCandidate(
                    id=cand.id,
                    request_code=cand.request_code,
                    name=cand.name,
                    mobile=cand.mobile,
                    email=cand.email,
                    district=cand.district,
                    qualification=cand.qualification,
                    lms_id=cand.lms_id,
                    nseit_id=cand.nseit_id,
                    exam_unique_code=cand.exam_unique_code,
                    dob=cand.dob,
                    aadhaar=cand.aadhaar,
                    address=cand.address,
                    pincode=cand.pincode,
                    photo_upload=cand.photo_upload,
                    tenth_marksheet_upload=cand.tenth_marksheet_upload,
                    marksheet_upload=cand.marksheet_upload,
                    is_existing_operator=cand.is_existing_operator,
                    created_at=cand.created_at,
                    updated_at=get_ist_now(),
                    status_id=StatusEnum.ON_HOLD.value,
                    hold_remark="Automatically placed on hold: No action taken for more than 1 month."
                )
                db.query(DCRemark).filter(DCRemark.request_id == cand.id).delete()
                db.delete(cand)
                db.add(hold_cand)
            db.commit()

        # 2. Query normal candidates
        query = db.query(Candidate)
        if district_code and district_code != "all":
            query = query.filter(Candidate.district == district_code)
        candidates = query.order_by(func.coalesce(Candidate.updated_at, Candidate.created_at).desc()).all()
        
        # 3. Query hold candidates
        hold_query = db.query(HoldCandidate)
        if district_code and district_code != "all":
            hold_query = hold_query.filter(HoldCandidate.district == district_code)
        hold_candidates = hold_query.order_by(func.coalesce(HoldCandidate.updated_at, HoldCandidate.created_at).desc()).all()

        result = []
        for c in hold_candidates:
            district_name = c.district_rel.district_name if c.district_rel else "Unknown"
            result.append({
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
                "tenth_marksheet_upload": c.tenth_marksheet_upload or "",
                "marksheet_upload": c.marksheet_upload or "",
                "lms_certificate_upload": "",
                "nseit_certificate_upload": "",
                "status": "On Hold",
                "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "",
                "updated_at": c.updated_at.strftime("%Y-%m-%d %H:%M:%S") if c.updated_at else "",
                "remarks_history": [
                    {
                        "id": 0,
                        "remark": c.hold_remark or "Placed on hold.",
                        "created_at": c.updated_at.strftime("%Y-%m-%d %H:%M:%S") if c.updated_at else "",
                        "sender_role": "DC",
                        "sender_username": "System"
                    }
                ]
            })
        for c in candidates:
            district_name = c.district_rel.district_name if c.district_rel else "Unknown"
            remarks = db.query(DCRemark).filter(DCRemark.request_id == c.id).order_by(DCRemark.time.asc()).all()

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
            if c.status_id == StatusEnum.APPROVED.value and c.login:
                login_id = c.login.user_id
                password_raw = "Test@123"
                
            result.append({
                "r_id": c.id,
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
                "lms_certificate_upload": c.lms_certificate_upload or "",
                "nseit_certificate_upload": c.nseit_certificate_upload or "",
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
    from backend.models.hold_candidate import HoldCandidate
    id_list = []
    if ids:
        id_list = [int(x) for x in ids.split(",") if x.isdigit()]

    c_query = db.query(Candidate)
    if id_list:
        c_query = c_query.filter(Candidate.id.in_(id_list))
    candidates = c_query.all()

    h_query = db.query(HoldCandidate)
    if id_list:
        h_query = h_query.filter(HoldCandidate.id.in_(id_list))
    hold_candidates = h_query.all()

    export_data = []
    idx = 0
    for c in candidates:
        district_name = c.district_rel.district_name if c.district_rel else "Unknown"

        login_id = ""
        password_raw = ""
        if c.status_id == StatusEnum.APPROVED.value and c.login:
            login_id = c.login.user_id
            password_raw = "Test@123"

        latest_remark = (
            db.query(DCRemark)
            .filter(DCRemark.request_id == c.id)
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
        idx += 1

    for c in hold_candidates:
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
            "nseit_id": c.nseit_id or "",
            "status": "On Hold",
            "dc_remark": c.hold_remark or "Placed on hold.",
            "submitted_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "",
            "updated_at": (c.updated_at or c.created_at).strftime("%Y-%m-%d %H:%M:%S") if (c.updated_at or c.created_at) else "",
        })
        idx += 1

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

    # If all requests in the export are Pending, remove updated_at and dc_remark columns
    if candidates and all(c.status_id == StatusEnum.PENDING.value for c in candidates):
        column_mappings.pop("dc_remark", None)
        column_mappings.pop("updated_at", None)

    return generate_csv_export(export_data, column_mappings, "candidate_requests")

@router.post("/approve-candidate/{r_id}")
def approve_candidate(r_id: int, payload: CandidateApproveRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    if not candidate:
        from backend.models.hold_candidate import HoldCandidate
        from backend.models.base import get_ist_now
        hold_cand = db.query(HoldCandidate).filter(HoldCandidate.id == r_id).first()
        if not hold_cand:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        # Move back to Candidate
        candidate = Candidate(
            id=hold_cand.id,
            request_code=hold_cand.request_code,
            name=hold_cand.name,
            mobile=hold_cand.mobile,
            email=hold_cand.email,
            district=hold_cand.district,
            qualification=hold_cand.qualification,
            lms_id=hold_cand.lms_id,
            nseit_id=hold_cand.nseit_id,
            exam_unique_code=hold_cand.exam_unique_code,
            dob=hold_cand.dob,
            aadhaar=hold_cand.aadhaar,
            address=hold_cand.address,
            pincode=hold_cand.pincode,
            photo_upload=hold_cand.photo_upload,
            tenth_marksheet_upload=hold_cand.tenth_marksheet_upload,
            marksheet_upload=hold_cand.marksheet_upload,
            is_existing_operator=hold_cand.is_existing_operator,
            created_at=hold_cand.created_at,
            updated_at=get_ist_now(),
            status_id=StatusEnum.PENDING.value
        )
        db.delete(hold_cand)
        db.add(candidate)
        db.flush()
        
    existing_login = db.query(CandidateLogin).filter(CandidateLogin.request_id == r_id).first()
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
        request_id=r_id,
        user_id=username,
        password=hashed_pw
    )
    db.add(new_login)
    
    candidate.status_id = StatusEnum.APPROVED.value
    
    remark_text = payload.remark or "Application reviewed and approved."
    if payload.force_without_email:
        remark_text = f"[Email Failed] {remark_text}"

    new_remark = DCRemark(
        request_id=r_id,
        remark=remark_text,
        by=payload.by_user_id,
        status_after_id=StatusEnum.APPROVED.value
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
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    if not candidate:
        from backend.models.hold_candidate import HoldCandidate
        from backend.models.base import get_ist_now
        hold_cand = db.query(HoldCandidate).filter(HoldCandidate.id == r_id).first()
        if not hold_cand:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        # Move back to Candidate
        candidate = Candidate(
            id=hold_cand.id,
            request_code=hold_cand.request_code,
            name=hold_cand.name,
            mobile=hold_cand.mobile,
            email=hold_cand.email,
            district=hold_cand.district,
            qualification=hold_cand.qualification,
            lms_id=hold_cand.lms_id,
            nseit_id=hold_cand.nseit_id,
            exam_unique_code=hold_cand.exam_unique_code,
            dob=hold_cand.dob,
            aadhaar=hold_cand.aadhaar,
            address=hold_cand.address,
            pincode=hold_cand.pincode,
            photo_upload=hold_cand.photo_upload,
            tenth_marksheet_upload=hold_cand.tenth_marksheet_upload,
            marksheet_upload=hold_cand.marksheet_upload,
            is_existing_operator=hold_cand.is_existing_operator,
            created_at=hold_cand.created_at,
            updated_at=get_ist_now(),
            status_id=StatusEnum.PENDING.value
        )
        db.delete(hold_cand)
        db.add(candidate)
        db.flush()
        
    candidate.status_id = StatusEnum.REJECTED.value
    
    remark_text = payload.remark
    if payload.force_without_email:
        remark_text = f"[Email Failed] {remark_text}"

    new_remark = DCRemark(
        request_id=r_id,
        remark=remark_text,
        by=payload.by_user_id,
        status_after_id=StatusEnum.REJECTED.value
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


class CandidateHoldRequest(BaseModel):
    remark: str
    by_user_id: int


@router.post("/hold-candidate/{r_id}")
def hold_candidate(r_id: int, payload: CandidateHoldRequest, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == r_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    remark_text = payload.remark.strip()
    if not remark_text:
        raise HTTPException(status_code=400, detail="Hold remark is mandatory.")
        
    from backend.models.hold_candidate import HoldCandidate
    from backend.models.base import get_ist_now
    
    # Move to HoldCandidate
    hold_cand = HoldCandidate(
        id=candidate.id,
        request_code=candidate.request_code,
        name=candidate.name,
        mobile=candidate.mobile,
        email=candidate.email,
        district=candidate.district,
        qualification=candidate.qualification,
        lms_id=candidate.lms_id,
        nseit_id=candidate.nseit_id,
        exam_unique_code=candidate.exam_unique_code,
        dob=candidate.dob,
        aadhaar=candidate.aadhaar,
        address=candidate.address,
        pincode=candidate.pincode,
        photo_upload=candidate.photo_upload,
        tenth_marksheet_upload=candidate.tenth_marksheet_upload,
        marksheet_upload=candidate.marksheet_upload,
        is_existing_operator=candidate.is_existing_operator,
        created_at=candidate.created_at,
        updated_at=get_ist_now(),
        status_id=StatusEnum.ON_HOLD.value,
        hold_remark=remark_text
    )
    
    # Delete associated DC remarks to avoid FK conflict
    db.query(DCRemark).filter(DCRemark.request_id == candidate.id).delete()
    db.delete(candidate)
    db.add(hold_cand)
    db.commit()
    
    return {"success": True, "detail": "Candidate onboarding request successfully placed on hold."}
