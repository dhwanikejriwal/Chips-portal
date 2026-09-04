from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
from sqlalchemy import or_

from backend.database import get_db
from backend.models.user_login import UserLogin
from backend.models.operator import Operator
from backend.models.station_id import StationIDRequest
from backend.models.kit_registration import KitRegistration
from backend.models.l1_registration import L1RegistrationRequest
from backend.models.l2_registration import L2RegistrationRequest
from backend.models.operator_onboarding_detail import OperatorOnboardingDetail
from backend.models.operator_station_mapping import OperatorStationMapping
from backend.models.operator_activation import OperatorActivationRequest
from backend.models.reactivation import ReactivationOperator
from backend.models.base import StatusEnum
from backend.routers.auth import get_current_user

router = APIRouter(
    prefix="/dc/operator-mapping",
    tags=["operator_mapping"],
)

from backend.utils.district_mapper import normalize_district_name, DISTRICT_ALIAS_MAP

def get_district_search_terms(district_name: str | None, district_code: str | None) -> set:
    terms = set()
    if district_code:
        terms.add(str(district_code).strip())
    if district_name:
        clean_name = district_name.strip()
        norm = normalize_district_name(clean_name)
        terms.add(clean_name)
        if norm:
            terms.add(norm)
        # Find all variants in centralized DISTRICT_ALIAS_MAP that match
        for alias_key, standard_name in DISTRICT_ALIAS_MAP.items():
            if standard_name.lower() == norm.lower() or standard_name.lower() == clean_name.lower():
                terms.add(alias_key)
                terms.add(standard_name)
    return terms


class OperatorMappingCreate(BaseModel):
    station_id: str
    operator_id: int


