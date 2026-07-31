"""add allotted and done statuses to master_status

Revision ID: b2f4a1c9d3e7
Revises: 8e26e326a712
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f4a1c9d3e7'
down_revision: Union[str, Sequence[str], None] = '8e26e326a712'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the 'Allotted' (17) and 'Done' (18) statuses."""
    op.execute(
        "INSERT INTO master_status (id, name) VALUES (17, 'Allotted') "
        "ON CONFLICT (id) DO NOTHING"
    )
    op.execute(
        "INSERT INTO master_status (id, name) VALUES (18, 'Done') "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    """Remove the 'Allotted' (17) and 'Done' (18) statuses."""
    op.execute("DELETE FROM master_status WHERE id IN (17, 18)")
