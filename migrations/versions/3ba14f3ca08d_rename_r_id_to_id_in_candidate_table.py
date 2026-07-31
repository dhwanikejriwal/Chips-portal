"""rename_r_id_to_id_in_candidate_table

Revision ID: 3ba14f3ca08d
Revises: e59275b19342
Create Date: 2026-07-11 19:50:12.749025

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ba14f3ca08d'
down_revision: Union[str, Sequence[str], None] = 'e59275b19342'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
