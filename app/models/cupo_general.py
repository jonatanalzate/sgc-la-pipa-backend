from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.config import Base
from app.models.mixins import TimestampMixin


class CupoGeneral(TimestampMixin, Base):
    __tablename__ = "cupos_generales"

    id_cupo_general: Mapped[int] = mapped_column(primary_key=True, index=True)
    valor_total: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    valor_disponible: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)

    id_fondo: Mapped[int] = mapped_column(
        ForeignKey("fondos.id_fondo"),
        nullable=False,
    )

    fondo: Mapped["Fondo"] = relationship(
        "Fondo",
        back_populates="cupos_generales",
    )

