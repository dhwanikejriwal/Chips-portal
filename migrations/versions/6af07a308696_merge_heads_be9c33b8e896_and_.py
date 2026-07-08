"""Merge heads be9c33b8e896 and 0165ef25f079

Revision ID: 6af07a308696
Revises: be9c33b8e896, 0165ef25f079
Create Date: 2026-07-04 12:22:11.245340

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6af07a308696'
down_revision: Union[str, Sequence[str], None] = ('be9c33b8e896', '0165ef25f079')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
