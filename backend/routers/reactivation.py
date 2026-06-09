# backend/routers/reactivation.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
import pandas as pd
import os
import shutil
from datetime import date
from typing import Optional

from backend.database import SessionLocal
from backend.routers.auth import get_current_user, RoleChecker
from backend.models import User, OperatorReactivationRequest, ReactivationDocument, ReactivationOperator, District
from backend.models.reactivation import RequestStatus
from backend.models.base import get_ist_time

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =====================================================================
# FILE SYSTEM DIR CONFIG
# =====================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "reactivation_docs")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# =====================================================================
# PYDANTIC SCHEMAS
# =====================================================================
class ReactivationCredentialsAssign(BaseModel):
    remark: Optional[str] = Field(None, max_length=1000)

class ReactivationRequestRevert(BaseModel):
    revert_reason: str = Field(..., min_length=1, max_length=500, example="Attendance sheet structure is invalid.")

# =====================================================================
# HELPER FUNCTIONS FOR ALPHANUMERIC GENERATION (MATCHING LMS.PY)
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

def generate_reactivation_code(db: Session, district_id: int, district_name: str, process_code: str = "R") -> tuple:
    """
    Generates regional sequential codes mirroring LMS logic.
    Returns: (Formatted Alphanumeric ID string, next integer sequence index)
    """
    prefix = get_district_prefix(district_name)
    
    # Query last request for this district to determine the sequence number
    last_request = db.query(OperatorReactivationRequest).filter(
        OperatorReactivationRequest.district_id == district_id
    ).order_by(OperatorReactivationRequest.id.desc()).first()
    
    next_num = 1
    if last_request and last_request.request_number:
        next_num = int(last_request.request_number) + 1
                    
    return f"{prefix}-{process_code}{next_num:04d}", next_num

# =====================================================================
# ENDPOINTS
# =====================================================================

@router.post("/submit", status_code=status.HTTP_201_CREATED)
async def submit_operator_reactivation(
    training_date: str = Form(...),
    training_photo: UploadFile = File(...),
    nodal_letter: UploadFile = File(...),
    om_letter: UploadFile = File(...),
    attendance_list: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    DC Submission Route: Uploads batch validation items and parses attendance vectors.
    """
    if hasattr(current_user.role, "value"):
        user_role_str = str(current_user.role.value).lower()
    else:
        user_role_str = current_user.role.name.lower()
        
    if user_role_str != "dc":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access Denied. Only District Commissioners can initiate reactivation requests."
        )
        
    if not current_user.district_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your DC profile is not linked to a specific district."
        )

    # 1. Parse Data Spreadsheets Matrix Securely
    try:
        df = pd.read_excel(attendance_list.file)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Excel Workbook File Signature: {str(e)}"
        )

    # Normalize column maps headers cleanly
    df.columns = [str(col).strip().lower().replace(" ", "_") for col in df.columns]
    name_col = next((col for col in df.columns if "name" in col or "operator" in col), None)
    mobile_col = next((col for col in df.columns if "mobile" in col or "phone" in col or "contact" in col), None)

    if not name_col or not mobile_col:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Excel structure invalid. Worksheet must contain operator name and mobile columns."
        )

    parsed_operator_count = len(df.dropna(subset=[name_col]))
    if parsed_operator_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded attendance matrix array holds zero valid operator rows."
        )

    # 2. Fetch District Context and Calculate Code Sequence Tags (Aligned with LMS layout)
    district = db.query(District).filter(District.id == current_user.district_id).first()
    district_name = district.name if district else "Unknown"
    
    req_code, next_seq = generate_reactivation_code(db, current_user.district_id, district_name, "R")

    # 3. Create Request Entry
    new_request = OperatorReactivationRequest(
        dc_id=current_user.id,
        district_id=current_user.district_id,
        operator_count=parsed_operator_count,
        training_date=date.fromisoformat(training_date.strip()),
        request_code=req_code,
        request_number=next_seq,
        status=RequestStatus.PENDING
    )
    db.add(new_request)
    db.flush()

    # 4. Stream and Write Binary payloads on local data drive
    request_folder = os.path.join(UPLOAD_DIR, str(new_request.id))
    os.makedirs(request_folder, exist_ok=True)

    document_files = {
        "training_photo": training_photo,
        "nodal_letter": nodal_letter,
        "om_letter": om_letter,
        "attendance_list": attendance_list
    }

    for doc_type, uploaded_file in document_files.items():
        file_save_path = os.path.join(request_folder, f"{doc_type}_{uploaded_file.filename}")
        uploaded_file.file.seek(0)
        with open(file_save_path, "wb") as buffer:
            shutil.copyfileobj(uploaded_file.file, buffer)

        db.add(ReactivationDocument(
            request_id=new_request.id,
            doc_type=doc_type,
            file_path=file_save_path,
            original_filename=uploaded_file.filename
        ))

    # 5. Extract Operator Sub-Profiles
    for _, row in df.iterrows():
        if pd.isna(row[name_col]) or str(row[name_col]).strip() == "":
            continue

        mobile_str = None
        if not pd.isna(row[mobile_col]) and str(row[mobile_col]).strip() != "":
            raw_mobile = row[mobile_col]
            if isinstance(raw_mobile, (int, float)):
                mobile_str = str(int(raw_mobile))
            else:
                mobile_str = str(raw_mobile).strip().split('.')[0]

        db.add(ReactivationOperator(
            request_id=new_request.id,
            operator_name=str(row[name_col]).strip(),
            operator_mobile=mobile_str
        ))

    db.commit()
    
    return {
        "message": "Operator Reactivation batch package routed successfully to CHIPS queue.",
        "request_id": new_request.id,
        "request_code": new_request.request_code,
        "status": new_request.status.value
    }


@router.get("/requests")
async def get_reactivation_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetch history logs tracking array: DCs lock onto local scope, Admins query everything.
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
        requests = db.query(OperatorReactivationRequest).filter(
            OperatorReactivationRequest.district_id == current_user.district_id
        ).order_by(OperatorReactivationRequest.submitted_at.desc()).all()
    elif user_role_str == "chips_admin":
        requests = db.query(OperatorReactivationRequest).order_by(OperatorReactivationRequest.submitted_at.desc()).all()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Invalid role context."
        )
        
    return [
        {
            "id": req.id,
            "request_code": req.request_code,  # Naming synced with database column
            "operator_count": req.operator_count,
            "training_date": req.training_date.isoformat() if req.training_date else "",
            "status": "revert back" if req.status == RequestStatus.REVERTED else req.status.name.lower(),
            "submitted_at": req.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if req.submitted_at else "",  # Formatted Timestamp
            "district_name": req.district_details.name if req.district_details else "Unknown",
            "revert_reason": req.revert_reason or "",
            "remarks_history": req.remarks_history or []
        }
        for req in requests
    ]