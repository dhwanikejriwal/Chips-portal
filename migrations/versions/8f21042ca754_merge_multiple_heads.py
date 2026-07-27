"""merge_multiple_heads

Revision ID: 8f21042ca754
Revises: 75bb5852b280, a1bd704d3525
Create Date: 2026-07-25 09:43:18.469963

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f21042ca754'
down_revision: Union[str, Sequence[str], None] = ('75bb5852b280', 'a1bd704d3525')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
