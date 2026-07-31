"""split multi-id station allotments into one record per station id

Revision ID: b8e0c2d4f6a7
Revises: a7d9f1b3c5e6
Create Date: 2026-07-12 01:00:00.000000

- request_no is no longer unique (a batch allotment shares one request_no across rows).
- Existing rows whose station_id_inserted holds a comma-separated list are split so
  every Station ID gets its own row (number_of_kits = 1), all sharing the request_no.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e0c2d4f6a7'
down_revision: Union[str, Sequence[str], None] = 'a7d9f1b3c5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1) Drop any UNIQUE constraint / index on request_no so rows can share it.
    for uc in inspector.get_unique_constraints('station_id_requests'):
        if uc.get('column_names') == ['request_no']:
            op.drop_constraint(uc['name'], 'station_id_requests', type_='unique')
    for ix in inspector.get_indexes('station_id_requests'):
        if ix.get('unique') and ix.get('column_names') == ['request_no']:
            op.drop_index(ix['name'], table_name='station_id_requests')

    # Keep a plain (non-unique) index on request_no for lookups.
    existing_index_names = {ix['name'] for ix in inspector.get_indexes('station_id_requests')}
    if 'ix_station_id_requests_request_no' not in existing_index_names:
        op.create_index('ix_station_id_requests_request_no', 'station_id_requests', ['request_no'], unique=False)

    # 2) Create sibling rows for the 2nd..Nth Station ID of every batch allotment.
    op.execute("""
        INSERT INTO station_id_requests
            (request_no, dc_id, district_id, model, user_type, user_type_custom_reason,
             number_of_kits, slot, status_id, station_id_inserted, submitted_at, reviewed_at, reviewed_by)
        SELECT
            s.request_no, s.dc_id, s.district_id, s.model, s.user_type, s.user_type_custom_reason,
            1, s.slot, s.status_id, btrim(part.val), s.submitted_at, s.reviewed_at, s.reviewed_by
        FROM station_id_requests s
        CROSS JOIN LATERAL unnest(string_to_array(s.station_id_inserted, ',')) WITH ORDINALITY AS part(val, ord)
        WHERE s.station_id_inserted LIKE '%,%'
          AND part.ord > 1
          AND btrim(part.val) <> '';
    """)

    # 3) Collapse the original rows to just their first Station ID.
    op.execute("""
        UPDATE station_id_requests
        SET station_id_inserted = btrim(split_part(station_id_inserted, ',', 1)),
            number_of_kits = 1
        WHERE station_id_inserted LIKE '%,%';
    """)


def downgrade() -> None:
    # Splitting is not automatically reversible (sibling rows can't be safely re-merged).
    # We only restore a non-unique -> unique index is intentionally NOT re-added, because
    # duplicate request_no values may now exist.
    pass
