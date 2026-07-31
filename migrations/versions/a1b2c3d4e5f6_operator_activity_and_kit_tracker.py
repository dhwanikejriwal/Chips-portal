"""operator activity + kit tracker tables

Revision ID: a1b2c3d4e5f6
Revises: 75bb5852b280
Create Date: 2026-07-23 00:00:00.000000

Creates:
  - kit_tracker
  - operator_daily_activity (+ indexes)
  - activity_stations
  - operator_activity_master
  - activity_upload_batch
  - activity_daily_upload_log

Each create is guarded so it stays a safe no-op if the app's startup already
created the table via Base.metadata.create_all.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "75bb5852b280"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ------------------------------------------------------------------ kit_tracker
    if not _has(inspector, "kit_tracker"):
        op.create_table(
            "kit_tracker",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("sr_no", sa.Integer(), nullable=True),
            sa.Column("district_code", sa.String(length=20), nullable=True),
            sa.Column("operator_id", sa.Integer(), nullable=True),
            sa.Column("kit_slot", sa.String(length=50), nullable=True),
            sa.Column("station_id", sa.String(length=50), nullable=False),
            sa.Column("station_id_allotted_date", sa.Date(), nullable=True),
            sa.Column("machine_id", sa.String(length=100), nullable=True),
            sa.Column("laptop_serial_no", sa.String(length=50), nullable=True),
            sa.Column("laptop_name", sa.String(length=100), nullable=True),
            sa.Column("operator_code_raw", sa.String(length=100), nullable=True),
            sa.Column("operator_name_raw", sa.String(length=120), nullable=True),
            sa.Column("operator_mobile_raw", sa.String(length=20), nullable=True),
            sa.Column("security_deposit_status", sa.String(length=30), nullable=True),
            sa.Column("security_deposit_date", sa.Date(), nullable=True),
            sa.Column("l1_status", sa.String(length=30), nullable=True),
            sa.Column("l1_date", sa.Date(), nullable=True),
            sa.Column("l2_status", sa.String(length=30), nullable=True),
            sa.Column("l2_date", sa.Date(), nullable=True),
            sa.Column("block", sa.String(length=100), nullable=True),
            sa.Column("category", sa.String(length=100), nullable=True),
            sa.Column("locality", sa.String(length=150), nullable=True),
            sa.Column("ask_address", sa.Text(), nullable=True),
            sa.Column("operator_status", sa.String(length=30), nullable=True),
            sa.Column("inactive_reason", sa.String(length=255), nullable=True),
            sa.Column("inactive_date", sa.Date(), nullable=True),
            sa.Column("permit_18_plus", sa.Integer(), nullable=True),
            sa.Column("station_status", sa.String(length=30), nullable=True),
            sa.Column("onboarding_status", sa.String(length=30), nullable=True),
            sa.Column("onboard_date", sa.Date(), nullable=True),
            sa.Column("kit_working", sa.Integer(), nullable=True),
            sa.Column("visit_status", sa.String(length=30), nullable=True),
            sa.Column("visit_date", sa.Date(), nullable=True),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("batch_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["district_code"], ["district_table.district_code"]),
            sa.ForeignKeyConstraint(["operator_id"], ["operators.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("station_id"),
        )
        op.create_index(op.f("ix_kit_tracker_id"), "kit_tracker", ["id"])
        op.create_index(op.f("ix_kit_tracker_station_id"), "kit_tracker", ["station_id"], unique=True)
        op.create_index(op.f("ix_kit_tracker_district_code"), "kit_tracker", ["district_code"])
        op.create_index(op.f("ix_kit_tracker_operator_id"), "kit_tracker", ["operator_id"])
        op.create_index(op.f("ix_kit_tracker_batch_id"), "kit_tracker", ["batch_id"])

    # -------------------------------------------------- operator_daily_activity
    if not _has(inspector, "operator_daily_activity"):
        op.create_table(
            "operator_daily_activity",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("activity_date", sa.Date(), nullable=False),
            sa.Column("station_ea_code", sa.Integer(), nullable=False),
            sa.Column("session_operator_id", sa.String(length=120), nullable=False),
            sa.Column("station_number", sa.Integer(), nullable=False),
            sa.Column("machine_district", sa.String(length=120), nullable=True),
            sa.Column("New_Aadhaar_Enrolment", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("New_Aadhar_18_plus", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("Total_Updates", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("Total_Demographic_Updates", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("Total_Biometric_Updates", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("NON_MBU", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("IS_MBU", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("COUNT_6AM_TO_10PM", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("COUNT_10PM_TO_6AM", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("Total_Enrollment_and_Updates", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("batch_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "activity_date", "station_ea_code", "session_operator_id", "station_number",
                name="uq_operator_daily_activity_key",
            ),
        )
        op.create_index("ix_oda_date", "operator_daily_activity", ["activity_date"])
        op.create_index("ix_oda_operator_date", "operator_daily_activity", ["session_operator_id", "activity_date"])
        op.create_index("ix_oda_district_date", "operator_daily_activity", ["machine_district", "activity_date"])
        op.create_index("ix_operator_daily_activity_batch_id", "operator_daily_activity", ["batch_id"])

    # ------------------------------------------------------------ activity_stations
    if not _has(inspector, "activity_stations"):
        op.create_table(
            "activity_stations",
            sa.Column("station_ea_code", sa.Integer(), nullable=False),
            sa.Column("station_number", sa.Integer(), nullable=False),
            sa.Column("machine_address", sa.Text(), nullable=True),
            sa.Column("machine_district", sa.String(length=120), nullable=True),
            sa.Column("machine_state", sa.String(length=120), nullable=True),
            sa.Column("machine_pincode", sa.String(length=12), nullable=True),
            sa.Column("machine_lat", sa.String(length=40), nullable=True),
            sa.Column("machine_long", sa.String(length=40), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("station_ea_code", "station_number"),
        )

    # ---------------------------------------------------- operator_activity_master
    if not _has(inspector, "operator_activity_master"):
        op.create_table(
            "operator_activity_master",
            sa.Column("session_operator_id", sa.String(length=120), nullable=False),
            sa.Column("operator_id", sa.Integer(), nullable=True),
            sa.Column("operator_name", sa.String(length=120), nullable=True),
            sa.Column("operator_photo_url", sa.String(length=255), nullable=True),
            sa.Column("mobile_number", sa.String(length=20), nullable=True),
            sa.Column("email", sa.String(length=120), nullable=True),
            sa.Column("aadhaar_last4", sa.String(length=4), nullable=True),
            sa.Column("onboarding_date", sa.Date(), nullable=True),
            sa.Column("certification_id", sa.String(length=60), nullable=True),
            sa.Column("certification_expiry_date", sa.Date(), nullable=True),
            sa.Column("security_deposit_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("security_deposit_paid_on", sa.Date(), nullable=True),
            sa.Column("security_deposit_txn_ref", sa.String(length=80), nullable=True),
            sa.Column("security_deposit_status", sa.String(length=20), nullable=True),
            sa.Column("agency_name", sa.String(length=120), nullable=True),
            sa.Column("supervisor_name", sa.String(length=120), nullable=True),
            sa.Column("current_status", sa.String(length=20), nullable=True, server_default="ACTIVE"),
            sa.Column("status_changed_on", sa.Date(), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["operator_id"], ["operators.id"]),
            sa.PrimaryKeyConstraint("session_operator_id"),
        )
        op.create_index("ix_operator_activity_master_operator_id", "operator_activity_master", ["operator_id"])

    # ------------------------------------------------------- activity_upload_batch
    if not _has(inspector, "activity_upload_batch"):
        op.create_table(
            "activity_upload_batch",
            sa.Column("batch_id", sa.String(length=36), nullable=False),
            sa.Column("source", sa.String(length=30), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=True),
            sa.Column("uploaded_by", sa.String(length=120), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="uploading"),
            sa.Column("stage", sa.String(length=60), nullable=True),
            sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("registrar_code", sa.Integer(), nullable=True),
            sa.Column("ea_code", sa.Integer(), nullable=True),
            sa.Column("rows_read", sa.BigInteger(), nullable=True),
            sa.Column("rows_after_filter", sa.BigInteger(), nullable=True),
            sa.Column("rows_written", sa.BigInteger(), nullable=True),
            sa.Column("rows_inserted", sa.BigInteger(), nullable=True),
            sa.Column("rows_updated", sa.BigInteger(), nullable=True),
            sa.Column("rejected_count", sa.BigInteger(), nullable=True),
            sa.Column("date_min", sa.Date(), nullable=True),
            sa.Column("date_max", sa.Date(), nullable=True),
            sa.Column("distinct_operators", sa.Integer(), nullable=True),
            sa.Column("processing_ms", sa.Integer(), nullable=True),
            sa.Column("peak_rss_mb", sa.Integer(), nullable=True),
            sa.Column("rejected_path", sa.String(length=500), nullable=True),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("batch_id"),
        )

    # --------------------------------------------------- activity_daily_upload_log
    if not _has(inspector, "activity_daily_upload_log"):
        op.create_table(
            "activity_daily_upload_log",
            sa.Column("activity_date", sa.Date(), nullable=False),
            sa.Column("batch_id", sa.String(length=36), nullable=True),
            sa.Column("row_count", sa.BigInteger(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("activity_date"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for tbl in (
        "activity_daily_upload_log",
        "activity_upload_batch",
        "operator_activity_master",
        "activity_stations",
        "operator_daily_activity",
        "kit_tracker",
    ):
        if _has(inspector, tbl):
            op.drop_table(tbl)
