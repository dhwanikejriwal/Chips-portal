# backend/models.py
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey
from backend.database import Base

class UserRole(str, enum.Enum):
    DC          = "dc"
    CHIPS_ADMIN = "chips_admin"

class RequestStatus(str, enum.Enum):
    PENDING  = "pending"
    ASSIGNED = "assigned"

class District(Base):
    __tablename__ = "districts"
    id   = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)

class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True)
    username      = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role          = Column(String(20), nullable=False, default="dc")
    district_id   = Column(Integer, ForeignKey("districts.id"), nullable=True)

class CredentialRequest(Base):
    __tablename__ = "credential_requests"
    id                    = Column(Integer, primary_key=True)
    operator_first_name   = Column(String(100), nullable=False)
    operator_middle_name  = Column(String(100), nullable=True)
    operator_last_name    = Column(String(100), nullable=False)
    operator_phone        = Column(String(15),  nullable=False)
    operator_email        = Column(String(150), nullable=False)
    district_id           = Column(Integer, ForeignKey("districts.id"), nullable=False)
    submitted_by_id       = Column(Integer, ForeignKey("users.id"),     nullable=False)
    status                = Column(String(20), default="pending", nullable=False)
    created_at            = Column(DateTime, default=datetime.utcnow, nullable=False)
    generated_login_id    = Column(String(100), nullable=True)
    generated_password_raw = Column(String(100), nullable=True)