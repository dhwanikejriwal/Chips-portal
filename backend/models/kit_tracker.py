# backend/models/kit_tracker.py
"""Kit Tracker master table.

One row per Station ID, ingested from the operational "Kit Tracker.xlsx".
Free-text names are resolved to IDs where a matching master/dimension row
exists (district -> district_table, operator -> operators), while the raw
values are always kept so unmatched rows are never lost.
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.models.base import Base, get_ist_now


class KitTracker(Base):
    __tablename__ = "kit_tracker"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    sr_no = Column(Integer, nullable=True)

    # --- Linked IDs (resolved on ingest) ---
    district_code = Column(String(20), ForeignKey("district_table.district_code"), nullable=True, index=True)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=True, index=True)

    # --- Station identity ---
    kit_slot = Column(String(50), nullable=True)
    station_id = Column(String(50), nullable=False, unique=True, index=True)
    station_id_allotted_date = Column(Date, nullable=True)
    machine_id = Column(String(100), nullable=True)
    laptop_serial_no = Column(String(50), nullable=True)
    laptop_name = Column(String(100), nullable=True)

    # --- Raw operator values (kept even when operator_id is unmatched) ---
    operator_code_raw = Column(String(100), nullable=True)
    operator_name_raw = Column(String(120), nullable=True)
    operator_mobile_raw = Column(String(20), nullable=True)

    # --- Security deposit ---
    security_deposit_status = Column(String(30), nullable=True)   # Yes / None / Camp Mode
    security_deposit_date = Column(Date, nullable=True)

    # --- L1 / L2 (Yes / No / Sent To UIDAI) ---
    l1_status = Column(String(30), nullable=True)
    l1_date = Column(Date, nullable=True)
    l2_status = Column(String(30), nullable=True)
    l2_date = Column(Date, nullable=True)

    # --- Location / classification ---
    block = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)
    locality = Column(String(150), nullable=True)
    ask_address = Column(Text, nullable=True)

    # --- Operational status ---
    operator_status = Column(String(30), nullable=True)           # Active / Inactive
    inactive_reason = Column(String(255), nullable=True)
    inactive_date = Column(Date, nullable=True)
    permit_18_plus = Column(Integer, nullable=True)               # 1 / 0
    station_status = Column(String(30), nullable=True)
    onboarding_status = Column(String(30), nullable=True)
    onboard_date = Column(Date, nullable=True)
    kit_working = Column(Integer, nullable=True)                  # 1 / 0
    visit_status = Column(String(30), nullable=True)
    visit_date = Column(Date, nullable=True)
    remark = Column(Text, nullable=True)

    # --- Provenance ---
    batch_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=get_ist_now)
    updated_at = Column(DateTime, nullable=False, default=get_ist_now, onupdate=get_ist_now)

    district = relationship("District", foreign_keys=[district_code])
    operator = relationship("Operator", foreign_keys=[operator_id])
