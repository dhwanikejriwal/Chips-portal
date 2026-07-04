"""standardize_database

Revision ID: 5ae425ef03a3
Revises: 2b6f48a9c013
Create Date: 2026-06-22 10:43:44.292298

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ae425ef03a3'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop unused tables safely
    unused_tables = [
        "approval_history",
        "credential_requests",
        "station_kit_details",
        "reactivation_requests",
        "activation_requests",
        "noc_requests",
        "users",
        "districts"
    ]
    for table in unused_tables:
        op.drop_table(table)

    # 2. Create master_status table
    op.create_table(
        "master_status",
        sa.Column("code", sa.String(length=2), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("code")
    )

    # Seed master_status
    master_status_table = sa.table(
        "master_status",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
    )
    op.bulk_insert(
        master_status_table,
        [
            {"code": "PE", "name": "Pending"},
            {"code": "AP", "name": "Approved"},
            {"code": "RV", "name": "Reverted"},
            {"code": "RA", "name": "Reapplied"},
            {"code": "SC", "name": "Sent to CHiPS"},
            {"code": "SU", "name": "Sent to UIDAI"},
            {"code": "UA", "name": "UIDAI Approved"},
            {"code": "UR", "name": "UIDAI Rejected"},
            {"code": "RW", "name": "Reviewed"},
            {"code": "AS", "name": "Assigned"},
            {"code": "FW", "name": "Forwarded"},
            {"code": "FA", "name": "Forwarded Again"},
            {"code": "SK", "name": "Skipped"},
            {"code": "RJ", "name": "Rejected"},
            {"code": "RC", "name": "Reverted by CHiPS"},
            {"code": "AC", "name": "Activated"},
        ]
    )

    # 3. Add status_code and map/drop old status column on requests/operators tables
    status_tables = [
        "candidate_table",
        "LMS_table",
        "nseit_request_table",
        "l1_registration_requests",
        "l2_registration_requests",
        "station_id_requests",
        "operator_activation_requests",
        "operator_reactivation_requests",
        "reactivation_operators",
    ]
    
    for table in status_tables:
        op.add_column(table, sa.Column("status_code", sa.String(length=2), nullable=True))
        # Backfill status_code based on status values
        op.execute(f"""
            UPDATE "{table}" SET status_code = CASE
                WHEN TRIM(LOWER(status)) = 'pending' THEN 'PE'
                WHEN TRIM(LOWER(status)) = 'approved' THEN 'AP'
                WHEN TRIM(LOWER(status)) = 'reverted' THEN 'RV'
                WHEN TRIM(LOWER(status)) = 'reapplied' THEN 'RA'
                WHEN TRIM(LOWER(status)) = 'sent_to_chips' OR TRIM(LOWER(status)) = 'sent to chips' THEN 'SC'
                WHEN TRIM(LOWER(status)) = 'sent_to_uidai' OR TRIM(LOWER(status)) = 'sent to uidai' THEN 'SU'
                WHEN TRIM(LOWER(status)) = 'uidai_approved' OR TRIM(LOWER(status)) = 'uidai approved' THEN 'UA'
                WHEN TRIM(LOWER(status)) = 'uidai_rejected' OR TRIM(LOWER(status)) = 'uidai rejected' THEN 'UR'
                WHEN TRIM(LOWER(status)) = 'reviewed' THEN 'RW'
                WHEN TRIM(LOWER(status)) = 'assigned' THEN 'AS'
                WHEN TRIM(LOWER(status)) = 'forwarded' THEN 'FW'
                WHEN TRIM(LOWER(status)) = 'forwarded again' OR TRIM(LOWER(status)) = 'forwarded_again' THEN 'FA'
                WHEN TRIM(LOWER(status)) = 'skipped' THEN 'SK'
                WHEN TRIM(LOWER(status)) = 'rejected' THEN 'RJ'
                WHEN TRIM(LOWER(status)) = 'reverted by chips' OR TRIM(LOWER(status)) = 'reverted_by_chips' THEN 'RC'
                WHEN TRIM(LOWER(status)) = 'activated' THEN 'AC'
                ELSE 'PE'
            END
        """)
        op.execute(f'UPDATE "{table}" SET status_code = \'PE\' WHERE status_code IS NULL')
        
        # Set nullable=False for specific tables
        if table in ["l2_registration_requests", "station_id_requests", "operator_activation_requests", "operator_reactivation_requests", "reactivation_operators"]:
            op.alter_column(table, "status_code", nullable=False)
            
        op.drop_column(table, "status")

    # 4. Handle status_after_code for remark history tables
    # dc_remark_table, lms_remark_table, nseit_request_remark_table
    remark_tables_with_old_col = [
        "dc_remark_table",
        "lms_remark_table",
        "nseit_request_remark_table"
    ]
    for table in remark_tables_with_old_col:
        op.add_column(table, sa.Column("status_after_code", sa.String(length=2), nullable=True))
        op.execute(f"""
            UPDATE "{table}" SET status_after_code = CASE
                WHEN TRIM(LOWER(status_after)) = 'pending' THEN 'PE'
                WHEN TRIM(LOWER(status_after)) = 'approved' THEN 'AP'
                WHEN TRIM(LOWER(status_after)) = 'reverted' THEN 'RV'
                WHEN TRIM(LOWER(status_after)) = 'reapplied' THEN 'RA'
                WHEN TRIM(LOWER(status_after)) = 'sent_to_chips' OR TRIM(LOWER(status_after)) = 'sent to chips' THEN 'SC'
                WHEN TRIM(LOWER(status_after)) = 'sent_to_uidai' OR TRIM(LOWER(status_after)) = 'sent to uidai' THEN 'SU'
                WHEN TRIM(LOWER(status_after)) = 'uidai_approved' OR TRIM(LOWER(status_after)) = 'uidai approved' THEN 'UA'
                WHEN TRIM(LOWER(status_after)) = 'uidai_rejected' OR TRIM(LOWER(status_after)) = 'uidai rejected' THEN 'UR'
                WHEN TRIM(LOWER(status_after)) = 'reviewed' THEN 'RW'
                WHEN TRIM(LOWER(status_after)) = 'assigned' THEN 'AS'
                WHEN TRIM(LOWER(status_after)) = 'forwarded' THEN 'FW'
                WHEN TRIM(LOWER(status_after)) = 'forwarded again' OR TRIM(LOWER(status_after)) = 'forwarded_again' THEN 'FA'
                WHEN TRIM(LOWER(status_after)) = 'skipped' THEN 'SK'
                WHEN TRIM(LOWER(status_after)) = 'rejected' THEN 'RJ'
                WHEN TRIM(LOWER(status_after)) = 'reverted by chips' OR TRIM(LOWER(status_after)) = 'reverted_by_chips' THEN 'RC'
                WHEN TRIM(LOWER(status_after)) = 'activated' THEN 'AC'
                ELSE NULL
            END
        """)
        op.drop_column(table, "status_after")

    # l1_registration_remark_history (uses 'action')
    op.add_column("l1_registration_remark_history", sa.Column("status_after_code", sa.String(length=2), nullable=True))
    op.execute("""
        UPDATE "l1_registration_remark_history" SET status_after_code = CASE
            WHEN TRIM(LOWER(action)) = 'submitted' THEN 'PE'
            WHEN TRIM(LOWER(action)) = 'pending' THEN 'PE'
            WHEN TRIM(LOWER(action)) = 'approved' THEN 'AP'
            WHEN TRIM(LOWER(action)) = 'reverted' THEN 'RV'
            WHEN TRIM(LOWER(action)) = 'reapplied' THEN 'RA'
            WHEN TRIM(LOWER(action)) = 'sent_to_chips' OR TRIM(LOWER(action)) = 'sent to chips' THEN 'SC'
            WHEN TRIM(LOWER(action)) = 'sent_to_uidai' OR TRIM(LOWER(action)) = 'sent to uidai' THEN 'SU'
            WHEN TRIM(LOWER(action)) = 'uidai_approved' OR TRIM(LOWER(action)) = 'uidai approved' THEN 'UA'
            WHEN TRIM(LOWER(action)) = 'uidai_rejected' OR TRIM(LOWER(action)) = 'uidai rejected' THEN 'UR'
            WHEN TRIM(LOWER(action)) = 'reviewed' THEN 'RW'
            WHEN TRIM(LOWER(action)) = 'assigned' THEN 'AS'
            WHEN TRIM(LOWER(action)) = 'forwarded' THEN 'FW'
            WHEN TRIM(LOWER(action)) = 'forwarded again' OR TRIM(LOWER(action)) = 'forwarded_again' THEN 'FA'
            WHEN TRIM(LOWER(action)) = 'skipped' THEN 'SK'
            WHEN TRIM(LOWER(action)) = 'rejected' THEN 'RJ'
            WHEN TRIM(LOWER(action)) = 'reverted by chips' OR TRIM(LOWER(action)) = 'reverted_by_chips' THEN 'RC'
            WHEN TRIM(LOWER(action)) = 'activated' THEN 'AC'
            ELSE NULL
        END
    """)
    op.drop_column("l1_registration_remark_history", "action")

    # Add status_after_code to new remark tables (starting as NULL)
    new_remark_tables = [
        "l2_registration_remarks",
        "station_id_remarks",
        "operator_activation_remarks",
        "reactivation_remark_history"
    ]
    for table in new_remark_tables:
        op.add_column(table, sa.Column("status_after_code", sa.String(length=2), nullable=True))

    # 5. Create indexes
    op.create_index("ix_l2_registration_requests_status_code", "l2_registration_requests", ["status_code"])
    op.create_index("ix_station_id_requests_status_code", "station_id_requests", ["status_code"])
    op.create_index("ix_operator_activation_requests_status_code", "operator_activation_requests", ["status_code"])
    op.create_index("ix_operator_reactivation_requests_status_code", "operator_reactivation_requests", ["status_code"])


def downgrade() -> None:
    # 1. Drop indexes
    op.drop_index("ix_l2_registration_requests_status_code", "l2_registration_requests")
    op.drop_index("ix_station_id_requests_status_code", "station_id_requests")
    op.drop_index("ix_operator_activation_requests_status_code", "operator_activation_requests")
    op.drop_index("ix_operator_reactivation_requests_status_code", "operator_reactivation_requests")

    # 2. Drop status_after_code from new remark tables
    new_remark_tables = [
        "l2_registration_remarks",
        "station_id_remarks",
        "operator_activation_remarks",
        "reactivation_remark_history"
    ]
    for table in new_remark_tables:
        op.drop_column(table, "status_after_code")

    # 3. Restore action column in l1_registration_remark_history
    op.add_column("l1_registration_remark_history", sa.Column("action", sa.String(), nullable=True))
    op.execute("""
        UPDATE "l1_registration_remark_history" SET action = CASE
            WHEN status_after_code = 'PE' THEN 'PENDING'
            WHEN status_after_code = 'AP' THEN 'APPROVED'
            WHEN status_after_code = 'RV' THEN 'REVERTED'
            WHEN status_after_code = 'RA' THEN 'REAPPLIED'
            WHEN status_after_code = 'RW' THEN 'REVIEWED'
            ELSE 'SUBMITTED'
        END
    """)
    op.drop_column("l1_registration_remark_history", "status_after_code")

    # 4. Restore status_after in old remark tables
    remark_tables_with_old_col = [
        "dc_remark_table",
        "lms_remark_table",
        "nseit_request_remark_table"
    ]
    for table in remark_tables_with_old_col:
        op.add_column(table, sa.Column("status_after", sa.String(), nullable=True))
        op.execute(f"""
            UPDATE "{table}" SET status_after = CASE
                WHEN status_after_code = 'PE' THEN 'Pending'
                WHEN status_after_code = 'AP' THEN 'Approved'
                WHEN status_after_code = 'RV' THEN 'Reverted'
                WHEN status_after_code = 'RA' THEN 'Reapplied'
                WHEN status_after_code = 'SC' THEN 'Sent to CHiPS'
                WHEN status_after_code = 'SU' THEN 'Sent to UIDAI'
                WHEN status_after_code = 'UA' THEN 'UIDAI Approved'
                WHEN status_after_code = 'UR' THEN 'UIDAI Rejected'
                WHEN status_after_code = 'RW' THEN 'Reviewed'
                WHEN status_after_code = 'AS' THEN 'Assigned'
                WHEN status_after_code = 'FW' THEN 'Forwarded'
                WHEN status_after_code = 'FA' THEN 'Forwarded Again'
                WHEN status_after_code = 'SK' THEN 'Skipped'
                WHEN status_after_code = 'RJ' THEN 'Rejected'
                WHEN status_after_code = 'RC' THEN 'Reverted by CHiPS'
                WHEN status_after_code = 'AC' THEN 'Activated'
                ELSE NULL
            END
        """)
        op.drop_column(table, "status_after_code")

    # 5. Restore status column in requests/operators tables
    status_tables = [
        ("candidate_table", "title"),
        ("LMS_table", "title"),
        ("nseit_request_table", "title"),
        ("l1_registration_requests", "upper"),
        ("l2_registration_requests", "lower"),
        ("station_id_requests", "lower"),
        ("operator_activation_requests", "lower"),
        ("operator_reactivation_requests", "upper"),
        ("reactivation_operators", "upper"),
    ]
    
    for table, casing in status_tables:
        op.add_column(table, sa.Column("status", sa.String(), nullable=True))
        if casing == "lower":
            op.execute(f"""
                UPDATE "{table}" SET status = CASE
                    WHEN status_code = 'PE' THEN 'pending'
                    WHEN status_code = 'AP' THEN 'approved'
                    WHEN status_code = 'RV' THEN 'reverted'
                    WHEN status_code = 'RA' THEN 'reapplied'
                    WHEN status_code = 'SC' THEN 'sent_to_chips'
                    WHEN status_code = 'SU' THEN 'sent_to_uidai'
                    WHEN status_code = 'UA' THEN 'uidai_approved'
                    WHEN status_code = 'UR' THEN 'uidai_rejected'
                    WHEN status_code = 'RW' THEN 'reviewed'
                    WHEN status_code = 'AS' THEN 'assigned'
                    WHEN status_code = 'FW' THEN 'forwarded'
                    WHEN status_code = 'FA' THEN 'forwarded again'
                    WHEN status_code = 'SK' THEN 'skipped'
                    WHEN status_code = 'RJ' THEN 'rejected'
                    WHEN status_code = 'RC' THEN 'reverted by chips'
                    WHEN status_code = 'AC' THEN 'activated'
                    ELSE 'pending'
                END
            """)
        elif casing == "upper":
            op.execute(f"""
                UPDATE "{table}" SET status = CASE
                    WHEN status_code = 'PE' THEN 'PENDING'
                    WHEN status_code = 'AP' THEN 'APPROVED'
                    WHEN status_code = 'RV' THEN 'REVERTED'
                    WHEN status_code = 'RA' THEN 'REAPPLIED'
                    WHEN status_code = 'SC' THEN 'SENT_TO_CHIPS'
                    WHEN status_code = 'SU' THEN 'SENT_TO_UIDAI'
                    WHEN status_code = 'UA' THEN 'UIDAI_APPROVED'
                    WHEN status_code = 'UR' THEN 'UIDAI_REJECTED'
                    WHEN status_code = 'RW' THEN 'REVIEWED'
                    WHEN status_code = 'AS' THEN 'ASSIGNED'
                    WHEN status_code = 'FW' THEN 'FORWARDED'
                    WHEN status_code = 'FA' THEN 'FORWARDED AGAIN'
                    WHEN status_code = 'SK' THEN 'SKIPPED'
                    WHEN status_code = 'RJ' THEN 'REJECTED'
                    WHEN status_code = 'RC' THEN 'REVERTED BY CHIPS'
                    WHEN status_code = 'AC' THEN 'ACTIVATED'
                    ELSE 'PENDING'
                END
            """)
        else: # title casing
            op.execute(f"""
                UPDATE "{table}" SET status = CASE
                    WHEN status_code = 'PE' THEN 'Pending'
                    WHEN status_code = 'AP' THEN 'Approved'
                    WHEN status_code = 'RV' THEN 'Reverted'
                    WHEN status_code = 'RA' THEN 'Reapplied'
                    WHEN status_code = 'SC' THEN 'Sent to CHiPS'
                    WHEN status_code = 'SU' THEN 'Sent to UIDAI'
                    WHEN status_code = 'UA' THEN 'UIDAI Approved'
                    WHEN status_code = 'UR' THEN 'UIDAI Rejected'
                    WHEN status_code = 'RW' THEN 'Reviewed'
                    WHEN status_code = 'AS' THEN 'Assigned'
                    WHEN status_code = 'FW' THEN 'Forwarded'
                    WHEN status_code = 'FA' THEN 'Forwarded Again'
                    WHEN status_code = 'SK' THEN 'Skipped'
                    WHEN status_code = 'RJ' THEN 'Rejected'
                    WHEN status_code = 'RC' THEN 'Reverted by CHiPS'
                    WHEN status_code = 'AC' THEN 'Activated'
                    ELSE 'Pending'
                END
            """)
        op.drop_column(table, "status_code")

    # 6. Drop master_status table
    op.drop_table("master_status")

    # 7. Recreate unused tables (simple structure)
    unused_tables = [
        "districts",
        "users",
        "noc_requests",
        "activation_requests",
        "reactivation_requests",
        "station_kit_details",
        "credential_requests",
        "approval_history"
    ]
    for table in unused_tables:
        op.create_table(
            table,
            sa.Column("id", sa.Integer, sa.Identity(always=True), primary_key=True)
        )
