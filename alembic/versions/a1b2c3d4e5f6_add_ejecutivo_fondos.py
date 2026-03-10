"""add_ejecutivo_fondos

Revision ID: a1b2c3d4e5f6
Revises: f8e7d6c5b4a3
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f8e7d6c5b4a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ejecutivo_fondos",
        sa.Column("id_usuario", sa.Integer(), nullable=False),
        sa.Column("id_fondo", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_usuario"],
            ["usuarios.id_usuario"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["id_fondo"],
            ["fondos.id_fondo"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_usuario", "id_fondo"),
    )
    op.create_index(
        "ix_ejecutivo_fondos_id_usuario",
        "ejecutivo_fondos",
        ["id_usuario"],
    )
    op.create_index(
        "ix_ejecutivo_fondos_id_fondo",
        "ejecutivo_fondos",
        ["id_fondo"],
    )
    op.execute(
        """
        INSERT INTO ejecutivo_fondos (id_usuario, id_fondo)
        VALUES (16, 8)
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_ejecutivo_fondos_id_fondo", table_name="ejecutivo_fondos")
    op.drop_index("ix_ejecutivo_fondos_id_usuario", table_name="ejecutivo_fondos")
    op.drop_table("ejecutivo_fondos")

