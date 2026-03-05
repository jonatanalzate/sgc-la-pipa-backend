from datetime import datetime

from pydantic import BaseModel, Field


class EntregaCreate(BaseModel):
    """
    Esquema de entrada para registrar la entrega de un producto vendido.

    - Solo puede existir una entrega por venta.
    - El tipo de entrega se espera como 'Presencial' o 'Envío' (validado a nivel de API).
    """

    id_venta: int = Field(..., description="Identificador de la venta asociada.")
    tipo_entrega: str = Field(
        ...,
        max_length=100,
        description="Tipo de entrega (ej. 'Presencial', 'Envío').",
    )


class EntregaRead(BaseModel):
    id_entrega: int
    tipo_entrega: str
    fecha_entrega: datetime
    id_venta: int
    id_fondo: int

    class Config:
        from_attributes = True

