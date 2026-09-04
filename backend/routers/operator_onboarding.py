from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from pydantic import BaseModel
from sqlalchemy import or_
from datetime import date

from backend.database import get_db
from backend.models.user_login import UserLogin
from backend.models.operator import Operator
from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
from backend.models.operator_station_mapping import OperatorStationMapping
from backend.models.kit_registration import KitRegistration
from backend.models.l2_registration import L2RegistrationRequest
from backend.utils.district_mapper import get_district_search_terms
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
    """Returns Station IDs that are mapped to an operator and not yet onboarded (Pending/Mapped)."""
    if current_user.role.role not in ["DC", "EDM"]:
        raise HTTPException(status_code=403, detail="Only DC/EDM can fetch these options.")

    d_code = str(current_user.district_id).strip() if current_user.district_id else ""
    d_name = current_user.district.district_name.strip() if current_user.district else ""
    search_terms = get_district_search_terms(d_name, d_code)

    # 1. District station IDs from KitRegistration
    district_station_ids = set()
    try:
        kit_conds = [KitRegistration.district.ilike(f"%{t}%") for t in search_terms if t]
        if kit_conds:
            for k in db.query(KitRegistration).filter(or_(*kit_conds)).all():
                if k.station_id and str(k.station_id).strip():
                    district_station_ids.add(str(k.station_id).strip())
    except Exception:
        pass

    # 2. Completed station IDs (already onboarded)
    completed_station_ids = set()
    try:
        for r in db.query(OperatorOnboardingDetail).filter(
            OperatorOnboardingDetail.onboarding_status == "Completed"
        ).all():
            if r.station_id:
                completed_station_ids.add(str(r.station_id).strip())
    except Exception:
        pass

    mapped_station_ids = set()

    # 3. From OperatorOnboardingDetail (Mapped / Pending status)
    try:
        detail_conds = [
            Operator.mapped_dc_id == current_user.id,
        ]
        if d_code:
            detail_conds.append(Operator.district_id == d_code)
        if district_station_ids:
            detail_conds.append(OperatorOnboardingDetail.station_id.in_(district_station_ids))

        pending_details = db.query(OperatorOnboardingDetail).join(Operator).filter(
            or_(*detail_conds),
            OperatorOnboardingDetail.onboarding_status != "Completed"
        ).all()

        for r in pending_details:
            if r.station_id and str(r.station_id).strip():
                mapped_station_ids.add(str(r.station_id).strip())
    except Exception:
        pass

    # 4. From OperatorStationMapping
    try:
        mapping_conds = [
            Operator.mapped_dc_id == current_user.id,
        ]
        if d_code:
            mapping_conds.append(Operator.district_id == d_code)
        if district_station_ids:
            mapping_conds.append(OperatorStationMapping.station_id.in_(district_station_ids))

        st_mappings = db.query(OperatorStationMapping).join(Operator).filter(
            or_(*mapping_conds)
        ).all()

        for m in st_mappings:
            if m.station_id and str(m.station_id).strip():
                mapped_station_ids.add(str(m.station_id).strip())
    except Exception:
        pass

    # 5. From approved L2 registration requests
    try:
        l2_conds = []
        if d_code:
            l2_conds.append(L2RegistrationRequest.district_id == d_code)
        l2_conds.append(L2RegistrationRequest.dc_id == current_user.id)

        l2_reqs = db.query(L2RegistrationRequest).filter(or_(*l2_conds)).all()
        for req in l2_reqs:
            if req.new_station_id and req.status.upper() in ["APPROVED", "APPROVED_BY_CHIPS", "L2_DONE"]:
                mapped_station_ids.add(str(req.new_station_id).strip())
    except Exception:
        pass

    available_station_ids = sorted([
        sid for sid in mapped_station_ids if sid and sid not in completed_station_ids
    ])

    return {
        "station_ids": available_station_ids
    }

@router.post("")
def confirm_onboarding(
    payload: OperatorOnboardingSubmit,
    db: Session = Depends(get_db),
    current_user: UserLogin = Depends(get_current_user)
):
    if current_user.role.role not in ["DC", "EDM"]:
        raise HTTPException(status_code=403, detail="Only DC/EDM can onboard operators.")

    d_code = str(current_user.district_id).strip() if current_user.district_id else ""
    sid = payload.station_id.strip()

    # Find the mapping record
    mapping = db.query(OperatorOnboardingDetail).filter(
        OperatorOnboardingDetail.station_id == sid
    ).first()

    if not mapping:
        # Check OperatorStationMapping
        st_map = db.query(OperatorStationMapping).filter(
            OperatorStationMapping.station_id == sid
        ).first()

        if st_map:
            mapping = OperatorOnboardingDetail(
                mapping_id=st_map.id,
                operator_id=st_map.operator_id,
                station_id=sid,
                onboarding_status=payload.onboarding_status,
                ask_kit_working_status=payload.ask_kit_working_status,
                permitted_18_plus=payload.permitted_18_plus,
                remark=payload.remark,
                onboard_date=date.today() if payload.onboarding_status == "Completed" else None
            )
            db.add(mapping)
        else:
            # Check if the station is from an approved L2 request
            l2_conds = [L2RegistrationRequest.new_station_id == sid]
            if d_code:
                l2_conds.append(L2RegistrationRequest.district_id == d_code)
            l2_req = db.query(L2RegistrationRequest).filter(
                *l2_conds
            ).order_by(L2RegistrationRequest.id.desc()).first()

            if l2_req and l2_req.status.upper() in ["APPROVED", "APPROVED_BY_CHIPS", "L2_DONE"]:
                operator = db.query(Operator).filter(
                    Operator.user_code == l2_req.operator_id
                ).first()

                if not operator:
                    raise HTTPException(status_code=404, detail="Operator associated with this L2 request is not activated or found.")

                station_map = OperatorStationMapping(
                    operator_id=operator.id,
                    station_id=sid
                )
                db.add(station_map)
                db.flush()

                mapping = OperatorOnboardingDetail(
                    mapping_id=station_map.id,
                    operator_id=operator.id,
                    station_id=sid,
                    onboarding_status=payload.onboarding_status,
                    ask_kit_working_status=payload.ask_kit_working_status,
                    permitted_18_plus=payload.permitted_18_plus,
                    remark=payload.remark,
                    onboard_date=date.today() if payload.onboarding_status == "Completed" else None
                )
                db.add(mapping)
            else:
                raise HTTPException(status_code=404, detail="No operator mapping found for this Station ID.")
    else:
        # Update existing record
        mapping.onboarding_status = payload.onboarding_status
        mapping.ask_kit_working_status = payload.ask_kit_working_status
        mapping.permitted_18_plus = payload.permitted_18_plus
        mapping.remark = payload.remark
        if payload.onboarding_status == "Completed":
            mapping.onboard_date = date.today()

    db.commit()

    return {"status": "success", "message": "Operator onboarded successfully."}
