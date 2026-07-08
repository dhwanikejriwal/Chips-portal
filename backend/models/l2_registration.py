from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_time, to_code, to_name, get_status_expression

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
    unique_id = Column(String(50), nullable=True)
    block = Column(String(100), nullable=False)
    address_of_govt_premises = Column(Text, nullable=False)

    status_code = Column(String(2), nullable=False, default="SC", index=True)

    @hybrid_property
    def status(self) -> str:
        return to_name(self.status_code, casing="lower")

    @status.setter
    def status(self, value: str):
        self.status_code = to_code(value)

    @status.expression
    def status(cls):
        return get_status_expression(cls.status_code, casing="lower")
        
    uidai_remarks = Column(Text, nullable=True)

    submitted_at = Column(DateTime, nullable=False, default=get_ist_time, index=True)
    # reviewed_at = Column(DateTime, nullable=True) # column does not exist in DB
    # completed_at = Column(DateTime, nullable=True) # column does not exist in DB
    # reviewed_by = Column(Integer, ForeignKey("user_login_table.id"), nullable=True) # column does not exist in DB

    # Relationships
    dc = relationship("UserLogin", foreign_keys=[dc_id])
    # reviewer = relationship("UserLogin", foreign_keys=[reviewed_by])
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
    
    status_after_code = Column(String(2), nullable=True)

    @hybrid_property
    def status_after(self) -> str | None:
        if self.status_after_code is None:
            return None
        return to_name(self.status_after_code, casing="lower")

    @status_after.setter
    def status_after(self, value: str | None):
        if value is None:
            self.status_after_code = None
        else:
            self.status_after_code = to_code(value)

    @status_after.expression
    def status_after(cls):
        return get_status_expression(cls.status_after_code, casing="lower")
        
    created_at = Column(DateTime, nullable=False, default=get_ist_time)

    request = relationship("L2RegistrationRequest", back_populates="remarks")
    author = relationship("UserLogin", foreign_keys=[author_id])
