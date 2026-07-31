"""create kit_registration_table

Revision ID: f6c8e0a2b4d5
Revises: e5b7d9f1a3c4
Create Date: 2026-07-12 00:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6c8e0a2b4d5'
down_revision: Union[str, Sequence[str], None] = 'e5b7d9f1a3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # The app's startup may have already created this table via Base.metadata.create_all;
    # skip creation in that case so this migration stays a safe no-op.
    if 'kit_registration_table' in inspector.get_table_names():
        return

    op.create_table(
        'kit_registration_table',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('station_id', sa.String(length=50), nullable=False),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('machine_id', sa.String(length=50), nullable=True),
        sa.Column('laptop_serial_no', sa.String(length=50), nullable=True),
        sa.Column('laptop_name', sa.String(length=100), nullable=True),
        sa.Column('station_id_provided_date', sa.Date(), nullable=True),
        sa.Column('l1_status_id', sa.Integer(), nullable=True),
        sa.Column('l1_done_date', sa.Date(), nullable=True),
        sa.Column('l2_status_id', sa.Integer(), nullable=True),
        sa.Column('l2_done_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['l1_status_id'], ['master_status.id']),
        sa.ForeignKeyConstraint(['l2_status_id'], ['master_status.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('station_id'),
    )
    op.create_index(op.f('ix_kit_registration_table_id'), 'kit_registration_table', ['id'], unique=False)
    op.create_index(op.f('ix_kit_registration_table_station_id'), 'kit_registration_table', ['station_id'], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'kit_registration_table' not in inspector.get_table_names():
        return
    op.drop_index(op.f('ix_kit_registration_table_station_id'), table_name='kit_registration_table')
    op.drop_index(op.f('ix_kit_registration_table_id'), table_name='kit_registration_table')
    op.drop_table('kit_registration_table')
