from datetime import datetime

from pydantic import BaseModel

from app.models.cartera import TipoMovimiento


class MovimientoCreate(BaseModel):
  monto: float
  descripcion: str | None = None


class MovimientoRead(BaseModel):
  id_movimiento: int
  id_fondo: int
  tipo: TipoMovimiento
  monto: float
  descripcion: str | None
  fecha: datetime

  class Config:
    from_attributes = True

