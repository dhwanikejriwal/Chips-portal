# backend/models/reactivation.py
import enum
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, TEXT, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from backend.models.base import Base, get_ist_time

class RequestStatus(enum.Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    REVERTED = "REVERTED"
    REAPPLIED = "REAPPLIED"

class OperatorReactivationRequest(Base):
    __tablename__ = "operator_reactivation_requests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_code = Column(String(50), unique=True, nullable=True, index=True)

    # Information Parameters
    dc_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    district_id = Column(Integer, ForeignKey("districts.id", ondelete="RESTRICT"), nullable=False)
    operator_count = Column(Integer, nullable=False)
    training_date = Column(Date, nullable=False)
    
    # Sequential number tracking per district to formulate alphanumeric codes
    request_number = Column(Integer, nullable=False, default=1)
    
    # States & Auditing
    status = Column(SQLEnum(RequestStatus, name="requeststatus"), default=RequestStatus.PENDING, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=get_ist_time, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=get_ist_time, onupdate=get_ist_time, nullable=False)
    
    revert_reason = Column(String(500), nullable=True)
    remarks_history = Column(JSON, default=list, nullable=True)
    submitted_at = Column(DateTime(timezone=True), default=get_ist_time, nullable=False)

    # Core Bidirectional child maps
    documents = relationship("ReactivationDocument", back_populates="parent_request", cascade="all, delete-orphan")
    operators = relationship("ReactivationOperator", back_populates="parent_request", cascade="all, delete-orphan")

    # Explicit Cross-Table Relationships
    district_details = relationship("District")
    submitted_by = relationship("User")


class ReactivationDocument(Base):
    __tablename__ = "reactivation_documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    # FIX: Datatype matches the integer ID of the parent table primary key perfectly
    request_id = Column(Integer, ForeignKey("operator_reactivation_requests.id", ondelete="CASCADE"), nullable=False)
    doc_type = Column(String(50), nullable=False)  # training_photo, nodal_letter, om_letter, attendance_list
    file_path = Column(TEXT, nullable=False)
    original_filename = Column(String(255), nullable=False)
    
    parent_request = relationship("OperatorReactivationRequest", back_populates="documents")


class ReactivationOperator(Base):
    __tablename__ = "reactivation_operators"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    # FIX: Datatype matches the integer ID of the parent table primary key perfectly
    request_id = Column(Integer, ForeignKey("operator_reactivation_requests.id", ondelete="CASCADE"), nullable=False)
    operator_name = Column(String(150), nullable=False)
    operator_mobile = Column(String(20), nullable=True)
    
    parent_request = relationship("OperatorReactivationRequest", back_populates="operators")