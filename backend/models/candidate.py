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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    is_existing_operator: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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
    document_record: Mapped["CandidateDocument | None"] = relationship("CandidateDocument", back_populates="candidate", cascade="all, delete-orphan", lazy="joined")

    def _get_or_create_doc_record(self) -> "CandidateDocument":
        if self.document_record is None:
            self.document_record = CandidateDocument()
        return self.document_record

    @property
    def photo_upload(self) -> str | None:
        return self.document_record.photo_upload if self.document_record else None

    @photo_upload.setter
    def photo_upload(self, value: str | None):
        self._get_or_create_doc_record().photo_upload = value

    @property
    def marksheet_upload(self) -> str | None:
        return self.document_record.marksheet_upload if self.document_record else None

    @marksheet_upload.setter
    def marksheet_upload(self, value: str | None):
        self._get_or_create_doc_record().marksheet_upload = value

    @property
    def tenth_marksheet_upload(self) -> str | None:
        return self.document_record.tenth_marksheet_upload if self.document_record else None

    @tenth_marksheet_upload.setter
    def tenth_marksheet_upload(self, value: str | None):
        self._get_or_create_doc_record().tenth_marksheet_upload = value

    @property
    def lms_certificate_upload(self) -> str | None:
        return self.document_record.lms_certificate_upload if self.document_record else None

    @lms_certificate_upload.setter
    def lms_certificate_upload(self, value: str | None):
        self._get_or_create_doc_record().lms_certificate_upload = value

    @property
    def nseit_certificate_upload(self) -> str | None:
        return self.document_record.nseit_certificate_upload if self.document_record else None

    @nseit_certificate_upload.setter
    def nseit_certificate_upload(self, value: str | None):
        self._get_or_create_doc_record().nseit_certificate_upload = value


class CandidateDocument(Base):
    __tablename__ = "candidate_document_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidate_table.id", ondelete="CASCADE"), unique=True, nullable=False)
    photo_upload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    marksheet_upload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tenth_marksheet_upload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lms_certificate_upload: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nseit_certificate_upload: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    candidate: Mapped["Candidate"] = relationship("Candidate", back_populates="document_record")


class CandidateLogin(Base):
    __tablename__ = "candidate_login_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("candidate_table.id"), unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    has_changed_password: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    candidate: Mapped[Candidate] = relationship("Candidate", back_populates="login")
    
    lms_remarks_written: Mapped[list["LMSRemark"]] = relationship("LMSRemark", foreign_keys="[LMSRemark.sender_id]", primaryjoin="LMSRemark.sender_id == CandidateLogin.id", viewonly=True)
    
    nseit_remarks_written: Mapped[list["NSEITRemark"]] = relationship("NSEITRemark", foreign_keys="[NSEITRemark.sender_id]", primaryjoin="NSEITRemark.sender_id == CandidateLogin.id", viewonly=True)
