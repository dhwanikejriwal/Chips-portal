"""merge_all_heads

Revision ID: b9e8d7c6b5a4
Revises: 8f21042ca754, a5c7d9e1f3b4
Create Date: 2026-07-31 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9e8d7c6b5a4'
down_revision: Union[str, Sequence[str], None] = ('8f21042ca754', 'a5c7d9e1f3b4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
