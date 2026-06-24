from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_now, to_code, to_name, get_status_expression

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
    
    status_code = Column(String(2), default="PE")

    @hybrid_property
    def status(self) -> str:
        return to_name(self.status_code, casing="upper")

    @status.setter
    def status(self, value: str):
        self.status_code = to_code(value)

    @status.expression
    def status(cls):
        return get_status_expression(cls.status_code, casing="upper")
    
    created_at = Column(DateTime, default=get_ist_now)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now)

    district = relationship("District")
    remarks = relationship("L1RegistrationRemarkHistory", back_populates="parent_request", cascade="all, delete-orphan", order_by="L1RegistrationRemarkHistory.timestamp")


class L1RegistrationRemarkHistory(Base):
    __tablename__ = "l1_registration_remark_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_code = Column(String, ForeignKey("l1_registration_requests.request_code", ondelete="CASCADE"), nullable=False, index=True)
    remark = Column(String, nullable=False)
    
    status_after_code = Column(String(2), nullable=True)

    @hybrid_property
    def status_after(self) -> str | None:
        if self.status_after_code is None:
            return None
        return to_name(self.status_after_code, casing="upper")

    @status_after.setter
    def status_after(self, value: str | None):
        if value is None:
            self.status_after_code = None
        else:
            self.status_after_code = to_code(value)

    @status_after.expression
    def status_after(cls):
        return get_status_expression(cls.status_after_code, casing="upper")

    @property
    def action(self) -> str:
        return self.status_after or "SUBMITTED"

    @action.setter
    def action(self, value: str):
        self.status_after = value

    user_role = Column(String, nullable=False) # e.g. dc, chips_admin
    timestamp = Column(DateTime, default=get_ist_now, nullable=False)

    parent_request = relationship("L1RegistrationRequest", back_populates="remarks")
