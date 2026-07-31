"""add slot column to station_id_requests

Revision ID: d4a6c8e0b2f3
Revises: c3e5b7a9f1d2
Create Date: 2026-07-12 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a6c8e0b2f3'
down_revision: Union[str, Sequence[str], None] = 'c3e5b7a9f1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Slot type: '937 slot' or '300 slot'
    op.add_column('station_id_requests', sa.Column('slot', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('station_id_requests', 'slot')
