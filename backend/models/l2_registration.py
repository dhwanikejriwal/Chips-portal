# backend/models/l2_registration.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from backend.models.base import Base, get_ist_time

class L2RegistrationRequest(Base):
    __tablename__ = "l2_registration_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_no = Column(String(20), nullable=True, unique=True)
    dc_id = Column(Integer, ForeignKey("user_login_table.id"), nullable=False, index=True)
    district_id = Column(String(20), ForeignKey("district_table.district_code"), nullable=True, index=True)

    client_version = Column(String(50), nullable=False)
    new_station_id = Column(String(50), nullable=False)
    ea_code = Column(String(50), nullable=False)
    reg_code = Column(String(50), nullable=False)
    new_machine_id = Column(String(50), nullable=False)
    client_type = Column(String(50), nullable=False)
    old_station_id = Column(String(50), nullable=True)
    reason_for_l2_registration = Column(Text, nullable=True)
    old_machine_id = Column(String(50), nullable=True)
    tech_center_remarks = Column(Text, nullable=True)
    operator_name = Column(String(100), nullable=False)
    operator_id = Column(String(50), nullable=False)
    # 🌟 FIXED: Changed nullable to True so the database can successfully save empty values when this field is left blank
    unique_id = Column(String(50), nullable=True)
    block = Column(String(100), nullable=False)
    address_of_govt_premises = Column(Text, nullable=False)

    status = Column(String(20), nullable=False, default="sent_to_chips", index=True)
    uidai_remarks = Column(Text, nullable=True)

    submitted_at = Column(DateTime, nullable=False, default=get_ist_time, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("user_login_table.id"), nullable=True)

    # Relationships
    dc = relationship("UserLogin", foreign_keys=[dc_id])
    reviewer = relationship("UserLogin", foreign_keys=[reviewed_by])
    district = relationship("District", foreign_keys=[district_id])
    remarks = relationship(
        "L2RegistrationRemark",
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="L2RegistrationRemark.created_at",
    )

class L2RegistrationRemark(Base):
    __tablename__ = "l2_registration_remarks"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(
        Integer,
        ForeignKey("l2_registration_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id = Column(Integer, ForeignKey("user_login_table.id"), nullable=False)
    author_role = Column(String(20), nullable=False)  # 'dc' or 'chips_admin'
    remark = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=get_ist_time)

    request = relationship("L2RegistrationRequest", back_populates="remarks")
    author = relationship("UserLogin", foreign_keys=[author_id])
