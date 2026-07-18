"""merge heads 0b158e3b72d6 and d6fca808e805

Revision ID: e6a2480c7d79
Revises: 0b158e3b72d6, d6fca808e805
Create Date: 2026-07-17 13:40:25.433124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6a2480c7d79'
down_revision: Union[str, Sequence[str], None] = ('0b158e3b72d6', 'd6fca808e805')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
