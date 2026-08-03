"""add status and include it in the duplicate-identity key

The identity of a record becomes
(name_normalized, aadhar_hash, registrar_code, operator_code, status).

An operator who is DEBOARDED and later ONBOARDED therefore produces two rows
rather than one - the table keeps the history of each state instead of
overwriting it. The newest row (max created_at) is the current state.

status is NOT NULL for the same reason as operator_code: Postgres treats NULLs
as distinct inside a UNIQUE constraint, so a nullable member of the key would
silently stop deduplicating.

Revision ID: f4a6b8c0d2e3
Revises: e3f5a7b9c1d2
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a6b8c0d2e3'
down_revision: Union[str, Sequence[str], None] = 'e3f5a7b9c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = 'operator_master'
UQ = 'uq_operator_master_identity'


def _cols() -> set[str]:
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}


def _constraints() -> set[str]:
    return {u['name'] for u in sa.inspect(op.get_bind()).get_unique_constraints(TABLE)}


def upgrade() -> None:
    if 'status' not in _cols():
        op.add_column(TABLE, sa.Column('status', sa.String(length=30),
                                       nullable=False, server_default=''))
        op.alter_column(TABLE, 'status', server_default=None)
        op.create_index('ix_operator_master_status', TABLE, ['status'])

    if UQ in _constraints():
        op.drop_constraint(UQ, TABLE, type_='unique')
    op.create_unique_constraint(
        UQ, TABLE,
        ['name_normalized', 'aadhar_hash', 'registrar_code', 'operator_code', 'status'],
    )


def downgrade() -> None:
    if UQ in _constraints():
        op.drop_constraint(UQ, TABLE, type_='unique')
    op.create_unique_constraint(
        UQ, TABLE,
        ['name_normalized', 'aadhar_hash', 'registrar_code', 'operator_code'],
    )

    if 'status' in _cols():
        op.drop_index('ix_operator_master_status', table_name=TABLE)
        op.drop_column(TABLE, 'status')
