# backend/routers/noc.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.routers.auth import get_current_user, RoleChecker
from backend.models import User, NocRequest, RequestStatus, District

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
class NOCRequestSubmit(BaseModel):
    operator_unique_id: str = Field(..., min_length=1, max_length=100, example="OP-98765")
    operator_first_name: str = Field(..., min_length=1, max_length=100, example="Ramesh")
    operator_middle_name: str | None = Field(None, max_length=100, example="Kumar")
    operator_last_name: str = Field(..., min_length=1, max_length=100, example="Sahu")

class NOCDetailsAssign(BaseModel):
    remark: str = Field(..., min_length=1, max_length=1000, example="Approved NOC request.")

class NOCRequestRevert(BaseModel):
    revert_reason: str = Field(..., min_length=1, max_length=500, example="Invalid unique ID.")

class NOCRequestReapply(BaseModel):
    operator_unique_id: str = Field(..., min_length=1, max_length=100, example="OP-98765")
    operator_first_name: str = Field(..., min_length=1, max_length=100, example="Ramesh")
    operator_middle_name: str | None = Field(None, max_length=100, example="Kumar")
    operator_last_name: str = Field(..., min_length=1, max_length=100, example="Sahu")
    remark: str = Field(..., min_length=1, max_length=1000, example="Corrected operator ID.")

# =====================================================================
# HELPER FOR UNIQUE CODE GENERATION
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

def generate_noc_request_code(db: Session, district_id: int, district_name: str, process_code: str = "N") -> str:
    prefix = get_district_prefix(district_name)
    
    last_request = db.query(NocRequest).filter(
        NocRequest.district_id == district_id
    ).order_by(NocRequest.id.desc()).first()
    
    next_num = 1
    if last_request and last_request.request_code:
        code_str = last_request.request_code
        if "-" in code_str:
            parts = code_str.split("-")
            suffix = parts[-1]
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
async def submit_noc_request(
    payload: NOCRequestSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if hasattr(current_user.role, "value"):
        user_role_str = str(current_user.role.value).lower()
    else:
        user_role_str = current_user.role.name.lower()
        
    if user_role_str != "dc":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied. Only District Coordinators can initiate NOC requests."
        )
        
    if not current_user.district_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your DC profile is not linked to a specific district."
        )

    district = db.query(District).filter(District.id == current_user.district_id).first()
    district_name = district.name if district else "Unknown"
    
    req_code = generate_noc_request_code(db, current_user.district_id, district_name, "N")

    new_request = NocRequest(
        operator_unique_id=payload.operator_unique_id,
        operator_first_name=payload.operator_first_name,
        operator_middle_name=payload.operator_middle_name,
        operator_last_name=payload.operator_last_name,
        district_id=current_user.district_id,
        submitted_by_id=current_user.id,
        status=RequestStatus.PENDING,
        request_code=req_code
    )
    
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    
    return {
        "message": "NOC request successfully routed to CHIPS queue.",
        "request_id": new_request.id,
        "request_code": new_request.request_code,
        "status": new_request.status.value
    }

@router.get("/requests")
async def get_noc_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
        requests = db.query(NocRequest).filter(
            NocRequest.district_id == current_user.district_id
        ).order_by(NocRequest.updated_at.desc()).all()
    elif user_role_str == "chips_admin":
        requests = db.query(NocRequest).order_by(NocRequest.updated_at.desc()).all()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Invalid role."
        )
        
    return [
        {
            "id": req.id,
            "request_code": req.request_code,
            "operator_unique_id": req.operator_unique_id,
            "operator_first_name": req.operator_first_name,
            "operator_middle_name": req.operator_middle_name,
            "operator_last_name": req.operator_last_name,
            "status": "revert back" if req.status == RequestStatus.REVERTED else req.status.name.lower(),
            "created_at": req.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "accepted_at": req.updated_at.strftime("%Y-%m-%d %H:%M:%S") if req.status in [RequestStatus.ASSIGNED, RequestStatus.REVERTED, RequestStatus.REAPPLIED] else "",
            "district_name": req.district.name if req.district else "Unknown",
            "revert_reason": req.revert_reason or "",
            "remarks_history": req.remarks_history or []
        }
        for req in requests
    ]

@router.put("/assign/{request_id}", dependencies=[Depends(RoleChecker(["chips_admin"]))])
async def assign_noc_credentials(
    request_id: int,
    payload: NOCDetailsAssign,
    db: Session = Depends(get_db)
):
    target_request = db.query(NocRequest).filter(NocRequest.id == request_id).first()
    
    if not target_request:
        raise HTTPException(status_code=404, detail="NOC request record not found.")
        
    if target_request.status == RequestStatus.ASSIGNED:
        raise HTTPException(status_code=400, detail="NOC has already been issued.")
        
    target_request.status = RequestStatus.ASSIGNED
    
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
        "message": f"NOC issued for Operator {target_request.operator_first_name}.",
        "request_id": target_request.id,
        "status": target_request.status.value
    }

@router.put("/revert/{request_id}", dependencies=[Depends(RoleChecker(["chips_admin"]))])
async def revert_noc_request(
    request_id: int,
    payload: NOCRequestRevert,
    db: Session = Depends(get_db)
):
    target_request = db.query(NocRequest).filter(NocRequest.id == request_id).first()
    
    if not target_request:
        raise HTTPException(status_code=404, detail="NOC request record not found.")
        
    if target_request.status not in [RequestStatus.PENDING, RequestStatus.REAPPLIED, RequestStatus.ASSIGNED]:
        raise HTTPException(status_code=400, detail="Only pending, reapplied, or approved requests can be reverted.")
        
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
        "message": f"NOC request {request_id} has been reverted.",
        "request_id": target_request.id,
        "status": "revert back"
    }

@router.put("/reapply/{request_id}")
async def reapply_noc_request(
    request_id: int,
    payload: NOCRequestReapply,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if hasattr(current_user.role, "value"):
        user_role_str = str(current_user.role.value).lower()
    else:
        user_role_str = current_user.role.name.lower()
        
    if user_role_str != "dc":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied. Only District Coordinators can reapply requests."
        )
        
    target_request = db.query(NocRequest).filter(NocRequest.id == request_id).first()
    if not target_request:
        raise HTTPException(status_code=404, detail="NOC request record not found.")
        
    if target_request.status != RequestStatus.REVERTED:
        raise HTTPException(status_code=400, detail="Only reverted requests can be reapplied.")
        
    target_request.operator_unique_id = payload.operator_unique_id
    target_request.operator_first_name = payload.operator_first_name
    target_request.operator_middle_name = payload.operator_middle_name
    target_request.operator_last_name = payload.operator_last_name
    target_request.status = RequestStatus.REAPPLIED
    
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
        "message": f"NOC Request {request_id} has been reapplied successfully.",
        "request_id": target_request.id,
        "status": "reapplied"
    }
