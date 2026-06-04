import enum
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Enum as SQLEnum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

def get_ist_time():
    # Naive datetime representing current time in IST (UTC + 5:30)
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

class UserRole(enum.Enum):
    DC = "DC"
    CHIPS_ADMIN = "CHIPS_ADMIN"

class RequestStatus(enum.Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"

class District(Base):
    __tablename__ = "districts"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    
    # Relationships
    users = relationship("User", back_populates="district_details", cascade="all, delete-orphan")
    requests = relationship("CredentialRequest", back_populates="district_details", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole, name="userrole"), nullable=False, default=UserRole.DC)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=True)
    
    # Relationships
    district_details = relationship("District", back_populates="users")
    requests = relationship("CredentialRequest", back_populates="submitted_by")

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
