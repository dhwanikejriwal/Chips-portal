from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.l1_registration import L1RegistrationRequest
from backend.models.l2_registration import L2RegistrationRequest
from backend.models.station_id import StationIDRequest
from backend.models.operator_activation import OperatorActivationRequest
from backend.models.reactivation import OperatorReactivationRequest
from backend.models import LMS, LMSRemark, NSEITRequest, NSEITRemark, Candidate
from backend.models.base import to_code, get_ist_now

FORWARDED_STATUSES = ("Forwarded", "Forwarded Again")
# `status`/`status_after` are Python-only hybrid properties (name <-> id via
# to_name/to_code) with no SQL expression, so they cannot be used inside a
# query filter. Filter on the underlying *_id columns instead.
FORWARDED_STATUS_IDS = [to_code(s) for s in FORWARDED_STATUSES]

# Statuses that mean CHiPS sent a request back to the DC for re-action.
REVERTED_REJECTED = {"reverted", "reverted_by_chips", "reverted by chips", "rejected", "revert back", "revert_back", "uidai rejected", "uidai_rejected"}


def make_naive(dt):
    if dt is None:
        return None
    if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def _get_item_timestamp(r):
    """Retrieve the most relevant action/creation timestamp for an item."""
    for attr in ("updated_at", "created_at", "submitted_at", "time", "timestamp"):
        val = getattr(r, attr, None)
        if val is not None:
            return make_naive(val)
    remarks = getattr(r, "remarks", None)
    if remarks and len(remarks) > 0:
        last_rem = remarks[-1]
        for attr in ("created_at", "timestamp", "time"):
            val = getattr(last_rem, attr, None)
            if val is not None:
                return make_naive(val)
    return None


def _is_under_a_day_old(r, cutoff_time: datetime) -> bool:
    """True if the request arrived / was updated within the last 24 hours (under a day old)."""
    ts = _get_item_timestamp(r)
    if ts is None:
        return False
    return ts >= cutoff_time


def _is_reverted_rejected(status) -> bool:
    """True when CHiPS reverted or rejected a request back to the DC."""
    s = str(status or "").strip().lower().replace("_", " ")
    if not s:
        return False
    return any(keyword in s for keyword in ("revert", "reject"))


# Stable per-type labels shared by both panels.
TYPE_LABELS = {
    "station_id": "Station ID",
    "l1": "L1 Registration",
    "l2": "L2 Registration",
    "operator_activation": "Operator Activation",
    "operator_reactivation": "Operator Reactivation",
    "lms": "LMS Credential",
    "nseit": "NSEIT Request",
}

# Fixed type ordering for the expanded per-type list.
TYPE_ORDER = ["station_id", "l1", "l2", "operator_activation",
              "operator_reactivation", "lms", "nseit"]


def _group(name, description, splits, keys):
    """Roll a set of type keys up into one panel group, keeping the
    new/revert split so the frontend can render "N new · M revert"."""
    new_count = sum(splits[k][0] for k in keys)
    revert_count = sum(splits[k][1] for k in keys)
    return {
        "name": name,
        "description": description,
        "count": new_count + revert_count,
        "new_count": new_count,
        "revert_count": revert_count,
    }


def _types(splits):
    """Per-type rows for the expanded list, each with its new/revert split."""
    rows = []
    for key in TYPE_ORDER:
        new_count, revert_count = splits.get(key, (0, 0))
        rows.append({
            "key": key,
            "label": TYPE_LABELS[key],
            "count": new_count + revert_count,
            "new_count": new_count,
            "revert_count": revert_count,
        })
    return rows


