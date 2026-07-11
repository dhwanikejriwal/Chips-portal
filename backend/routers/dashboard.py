# backend/routers/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from backend.database import get_db
from backend.models import (
    OperatorActivationRequest,
    UserLogin as User,
    District,
    MasterUserRole,
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

router = APIRouter()


# ── Per-workflow status vocabularies (case-insensitive membership checks) ────
# terminal  = a final decision was recorded; used for turnaround math
# approved  = counts toward approval rate
# reverted  = counts toward reversion rate
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


def _fetch_workflow_rows(db, workflow):
    """Minimal (submitted, decided, status, district_name) tuples for one workflow.

    Timestamps: submission is created_at/submitted_at — the ORIGINAL first
    submission. Reapplies after a reversion do NOT reset this clock, matching
    how the frontend aging buckets (submitted_days_ago) already behave.
    """
    if workflow == "lms":
        return db.query(LMS.created_at, LMS.updated_at, LMS.status, District.district_name)\
            .join(Candidate, LMS.r_id == Candidate.r_id)\
            .outerjoin(District, Candidate.district == District.district_code).all()
    if workflow == "nseit":
        return db.query(NSEITRequest.created_at, NSEITRequest.updated_at, NSEITRequest.status, District.district_name)\
            .join(Candidate, NSEITRequest.r_id == Candidate.r_id)\
            .outerjoin(District, Candidate.district == District.district_code).all()
    if workflow == "activation":
        return db.query(OperatorActivationRequest.submitted_at, OperatorActivationRequest.reviewed_at,
                        OperatorActivationRequest.status, District.district_name)\
            .outerjoin(District, OperatorActivationRequest.district_id == District.district_code).all()
    if workflow == "reactivation":
        return db.query(OperatorReactivationRequest.created_at, OperatorReactivationRequest.updated_at,
                        OperatorReactivationRequest.status, District.district_name)\
            .outerjoin(District, OperatorReactivationRequest.district_id == District.district_code).all()
    return []


def _workflow_insights(db, workflow):
    """Turnaround KPI, reversion rate, and district leaderboard for one workflow."""
    from datetime import datetime, timedelta

    sets = _WORKFLOW_STATUS_SETS[workflow]
    rows = _fetch_workflow_rows(db, workflow)
    now = datetime.now()

    def _days(sub, dec):
        try:
            return max(0.0, (dec - sub).total_seconds() / 86400)
        except Exception:
            return None

    # ── Turnaround: mean(decision − ORIGINAL submission) over terminal rows only.
    # Delta compares decisions made in the last 30 days vs the 30 days before that.
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

    # ── Reversion rate: requests EVER reverted / total.
    # LMS & NSEIT log status_after in their remark tables, so DC vs CHIPS splits
    # are real. Activation and Reactivation have no per-actor revert marker in
    # the schema — only current status — so the split is omitted there rather
    # than fabricated.
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

    # ── District leaderboard: top 5 by pending backlog.
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


def _timeframe_cutoff(timeframe):
    """Map the dashboard's timeframe selector values to a cutoff datetime (or None)."""
    from datetime import datetime, timedelta
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


def _compute_monthly_trend(db, model, date_field, status_field, update_field, approved_values, rejected_values):
    """Last-12-months submissions/approvals/rejections trend for any request model."""
    from datetime import date
    today = date.today()
    monthly_trend = []
    for i in range(11, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_start = date(year, month, 1)
        month_end = date(month_start.year + 1, 1, 1) if month_start.month == 12 else date(month_start.year, month_start.month + 1, 1)

        submissions = db.query(func.count(model.id)).filter(
            date_field >= month_start,
            date_field < month_end,
        ).scalar() or 0

        approvals = db.query(func.count(model.id)).filter(
            status_field.in_(approved_values),
            update_field >= month_start,
            update_field < month_end,
        ).scalar() or 0

        rejections = db.query(func.count(model.id)).filter(
            status_field.in_(rejected_values),
            update_field >= month_start,
            update_field < month_end,
        ).scalar() or 0

        monthly_trend.append({
            "month": month_start.strftime("%b"),
            "submissions": submissions,
            "approvals": approvals,
            "rejections": rejections,
        })
    return monthly_trend


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    # 1. Summary Counts
    status_counts = db.query(
        OperatorActivationRequest.status,
        func.count(OperatorActivationRequest.id)
    ).group_by(OperatorActivationRequest.status).all()
    
    counts_map = dict(status_counts)
    
    # "sent_to_chips" is also treated as pending in the application lifecycle
    pending_count = counts_map.get("pending", 0) + counts_map.get("sent_to_chips", 0)
    
    summary = {
        "total": sum(counts_map.values()),
        "pending": pending_count,
        "approved": counts_map.get("approved", 0),
        "rejected": counts_map.get("rejected", 0),
        "sent_to_uidai": counts_map.get("sent_to_uidai", 0),
        "reverted": counts_map.get("reverted", 0)
    }

    # 2. DC Performance
    dc_perf_rows = db.query(
        User.username,
        District.district_name.label("district_name"),
        func.count(OperatorActivationRequest.id).label("total"),
        func.count(case((OperatorActivationRequest.status == "approved", 1))).label("approved"),
        func.count(case((OperatorActivationRequest.status == "rejected", 1))).label("rejected"),
        func.count(case((OperatorActivationRequest.status.in_(["pending", "sent_to_chips"]), 1))).label("pending"),
        func.avg(func.extract("epoch", OperatorActivationRequest.reviewed_at - OperatorActivationRequest.submitted_at) / 3600).label("avg_pending_hours")
    ).select_from(User)\
     .outerjoin(District, User.district_id == District.district_code)\
     .outerjoin(OperatorActivationRequest, User.id == OperatorActivationRequest.dc_id)\
     .join(MasterUserRole, User.roleid == MasterUserRole.id)\
     .filter(MasterUserRole.role == "DC")\
     .group_by(User.id, User.username, District.district_name)\
     .all()

    dc_performance = []
    for row in dc_perf_rows:
        avg_h = row.avg_pending_hours
        dc_performance.append({
            "dc_name": row.username,
            "district": row.district_name or "N/A",
            "total": row.total,
            "approved": row.approved,
            "rejected": row.rejected,
            "pending": row.pending,
            "avg_pending_hours": round(avg_h, 2) if avg_h is not None else None
        })

    # 3. Recent Requests
    recent_rows = db.query(
        OperatorActivationRequest.id,
        OperatorActivationRequest.request_no,
        OperatorActivationRequest.name_as_per_aadhaar,
        District.district_name.label("district_name"),
        OperatorActivationRequest.status,
        OperatorActivationRequest.submitted_at
    ).select_from(OperatorActivationRequest)\
     .join(District, OperatorActivationRequest.district_id == District.district_code)\
     .order_by(OperatorActivationRequest.submitted_at.desc())\
     .limit(10)\
     .all()

    recent_requests = []
    for r in recent_rows:
        recent_requests.append({
            "id": r.id,
            "request_no": r.request_no or f"RP-A{r.id:04d}",
            "name_as_per_aadhaar": r.name_as_per_aadhaar,
            "district": r.district_name,
            "status": r.status,
            "submitted_at": r.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if r.submitted_at else "N/A"
        })

    # 4. operator_funnel calculations
    operator_funnel = {
        "lms_applied": 0,
        "nseit_done": 0,
        "activation_submitted": 0,
        "sent_to_uidai": 0,
        "approved": 0
    }
    try:
        operator_funnel["lms_applied"] = db.query(LMS).count()
    except Exception:
        pass

    try:
        operator_funnel["nseit_done"] = db.query(NSEITRequest).filter(NSEITRequest.status == "Approved").count()
    except Exception:
        pass

    try:
        operator_funnel["activation_submitted"] = db.query(OperatorActivationRequest).count()
    except Exception:
        pass

    # sent_to_uidai: activation + reactivation
    try:
        act_sent = db.query(OperatorActivationRequest).filter(
            func.lower(OperatorActivationRequest.status) == "sent_to_uidai"
        ).count()
        react_sent = 0
        try:
            react_sent = db.query(OperatorReactivationRequest).filter(
                func.lower(OperatorReactivationRequest.status) == "sent_to_uidai"
            ).count()
        except Exception:
            pass
        operator_funnel["sent_to_uidai"] = act_sent + react_sent
    except Exception:
        pass

    # approved: activation + reactivation
    try:
        act_app = db.query(OperatorActivationRequest).filter(
            func.lower(OperatorActivationRequest.status) == "approved"
        ).count()
        react_app = 0
        try:
            react_app = db.query(OperatorReactivationRequest).filter(
                func.lower(OperatorReactivationRequest.status) == "approved"
            ).count()
        except Exception:
            pass
        operator_funnel["approved"] = act_app + react_app
    except Exception:
        pass

    # 5. NSEIT Certificate Analysis
    nseit_analysis = {
        "expiring_soon": 0,
        "already_expired": 0,
        "monthly_trend": [],
        "expiring_soon_list": [],
        "expired_list": [],
    }
    try:
        from datetime import date, timedelta
        today = date.today()
        in_30 = today + timedelta(days=30)

        # Expiring within 30 days
        try:
            expiring_soon_count = db.query(func.count(OperatorActivationRequest.id)).filter(
                OperatorActivationRequest.nseit_certificate_expiry_date != None,
                OperatorActivationRequest.nseit_certificate_expiry_date >= today,
                OperatorActivationRequest.nseit_certificate_expiry_date <= in_30,
            ).scalar() or 0
            nseit_analysis["expiring_soon"] = expiring_soon_count
        except Exception:
            pass

        # Already expired
        try:
            expired_count = db.query(func.count(OperatorActivationRequest.id)).filter(
                OperatorActivationRequest.nseit_certificate_expiry_date != None,
                OperatorActivationRequest.nseit_certificate_expiry_date < today,
            ).scalar() or 0
            nseit_analysis["already_expired"] = expired_count
        except Exception:
            pass

        # Monthly submissions/approvals/rejections trend — last 12 months (NSEIT exam requests)
        try:
            nseit_analysis["monthly_trend"] = _compute_monthly_trend(
                db, NSEITRequest, NSEITRequest.created_at, NSEITRequest.status, NSEITRequest.updated_at,
                approved_values=["Approved"],
                rejected_values=["Reverted", "Reverted by CHiPS", "reverted", "reverted_by_chips"],
            )
        except Exception:
            pass

        # Expiring soon list (ordered by expiry ASC)
        try:
            expiring_rows = db.query(
                OperatorActivationRequest.request_no,
                OperatorActivationRequest.name_as_per_aadhaar,
                OperatorActivationRequest.operator_mobile,
                OperatorActivationRequest.nseit_certificate_expiry_date,
            ).filter(
                OperatorActivationRequest.nseit_certificate_expiry_date != None,
                OperatorActivationRequest.nseit_certificate_expiry_date >= today,
                OperatorActivationRequest.nseit_certificate_expiry_date <= in_30,
            ).order_by(OperatorActivationRequest.nseit_certificate_expiry_date.asc()).all()

            nseit_analysis["expiring_soon_list"] = [
                {
                    "request_no": r.request_no or "N/A",
                    "name_as_per_aadhaar": r.name_as_per_aadhaar or "N/A",
                    "operator_mobile": r.operator_mobile or "N/A",
                    "nseit_certificate_expiry_date": r.nseit_certificate_expiry_date.strftime("%Y-%m-%d") if r.nseit_certificate_expiry_date else "N/A",
                    "days_remaining": (r.nseit_certificate_expiry_date.date() - today).days if r.nseit_certificate_expiry_date else 0,
                }
                for r in expiring_rows
            ]
        except Exception:
            pass

        # Expired list (ordered by expiry DESC — most recently expired first)
        try:
            expired_rows = db.query(
                OperatorActivationRequest.request_no,
                OperatorActivationRequest.name_as_per_aadhaar,
                OperatorActivationRequest.operator_mobile,
                OperatorActivationRequest.nseit_certificate_expiry_date,
            ).filter(
                OperatorActivationRequest.nseit_certificate_expiry_date != None,
                OperatorActivationRequest.nseit_certificate_expiry_date < today,
            ).order_by(OperatorActivationRequest.nseit_certificate_expiry_date.desc()).all()

            nseit_analysis["expired_list"] = [
                {
                    "request_no": r.request_no or "N/A",
                    "name_as_per_aadhaar": r.name_as_per_aadhaar or "N/A",
                    "operator_mobile": r.operator_mobile or "N/A",
                    "nseit_certificate_expiry_date": r.nseit_certificate_expiry_date.strftime("%Y-%m-%d") if r.nseit_certificate_expiry_date else "N/A",
                    "days_overdue": (today - r.nseit_certificate_expiry_date.date()).days if r.nseit_certificate_expiry_date else 0,
                }
                for r in expired_rows
            ]
        except Exception:
            pass

    except Exception:
        pass

    # LMS Credential monthly trend
    lms_analysis = {"monthly_trend": []}
    try:
        lms_analysis["monthly_trend"] = _compute_monthly_trend(
            db, LMS, LMS.created_at, LMS.status, LMS.updated_at,
            approved_values=["Approved"],
            rejected_values=["Reverted", "Reverted by CHiPS"],
        )
    except Exception:
        pass

    # Operator Activation monthly trend
    activation_analysis = {"monthly_trend": []}
    try:
        activation_analysis["monthly_trend"] = _compute_monthly_trend(
            db, OperatorActivationRequest, OperatorActivationRequest.submitted_at,
            OperatorActivationRequest.status, OperatorActivationRequest.reviewed_at,
            approved_values=["approved"],
            rejected_values=["rejected", "reverted", "reverted_by_chips"],
        )
    except Exception:
        pass

    # Operator Re-activation monthly trend
    reactivation_analysis = {"monthly_trend": []}
    try:
        reactivation_analysis["monthly_trend"] = _compute_monthly_trend(
            db, OperatorReactivationRequest, OperatorReactivationRequest.created_at,
            OperatorReactivationRequest.status, OperatorReactivationRequest.updated_at,
            approved_values=["REVIEWED", "ASSIGNED", "APPROVED"],
            rejected_values=["REVERTED"],
        )
    except Exception:
        pass

    # ── Kit request monthly trends ────────────────────────────────────────
    station_id_analysis = {"monthly_trend": []}
    try:
        station_id_analysis["monthly_trend"] = _compute_monthly_trend(
            db, StationIDRequest, StationIDRequest.submitted_at,
            StationIDRequest.status, StationIDRequest.reviewed_at,
            approved_values=["approved", "activated"],
            rejected_values=["rejected", "reverted", "reverted_by_chips"],
        )
    except Exception:
        pass

    l1_analysis = {"monthly_trend": []}
    try:
        l1_analysis["monthly_trend"] = _compute_monthly_trend(
            db, L1RegistrationRequest, L1RegistrationRequest.created_at,
            L1RegistrationRequest.status, L1RegistrationRequest.updated_at,
            approved_values=["REVIEWED"],
            rejected_values=["REVERTED"],
        )
    except Exception:
        pass

    l2_analysis = {"monthly_trend": []}
    try:
        l2_analysis["monthly_trend"] = _compute_monthly_trend(
            db, L2RegistrationRequest, L2RegistrationRequest.submitted_at,
            L2RegistrationRequest.status, L2RegistrationRequest.reviewed_at,
            approved_values=["approved", "activated"],
            rejected_values=["rejected", "reverted", "reverted_by_chips"],
        )
    except Exception:
        pass

    # Per-workflow insight blocks (turnaround KPI, reversion rate, district
    # leaderboard) — additive keys on the existing analysis objects.
    for analysis, wf in (
        (lms_analysis, "lms"),
        (nseit_analysis, "nseit"),
        (activation_analysis, "activation"),
        (reactivation_analysis, "reactivation"),
    ):
        try:
            analysis.update(_workflow_insights(db, wf))
        except Exception:
            pass

    return {
        "summary": summary,
        "dc_performance": dc_performance,
        "recent_requests": recent_requests,
        "nseit_analysis": nseit_analysis,
        "operator_funnel": operator_funnel,
        "lms_analysis": lms_analysis,
        "activation_analysis": activation_analysis,
        "reactivation_analysis": reactivation_analysis,
        "station_id_analysis": station_id_analysis,
        "l1_analysis": l1_analysis,
        "l2_analysis": l2_analysis,
    }


def _serialize_nseit_row(req, district_name):
    return {
        "request_no": req.request_no or "N/A",
        "name_as_per_aadhaar": req.name_as_per_aadhaar,
        "operator_mobile": req.operator_mobile,
        "primary_email": req.primary_email,
        "operator_aadhaar": req.operator_aadhaar,
        "district_name": district_name or "N/A",
        "nseit_certificate_number": req.nseit_certificate_number,
        "nseit_certification_date": req.nseit_certification_date.strftime("%Y-%m-%d") if req.nseit_certification_date else None,
        "nseit_certificate_expiry_date": req.nseit_certificate_expiry_date.strftime("%Y-%m-%d") if req.nseit_certificate_expiry_date else None,
        "status": req.status,
    }


@router.get("/nseit/expiring")
def get_nseit_expiring(db: Session = Depends(get_db)):
    try:
        from datetime import date, timedelta
        today = date.today()
        in_30 = today + timedelta(days=30)

        rows = db.query(OperatorActivationRequest, District.district_name)\
            .outerjoin(District, OperatorActivationRequest.district_id == District.district_code)\
            .filter(
                OperatorActivationRequest.nseit_certificate_expiry_date != None,
                OperatorActivationRequest.nseit_certificate_expiry_date >= today,
                OperatorActivationRequest.nseit_certificate_expiry_date <= in_30,
            ).order_by(OperatorActivationRequest.nseit_certificate_expiry_date.asc()).all()

        result = []
        for req, district_name in rows:
            item = _serialize_nseit_row(req, district_name)
            item["days_remaining"] = (req.nseit_certificate_expiry_date.date() - today).days
            result.append(item)
        return result
    except Exception:
        return []


@router.get("/nseit/expired")
def get_nseit_expired(db: Session = Depends(get_db)):
    try:
        from datetime import date
        today = date.today()

        rows = db.query(OperatorActivationRequest, District.district_name)\
            .outerjoin(District, OperatorActivationRequest.district_id == District.district_code)\
            .filter(
                OperatorActivationRequest.nseit_certificate_expiry_date != None,
                OperatorActivationRequest.nseit_certificate_expiry_date < today,
            ).order_by(OperatorActivationRequest.nseit_certificate_expiry_date.desc()).all()

        result = []
        for req, district_name in rows:
            item = _serialize_nseit_row(req, district_name)
            item["days_overdue"] = (today - req.nseit_certificate_expiry_date.date()).days
            result.append(item)
        return result
    except Exception:
        return []

from pydantic import BaseModel
from typing import Optional

class DistrictSettingsUpdate(BaseModel):
    registration_open: bool
    registration_start_date: Optional[str] = None
    registration_end_date: Optional[str] = None

@router.get("/districts/settings")
def get_district_settings(db: Session = Depends(get_db)):
    districts = db.query(District).order_by(District.district_name).all()
    res = []
    for d in districts:
        res.append({
            "district_code": d.district_code,
            "district_name": d.district_name,
            "registration_open": d.registration_open,
            "registration_start_date": d.registration_start_date,
            "registration_end_date": d.registration_end_date,
        })
    return {"districts": res}

@router.put("/districts/{district_code}/settings")
def update_district_settings(district_code: str, settings: DistrictSettingsUpdate, db: Session = Depends(get_db)):
    from datetime import datetime
    from fastapi import HTTPException
    
    d = db.query(District).filter(District.district_code == district_code).first()
    if not d:
        raise HTTPException(status_code=404, detail="District not found")
        
    d.registration_open = settings.registration_open
    d.registration_start_date = settings.registration_start_date
    d.registration_end_date = settings.registration_end_date
    
    if settings.registration_open:
        d.registration_opened_at = datetime.now().isoformat()
        
    db.commit()
    return {"message": "Settings updated successfully"}



