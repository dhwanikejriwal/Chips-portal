"""add aadhar_last4 for the name + last-4 search mode

The full-Aadhar search HMACs the whole number, and that fingerprint has no
relationship to a fingerprint of the last four digits, so last-4 lookup cannot
reuse aadhar_hash. This column stores the last four digits in the clear (four
digits on their own are low sensitivity) purely as a lookup key.

It is NOT part of the identity/UNIQUE key - it is derived from the same Aadhar
that aadhar_hash already covers, so adding it would change nothing.

Left nullable so this revision never fails on existing rows; the values are
backfilled by backend.services.operator_master_ingest.backfill_last4(), which
decrypts aadhar_encrypted server-side.

Revision ID: a5c7d9e1f3b4
Revises: f4a6b8c0d2e3
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5c7d9e1f3b4'
down_revision: Union[str, Sequence[str], None] = 'f4a6b8c0d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'operator_master'


def _cols() -> set[str]:
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    if 'aadhar_last4' not in _cols():
        op.add_column(TABLE, sa.Column('aadhar_last4', sa.String(length=4), nullable=True))
        # Mode 2 always filters on both columns together.
        op.create_index('ix_operator_master_name_last4', TABLE,
                        ['name_normalized', 'aadhar_last4'])


def downgrade() -> None:
    if 'aadhar_last4' in _cols():
        op.drop_index('ix_operator_master_name_last4', table_name=TABLE)
        op.drop_column(TABLE, 'aadhar_last4')
