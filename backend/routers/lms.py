from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.routers.auth import get_current_user, RoleChecker
from backend.models import User, CredentialRequest, RequestStatus, District
from backend.utils.email_verifier import verify_email_exists

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =====================================================================
# PYDANTIC SCHEMAS
# =====================================================================
class LMSRequestSubmit(BaseModel):
    operator_first_name: str = Field(..., min_length=1, max_length=100, example="Ramesh")
    operator_middle_name: str | None = Field(None, max_length=100, example="Kumar")
    operator_last_name: str = Field(..., min_length=1, max_length=100, example="Sahu")
    operator_phone: str = Field(..., min_length=10, max_length=15, example="9876543210")
    operator_email: EmailStr = Field(..., example="ramesh.sahu@example.com")

class LMSCredentialsAssign(BaseModel):
    generated_login_id: str = Field(..., example="LMS-RAIPUR-OP88")
    generated_password_raw: str = Field(..., example="VideoPass2026!")
    remark: str | None = Field(None, max_length=1000)

class LMSRequestRevert(BaseModel):
    revert_reason: str = Field(..., min_length=1, max_length=500, example="Invalid coordinates.")

class LMSRequestReapply(BaseModel):
    operator_first_name: str = Field(..., min_length=1, max_length=100, example="Ramesh")
    operator_middle_name: str | None = Field(None, max_length=100, example="Kumar")
    operator_last_name: str = Field(..., min_length=1, max_length=100, example="Sahu")
    operator_phone: str = Field(..., min_length=10, max_length=15, example="9876543210")
    operator_email: EmailStr = Field(..., example="ramesh.sahu@example.com")
    remark: str = Field(..., min_length=1, max_length=1000, example="Corrected operator details.")

# =====================================================================
# HELPER FUNCTIONS FOR UNIQUE ID GENERATION
# =====================================================================
DISTRICT_PREFIX_MAP = {
    "raipur": "RP",
    "bilaspur": "BP",
    "durg": "DG"
}

def get_district_prefix(district_name: str) -> str:
    name_clean = district_name.strip().lower()
    if name_clean in DISTRICT_PREFIX_MAP:
        return DISTRICT_PREFIX_MAP[name_clean]
    prefix = "".join([c for c in name_clean if c.isalnum()])[:2].upper()
    return prefix if len(prefix) == 2 else "XX"

def generate_request_code(db: Session, district_id: int, district_name: str, process_code: str = "A") -> str:
    prefix = get_district_prefix(district_name)
    
    # Query last request for this district to determine the sequence number
    last_request = db.query(CredentialRequest).filter(
        CredentialRequest.district_id == district_id
    ).order_by(CredentialRequest.id.desc()).first()
    
    next_num = 1
    if last_request and last_request.request_code:
        code_str = last_request.request_code
        if "-" in code_str:
            parts = code_str.split("-")
            suffix = parts[-1] # e.g. A0001
            if len(suffix) > 1 and suffix[0].isalpha():
                try:
                    next_num = int(suffix[1:]) + 1
                except ValueError:
                    pass
                    
    return f"{prefix}-{process_code}{next_num:04d}"

# =====================================================================
# ENDPOINTS
# =====================================================================

