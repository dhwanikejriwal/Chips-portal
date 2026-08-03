# backend/routers/chips_dashboard.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date, timedelta

from backend.database import get_db
from backend.models import (
    OperatorActivationRequest,
    UserLogin as User,
    District,
    MasterUserRole,
    LMS,
    NSEITRequest,
    OperatorReactivationRequest,
    Candidate,
    StationIDRequest,
    L1RegistrationRequest,
    L2RegistrationRequest,
)

from backend.utils.dashboard_analytics import (
    _compute_monthly_trend,
    _workflow_insights,
)

router = APIRouter(prefix="/dashboard", tags=["CHiPS Dashboard"])


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


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Summary statistics, DC performance, operator funnel, and trend analytics."""
    # 1. Summary Counts
    all_act = db.query(OperatorActivationRequest).all()
    counts_map = {}
    for r in all_act:
        s = str(r.status or "").strip().lower()
        counts_map[s] = counts_map.get(s, 0) + 1
    
    pending_count = counts_map.get("pending", 0) + counts_map.get("sent_to_chips", 0)
    summary = {
        "total": len(all_act),
        "pending": pending_count,
        "approved": counts_map.get("approved", 0),
        "rejected": counts_map.get("rejected", 0),
        "sent_to_uidai": counts_map.get("sent_to_uidai", 0),
        "reverted": counts_map.get("reverted", 0)
    }

    # 2. DC Performance
    dcs = db.query(User).join(MasterUserRole, User.roleid == MasterUserRole.id).filter(MasterUserRole.role == "DC").all()
    dc_performance = []
    for dc_user in dcs:
        dist_name = "N/A"
        if dc_user.district_id:
            d_obj = db.query(District).filter(District.district_code == dc_user.district_id).first()
            if d_obj:
                dist_name = d_obj.district_name
        
        user_reqs = [r for r in all_act if r.dc_id == dc_user.id]
        total = len(user_reqs)
        approved = sum(1 for r in user_reqs if str(r.status or "").strip().lower() == "approved")
        rejected = sum(1 for r in user_reqs if str(r.status or "").strip().lower() == "rejected")
        pending = sum(1 for r in user_reqs if str(r.status or "").strip().lower() in ["pending", "sent_to_chips"])
        
        hours_list = []
        for r in user_reqs:
            if r.reviewed_at and r.submitted_at:
                try:
                    sub_dt = r.submitted_at
                    rev_dt = r.reviewed_at
                    h = max(0.0, (rev_dt - sub_dt).total_seconds() / 3600)
                    hours_list.append(h)
                except Exception:
                    pass
        avg_h = (sum(hours_list) / len(hours_list)) if hours_list else None

        dc_performance.append({
            "dc_name": dc_user.username,
            "district": dist_name,
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "avg_pending_hours": round(avg_h, 2) if avg_h is not None else None
        })

    # 3. Recent Requests
    recent_act = sorted(all_act, key=lambda r: r.submitted_at or datetime.min, reverse=True)[:10]
    recent_requests = []
    for r in recent_act:
        dist_name = "N/A"
        if r.district_id:
            d_obj = db.query(District).filter(District.district_code == r.district_id).first()
            if d_obj:
                dist_name = d_obj.district_name
        recent_requests.append({
            "id": r.id,
            "request_no": r.request_no or f"RP-A{r.id:04d}",
            "name_as_per_aadhaar": r.name_as_per_aadhaar,
            "district": dist_name,
            "status": r.status,
            "submitted_at": r.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if r.submitted_at else "N/A"
        })

    # 4. Operator Funnel
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
        nseit_rows = db.query(NSEITRequest).all()
        operator_funnel["nseit_done"] = sum(1 for r in nseit_rows if str(r.status or "").strip().lower() == "approved")
    except Exception:
        pass

    try:
        operator_funnel["activation_submitted"] = len(all_act)
    except Exception:
        pass

    try:
        act_sent = sum(1 for r in all_act if str(r.status or "").strip().lower() == "sent_to_uidai")
        all_react = db.query(OperatorReactivationRequest).all()
        react_sent = sum(1 for r in all_react if str(r.status or "").strip().lower() == "sent_to_uidai")
        operator_funnel["sent_to_uidai"] = act_sent + react_sent
    except Exception:
        pass

    try:
        act_app = sum(1 for r in all_act if str(r.status or "").strip().lower() == "approved")
        react_app = sum(1 for r in all_react if str(r.status or "").strip().lower() == "approved")
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
        today_date = date.today()
        in_30 = today_date + timedelta(days=30)

        try:
            nseit_analysis["expiring_soon"] = db.query(func.count(OperatorActivationRequest.id)).filter(
                OperatorActivationRequest.nseit_certificate_expiry_date != None,
                OperatorActivationRequest.nseit_certificate_expiry_date >= today_date,
                OperatorActivationRequest.nseit_certificate_expiry_date <= in_30,
            ).scalar() or 0
        except Exception:
            pass

        try:
            nseit_analysis["already_expired"] = db.query(func.count(OperatorActivationRequest.id)).filter(
                OperatorActivationRequest.nseit_certificate_expiry_date != None,
                OperatorActivationRequest.nseit_certificate_expiry_date < today_date,
            ).scalar() or 0
        except Exception:
            pass

        try:
            nseit_analysis["monthly_trend"] = _compute_monthly_trend(
                db, NSEITRequest, NSEITRequest.created_at, NSEITRequest.status, NSEITRequest.updated_at,
                approved_values=["Approved"],
                rejected_values=["Reverted", "Reverted by CHiPS", "reverted", "reverted_by_chips"],
            )
        except Exception:
            pass

        try:
            expiring_rows = db.query(
                OperatorActivationRequest.request_no,
                OperatorActivationRequest.name_as_per_aadhaar,
                OperatorActivationRequest.operator_mobile,
                OperatorActivationRequest.nseit_certificate_expiry_date,
            ).filter(
                OperatorActivationRequest.nseit_certificate_expiry_date != None,
                OperatorActivationRequest.nseit_certificate_expiry_date >= today_date,
                OperatorActivationRequest.nseit_certificate_expiry_date <= in_30,
            ).order_by(OperatorActivationRequest.nseit_certificate_expiry_date.asc()).all()

            nseit_analysis["expiring_soon_list"] = [
                {
                    "request_no": r.request_no or "N/A",
                    "name_as_per_aadhaar": r.name_as_per_aadhaar or "N/A",
                    "operator_mobile": r.operator_mobile or "N/A",
                    "nseit_certificate_expiry_date": r.nseit_certificate_expiry_date.strftime("%Y-%m-%d") if r.nseit_certificate_expiry_date else "N/A",
                    "days_remaining": (r.nseit_certificate_expiry_date.date() - today_date).days if r.nseit_certificate_expiry_date else 0,
                }
                for r in expiring_rows
            ]
        except Exception:
            pass

        try:
            expired_rows = db.query(
                OperatorActivationRequest.request_no,
                OperatorActivationRequest.name_as_per_aadhaar,
                OperatorActivationRequest.operator_mobile,
                OperatorActivationRequest.nseit_certificate_expiry_date,
            ).filter(
                OperatorActivationRequest.nseit_certificate_expiry_date != None,
                OperatorActivationRequest.nseit_certificate_expiry_date < today_date,
            ).order_by(OperatorActivationRequest.nseit_certificate_expiry_date.desc()).all()

            nseit_analysis["expired_list"] = [
                {
                    "request_no": r.request_no or "N/A",
                    "name_as_per_aadhaar": r.name_as_per_aadhaar or "N/A",
                    "operator_mobile": r.operator_mobile or "N/A",
                    "nseit_certificate_expiry_date": r.nseit_certificate_expiry_date.strftime("%Y-%m-%d") if r.nseit_certificate_expiry_date else "N/A",
                    "days_overdue": (today_date - r.nseit_certificate_expiry_date.date()).days if r.nseit_certificate_expiry_date else 0,
                }
                for r in expired_rows
            ]
        except Exception:
            pass
    except Exception:
        pass

    lms_analysis = {"monthly_trend": []}
    try:
        lms_analysis["monthly_trend"] = _compute_monthly_trend(
            db, LMS, LMS.created_at, LMS.status, LMS.updated_at,
            approved_values=["Approved"],
            rejected_values=["Reverted", "Reverted by CHiPS"],
        )
    except Exception:
        pass

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

    station_id_analysis = {"monthly_trend": []}
    try:
        station_id_analysis["monthly_trend"] = _compute_monthly_trend(
            db, StationIDRequest, StationIDRequest.submitted_at,
            StationIDRequest.status, StationIDRequest.reviewed_at,
            approved_values=["allotted", "approved", "activated"],
            rejected_values=["rejected", "reverted", "reverted_by_chips"],
        )
    except Exception:
        pass

    l1_analysis = {"monthly_trend": []}
    try:
        l1_analysis["monthly_trend"] = _compute_monthly_trend(
            db, L1RegistrationRequest, L1RegistrationRequest.created_at,
            L1RegistrationRequest.status, L1RegistrationRequest.updated_at,
            approved_values=["DONE", "REVIEWED", "APPROVED"],
            rejected_values=["REVERTED"],
        )
    except Exception:
        pass

    l2_analysis = {"monthly_trend": []}
    try:
        l2_analysis["monthly_trend"] = _compute_monthly_trend(
            db, L2RegistrationRequest, L2RegistrationRequest.submitted_at,
            L2RegistrationRequest.status, L2RegistrationRequest.submitted_at,
            approved_values=["approved", "activated"],
            rejected_values=["rejected", "reverted", "reverted_by_chips"],
        )
    except Exception:
        pass

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


@router.get("/chips/summary")
def get_chips_dashboard_summary(db: Session = Depends(get_db)):
    """Single-payload aggregated CHiPS Admin Dashboard endpoint."""
    stats = get_dashboard_stats(db)

    # 1. LMS List
    lms_raw = db.query(LMS, Candidate, District.district_name)\
        .join(Candidate, LMS.request_id == Candidate.id)\
        .outerjoin(District, Candidate.district == District.district_code).all()
    
    lms_requests = []
    for r, cand, dname in lms_raw:
        lms_requests.append({
            "r_id": r.request_id or r.id,
            "district": dname or "Unknown",
            "district_code": cand.district if cand else "",
            "name": cand.name if cand else "",
            "status": (r.status or "Pending").strip(),
            "submitted_days_ago": _days_ago(r.created_at),
            "lms_id": getattr(cand, "lms_id", "") or "",
        })

    # 2. NSEIT List
    nseit_raw = db.query(NSEITRequest, Candidate, District.district_name)\
        .join(Candidate, NSEITRequest.request_id == Candidate.id)\
        .outerjoin(District, Candidate.district == District.district_code).all()
    
    nseit_requests = []
    for r, cand, dname in nseit_raw:
        nseit_requests.append({
            "r_id": r.request_id or r.id,
            "district": dname or "Unknown",
            "district_code": cand.district if cand else "",
            "name": cand.name if cand else "",
            "status": (r.status or "Pending").strip(),
            "submitted_days_ago": _days_ago(r.created_at),
            "nseit_id": getattr(cand, "nseit_id", "") or "",
        })

    # 3. Activation List
    act_raw = db.query(OperatorActivationRequest, District.district_name)\
        .outerjoin(District, OperatorActivationRequest.district_id == District.district_code).all()
    
    activation_requests = []
    for r, dname in act_raw:
        submitted_at = r.submitted_at
        reviewed_at = r.reviewed_at
        resp_hours = None
        if reviewed_at and submitted_at:
            try:
                sub_dt = datetime.fromisoformat(str(submitted_at).replace("T", " ")[:19]) if isinstance(submitted_at, str) else submitted_at
                rev_dt = datetime.fromisoformat(str(reviewed_at).replace("T", " ")[:19]) if isinstance(reviewed_at, str) else reviewed_at
                resp_hours = max(0, (rev_dt - sub_dt).total_seconds() / 3600)
            except Exception:
                pass
        activation_requests.append({
            "id": r.id,
            "name": r.name_as_per_aadhaar or r.operator_name or "",
            "district": dname or "Unknown",
            "district_id": str(r.district_id or ""),
            "status": (r.status or "sent_to_chips").strip().lower(),
            "submitted_days_ago": _days_ago(submitted_at),
            "response_time_hours": resp_hours,
            "nseit_certificate_number": r.operator_aadhaar or "",
        })

    # 4. Station ID List
    station_raw = db.query(StationIDRequest, District.district_name)\
        .outerjoin(District, StationIDRequest.district_id == District.district_code).all()
    
    station_id_requests = []
    for r, dname in station_raw:
        station_id_requests.append({
            "id": r.id,
            "district": dname or "Unknown",
            "status": (r.status or "sent_to_chips").strip().lower(),
            "submitted_days_ago": _days_ago(r.submitted_at),
        })

    # 5. L2 List
    l2_raw = db.query(L2RegistrationRequest, District.district_name)\
        .outerjoin(District, L2RegistrationRequest.district_id == District.district_code).all()
    
    l2_requests = []
    for r, dname in l2_raw:
        submitted_at = r.submitted_at
        reviewed_at = getattr(r, "reviewed_at", None) if hasattr(r, "reviewed_at") else None
        resp_hours = None
        if reviewed_at and submitted_at:
            try:
                sub_dt = datetime.fromisoformat(str(submitted_at).replace("T", " ")[:19]) if isinstance(submitted_at, str) else submitted_at
                rev_dt = datetime.fromisoformat(str(reviewed_at).replace("T", " ")[:19]) if isinstance(reviewed_at, str) else reviewed_at
                resp_hours = max(0, (rev_dt - sub_dt).total_seconds() / 3600)
            except Exception:
                pass
        l2_requests.append({
            "id": r.id,
            "district": dname or "Unknown",
            "status": (r.status or "sent_to_chips").strip().lower(),
            "client_type": getattr(r, "client_type", ""),
            "submitted_days_ago": _days_ago(submitted_at),
            "response_time_hours": resp_hours,
        })

    # 6. L1 List
    l1_raw = db.query(L1RegistrationRequest, District.district_name)\
        .outerjoin(District, L1RegistrationRequest.district_id == District.district_code).all()
    
    l1_requests = []
    for r, dname in l1_raw:
        submitted_at = getattr(r, "submitted_at", r.created_at)
        reviewed_at = getattr(r, "reviewed_at", r.updated_at)
        resp_hours = None
        if reviewed_at and submitted_at:
            try:
                sub_dt = datetime.fromisoformat(str(submitted_at).replace("T", " ")[:19]) if isinstance(submitted_at, str) else submitted_at
                rev_dt = datetime.fromisoformat(str(reviewed_at).replace("T", " ")[:19]) if isinstance(reviewed_at, str) else reviewed_at
                resp_hours = max(0, (rev_dt - sub_dt).total_seconds() / 3600)
            except Exception:
                pass
        l1_requests.append({
            "id": r.id,
            "district": dname or "Unknown",
            "status": (r.status or "sent_to_chips").strip().lower(),
            "submitted_days_ago": _days_ago(submitted_at),
            "response_time_hours": resp_hours,
        })

    # 7. Reactivation List
    react_raw = db.query(OperatorReactivationRequest, District.district_name)\
        .outerjoin(District, OperatorReactivationRequest.district_id == District.district_code).all()
    
    reactivation_requests = []
    for r, dname in react_raw:
        dist = dname or "Unknown"
        created_at = getattr(r, "created_at", None)
        ops = getattr(r, "operators", None)
        if ops and isinstance(ops, list) and len(ops) > 0:
            for op in ops:
                op_status = str(getattr(op, "status", None) or r.status or "PENDING").strip().upper()
                reactivation_requests.append({
                    "id": getattr(op, "id", None) or r.id,
                    "district": dist,
                    "status": op_status,
                    "submitted_days_ago": _days_ago(created_at),
                    "operator_count": 1,
                })
        else:
            reactivation_requests.append({
                "id": r.id,
                "district": dist,
                "status": (r.status or "PENDING").strip().upper(),
                "submitted_days_ago": _days_ago(created_at),
                "operator_count": r.operator_count or 1,
            })

    # Districts list
    districts = db.query(District.district_name).order_by(District.district_name).all()
    dist_names = [d[0] for d in districts if d[0]]

    # District Resources Map
    resources = get_districts_with_resources(db)
    resources_map = {d["district_name"]: d.get("aadhaar_resources") for d in resources if isinstance(d, dict) and d.get("district_name")}

    return {
        "districts": dist_names,
        "lms_requests": lms_requests,
        "nseit_requests": nseit_requests,
        "activation_requests": activation_requests,
        "station_id_requests": station_id_requests,
        "l2_requests": l2_requests,
        "l1_requests": l1_requests,
        "reactivation_requests": reactivation_requests,
        "dcs": [],
        "district_resources": resources_map,
        "nseit_analysis": stats.get("nseit_analysis", {}),
        "operator_funnel": stats.get("operator_funnel", {}),
        "lms_analysis": stats.get("lms_analysis", {}),
        "activation_analysis": stats.get("activation_analysis", {}),
        "reactivation_analysis": stats.get("reactivation_analysis", {}),
        "station_id_analysis": stats.get("station_id_analysis", {}),
        "l1_analysis": stats.get("l1_analysis", {}),
        "l2_analysis": stats.get("l2_analysis", {}),
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
        today_date = date.today()
        in_30 = today_date + timedelta(days=30)

        rows = db.query(OperatorActivationRequest, District.district_name)\
            .outerjoin(District, OperatorActivationRequest.district_id == District.district_code)\
            .filter(
                OperatorActivationRequest.nseit_certificate_expiry_date != None,
                OperatorActivationRequest.nseit_certificate_expiry_date >= today_date,
                OperatorActivationRequest.nseit_certificate_expiry_date <= in_30,
            ).order_by(OperatorActivationRequest.nseit_certificate_expiry_date.asc()).all()

        result = []
        for req, district_name in rows:
            item = _serialize_nseit_row(req, district_name)
            item["days_remaining"] = (req.nseit_certificate_expiry_date.date() - today_date).days
            result.append(item)
        return result
    except Exception:
        return []


@router.get("/nseit/expired")
def get_nseit_expired(db: Session = Depends(get_db)):
    try:
        today_date = date.today()

        rows = db.query(OperatorActivationRequest, District.district_name)\
            .outerjoin(District, OperatorActivationRequest.district_id == District.district_code)\
            .filter(
                OperatorActivationRequest.nseit_certificate_expiry_date != None,
                OperatorActivationRequest.nseit_certificate_expiry_date < today_date,
            ).order_by(OperatorActivationRequest.nseit_certificate_expiry_date.desc()).all()

        result = []
        for req, district_name in rows:
            item = _serialize_nseit_row(req, district_name)
            item["days_overdue"] = (today_date - req.nseit_certificate_expiry_date.date()).days
            result.append(item)
        return result
    except Exception:
        return []


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


class DistrictSettingsUpdateWithCode(DistrictSettingsUpdate):
    district_code: Optional[str] = None


@router.put("/districts/{district_code}/settings")
@router.post("/districts/{district_code}/settings")
def update_district_settings(district_code: str, settings: DistrictSettingsUpdate, db: Session = Depends(get_db)):
    d = db.query(District).filter(District.district_code == district_code).first()
    if not d:
        raise HTTPException(status_code=404, detail="District not found")
        
    d.registration_open = 1 if settings.registration_open else 0
    d.registration_start_date = settings.registration_start_date
    d.registration_end_date = settings.registration_end_date
    
    if settings.registration_open:
        d.registration_opened_at = datetime.now().isoformat()
        
    db.commit()
    return {"message": "Settings updated successfully"}


@router.post("/districts/settings")
def update_district_settings_post(settings: DistrictSettingsUpdateWithCode, db: Session = Depends(get_db)):
    if not settings.district_code:
        raise HTTPException(status_code=400, detail="district_code is required")
    return update_district_settings(settings.district_code, settings, db)


@router.get("/districts-with-resources")
def get_districts_with_resources(db: Session = Depends(get_db)):
    districts = db.query(District).order_by(District.district_name).all()

    all_users = db.query(User).filter(
        User.district_id.isnot(None),
        User.is_active == 1
    ).options(joinedload(User.profile)).all()

    district_resources = {}
    for user in all_users:
        dist_id = user.district_id
        if dist_id not in district_resources:
            district_resources[dist_id] = {
                "edm_name": "", "edm_contact": "", "edm_email": "",
                "dc_name": "", "dc_contact": "", "dc_email": "",
                "mto_name": "", "mto_contact": "", "mto_email": "",
                "adc_name": "", "adc_contact": "", "adc_email": ""
            }
        
        profile = user.profile
        name = profile.full_name if (profile and profile.full_name) else ""
        contact = profile.phone if (profile and profile.phone) else ""
        email = profile.email if (profile and profile.email) else (user.username or "")

        if user.roleid == 3:
            district_resources[dist_id]["edm_name"] = name
            district_resources[dist_id]["edm_contact"] = contact
            district_resources[dist_id]["edm_email"] = email
        elif user.roleid == 2:
            district_resources[dist_id]["dc_name"] = name
            district_resources[dist_id]["dc_contact"] = contact
            district_resources[dist_id]["dc_email"] = email
        elif user.roleid == 5:
            district_resources[dist_id]["mto_name"] = name
            district_resources[dist_id]["mto_contact"] = contact
            district_resources[dist_id]["mto_email"] = email
        elif user.roleid == 6:
            district_resources[dist_id]["adc_name"] = name
            district_resources[dist_id]["adc_contact"] = contact
            district_resources[dist_id]["adc_email"] = email

    res = []
    for d in districts:
        res_info = district_resources.get(d.district_code)
        if not res_info:
            res_info = {
                "edm_name": "", "edm_contact": "", "edm_email": "",
                "dc_name": "Not Assigned", "dc_contact": "", "dc_email": "",
                "mto_name": "", "mto_contact": "", "mto_email": "",
                "adc_name": "", "adc_contact": "", "adc_email": ""
            }
        res.append({
            "district_code": d.district_code,
            "district_name": d.district_name,
            "district_short_name": d.district_short_name,
            "aadhaar_resources": res_info
        })
    return res
