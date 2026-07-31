from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user_login import UserLogin
from backend.models.operator import Operator
from backend.models.operator_onboarding import OperatorOnboarding
from backend.models.l2_registration import L2RegistrationRequest
from backend.routers.auth import get_current_user

router = APIRouter(
    prefix="/dc/operator-onboarding",
    tags=["operator_onboarding"],
)

class OperatorOnboardingSubmit(BaseModel):
    station_id: str
    onboarding_status: str
    ask_kit_working_status: str
    permitted_18_plus: str
    remark: str = ""

@router.get("/options")
def get_onboarding_options(
    db: Session = Depends(get_db),
    current_user: UserLogin = Depends(get_current_user)
) -> Dict[str, Any]:
    """Returns Station IDs that have L2 done AND have a mapped operator pending onboarding."""
    if current_user.role.role not in ["DC", "EDM"]:
        raise HTTPException(status_code=403, detail="Only DC/EDM can fetch these options.")
        
    # Get all Station IDs whose L2 is done for the current user's district
    l2_requests = db.query(L2RegistrationRequest).filter(
        L2RegistrationRequest.district_id == current_user.district_id
    ).all()
    
    approved_l2_stations = [
        req.new_station_id for req in l2_requests if req.status.upper() in ["APPROVED", "APPROVED_BY_CHIPS", "L2_DONE"]
    ]

    # Find OperatorOnboarding records mapped to these stations but NOT fully onboarded
    pending_mappings = db.query(OperatorOnboarding).join(Operator).filter(
        Operator.district_id == current_user.district_id,
        OperatorOnboarding.station_id.in_(approved_l2_stations) if approved_l2_stations else False,
        OperatorOnboarding.onboarding_status == "Mapped"
    ).all()

    mapped_station_ids = [m.station_id for m in pending_mappings]

    # Combine L2 stations and explicitly mapped stations
    station_ids = list(set(approved_l2_stations + mapped_station_ids))

    # Find onboarding records that are already fully onboarded (Completed)
    completed_mappings = db.query(OperatorOnboarding).filter(
        OperatorOnboarding.onboarding_status == "Completed"
    ).all()
    completed_station_ids = set(c.station_id for c in completed_mappings)

    available_station_ids = [s for s in station_ids if s not in completed_station_ids]

    return {
        "station_ids": list(set(available_station_ids))
    }

@router.post("")
def confirm_onboarding(
    payload: OperatorOnboardingSubmit,
    db: Session = Depends(get_db),
    current_user: UserLogin = Depends(get_current_user)
):
    if current_user.role.role not in ["DC", "EDM"]:
        raise HTTPException(status_code=403, detail="Only DC/EDM can onboard operators.")

    # Find the pending mapping
    mapping = db.query(OperatorOnboarding).join(Operator).filter(
        OperatorOnboarding.station_id == payload.station_id,
        Operator.district_id == current_user.district_id,
        OperatorOnboarding.onboarding_status == "Mapped"
    ).first()

    if not mapping:
        # Check if the station is from an approved L2 request
        l2_req = db.query(L2RegistrationRequest).filter(
            L2RegistrationRequest.new_station_id == payload.station_id,
            L2RegistrationRequest.district_id == current_user.district_id
        ).order_by(L2RegistrationRequest.id.desc()).first()
        
        if l2_req and l2_req.status.upper() in ["APPROVED", "APPROVED_BY_CHIPS", "L2_DONE"]:
            # Find the operator from the L2 request
            operator = db.query(Operator).filter(
                Operator.user_code == l2_req.operator_id
            ).first()
            
            if not operator:
                raise HTTPException(status_code=404, detail="Operator associated with this L2 request is not activated or found.")
                
            # Create a new mapping record on the fly
            mapping = OperatorOnboarding(
                operator_id=operator.id,
                station_id=payload.station_id,
                onboarding_status="Mapped",
                ask_kit_working_status="Pending",
                permitted_18_plus="Pending",
                remark="Auto-mapped from L2 Request"
            )
            db.add(mapping)
            db.flush()
        else:
            raise HTTPException(status_code=404, detail="No pending operator mapping or approved L2 request found for this Station ID.")

    # Update onboarding history record
    mapping.onboarding_status = payload.onboarding_status
    mapping.ask_kit_working_status = payload.ask_kit_working_status
    mapping.permitted_18_plus = payload.permitted_18_plus
    mapping.remark = payload.remark

    db.commit()
    
    return {"status": "success", "message": "Operator onboarded successfully."}
