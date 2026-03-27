from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_tenant_id, require_roles
from app.core.roles import (
    ADMIN_FONDO,
    ADMIN_GLOBAL,
    EJECUTIVO_COMERCIAL,
    TIENDA_OPERADOR,
)
from app.database.config import get_db
from app.models.asociado import Asociado
from app.models.entrega import Entrega
from app.models.microcupo import Microcupo
from app.models.usuario import Usuario
from app.models.venta import Venta
from app.schemas.entrega import EntregaRead

router = APIRouter(prefix="/entregas", tags=["entregas"])


@router.get("/", response_model=list[EntregaRead])
async def list_entregas(
    fecha_desde: datetime | None = Query(default=None, description="Filtro fecha desde"),
    fecha_hasta: datetime | None = Query(default=None, description="Filtro fecha hasta"),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR)),
):
    """
    Lista de entregas. Multi-tenancy vía Entrega → Venta → Microcupo → Asociado.
    Usuario de fondo solo ve entregas de su fondo.
    """
    tenant_id = get_tenant_id(current_user)

    query: Select[tuple] = (
        select(Entrega, Asociado.nombre)
        .join(Venta, Entrega.id_venta == Venta.id_venta)
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
    )
    if tenant_id is not None:
        query = query.where(Asociado.id_fondo == tenant_id)
    if fecha_desde is not None:
        query = query.where(Entrega.fecha_entrega >= fecha_desde)
    if fecha_hasta is not None:
        fecha_hasta_fin = fecha_hasta.replace(
            hour=23, minute=59, second=59, microsecond=999999
        )
        query = query.where(Entrega.fecha_entrega <= fecha_hasta_fin)

    query = query.order_by(Entrega.fecha_entrega.desc())
    result = await db.execute(query)
    rows = result.all()
    return [
        EntregaRead(
            id_entrega=e.id_entrega,
            tipo_entrega=e.tipo_entrega,
            fecha_entrega=e.fecha_entrega,
            id_venta=e.id_venta,
            id_fondo=e.id_fondo,
            nombre_asociado=nombre,
        )
        for e, nombre in rows
    ]


@router.get("/{id_entrega}", response_model=EntregaRead)
async def get_entrega(
    id_entrega: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR)),
):
    """
    Detalle de una entrega. 404 si no existe o no pertenece al fondo del usuario.
    """
    tenant_id = get_tenant_id(current_user)

    query: Select[tuple] = (
        select(Entrega, Asociado.nombre)
        .join(Venta, Entrega.id_venta == Venta.id_venta)
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(Entrega.id_entrega == id_entrega)
    )
    if tenant_id is not None:
        query = query.where(Asociado.id_fondo == tenant_id)

    result = await db.execute(query)
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entrega no encontrada.",
        )
    entrega, nombre = row
    return EntregaRead(
        id_entrega=entrega.id_entrega,
        tipo_entrega=entrega.tipo_entrega,
        fecha_entrega=entrega.fecha_entrega,
        id_venta=entrega.id_venta,
        id_fondo=entrega.id_fondo,
        nombre_asociado=nombre,
    )
