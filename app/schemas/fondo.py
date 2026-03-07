from datetime import datetime

from pydantic import BaseModel, Field


class FondoBase(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=150)
    nit: str = Field(..., min_length=3, max_length=50)


class FondoCreate(FondoBase):
    """
    Esquema para creación de fondos.

    - estado se inicializa siempre en True.
    - El cupo general se crea en 0 automáticamente en el endpoint.
    """


class FondoUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=3, max_length=150)
    nit: str | None = Field(default=None, min_length=3, max_length=50)
    estado: bool | None = None
    id_ejecutivo: int | None = None


class FondoRead(FondoBase):
    id_fondo: int
    estado: bool
    activo: bool = True
    fecha_creacion: datetime | None = None
    fecha_actualizacion: datetime | None = None
    fecha_eliminacion: datetime | None = None

    class Config:
        from_attributes = True

class FondoCargaMasivaResult(BaseModel):
    creados: int
    errores: int
    detalle_errores: list[str] = []