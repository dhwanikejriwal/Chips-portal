"""Merge multiple heads

Revision ID: be9c33b8e896
Revises: 1be3dc4a9bfd, 3abd22e6a4a3
Create Date: 2026-06-30 17:31:36.333463

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be9c33b8e896'
down_revision: Union[str, Sequence[str], None] = ('1be3dc4a9bfd', '3abd22e6a4a3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
