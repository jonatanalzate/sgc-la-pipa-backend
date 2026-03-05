from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.config import Base


class Auditoria(Base):
    __tablename__ = "auditorias"

    id_auditoria: Mapped[int] = mapped_column(primary_key=True, index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accion: Mapped[str] = mapped_column(String(255), nullable=False)

    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id_usuario"),
        nullable=False,
    )

    usuario: Mapped["Usuario"] = relationship(
        "Usuario",
        back_populates="auditorias",
    )

