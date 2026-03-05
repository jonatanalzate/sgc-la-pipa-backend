from datetime import datetime

from pydantic import BaseModel, Field


class IPWhitelistCreate(BaseModel):
    direccion_ip: str = Field(..., max_length=45)
    descripcion: str | None = None


class IPWhitelistRead(BaseModel):
    id_ip: int
    direccion_ip: str
    descripcion: str | None
    activa: bool
    fecha_creacion: datetime
    id_usuario_creador: int

    class Config:
        from_attributes = True


class IPWhitelistUpdate(BaseModel):
    descripcion: str | None = None
    activa: bool | None = None
