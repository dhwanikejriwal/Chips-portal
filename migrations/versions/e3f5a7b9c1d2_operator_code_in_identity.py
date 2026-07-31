"""add operator_code and include it in the duplicate-identity key

The identity of a record becomes
(name_normalized, aadhar_hash, registrar_code, operator_code), so the same
person under a different operator code is a distinct record.

operator_code is NOT NULL on purpose: Postgres treats NULLs as distinct inside
a UNIQUE constraint, so a nullable column would silently stop deduplicating
whenever the value were missing. Rows without an operator code are rejected at
ingest instead.

Revision ID: e3f5a7b9c1d2
Revises: d2e4f6a8b0c1
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3f5a7b9c1d2'
down_revision: Union[str, Sequence[str], None] = 'd2e4f6a8b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'operator_master'
UQ = 'uq_operator_master_identity'


def _cols() -> set[str]:
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def _constraints() -> set[str]:
    return {u['name'] for u in sa.inspect(op.get_bind()).get_unique_constraints(TABLE)}


def upgrade() -> None:
    if 'operator_code' not in _cols():
        # server_default lets the NOT NULL apply to any pre-existing rows; it is
        # dropped immediately so the application must always supply a value.
        op.add_column(TABLE, sa.Column('operator_code', sa.String(length=100),
                                       nullable=False, server_default=''))
        op.alter_column(TABLE, 'operator_code', server_default=None)
        op.create_index('ix_operator_master_operator_code', TABLE, ['operator_code'])

    if UQ in _constraints():
        op.drop_constraint(UQ, TABLE, type_='unique')
    op.create_unique_constraint(
        UQ, TABLE,
        ['name_normalized', 'aadhar_hash', 'registrar_code', 'operator_code'],
    )


def downgrade() -> None:
    if UQ in _constraints():
        op.drop_constraint(UQ, TABLE, type_='unique')
    op.create_unique_constraint(
        UQ, TABLE, ['name_normalized', 'aadhar_hash', 'registrar_code'])

    if 'operator_code' in _cols():
        op.drop_index('ix_operator_master_operator_code', table_name=TABLE)
        op.drop_column(TABLE, 'operator_code')
