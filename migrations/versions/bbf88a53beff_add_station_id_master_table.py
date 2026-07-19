"""add station_id_master table

Revision ID: bbf88a53beff
Revises: d0a2c4e6f8b9
Create Date: 2026-07-16 10:42:16.905200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'bbf88a53beff'
down_revision: Union[str, Sequence[str], None] = 'd0a2c4e6f8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if 'station_id_master' not in inspector.get_table_names():
        op.create_table(
            'station_id_master',
            sa.Column('district_code', sa.String(length=20), nullable=False),
            sa.Column('district_name', sa.String(length=100), nullable=False),
            sa.Column('start_station_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['district_code'], ['district_table.district_code'], ),
            sa.PrimaryKeyConstraint('district_code'),
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('station_id_master')
