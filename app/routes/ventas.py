from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import registrar_auditoria
from app.core.dependencies import (
    get_current_user,
    get_tenant_id,
    get_tenant_ids,
    require_roles,
    ensure_fondo_user,
)
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
from app.models.microcupo import Microcupo, MicrocupoEstado
from app.models.usuario import Usuario
from app.models.venta import Venta
from app.schemas.venta import VentaCreate, VentaRead


router = APIRouter(prefix="/ventas", tags=["ventas"])


def _build_venta_read(venta: Venta, nombre_asociado: str | None, id_entrega: int | None) -> VentaRead:
    return VentaRead(
        id_venta=venta.id_venta,
        fecha=venta.fecha,
        valor_total=venta.valor_total,
        producto_detalle=venta.producto_detalle,
        id_microcupo=venta.id_microcupo,
        id_asociado=venta.id_asociado,
        id_fondo=venta.id_fondo,
        id_usuario_tienda=venta.id_usuario_tienda,
        nombre_asociado=nombre_asociado,
        id_entrega=id_entrega,
    )


@router.get("/", response_model=list[VentaRead])
async def list_ventas(
    fecha_desde: datetime | None = Query(default=None, description="Filtro fecha desde"),
    fecha_hasta: datetime | None = Query(default=None, description="Filtro fecha hasta"),
    id_asociado: int | None = Query(default=None, description="Filtro por asociado"),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    Lista de ventas con filtros opcionales.

    - Admin Global: ve todas las ventas. Si pasa id_asociado, filtra por ese asociado.
    - Usuario de fondo: solo ventas de microcupos de asociados de su fondo.
    """
    query: Select[tuple] = (
        select(Venta, Asociado.nombre, Entrega.id_entrega)
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .outerjoin(Entrega, Venta.id_venta == Entrega.id_venta)
    )
    if tenant_ids:
        query = query.where(Asociado.id_fondo.in_(tenant_ids))
    if id_asociado is not None:
        query = query.where(Asociado.id_asociado == id_asociado)
    if fecha_desde is not None:
        query = query.where(Venta.fecha >= fecha_desde)
    if fecha_hasta is not None:
        query = query.where(Venta.fecha <= fecha_hasta)

    query = query.order_by(Venta.fecha.desc())
    result = await db.execute(query)
    rows = result.all()

    return [
        _build_venta_read(venta, nombre_asociado, id_entrega)
        for venta, nombre_asociado, id_entrega in rows
    ]


@router.get("/{id_venta}", response_model=VentaRead)
async def get_venta(
    id_venta: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    Detalle de una venta individual. 404 si no existe o no pertenece al fondo del usuario.
    """
    query: Select[tuple] = (
        select(Venta, Asociado.nombre, Entrega.id_entrega)
        .join(Microcupo, Venta.id_microcupo == Microcupo.id_microcupo)
        .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
        .outerjoin(Entrega, Venta.id_venta == Entrega.id_venta)
        .where(Venta.id_venta == id_venta)
    )
    if tenant_ids:
        query = query.where(Asociado.id_fondo.in_(tenant_ids))

    result = await db.execute(query)
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta no encontrada.",
        )
    venta, nombre_asociado, id_entrega = row
    return _build_venta_read(venta, nombre_asociado, id_entrega)


@router.post(
    "/",
    response_model=VentaRead,
    status_code=status.HTTP_201_CREATED,
)
async def crear_venta(
    payload: VentaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR)),
):
    """
    POST /ventas

    Ejecuta la venta de un microcupo:

    - Valida que el microcupo exista y, para usuarios de fondo, pertenezca a su fondo.
    - Verifica que el microcupo esté en estado 'APROBADO'.
    - Cambia el estado del microcupo a 'CONSUMIDO'.
    - Crea el registro de Venta con valor_total igual al monto del microcupo.
    - El id_fondo de la venta se toma del asociado (microcupo.asociado.id_fondo),
      no del usuario (permite a TIENDA_OPERADOR operar sin id_fondo).
    - Registra en Auditoria la acción 'VENTA_REALIZADA'.
    - Todo dentro de una transacción atómica.
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
        # Buscar el microcupo. Para usuarios de fondo se filtra por su propio fondo.
        # ADMIN_GLOBAL y TIENDA_OPERADOR (sin id_fondo) pueden operar sobre cualquier fondo.
        microcupo_query: Select[tuple] = (
            select(Microcupo, Asociado)
            .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
            .where(Microcupo.id_microcupo == payload.id_microcupo)
        )
        if tenant_id is not None:
            microcupo_query = microcupo_query.where(Asociado.id_fondo == tenant_id)
        microcupo_result = await db.execute(microcupo_query)
        row = microcupo_result.one_or_none()

        if row is None:
            microcupo = None
            asociado = None
        else:
            microcupo, asociado = row

        if microcupo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Microcupo no encontrado para el fondo del usuario.",
            )

        if microcupo.estado != MicrocupoEstado.APROBADO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El microcupo no está aprobado para venta.",
            )

        # Cambiar estado del microcupo a CONSUMIDO
        microcupo.estado = MicrocupoEstado.CONSUMIDO

        # Crear la venta asociada
        venta = Venta(
            fecha=datetime.now(timezone.utc),
            valor_total=microcupo.monto,
            producto_detalle=payload.producto_detalle,
            id_microcupo=microcupo.id_microcupo,
            id_asociado=microcupo.id_asociado,
            id_fondo=asociado.id_fondo if asociado is not None else tenant_id,
            id_usuario_tienda=current_user.id_usuario,
        )
        db.add(venta)

        await registrar_auditoria(db, current_user, acciones.VENTA_REALIZADA)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    await db.refresh(venta)
    nombre_asociado_result = await db.execute(
        select(Asociado.nombre).where(Asociado.id_asociado == microcupo.id_asociado)
    )
    nombre_asociado = nombre_asociado_result.scalar_one_or_none()
    return _build_venta_read(venta, nombre_asociado, None)

