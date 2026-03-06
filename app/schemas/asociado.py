from datetime import datetime

from pydantic import BaseModel, Field


class AsociadoBase(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=150)
    documento: str = Field(..., min_length=3, max_length=50)


class AsociadoCreate(AsociadoBase):
    """
    Creación individual de asociado.

    - El id_fondo se determina a partir del usuario autenticado (multi-tenancy).
    """


class AsociadoBatchCreate(AsociadoBase):
    """
    Esquema para carga masiva de asociados.

    - El id_fondo se determina a partir del usuario autenticado (multi-tenancy).
    """


class AsociadoUpdate(BaseModel):
    """Esquema para actualización parcial de asociado (PATCH)."""

    nombre: str | None = Field(default=None, min_length=3, max_length=150)
    documento: str | None = Field(default=None, min_length=3, max_length=50)
    estado: bool | None = None


class AsociadoRead(AsociadoBase):
    id_asociado: int
    id_fondo: int | None = None
    estado: bool
    activo: bool = True
    fecha_creacion: datetime | None = None
    fecha_actualizacion: datetime | None = None
    fecha_eliminacion: datetime | None = None

    class Config:
        from_attributes = True


class AsociadoBulkUploadResult(BaseModel):
    """Resumen de una carga masiva desde Excel/CSV."""

    creados: int = Field(..., description="Cantidad de asociados creados exitosamente.")
    errores: int = Field(..., description="Cantidad de filas con errores.")
    detalles_errores: list[str] = Field(
        default_factory=list,
        description="Lista de mensajes de error por fila (ej. 'Fila 2: documento duplicado').",
    )

