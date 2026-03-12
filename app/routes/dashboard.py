from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_user,
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
    ActividadRecienteResponse,
    AdminDashboardStats,
    FondoDashboardStats,
    MicrocupoRecienteItem,
    ProductoMasVendido,
    TopAsociadoItem,
    VentaRecienteItem,
)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/admin/estadisticas",
    response_model=AdminDashboardStats,
)
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
    fecha: date | None = Query(default=None, description="Fecha del día a consultar. Por defecto hoy."),
):
    """
    GET /dashboard/admin/estadisticas - Resumen global. Solo ADMIN_GLOBAL.
    Las métricas de ventas se filtran por el día indicado (por defecto hoy).
    """
    dia = fecha if fecha is not None else date.today()
    dia_inicio = datetime(dia.year, dia.month, dia.day, 0, 0, 0, tzinfo=timezone.utc)
    dia_fin = datetime(dia.year, dia.month, dia.day, 23, 59, 59, 999999, tzinfo=timezone.utc)

    fondos_activos_query: Select[tuple] = select(func.count(Fondo.id_fondo)).where(
        Fondo.estado.is_(True),
        Fondo.activo == True,
    )
    fondos_activos_result = await db.execute(fondos_activos_query)
    total_fondos_activos: int = fondos_activos_result.scalar_one()

    total_cupo_query: Select[tuple] = select(
        func.coalesce(func.sum(CupoGeneral.valor_total), 0)
    )
    total_cupo_result = await db.execute(total_cupo_query)
    total_cupo_general = total_cupo_result.scalar_one()

    total_ventas_query: Select[tuple] = select(
        func.coalesce(func.sum(Venta.valor_total), 0)
    ).where(
        Venta.fecha >= dia_inicio,
        Venta.fecha <= dia_fin,
    )
    total_ventas_result = await db.execute(total_ventas_query)
    total_ventas = total_ventas_result.scalar_one()

    fondo_top_query: Select[tuple] = (
        select(
            Fondo.id_fondo,
            Fondo.nombre,
            func.coalesce(func.sum(Venta.valor_total), 0).label("monto_total"),
        )
        .join(CupoGeneral, CupoGeneral.id_fondo == Fondo.id_fondo)
        .join(Asociado, Asociado.id_fondo == Fondo.id_fondo, isouter=True)
        .join(Microcupo, Microcupo.id_asociado == Asociado.id_asociado, isouter=True)
        .join(Venta, Venta.id_microcupo == Microcupo.id_microcupo, isouter=True)
        .where(
            Fondo.estado.is_(True),
            Venta.fecha >= dia_inicio,
            Venta.fecha <= dia_fin,
        )
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
    GET /dashboard/fondo/estadisticas
    ADMIN_FONDO: datos de su único fondo.
    EJECUTIVO_COMERCIAL: datos consolidados de todos sus fondos.
    """
    if not tenant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo usuarios de fondo pueden acceder a las estadísticas de fondo.",
        )

    # Para el response: None si son múltiples fondos, id si es uno solo
    id_fondo_response = tenant_ids[0] if len(tenant_ids) == 1 else None

    # Cupo total consolidado de todos los fondos del usuario
    cupo_query: Select[tuple] = select(
        func.coalesce(func.sum(CupoGeneral.valor_total), 0)
    ).where(CupoGeneral.id_fondo.in_(tenant_ids))
    cupo_result = await db.execute(cupo_query)
    valor_total_consolidado = float(cupo_result.scalar_one())

    # Valor disponible consolidado
    disponible_query: Select[tuple] = select(
        func.coalesce(func.sum(CupoGeneral.valor_disponible), 0)
    ).where(CupoGeneral.id_fondo.in_(tenant_ids))
    disponible_result = await db.execute(disponible_query)
    valor_disponible_consolidado = float(disponible_result.scalar_one())

    if valor_total_consolidado == 0:
        porcentaje_ejecucion = 0.0
        porcentaje_compromiso = 0.0
    else:
        # Monto ejecutado consolidado
        ejecutado_query: Select[tuple] = (
            select(func.coalesce(func.sum(Venta.valor_total), 0))
            .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
            .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
            .where(Asociado.id_fondo.in_(tenant_ids))
        )
        ejecutado_result = await db.execute(ejecutado_query)
        monto_ejecutado = float(ejecutado_result.scalar_one())

        # Monto reservado consolidado (microcupos APROBADO)
        reservado_query: Select[tuple] = (
            select(func.coalesce(func.sum(Microcupo.monto), 0))
            .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
            .where(
                Asociado.id_fondo.in_(tenant_ids),
                Microcupo.estado == MicrocupoEstado.APROBADO,
            )
        )
        reservado_result = await db.execute(reservado_query)
        monto_reservado = float(reservado_result.scalar_one())

        # % ejecución en tiempo real: dinero que ya no está disponible
        dinero_no_disponible = valor_total_consolidado - valor_disponible_consolidado
        porcentaje_ejecucion = dinero_no_disponible / valor_total_consolidado * 100

        # % compromiso: ejecutado + reservado
        porcentaje_compromiso = (monto_ejecutado + monto_reservado) / valor_total_consolidado * 100

    # Microcupos vencidos y consumidos consolidados
    microcupos_estado_query: Select[tuple] = (
        select(Microcupo.estado, func.count(Microcupo.id_microcupo))
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(Asociado.id_fondo.in_(tenant_ids))
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

    # Top 5 productos consolidados
    top_productos_query: Select[tuple] = (
        select(
            Venta.producto_detalle,
            func.count(Venta.id_venta).label("cantidad_ventas"),
            func.coalesce(func.sum(Venta.valor_total), 0).label("monto_total"),
        )
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(
            Asociado.id_fondo.in_(tenant_ids),
            Venta.producto_detalle.is_not(None),
        )
        .group_by(Venta.producto_detalle)
        .order_by(func.count(Venta.id_venta).desc())
        .limit(5)
    )
    top_productos_result = await db.execute(top_productos_query)

    top_productos: list[ProductoMasVendido] = [
        ProductoMasVendido(
            producto=row[0],
            cantidad_ventas=row[1],
            monto_total=row[2],
        )
        for row in top_productos_result.all()
    ]

    return FondoDashboardStats(
        id_fondo=id_fondo_response,
        porcentaje_ejecucion_cupo=porcentaje_ejecucion,
        porcentaje_compromiso_cupo=porcentaje_compromiso,
        microcupos_vencidos=microcupos_vencidos,
        microcupos_consumidos=microcupos_consumidos,
        top_productos=top_productos,
    )


@router.get(
    "/fondo/actividad-reciente",
    response_model=ActividadRecienteResponse,
)
async def get_fondo_actividad_reciente(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    GET /dashboard/fondo/actividad-reciente
    Últimas ventas y microcupos — consolidado para todos los fondos del usuario.
    """
    if not tenant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo usuarios de fondo pueden acceder a la actividad reciente.",
        )

    ultimas_ventas_query: Select[tuple] = (
        select(
            Venta.id_venta,
            Venta.valor_total,
            Venta.fecha,
            Venta.producto_detalle,
            Asociado.nombre.label("nombre_asociado"),
        )
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(Asociado.id_fondo.in_(tenant_ids))
        .order_by(Venta.fecha.desc())
        .limit(5)
    )
    ultimas_ventas_result = await db.execute(ultimas_ventas_query)

    ultimas_ventas = [
        VentaRecienteItem(
            id_venta=row[0],
            valor_total=float(row[1]) if row[1] is not None else 0.0,
            fecha=row[2],
            producto_detalle=row[3],
            nombre_asociado=row[4],
        )
        for row in ultimas_ventas_result.all()
    ]

    ultimos_microcupos_query: Select[tuple] = (
        select(
            Microcupo.id_microcupo,
            Microcupo.monto,
            Microcupo.estado,
            Microcupo.fecha_creacion,
            Asociado.nombre.label("nombre_asociado"),
        )
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(Asociado.id_fondo.in_(tenant_ids))
        .order_by(Microcupo.fecha_creacion.desc())
        .limit(5)
    )
    ultimos_microcupos_result = await db.execute(ultimos_microcupos_query)

    ultimos_microcupos = [
        MicrocupoRecienteItem(
            id_microcupo=row[0],
            monto=float(row[1]) if row[1] is not None else 0.0,
            estado=row[2].value if row[2] is not None else "",
            fecha_creacion=row[3],
            nombre_asociado=row[4],
        )
        for row in ultimos_microcupos_result.all()
    ]

    return ActividadRecienteResponse(
        ultimas_ventas=ultimas_ventas,
        ultimos_microcupos=ultimos_microcupos,
    )


