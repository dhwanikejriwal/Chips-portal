import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum as SQLEnum, DateTime, ForeignKey, JSON, Boolean, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_time, get_ist_now, to_code, to_name, get_status_expression

class RequestStatus(enum.Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    REVERTED = "REVERTED"
    REAPPLIED = "REAPPLIED"

class CredentialRequest(Base):
    __tablename__ = "credential_requests"
    
    id = Column(Integer, primary_key=True)
    request_code = Column(String(20), unique=True, nullable=True, index=True)
    
    # Operator Information parameters
    operator_first_name = Column(String(100), nullable=False)
    operator_middle_name = Column(String(100), nullable=True)
    operator_last_name = Column(String(100), nullable=False)
    operator_phone = Column(String(15), nullable=False)
    operator_email = Column(String(150), nullable=False)
    
    # Tracking references
    district_id = Column(Integer, ForeignKey("district_table.id"), nullable=False)
    submitted_by_id = Column(Integer, ForeignKey("user_login_table.id"), nullable=False)
    
    # States
    status = Column(SQLEnum(RequestStatus, name="requeststatus"), default=RequestStatus.PENDING, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=get_ist_time, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=get_ist_time, onupdate=get_ist_time, nullable=False)
    
    # Credentials
    generated_login_id = Column(String(100), unique=True, nullable=True)
    generated_password_raw = Column(String(100), nullable=True)
    revert_reason = Column(String(500), nullable=True)
    remarks_history = Column(JSON, default=list, nullable=True)
    
    # Relationships
    district_details = relationship("District", foreign_keys=[district_id])
    submitted_by = relationship("User", foreign_keys=[submitted_by_id])

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