def _snapshot(groups, types, baseline_at):
    """Assemble the final response. new_request_count is kept for backward
    compatibility with the existing frontend; new_item_count is the spec name
    (Part 5) — both hold the same total."""
    total = sum(g["count"] for g in groups)
    return {
        "new_request_count": total,
        "new_item_count": total,
        "groups": groups,
        "types": types,
        "baseline_at": baseline_at.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _compute_dc_snapshot(district_id, baseline_at, db):
    """Compute active actionable items under 1 day old for DC / EDM users (candidate requests & reverted items)."""
    splits = {}
    now = make_naive(get_ist_now())
    one_day_cutoff = now - timedelta(days=1)

    user_dist_codes = set()
    user_dist_names = set()
    if district_id:
        from backend.utils.district_mapper import normalize_district_name
        from backend.models.district import District

        user_dist_str = str(district_id).strip().lower()
        user_dist_codes.add(user_dist_str)
        user_dist_names.add(normalize_district_name(str(district_id)).lower())

        dist_obj = db.query(District).filter(
            (District.district_code == str(district_id)) | (District.district_name.ilike(str(district_id)))
        ).first()
        if dist_obj:
            user_dist_codes.add(str(dist_obj.district_code).lower())
            user_dist_names.add(dist_obj.district_name.lower())
            user_dist_names.add(normalize_district_name(dist_obj.district_name).lower())

    def _matches_district(d_val):
        if not district_id or d_val is None:
            return True
        d_str = str(d_val).strip().lower()
        if d_str in user_dist_codes or d_str in user_dist_names:
            return True
        from backend.utils.district_mapper import normalize_district_name
        if normalize_district_name(d_str).lower() in user_dist_names:
            return True
        return False

    def _revert_count(model):
        q = db.query(model)
        matching_rows = [r for r in q.all() if _matches_district(getattr(r, 'district_id', None) or getattr(r, 'district', None))]
        n = 0
        for r in matching_rows:
            if _is_reverted_rejected(getattr(r, 'status', None)) and _is_under_a_day_old(r, one_day_cutoff):
                n += 1
        return n

    splits["station_id"] = (0, _revert_count(StationIDRequest))
    splits["l1"] = (0, _revert_count(L1RegistrationRequest))
    splits["l2"] = (0, _revert_count(L2RegistrationRequest))
    splits["operator_activation"] = (0, _revert_count(OperatorActivationRequest))

    react_q = db.query(OperatorReactivationRequest)
    react_rows = [r for r in react_q.all() if _matches_district(r.district_id)]

    react_revert = 0
    for r in react_rows:
        batch_is_rev = _is_reverted_rejected(getattr(r, 'status', None))
        batch_under_day = _is_under_a_day_old(r, one_day_cutoff)
        if batch_is_rev and batch_under_day:
            # Batch itself is marked reverted/rejected within 24h
            count_val = getattr(r, 'operator_count', None) or (len(r.operators) if r.operators else 1) or 1
            react_revert += count_val
        elif r.operators:
            # Count individual child operators marked reverted/rejected within 24h
            for op in r.operators:
                if _is_reverted_rejected(getattr(op, 'status', None)) and (_is_under_a_day_old(op, one_day_cutoff) or batch_under_day):
                    react_revert += 1

    splits["operator_reactivation"] = (0, react_revert)

    def _creds_count(model):
        q = db.query(model).join(Candidate, model.request_id == Candidate.id)
        all_rows = q.all()
        rows = [r for r in all_rows if r.candidate and _matches_district(r.candidate.district)]
        n = 0
        for r in rows:
            status_str = str(getattr(r, 'status', '') or "").strip().lower()
            if status_str in ("pending", "reapplied") and _is_under_a_day_old(r, one_day_cutoff):
                n += 1
        return n

    splits["lms"] = (_creds_count(LMS), 0)
    splits["nseit"] = (_creds_count(NSEITRequest), 0)

    reg_keys = ["station_id", "l1", "l2", "operator_activation", "operator_reactivation"]
    cred_keys = ["lms", "nseit"]

    groups = [
        _group("Registration and activation",
               "Station ID, L1, L2, operator activation and reactivation reverted or rejected by CHiPS (last 24h)",
               splits, reg_keys),
        _group("Credentials and exams",
               "New and reapplied LMS credential and NSEIT exam requests (last 24h)",
               splits, cred_keys),
    ]

    types = _types(splits)

    return _snapshot(groups, types, one_day_cutoff)


def compute_notification_snapshot(admin_type: str, district_id: str | None, baseline_at: datetime, db: Session) -> dict:
    """Compute requests under 1 day old that require action, grouped for the notification bell."""
    if admin_type == "dc_admin":
        return _compute_dc_snapshot(district_id, baseline_at, db)

    now = make_naive(get_ist_now())
    one_day_cutoff = now - timedelta(days=1)

    chips_actionable = {"pending", "reapplied", "forwarded", "forwarded again"}

    type_counts = {}

    l1_all = db.query(L1RegistrationRequest).all()
    l1_pending = [
        r for r in l1_all
        if str(r.status or "").strip().lower() in chips_actionable and _is_under_a_day_old(r, one_day_cutoff)
    ]
    type_counts["l1"] = len(l1_pending)

    l2_all = db.query(L2RegistrationRequest).all()
    l2_pending = [
        r for r in l2_all
        if str(r.status or "").strip().lower() in chips_actionable
        and (getattr(r, 'is_mailed', 0) == 0 or not r.is_mailed)
        and _is_under_a_day_old(r, one_day_cutoff)
    ]
    type_counts["l2"] = len(l2_pending)

    station_all = db.query(StationIDRequest).all()
    station_pending = [
        r for r in station_all
        if str(r.status or "").strip().lower() in chips_actionable and _is_under_a_day_old(r, one_day_cutoff)
    ]
    type_counts["station_id"] = len(station_pending)

    act_all = db.query(OperatorActivationRequest).all()
    act_pending = [
        r for r in act_all
        if str(r.status or "").strip().lower() in chips_actionable
        and (getattr(r, 'is_mailed', 0) == 0 or not r.is_mailed)
        and _is_under_a_day_old(r, one_day_cutoff)
    ]
    type_counts["operator_activation"] = len(act_pending)

    react_all = db.query(OperatorReactivationRequest).all()
    react_count = 0
    for r in react_all:
        if str(r.status or "").strip().lower() not in chips_actionable:
            continue
        if getattr(r, 'is_mailed', 0) == 1:
            continue
        batch_under_day = _is_under_a_day_old(r, one_day_cutoff)
        if r.operators:
            # Count only active pending/reapplied operators in the batch under 1 day old
            pending_ops = sum(
                1 for op in r.operators
                if str(op.status or "").strip().lower() in chips_actionable
                and (_is_under_a_day_old(op, one_day_cutoff) or batch_under_day)
            )
            react_count += pending_ops
        elif batch_under_day:
            react_count += (getattr(r, 'operator_count', 1) or 1)
    type_counts["operator_reactivation"] = react_count

    if admin_type == "chips_admin":
        # LMS & NSEIT requests forwarded to CHiPS within the last 24h
        lms_all = db.query(LMS).join(Candidate, LMS.request_id == Candidate.id).all()
        lms_pending = [
            r for r in lms_all
            if (r.status_id in FORWARDED_STATUS_IDS or str(r.status or "").strip().lower() in ("forwarded", "forwarded again"))
            and _is_under_a_day_old(r, one_day_cutoff)
        ]
        type_counts["lms"] = len(lms_pending)

        nseit_all = db.query(NSEITRequest).join(Candidate, NSEITRequest.request_id == Candidate.id).all()
        nseit_pending = [
            r for r in nseit_all
            if (r.status_id in FORWARDED_STATUS_IDS or str(r.status or "").strip().lower() in ("forwarded", "forwarded again"))
            and _is_under_a_day_old(r, one_day_cutoff)
        ]
        type_counts["nseit"] = len(nseit_pending)
    else:
        lms_query = db.query(LMS).join(Candidate, LMS.request_id == Candidate.id)
        if district_id:
            lms_query = lms_query.filter(Candidate.district == district_id)
        lms_all = lms_query.all()
        type_counts["lms"] = len([
            r for r in lms_all
            if str(r.status or "").strip().lower() in ("pending", "reapplied") and _is_under_a_day_old(r, one_day_cutoff)
        ])

        nseit_query = db.query(NSEITRequest).join(Candidate, NSEITRequest.request_id == Candidate.id)
        if district_id:
            nseit_query = nseit_query.filter(Candidate.district == district_id)
        nseit_all = nseit_query.all()
        type_counts["nseit"] = len([
            r for r in nseit_all
            if str(r.status or "").strip().lower() in ("pending", "reapplied") and _is_under_a_day_old(r, one_day_cutoff)
        ])

    splits = {key: (type_counts.get(key, 0), 0) for key in TYPE_ORDER}

    groups = [
        _group("Registration and activation",
               "Station ID, L1, L2, operator activation and reactivation",
               splits, ["station_id", "l1", "l2", "operator_activation", "operator_reactivation"]),
        _group("Credentials and exams",
               "LMS credential and NSEIT exam requests",
               splits, ["lms", "nseit"]),
    ]

    return _snapshot(groups, _types(splits), one_day_cutoff)
