from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_tenant_id, require_roles
from app.core.roles import ADMIN_FONDO, ADMIN_GLOBAL, EJECUTIVO_COMERCIAL
from app.database.config import get_db
from app.models.auditoria import Auditoria
from app.models.usuario import Usuario
from app.models.fondo import Fondo
from app.schemas.auditoria import AuditoriaLogRead


router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get(
    "/registros",
    response_model=list[AuditoriaLogRead],
)
async def get_auditoria_logs(
    accion: str | None = Query(
        default=None,
        description="Filtra por tipo de acción de auditoría.",
    ),
    fecha_desde: datetime | None = Query(
        default=None,
        description="Fecha desde (inclusive) para filtrar los logs.",
    ),
    fecha_hasta: datetime | None = Query(
        default=None,
        description="Fecha hasta (inclusive) para filtrar los logs.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
):
    """
    GET /auditoria/logs

    - Admin Global: ve todos los registros del sistema.
    - Usuario de fondo: ve solo registros de usuarios de su fondo.
    """

    tenant_id = get_tenant_id(current_user)

    query: Select[tuple] = (
        select(
            Auditoria.id_auditoria,
            Auditoria.fecha,
            Auditoria.accion,
            Usuario.id_usuario,
            Usuario.nombre,
            Fondo.id_fondo,
            Fondo.nombre,
        )
        .join(Usuario, Auditoria.id_usuario == Usuario.id_usuario)
        .join(Fondo, Usuario.id_fondo == Fondo.id_fondo, isouter=True)
    )

    conditions = []

    # Filtro por multi-tenancy
    if tenant_id is not None:
        conditions.append(Fondo.id_fondo == tenant_id)

    # Filtro por acción
    if accion is not None:
        conditions.append(Auditoria.accion == accion)

    # Filtros por fecha
    if fecha_desde is not None:
        conditions.append(Auditoria.fecha >= fecha_desde)
    if fecha_hasta is not None:
        fecha_hasta_fin = fecha_hasta.replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
        conditions.append(Auditoria.fecha <= fecha_hasta_fin)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Auditoria.fecha.desc())

    result = await db.execute(query)
    rows = result.all()

    logs: list[AuditoriaLogRead] = []
    for (
        id_auditoria,
        fecha,
        accion_value,
        id_usuario,
        nombre_usuario,
        id_fondo,
        nombre_fondo,
    ) in rows:
        logs.append(
            AuditoriaLogRead(
                id_auditoria=id_auditoria,
                fecha=fecha,
                accion=accion_value,
                id_usuario=id_usuario,
                nombre_usuario=nombre_usuario,
                id_fondo=id_fondo,
                nombre_fondo=nombre_fondo,
            )
        )

    return logs

