from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import registrar_auditoria
from app.core.dependencies import (
    get_current_user,
    get_tenant_id,
    get_tenant_ids,
    require_roles,
)
from app.core import acciones
from app.core.roles import ADMIN_FONDO, ADMIN_GLOBAL, EJECUTIVO_COMERCIAL
from app.database.config import get_db
from app.models.asociado import Asociado
from app.models.auditoria import Auditoria
from app.models.cupo_general import CupoGeneral
from app.models.fondo import Fondo
from app.models.usuario import Usuario
from app.models.venta import Venta
from app.models.microcupo import Microcupo, MicrocupoEstado
from app.schemas.cupo import CupoEstadoRead, CupoRecarga, FondoResumenFinanciero


router = APIRouter(prefix="/cupos", tags=["cupos"])


async def _get_cupo_general_for_fondo(
    db: AsyncSession,
    id_fondo: int,
) -> CupoGeneral:
    result = await db.execute(
        select(CupoGeneral).where(CupoGeneral.id_fondo == id_fondo)
    )
    cupo = result.scalar_one_or_none()
    if cupo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cupo general no encontrado para el fondo indicado.",
        )
    return cupo


async def _build_cupo_estado(
    db: AsyncSession,
    id_fondo: int,
    cupo: CupoGeneral,
) -> CupoEstadoRead:
    """
    Calcula los saldos reservados y ejecutados para un fondo y devuelve
    un esquema de estado consolidado.
    """

    # Suma de microcupos activos (APROBADO) del fondo
    reserved_query: Select[tuple] = (
        select(func.coalesce(func.sum(Microcupo.monto), 0))
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(
            Asociado.id_fondo == id_fondo,
            Microcupo.estado == MicrocupoEstado.APROBADO,
        )
    )
    reserved_result = await db.execute(reserved_query)
    saldo_reservado = reserved_result.scalar_one()

    # Suma de ventas asociadas a microcupos del fondo
    executed_query: Select[tuple] = (
        select(func.coalesce(func.sum(Venta.valor_total), 0))
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(Asociado.id_fondo == id_fondo)
    )
    executed_result = await db.execute(executed_query)
    saldo_ejecutado = executed_result.scalar_one()

    return CupoEstadoRead(
        id_fondo=id_fondo,
        valor_total=cupo.valor_total,
        valor_disponible=cupo.valor_disponible,
        saldo_reservado=saldo_reservado,
        saldo_ejecutado=saldo_ejecutado,
        fecha_creacion=cupo.fecha_creacion,
        fecha_actualizacion=cupo.fecha_actualizacion,
    )


async def _build_fondo_resumen_financiero(
    db: AsyncSession,
    fondo: Fondo,
    cupo: CupoGeneral | None,
) -> FondoResumenFinanciero:
    """Construye FondoResumenFinanciero para un fondo."""
    id_fondo = fondo.id_fondo
    valor_total = cupo.valor_total if cupo is not None else 0
    valor_disponible = cupo.valor_disponible if cupo is not None else 0

    reserved_query: Select[tuple] = (
        select(func.coalesce(func.sum(Microcupo.monto), 0))
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(
            Asociado.id_fondo == id_fondo,
            Microcupo.estado == MicrocupoEstado.APROBADO,
        )
    )
    reserved_result = await db.execute(reserved_query)
    saldo_reservado = reserved_result.scalar_one()

    executed_query: Select[tuple] = (
        select(func.coalesce(func.sum(Venta.valor_total), 0))
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(Asociado.id_fondo == id_fondo)
    )
    executed_result = await db.execute(executed_query)
    saldo_ejecutado = executed_result.scalar_one()

    count_asociados_result = await db.execute(
        select(func.count(Asociado.id_asociado)).where(
            Asociado.id_fondo == id_fondo,
            Asociado.activo.is_(True),
        )
    )
    total_asociados = count_asociados_result.scalar_one() or 0

    count_ventas_result = await db.execute(
        select(func.count(Venta.id_venta))
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(Asociado.id_fondo == id_fondo)
    )
    total_ventas = count_ventas_result.scalar_one() or 0

    if valor_total == 0:
        porcentaje_ejecucion = 0.0
        porcentaje_compromiso = 0.0
    else:
        porcentaje_ejecucion = float(saldo_ejecutado / valor_total * 100)
        porcentaje_compromiso = float((saldo_ejecutado + saldo_reservado) / valor_total * 100)

    return FondoResumenFinanciero(
        id_fondo=fondo.id_fondo,
        nombre_fondo=fondo.nombre,
        nit=fondo.nit,
        estado=fondo.estado,
        valor_total=valor_total,
        valor_disponible=valor_disponible,
        saldo_reservado=saldo_reservado,
        saldo_ejecutado=saldo_ejecutado,
        porcentaje_ejecucion=porcentaje_ejecucion,
        porcentaje_compromiso=porcentaje_compromiso,
        total_asociados=total_asociados,
        total_ventas=total_ventas,
        fecha_creacion_cupo=cupo.fecha_creacion if cupo is not None else None,
        fecha_actualizacion_cupo=cupo.fecha_actualizacion if cupo is not None else None,
    )