@router.get("/options")
def get_mapping_options(
    db: Session = Depends(get_db),
    current_user: UserLogin = Depends(get_current_user)
) -> Dict[str, Any]:
    """Returns unmapped operators and all allotted unmapped station IDs for the DC's district."""
    if current_user.role.role not in ["DC", "EDM"]:
        raise HTTPException(status_code=403, detail="Only DC/EDM can fetch these options.")

    d_code = str(current_user.district_id).strip() if current_user.district_id else ""
    d_name = current_user.district.district_name.strip() if current_user.district else ""
    search_terms = get_district_search_terms(d_name, d_code)

    # 1. Sync approved OperatorActivationRequest records into Operator table safely
    try:
        act_query = db.query(OperatorActivationRequest).filter(
            or_(
                OperatorActivationRequest.dc_id == current_user.id,
                OperatorActivationRequest.district_id == d_code
            ),
            or_(
                OperatorActivationRequest.status_id == StatusEnum.APPROVED.value,
                OperatorActivationRequest.status_id == 2
            )
        )
        for req in act_query.all():
            op = None
            if req.user_code:
                op = db.query(Operator).filter(Operator.user_code == req.user_code).first()
            if not op and req.operator_mobile:
                op = db.query(Operator).filter(Operator.mobile == req.operator_mobile).first()
            if not op and req.name_as_per_aadhaar and req.operator_aadhaar:
                op = db.query(Operator).filter(
                    Operator.name == req.name_as_per_aadhaar,
                    Operator.aadhaar_last4 == req.operator_aadhaar
                ).first()

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
                    district_id=d_code
                )
                db.add(op)
            else:
                if not op.mapped_dc_id:
                    op.mapped_dc_id = current_user.id
                if not op.district_id:
                    op.district_id = d_code
                if (op.status or "").lower() == "suspended":
                    op.status = "Inactive"
        db.commit()
    except Exception:
        db.rollback()

    # 2. Sync approved ReactivationOperator records safely
    try:
        approved_reactivations = db.query(ReactivationOperator).filter(
            or_(
                ReactivationOperator.dc_id == current_user.id,
                ReactivationOperator.district_id == d_code
            ),
            or_(
                ReactivationOperator.status_id == StatusEnum.APPROVED.value,
                ReactivationOperator.status_id == 2
            )
        ).all()

        for r_op in approved_reactivations:
            op_rec = None
            if r_op.user_code:
                op_rec = db.query(Operator).filter(Operator.user_code == r_op.user_code).first()
            if not op_rec and r_op.mobile:
                op_rec = db.query(Operator).filter(Operator.mobile == r_op.mobile).first()

            if op_rec:
                if not op_rec.mapped_dc_id:
                    op_rec.mapped_dc_id = current_user.id
                if not op_rec.district_id:
                    op_rec.district_id = d_code
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
                    district_id=d_code
                )
                db.add(new_op)
        db.commit()
    except Exception:
        db.rollback()

    # 3. Gather all currently mapped station IDs and mapped operator IDs
    mapped_st_ids = set()
    mapped_op_ids = set()

    try:
        for r in db.query(OperatorOnboardingDetail).all():
            status = (r.onboarding_status or "").strip().lower()
            if status not in ["inactive", "unmapped", "removed"]:
                if r.station_id:
                    mapped_st_ids.add(str(r.station_id).strip())
                if r.operator_id:
                    mapped_op_ids.add(r.operator_id)
    except Exception:
        pass

    try:
        for m in db.query(OperatorStationMapping).all():
            if m.station_id:
                mapped_st_ids.add(str(m.station_id).strip())
            if m.operator_id:
                mapped_op_ids.add(m.operator_id)
    except Exception:
        pass

    # 4. Gather ALL allotted station IDs for this DC/district
    station_ids_set = set()

    # A. From KitRegistration (master tracker for all allotted stations)
    try:
        kit_conditions = [KitRegistration.district.ilike(f"%{term}%") for term in search_terms if term]
        if kit_conditions:
            kits = db.query(KitRegistration).filter(or_(*kit_conditions)).all()
            for k in kits:
                if k.station_id and str(k.station_id).strip():
                    station_ids_set.add(str(k.station_id).strip())
    except Exception:
        pass

    # B. From StationIDRequest
    try:
        sid_query = db.query(StationIDRequest).filter(
            or_(
                StationIDRequest.dc_id == current_user.id,
                StationIDRequest.district_id == d_code
            ),
            or_(
                StationIDRequest.status_id == StatusEnum.ALLOTTED.value,
                StationIDRequest.status_id == 18,
                StationIDRequest.station_id_inserted.isnot(None)
            )
        )
        for s in sid_query.all():
            if s.station_id_inserted:
                for sid in str(s.station_id_inserted).split(","):
                    clean_sid = sid.strip()
                    if clean_sid:
                        station_ids_set.add(clean_sid)
    except Exception:
        pass

    # C. From L1RegistrationRequest & L2RegistrationRequest
    try:
        l1_reqs = db.query(L1RegistrationRequest).filter(
            or_(L1RegistrationRequest.district_id == d_code, L1RegistrationRequest.dc_id == current_user.id)
        ).all()
        for l1 in l1_reqs:
            if l1.station_id and l1.station_id.strip():
                station_ids_set.add(l1.station_id.strip())
    except Exception:
        pass

    try:
        l2_reqs = db.query(L2RegistrationRequest).filter(
            or_(L2RegistrationRequest.district_id == d_code, L2RegistrationRequest.dc_id == current_user.id)
        ).all()
        for l2 in l2_reqs:
            if l2.new_station_id and l2.new_station_id.strip():
                station_ids_set.add(l2.new_station_id.strip())
    except Exception:
        pass

    # Available allotted station IDs (not already mapped)
    available_station_ids = sorted([s for s in station_ids_set if s not in mapped_st_ids])

    # 5. Fetch operators for this DC/district that are not mapped and not suspended/resigned
    available_operators = []
    try:
        op_query = db.query(Operator).filter(
            or_(
                Operator.mapped_dc_id == current_user.id,
                Operator.district_id == d_code
            ),
            ~Operator.status.ilike("%suspended%"),
            ~Operator.status.ilike("%resigned%")
        ).order_by(Operator.name.asc())

        for op in op_query.all():
            if op.id not in mapped_op_ids:
                # Format mobile nicely
                mob_str = str(op.mobile or "")
                if mob_str.endswith(".0"):
                    mob_str = mob_str[:-2]
                op_text = f"{op.name} || {mob_str}" if mob_str else op.name
                if op.user_code:
                    op_text += f" || {op.user_code}"

                available_operators.append({
                    "id": op.id,
                    "text": op_text
                })
    except Exception:
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

    d_code = str(current_user.district_id).strip() if current_user.district_id else ""

    # Find the operator
    operator = db.query(Operator).filter(
        Operator.id == payload.operator_id,
        or_(
            Operator.mapped_dc_id == current_user.id,
            Operator.district_id == d_code
        )
    ).first()

    if not operator:
        # Fallback search by id if belonging to this district
        operator = db.query(Operator).filter(Operator.id == payload.operator_id).first()
        if not operator:
            raise HTTPException(status_code=404, detail="Operator not found.")

    existing_mapping = db.query(OperatorOnboardingDetail).filter(
        OperatorOnboardingDetail.operator_id == operator.id
    ).first()
    if existing_mapping:
        raise HTTPException(status_code=400, detail="Operator is already mapped to a station.")

    existing_station_mapping = db.query(OperatorOnboardingDetail).filter(
        OperatorOnboardingDetail.station_id == payload.station_id
    ).first()
    if existing_station_mapping:
        raise HTTPException(status_code=400, detail="This Station ID is already mapped to another operator.")

    # 1. Create OperatorStationMapping record
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

    # Update operator status and association
    operator.status = "Active"
    operator.mapped_dc_id = current_user.id
    if d_code and not operator.district_id:
        operator.district_id = d_code

    db.commit()

    return {"status": "success", "message": "Operator mapped successfully."}


