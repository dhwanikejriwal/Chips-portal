# =====================================================================
# 📊 BACKEND SYSTEM GLOBAL STATUS STATES SPECIFICATION LOG
# =====================================================================
# The system utilizes strict uppercase snake_case string values to bypass 
# low-level Cython mapping LookupErrors when spaces exist in rows.
# Valid Status Tracking Indicators:
#   - "PENDING"       : Default state when DC submits a new batch request.
#   - "REVIEWED"      : Processed and finalized by a CHIPS Admin.
#   - "ASSIGNED"      : Approved routing advanced for structural assignment.
#   - "REVERTED"      : Sent back to the DC due to validation errors.
#   - "SENT_TO_UIDAI" : Formally advanced and submitted to UIDAI logs.
# =====================================================================

# backend/models/reactivation.py
import enum
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, TEXT
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_now, to_code, to_name

class OperatorReactivationRequest(Base):
    __tablename__ = "operator_reactivation_requests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_code = Column(String(50), unique=True, nullable=False, index=True)
    dc_id = Column(Integer, ForeignKey("user_login_table.id", ondelete="RESTRICT"), nullable=False)
    district_id = Column(String(20), ForeignKey("district_table.district_code", ondelete="RESTRICT"), nullable=False)
    operator_count = Column(Integer, nullable=False)
    training_date = Column(Date, nullable=False)
    
    status_id = Column(Integer, ForeignKey("master_status.id"), default=1, nullable=False, index=True)

    @hybrid_property
    def status(self) -> str:
        return to_name(self.status_id)

    @status.setter
    def status(self, value: str):
        self.status_id = to_code(value)
    created_at = Column(DateTime(timezone=True), default=get_ist_now, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=get_ist_now, onupdate=get_ist_now, nullable=False)
    reviewed_by = Column(Integer, ForeignKey("user_login_table.id"), nullable=True)

    operators = relationship("ReactivationOperator", back_populates="parent_request", cascade="all, delete-orphan")
    remarks = relationship("ReactivationRemarkHistory", back_populates="parent_request", cascade="all, delete-orphan")


class ReactivationOperator(Base):
    __tablename__ = "reactivation_operators"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("operator_reactivation_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=True)
    operator_name = Column(String(150), nullable=False)
    registrar_code = Column(String(50), nullable=True)
    ea_code = Column(String(50), nullable=True)
    user_code = Column(String(50), nullable=True)
    certificate_number = Column(String(100), nullable=True)
    
    lms_certificate_id = Column(String(100), nullable=True)
    
    operator_mobile = Column(String(20), nullable=False)
    email_id = Column(String(100), nullable=True)
    aadhaar_number = Column(String(20), nullable=True)
    certification_date = Column(Date, nullable=True)
    remarks = Column(String(250), nullable=True)
    model_type = Column(String(50), nullable=True)
    
    status_id = Column(Integer, ForeignKey("master_status.id"), default=1, nullable=False)

    @hybrid_property
    def status(self) -> str:
        return to_name(self.status_id)

    @status.setter
    def status(self, value: str):
        self.status_id = to_code(value)
    reject_reason = Column(String(500), nullable=True)

    parent_request = relationship("OperatorReactivationRequest", back_populates="operators")


class ReactivationRemarkHistory(Base):
    __tablename__ = "reactivation_remark_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("operator_reactivation_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    operator_id = Column(Integer, ForeignKey("reactivation_operators.id", ondelete="CASCADE"), nullable=True, index=True)
    remark_history = Column(TEXT, nullable=False)
    sender_role = Column(String(50), nullable=False)
    author_id = Column(Integer, ForeignKey("user_login_table.id"), nullable=True)
    
    status_after_id = Column(Integer, ForeignKey("master_status.id"), nullable=True)

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
    timestamp = Column(DateTime(timezone=True), default=get_ist_now, nullable=False)

    parent_request = relationship("OperatorReactivationRequest", back_populates="remarks")
    author = relationship("UserLogin")


class ReactivationDocument(Base):
    __tablename__ = "reactivation_documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("operator_reactivation_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type = Column(String(100), nullable=False)
    path = Column(String(500), nullable=False)
    original_filename = Column(String(250), nullable=False)
    file_size = Column(Integer, nullable=False)