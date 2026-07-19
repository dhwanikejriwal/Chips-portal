"""l1_registration: convert Approved/Reviewed status to Done

Revision ID: d0a2c4e6f8b9
Revises: c9f1a3b5d7e8
Create Date: 2026-07-12 02:00:00.000000

L1's terminal success state is now "Done" (master_status id 18) instead of
"Approved" (2) / "Reviewed" (9). Both previously rendered as "Approved" in the
L1 UI, so both are migrated to Done. The remark-history audit trail is updated
too so timelines stay consistent.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0a2c4e6f8b9'
down_revision: Union[str, Sequence[str], None] = 'c9f1a3b5d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# master_status: APPROVED = 2, REVIEWED = 9, DONE = 18
_DONE = 18


def upgrade() -> None:
    op.execute(f"UPDATE l1_registration_requests SET status_id = {_DONE} WHERE status_id IN (2, 9)")
    op.execute(f"UPDATE l1_registration_remark_history SET status_after_id = {_DONE} WHERE status_after_id IN (2, 9)")


def downgrade() -> None:
    # Not reversible: cannot tell which rows were originally Approved vs Reviewed.
    pass
