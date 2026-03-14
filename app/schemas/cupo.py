from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class FondoResumenFinanciero(BaseModel):
    """Resumen financiero de un fondo para Admin Global."""

    id_fondo: int
    nombre_fondo: str
    nit: str
    estado: bool
    valor_total: Decimal
    valor_disponible: Decimal
    saldo_reservado: Decimal
    saldo_ejecutado: Decimal
    porcentaje_ejecucion: float
    porcentaje_compromiso: float
    total_asociados: int
    total_ventas: int
    fecha_creacion_cupo: datetime | None = None
    fecha_actualizacion_cupo: datetime | None = None

    class Config:
        from_attributes = True


class CupoRecarga(BaseModel):
    """
    Esquema para recargar el cupo de un fondo.
    """

    valor_recarga: Decimal = Field(..., gt=0, description="Valor a adicionar al cupo.")


class CupoEstadoRead(BaseModel):
    """
    Esquema de lectura del estado financiero de un cupo.

    Incluye:
    - valor_total: cupo total asignado al fondo.
    - valor_disponible: saldo disponible para futuras reservas.
    - saldo_reservado: suma de microcupos activos (DISPONIBLE).
    - saldo_ejecutado: suma de ventas asociadas a microcupos del fondo.
    """

    id_fondo: int
    nombre_fondo: str = ""
    valor_total: Decimal
    valor_disponible: Decimal
    saldo_reservado: Decimal
    saldo_ejecutado: Decimal
    fecha_creacion: datetime | None = None
    fecha_actualizacion: datetime | None = None

