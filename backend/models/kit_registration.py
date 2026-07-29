# backend/models/kit_registration.py
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from backend.models.base import Base, get_ist_now, to_name


class KitRegistration(Base):
    """Tracks L1/L2 kit-registration progress for each allotted Station ID.

    A row is created automatically when a Station ID request is allotted.
    L1 starts as Pending; when L1 is marked Done, L2 auto-starts as Pending;
    when L2 is marked Done the kit is fully registered.
    """
    __tablename__ = "kit_registration_table"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    request_no = Column(String(50), nullable=True, index=True)
    station_id = Column(String(50), nullable=False, unique=True, index=True)
    district = Column(String(100), nullable=True)
    machine_id = Column(String(255), nullable=True)
    laptop_serial_no = Column(String(255), nullable=True)
    laptop_name = Column(String(255), nullable=True)
    station_id_provided_date = Column(Date, nullable=True)
    block = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)
    locality = Column(String(100), nullable=True)
    ask_address = Column(String(255), nullable=True)
    station_status = Column(String(50), nullable=True)

    l1_status_id = Column(Integer, ForeignKey("master_status.id"), nullable=True)
    l1_done_date = Column(Date, nullable=True)
    l2_status_id = Column(Integer, ForeignKey("master_status.id"), nullable=True)
    l2_done_date = Column(Date, nullable=True)

    created_at = Column(DateTime, default=get_ist_now)
    updated_at = Column(DateTime, default=get_ist_now, onupdate=get_ist_now)

    # Convenience relationships to the master_status lookup for display names
    l1_status_ref = relationship("MasterStatus", foreign_keys=[l1_status_id])
    l2_status_ref = relationship("MasterStatus", foreign_keys=[l2_status_id])

    @hybrid_property
    def l1_status(self) -> str | None:
        return to_name(self.l1_status_id) if self.l1_status_id else None

    @hybrid_property
    def l2_status(self) -> str | None:
        return to_name(self.l2_status_id) if self.l2_status_id else None
