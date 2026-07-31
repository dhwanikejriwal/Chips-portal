from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_now, to_code, to_name
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.candidate import Candidate, CandidateLogin
    from backend.models.user_login import UserLogin

class NSEITRequest(Base):
    __tablename__ = "nseit_request_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidate_table.id"), unique=True, nullable=False)
    
    status_id: Mapped[int] = mapped_column(Integer, ForeignKey("master_status.id"), default=1)

    @hybrid_property
    def status(self) -> str:
        return to_name(self.status_id)

    @status.setter
    def status(self, value: str):
        self.status_id = to_code(value)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=get_ist_now, nullable=True, default=None)

    # Relationships
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="nseit_requests")
    remarks: Mapped[list["NSEITRemark"]] = relationship("NSEITRemark", back_populates="nseit_request")


class NSEITRemark(Base):
    __tablename__ = "nseit_request_remark_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("nseit_request_table.id"), nullable=False)
    remark: Mapped[str] = mapped_column(String(1000), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime, default=get_ist_now, nullable=False)
    
    status_after_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("master_status.id"), nullable=True)

    @hybrid_property
    def status_after(self) -> str | None:
        if self.status_after_id is None:
            return None
        return to_name(self.status_after_id)

    @status_after.setter
    def status_after(self, value: str | None):
        if value is None:
            self.status_after_id = None
        else:
            self.status_after_id = to_code(value)
    
    sender_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    receiver_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_public: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    nseit_request: Mapped[NSEITRequest] = relationship("NSEITRequest", back_populates="remarks")
    
    sender_admin: Mapped["UserLogin | None"] = relationship("UserLogin", foreign_keys=[sender_id], primaryjoin="NSEITRemark.sender_id == UserLogin.id", viewonly=True)
    sender_candidate: Mapped["CandidateLogin | None"] = relationship("CandidateLogin", foreign_keys=[sender_id], primaryjoin="NSEITRemark.sender_id == CandidateLogin.id", viewonly=True)

    @property
    def is_candidate_sender(self) -> bool:
        if self.nseit_request and self.nseit_request.candidate and self.nseit_request.candidate.login:
            return self.sender_id == self.nseit_request.candidate.login.id
        return False

    @property
    def admin_by_id(self) -> int | None:
        return None if self.is_candidate_sender else self.sender_id

    @property
    def candidate_by_id(self) -> int | None:
        return self.sender_id if self.is_candidate_sender else None

    @property
    def admin_author(self) -> "UserLogin | None":
        return None if self.is_candidate_sender else self.sender_admin

    @property
    def candidate_author(self) -> "CandidateLogin | None":
        return self.sender_candidate if self.is_candidate_sender else None

