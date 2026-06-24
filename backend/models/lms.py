from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_now, to_code, to_name, get_status_expression

class LMS(Base):
    __tablename__ = "LMS_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    r_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidate_table.r_id"), unique=True, nullable=False, name="R_Id")
    
    status_code: Mapped[str] = mapped_column(String(2), default="PE")

    @hybrid_property
    def status(self) -> str:
        return to_name(self.status_code, casing="title")

    @status.setter
    def status(self, value: str):
        self.status_code = to_code(value)

    @status.expression
    def status(cls):
        return get_status_expression(cls.status_code, casing="title")

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
    
    status_after_code: Mapped[str | None] = mapped_column(String(2), nullable=True)

    @hybrid_property
    def status_after(self) -> str | None:
        if self.status_after_code is None:
            return None
        return to_name(self.status_after_code, casing="title")

    @status_after.setter
    def status_after(self, value: str | None):
        if value is None:
            self.status_after_code = None
        else:
            self.status_after_code = to_code(value)

    @status_after.expression
    def status_after(cls):
        return get_status_expression(cls.status_after_code, casing="title")
    
    admin_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user_login_table.id"), nullable=True)
    candidate_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("candidate_login_table.id"), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    lms_request: Mapped[LMS] = relationship("LMS", back_populates="remarks")
    
    admin_author: Mapped["UserLogin | None"] = relationship("UserLogin", back_populates="lms_remarks_written", foreign_keys=[admin_by_id])
    candidate_author: Mapped["CandidateLogin | None"] = relationship("CandidateLogin", back_populates="lms_remarks_written", foreign_keys=[candidate_by_id])

