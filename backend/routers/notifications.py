from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.routers.auth import get_current_user, get_current_session
from backend.models import UserLogin
from backend.notification_utils import compute_notification_snapshot

router = APIRouter()


@router.get("/notifications/summary")
def get_notifications_summary(
    current_user: UserLogin = Depends(get_current_user),
    current_session=Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Notification-bell data for the CURRENT session only.

    baseline_at is fixed for the session's lifetime (the previous session's
    login_time for this same user, across any device), but the counts are
    queried live against it on every call — so requests that arrive during
    this session do show up. The cutoff only moves forward on the next fresh
    login, which is what keeps a session's view independent from other
    devices and from requests that arrive after this session ends.
    """
    if current_user.role.role not in ("Admin", "DC", "EDM"):
        raise HTTPException(status_code=403, detail="Not authorized")
    if current_session is None:
        raise HTTPException(status_code=403, detail="No active session found")

    admin_type = "chips_admin" if current_user.role.role == "Admin" else "dc_admin"
    return compute_notification_snapshot(
        admin_type,
        current_user.district_id if admin_type == "dc_admin" else None,
        current_session.baseline_at,
        db,
    )
