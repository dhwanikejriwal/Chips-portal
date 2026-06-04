import enum
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

def get_ist_time():
    # Naive datetime representing current time in IST (UTC + 5:30)
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

class UserRole(enum.Enum):
    DC = "DC"
    CHIPS_ADMIN = "CHIPS_ADMIN"

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