@router.get("")
def list_mappings(
    db: Session = Depends(get_db),
    current_user: UserLogin = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    if current_user.role.role not in ["DC", "EDM"]:
        raise HTTPException(status_code=403, detail="Only DC/EDM can view mappings.")

    d_code = str(current_user.district_id).strip() if current_user.district_id else ""
    d_name = current_user.district.district_name.strip() if current_user.district else ""
    search_terms = get_district_search_terms(d_name, d_code)

    # Get all station IDs for this district to catch mappings where operator district_id was previously unset
    district_station_ids = set()
    try:
        kit_conditions = [KitRegistration.district.ilike(f"%{term}%") for term in search_terms if term]
        if kit_conditions:
            for k in db.query(KitRegistration).filter(or_(*kit_conditions)).all():
                if k.station_id:
                    district_station_ids.add(str(k.station_id).strip())
    except Exception:
        pass

    # Fetch operators that are mapped to a station for this DC/district
    query_conditions = [
        Operator.mapped_dc_id == current_user.id,
    ]
    if d_code:
        query_conditions.append(Operator.district_id == d_code)
    if district_station_ids:
        query_conditions.append(OperatorOnboardingDetail.station_id.in_(district_station_ids))

    mappings = db.query(OperatorOnboardingDetail).join(Operator).filter(
        or_(*query_conditions)
    ).order_by(OperatorOnboardingDetail.id.desc()).all()

    results = []
    seen_ops = set()
    for m in mappings:
        op = m.operator
        if not op or op.id in seen_ops:
            continue
        seen_ops.add(op.id)

        mob_str = str(op.mobile or "")
        if mob_str.endswith(".0"):
            mob_str = mob_str[:-2]
        op_text = f"{op.name} || {mob_str}" if mob_str else op.name
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

    d_code = str(current_user.district_id).strip() if current_user.district_id else ""

    operator = db.query(Operator).filter(
        Operator.id == operator_id,
        or_(
            Operator.mapped_dc_id == current_user.id,
            Operator.district_id == d_code
        )
    ).first()

    if not operator:
        # Fallback check
        operator = db.query(Operator).filter(Operator.id == operator_id).first()
        if not operator:
            raise HTTPException(status_code=404, detail="Operator not found.")

    # Delete OperatorOnboardingDetail record(s)
    mappings = db.query(OperatorOnboardingDetail).filter(
        OperatorOnboardingDetail.operator_id == operator_id
    ).all()
    st_ids = [m.station_id for m in mappings if m.station_id]
    for mapping in mappings:
        db.delete(mapping)

    # Delete OperatorStationMapping record(s)
    st_mappings = db.query(OperatorStationMapping).filter(
        or_(
            OperatorStationMapping.operator_id == operator_id,
            OperatorStationMapping.station_id.in_(st_ids) if st_ids else False
        )
    ).all()
    for sm in st_mappings:
        db.delete(sm)

    valid_reasons = {"Inactive", "Suspended", "Resigned"}
    if reason not in valid_reasons:
        reason = "Inactive"

    operator.status = reason
    operator.mapped_dc_id = current_user.id
    if d_code:
        operator.district_id = d_code

    db.commit()
    return {"status": "success", "message": "Mapping removed.", "new_status": reason}
