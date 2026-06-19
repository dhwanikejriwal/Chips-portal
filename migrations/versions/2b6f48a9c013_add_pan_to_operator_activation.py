"""add_pan_to_operator_activation

Revision ID: 2b6f48a9c013
Revises: 1cee02034d17
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b6f48a9c013'
down_revision: Union[str, Sequence[str], None] = '1cee02034d17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add PAN number captured by the DC operator activation form."""
    op.add_column('operator_activation_requests', sa.Column('pan_number', sa.String(length=10), nullable=True))


def downgrade() -> None:
    """Remove PAN number from operator activation requests."""
    op.drop_column('operator_activation_requests', 'pan_number')
