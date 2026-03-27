"""fase3_puntos_venta_campos_venta

Revision ID: c3f8a1b2d4e5
Revises: a1b2c3d4e5f6
Create Date: 2026-03-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f8a1b2d4e5"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "puntos_de_venta",
        sa.Column("id_punto_venta", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("direccion", sa.String(length=255), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id_fondo", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["id_fondo"], ["fondos.id_fondo"]),
        sa.PrimaryKeyConstraint("id_punto_venta"),
    )
    op.create_index(
        "ix_puntos_de_venta_id_punto_venta",
        "puntos_de_venta",
        ["id_punto_venta"],
        unique=False,
    )

    op.add_column("ventas", sa.Column("numero_factura", sa.String(length=100), nullable=True))
    op.add_column("ventas", sa.Column("id_punto_venta", sa.Integer(), nullable=True))
    op.add_column("ventas", sa.Column("tipo_entrega", sa.String(length=50), nullable=True))
    op.add_column("ventas", sa.Column("numero_guia", sa.String(length=150), nullable=True))
    op.add_column("ventas", sa.Column("origen", sa.String(length=255), nullable=True))
    op.add_column("ventas", sa.Column("destino", sa.String(length=255), nullable=True))
    op.create_foreign_key(
        "fk_ventas_id_punto_venta_puntos_de_venta",
        "ventas",
        "puntos_de_venta",
        ["id_punto_venta"],
        ["id_punto_venta"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_ventas_id_punto_venta_puntos_de_venta", "ventas", type_="foreignkey")
    op.drop_column("ventas", "destino")
    op.drop_column("ventas", "origen")
    op.drop_column("ventas", "numero_guia")
    op.drop_column("ventas", "tipo_entrega")
    op.drop_column("ventas", "id_punto_venta")
    op.drop_column("ventas", "numero_factura")

    op.drop_index("ix_puntos_de_venta_id_punto_venta", table_name="puntos_de_venta")
    op.drop_table("puntos_de_venta")
