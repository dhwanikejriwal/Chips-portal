# backend/routers/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from backend.database import get_db
from backend.models.operator_activation import OperatorActivationRequest
from backend.models.base import User, District, UserRole

router = APIRouter()

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
        District.name.label("district_name"),
        func.count(OperatorActivationRequest.id).label("total"),
        func.count(case((OperatorActivationRequest.status == "approved", 1))).label("approved"),
        func.count(case((OperatorActivationRequest.status == "rejected", 1))).label("rejected"),
        func.count(case((OperatorActivationRequest.status.in_(["pending", "sent_to_chips"]), 1))).label("pending"),
        func.avg(func.extract("epoch", OperatorActivationRequest.reviewed_at - OperatorActivationRequest.submitted_at) / 3600).label("avg_pending_hours")
    ).select_from(User)\
     .outerjoin(District, User.district_id == District.id)\
     .outerjoin(OperatorActivationRequest, User.id == OperatorActivationRequest.dc_id)\
     .filter(User.role == UserRole.DC)\
     .group_by(User.id, User.username, District.name)\
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
        District.name.label("district_name"),
        OperatorActivationRequest.status,
        OperatorActivationRequest.submitted_at
    ).select_from(OperatorActivationRequest)\
     .join(District, OperatorActivationRequest.district_id == District.id)\
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

    return {
        "summary": summary,
        "dc_performance": dc_performance,
        "recent_requests": recent_requests
    }