@router.post("/request", status_code=status.HTTP_201_CREATED)
async def submit_lms_request(
    payload: LMSRequestSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    DC Submission Route: Creates a pending operator request for video credentials.
    """
    if hasattr(current_user.role, "value"):
        user_role_str = str(current_user.role.value).lower()
    else:
        user_role_str = current_user.role.name.lower()
    print(f"DEBUG: username={current_user.username}, role={current_user.role}, user_role_str={user_role_str}")
    if user_role_str != "dc":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access Denied. Only District Commissioners can initiate LMS requests. Active User: {current_user.username}, Role: {current_user.role}, Resolved: {user_role_str}"
        )
        
    if not current_user.district_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your DC profile is not linked to a specific district."
        )

    # Fetch district name to generate prefix
    district = db.query(District).filter(District.id == current_user.district_id).first()
    district_name = district.name if district else "Unknown"
    
    req_code = generate_request_code(db, current_user.district_id, district_name, "A")

    # Verify operator email exists
    if not verify_email_exists(payload.operator_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter a valid active email ID."
        )

    new_request = CredentialRequest(
        operator_first_name=payload.operator_first_name,
        operator_middle_name=payload.operator_middle_name,
        operator_last_name=payload.operator_last_name,
        operator_phone=payload.operator_phone,
        operator_email=payload.operator_email,
        district_id=current_user.district_id,
        submitted_by_id=current_user.id,
        status=RequestStatus.PENDING,
        request_code=req_code
    )
    
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    
    return {
        "message": "LMS request successfully routed to CHIPS queue.",
        "request_id": new_request.id,
        "request_code": new_request.request_code,
        "status": new_request.status.value
    }

@router.put("/assign/{request_id}", dependencies=[Depends(RoleChecker(["chips_admin"]))])
async def assign_lms_credentials(
    request_id: int,
    payload: LMSCredentialsAssign,
    db: Session = Depends(get_db)
):
    """
    CHIPS Admin Assignment Route: Fulfills a pending request with login/password keys.
    """
    target_request = db.query(CredentialRequest).filter(CredentialRequest.id == request_id).first()
    
    if not target_request:
        raise HTTPException(status_code=404, detail="LMS request record not found.")
        
    if target_request.status == RequestStatus.ASSIGNED:
        raise HTTPException(status_code=400, detail="Credentials have already been issued.")
        
    if target_request.status == RequestStatus.REVERTED and (not payload.remark or not payload.remark.strip()):
        raise HTTPException(status_code=400, detail="A remark is mandatory when approving a reverted request.")
        
    target_request.generated_login_id = payload.generated_login_id
    target_request.generated_password_raw = payload.generated_password_raw
    target_request.status = RequestStatus.ASSIGNED
    
    if payload.remark and payload.remark.strip():
        from backend.models.base import get_ist_time
        from sqlalchemy.orm.attributes import flag_modified
        new_remark = {
            "sender_role": "CHIPS",
            "remark": payload.remark.strip(),
            "created_at": get_ist_time().strftime("%Y-%m-%d %H:%M:%S")
        }
        history = list(target_request.remarks_history or [])
        history.append(new_remark)
        target_request.remarks_history = history
        flag_modified(target_request, "remarks_history")
        
    db.commit()
    
    return {
        "message": f"Video access tokens assigned for Operator {target_request.operator_first_name}.",
        "request_id": target_request.id,
        "status": target_request.status.value
    }

@router.put("/revert/{request_id}", dependencies=[Depends(RoleChecker(["chips_admin"]))])
async def revert_lms_request(
    request_id: int,
    payload: LMSRequestRevert,
    db: Session = Depends(get_db)
):
    """
    CHIPS Admin Revert Route: Marks a request as reverted with a reason.
    """
    target_request = db.query(CredentialRequest).filter(CredentialRequest.id == request_id).first()
    
    if not target_request:
        raise HTTPException(status_code=404, detail="LMS request record not found.")
        
    if target_request.status not in [RequestStatus.PENDING, RequestStatus.REAPPLIED, RequestStatus.ASSIGNED]:
        raise HTTPException(status_code=400, detail="Only pending, reapplied, or approved requests can be reverted.")
        
    target_request.generated_login_id = None
    target_request.generated_password_raw = None
    target_request.revert_reason = payload.revert_reason
    target_request.status = RequestStatus.REVERTED
    
    from backend.models.base import get_ist_time
    from sqlalchemy.orm.attributes import flag_modified
    new_remark = {
        "sender_role": "CHIPS",
        "remark": payload.revert_reason,
        "created_at": get_ist_time().strftime("%Y-%m-%d %H:%M:%S")
    }
    history = list(target_request.remarks_history or [])
    history.append(new_remark)
    target_request.remarks_history = history
    flag_modified(target_request, "remarks_history")
    
    db.commit()
    
    return {
        "message": f"Request {request_id} has been reverted.",
        "request_id": target_request.id,
        "status": "revert back"
    }

@router.put("/reapply/{request_id}")
async def reapply_lms_request(
    request_id: int,
    payload: LMSRequestReapply,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    DC Reapply Route: Updates operator details and changes status to REAPPLIED.
    """
    if hasattr(current_user.role, "value"):
        user_role_str = str(current_user.role.value).lower()
    else:
        user_role_str = current_user.role.name.lower()
        
    if user_role_str != "dc":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied. Only District Coordinators can reapply requests."
        )
        
    target_request = db.query(CredentialRequest).filter(CredentialRequest.id == request_id).first()
    if not target_request:
        raise HTTPException(status_code=404, detail="LMS request record not found.")
        
    if target_request.status != RequestStatus.REVERTED:
        raise HTTPException(status_code=400, detail="Only reverted requests can be reapplied.")
        
    # Verify operator email exists
    if not verify_email_exists(payload.operator_email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter a valid active email ID."
        )

    # Update operator info
    target_request.operator_first_name = payload.operator_first_name
    target_request.operator_middle_name = payload.operator_middle_name
    target_request.operator_last_name = payload.operator_last_name
    target_request.operator_phone = payload.operator_phone
    target_request.operator_email = payload.operator_email
    target_request.status = RequestStatus.REAPPLIED
    
    # Log the reapply remark
    from backend.models.base import get_ist_time
    from sqlalchemy.orm.attributes import flag_modified
    new_remark = {
        "sender_role": "DC",
        "remark": payload.remark,
        "created_at": get_ist_time().strftime("%Y-%m-%d %H:%M:%S")
    }
    history = list(target_request.remarks_history or [])
    history.append(new_remark)
    target_request.remarks_history = history
    flag_modified(target_request, "remarks_history")
    
    db.commit()
    
    return {
        "message": f"Request {request_id} has been reapplied successfully.",
        "request_id": target_request.id,
        "status": "reapplied"
    }

