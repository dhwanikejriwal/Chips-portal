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
from backend.models.base import Base, get_ist_now

class OperatorReactivationRequest(Base):
    __tablename__ = "operator_reactivation_requests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_code = Column(String(50), unique=True, nullable=False, index=True)
    dc_id = Column(Integer, ForeignKey("user_login_table.id", ondelete="RESTRICT"), nullable=False)
    district_id = Column(String(20), ForeignKey("district_table.district_code", ondelete="RESTRICT"), nullable=False)
    operator_count = Column(Integer, nullable=False)
    training_date = Column(Date, nullable=False)
    
    # Standard string tracking completely removes space character constraints
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=get_ist_now, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=get_ist_now, onupdate=get_ist_now, nullable=False)
    reject_reason = Column(String(500), nullable=True)

    operators = relationship("ReactivationOperator", back_populates="parent_request", cascade="all, delete-orphan")
    remarks = relationship("ReactivationRemarkHistory", back_populates="parent_request", cascade="all, delete-orphan")


class ReactivationOperator(Base):
    __tablename__ = "reactivation_operators"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_code = Column(String(50), ForeignKey("operator_reactivation_requests.request_code", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=True)
    operator_name = Column(String(150), nullable=False)
    registrar_code = Column(String(50), nullable=True)
    ea_code = Column(String(50), nullable=True)
    user_code = Column(String(50), nullable=True)
    certificate_number = Column(String(100), nullable=True)
    
    # LMS Certificate ID explicitly added to model class schema structure
    lms_certificate_id = Column(String(100), nullable=True)
    
    operator_mobile = Column(String(20), nullable=False)
    email_id = Column(String(100), nullable=True)
    aadhaar_number = Column(String(20), nullable=True)
    certification_date = Column(Date, nullable=True)
    remarks = Column(String(250), nullable=True)
    model_type = Column(String(50), nullable=True)
    status = Column(String(50), default="PENDING", nullable=False)
    reject_reason = Column(String(500), nullable=True)

    parent_request = relationship("OperatorReactivationRequest", back_populates="operators")


class ReactivationRemarkHistory(Base):
    __tablename__ = "reactivation_remark_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_code = Column(String(50), ForeignKey("operator_reactivation_requests.request_code", ondelete="CASCADE"), nullable=False, index=True)
    remark_history = Column(TEXT, nullable=False)
    sender_role = Column(String(50), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=get_ist_now, nullable=False)

    parent_request = relationship("OperatorReactivationRequest", back_populates="remarks")


class ReactivationDocument(Base):
    __tablename__ = "reactivation_documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_code = Column(String(50), ForeignKey("operator_reactivation_requests.request_code", ondelete="CASCADE"), nullable=False, index=True)
    doc_type = Column(String(100), nullable=False)
    path = Column(String(500), nullable=False)
    original_filename = Column(String(250), nullable=False)
    file_size = Column(Integer, nullable=False)