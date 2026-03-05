from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.config import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class Fondo(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "fondos"

    id_fondo: Mapped[int] = mapped_column(primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    nit: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    estado: Mapped[bool] = mapped_column(default=True, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    id_ejecutivo: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id_usuario"),
        nullable=True,
    )

    ejecutivo: Mapped["Usuario | None"] = relationship(
        "Usuario",
        back_populates="fondos_ejecutivo",
        foreign_keys=[id_ejecutivo],
    )

    cupos_generales: Mapped[list["CupoGeneral"]] = relationship(
        "CupoGeneral",
        back_populates="fondo",
    )

    asociados: Mapped[list["Asociado"]] = relationship(
        "Asociado",
        back_populates="fondo",
    )

    usuarios: Mapped[list["Usuario"]] = relationship(
        "Usuario",
        back_populates="fondo",
        foreign_keys="Usuario.id_fondo",
    )