@router.get("/requests")
async def get_lms_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch credential requests. DCs see requests for their district, Admins see all.
    """
    if hasattr(current_user.role, "value"):
        user_role_str = str(current_user.role.value).lower()
    else:
        user_role_str = current_user.role.name.lower()
    
    if user_role_str == "dc":
        if not current_user.district_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your DC profile is not linked to a specific district."
            )
        requests = db.query(CredentialRequest).filter(
            CredentialRequest.district_id == current_user.district_id
        ).order_by(CredentialRequest.updated_at.desc()).all()
    elif user_role_str == "chips_admin":
        requests = db.query(CredentialRequest).order_by(CredentialRequest.updated_at.desc()).all()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Invalid role."
        )
        
    return [
        {
            "id": req.id,
            "request_code": req.request_code,
            "operator_first_name": req.operator_first_name,
            "operator_middle_name": req.operator_middle_name,
            "operator_last_name": req.operator_last_name,
            "operator_phone": req.operator_phone,
            "operator_email": req.operator_email,
            "status": "revert back" if req.status == RequestStatus.REVERTED else req.status.name.lower(), # "pending", "assigned", "revert back", "reapplied"
            "created_at": req.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "accepted_at": req.updated_at.strftime("%Y-%m-%d %H:%M:%S") if req.status in [RequestStatus.ASSIGNED, RequestStatus.REVERTED, RequestStatus.REAPPLIED] else "",
            "district_name": req.district_details.name if req.district_details else "Unknown",
            "generated_login_id": req.generated_login_id or "",
            "generated_password_raw": req.generated_password_raw or "",
            "revert_reason": req.revert_reason or "",
            "remarks_history": req.remarks_history or []
        }
        for req in requests
    ]
        
