"""backfill station_id_requests.slot with '937 slot' where missing

Revision ID: e5b7d9f1a3c4
Revises: d4a6c8e0b2f3
Create Date: 2026-07-12 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b7d9f1a3c4'
down_revision: Union[str, Sequence[str], None] = 'd4a6c8e0b2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing requests (log history + pending) with no slot default to the 937 slot.
    op.execute("UPDATE station_id_requests SET slot = '937 slot' WHERE slot IS NULL OR slot = ''")


def downgrade() -> None:
    # No safe automatic reversal: cannot distinguish backfilled rows from real ones.
    pass
