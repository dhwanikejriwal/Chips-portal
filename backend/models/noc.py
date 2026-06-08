# backend/models/noc.py
from sqlalchemy import Column, Integer, String, Enum as SQLEnum, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from backend.models.base import Base, get_ist_time
from backend.models.lms import RequestStatus

class NocRequest(Base):
    __tablename__ = "noc_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    request_code = Column(String(50), unique=True, nullable=True, index=True)
    
    # Operator Information parameters
    operator_unique_id = Column(String(100), nullable=False)
    operator_first_name = Column(String(100), nullable=False)
    operator_middle_name = Column(String(100), nullable=True)
    operator_last_name = Column(String(100), nullable=False)
    
    # Tracking references
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    submitted_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # States
    status = Column(SQLEnum(RequestStatus, name="requeststatus"), default=RequestStatus.PENDING, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=get_ist_time, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=get_ist_time, onupdate=get_ist_time, nullable=False)
    
    # Credentials / Details
    revert_reason = Column(String(500), nullable=True)
    remarks_history = Column(JSON, default=list, nullable=True)
    
    # Relationships
    district = relationship("District")
    submitted_by = relationship("User")
