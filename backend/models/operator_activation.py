from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_time, to_code, to_name, get_status_expression


class OperatorActivationRequest(Base):
    __tablename__ = "operator_activation_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_no = Column(String(20), nullable=True, unique=True)
    dc_id = Column(Integer, ForeignKey("user_login_table.id"), nullable=False, index=True)
    district_id = Column(
        String(20), ForeignKey("district_table.district_code"), nullable=True, index=True
    )
    role = Column(String(50), nullable=True)
    name_as_per_aadhaar = Column(String(120), nullable=False)
    registrar_code = Column(String(50), nullable=True)
    ea_code = Column(String(50), nullable=True)
    user_code = Column(String(50), nullable=True)
    nseit_certificate_number = Column(String(50), nullable=True)
    operator_mobile = Column(String(15), nullable=False)
    primary_email = Column(String(120), nullable=True)
    operator_aadhaar = Column(String(4), nullable=True)  # Last 4 digits only
    pan_number = Column(String(10), nullable=True)
    nseit_certification_date = Column(DateTime, nullable=True)
    nseit_certificate_expiry_date = Column(DateTime, nullable=True)
    pincode = Column(String(10), nullable=True)
    
    status_code = Column(String(2), nullable=False, default="SC", index=True)

    @hybrid_property
    def status(self) -> str:
        return to_name(self.status_code, casing="lower")

    @status.setter
    def status(self, value: str):
        self.status_code = to_code(value)

    @status.expression
    def status(cls):
        return get_status_expression(cls.status_code, casing="lower")
        

    submitted_at = Column(DateTime, nullable=False, default=get_ist_time, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("user_login_table.id"), nullable=True, index=True)

    # Relationships
    dc = relationship("UserLogin", foreign_keys=[dc_id])
    reviewer = relationship("UserLogin", foreign_keys=[reviewed_by])
    district = relationship("District", foreign_keys=[district_id])
    documents = relationship(
        "ActivationDocument", back_populates="request", cascade="all, delete-orphan"
    )
    remarks = relationship(
        "OperatorActivationRemark",
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="OperatorActivationRemark.created_at",
    )


class ActivationDocument(Base):
    __tablename__ = "activation_documents"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(
        Integer,
        ForeignKey("operator_activation_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # One of: hard_copy_form | aadhaar_photo | pan_card | passbook | nseit_certificate | excel_sheet
    doc_type = Column(String(40), nullable=False)

    file_path = Column(
        Text, nullable=False
    )  # Server path: /uploads/{dc_id}/{request_id}/{doc_type}.ext
    original_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)  # e.g. application/pdf, image/jpeg

    uploaded_at = Column(DateTime, nullable=False, default=get_ist_time)

    # Relationship
    request = relationship("OperatorActivationRequest", back_populates="documents")

    # Ensures each request can only have one of each document type
    __table_args__ = (
        UniqueConstraint(
            "request_id", "doc_type", name="uq_activation_doc_request_doctype"
        ),
    )


class OperatorActivationRemark(Base):
    __tablename__ = "operator_activation_remarks"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(
        Integer,
        ForeignKey("operator_activation_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id = Column(Integer, ForeignKey("user_login_table.id"), nullable=False)
    author_role = Column(String(20), nullable=False)  # 'dc' or 'chips_admin'
    remark = Column(Text, nullable=False)
    
    status_after_code = Column(String(2), nullable=True)

    @hybrid_property
    def status_after(self) -> str | None:
        if self.status_after_code is None:
            return None
        return to_name(self.status_after_code, casing="lower")

    @status_after.setter
    def status_after(self, value: str | None):
        if value is None:
            self.status_after_code = None
        else:
            self.status_after_code = to_code(value)

    @status_after.expression
    def status_after(cls):
        return get_status_expression(cls.status_after_code, casing="lower")
        
    created_at = Column(DateTime, nullable=False, default=get_ist_time)

    request = relationship("OperatorActivationRequest", back_populates="remarks")
    author = relationship("UserLogin", foreign_keys=[author_id])
