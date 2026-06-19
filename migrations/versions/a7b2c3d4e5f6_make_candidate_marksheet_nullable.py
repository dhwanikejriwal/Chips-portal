"""make_candidate_marksheet_nullable

Revision ID: a7b2c3d4e5f6
Revises: 5d0e09a3f538
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5d0e09a3f538'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow 10th-only candidates to leave marksheet_upload empty."""
    op.alter_column(
        'candidate_table',
        'marksheet_upload',
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    """Restore the previous NOT NULL constraint."""
    op.execute(
        "UPDATE candidate_table "
        "SET marksheet_upload = COALESCE(marksheet_upload, tenth_marksheet_upload, '') "
        "WHERE marksheet_upload IS NULL"
    )
    op.alter_column(
        'candidate_table',
        'marksheet_upload',
        existing_type=sa.String(length=255),
        nullable=False,
    )
