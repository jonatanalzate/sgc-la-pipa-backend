from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class VentaCreate(BaseModel):
    id_microcupo: int = Field(..., description="Identificador del microcupo a consumir.")
    producto_detalle: str | None = Field(default=None, max_length=255)
    observaciones: str | None = Field(default=None, max_length=500)
    numero_factura: str | None = Field(default=None, max_length=100)
    id_punto_venta: int | None = Field(default=None)
    tipo_entrega: Literal["TIENDA", "DOMICILIO"] | None = Field(default=None)
    numero_guia: str | None = Field(default=None, max_length=150)
    origen: str | None = Field(default=None, max_length=255)
    destino: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validar_campos_domicilio(self):
        if self.tipo_entrega == "DOMICILIO":
            faltantes = []
            if not self.numero_guia:
                faltantes.append("numero_guia")
            if not self.origen:
                faltantes.append("origen")
            if not self.destino:
                faltantes.append("destino")
            if faltantes:
                raise ValueError(
                    f"Los campos {faltantes} son requeridos cuando tipo_entrega es DOMICILIO"
                )
        return self


class VentaRead(BaseModel):
    id_venta: int
    fecha: datetime
    valor_total: Decimal
    producto_detalle: str | None
    observaciones: str | None = None
    id_microcupo: int
    id_asociado: int
    id_fondo: int
    id_usuario_tienda: int
    nombre_asociado: str | None = None
    id_entrega: int | None = None
    numero_factura: str | None = None
    id_punto_venta: int | None = None
    nombre_punto_venta: str | None = None
    tipo_entrega: str | None = None
    numero_guia: str | None = None
    origen: str | None = None
    destino: str | None = None

    class Config:
        from_attributes = True
