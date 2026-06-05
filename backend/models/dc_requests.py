# backend/models/dc_requests.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.models.base import Base, get_ist_time

class NocRequest(Base):
    __tablename__ = "noc_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    operator_first_name = Column(String, nullable=False)
    operator_middle_name = Column(String, nullable=True)
    operator_last_name = Column(String, nullable=False)
    operator_email = Column(String, nullable=False)
    operator_phone = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, default=get_ist_time)
    accepted_at = Column(DateTime, nullable=True)
    
    district = relationship("District")

class ActivationRequest(Base):
    __tablename__ = "activation_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    operator_first_name = Column(String, nullable=False)
    operator_middle_name = Column(String, nullable=True)
    operator_last_name = Column(String, nullable=False)
    operator_email = Column(String, nullable=False)
    operator_phone = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, default=get_ist_time)
    accepted_at = Column(DateTime, nullable=True)
    
    district = relationship("District")

class ReactivationRequest(Base):
    __tablename__ = "reactivation_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False)
    operator_first_name = Column(String, nullable=False)
    operator_middle_name = Column(String, nullable=True)
    operator_last_name = Column(String, nullable=False)
    operator_email = Column(String, nullable=False)
    operator_phone = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, default=get_ist_time)
    accepted_at = Column(DateTime, nullable=True)
    
    district = relationship("District")
