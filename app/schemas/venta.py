from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class VentaCreate(BaseModel):
    """
    Esquema de entrada para ejecutar una venta.

    - Recibe el identificador del microcupo a consumir.
    - Permite detallar el producto vendido.
    """

    id_microcupo: int = Field(..., description="Identificador del microcupo a consumir.")
    producto_detalle: str | None = Field(
        default=None,
        max_length=255,
        description="Detalle del producto vendido.",
    )


class VentaRead(BaseModel):
    """
    Representación de una venta ejecutada.
    """

    id_venta: int
    fecha: datetime
    valor_total: Decimal
    producto_detalle: str | None
    id_microcupo: int
    id_asociado: int
    id_fondo: int
    id_usuario_tienda: int
    nombre_asociado: str | None = None  # nombre del asociado del microcupo
    id_entrega: int | None = None  # si ya tiene entrega registrada

    class Config:
        from_attributes = True

