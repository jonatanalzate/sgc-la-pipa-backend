from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.config import Base


class Venta(Base):
    __tablename__ = "ventas"

    id_venta: Mapped[int] = mapped_column(primary_key=True, index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valor_total: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    producto_detalle: Mapped[str] = mapped_column(String(255), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(String(500), nullable=True)

    id_microcupo: Mapped[int] = mapped_column(
        ForeignKey("microcupos.id_microcupo"),
        nullable=False,
    )

    id_asociado: Mapped[int] = mapped_column(
        ForeignKey("asociados.id_asociado"),
        nullable=False,
    )

    id_fondo: Mapped[int] = mapped_column(
        ForeignKey("fondos.id_fondo"),
        nullable=False,
    )

    id_usuario_tienda: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id_usuario"),
        nullable=False,
    )

    numero_factura: Mapped[str | None] = mapped_column(String(100), nullable=True)
    id_punto_venta: Mapped[int | None] = mapped_column(
        ForeignKey("puntos_de_venta.id_punto_venta"),
        nullable=True,
    )
    tipo_entrega: Mapped[str | None] = mapped_column(String(50), nullable=True)
    numero_guia: Mapped[str | None] = mapped_column(String(150), nullable=True)
    origen: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destino: Mapped[str | None] = mapped_column(String(255), nullable=True)

    microcupo: Mapped["Microcupo"] = relationship(
        "Microcupo",
        back_populates="ventas",
    )

    usuario_tienda: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="ventas",
    )

    entrega: Mapped["Entrega | None"] = relationship(
        "Entrega",
        back_populates="venta",
        uselist=False,
    )

    punto_de_venta: Mapped["PuntoDeVenta | None"] = relationship(
        "PuntoDeVenta",
        back_populates="ventas",
    )

