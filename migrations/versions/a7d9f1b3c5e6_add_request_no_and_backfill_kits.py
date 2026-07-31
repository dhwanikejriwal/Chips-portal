"""add request_no to kit_registration_table and backfill allotted station ids

Revision ID: a7d9f1b3c5e6
Revises: f6c8e0a2b4d5
Create Date: 2026-07-12 00:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7d9f1b3c5e6'
down_revision: Union[str, Sequence[str], None] = 'f6c8e0a2b4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# StatusEnum: ALLOTTED = 17, PENDING = 1
_ALLOTTED = 17
_PENDING = 1


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1) Add request_no if it isn't already there (create_all may have made it).
    columns = [c['name'] for c in inspector.get_columns('kit_registration_table')]
    if 'request_no' not in columns:
        op.add_column('kit_registration_table', sa.Column('request_no', sa.String(length=50), nullable=True))
        op.create_index(op.f('ix_kit_registration_table_request_no'), 'kit_registration_table', ['request_no'], unique=False)

    # 2) Backfill: one kit row per already-allotted Station ID.
    #    station_id_inserted may hold a comma-separated list of Station IDs.
    #    L1 starts Pending (L1 done date -> NULL); L2 not started (L2 status/date/days -> NULL).
    #    station_id_provided_date = the date the request was actually allotted.
    op.execute(f"""
        INSERT INTO kit_registration_table
            (request_no, station_id, district, station_id_provided_date,
             l1_status_id, l1_done_date, l2_status_id, l2_done_date, created_at, updated_at)
        SELECT DISTINCT ON (btrim(sid.val))
            s.request_no,
            btrim(sid.val)                              AS station_id,
            d.district_name                             AS district,
            COALESCE(s.reviewed_at, s.submitted_at)::date AS station_id_provided_date,
            {_PENDING}                                  AS l1_status_id,
            NULL                                        AS l1_done_date,
            NULL                                        AS l2_status_id,
            NULL                                        AS l2_done_date,
            NOW(),
            NOW()
        FROM station_id_requests s
        CROSS JOIN LATERAL unnest(string_to_array(s.station_id_inserted, ',')) AS sid(val)
        LEFT JOIN district_table d ON d.district_code = s.district_id
        WHERE s.status_id = {_ALLOTTED}
          AND s.station_id_inserted IS NOT NULL
          AND btrim(sid.val) <> ''
          AND NOT EXISTS (
              SELECT 1 FROM kit_registration_table k
              WHERE k.station_id = btrim(sid.val)
          )
        ORDER BY btrim(sid.val), COALESCE(s.reviewed_at, s.submitted_at) DESC;
    """)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('kit_registration_table')]
    if 'request_no' in columns:
        try:
            op.drop_index(op.f('ix_kit_registration_table_request_no'), table_name='kit_registration_table')
        except Exception:
            pass
        op.drop_column('kit_registration_table', 'request_no')
