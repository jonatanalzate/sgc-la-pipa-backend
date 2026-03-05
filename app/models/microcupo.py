from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.config import Base
from app.models.mixins import TimestampMixin


class MicrocupoEstado(str, PyEnum):
    PENDIENTE = "pendiente"
    APROBADO = "aprobado"
    CONSUMIDO = "consumido"
    VENCIDO = "vencido"
    DENEGADO = "denegado"


class ModalidadEntrega(str, PyEnum):
    TIENDA = "tienda"
    DOMICILIO = "domicilio"


class Microcupo(TimestampMixin, Base):
    __tablename__ = "microcupos"

    id_microcupo: Mapped[int] = mapped_column(primary_key=True, index=True)
    monto: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    estado: Mapped[MicrocupoEstado] = mapped_column(
        SQLEnum(MicrocupoEstado, name="microcupo_estado"),
        nullable=False,
        default=MicrocupoEstado.PENDIENTE,
    )
    fecha_vencimiento: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    producto_referencia: Mapped[str] = mapped_column(String(255), nullable=True)

    modalidad_entrega: Mapped[ModalidadEntrega | None] = mapped_column(
        SQLEnum(ModalidadEntrega, name="modalidad_entrega"),
        nullable=True,
        default=None,
    )
    direccion_entrega: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ciudad_entrega: Mapped[str | None] = mapped_column(String(100), nullable=True)
    telefono_contacto: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notas_entrega: Mapped[str | None] = mapped_column(String(500), nullable=True)

    id_asociado: Mapped[int] = mapped_column(
        ForeignKey("asociados.id_asociado"),
        nullable=False,
    )

    id_fondo: Mapped[int] = mapped_column(
        ForeignKey("fondos.id_fondo"),
        nullable=False,
    )

    asociado: Mapped["Asociado"] = relationship(
        "Asociado",
        back_populates="microcupos",
    )

    ventas: Mapped[list["Venta"]] = relationship(
        "Venta",
        back_populates="microcupo",
    )

