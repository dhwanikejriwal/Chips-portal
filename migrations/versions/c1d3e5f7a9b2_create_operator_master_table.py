"""create operator_master table if absent (name + hashed/encrypted aadhar)

The table already exists in the target environment; this revision only
provisions it on a fresh database and is a no-op everywhere else, so it never
recreates or alters live data.

Revision ID: c1d3e5f7a9b2
Revises: a1b2c3d4e5f6
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d3e5f7a9b2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'operator_master'


def _exists() -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(TABLE)


def upgrade() -> None:
    if _exists():
        return
    op.create_table(
        TABLE,
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('name_normalized', sa.String(length=150), nullable=False),
        sa.Column('aadhar_hash', sa.String(length=64), nullable=False),
        sa.Column('aadhar_encrypted', sa.Text(), nullable=False),
        sa.Column('registrar_code', sa.String(length=50), nullable=False),
        sa.Column('agency', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'name_normalized', 'aadhar_hash', 'registrar_code',
            name='uq_operator_master_identity',
        ),
    )
    op.create_index('ix_operator_master_id', TABLE, ['id'])
    op.create_index('ix_operator_master_name_normalized', TABLE, ['name_normalized'])
    op.create_index('ix_operator_master_aadhar_hash', TABLE, ['aadhar_hash'])
    op.create_index('ix_operator_master_registrar_code', TABLE, ['registrar_code'])
    op.create_index('ix_operator_master_agency', TABLE, ['agency'])
    op.create_index('ix_operator_master_registrar_agency', TABLE, ['registrar_code', 'agency'])


def downgrade() -> None:
    if not _exists():
        return
    op.drop_table(TABLE)
