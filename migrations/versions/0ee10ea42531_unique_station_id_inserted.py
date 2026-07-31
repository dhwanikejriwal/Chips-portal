"""unique constraint on station_id_requests.station_id_inserted

Revision ID: 0ee10ea42531
Revises: 39c53dc713eb
Create Date: 2026-07-16 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '0ee10ea42531'
down_revision: Union[str, Sequence[str], None] = '39c53dc713eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT_NAME = 'uq_station_id_requests_station_id_inserted'


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
