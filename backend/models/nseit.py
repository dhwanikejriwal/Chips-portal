from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_now, to_code, to_name, get_status_expression
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.candidate import Candidate, CandidateLogin
    from backend.models.user_login import UserLogin

class NSEITRequest(Base):
    __tablename__ = "nseit_request_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    r_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidate_table.r_id"), unique=True, nullable=False, name="R_Id")
    
    status_code: Mapped[str] = mapped_column(String(2), ForeignKey("master_status.code"), default="PE")

    @hybrid_property
    def status(self) -> str:
        return to_name(self.status_code)

    @status.setter
    def status(self, value: str):
        self.status_code = to_code(value)

    @status.expression
    def status(cls):
        return get_status_expression(cls.status_code)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=get_ist_now, nullable=True, default=None)

    # Relationships
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="nseit_requests")
    remarks: Mapped[list["NSEITRemark"]] = relationship("NSEITRemark", back_populates="nseit_request")


class NSEITRemark(Base):
    __tablename__ = "nseit_request_remark_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nseit_id: Mapped[int] = mapped_column(Integer, ForeignKey("nseit_request_table.id"), nullable=False, name="R_Id")
    remark: Mapped[str] = mapped_column(String(1000), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, nullable=False)
    
    status_after_code: Mapped[str | None] = mapped_column(String(2), ForeignKey("master_status.code"), nullable=True)

    @hybrid_property
    def status_after(self) -> str | None:
        if self.status_after_code is None:
            return None
        return to_name(self.status_after_code)

    @status_after.setter
    def status_after(self, value: str | None):
        if value is None:
            self.status_after_code = None
        else:
            self.status_after_code = to_code(value)

    @status_after.expression
    def status_after(cls):
        return get_status_expression(cls.status_after_code)
    
    admin_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("user_login_table.id"), nullable=True)
    candidate_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("candidate_login_table.id"), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    nseit_request: Mapped[NSEITRequest] = relationship("NSEITRequest", back_populates="remarks")
    
    admin_author: Mapped["UserLogin | None"] = relationship("UserLogin", back_populates="nseit_remarks_written", foreign_keys=[admin_by_id])
    candidate_author: Mapped["CandidateLogin | None"] = relationship("CandidateLogin", back_populates="nseit_remarks_written", foreign_keys=[candidate_by_id])

