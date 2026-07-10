"""Merge multiple heads

Revision ID: 8e26e326a712
Revises: 7b21a4c9e3d1, 83259d988978
Create Date: 2026-07-10 12:14:51.923278

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e26e326a712'
down_revision: Union[str, Sequence[str], None] = ('7b21a4c9e3d1', '83259d988978')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