@router.get(
    "/fondo/top-asociados",
    response_model=list[TopAsociadoItem],
)
async def get_fondo_top_asociados(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    GET /dashboard/fondo/top-asociados
    Top 5 asociados por monto — consolidado para todos los fondos del usuario.
    """
    if not tenant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo usuarios de fondo pueden acceder al ranking de asociados.",
        )

    top_asociados_query: Select[tuple] = (
        select(
            Asociado.nombre.label("nombre_asociado"),
            func.count(Venta.id_venta).label("cantidad_ventas"),
            func.coalesce(func.sum(Venta.valor_total), 0).label("monto_total"),
        )
        .join(Microcupo, Microcupo.id_asociado == Asociado.id_asociado)
        .join(Venta, Venta.id_microcupo == Microcupo.id_microcupo)
        .where(Asociado.id_fondo.in_(tenant_ids))
        .group_by(Asociado.id_asociado, Asociado.nombre)
        .order_by(func.coalesce(func.sum(Venta.valor_total), 0).desc())
        .limit(5)
    )
    top_asociados_result = await db.execute(top_asociados_query)

    return [
        TopAsociadoItem(
            nombre_asociado=row[0],
            cantidad_ventas=row[1],
            monto_total=float(row[2]) if row[2] is not None else 0.0,
        )
        for row in top_asociados_result.all()
    ]