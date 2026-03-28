from decimal import Decimal

from pydantic import BaseModel


class FondoResumenRead(BaseModel):
    """
    Resumen financiero de un fondo para cierre:

    - total_ventas: número de ventas ejecutadas.
    - monto_ejecutado: valor total vendido.
    - monto_reservado: valor aún reservado en microcupos disponibles.
    """

    id_fondo: int
    total_ventas: int
    monto_ejecutado: Decimal
    monto_reservado: Decimal


class VentasPorEjecutivoItem(BaseModel):
    nombre_ejecutivo: str
    total_ventas: int
    monto_total: Decimal


class VentasPorFondoItem(BaseModel):
    nombre_fondo: str
    total_ventas: int
    monto_total: Decimal


class EvolucionVentasItem(BaseModel):
    periodo: str
    total_ventas: int
    monto_total: Decimal


class MicrocuposEstadoItem(BaseModel):
    estado: str
    cantidad: int
    monto_total: Decimal

