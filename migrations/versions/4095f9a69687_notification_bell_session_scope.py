"""notification_bell_session_scope

Revision ID: 4095f9a69687
Revises: 791dd5fa60fa
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4095f9a69687'
down_revision: Union[str, Sequence[str], None] = '791dd5fa60fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('admin_login_logs', sa.Column('baseline_at', sa.DateTime(), nullable=True))
    op.add_column('admin_login_logs', sa.Column('new_request_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('admin_login_logs', sa.Column('notification_snapshot', sa.JSON(), nullable=True))
    # Backfill existing rows so baseline_at can be made NOT NULL: fall back to login_time.
    op.execute("UPDATE admin_login_logs SET baseline_at = login_time WHERE baseline_at IS NULL;")
    op.alter_column('admin_login_logs', 'baseline_at', nullable=False)

    # notifications_last_viewed_at is superseded by the session-scoped baseline_at model.
    op.drop_column('user_login_table', 'notifications_last_viewed_at')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('user_login_table', sa.Column('notifications_last_viewed_at', sa.DateTime(), nullable=True))

    op.drop_column('admin_login_logs', 'notification_snapshot')
    op.drop_column('admin_login_logs', 'new_request_count')
    op.drop_column('admin_login_logs', 'baseline_at')
