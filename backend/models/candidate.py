from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, Date, ForeignKey, DateTime, func, Boolean

if TYPE_CHECKING:
    from backend.models.district import District
    from backend.models.lms import LMS, LMSRemark
    from backend.models.nseit import NSEITRequest, NSEITRemark
    from backend.models.dc_remark import DCRemark
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_now, to_code, to_name

class Candidate(Base):
    __tablename__ = "candidate_table"

    r_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    mobile: Mapped[str] = mapped_column(String(15), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(20), ForeignKey("district_table.district_code"), nullable=False)
    qualification: Mapped[str] = mapped_column(String(100), nullable=False)
    lms_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nseit_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    exam_unique_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dob: Mapped[datetime] = mapped_column(Date, nullable=False)
    aadhaar: Mapped[str] = mapped_column(String(12), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_existing_operator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    photo_upload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    marksheet_upload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tenth_marksheet_upload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
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
    district_rel: Mapped["District"] = relationship("District", back_populates="candidates")
    login: Mapped["CandidateLogin | None"] = relationship("CandidateLogin", back_populates="candidate")
    lms_requests: Mapped[list["LMS"]] = relationship("LMS", back_populates="candidate")
    nseit_requests: Mapped[list["NSEITRequest"]] = relationship("NSEITRequest", back_populates="candidate")
    dc_remarks: Mapped[list["DCRemark"]] = relationship("DCRemark", back_populates="candidate")


class CandidateLogin(Base):
    __tablename__ = "candidate_login_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    r_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidate_table.r_id"), unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    has_changed_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    candidate: Mapped[Candidate] = relationship("Candidate", back_populates="login")
    
    lms_remarks_written: Mapped[list["LMSRemark"]] = relationship("LMSRemark", back_populates="candidate_author", foreign_keys="[LMSRemark.candidate_by_id]")
    
    nseit_remarks_written: Mapped[list["NSEITRemark"]] = relationship("NSEITRemark", back_populates="candidate_author", foreign_keys="[NSEITRemark.candidate_by_id]")
