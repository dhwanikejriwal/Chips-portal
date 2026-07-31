"""station_id: convert existing Approved (2) status to Allotted (17)

Revision ID: c3e5b7a9f1d2
Revises: b2f4a1c9d3e7
Create Date: 2026-07-12 00:10:00.000000

Only affects the Station ID module. Other request types keep 'Approved'.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e5b7a9f1d2'
down_revision: Union[str, Sequence[str], None] = 'b2f4a1c9d3e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Request rows: Approved (2) -> Allotted (17)
    op.execute("UPDATE station_id_requests SET status_id = 17 WHERE status_id = 2")
    # Remark/timeline history for Station ID only: keep the badge consistent
    op.execute("UPDATE station_id_remarks SET status_after_id = 17 WHERE status_after_id = 2")


def downgrade() -> None:
    op.execute("UPDATE station_id_requests SET status_id = 2 WHERE status_id = 17")
    op.execute("UPDATE station_id_remarks SET status_after_id = 2 WHERE status_after_id = 17")
