from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.config import Base


class Rol(Base):
    __tablename__ = "roles"

    id_rol: Mapped[int] = mapped_column(primary_key=True, index=True)
    nombre_rol: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    usuarios: Mapped[list["Usuario"]] = relationship(
        "Usuario",
        back_populates="rol",
    )

