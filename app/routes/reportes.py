from datetime import date
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import registrar_auditoria
from app.core.dependencies import (
    get_current_user,
    get_tenant_id,
    get_tenant_ids,
    require_roles,
)
from app.core.roles import ADMIN_FONDO, ADMIN_GLOBAL, EJECUTIVO_COMERCIAL, _get_rol_name
from app.database.config import get_db
from app.models.asociado import Asociado
from app.models.cupo_general import CupoGeneral
from app.models.fondo import Fondo
from app.models.microcupo import Microcupo, MicrocupoEstado
from app.models.usuario import Usuario
from app.models.venta import Venta
from app.routes.cupos import _build_fondo_resumen_financiero
from app.schemas.cupo import FondoResumenFinanciero
from app.schemas.reporte import FondoResumenRead


router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get(
    "/fondo/resumen",
    response_model=FondoResumenRead,
)
async def get_fondo_resumen(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    GET /reportes/fondo/resumen

    Para usuarios de fondo. Muestra:

    - Número total de ventas ejecutadas.
    - Monto total ejecutado (ventas).
    - Monto reservado (microcupos en estado DISPONIBLE).
    """
    tenant_id = tenant_ids[0] if tenant_ids else None
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo usuarios de fondo pueden consultar el resumen de su fondo.",
        )

    # Contar ventas del fondo
    ventas_count_query: Select[tuple] = (
        select(func.count(Venta.id_venta))
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(Asociado.id_fondo == tenant_id)
    )
    ventas_count_result = await db.execute(ventas_count_query)
    total_ventas: int = ventas_count_result.scalar_one()

    # Monto ejecutado (ventas)
    ejecutado_query: Select[tuple] = (
        select(func.coalesce(func.sum(Venta.valor_total), 0))
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(Asociado.id_fondo == tenant_id)
    )
    ejecutado_result = await db.execute(ejecutado_query)
    monto_ejecutado = ejecutado_result.scalar_one()

    # Monto reservado (microcupos disponibles)
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

    return FondoResumenRead(
        id_fondo=tenant_id,
        total_ventas=total_ventas,
        monto_ejecutado=monto_ejecutado,
        monto_reservado=monto_reservado,
    )


@router.get(
    "/fondo/exportar",
    response_class=StreamingResponse,
)
async def exportar_fondo_resumen_excel(
    id_fondo: int | None = Query(
        default=None,
        description="Identificador del fondo a exportar. Solo aplica para ADMIN_GLOBAL.",
    ),
    fecha_inicio: date | None = Query(
        default=None,
        description="Fecha inicio del período a exportar (inclusive).",
    ),
    fecha_fin: date | None = Query(
        default=None,
        description="Fecha fin del período a exportar (inclusive).",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(
        require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL)
    ),
):
    """
    GET /reportes/fondo/exportar

    Exporta a Excel el resumen financiero por fondo.

    - Usuario de fondo (ADMIN_FONDO, EJECUTIVO_COMERCIAL): siempre exporta solo su fondo.
    - ADMIN_GLOBAL: puede pasar id_fondo para un fondo específico o dejarlo vacío para exportar todos.
    """
    tenant_id = get_tenant_id(current_user)

    fondos_resumen: list[FondoResumenFinanciero] = []
    auditoria_id_fondo: str

    # Usuario de fondo: siempre restringido a su fondo
    rol = _get_rol_name(current_user)
    if tenant_id is not None and rol in (ADMIN_FONDO, EJECUTIVO_COMERCIAL):
        if id_fondo is not None and id_fondo != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a este fondo.",
            )

        result = await db.execute(select(Fondo).where(Fondo.id_fondo == tenant_id))
        fondo = result.scalar_one_or_none()
        if fondo is None or not fondo.activo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fondo no encontrado.",
            )

        cupo_result = await db.execute(
            select(CupoGeneral).where(CupoGeneral.id_fondo == tenant_id)
        )
        cupo = cupo_result.scalar_one_or_none()

        resumen = await _build_fondo_resumen_financiero(db, fondo, cupo)
        fondos_resumen = [resumen]
        auditoria_id_fondo = str(tenant_id)

    else:
        # ADMIN_GLOBAL
        if id_fondo is not None:
            result = await db.execute(select(Fondo).where(Fondo.id_fondo == id_fondo))
            fondo = result.scalar_one_or_none()
            if fondo is None or not fondo.activo:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Fondo no encontrado.",
                )

            cupo_result = await db.execute(
                select(CupoGeneral).where(CupoGeneral.id_fondo == id_fondo)
            )
            cupo = cupo_result.scalar_one_or_none()

            resumen = await _build_fondo_resumen_financiero(db, fondo, cupo)
            fondos_resumen = [resumen]
            auditoria_id_fondo = str(id_fondo)
        else:
            result = await db.execute(
                select(Fondo)
                .where(Fondo.activo.is_(True))
                .order_by(Fondo.nombre.asc())
            )
            fondos = result.scalars().all()

            if fondos:
                cupos_result = await db.execute(
                    select(CupoGeneral).where(
                        CupoGeneral.id_fondo.in_(f.id_fondo for f in fondos)
                    )
                )
                cupos_map = {
                    c.id_fondo: c for c in cupos_result.scalars().all()
                }
                fondos_resumen = [
                    await _build_fondo_resumen_financiero(
                        db,
                        fondo,
                        cupos_map.get(fondo.id_fondo),
                    )
                    for fondo in fondos
                ]
            else:
                fondos_resumen = []

            auditoria_id_fondo = "todos"

    # Filtrar ventas por período si se especificó
    from datetime import datetime, timezone
    ventas_por_fondo: dict[int, dict] = {}
    if fecha_inicio or fecha_fin:
        fi = datetime(fecha_inicio.year, fecha_inicio.month, fecha_inicio.day, 0, 0, 0, tzinfo=timezone.utc) if fecha_inicio else None
        ff = datetime(fecha_fin.year, fecha_fin.month, fecha_fin.day, 23, 59, 59, 999999, tzinfo=timezone.utc) if fecha_fin else None

        for resumen in fondos_resumen:
            q = (
                select(
                    func.count(Venta.id_venta),
                    func.coalesce(func.sum(Venta.valor_total), 0),
                )
                .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
                .where(Microcupo.id_fondo == resumen.id_fondo)
            )
            if fi:
                q = q.where(Venta.fecha >= fi)
            if ff:
                q = q.where(Venta.fecha <= ff)
            r = await db.execute(q)
            count, monto = r.one()
            ventas_por_fondo[resumen.id_fondo] = {
                "total_ventas": int(count),
                "saldo_ejecutado": float(monto),
            }

    # Generar archivo Excel en memoria
    wb = Workbook()
    ws = wb.active
    ws.title = "Fondos"

    periodo = ""
    if fecha_inicio or fecha_fin:
        desde = fecha_inicio.strftime("%d/%m/%Y") if fecha_inicio else "inicio"
        hasta = fecha_fin.strftime("%d/%m/%Y") if fecha_fin else "hoy"
        periodo = f" ({desde} - {hasta})"

    headers = [
        "Nombre del Fondo",
        "NIT",
        "Cupo Total",
        f"Ventas ejecutadas{periodo}",
        "Saldo Reservado",
        "Saldo Disponible",
        f"Total transacciones{periodo}",
        "Porcentaje de Ejecución",
        "Porcentaje de Compromiso",
    ]
    ws.append(headers)

    for resumen in fondos_resumen:
        filtrado = ventas_por_fondo.get(resumen.id_fondo)
        ws.append(
            [
                resumen.nombre_fondo,
                resumen.nit,
                float(resumen.valor_total),
                filtrado["saldo_ejecutado"] if filtrado else float(resumen.saldo_ejecutado),
                float(resumen.saldo_reservado),
                float(resumen.valor_disponible),
                filtrado["total_ventas"] if filtrado else resumen.total_ventas,
                resumen.porcentaje_ejecucion,
                resumen.porcentaje_compromiso,
            ]
        )

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    # Registrar auditoría
    await registrar_auditoria(
        db,
        current_user,
        f"REPORTE_EXPORTADO;id_fondo={auditoria_id_fondo}",
    )

    return StreamingResponse(
        stream,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": 'attachment; filename="reporte_fondos.xlsx"'
        },
    )

