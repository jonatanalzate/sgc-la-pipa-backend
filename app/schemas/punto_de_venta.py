from pydantic import BaseModel, Field


class PuntoDeVentaCreate(BaseModel):
    nombre: str = Field(..., max_length=150)
    direccion: str | None = Field(default=None, max_length=255)
    ciudad: str = Field(..., max_length=150)


class PuntoDeVentaRead(BaseModel):
    id_punto_venta: int
    nombre: str
    direccion: str | None
    activo: bool
    ciudad: str

    class Config:
        from_attributes = True
