from datetime import datetime
from sqlalchemy import Integer, DateTime, Boolean, Enum, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, get_ist_now

class AdminLoginLog(Base):
    """One row per login session. Also doubles as the notification-bell session record:
    baseline_at is fixed at login (see backend/routers/auth.py) and used to query
    notification counts live on every request (see backend/utils/notification_utils.py)."""

    __tablename__ = "admin_login_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    admin_type: Mapped[str] = mapped_column(
        Enum("chips_admin", "dc_admin", name="admin_type_enum"),
        nullable=False
    )
    login_time: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, nullable=False)
    logout_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_current: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)

    # Previous session's login_time for this same admin (or this session's own
    # login_time if there was no previous session) — the notification cutoff.
    baseline_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_admin_login_logs_lookup", "admin_id", "admin_type", "is_current"),
    )
