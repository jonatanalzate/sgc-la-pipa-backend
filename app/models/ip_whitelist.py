from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.config import Base


class IPWhitelist(Base):
    __tablename__ = "ip_whitelist"

    id_ip: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    direccion_ip: Mapped[str] = mapped_column(String(45), unique=True, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    id_usuario_creador: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id_usuario"), nullable=False
    )
