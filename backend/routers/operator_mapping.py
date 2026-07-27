from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user_login import UserLogin
from backend.models.operator import Operator
from backend.models.station_id import StationIDRequest
from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
from backend.routers.auth import get_current_user

router = APIRouter(
    prefix="/dc/operator-mapping",
    tags=["operator_mapping"],
)

class OperatorMappingCreate(BaseModel):
    station_id: str
    operator_id: int

@router.get("/options")
def get_mapping_options(
    db: Session = Depends(get_db),
    current_user: UserLogin = Depends(get_current_user)
) -> Dict[str, Any]:
    """Returns unmapped operators and available station IDs for the DC."""
    if current_user.role.role not in ["DC", "EDM"]:
        raise HTTPException(status_code=403, detail="Only DC/EDM can fetch these options.")
        
    # Get all active station IDs approved for this DC's district
    approved_stations = db.query(StationIDRequest).filter(
        StationIDRequest.district_id == current_user.district_id,
        StationIDRequest.station_id_inserted.isnot(None)
    ).all()
    
    station_ids = []
    for s in approved_stations:
        if s.station_id_inserted:
            # Handle comma-separated Station IDs
            ids = [i.strip() for i in s.station_id_inserted.split(',')]
            station_ids.extend(ids)

    # Get already mapped records
    onboarded_records = db.query(OperatorOnboardingDetail).all()
    onboarded_ids = [r.operator_id for r in onboarded_records]
    mapped_station_ids = set([r.station_id for r in onboarded_records])

    # Filter out station IDs that are already mapped
    available_station_ids = [s for s in station_ids if s not in mapped_station_ids]

    # Get all Operators for this DC that are not yet onboarded/mapped and are Inactive
    query = db.query(Operator).filter(
        Operator.mapped_dc_id == current_user.id,
        Operator.status == "Inactive"
    )
    if onboarded_ids:
        query = query.filter(Operator.id.notin_(onboarded_ids))
        
    available_operators = query.all()

    operator_data = []
    for op in available_operators:
        op_text = f"{op.name} || {op.mobile}"
        if op.user_code:
            op_text += f" || {op.user_code}"
        operator_data.append({
            "id": op.id,
            "text": op_text
        })

    return {
        "station_ids": list(set(available_station_ids)),
        "operators": operator_data
    }


@router.post("")
def create_mapping(
    payload: OperatorMappingCreate,
    db: Session = Depends(get_db),
    current_user: UserLogin = Depends(get_current_user)
):
    if current_user.role.role not in ["DC", "EDM"]:
        raise HTTPException(status_code=403, detail="Only DC/EDM can map operators.")

    # Find the operator
    operator = db.query(Operator).filter(
        Operator.id == payload.operator_id,
        Operator.mapped_dc_id == current_user.id
    ).first()

    if not operator:
        raise HTTPException(status_code=404, detail="Operator not found.")

    existing_mapping = db.query(OperatorOnboardingDetail).filter(OperatorOnboardingDetail.operator_id == operator.id).first()
    if existing_mapping:
        raise HTTPException(status_code=400, detail="Operator is already mapped to a station.")

    existing_station_mapping = db.query(OperatorOnboardingDetail).filter(OperatorOnboardingDetail.station_id == payload.station_id).first()
    if existing_station_mapping:
        raise HTTPException(status_code=400, detail="This Station ID is already mapped to another operator.")

    # Map the operator using OperatorOnboardingDetail
    new_mapping = OperatorOnboardingDetail(
        operator_id=operator.id,
        station_id=payload.station_id,
        onboarding_status="Mapped",
        ask_kit_working_status="Pending",
        permitted_18_plus="Pending",
        remark="Mapped via DC Portal"
    )
    db.add(new_mapping)
    db.commit()
    
    return {"status": "success", "message": "Operator mapped successfully."}


@router.get("")
def list_mappings(
    db: Session = Depends(get_db),
    current_user: UserLogin = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    if current_user.role.role not in ["DC", "EDM"]:
        raise HTTPException(status_code=403, detail="Only DC/EDM can view mappings.")

    # Fetch operators that are mapped to a station via OperatorOnboardingDetail
    mappings = db.query(OperatorOnboardingDetail).join(Operator).filter(
        Operator.mapped_dc_id == current_user.id
    ).all()
    
    results = []
    for m in mappings:
        op = m.operator
        op_text = f"{op.name} || {op.mobile}"
        if op.user_code:
            op_text += f" || {op.user_code}"
            
        results.append({
            "id": op.id,
            "station_id": m.station_id,
            "operator_text": op_text
        })
        
    return results

@router.delete("/{operator_id}")
def delete_mapping(
    operator_id: int,
    reason: str = "Inactive",
    db: Session = Depends(get_db),
    current_user: UserLogin = Depends(get_current_user)
):
    if current_user.role.role not in ["DC", "EDM"]:
        raise HTTPException(status_code=403, detail="Only DC/EDM can delete mappings.")

    operator = db.query(Operator).filter(
        Operator.id == operator_id,
        Operator.mapped_dc_id == current_user.id
    ).first()
    
    if not operator:
        raise HTTPException(status_code=404, detail="Operator not found.")

    mapping = db.query(OperatorOnboardingDetail).filter(OperatorOnboardingDetail.operator_id == operator_id).first()
    if mapping:
        db.delete(mapping)

    valid_reasons = {"Inactive", "Suspended", "Resigned"}
    if reason not in valid_reasons:
        reason = "Inactive"

    operator.status = reason

    db.commit()
    return {"status": "success", "message": "Mapping removed.", "new_status": reason}
