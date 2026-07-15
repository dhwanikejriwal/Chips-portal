"""add laptop_serial_no and laptop_brand to l1_registration_requests

Revision ID: c9f1a3b5d7e8
Revises: b8e0c2d4f6a7
Create Date: 2026-07-12 01:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9f1a3b5d7e8'
down_revision: Union[str, Sequence[str], None] = 'b8e0c2d4f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('l1_registration_requests')]
    if 'laptop_serial_no' not in columns:
        op.add_column('l1_registration_requests', sa.Column('laptop_serial_no', sa.String(), nullable=True))
    if 'laptop_brand' not in columns:
        op.add_column('l1_registration_requests', sa.Column('laptop_brand', sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c['name'] for c in inspector.get_columns('l1_registration_requests')]
    if 'laptop_brand' in columns:
        op.drop_column('l1_registration_requests', 'laptop_brand')
    if 'laptop_serial_no' in columns:
        op.drop_column('l1_registration_requests', 'laptop_serial_no')
