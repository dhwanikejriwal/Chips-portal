# backend/models/operator_daily_activity.py
"""Operator Activity data model (from the RegistrarEA daily upload).

Only the *aggregated* result of the filter+group-by is persisted here; the
uploaded Excel/CSV is processed in bounded memory (DuckDB) and discarded.

Tables:
  - operator_daily_activity : the fact table (one row per operator/station/day)
  - activity_stations       : station dimension (factored-out machine_address)
  - operator_activity_master: operator dimension keyed on session_operator_id
  - activity_upload_batch   : upload job tracking / history
  - activity_daily_upload_log: which dates have data (drives missing-date reminders)
"""
from sqlalchemy import (
    Column, Integer, BigInteger, String, Text, Date, DateTime, Numeric,
    ForeignKey, ForeignKeyConstraint, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from backend.models.base import Base, get_ist_now


class OperatorDailyActivity(Base):
    __tablename__ = "operator_daily_activity"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    activity_date = Column(Date, nullable=False)
    station_ea_code = Column(Integer, nullable=False)
    session_operator_id = Column(String(120), nullable=False)
    station_number = Column(Integer, nullable=False)
    machine_district = Column(String(120), nullable=True)

    # Business measures (all summed on aggregate)
    New_Aadhaar_Enrolment = Column(Integer, nullable=False, default=0)
    New_Aadhar_18_plus = Column(Integer, nullable=False, default=0)
    Total_Updates = Column(Integer, nullable=False, default=0)
    Total_Demographic_Updates = Column(Integer, nullable=False, default=0)
    Total_Biometric_Updates = Column(Integer, nullable=False, default=0)
    NON_MBU = Column(Integer, nullable=False, default=0)
    IS_MBU = Column(Integer, nullable=False, default=0)
    COUNT_6AM_TO_10PM = Column(Integer, nullable=False, default=0)
    COUNT_10PM_TO_6AM = Column(Integer, nullable=False, default=0)
    Total_Enrollment_and_Updates = Column(Integer, nullable=False, default=0)

    batch_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=get_ist_now)

    __table_args__ = (
        UniqueConstraint(
            "activity_date", "station_ea_code", "session_operator_id", "station_number",
            name="uq_operator_daily_activity_key",
        ),
        Index("ix_oda_date", "activity_date"),
        Index("ix_oda_operator_date", "session_operator_id", "activity_date"),
        Index("ix_oda_district_date", "machine_district", "activity_date"),
    )


class ActivityStation(Base):
    __tablename__ = "activity_stations"

    station_ea_code = Column(Integer, primary_key=True)
    station_number = Column(Integer, primary_key=True)
    machine_address = Column(Text, nullable=True)
    machine_district = Column(String(120), nullable=True)
    machine_state = Column(String(120), nullable=True)
    machine_pincode = Column(String(12), nullable=True)
    machine_lat = Column(String(40), nullable=True)
    machine_long = Column(String(40), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=get_ist_now, onupdate=get_ist_now)


class OperatorActivityMaster(Base):
    """Operator dimension for the activity data.

    Keyed on the UIDAI session_operator_id (e.g. '2084_S_Tawarilata'), which is
    NOT the portal's operators.user_code, so this is a separate dimension with an
    optional link back to `operators` when a match is found. Auto-stubbed on first
    sighting so the drill-down never 404s.
    """
    __tablename__ = "operator_activity_master"

    session_operator_id = Column(String(120), primary_key=True)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=True, index=True)

    operator_name = Column(String(120), nullable=True)
    operator_photo_url = Column(String(255), nullable=True)
    mobile_number = Column(String(20), nullable=True)
    email = Column(String(120), nullable=True)
    aadhaar_last4 = Column(String(4), nullable=True)
    onboarding_date = Column(Date, nullable=True)

    certification_id = Column(String(60), nullable=True)
    certification_expiry_date = Column(Date, nullable=True)

    security_deposit_amount = Column(Numeric(12, 2), nullable=True)
    security_deposit_paid_on = Column(Date, nullable=True)
    security_deposit_txn_ref = Column(String(80), nullable=True)
    security_deposit_status = Column(String(20), nullable=True)   # PAID / PENDING / REFUNDED

    agency_name = Column(String(120), nullable=True)
    supervisor_name = Column(String(120), nullable=True)
    current_status = Column(String(20), nullable=True, default="ACTIVE")  # ACTIVE / SUSPENDED / DEACTIVATED
    status_changed_on = Column(Date, nullable=True)
    remarks = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=get_ist_now)
    updated_at = Column(DateTime, nullable=False, default=get_ist_now, onupdate=get_ist_now)

    operator = relationship("Operator", foreign_keys=[operator_id])


class ActivityUploadBatch(Base):
    __tablename__ = "activity_upload_batch"

    batch_id = Column(String(36), primary_key=True)
    source = Column(String(30), nullable=False)          # kit_tracker | registrar_ea
    filename = Column(String(255), nullable=True)
    uploaded_by = Column(String(120), nullable=True)
    uploaded_at = Column(DateTime, nullable=False, default=get_ist_now)

    status = Column(String(20), nullable=False, default="uploading")  # uploading/validating/aggregating/writing/done/failed
    stage = Column(String(60), nullable=True)
    progress = Column(Integer, nullable=False, default=0)

    registrar_code = Column(Integer, nullable=True)
    ea_code = Column(Integer, nullable=True)

    rows_read = Column(BigInteger, nullable=True)
    rows_after_filter = Column(BigInteger, nullable=True)
    rows_written = Column(BigInteger, nullable=True)
    rows_inserted = Column(BigInteger, nullable=True)
    rows_updated = Column(BigInteger, nullable=True)
    rejected_count = Column(BigInteger, nullable=True)

    date_min = Column(Date, nullable=True)
    date_max = Column(Date, nullable=True)
    distinct_operators = Column(Integer, nullable=True)

    processing_ms = Column(Integer, nullable=True)
    peak_rss_mb = Column(Integer, nullable=True)
    rejected_path = Column(String(500), nullable=True)
    error_detail = Column(Text, nullable=True)


class ActivityDailyUploadLog(Base):
    """One row per date the RegistrarEA data actually covers.

    A daily check compares this against the expected calendar; any absent date
    becomes a missing-data reminder in the notification bell.
    """
    __tablename__ = "activity_daily_upload_log"

    activity_date = Column(Date, primary_key=True)
    batch_id = Column(String(36), nullable=True)
    row_count = Column(BigInteger, nullable=True)
    uploaded_at = Column(DateTime, nullable=False, default=get_ist_now)
