from datetime import datetime, timedelta, timezone

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
from app.models.auditoria import Auditoria
from app.models.cupo_general import CupoGeneral
from app.models.microcupo import Microcupo, MicrocupoEstado
from app.models.usuario import Usuario
from app.schemas.microcupo import MicrocupoCreate, MicrocupoRead, MicrocupoUpdate


router = APIRouter(prefix="/microcupos", tags=["microcupos"])


@router.post(
    "/",
    response_model=MicrocupoRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_microcupo(
    payload: MicrocupoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
):
    """
    POST /microcupos

    Solo usuario de fondo.

    Lógica:
    - Verifica que el asociado pertenezca al mismo fondo (multi-tenancy).
    - Verifica que el CupoGeneral.valor_disponible sea >= monto.
    - Crea el Microcupo en estado 'APROBADO' y descuenta cupo de inmediato.
    - Todo dentro de una transacción atómica.
    """
    tenant_id = ensure_fondo_user(current_user)

    # La sesión de get_db ya tiene una transacción (p. ej. por get_current_user).
    # No usar db.begin() para evitar InvalidRequestError ("A transaction is already begun").
    try:
        # Validar que el asociado exista y pertenezca al fondo del usuario
        asociado_query: Select[tuple] = select(Asociado).where(
            Asociado.id_asociado == payload.id_asociado,
            Asociado.id_fondo == tenant_id,
        )
        asociado_result = await db.execute(asociado_query)
        asociado = asociado_result.scalar_one_or_none()
        if asociado is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asociado no encontrado para el fondo del usuario.",
            )

        cupo_query: Select[tuple] = select(CupoGeneral).where(
            CupoGeneral.id_fondo == asociado.id_fondo
        )
        cupo_result = await db.execute(cupo_query)
        cupo = cupo_result.scalar_one_or_none()
        if cupo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El fondo no tiene un cupo general configurado.",
            )

        if cupo.valor_disponible < payload.monto:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Saldo insuficiente en el fondo para crear este microcupo.",
            )

        cupo.valor_disponible -= payload.monto

        # Crear el microcupo asociado
        microcupo = Microcupo(
            monto=payload.monto,
            estado=MicrocupoEstado.APROBADO,
            fecha_vencimiento=payload.fecha_vencimiento
            if payload.fecha_vencimiento is not None
            else datetime.now(timezone.utc) + timedelta(days=15),
            producto_referencia=payload.producto_referencia,
            modalidad_entrega=payload.modalidad_entrega,
            direccion_entrega=payload.direccion_entrega,
            ciudad_entrega=payload.ciudad_entrega,
            telefono_contacto=payload.telefono_contacto,
            notas_entrega=payload.notas_entrega,
            id_asociado=asociado.id_asociado,
            id_fondo=asociado.id_fondo,
        )
        db.add(microcupo)

        await registrar_auditoria(db, current_user, acciones.CREAR_MICROCUPO)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    await db.refresh(microcupo)
    return microcupo


@router.get(
    "/",
    response_model=list[MicrocupoRead],
)
async def list_microcupos(
    id_fondo: int | None = Query(
        default=None,
        description=(
            "Filtra por fondo. "
            "Para Admin Global: opcional. "
            "Para usuarios de fondo: se ignora y se usa su propio fondo."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(
        require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR)
    ),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    GET /microcupos

    - Usuario de fondo (ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR con id_fondo):
      ve solo microcupos de su propio fondo.
    - TIENDA_OPERADOR sin id_fondo: ve todos los microcupos en estado APROBADO
      de todos los fondos (para operar en punto de venta).
    - Admin Global: ve todos los microcupos, o puede filtrar por id_fondo.
    """
    rol = _get_rol_name(current_user)

    query: Select[tuple] = select(Microcupo).join(
        Asociado, Microcupo.id_asociado == Asociado.id_asociado
    )

    if rol == TIENDA_OPERADOR:
        query = query.where(Microcupo.estado == MicrocupoEstado.APROBADO)
        if tenant_ids:
            query = query.where(Asociado.id_fondo.in_(tenant_ids))
    else:
        if tenant_ids:
            query = query.where(Asociado.id_fondo.in_(tenant_ids))
        elif id_fondo is not None:
            # Admin Global con filtro explícito (comportamiento previo intacto)
            query = query.where(Asociado.id_fondo == id_fondo)

    result = await db.execute(query)
    microcupos = result.scalars().all()
    return microcupos


@router.get("/{id_microcupo}", response_model=MicrocupoRead)
async def get_microcupo(
    id_microcupo: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    Detalle de un microcupo. 404 si no existe o no pertenece al fondo del usuario.
    """
    query: Select[tuple] = select(Microcupo).join(
        Asociado, Microcupo.id_asociado == Asociado.id_asociado
    ).where(Microcupo.id_microcupo == id_microcupo)
    if tenant_ids:
        query = query.where(Asociado.id_fondo.in_(tenant_ids))

    result = await db.execute(query)
    microcupo = result.scalar_one_or_none()
    if microcupo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Microcupo no encontrado.",
        )
    return microcupo


@router.patch(
    "/{id_microcupo}/cancelar",
    response_model=MicrocupoRead,
)
async def cancelar_microcupo(
    id_microcupo: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
):
    """
    PATCH /microcupos/{id_microcupo}/cancelar

    - ADMIN_FONDO y EJECUTIVO_COMERCIAL.
    - Solo se pueden cancelar microcupos en estado APROBADO.
    - Devuelve el saldo al cupo general y cambia el estado del microcupo a DENEGADO.
    - Registra auditoría MICROCUPO_DENEGADO.
    """
    try:
        query: Select[tuple] = (
            select(Microcupo, Asociado.id_fondo)
            .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
            .where(Microcupo.id_microcupo == id_microcupo)
        )
        result = await db.execute(query)
        row = result.one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Microcupo no encontrado.",
            )

        microcupo, id_fondo = row

        if microcupo.estado != MicrocupoEstado.APROBADO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden cancelar microcupos en estado APROBADO.",
            )

        cupo_query: Select[tuple] = select(CupoGeneral).where(
            CupoGeneral.id_fondo == id_fondo,
        )
        cupo_result = await db.execute(cupo_query)
        cupo = cupo_result.scalar_one_or_none()
        if cupo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El fondo no tiene un cupo general configurado.",
            )

        cupo.valor_disponible += microcupo.monto
        microcupo.estado = MicrocupoEstado.DENEGADO
        microcupo.id_fondo = id_fondo

        await registrar_auditoria(db, current_user, acciones.MICROCUPO_DENEGADO)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    await db.refresh(microcupo)
    return microcupo


