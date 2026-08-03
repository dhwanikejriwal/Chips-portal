"""align operator_master with the specified schema

Revision c1d3e5f7a9b2 created the table with the `aadhaar_*` spelling plus
operator_code / status / aadhaar_last4 / batch_id. The agreed schema is
`aadhar_*` with an `agency` column and no operator/status columns, so this
revision renames and reshapes the table to match.

Safe to run: the table holds no rows at this point, and renames preserve the
identity UNIQUE constraint rather than dropping and recreating it.

Revision ID: d2e4f6a8b0c1
Revises: c1d3e5f7a9b2
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e4f6a8b0c1'
down_revision: Union[str, Sequence[str], None] = 'c1d3e5f7a9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'operator_master'


def _cols() -> set[str]:
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def _indexes() -> set[str]:
    return {i['name'] for i in sa.inspect(op.get_bind()).get_indexes(TABLE)}


def upgrade() -> None:
    cols = _cols()

    # aadhaar_* -> aadhar_*. The rename carries the UNIQUE constraint and the
    # index along with the column, so neither needs rebuilding.
    if 'aadhaar_hash' in cols and 'aadhar_hash' not in cols:
        op.alter_column(TABLE, 'aadhaar_hash', new_column_name='aadhar_hash')
    if 'aadhaar_encrypted' in cols and 'aadhar_encrypted' not in cols:
        op.alter_column(TABLE, 'aadhaar_encrypted', new_column_name='aadhar_encrypted')

    # Columns that are not part of the agreed schema.
    for dropped in ('aadhaar_last4', 'operator_code', 'status', 'batch_id'):
        if dropped in cols:
            op.drop_column(TABLE, dropped)

    if 'agency' not in cols:
        op.add_column(TABLE, sa.Column('agency', sa.String(length=100), nullable=True))
        op.create_index('ix_operator_master_agency', TABLE, ['agency'])
        op.create_index('ix_operator_master_registrar_agency', TABLE,
                        ['registrar_code', 'agency'])

    # Stale index names left behind by the dropped columns.
    for stale in ('ix_operator_master_aadhaar_hash', 'ix_operator_master_registrar_status'):
        if stale in _indexes():
            op.drop_index(stale, table_name=TABLE)
    if 'ix_operator_master_aadhar_hash' not in _indexes():
        op.create_index('ix_operator_master_aadhar_hash', TABLE, ['aadhar_hash'])


def downgrade() -> None:
    cols = _cols()

    for stale in ('ix_operator_master_registrar_agency', 'ix_operator_master_agency'):
        if stale in _indexes():
            op.drop_index(stale, table_name=TABLE)
    if 'agency' in cols:
        op.drop_column(TABLE, 'agency')

    if 'aadhar_hash' in cols and 'aadhaar_hash' not in cols:
        op.alter_column(TABLE, 'aadhar_hash', new_column_name='aadhaar_hash')
    if 'aadhar_encrypted' in cols and 'aadhaar_encrypted' not in cols:
        op.alter_column(TABLE, 'aadhar_encrypted', new_column_name='aadhaar_encrypted')

    op.add_column(TABLE, sa.Column('aadhaar_last4', sa.String(length=4), nullable=True))
    op.add_column(TABLE, sa.Column('operator_code', sa.String(length=100),
                                   nullable=False, server_default=''))
    op.add_column(TABLE, sa.Column('status', sa.String(length=30),
                                   nullable=False, server_default=''))
    op.add_column(TABLE, sa.Column('batch_id', sa.String(length=36), nullable=True))
