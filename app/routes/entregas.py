from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import registrar_auditoria
from app.core.dependencies import get_current_user, get_tenant_id, require_roles, ensure_fondo_user
from app.core import acciones
from app.core.roles import (
    ADMIN_FONDO,
    ADMIN_GLOBAL,
    EJECUTIVO_COMERCIAL,
    TIENDA_OPERADOR,
    _get_rol_name,
)
from app.database.config import get_db
from app.models.asociado import Asociado
from app.models.entrega import Entrega
from app.models.microcupo import Microcupo
from app.models.usuario import Usuario
from app.models.venta import Venta
from app.schemas.entrega import EntregaCreate, EntregaRead


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
        select(Entrega)
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
    return result.scalars().all()


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
        select(Entrega)
        .join(Venta, Entrega.id_venta == Venta.id_venta)
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .where(Entrega.id_entrega == id_entrega)
    )
    if tenant_id is not None:
        query = query.where(Asociado.id_fondo == tenant_id)

    result = await db.execute(query)
    entrega = result.scalar_one_or_none()
    if entrega is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entrega no encontrada.",
        )
    return entrega


@router.post(
    "/",
    response_model=EntregaRead,
    status_code=status.HTTP_201_CREATED,
)
async def crear_entrega(
    payload: EntregaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR)),
):
    """
    POST /entregas

    Registra la entrega de un producto vendido.

    - Solo puede existir una Entrega por cada venta (relación 1:1).
    - Para usuarios de fondo, valida que la venta pertenezca a su fondo.
    - TIENDA_OPERADOR puede crear entregas sin id_fondo; el id_fondo se obtiene
      desde la venta → microcupo → asociado.
    - Registra tipo y fecha de entrega.
    """
    rol = _get_rol_name(current_user)

    # Solo roles de fondo requieren id_fondo en el usuario.
    # ADMIN_GLOBAL y TIENDA_OPERADOR pueden operar sin id_fondo.
    if rol in (ADMIN_FONDO, EJECUTIVO_COMERCIAL):
        tenant_id = ensure_fondo_user(current_user)
    else:
        tenant_id = None

    # La sesión de get_db ya tiene una transacción (p. ej. por get_current_user).
    # No usar db.begin() para evitar InvalidRequestError ("A transaction is already begun").
    try:
        # Verificar que la venta exista. Para usuarios de fondo se filtra por su propio fondo.
        # ADMIN_GLOBAL y TIENDA_OPERADOR (sin id_fondo) pueden operar sobre cualquier fondo.
        venta_query: Select[tuple] = (
            select(Venta, Asociado.id_fondo)
            .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
            .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
            .where(Venta.id_venta == payload.id_venta)
        )
        if tenant_id is not None:
            venta_query = venta_query.where(Asociado.id_fondo == tenant_id)
        venta_result = await db.execute(venta_query)
        row = venta_result.one_or_none()

        if row is None:
            venta = None
            fondo_id = None
        else:
            venta, fondo_id = row

        if venta is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venta no encontrada para el fondo del usuario.",
            )

        # Verificar que no exista ya una entrega asociada (1:1)
        entrega_existente_query: Select[tuple] = select(Entrega).where(
            Entrega.id_venta == venta.id_venta
        )
        entrega_existente_result = await db.execute(entrega_existente_query)
        entrega_existente = entrega_existente_result.scalar_one_or_none()

        if entrega_existente is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe una entrega registrada para esta venta.",
            )

        entrega = Entrega(
            tipo_entrega=payload.tipo_entrega,
            fecha_entrega=datetime.now(timezone.utc),
            id_venta=venta.id_venta,
            id_fondo=fondo_id if fondo_id is not None else tenant_id,
        )
        db.add(entrega)

        await registrar_auditoria(db, current_user, acciones.CREAR_ENTREGA)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    await db.refresh(entrega)
    return entrega

