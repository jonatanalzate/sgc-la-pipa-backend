from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.config import Base


class Entrega(Base):
    __tablename__ = "entregas"

    id_entrega: Mapped[int] = mapped_column(primary_key=True, index=True)
    tipo_entrega: Mapped[str] = mapped_column(String(100), nullable=False)
    fecha_entrega: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    id_venta: Mapped[int] = mapped_column(
        ForeignKey("ventas.id_venta"),
        nullable=False,
        unique=True,
    )

    id_fondo: Mapped[int] = mapped_column(
        ForeignKey("fondos.id_fondo"),
        nullable=False,
    )

    venta: Mapped["Venta"] = relationship(
        "Venta",
        back_populates="entrega",
    )

