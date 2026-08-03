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
        d_obj = db.query(District).filter(District.district_code == dist_code).first()
        if d_obj:
            district_name = d_obj.district_name

    # 1. LMS Candidates
    lms_rows = db.query(LMS, Candidate, District.district_name)\
        .join(Candidate, LMS.request_id == Candidate.id)\
        .outerjoin(District, Candidate.district == District.district_code)\
        .filter(Candidate.district == dist_code).all() if dist_code else []
    
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
    nseit_rows = db.query(NSEITRequest, Candidate, District.district_name)\
        .join(Candidate, NSEITRequest.request_id == Candidate.id)\
        .outerjoin(District, Candidate.district == District.district_code)\
        .filter(Candidate.district == dist_code).all() if dist_code else []

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

    # 3. Operator Activation Requests
    act_rows = db.query(OperatorActivationRequest, District.district_name)\
        .outerjoin(District, OperatorActivationRequest.district_id == District.district_code)\
        .filter(OperatorActivationRequest.dc_id == dc_id).all()

    activation_requests = []
    for r, dname in act_rows:
        label = r.name_as_per_aadhaar or r.operator_name or (f"#{r.id}" if r.id else "Request")
        activation_requests.append({
            "name": r.name_as_per_aadhaar or r.operator_name or "",
            "label": label,
            "district": dname or district_name,
            "status": (r.status or "sent_to_chips").strip().lower(),
            "submitted_days_ago": _days_ago(r.submitted_at),
            "created_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "revert_reason": getattr(r, "revert_reason", None) or getattr(r, "reject_reason", "") or "",
        })

    # 4. Operator Reactivation Requests
    react_rows = db.query(OperatorReactivationRequest, District.district_name)\
        .outerjoin(District, OperatorReactivationRequest.district_id == District.district_code).all()

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

    # 5. Selection Candidates
    cand_rows = db.query(Candidate, District.district_name)\
        .outerjoin(District, Candidate.district == District.district_code)\
        .filter(Candidate.district == dist_code).all() if dist_code else []

    cand_requests = []
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

    # 6. Station ID Requests
    station_rows = db.query(StationIDRequest, District.district_name)\
        .outerjoin(District, StationIDRequest.district_id == District.district_code)\
        .filter(StationIDRequest.dc_id == dc_id).all()

    station_id_requests = []
    for r, dname in station_rows:
        label = getattr(r, "station_id", None) or getattr(r, "station_id_inserted", None) or (f"#{r.id}" if r.id else "Request")
        station_id_requests.append({
            "district": dname or district_name,
            "status": (r.status or "sent_to_chips").strip().lower(),
            "submitted_days_ago": _days_ago(r.submitted_at),
            "created_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "label": label,
            "revert_reason": getattr(r, "revert_reason", None) or getattr(r, "reject_reason", "") or "",
        })

    # 7. L1 Registration Requests
    l1_rows = db.query(L1RegistrationRequest, District.district_name)\
        .outerjoin(District, L1RegistrationRequest.district_id == District.district_code).all()

    l1_requests = []
    for r, dname in l1_rows:
        label = getattr(r, "request_code", None) or (f"#{r.id}" if r.id else "Request")
        l1_requests.append({
            "district": dname or district_name,
            "status": (r.status or "sent_to_chips").strip().lower(),
            "submitted_days_ago": _days_ago(r.created_at),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "label": label,
            "revert_reason": getattr(r, "revert_reason", None) or getattr(r, "reject_reason", "") or "",
        })

    # 8. L2 Registration Requests
    l2_rows = db.query(L2RegistrationRequest, District.district_name)\
        .outerjoin(District, L2RegistrationRequest.district_id == District.district_code)\
        .filter(L2RegistrationRequest.dc_id == dc_id).all()

    l2_requests = []
    for r, dname in l2_rows:
        label = getattr(r, "request_no", None) or getattr(r, "new_station_id", None) or (f"#{r.id}" if r.id else "Request")
        l2_requests.append({
            "district": dname or district_name,
            "status": (r.status or "sent_to_chips").strip().lower(),
            "submitted_days_ago": _days_ago(r.submitted_at),
            "created_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "label": label,
            "revert_reason": getattr(r, "revert_reason", None) or getattr(r, "reject_reason", "") or "",
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
