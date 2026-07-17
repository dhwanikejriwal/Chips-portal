"""station_id_master: use district_code as primary key

Revision ID: 39c53dc713eb
Revises: bbf88a53beff
Create Date: 2026-07-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '39c53dc713eb'
down_revision: Union[str, Sequence[str], None] = 'bbf88a53beff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {c['name'] for c in inspector.get_columns('station_id_master')}
    if 'id' not in columns:
        # Fresh databases already get district_code as the primary key
        # from the bbf88a53beff table creation.
        return
    op.drop_constraint('station_id_master_pkey', 'station_id_master', type_='primary')
    op.drop_constraint('station_id_master_district_code_key', 'station_id_master', type_='unique')
    op.drop_column('station_id_master', 'id')
    op.create_primary_key('station_id_master_pkey', 'station_id_master', ['district_code'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('station_id_master_pkey', 'station_id_master', type_='primary')
    op.add_column('station_id_master', sa.Column('id', sa.Integer(), autoincrement=True, nullable=False))
    op.create_primary_key('station_id_master_pkey', 'station_id_master', ['id'])
    op.create_unique_constraint('station_id_master_district_code_key', 'station_id_master', ['district_code'])
