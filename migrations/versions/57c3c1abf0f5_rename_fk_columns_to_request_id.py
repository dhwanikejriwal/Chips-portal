"""rename_fk_columns_to_request_id

Revision ID: 57c3c1abf0f5
Revises: 3ba14f3ca08d
Create Date: 2026-07-11 21:54:01.869726

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57c3c1abf0f5'
down_revision: Union[str, Sequence[str], None] = '3ba14f3ca08d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('ALTER TABLE candidate_login_table RENAME COLUMN r_id TO request_id;')
    op.execute('ALTER TABLE "LMS_table" RENAME COLUMN "R_Id" TO request_id;')
    op.execute('ALTER TABLE nseit_request_table RENAME COLUMN "R_Id" TO request_id;')
    op.execute('ALTER TABLE dc_remark_table RENAME COLUMN r_id TO request_id;')
    op.execute('ALTER TABLE lms_remark_table RENAME COLUMN "R_id" TO request_id;')
    op.execute('ALTER TABLE nseit_request_remark_table RENAME COLUMN "R_Id" TO request_id;')


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('ALTER TABLE candidate_login_table RENAME COLUMN request_id TO r_id;')
    op.execute('ALTER TABLE "LMS_table" RENAME COLUMN request_id TO "R_Id";')
    op.execute('ALTER TABLE nseit_request_table RENAME COLUMN request_id TO "R_Id";')
    op.execute('ALTER TABLE dc_remark_table RENAME COLUMN request_id TO r_id;')
    op.execute('ALTER TABLE lms_remark_table RENAME COLUMN request_id TO "R_id";')
    op.execute('ALTER TABLE nseit_request_remark_table RENAME COLUMN request_id TO "R_Id";')
