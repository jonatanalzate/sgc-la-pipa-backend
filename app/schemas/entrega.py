from datetime import datetime

from pydantic import BaseModel, Field


class EntregaCreate(BaseModel):
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
    nombre_asociado: str | None = None
    nombre_usuario_tienda: str | None = None

    class Config:
        from_attributes = True
