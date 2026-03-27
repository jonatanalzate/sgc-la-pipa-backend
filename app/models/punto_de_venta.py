from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.config import Base


class PuntoDeVenta(Base):
    __tablename__ = "puntos_de_venta"

    id_punto_venta: Mapped[int] = mapped_column(primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activo: Mapped[bool] = mapped_column(default=True)
    ciudad: Mapped[str] = mapped_column(
        String(150), nullable=False, server_default=text("''")
    )

    ventas: Mapped[list["Venta"]] = relationship("Venta", back_populates="punto_de_venta")
