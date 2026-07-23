from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Date
from backend.models.base import Base, get_ist_time

class Operator(Base):
    __tablename__ = "operators"

    id = Column(Integer, primary_key=True, index=True)
    user_code = Column(String(50), nullable=True, unique=True, index=True)
    name = Column(String(120), nullable=False)
    mobile = Column(String(15), nullable=True)
    email = Column(String(120), nullable=True)
    aadhaar_last4 = Column(String(4), nullable=True)
    pan_number = Column(String(10), nullable=True)
    role = Column(String(50), nullable=True)
    registrar_code = Column(String(50), nullable=True)
    ea_code = Column(String(50), nullable=True)
    nseit_certificate_number = Column(String(50), nullable=True)
    nseit_certification_date = Column(DateTime, nullable=True)
    nseit_certificate_expiry_date = Column(DateTime, nullable=True)
    pincode = Column(String(10), nullable=True)
    inactive_reason = Column(String(255), nullable=True)
    inactive_date = Column(Date, nullable=True)
    security_deposit_status = Column(String(50), nullable=True)
    security_deposit_date = Column(Date, nullable=True)
    
    # Status can be 'Active', 'Inactive', 'Suspended'
    status = Column(String(50), nullable=False, default="Inactive")
    
    mapped_dc_id = Column(Integer, ForeignKey("user_login_table.id"), nullable=True)
    district_id = Column(String(20), ForeignKey("district_table.district_code"), nullable=True)


    created_at = Column(DateTime, nullable=False, default=get_ist_time)
    updated_at = Column(DateTime, nullable=False, default=get_ist_time, onupdate=get_ist_time)
