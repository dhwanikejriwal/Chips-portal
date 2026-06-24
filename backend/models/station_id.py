from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_time, to_code, to_name, get_status_expression

class StationIDRequest(Base):
    __tablename__ = "station_id_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_no = Column(String(20), nullable=True, unique=True)
    dc_id = Column(Integer, ForeignKey("user_login_table.id"), nullable=False, index=True)
    district_id = Column(String(20), ForeignKey("district_table.district_code"), nullable=True, index=True)

    # Model: 'ECMP' (In house) or 'UCL'
    model = Column(String(10), nullable=False)

    # User type: 'new_user', 'machine_id', or 'custom'
    user_type = Column(String(20), nullable=False)
    user_type_custom_reason = Column(Text, nullable=True)  # filled when user_type == 'custom'

    number_of_kits = Column(Integer, nullable=False)

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

    # The actual Station ID string inserted by CHIPS Admin upon approval
    station_id_inserted = Column(Text, nullable=True)

    submitted_at = Column(DateTime, nullable=False, default=get_ist_time, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("user_login_table.id"), nullable=True)

    # Relationships
    dc = relationship("UserLogin", foreign_keys=[dc_id])
    reviewer = relationship("UserLogin", foreign_keys=[reviewed_by])
    district = relationship("District", foreign_keys=[district_id])
    remarks = relationship(
        "StationIDRemark",
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="StationIDRemark.created_at",
    )


class StationIDRemark(Base):
    """Chat / conversation history between DC and CHIPS Admin for a Station ID request."""

    __tablename__ = "station_id_remarks"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(
        Integer,
        ForeignKey("station_id_requests.id", ondelete="CASCADE"),
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

    request = relationship("StationIDRequest", back_populates="remarks")
    author = relationship("UserLogin", foreign_keys=[author_id])
