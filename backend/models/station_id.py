from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_time, to_code, to_name

class StationIDRequest(Base):
    __tablename__ = "station_id_requests"

    id = Column(Integer, primary_key=True, index=True)
    # Not unique: a batch allotment splits into one row per Station ID, all sharing the request_no.
    request_no = Column(String(20), nullable=True, index=True)
    dc_id = Column(Integer, ForeignKey("user_login_table.id"), nullable=False, index=True)
    district_id = Column(String(20), ForeignKey("district_table.district_code"), nullable=True, index=True)

    # Model: 'ECMP' (In house) or 'UCL'
    model = Column(String(10), nullable=False)

    # User type: 'new_user', 'machine_id', or 'custom'
    user_type = Column(String(20), nullable=False)
    user_type_custom_reason = Column(Text, nullable=True)  # filled when user_type == 'custom'

    number_of_kits = Column(Integer, nullable=False)

    # Slot type for the request: '937 slot' or '300 slot'
    slot = Column(String(20), nullable=True)

    status_id = Column(Integer, ForeignKey("master_status.id"), nullable=False, default=5, index=True) # 5 = SENT_TO_CHIPS

    @hybrid_property
    def status(self) -> str:
        return to_name(self.status_id)

    @status.setter
    def status(self, value: str):
        self.status_id = to_code(value)

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
    
    status_after_id = Column(Integer, ForeignKey("master_status.id"), nullable=True)

    @hybrid_property
    def status_after(self) -> str | None:
        if self.status_after_id is None:
            return None
        return to_name(self.status_after_id)

    @status_after.setter
    def status_after(self, value: str | None):
        if value is None:
            self.status_after_id = None
        else:
            self.status_after_id = to_code(value)
        
    created_at = Column(DateTime, nullable=False, default=get_ist_time)

    request = relationship("StationIDRequest", back_populates="remarks")
    author = relationship("UserLogin", foreign_keys=[author_id])
