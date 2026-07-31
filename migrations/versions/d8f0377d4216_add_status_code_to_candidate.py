"""add_status_code_to_candidate

Revision ID: d8f0377d4216
Revises: 5ae425ef03a3
Create Date: 2026-06-28 11:15:06.081456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd8f0377d4216'
down_revision: Union[str, Sequence[str], None] = '5ae425ef03a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass
    # ### end Alembic commands ###

def downgrade() -> None:
    pass
