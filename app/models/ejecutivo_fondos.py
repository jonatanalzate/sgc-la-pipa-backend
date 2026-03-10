from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database.config import Base


class EjecutivoFondo(Base):
    __tablename__ = "ejecutivo_fondos"

    id_usuario: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("usuarios.id_usuario", ondelete="CASCADE"),
        primary_key=True,
    )
    id_fondo: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("fondos.id_fondo", ondelete="CASCADE"),
        primary_key=True,
    )

