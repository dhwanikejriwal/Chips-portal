import enum
from sqlalchemy import Column, Integer, String, Enum as SQLEnum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base
from backend.models.base import get_ist_time

class RequestStatus(enum.Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"

class CredentialRequest(Base):
    __tablename__ = "credential_requests"
    
    id = Column(Integer, primary_key=True)
    
    # Operator Information parameters
    operator_first_name = Column(String(100), nullable=False)
    operator_middle_name = Column(String(100), nullable=True)
    operator_last_name = Column(String(100), nullable=False)
    operator_phone = Column(String(15), nullable=False)
    operator_email = Column(String(150), nullable=False)
    
    # Tracking references
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    submitted_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # States
    status = Column(SQLEnum(RequestStatus, name="requeststatus"), default=RequestStatus.PENDING, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=get_ist_time, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=get_ist_time, onupdate=get_ist_time, nullable=False)
    
    # Credentials
    generated_login_id = Column(String(100), unique=True, nullable=True)
    generated_password_raw = Column(String(100), nullable=True)
    
    # Relationships
    district_details = relationship("District", back_populates="requests")
    submitted_by = relationship("User", back_populates="requests")
