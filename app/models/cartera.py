from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database.config import Base


class TipoMovimiento(str, enum.Enum):
    RECARGA = "RECARGA"
    ABONO = "ABONO"


class MovimientoCartera(Base):
    __tablename__ = "movimientos_cartera"

    id_movimiento: Mapped[int] = mapped_column(primary_key=True, index=True)
    id_fondo: Mapped[int] = mapped_column(
        ForeignKey("fondos.id_fondo"),
        nullable=False,
    )

    fondo: Mapped["Fondo"] = relationship("Fondo")

    tipo: Mapped[TipoMovimiento] = mapped_column(Enum(TipoMovimiento), nullable=False)
    monto: Mapped[float] = mapped_column(Float, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String, nullable=True)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

