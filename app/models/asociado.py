from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.config import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class Asociado(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "asociados"

    id_asociado: Mapped[int] = mapped_column(primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    documento: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    estado: Mapped[bool] = mapped_column(default=True, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    id_fondo: Mapped[int] = mapped_column(
        ForeignKey("fondos.id_fondo"),
        nullable=False,
    )

    fondo: Mapped["Fondo"] = relationship(
        "Fondo",
        back_populates="asociados",
    )

    microcupos: Mapped[list["Microcupo"]] = relationship(
        "Microcupo",
        back_populates="asociado",
    )

