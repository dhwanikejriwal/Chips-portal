"""add_status_after_field

Revision ID: add_status_after_field
Revises: 0454a62a6223
Create Date: 2026-06-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_status_after_field'
down_revision: Union[str, Sequence[str], None] = '0454a62a6223'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add status_after column to lms_remark_table
    op.add_column('lms_remark_table', sa.Column('status_after', sa.String(50), nullable=True))
    
    # Add status_after column to nseit_request_remark_table
    op.add_column('nseit_request_remark_table', sa.Column('status_after', sa.String(50), nullable=True))
    
    # Add status_after column to dc_remark_table
    op.add_column('dc_remark_table', sa.Column('status_after', sa.String(50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove status_after column from dc_remark_table
    op.drop_column('dc_remark_table', 'status_after')
    
    # Remove status_after column from nseit_request_remark_table
    op.drop_column('nseit_request_remark_table', 'status_after')
    
    # Remove status_after column from lms_remark_table
    op.drop_column('lms_remark_table', 'status_after')
