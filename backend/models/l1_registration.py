from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.models.base import Base, get_ist_now

class L1RegistrationRequest(Base):
    __tablename__ = "l1_registration_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_code = Column(String, unique=True, index=True, nullable=False)
    district_id = Column(String(20), ForeignKey("district_table.district_code"), nullable=False)
    
    station_id = Column(String, nullable=False)
    machine_id = Column(String, nullable=False)
    operator_name = Column(String, nullable=True)
    operator_id = Column(String, nullable=True)
    model_type = Column(String, nullable=False)
    software_version = Column(String, nullable=False)
    uv_id = Column(String, nullable=False)
    uv_password = Column(String, nullable=False)
    
    status = Column(String, default="PENDING")  # PENDING, REAPPLIED, REVIEWED, REVERTED
    
    created_at = Column(DateTime, default=get_ist_now)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now)

    district = relationship("District")
    remarks = relationship("L1RegistrationRemarkHistory", back_populates="parent_request", cascade="all, delete-orphan", order_by="L1RegistrationRemarkHistory.timestamp")


class L1RegistrationRemarkHistory(Base):
    __tablename__ = "l1_registration_remark_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_code = Column(String, ForeignKey("l1_registration_requests.request_code", ondelete="CASCADE"), nullable=False, index=True)
    remark = Column(String, nullable=False)
    action = Column(String, nullable=False) # e.g. SUBMITTED, REVERTED, REAPPLIED, REVIEWED
    user_role = Column(String, nullable=False) # e.g. dc, chips_admin
    timestamp = Column(DateTime, default=get_ist_now, nullable=False)

    parent_request = relationship("L1RegistrationRequest", back_populates="remarks")
