"""drop_unused_aadhaar_district_resources_table

Revision ID: ad0d94cb8da3
Revises: e6a2480c7d79
Create Date: 2026-07-17 14:05:18.997050

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad0d94cb8da3'
down_revision: Union[str, Sequence[str], None] = 'e6a2480c7d79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('aadhaar_district_resources')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        'aadhaar_district_resources',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('district_name', sa.String(length=100), nullable=True),
        sa.Column('role', sa.String(length=100), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('mobile', sa.String(length=100), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
    )
