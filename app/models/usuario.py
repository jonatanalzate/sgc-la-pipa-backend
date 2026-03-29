from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.config import Base
from app.models.ejecutivo_fondos import EjecutivoFondo
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class Usuario(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "usuarios"

    id_usuario: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    intentos_fallidos: Mapped[int] = mapped_column(
        default=0, nullable=False
    )
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    bloqueado_permanente: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    reset_token: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    reset_token_expira: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    id_rol: Mapped[int] = mapped_column(
        ForeignKey("roles.id_rol"),
        nullable=False,
    )

    id_fondo: Mapped[int | None] = mapped_column(
        ForeignKey("fondos.id_fondo"),
        nullable=True,
    )

    rol: Mapped["Rol"] = relationship(
        "Rol",
        back_populates="usuarios",
    )

    fondo: Mapped["Fondo | None"] = relationship(
        "Fondo",
        back_populates="usuarios",
        foreign_keys=[id_fondo],
    )

    fondos_ejecutivo: Mapped[list["Fondo"]] = relationship(
        "Fondo",
        back_populates="ejecutivo",
        foreign_keys="Fondo.id_ejecutivo",
    )

    fondos_asignados: Mapped[list["Fondo"]] = relationship(
        "Fondo",
        secondary="ejecutivo_fondos",
        primaryjoin="Usuario.id_usuario == foreign(EjecutivoFondo.id_usuario)",
        secondaryjoin="Fondo.id_fondo == foreign(EjecutivoFondo.id_fondo)",
        viewonly=False,
        lazy="selectin",
    )

    ventas: Mapped[list["Venta"]] = relationship(
        "Venta",
        back_populates="usuario_tienda",
        foreign_keys="Venta.id_usuario_tienda",
    )

    auditorias: Mapped[list["Auditoria"]] = relationship(
        "Auditoria",
        back_populates="usuario",
    )

