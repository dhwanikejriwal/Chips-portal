from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.routers.auth import get_current_user, RoleChecker
from backend.models import User, CredentialRequest, RequestStatus, District

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

    new_request = CredentialRequest(
        operator_first_name=payload.operator_first_name,
        operator_middle_name=payload.operator_middle_name,
        operator_last_name=payload.operator_last_name,
        operator_phone=payload.operator_phone,
        operator_email=payload.operator_email,
        district_id=current_user.district_id,
        submitted_by_id=current_user.id,
        status=RequestStatus.PENDING
    )
    
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    
    return {
        "message": "LMS request successfully routed to CHIPS queue.",
        "request_id": new_request.id,
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
        
    target_request.generated_login_id = payload.generated_login_id
    target_request.generated_password_raw = payload.generated_password_raw
    target_request.status = RequestStatus.ASSIGNED
    
    db.commit()
    
    return {
        "message": f"Video access tokens assigned for Operator {target_request.operator_first_name}.",
        "request_id": target_request.id,
        "status": target_request.status.value
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
        ).order_by(CredentialRequest.created_at.desc()).all()
    elif user_role_str == "chips_admin":
        requests = db.query(CredentialRequest).order_by(CredentialRequest.created_at.desc()).all()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Invalid role."
        )
        
    return [
        {
            "id": req.id,
            "operator_first_name": req.operator_first_name,
            "operator_middle_name": req.operator_middle_name,
            "operator_last_name": req.operator_last_name,
            "operator_phone": req.operator_phone,
            "operator_email": req.operator_email,
            "status": req.status.name.lower(), # "pending" or "assigned"
            "created_at": req.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "accepted_at": req.updated_at.strftime("%Y-%m-%d %H:%M:%S") if req.status == RequestStatus.ASSIGNED else "",
            "district_name": req.district_details.name if req.district_details else "Unknown",
            "generated_login_id": req.generated_login_id or "",
            "generated_password_raw": req.generated_password_raw or ""
        }
        for req in requests
    ]