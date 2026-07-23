"""merge multiple heads

Revision ID: e43fbf38a016
Revises: 0ee10ea42531, 2392e65dd488
Create Date: 2026-07-21 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e43fbf38a016'
down_revision: Union[str, Sequence[str], None] = ('0ee10ea42531', '2392e65dd488')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