@router.patch(
    "/{id_microcupo}/denegar",
    response_model=MicrocupoRead,
)
async def denegar_microcupo(
    id_microcupo: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    PATCH /microcupos/{id_microcupo}/denegar

    - Solo ADMIN_GLOBAL.
    - Solo se pueden denegar microcupos en estado APROBADO.
    - Devuelve saldo al cupo general.
    - Registra auditoría MICROCUPO_DENEGADO.
    """
    try:
        query: Select[tuple] = (
            select(Microcupo, Asociado.id_fondo)
            .join(Asociado, Microcupo.id_asociado == Asociado.id_asociado)
            .where(Microcupo.id_microcupo == id_microcupo)
        )
        result = await db.execute(query)
        row = result.one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Microcupo no encontrado.",
            )
        microcupo, id_fondo = row

        if microcupo.estado != MicrocupoEstado.APROBADO:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden denegar microcupos en estado APROBADO.",
            )

        cupo_query: Select[tuple] = select(CupoGeneral).where(CupoGeneral.id_fondo == id_fondo)
        cupo_result = await db.execute(cupo_query)
        cupo = cupo_result.scalar_one_or_none()
        if cupo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El fondo no tiene un cupo general configurado.",
            )

        cupo.valor_disponible += microcupo.monto
        microcupo.estado = MicrocupoEstado.DENEGADO

        await registrar_auditoria(db, current_user, acciones.MICROCUPO_DENEGADO)
        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise

    await db.refresh(microcupo)
    return microcupo


@router.patch("/{id_microcupo}", response_model=MicrocupoRead)
async def update_microcupo(
    id_microcupo: int,
    payload: MicrocupoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    Actualización parcial de un microcupo (fecha_vencimiento, producto_referencia, estado).
    No se puede cambiar monto ni id_asociado.
    Solo se protege la transición a CONSUMIDO.
    """
    query: Select[tuple] = select(Microcupo).join(
        Asociado, Microcupo.id_asociado == Asociado.id_asociado
    ).where(Microcupo.id_microcupo == id_microcupo)
    if tenant_ids:
        query = query.where(Asociado.id_fondo.in_(tenant_ids))

    result = await db.execute(query)
    microcupo = result.scalar_one_or_none()
    if microcupo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Microcupo no encontrado.",
        )

    update_data = payload.model_dump(exclude_unset=True)

    if "estado" in update_data:
        nuevo_estado = update_data["estado"]
        if nuevo_estado == MicrocupoEstado.CONSUMIDO:
            if microcupo.estado != MicrocupoEstado.APROBADO:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Solo se puede marcar como CONSUMIDO un microcupo en estado APROBADO.",
                )
    for field, value in update_data.items():
        setattr(microcupo, field, value)

    nuevo_estado = microcupo.estado
    await registrar_auditoria(
        db,
        current_user,
        f"MICROCUPO_ACTUALIZADO;id={id_microcupo};estado={nuevo_estado.value}",
    )
    await db.commit()
    await db.refresh(microcupo)
    return microcupo

