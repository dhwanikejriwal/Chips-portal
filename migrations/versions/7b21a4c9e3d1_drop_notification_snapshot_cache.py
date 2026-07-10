"""drop_notification_snapshot_cache

Revision ID: 7b21a4c9e3d1
Revises: 4095f9a69687
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b21a4c9e3d1'
down_revision: Union[str, Sequence[str], None] = '4095f9a69687'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Notification counts are now computed live against baseline_at on every
    # request instead of being cached once at login.
    op.drop_column('admin_login_logs', 'notification_snapshot')
    op.drop_column('admin_login_logs', 'new_request_count')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('admin_login_logs', sa.Column('new_request_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('admin_login_logs', sa.Column('notification_snapshot', sa.JSON(), nullable=True))
