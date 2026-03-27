from datetime import datetime, timezone
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.microcupo import MicrocupoEstado, ModalidadEntrega


def _normalizar_tz(v: datetime | None) -> datetime | None:
    """Normaliza cualquier datetime naive a UTC. Reutilizable en todos los schemas."""
    if v is not None and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


class MicrocupoBase(BaseModel):
    monto: Decimal = Field(..., gt=0, description="Monto del microcupo.")
    producto_referencia: str | None = Field(
        default=None,
        max_length=255,
        description="Referencia o identificador del producto asociado.",
    )
    fecha_vencimiento: datetime

    @field_validator("fecha_vencimiento", mode="after")
    @classmethod
    def normalizar_timezone(cls, v: datetime | None) -> datetime | None:
        return _normalizar_tz(v)

    modalidad_entrega: ModalidadEntrega | None = Field(
        default=None,
        description="TIENDA o DOMICILIO. Si no se especifica, queda pendiente de definir.",
    )
    direccion_entrega: str | None = Field(default=None, max_length=255)
    ciudad_entrega: str | None = Field(default=None, max_length=100)
    telefono_contacto: str | None = Field(default=None, max_length=20)
    notas_entrega: str | None = Field(default=None, max_length=500)


class MicrocupoCreate(MicrocupoBase):
    id_asociado: int = Field(..., description="Identificador del asociado beneficiario.")
    fecha_vencimiento: datetime | None = None

    @model_validator(mode="after")
    def validar_domicilio(self) -> "MicrocupoCreate":
        if self.modalidad_entrega == ModalidadEntrega.DOMICILIO:
            if not self.direccion_entrega:
                raise ValueError("La dirección de entrega es obligatoria para modalidad DOMICILIO.")
            if not self.ciudad_entrega:
                raise ValueError("La ciudad de entrega es obligatoria para modalidad DOMICILIO.")
        return self


class MicrocupoUpdate(BaseModel):
    fecha_vencimiento: datetime | None = None
    producto_referencia: str | None = Field(default=None, max_length=255)
    estado: MicrocupoEstado | None = None
    modalidad_entrega: ModalidadEntrega | None = None
    direccion_entrega: str | None = Field(default=None, max_length=255)
    ciudad_entrega: str | None = Field(default=None, max_length=100)
    telefono_contacto: str | None = Field(default=None, max_length=20)
    notas_entrega: str | None = Field(default=None, max_length=500)

    @field_validator("fecha_vencimiento", mode="after")
    @classmethod
    def normalizar_timezone(cls, v: datetime | None) -> datetime | None:
        return _normalizar_tz(v)


class MicrocupoRead(MicrocupoBase):
    id_microcupo: int
    estado: MicrocupoEstado
    id_asociado: int
    id_fondo: int
    fecha_creacion: datetime | None = None
    fecha_actualizacion: datetime | None = None

    class Config:
        from_attributes = True