from datetime import datetime
from sqlalchemy import String, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base, get_ist_now

class OtpVerification(Base):
    __tablename__ = "otp_verification_table"

    email: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)
    otp_code: Mapped[str] = mapped_column(String(10), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_verified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=get_ist_now, nullable=True, default=None)
