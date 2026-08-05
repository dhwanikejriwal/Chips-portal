from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user_login import UserLogin
from backend.models.operator import Operator
from backend.models.station_id import StationIDRequest
from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
from backend.models.operator_station_mapping import OperatorStationMapping
from backend.routers.auth import get_current_user

from sqlalchemy import or_
from backend.models.operator_activation import OperatorActivationRequest
from backend.models.base import StatusEnum
from backend.routers.operator_activation import upsert_operator_from_request

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

    # 1. Sync approved OperatorActivationRequest records into Operator table safely
    try:
        approved_requests = db.query(OperatorActivationRequest).filter(
            or_(
                OperatorActivationRequest.dc_id == current_user.id,
                OperatorActivationRequest.district_id == current_user.district_id
            ),
            OperatorActivationRequest.status_id == StatusEnum.APPROVED.value
        ).all()

        for req in approved_requests:
            if req.user_code:
                op = db.query(Operator).filter(Operator.user_code == req.user_code).first()
                if not op:
                    op = Operator(
                        name=req.name_as_per_aadhaar,
                        mobile=req.operator_mobile,
                        email=req.primary_email,
                        user_code=req.user_code,
                        role=req.role,
                        registrar_code=req.registrar_code,
                        ea_code=req.ea_code,
                        nseit_certificate_number=req.nseit_certificate_number,
                        aadhaar_last4=req.operator_aadhaar,
                        status="Inactive",
                        mapped_dc_id=current_user.id,
                        district_id=current_user.district_id
                    )
                    db.add(op)
        db.commit()
    except Exception as ex:
        db.rollback()

    # 2. Sync approved ReactivationOperator records safely
    try:
        from backend.models.reactivation import ReactivationOperator
        approved_reactivation = db.query(ReactivationOperator).filter(
            or_(
                ReactivationOperator.dc_id == current_user.id,
                ReactivationOperator.district_id == current_user.district_id
            ),
            ReactivationOperator.status_id == StatusEnum.APPROVED.value
        ).all()

        for r_op in approved_reactivation:
            op_rec = None
            if r_op.user_code:
                op_rec = db.query(Operator).filter(Operator.user_code == r_op.user_code).first()
            if not op_rec and r_op.name and r_op.mobile:
                op_rec = db.query(Operator).filter(Operator.name == r_op.name, Operator.mobile == r_op.mobile).first()

            if op_rec:
                if (op_rec.status or "").lower() == "suspended":
                    op_rec.status = "Inactive"
            else:
                new_op = Operator(
                    name=r_op.name,
                    mobile=r_op.mobile,
                    email=r_op.email,
                    user_code=r_op.user_code,
                    role=r_op.role,
                    registrar_code=r_op.registrar_code,
                    ea_code=r_op.ea_code,
                    nseit_certificate_number=r_op.nseit_certificate_number,
                    aadhaar_last4=r_op.aadhaar_last4,
                    status="Inactive",
                    mapped_dc_id=current_user.id,
                    district_id=current_user.district_id
                )
                db.add(new_op)
        db.commit()
    except Exception as ex:
        db.rollback()

    # 3. Gather station IDs for this DC/district
    station_ids_set = set()

    # From StationIDRequest
    try:
        approved_stations = db.query(StationIDRequest).filter(
            or_(
                StationIDRequest.district_id == current_user.district_id,
                StationIDRequest.dc_id == current_user.id
            ),
            StationIDRequest.station_id_inserted.isnot(None)
        ).all()
        for s in approved_stations:
            if s.station_id_inserted:
                for sid in s.station_id_inserted.split(','):
                    if sid.strip():
                        station_ids_set.add(sid.strip())
    except Exception:
        pass

    # From L1RegistrationRequest
    try:
        from backend.models.l1_registration import L1RegistrationRequest
        l1_reqs = db.query(L1RegistrationRequest).filter(
            or_(
                L1RegistrationRequest.district_id == current_user.district_id,
                L1RegistrationRequest.dc_id == current_user.id
            )
        ).all()
        for l1 in l1_reqs:
            if l1.station_id and l1.station_id.strip():
                station_ids_set.add(l1.station_id.strip())
    except Exception:
        pass

    # From L2RegistrationRequest
    try:
        from backend.models.l2_registration import L2RegistrationRequest
        l2_reqs = db.query(L2RegistrationRequest).filter(
            or_(
                L2RegistrationRequest.district_id == current_user.district_id,
                L2RegistrationRequest.dc_id == current_user.id
            )
        ).all()
        for l2 in l2_reqs:
            if l2.new_station_id and l2.new_station_id.strip():
                station_ids_set.add(l2.new_station_id.strip())
    except Exception:
        pass

    # 4. Gather mapped operator IDs and mapped station IDs
    mapped_op_ids = set()
    mapped_st_ids = set()

    try:
        onboarded_records = db.query(OperatorOnboardingDetail).all()
        for r in onboarded_records:
            if r.operator_id:
                mapped_op_ids.add(r.operator_id)
            if r.station_id:
                mapped_st_ids.add(r.station_id)
    except Exception:
        pass

    try:
        st_mappings = db.query(OperatorStationMapping).all()
        for m in st_mappings:
            if m.operator_id:
                mapped_op_ids.add(m.operator_id)
            if m.station_id:
                mapped_st_ids.add(m.station_id)
    except Exception:
        pass

    # Available station IDs (unmapped)
    available_station_ids = sorted([s for s in station_ids_set if s not in mapped_st_ids])

    # 5. Fetch operators for this DC/district that are not suspended and not mapped
    available_operators = []
    try:
        op_query = db.query(Operator).filter(
            or_(
                Operator.mapped_dc_id == current_user.id,
                Operator.district_id == current_user.district_id
            ),
            ~Operator.status.ilike("%suspended%")
        )
        all_ops = op_query.all()
        for op in all_ops:
            if op.id not in mapped_op_ids:
                op_text = f"{op.name} || {op.mobile}"
                if op.user_code:
                    op_text += f" || {op.user_code}"
                available_operators.append({
                    "id": op.id,
                    "text": op_text
                })
    except Exception as e:
        pass

    return {
        "station_ids": available_station_ids,
        "operators": available_operators
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
        or_(
            Operator.mapped_dc_id == current_user.id,
            Operator.district_id == current_user.district_id
        )
    ).first()

    if not operator:
        raise HTTPException(status_code=404, detail="Operator not found.")

    existing_mapping = db.query(OperatorOnboardingDetail).filter(OperatorOnboardingDetail.operator_id == operator.id).first()
    if existing_mapping:
        raise HTTPException(status_code=400, detail="Operator is already mapped to a station.")

    existing_station_mapping = db.query(OperatorOnboardingDetail).filter(OperatorOnboardingDetail.station_id == payload.station_id).first()
    if existing_station_mapping:
        raise HTTPException(status_code=400, detail="This Station ID is already mapped to another operator.")

    # 1. Create OperatorStationMapping record to satisfy mapping_id foreign key constraint
    station_mapping = OperatorStationMapping(
        operator_id=operator.id,
        station_id=payload.station_id
    )
    db.add(station_mapping)
    db.flush()

    # 2. Map the operator using OperatorOnboardingDetail referencing mapping_id
    new_mapping = OperatorOnboardingDetail(
        mapping_id=station_mapping.id,
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

    # Delete corresponding OperatorStationMapping record
    st_mappings = db.query(OperatorStationMapping).filter(OperatorStationMapping.operator_id == operator_id).all()
    for sm in st_mappings:
        db.delete(sm)

    valid_reasons = {"Inactive", "Suspended", "Resigned"}
    if reason not in valid_reasons:
        reason = "Inactive"

    operator.status = reason

    db.commit()
    return {"status": "success", "message": "Mapping removed.", "new_status": reason}
