from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.l1_registration import L1RegistrationRequest
from backend.models.l2_registration import L2RegistrationRequest
from backend.models.station_id import StationIDRequest
from backend.models.operator_activation import OperatorActivationRequest
from backend.models.reactivation import OperatorReactivationRequest
from backend.models import LMS, LMSRemark, NSEITRequest, NSEITRemark, Candidate

FORWARDED_STATUSES = ("Forwarded", "Forwarded Again")

# Statuses that mean CHiPS sent a request back to the DC for re-action.
REVERTED_REJECTED = {"reverted", "reverted_by_chips", "reverted by chips", "rejected"}


def make_naive(dt):
    if dt is None:
        return None
    if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def _is_reverted_rejected(status) -> bool:
    """True when CHiPS reverted or rejected a request back to the DC."""
    return str(status or "").strip().lower() in REVERTED_REJECTED


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
    """DC bell/slider data — baseline-gated (an item is "new" only when its
    triggering event crossed this session's baseline_at, per Part 2 of the
    notification spec).

    Per the DC workflow, the actionable items differ by request family:
      • Registration & activation (Station ID, L1, L2, operator activation and
        reactivation): these reach the DC ONLY as reverts/rejections from
        CHiPS, so they are counted as REVERTS. The revert event's timestamp is
        reused from the existing columns — reviewed_at for Station ID / L2 /
        operator activation, updated_at for L1 / reactivation (no schema
        migration; see the notification design decision). A revert counts only
        when that timestamp is newer than baseline_at.
      • Credentials & exams (LMS, NSEIT): brand-new plus reapplied requests
        arriving from candidates. Both are counted as NEW — created_at (fresh
        submission) or updated_at (a reapply) crossing baseline_at.

    Each type carries a {new, revert} split so the panel can render
    "N new · M revert" (Part 6). For the DC, reg/activation types are
    revert-only and credential types are new-only, but the split is kept
    uniform so the frontend treats both panels the same way.
    """
    # {key: (new_count, revert_count)}
    splits = {}

    def _revert_count(model, ts_attr):
        """Rows currently reverted/rejected whose revert crossed baseline_at."""
        q = db.query(model)
        if district_id:
            q = q.filter(model.district_id == district_id)
        n = 0
        for r in q.all():
            if not _is_reverted_rejected(r.status):
                continue
            ts = make_naive(getattr(r, ts_attr, None))
            if ts and ts > baseline_at:
                n += 1
        return n

    splits["station_id"] = (0, _revert_count(StationIDRequest, "reviewed_at"))
    splits["l1"] = (0, _revert_count(L1RegistrationRequest, "updated_at"))
    splits["l2"] = (0, _revert_count(L2RegistrationRequest, "reviewed_at"))
    splits["operator_activation"] = (0, _revert_count(OperatorActivationRequest, "reviewed_at"))

    # Reactivation is counted by operators affected, not by request rows.
    react_q = db.query(OperatorReactivationRequest)
    if district_id:
        react_q = react_q.filter(OperatorReactivationRequest.district_id == district_id)
    react_revert = sum(
        (r.operator_count or 0)
        for r in react_q.all()
        if _is_reverted_rejected(r.status)
        and make_naive(r.updated_at) and make_naive(r.updated_at) > baseline_at
    )
    splits["operator_reactivation"] = (0, react_revert)

    # LMS / NSEIT: new = created since baseline, OR reapplied since baseline.
    def _creds_new_count(model):
        q = db.query(model).join(Candidate, model.request_id == Candidate.id)
        if district_id:
            q = q.filter(Candidate.district == district_id)
        n = 0
        for r in q.all():
            created = make_naive(r.created_at)
            if created and created > baseline_at:
                n += 1
                continue
            if str(r.status or "").strip().lower() == "reapplied":
                updated = make_naive(r.updated_at)
                if updated and updated > baseline_at:
                    n += 1
        return n

    splits["lms"] = (_creds_new_count(LMS), 0)
    splits["nseit"] = (_creds_new_count(NSEITRequest), 0)

    reg_keys = ["station_id", "l1", "l2", "operator_activation", "operator_reactivation"]
    cred_keys = ["lms", "nseit"]

    groups = [
        _group("Registration and activation",
               "Station ID, L1, L2, operator activation and reactivation reverted or rejected by CHiPS",
               splits, reg_keys),
        _group("Credentials and exams",
               "New and reapplied LMS credential and NSEIT exam requests",
               splits, cred_keys),
    ]

    types = _types(splits)

    return _snapshot(groups, types, baseline_at)


