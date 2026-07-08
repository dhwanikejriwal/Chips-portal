"""remove remark_to_uidai from OperatorActivationRequest

Revision ID: 90585e623d2c
Revises: df3f475a05ed
Create Date: 2026-07-06 17:10:28.310001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "90585e623d2c"
down_revision: Union[str, Sequence[str], None] = "df3f475a05ed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("operator_activation_requests", "remark_to_uidai")


def downgrade() -> None:
    op.add_column("operator_activation_requests", sa.Column("remark_to_uidai", sa.Text(), nullable=True))
