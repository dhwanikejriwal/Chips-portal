"""add_aadhaar_district_resources_table

Revision ID: 2134a12ee55a
Revises: 0001_initial_full_schema
Create Date: 2026-07-02 14:37:50.200164

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2134a12ee55a'
down_revision: Union[str, Sequence[str], None] = '0001_initial_full_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('aadhaar_district_resources',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('district_code', sa.String(length=20), nullable=False),
    sa.Column('edm_name', sa.String(length=100), nullable=True),
    sa.Column('edm_contact', sa.String(length=100), nullable=True),
    sa.Column('edm_email', sa.String(length=200), nullable=True),
    sa.Column('dc_name', sa.String(length=100), nullable=True),
    sa.Column('dc_contact', sa.String(length=100), nullable=True),
    sa.Column('dc_email', sa.String(length=200), nullable=True),
    sa.Column('mto_name', sa.String(length=100), nullable=True),
    sa.Column('mto_contact', sa.String(length=100), nullable=True),
    sa.Column('mto_email', sa.String(length=200), nullable=True),
    sa.Column('adc_name', sa.String(length=100), nullable=True),
    sa.Column('adc_contact', sa.String(length=100), nullable=True),
    sa.Column('adc_email', sa.String(length=200), nullable=True),
    sa.ForeignKeyConstraint(['district_code'], ['district_table.district_code'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('district_code')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('aadhaar_district_resources')
