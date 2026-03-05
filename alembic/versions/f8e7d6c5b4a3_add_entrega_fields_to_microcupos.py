"""add_entrega_fields_to_microcupos

Revision ID: f8e7d6c5b4a3
Revises: 7ae2f8d2393e
Create Date: 2026-02-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8e7d6c5b4a3"
down_revision: Union[str, None] = "7ae2f8d2393e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    modalidad_enum = sa.Enum("tienda", "domicilio", name="modalidad_entrega")
    modalidad_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "microcupos",
        sa.Column(
            "modalidad_entrega",
            sa.Enum("tienda", "domicilio", name="modalidad_entrega"),
            nullable=True,
        ),
    )
    op.add_column("microcupos", sa.Column("direccion_entrega", sa.String(255), nullable=True))
    op.add_column("microcupos", sa.Column("ciudad_entrega", sa.String(100), nullable=True))
    op.add_column("microcupos", sa.Column("telefono_contacto", sa.String(20), nullable=True))
    op.add_column("microcupos", sa.Column("notas_entrega", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("microcupos", "notas_entrega")
    op.drop_column("microcupos", "telefono_contacto")
    op.drop_column("microcupos", "ciudad_entrega")
    op.drop_column("microcupos", "direccion_entrega")
    op.drop_column("microcupos", "modalidad_entrega")
    sa.Enum(name="modalidad_entrega").drop(op.get_bind())
