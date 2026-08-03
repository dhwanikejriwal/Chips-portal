# backend/utils/dashboard_analytics.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.models import (
    OperatorActivationRequest,
    District,
    LMS,
    LMSRemark,
    NSEITRequest,
    NSEITRemark,
    OperatorReactivationRequest,
    Candidate,
    StationIDRequest,
    L1RegistrationRequest,
    L2RegistrationRequest,
)

# ── Per-workflow status vocabularies (case-insensitive membership checks) ────
_WORKFLOW_STATUS_SETS = {
    "lms": {
        "terminal": {"approved", "reverted", "reverted_by_chips"},
        "approved": {"approved"},
        "reverted": {"reverted", "reverted_by_chips"},
    },
    "nseit": {
        "terminal": {"approved", "reverted", "reverted_by_chips"},
        "approved": {"approved"},
        "reverted": {"reverted", "reverted_by_chips"},
    },
    "activation": {
        "terminal": {"approved", "rejected", "reverted", "reverted_by_chips"},
        "approved": {"approved"},
        "reverted": {"reverted", "reverted_by_chips"},
    },
    "reactivation": {
        "terminal": {"reviewed", "assigned", "approved", "reverted"},
        "approved": {"reviewed", "assigned", "approved"},
        "reverted": {"reverted"},
    },
}


def _fetch_workflow_rows(db: Session, workflow: str):
    """Minimal (submitted, decided, status, district_name) tuples for one workflow.
    Queries model instances to evaluate hybrid status properties in Python memory.
    """
    out = []
    try:
        if workflow == "lms":
            rows = db.query(LMS, District.district_name)\
                .join(Candidate, LMS.request_id == Candidate.id)\
                .outerjoin(District, Candidate.district == District.district_code).all()
            for r, dname in rows:
                out.append((r.created_at, r.updated_at, r.status, dname))
        elif workflow == "nseit":
            rows = db.query(NSEITRequest, District.district_name)\
                .join(Candidate, NSEITRequest.request_id == Candidate.id)\
                .outerjoin(District, Candidate.district == District.district_code).all()
            for r, dname in rows:
                out.append((r.created_at, r.updated_at, r.status, dname))
        elif workflow == "activation":
            rows = db.query(OperatorActivationRequest, District.district_name)\
                .outerjoin(District, OperatorActivationRequest.district_id == District.district_code).all()
            for r, dname in rows:
                out.append((r.submitted_at, r.reviewed_at, r.status, dname))
        elif workflow == "reactivation":
            rows = db.query(OperatorReactivationRequest, District.district_name)\
                .outerjoin(District, OperatorReactivationRequest.district_id == District.district_code).all()
            for r, dname in rows:
                out.append((r.created_at, r.updated_at, r.status, dname))
    except Exception:
        pass
    return out


def _workflow_insights(db: Session, workflow: str):
    """Turnaround KPI, reversion rate, and district leaderboard for one workflow."""
    sets = _WORKFLOW_STATUS_SETS.get(workflow, {})
    if not sets:
        return {}
    rows = _fetch_workflow_rows(db, workflow)
    now = datetime.now()

    def _days(sub, dec):
        try:
            return max(0.0, (dec - sub).total_seconds() / 86400)
        except Exception:
            return None

    # ── Turnaround: mean(decision − ORIGINAL submission) over terminal rows only.
    all_durs, last30, prev30 = [], [], []
    for sub, dec, status, _dist in rows:
        s = str(status or "").strip().lower()
        if s not in sets["terminal"] or not sub or not dec:
            continue
        d = _days(sub, dec)
        if d is None:
            continue
        all_durs.append(d)
        age = (now - dec).days
        if age <= 30:
            last30.append(d)
        elif age <= 60:
            prev30.append(d)

    def _avg(xs):
        return round(sum(xs) / len(xs), 1) if xs else None

    turnaround = {
        "avg_days": _avg(all_durs),
        "last30_avg_days": _avg(last30),
        "prev30_avg_days": _avg(prev30),
        "delta_days": round(_avg(last30) - _avg(prev30), 1) if last30 and prev30 else None,
    }

    total = len(rows)
    reversion = {"rate_pct": 0.0, "dc_pct": None, "chips_pct": None}
    try:
        if workflow in ("lms", "nseit"):
            remark_model = LMSRemark if workflow == "lms" else NSEITRemark
            fk = remark_model.lms_id if workflow == "lms" else remark_model.nseit_id
            dc_rev = db.query(func.count(func.distinct(fk))).filter(remark_model.status_after == "Reverted").scalar() or 0
            chips_rev = db.query(func.count(func.distinct(fk))).filter(remark_model.status_after == "Reverted by CHiPS").scalar() or 0
            ever = db.query(func.count(func.distinct(fk))).filter(
                remark_model.status_after.in_(["Reverted", "Reverted by CHiPS"])).scalar() or 0
            if total:
                reversion = {
                    "rate_pct": round(ever / total * 100, 1),
                    "dc_pct": round(dc_rev / total * 100, 1),
                    "chips_pct": round(chips_rev / total * 100, 1),
                }
        else:
            ever = sum(1 for _s, _d, status, _n in rows if str(status or "").strip().lower() in sets["reverted"])
            if total:
                reversion = {"rate_pct": round(ever / total * 100, 1), "dc_pct": None, "chips_pct": None}
    except Exception:
        pass

    by_district = {}
    for sub, dec, status, dist in rows:
        name = dist or "Unknown"
        s = str(status or "").strip().lower()
        b = by_district.setdefault(name, {"total": 0, "pending": 0, "approved": 0, "durs": []})
        b["total"] += 1
        if s not in sets["terminal"]:
            b["pending"] += 1
        if s in sets["approved"]:
            b["approved"] += 1
        if s in sets["terminal"] and sub and dec:
            d = _days(sub, dec)
            if d is not None:
                b["durs"].append(d)

    leaderboard = sorted(
        (
            {
                "district": name,
                "pending": b["pending"],
                "approval_rate_pct": round(b["approved"] / b["total"] * 100, 1) if b["total"] else 0.0,
                "avg_turnaround_days": _avg(b["durs"]),
            }
            for name, b in by_district.items()
        ),
        key=lambda r: r["pending"], reverse=True,
    )[:5]

    return {"turnaround": turnaround, "reversion": reversion, "district_leaderboard": leaderboard}


