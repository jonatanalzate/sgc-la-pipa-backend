from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_user,
    get_tenant_id,
    get_tenant_ids,
    require_roles,
)
from app.core.roles import ADMIN_FONDO, ADMIN_GLOBAL, EJECUTIVO_COMERCIAL
from app.database.config import get_db
from app.models.cupo_general import CupoGeneral
from app.models.fondo import Fondo
from app.models.asociado import Asociado
from app.models.microcupo import Microcupo, MicrocupoEstado
from app.models.usuario import Usuario
from app.models.venta import Venta
from app.schemas.dashboard import (
    AdminDashboardStats,
    FondoDashboardStats,
    ProductoMasVendido,
)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/admin/estadisticas",
    response_model=AdminDashboardStats,
)
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    GET /dashboard/admin/stats - Resumen global. Solo ADMIN_GLOBAL.
    """

    # Total de fondos activos
    fondos_activos_query: Select[tuple] = select(func.count(Fondo.id_fondo)).where(
        Fondo.estado.is_(True),
        Fondo.activo == True,
    )
    fondos_activos_result = await db.execute(fondos_activos_query)
    total_fondos_activos: int = fondos_activos_result.scalar_one()

    # Suma total de todos los CupoGeneral.valor_total
    total_cupo_query: Select[tuple] = select(
        func.coalesce(func.sum(CupoGeneral.valor_total), 0)
    )
    total_cupo_result = await db.execute(total_cupo_query)
    total_cupo_general = total_cupo_result.scalar_one()

    # Suma total de todas las ventas realizadas en el sistema
    total_ventas_query: Select[tuple] = select(
        func.coalesce(func.sum(Venta.valor_total), 0)
    )
    total_ventas_result = await db.execute(total_ventas_query)
    total_ventas = total_ventas_result.scalar_one()

    # Fondo con más ventas realizadas (por monto)
    fondo_top_query: Select[tuple] = (
        select(
            Fondo.id_fondo,
            Fondo.nombre,
            func.coalesce(func.sum(Venta.valor_total), 0).label("monto_total"),
        )
        .join(CupoGeneral, CupoGeneral.id_fondo == Fondo.id_fondo)
        .join(
            Asociado,
            Asociado.id_fondo == Fondo.id_fondo,
            isouter=True,
        )
        .join(
            Microcupo,
            Microcupo.id_asociado == Asociado.id_asociado,
            isouter=True,
        )
        .join(
            Venta,
            Venta.id_microcupo == Microcupo.id_microcupo,
            isouter=True,
        )
        .where(Fondo.estado.is_(True))
        .group_by(Fondo.id_fondo, Fondo.nombre)
        .order_by(func.coalesce(func.sum(Venta.valor_total), 0).desc())
        .limit(1)
    )
    fondo_top_result = await db.execute(fondo_top_query)
    fondo_top_row = fondo_top_result.first()

    if fondo_top_row is None:
        fondo_top_id = None
        fondo_top_nombre = None
        fondo_top_monto = None
    else:
        fondo_top_id = fondo_top_row[0]
        fondo_top_nombre = fondo_top_row[1]
        fondo_top_monto = fondo_top_row[2]

    return AdminDashboardStats(
        total_fondos_activos=total_fondos_activos,
        total_cupo_general=total_cupo_general,
        total_ventas=total_ventas,
        fondo_top_ventas_id=fondo_top_id,
        fondo_top_ventas_nombre=fondo_top_nombre,
        fondo_top_ventas_monto=fondo_top_monto,
    )


@router.get(
    "/fondo/estadisticas",
    response_model=FondoDashboardStats,
)
async def get_fondo_stats(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    GET /dashboard/fondo/stats - Dashboard financiero del fondo.
    ADMIN_FONDO, EJECUTIVO_COMERCIAL. No TIENDA_OPERADOR.
    """
    tenant_id = tenant_ids[0] if tenant_ids else None
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo usuarios de fondo pueden acceder a las estadísticas de fondo.",
        )

    # Obtener cupo general del fondo
    cupo_query: Select[tuple] = select(CupoGeneral).where(
        CupoGeneral.id_fondo == tenant_id
    )
    cupo_result = await db.execute(cupo_query)
    cupo = cupo_result.scalar_one_or_none()

    valor_total_fondo = cupo.valor_total if cupo is not None else 0

    if cupo is None or valor_total_fondo == 0:
        porcentaje_ejecucion = 0.0
        porcentaje_compromiso = 0.0
    else:
        # Monto ejecutado (ventas del fondo): Suma Venta.valor_total
        ejecutado_query: Select[tuple] = (
            select(func.coalesce(func.sum(Venta.valor_total), 0))
            .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
            .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
            .where(Asociado.id_fondo == tenant_id)
        )
        ejecutado_result = await db.execute(ejecutado_query)
        monto_ejecutado = ejecutado_result.scalar_one()

        # Monto reservado: Suma Microcupo.monto en estado APROBADO (reservado sin venta)
        reservado_query: Select[tuple] = (
            select(func.coalesce(func.sum(Microcupo.monto), 0))
            .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
            .where(
                Asociado.id_fondo == tenant_id,
                Microcupo.estado == MicrocupoEstado.APROBADO,
            )
        )
        reservado_result = await db.execute(reservado_query)
        monto_reservado = reservado_result.scalar_one()

        # Porcentaje Ejecución (Ventas Reales): dinero que ya se transformó en ventas
        porcentaje_ejecucion = float(monto_ejecutado / valor_total_fondo * 100)

        # Porcentaje Compromiso (Dinero Bloqueado): ventas + microcupos reservados
        monto_bloqueado = monto_ejecutado + monto_reservado
        porcentaje_compromiso = float(monto_bloqueado / valor_total_fondo * 100)

    # Microcupos vencidos y consumidos
    microcupos_estado_query: Select[tuple] = (
        select(
            Microcupo.estado,
            func.count(Microcupo.id_microcupo),
        )
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(Asociado.id_fondo == tenant_id)
        .group_by(Microcupo.estado)
    )
    microcupos_estado_result = await db.execute(microcupos_estado_query)

    microcupos_vencidos = 0
    microcupos_consumidos = 0
    for estado, cantidad in microcupos_estado_result.all():
        if estado == MicrocupoEstado.VENCIDO:
            microcupos_vencidos = cantidad
        elif estado == MicrocupoEstado.CONSUMIDO:
            microcupos_consumidos = cantidad

    # Ranking de los 5 productos más vendidos
    top_productos_query: Select[tuple] = (
        select(
            Venta.producto_detalle,
            func.count(Venta.id_venta).label("cantidad_ventas"),
            func.coalesce(func.sum(Venta.valor_total), 0).label("monto_total"),
        )
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(
            Asociado.id_fondo == tenant_id,
            Venta.producto_detalle.is_not(None),
        )
        .group_by(Venta.producto_detalle)
        .order_by(func.count(Venta.id_venta).desc())
        .limit(5)
    )
    top_productos_result = await db.execute(top_productos_query)
    top_productos_rows = top_productos_result.all()

    top_productos: list[ProductoMasVendido] = []
    for producto, cantidad_ventas, monto_total in top_productos_rows:
        top_productos.append(
            ProductoMasVendido(
                producto=producto,
                cantidad_ventas=cantidad_ventas,
                monto_total=monto_total,
            )
        )

    return FondoDashboardStats(
        id_fondo=tenant_id,
        porcentaje_ejecucion_cupo=porcentaje_ejecucion,
        porcentaje_compromiso_cupo=porcentaje_compromiso,
        microcupos_vencidos=microcupos_vencidos,
        microcupos_consumidos=microcupos_consumidos,
        top_productos=top_productos,
    )