def compute_notification_snapshot(admin_type: str, district_id: str | None, baseline_at: datetime, db: Session) -> dict:
    """Compute requests that became relevant after baseline_at, grouped for the bell.

    Called live on every /notifications/summary request. baseline_at is fixed
    per session (backend/routers/auth.py), but the query against it is live —
    requests arriving during the session show up on the next fetch/poll.
    """
    if admin_type == "dc_admin":
        return _compute_dc_snapshot(district_id, baseline_at, db)

    dc_district_id = district_id if admin_type == "dc_admin" else None

    reg_activation_dates = []
    credentials_exams_dates = []
    type_counts = {}

    l1_query = db.query(L1RegistrationRequest).filter(L1RegistrationRequest.created_at > baseline_at)
    if dc_district_id:
        l1_query = l1_query.filter(L1RegistrationRequest.district_id == dc_district_id)
    l1_dates = [make_naive(r.created_at) for r in l1_query.all()]
    reg_activation_dates += l1_dates
    type_counts["l1"] = len(l1_dates)

    l2_query = db.query(L2RegistrationRequest).filter(L2RegistrationRequest.submitted_at > baseline_at)
    if dc_district_id:
        l2_query = l2_query.filter(L2RegistrationRequest.district_id == dc_district_id)
    l2_dates = [make_naive(r.submitted_at) for r in l2_query.all()]
    reg_activation_dates += l2_dates
    type_counts["l2"] = len(l2_dates)

    station_query = db.query(StationIDRequest).filter(StationIDRequest.submitted_at > baseline_at)
    if dc_district_id:
        station_query = station_query.filter(StationIDRequest.district_id == dc_district_id)
    station_dates = [make_naive(r.submitted_at) for r in station_query.all()]
    reg_activation_dates += station_dates
    type_counts["station_id"] = len(station_dates)

    act_query = db.query(OperatorActivationRequest).filter(OperatorActivationRequest.submitted_at > baseline_at)
    if dc_district_id:
        act_query = act_query.filter(OperatorActivationRequest.district_id == dc_district_id)
    act_dates = [make_naive(r.submitted_at) for r in act_query.all()]
    reg_activation_dates += act_dates
    type_counts["operator_activation"] = len(act_dates)

    react_query = db.query(OperatorReactivationRequest).filter(OperatorReactivationRequest.created_at > baseline_at)
    if dc_district_id:
        react_query = react_query.filter(OperatorReactivationRequest.district_id == dc_district_id)
    react_dates = [make_naive(r.created_at) for r in react_query.all()]
    reg_activation_dates += react_dates
    type_counts["operator_reactivation"] = len(react_dates)

    if admin_type == "chips_admin":
        # LMS/NSEIT are submitted by the candidate to the DC first, then the DC
        # forwards them to CHiPS — that forward action, not the candidate's
        # original submission, is what makes the request "new" for a CHiPS
        # admin. Use the most recent forward-remark's timestamp instead of
        # created_at, and only count requests currently awaiting CHiPS action.
        lms_forward_sub = (
            db.query(LMSRemark.request_id.label("lms_id"), func.max(LMSRemark.time).label("forwarded_at"))
            .filter(LMSRemark.status_after.in_(FORWARDED_STATUSES))
            .group_by(LMSRemark.request_id)
            .subquery()
        )
        lms_query = (
            db.query(lms_forward_sub.c.forwarded_at)
            .select_from(LMS)
            .join(lms_forward_sub, LMS.id == lms_forward_sub.c.lms_id)
            .join(Candidate, LMS.request_id == Candidate.id)
            .filter(LMS.status.in_(FORWARDED_STATUSES), lms_forward_sub.c.forwarded_at > baseline_at)
        )
        lms_dates = [make_naive(row[0]) for row in lms_query.all()]
        credentials_exams_dates += lms_dates
        type_counts["lms"] = len(lms_dates)

        nseit_forward_sub = (
            db.query(NSEITRemark.request_id.label("nseit_id"), func.max(NSEITRemark.time).label("forwarded_at"))
            .filter(NSEITRemark.status_after.in_(FORWARDED_STATUSES))
            .group_by(NSEITRemark.request_id)
            .subquery()
        )
        nseit_query = (
            db.query(nseit_forward_sub.c.forwarded_at)
            .select_from(NSEITRequest)
            .join(nseit_forward_sub, NSEITRequest.id == nseit_forward_sub.c.nseit_id)
            .join(Candidate, NSEITRequest.request_id == Candidate.id)
            .filter(NSEITRequest.status.in_(FORWARDED_STATUSES), nseit_forward_sub.c.forwarded_at > baseline_at)
        )
        nseit_dates = [make_naive(row[0]) for row in nseit_query.all()]
        credentials_exams_dates += nseit_dates
        type_counts["nseit"] = len(nseit_dates)
    else:
        # For a DC admin, the candidate's own submission is what lands in
        # their queue — created_at is the right cutoff.
        lms_query = db.query(LMS).join(Candidate, LMS.request_id == Candidate.id).filter(LMS.created_at > baseline_at)
        if dc_district_id:
            lms_query = lms_query.filter(Candidate.district == dc_district_id)
        lms_dates = [make_naive(r.created_at) for r in lms_query.all()]
        credentials_exams_dates += lms_dates
        type_counts["lms"] = len(lms_dates)

        nseit_query = db.query(NSEITRequest).join(Candidate, NSEITRequest.request_id == Candidate.id).filter(NSEITRequest.created_at > baseline_at)
        if dc_district_id:
            nseit_query = nseit_query.filter(Candidate.district == dc_district_id)
        nseit_dates = [make_naive(r.created_at) for r in nseit_query.all()]
        credentials_exams_dates += nseit_dates
        type_counts["nseit"] = len(nseit_dates)

    # For CHiPS every counted item is fresh incoming work (a new submission or
    # a DC-forwarded credential request), so the revert side of the split is
    # always zero — reverts flow from CHiPS to the DC, not the other way.
    splits = {key: (type_counts.get(key, 0), 0) for key in TYPE_ORDER}

    groups = [
        _group("Registration and activation",
               "Station ID, L1, L2, operator activation and reactivation",
               splits, ["station_id", "l1", "l2", "operator_activation", "operator_reactivation"]),
        _group("Credentials and exams",
               "LMS credential and NSEIT exam requests",
               splits, ["lms", "nseit"]),
    ]

    return _snapshot(groups, _types(splits), baseline_at)
