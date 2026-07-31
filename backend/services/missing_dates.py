# backend/services/missing_dates.py
"""Detect dates with no RegistrarEA activity upload and surface them as reminders.

The RegistrarEA file is expected daily. Walking from the tracking-start (or the
earliest date we already have) up to *yesterday*, any date absent from
activity_daily_upload_log is a gap the operator must be reminded to upload.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.base import get_ist_now
from backend.models.operator_daily_activity import ActivityDailyUploadLog
from backend.services import activity_config as cfg

# In-process cache of the latest computed gaps, refreshed on each upload and on
# demand. Kept simple (no extra table) since it is cheap to recompute.
_cache: dict = {"missing": [], "computed_at": None}


def compute_missing_dates(db: Session) -> list[date]:
    covered = {row[0] for row in db.query(ActivityDailyUploadLog.activity_date).all()}
    if not covered and cfg.ACTIVITY_TRACKING_START is None:
        return []

    start = cfg.ACTIVITY_TRACKING_START or min(covered)
    yesterday = get_ist_now().date() - timedelta(days=1)
    if start > yesterday:
        return []

    missing = []
    d = start
    while d <= yesterday:
        if d not in covered:
            missing.append(d)
        d += timedelta(days=1)
    return missing


def refresh_missing_dates(db: Session) -> list[date]:
    missing = compute_missing_dates(db)
    _cache["missing"] = missing
    _cache["computed_at"] = get_ist_now()
    return missing


def get_missing_dates(db: Session, force: bool = False) -> list[date]:
    if force or _cache["computed_at"] is None:
        return refresh_missing_dates(db)
    return _cache["missing"]


def build_reminder(db: Session) -> dict | None:
    """Notification-bell payload for missing activity uploads (Admin/EDM)."""
    missing = get_missing_dates(db)
    if not missing:
        return None
    shown = [d.strftime("%d %b %Y") for d in missing[-10:]]
    return {
        "type": "operator_activity_missing",
        "count": len(missing),
        "label": "Operator activity data missing",
        "dates": [d.isoformat() for d in missing],
        "message": (
            f"Operator activity data missing for {len(missing)} date(s): "
            + ", ".join(shown) + ("…" if len(missing) > 10 else "")
        ),
    }
