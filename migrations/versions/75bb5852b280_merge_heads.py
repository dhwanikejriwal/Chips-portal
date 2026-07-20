"""merge heads

Revision ID: 75bb5852b280
Revises: 0ee10ea42531, ad0d94cb8da3
Create Date: 2026-07-18 22:04:54.849100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '75bb5852b280'
down_revision: Union[str, Sequence[str], None] = ('0ee10ea42531', 'ad0d94cb8da3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
