"""replace_remark_columns

Revision ID: d6fca808e805
Revises: 85bef9b36dfb
Create Date: 2026-07-12 11:50:44.252664

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6fca808e805'
down_revision: Union[str, Sequence[str], None] = '85bef9b36dfb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop constraints
    op.drop_constraint('lms_remark_table_admin_by_id_fkey', 'lms_remark_table', type_='foreignkey')
    op.drop_constraint('lms_remark_table_candidate_by_id_fkey', 'lms_remark_table', type_='foreignkey')
    
    # Add new columns
    op.add_column('lms_remark_table', sa.Column('sender_id', sa.Integer(), nullable=True))
    op.add_column('lms_remark_table', sa.Column('receiver_id', sa.Integer(), nullable=True))
    
    # Drop old columns
    op.drop_column('lms_remark_table', 'candidate_by_id')
    op.drop_column('lms_remark_table', 'admin_by_id')

    # Same for nseit_request_remark_table
    op.drop_constraint('nseit_request_remark_table_admin_by_id_fkey', 'nseit_request_remark_table', type_='foreignkey')
    op.drop_constraint('nseit_request_remark_table_candidate_by_id_fkey', 'nseit_request_remark_table', type_='foreignkey')
    
    op.add_column('nseit_request_remark_table', sa.Column('sender_id', sa.Integer(), nullable=True))
    op.add_column('nseit_request_remark_table', sa.Column('receiver_id', sa.Integer(), nullable=True))
    
    op.drop_column('nseit_request_remark_table', 'candidate_by_id')
    op.drop_column('nseit_request_remark_table', 'admin_by_id')


def downgrade() -> None:
    """Downgrade schema."""
    # Restore columns
    op.add_column('nseit_request_remark_table', sa.Column('admin_by_id', sa.INTEGER(), nullable=True))
    op.add_column('nseit_request_remark_table', sa.Column('candidate_by_id', sa.INTEGER(), nullable=True))
    op.create_foreign_key('nseit_request_remark_table_candidate_by_id_fkey', 'nseit_request_remark_table', 'candidate_login_table', ['candidate_by_id'], ['id'])
    op.create_foreign_key('nseit_request_remark_table_admin_by_id_fkey', 'nseit_request_remark_table', 'user_login_table', ['admin_by_id'], ['id'])
    op.drop_column('nseit_request_remark_table', 'receiver_id')
    op.drop_column('nseit_request_remark_table', 'sender_id')

    op.add_column('lms_remark_table', sa.Column('admin_by_id', sa.INTEGER(), nullable=True))
    op.add_column('lms_remark_table', sa.Column('candidate_by_id', sa.INTEGER(), nullable=True))
    op.create_foreign_key('lms_remark_table_admin_by_id_fkey', 'lms_remark_table', 'user_login_table', ['admin_by_id'], ['id'])
    op.create_foreign_key('lms_remark_table_candidate_by_id_fkey', 'lms_remark_table', 'candidate_login_table', ['candidate_by_id'], ['id'])
    op.drop_column('lms_remark_table', 'receiver_id')
    op.drop_column('lms_remark_table', 'sender_id')