def _timeframe_cutoff(timeframe: str):
    """Map the dashboard's timeframe selector values to a cutoff datetime (or None)."""
    now = datetime.now()
    mapping = {
        "last_month": 30,
        "quarterly": 90,
        "six_months": 180,
        "annually": 365,
    }
    if timeframe == "this_month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days = mapping.get(timeframe)
    return now - timedelta(days=days) if days else None


def _compute_monthly_trend(db: Session, model, date_field, status_field, update_field, approved_values, rejected_values):
    """Last-12-months submissions/approvals/rejections trend for any request model."""
    now = datetime.now()
    monthly_trend = []
    
    try:
        rows = db.query(model).all()
    except Exception:
        rows = []

    date_attr = date_field.key if hasattr(date_field, 'key') else str(date_field).split('.')[-1]
    status_attr = status_field.key if hasattr(status_field, 'key') else str(status_field).split('.')[-1]
    update_attr = update_field.key if (update_field and hasattr(update_field, 'key')) else (str(update_field).split('.')[-1] if update_field else None)

    for i in range(11, -1, -1):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_start = datetime(year, month, 1)
        if month == 12:
            month_end = datetime(year + 1, 1, 1)
        else:
            month_end = datetime(year, month + 1, 1)

        month_label = month_start.strftime("%b")

        sub_cnt = 0
        app_cnt = 0
        rej_cnt = 0

        for r in rows:
            raw_sub = getattr(r, date_attr, None)
            dt_sub = None
            if raw_sub:
                if isinstance(raw_sub, datetime):
                    dt_sub = raw_sub
                elif hasattr(raw_sub, 'year'):
                    dt_sub = datetime(raw_sub.year, raw_sub.month, raw_sub.day)
                elif isinstance(raw_sub, str):
                    try:
                        dt_sub = datetime.fromisoformat(raw_sub.replace("T", " ")[:19])
                    except Exception:
                        pass

            if dt_sub and month_start <= dt_sub < month_end:
                sub_cnt += getattr(r, 'operator_count', 1) or 1

            status_val = str(getattr(r, status_attr, '') or '').strip()
            raw_upd = getattr(r, update_attr, None) if update_attr else raw_sub
            dt_upd = None
            if raw_upd:
                if isinstance(raw_upd, datetime):
                    dt_upd = raw_upd
                elif hasattr(raw_upd, 'year'):
                    dt_upd = datetime(raw_upd.year, raw_upd.month, raw_upd.day)
                elif isinstance(raw_upd, str):
                    try:
                        dt_upd = datetime.fromisoformat(raw_upd.replace("T", " ")[:19])
                    except Exception:
                        pass
            if not dt_upd:
                dt_upd = dt_sub

            if dt_upd and month_start <= dt_upd < month_end:
                op_c = getattr(r, 'operator_count', 1) or 1
                if any(status_val.lower() == str(v).lower() for v in approved_values):
                    app_cnt += op_c
                elif any(status_val.lower() == str(v).lower() for v in rejected_values):
                    rej_cnt += op_c

        monthly_trend.append({
            "month": month_label,
            "submissions": sub_cnt,
            "approvals": app_cnt,
            "rejections": rej_cnt,
        })
    return monthly_trend
