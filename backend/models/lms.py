from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.models.base import Base, get_ist_now

class LMS(Base):
    __tablename__ = "LMS_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    r_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidate_table.r_id"), unique=True, nullable=False, name="R_Id")
    status: Mapped[str] = mapped_column(String(50), default="Pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=get_ist_now, nullable=True, default=None)

    # Relationships
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="lms_requests")
    remarks: Mapped[list["LMSRemark"]] = relationship("LMSRemark", back_populates="lms_request")


class LMSRemark(Base):
    __tablename__ = "lms_remark_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lms_id: Mapped[int] = mapped_column(Integer, ForeignKey("LMS_table.id"), nullable=False, name="R_id")
    remark: Mapped[str] = mapped_column(String(1000), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, nullable=False)
    status_after: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    admin_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user_login_table.id"), nullable=True)
    candidate_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("candidate_login_table.id"), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    lms_request: Mapped[LMS] = relationship("LMS", back_populates="remarks")
    
    admin_author: Mapped["UserLogin | None"] = relationship("UserLogin", back_populates="lms_remarks_written", foreign_keys=[admin_by_id])
    candidate_author: Mapped["CandidateLogin | None"] = relationship("CandidateLogin", back_populates="lms_remarks_written", foreign_keys=[candidate_by_id])

