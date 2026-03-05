from decimal import Decimal
from datetime import datetime

from pydantic import BaseModel


class AdminDashboardStats(BaseModel):
    """
    Métricas globales para el Admin Global.
    """

    total_fondos_activos: int
    total_cupo_general: Decimal
    total_ventas: Decimal
    fondo_top_ventas_id: int | None
    fondo_top_ventas_nombre: str | None
    fondo_top_ventas_monto: Decimal | None


class ProductoMasVendido(BaseModel):
    producto: str
    cantidad_ventas: int
    monto_total: Decimal


class FondoDashboardStats(BaseModel):
    """
    Métricas detalladas para un fondo específico.
    """

    id_fondo: int
    porcentaje_ejecucion_cupo: float  # (Suma Venta.valor_total / CupoGeneral.valor_total) * 100
    porcentaje_compromiso_cupo: float  # ((Ventas + Microcupos DISPONIBLE) / CupoGeneral.valor_total) * 100
    microcupos_vencidos: int
    microcupos_consumidos: int
    top_productos: list[ProductoMasVendido]

