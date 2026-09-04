# backend/routers/dc_dashboard.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from backend.database import get_db
from backend.models import (
    OperatorActivationRequest,
    UserLogin as User,
    District,
    LMS,
    NSEITRequest,
    OperatorReactivationRequest,
    Candidate,
    StationIDRequest,
    L1RegistrationRequest,
    L2RegistrationRequest,
)
from backend.models.hold_candidate import HoldCandidate
from backend.models.base import StatusEnum

router = APIRouter(prefix="/dashboard", tags=["DC Dashboard"])


def _days_ago(dt_val):
    if not dt_val:
        return 9999
    try:
        now_date = datetime.now().date()
        if isinstance(dt_val, datetime):
            dt_date = dt_val.date()
        elif hasattr(dt_val, 'year'):
            dt_date = datetime(dt_val.year, dt_val.month, dt_val.day).date()
        else:
            dt_date = datetime.fromisoformat(str(dt_val).replace("T", " ")[:19]).date()
        return max(0, (now_date - dt_date).days)
    except Exception:
        return 9999


@router.get("/dc/{dc_id}")
def get_dc_dashboard_summary(
    dc_id: int,
    district_code: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Aggregated DC Dashboard single-payload endpoint."""
    user = db.query(User).filter(User.id == dc_id).first()
    dist_code = district_code or (user.district_id if user else None)
    
    district_name = "your district"
    if dist_code:
        d_obj = db.query(District).filter(District.district_code == str(dist_code)).first()
        if d_obj:
            district_name = d_obj.district_name

    # Helper filter for district-scoped workflows
    def apply_dist_dc_filter(query, model):
        if dist_code:
            return query.filter((model.district_id == str(dist_code)) | (model.dc_id == dc_id))
        return query.filter(model.dc_id == dc_id)

    # 1. LMS Candidates
    lms_query = db.query(LMS, Candidate, District.district_name)\
        .join(Candidate, LMS.request_id == Candidate.id)\
        .outerjoin(District, Candidate.district == District.district_code)\
        .filter(LMS.status_id != StatusEnum.SKIPPED.value)
    if dist_code:
        lms_query = lms_query.filter(Candidate.district == str(dist_code))
    lms_rows = lms_query.all() if dist_code else []
    
    lms_requests = []
    for lms, cand, dname in lms_rows:
        lms_requests.append({
            "name": cand.name if cand else "",
            "district": dname or district_name,
            "status": (lms.status or "Pending").strip(),
            "submitted_days_ago": _days_ago(lms.created_at),
            "created_at": lms.created_at.isoformat() if lms.created_at else None,
            "lms_id": getattr(cand, "lms_id", "") or "",
        })

    # 2. NSEIT Candidates
    nseit_query = db.query(NSEITRequest, Candidate, District.district_name)\
        .join(Candidate, NSEITRequest.request_id == Candidate.id)\
        .outerjoin(District, Candidate.district == District.district_code)\
        .filter(NSEITRequest.status_id != StatusEnum.SKIPPED.value)
    if dist_code:
        nseit_query = nseit_query.filter(Candidate.district == str(dist_code))
    nseit_rows = nseit_query.all() if dist_code else []

    nseit_requests = []
    for nseit, cand, dname in nseit_rows:
        nseit_requests.append({
            "name": cand.name if cand else "",
            "district": dname or district_name,
            "status": (nseit.status or "Pending").strip(),
            "submitted_days_ago": _days_ago(nseit.created_at),
            "created_at": nseit.created_at.isoformat() if nseit.created_at else None,
            "nseit_id": getattr(cand, "nseit_id", "") or "",
        })

    # 3. Selection Candidates (Active Candidates + Hold Candidates)
    cand_requests = []
    if dist_code:
        cand_rows = db.query(Candidate, District.district_name)\
            .outerjoin(District, Candidate.district == District.district_code)\
            .filter(Candidate.district == str(dist_code)).all()
        for r, dname in cand_rows:
            cand_requests.append({
                "name": r.name or getattr(r, "candidate_name", "") or "",
                "label": getattr(r, "request_code", None) or r.name or (f"#{r.id}" if r.id else "Request"),
                "district": dname or district_name,
                "status": (r.status or "PENDING").strip() if hasattr(r, "status") else "PENDING",
                "submitted_days_ago": _days_ago(r.created_at),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "revert_reason": getattr(r, "hold_remark", None) or getattr(r, "reject_reason", "") or "",
            })

        hold_rows = db.query(HoldCandidate, District.district_name)\
            .outerjoin(District, HoldCandidate.district == District.district_code)\
            .filter(HoldCandidate.district == str(dist_code)).all()
        for r, dname in hold_rows:
            cand_requests.append({
                "name": r.name or "",
                "label": getattr(r, "request_code", None) or r.name or (f"#{r.id}" if r.id else "Request"),
                "district": dname or district_name,
                "status": "ON_HOLD",
                "submitted_days_ago": _days_ago(r.created_at),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "revert_reason": getattr(r, "hold_remark", "") or "",
            })

    # 4. Operator Activation Requests
    act_query = db.query(OperatorActivationRequest, District.district_name)\
        .outerjoin(District, OperatorActivationRequest.district_id == District.district_code)
    act_query = apply_dist_dc_filter(act_query, OperatorActivationRequest)
    act_rows = act_query.all()

    activation_requests = []
    for r, dname in act_rows:
        label = r.name_as_per_aadhaar or r.operator_name or (f"#{r.id}" if r.id else "Request")
        activation_requests.append({
            "name": r.name_as_per_aadhaar or r.operator_name or "",
            "label": label,
            "district": dname or district_name,
            "status": (r.status or "pending").strip().lower(),
            "submitted_days_ago": _days_ago(r.submitted_at),
            "created_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "revert_reason": getattr(r, "revert_reason", None) or getattr(r, "reject_reason", "") or "",
        })

    # 5. Operator Reactivation Requests
    react_query = db.query(OperatorReactivationRequest, District.district_name)\
        .outerjoin(District, OperatorReactivationRequest.district_id == District.district_code)
    react_query = apply_dist_dc_filter(react_query, OperatorReactivationRequest)
    react_rows = react_query.all()

    reactivation_requests = []
    for r, dname in react_rows:
        dist = dname or district_name
        req_code = getattr(r, "request_code", None) or (f"#{r.id}" if r.id else "Batch")
        created = getattr(r, "created_at", None)
        ops = getattr(r, "operators", None)
        if ops and isinstance(ops, list) and len(ops) > 0:
            for op in ops:
                op_status = str(getattr(op, "status", None) or r.status or "PENDING").strip().upper()
                reactivation_requests.append({
                    "id": getattr(op, "id", None) or r.id,
                    "district": dist,
                    "label": req_code,
                    "status": op_status,
                    "submitted_days_ago": _days_ago(created),
                    "created_at": created.isoformat() if isinstance(created, datetime) else created,
                    "operator_count": 1,
                    "revert_reason": getattr(op, "reject_reason", None) or getattr(r, "revert_reason", None) or getattr(r, "reject_reason", "") or "",
                })
        else:
            reactivation_requests.append({
                "id": r.id,
                "district": dist,
                "label": req_code,
                "status": (r.status or "PENDING").strip().upper(),
                "submitted_days_ago": _days_ago(created),
                "created_at": created.isoformat() if isinstance(created, datetime) else created,
                "operator_count": getattr(r, "operator_count", 1) or 1,
                "revert_reason": getattr(r, "revert_reason", None) or getattr(r, "reject_reason", "") or "",
            })

    # 6. Station ID Requests
    station_query = db.query(StationIDRequest, District.district_name)\
        .outerjoin(District, StationIDRequest.district_id == District.district_code)
    station_query = apply_dist_dc_filter(station_query, StationIDRequest)
    station_rows = station_query.all()

    station_id_requests = []
    for r, dname in station_rows:
        label = getattr(r, "station_id", None) or getattr(r, "station_id_inserted", None) or (f"#{r.id}" if r.id else "Request")
        kits_cnt = r.number_of_kits if r.number_of_kits else 1
        station_id_requests.append({
            "district": dname or district_name,
            "status": (r.status or "pending").strip().lower(),
            "submitted_days_ago": _days_ago(r.submitted_at),
            "created_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "label": label,
            "number_of_kits": kits_cnt,
            "operator_count": kits_cnt,
            "revert_reason": getattr(r, "revert_reason", None) or getattr(r, "reject_reason", "") or "",
        })

    # 7. L1 Registration Requests
    l1_query = db.query(L1RegistrationRequest, District.district_name)\
        .outerjoin(District, L1RegistrationRequest.district_id == District.district_code)
    l1_query = apply_dist_dc_filter(l1_query, L1RegistrationRequest)
    l1_rows = l1_query.all()

    l1_requests = []
    for r, dname in l1_rows:
        label = getattr(r, "request_code", None) or (f"#{r.id}" if r.id else "Request")
        is_done = getattr(r, "status_id", None) in [StatusEnum.L1_DONE.value, StatusEnum.APPROVED.value] or str(r.status or "").lower() in ["l1_done", "approved", "done"]
        l1_status = "approved" if is_done else ((r.status or "pending").strip().lower())
        l1_requests.append({
            "district": dname or district_name,
            "status": l1_status,
            "submitted_days_ago": _days_ago(r.created_at),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "label": label,
            "revert_reason": getattr(r, "revert_reason", None) or getattr(r, "reject_reason", "") or "",
        })

    # Add Awaiting L1: Allotted station IDs in this district with no L1 request yet
    allotted_query = db.query(StationIDRequest).filter(
        StationIDRequest.status_id == StatusEnum.ALLOTTED.value,
        StationIDRequest.station_id_inserted.isnot(None),
    )
    allotted_query = apply_dist_dc_filter(allotted_query, StationIDRequest)
    allotted_stations = allotted_query.all()
    existing_l1_stations = {
        (s.station_id or "").strip()
        for s in db.query(L1RegistrationRequest.station_id).all()
    }
    for r in allotted_stations:
        for sid in str(r.station_id_inserted or "").split(","):
            sid = sid.strip()
            if sid and sid not in existing_l1_stations:
                l1_requests.append({
                    "district": district_name,
                    "status": "awaiting_l1",
                    "submitted_days_ago": _days_ago(r.reviewed_at),
                    "created_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
                    "label": f"Awaiting L1 ({sid})",
                    "revert_reason": ""
                })

    # 8. L2 Registration Requests
    l2_query = db.query(L2RegistrationRequest, District.district_name)\
        .outerjoin(District, L2RegistrationRequest.district_id == District.district_code)
    l2_query = apply_dist_dc_filter(l2_query, L2RegistrationRequest)
    l2_rows = l2_query.all()

    l2_requests = []
    for r, dname in l2_rows:
        label = getattr(r, "request_no", None) or getattr(r, "new_station_id", None) or (f"#{r.id}" if r.id else "Request")
        st_lower = str(r.status or "pending").strip().lower()
        st_id = getattr(r, "status_id", None)
        
        if st_id in [StatusEnum.APPROVED.value, StatusEnum.L2_DONE.value, 20, 2] or st_lower in ["approved", "activated", "l2_done", "l2 done", "done"]:
            l2_status = "approved"
        elif st_id in [StatusEnum.SENT_TO_UIDAI.value, 6] or st_lower in ["sent_to_uidai", "sent to uidai"]:
            l2_status = "sent_to_uidai"
        elif st_id in [StatusEnum.REVERTED.value, 3] or st_lower in ["reverted", "reverted_by_chips", "reverted by chips", "revert_back"]:
            l2_status = "reverted"
        elif st_id in [StatusEnum.REJECTED.value, 14] or st_lower in ["rejected", "rejected_by_uidai"]:
            l2_status = "rejected"
        else:
            l2_status = "pending"

        l2_requests.append({
            "district": dname or district_name,
            "status": l2_status,
            "submitted_days_ago": _days_ago(r.submitted_at),
            "created_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "label": label,
            "revert_reason": getattr(r, "revert_reason", None) or getattr(r, "reject_reason", "") or "",
        })

    # Add Awaiting L2: L1 Done stations in this district with no L2 request yet
    done_l1_query = db.query(L1RegistrationRequest).filter(
        L1RegistrationRequest.status_id.in_([StatusEnum.L1_DONE.value, StatusEnum.APPROVED.value])
    )
    done_l1_query = apply_dist_dc_filter(done_l1_query, L1RegistrationRequest)
    done_l1_rows = done_l1_query.all()
    existing_l2_stations = {
        (s.new_station_id or "").strip()
        for s in db.query(L2RegistrationRequest.new_station_id).all()
    }
    for r in done_l1_rows:
        sid = (r.station_id or "").strip()
        if sid and sid not in existing_l2_stations:
            l2_requests.append({
                "district": district_name,
                "status": "awaiting_l2",
                "submitted_days_ago": _days_ago(r.updated_at or r.created_at),
                "created_at": (r.updated_at or r.created_at).isoformat() if (r.updated_at or r.created_at) else None,
                "label": f"Awaiting L2 ({sid})",
                "revert_reason": ""
            })

    return {
        "districts": [district_name] if district_name else [],
        "district_name": district_name,
        "cand_requests": cand_requests,
        "lms_requests": lms_requests,
        "nseit_requests": nseit_requests,
        "activation_requests": activation_requests,
        "reactivation_requests": reactivation_requests,
        "station_id_requests": station_id_requests,
        "l1_requests": l1_requests,
        "l2_requests": l2_requests,
    }
