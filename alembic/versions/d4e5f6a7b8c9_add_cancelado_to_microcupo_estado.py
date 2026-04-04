"""add_cancelado_to_microcupo_estado

Revision ID: d4e5f6a7b8c9
Revises: c3f8a1b2d4e5
Create Date: 2026-04-04

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3f8a1b2d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE microcupo_estado ADD VALUE IF NOT EXISTS 'CANCELADO'")


def downgrade() -> None:
    pass