@router.get(
    "/fondos/resumen",
    response_model=list[FondoResumenFinanciero],
)
async def get_fondos_resumen(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    GET /cupos/fondos/resumen - Lista todos los fondos con estado financiero. Solo ADMIN_GLOBAL.
    """
    result = await db.execute(
        select(Fondo).where(Fondo.activo.is_(True)).order_by(Fondo.nombre.asc())
    )
    fondos = result.scalars().all()

    cupos_result = await db.execute(
        select(CupoGeneral).where(CupoGeneral.id_fondo.in_(f.id_fondo for f in fondos))
    )
    cupos_map = {c.id_fondo: c for c in cupos_result.scalars().all()}

    return [
        await _build_fondo_resumen_financiero(db, f, cupos_map.get(f.id_fondo))
        for f in fondos
    ]


@router.get(
    "/fondos/mi-fondo",
    response_model=CupoEstadoRead,
)
async def get_cupo_fondo_me(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    GET /cupos/fondos/mi-fondo - Estado financiero del cupo.
    ADMIN_FONDO, EJECUTIVO_COMERCIAL (requiere id_fondo). No TIENDA_OPERADOR.
    """
    tenant_id = tenant_ids[0] if tenant_ids else None
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requiere estar asociado a un fondo.",
        )

    cupo = await _get_cupo_general_for_fondo(db, tenant_id)
    return await _build_cupo_estado(db, tenant_id, cupo)


@router.get(
    "/fondos/{id_fondo}",
    response_model=FondoResumenFinanciero,
)
async def get_fondo_detalle(
    id_fondo: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
):
    """
    GET /cupos/fondos/{id_fondo} - Detalle financiero de un fondo.
    Admin Global: cualquier fondo. Usuario de fondo: solo su propio fondo.
    """
    tenant_id = get_tenant_id(current_user)
    if tenant_id is not None and tenant_id != id_fondo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a este fondo.",
        )

    result = await db.execute(select(Fondo).where(Fondo.id_fondo == id_fondo))
    fondo = result.scalar_one_or_none()
    if fondo is None or not fondo.activo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fondo no encontrado.",
        )

    cupo = await db.execute(select(CupoGeneral).where(CupoGeneral.id_fondo == id_fondo))
    cupo_obj = cupo.scalar_one_or_none()
    return await _build_fondo_resumen_financiero(db, fondo, cupo_obj)


@router.patch(
    "/fondos/{id_fondo}/recargar",
    response_model=CupoEstadoRead,
)
async def recargar_cupo_fondo(
    id_fondo: int,
    payload: CupoRecarga,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    PATCH /cupos/fondos/{id_fondo}/recargar
    Solo ADMIN_GLOBAL. Aumenta valor_total y valor_disponible del cupo.
    """

    cupo = await _get_cupo_general_for_fondo(db, id_fondo)

    cupo.valor_total += payload.valor_recarga
    cupo.valor_disponible += payload.valor_recarga

    await registrar_auditoria(db, current_user, acciones.RECARGAR_CUPO)
    await db.commit()
    await db.refresh(cupo)

    return await _build_cupo_estado(db, id_fondo, cupo)

