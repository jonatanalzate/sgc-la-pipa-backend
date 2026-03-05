"""add_timestamp_fields

Revision ID: 7ae2f8d2393e
Revises: 
Create Date: 2026-02-25 11:54:03.230276

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7ae2f8d2393e"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # fondos: agrega fecha_creacion, fecha_actualizacion, fecha_eliminacion
    op.add_column(
        "fondos",
        sa.Column(
            "fecha_creacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "fondos",
        sa.Column(
            "fecha_actualizacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "fondos",
        sa.Column("fecha_eliminacion", sa.DateTime(timezone=True), nullable=True),
    )

    # usuarios: agrega fecha_creacion, fecha_actualizacion, fecha_eliminacion
    op.add_column(
        "usuarios",
        sa.Column(
            "fecha_creacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "usuarios",
        sa.Column(
            "fecha_actualizacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "usuarios",
        sa.Column("fecha_eliminacion", sa.DateTime(timezone=True), nullable=True),
    )

    # asociados: agrega fecha_creacion, fecha_actualizacion, fecha_eliminacion
    op.add_column(
        "asociados",
        sa.Column(
            "fecha_creacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "asociados",
        sa.Column(
            "fecha_actualizacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "asociados",
        sa.Column("fecha_eliminacion", sa.DateTime(timezone=True), nullable=True),
    )

    # microcupos: agrega fecha_creacion, fecha_actualizacion
    op.add_column(
        "microcupos",
        sa.Column(
            "fecha_creacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "microcupos",
        sa.Column(
            "fecha_actualizacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # cupos_generales: agrega fecha_creacion, fecha_actualizacion
    op.add_column(
        "cupos_generales",
        sa.Column(
            "fecha_creacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "cupos_generales",
        sa.Column(
            "fecha_actualizacion",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    # cupos_generales
    op.drop_column("cupos_generales", "fecha_actualizacion")
    op.drop_column("cupos_generales", "fecha_creacion")

    # microcupos
    op.drop_column("microcupos", "fecha_actualizacion")
    op.drop_column("microcupos", "fecha_creacion")

    # asociados
    op.drop_column("asociados", "fecha_eliminacion")
    op.drop_column("asociados", "fecha_actualizacion")
    op.drop_column("asociados", "fecha_creacion")

    # usuarios
    op.drop_column("usuarios", "fecha_eliminacion")
    op.drop_column("usuarios", "fecha_actualizacion")
    op.drop_column("usuarios", "fecha_creacion")

    # fondos
    op.drop_column("fondos", "fecha_eliminacion")
    op.drop_column("fondos", "fecha_actualizacion")
    op.drop_column("fondos", "fecha_creacion")
