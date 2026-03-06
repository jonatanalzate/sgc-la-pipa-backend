from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import registrar_auditoria
from app.core.dependencies import get_tenant_id, require_roles
from app.core.roles import ADMIN_FONDO, ADMIN_GLOBAL, _get_rol_name
from app.core import acciones
from app.database.config import get_db
from app.models.cartera import MovimientoCartera, TipoMovimiento
from app.models.cupo_general import CupoGeneral
from app.models.fondo import Fondo
from app.models.usuario import Usuario
from app.schemas.cartera import MovimientoCreate, MovimientoRead


router = APIRouter(prefix="/cartera", tags=["cartera"])


async def _ensure_fondo_access(
    db: AsyncSession,
    current_user: Usuario,
    id_fondo: int,
) -> Fondo:
    """
    Valida que el fondo exista y que el usuario tenga acceso a él.

    - ADMIN_GLOBAL: puede operar sobre cualquier fondo.
    - ADMIN_FONDO: solo sobre su propio fondo.
    """
    result = await db.execute(select(Fondo).where(Fondo.id_fondo == id_fondo))
    fondo = result.scalar_one_or_none()
    if fondo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fondo no encontrado",
        )

    rol = _get_rol_name(current_user)
    tenant_id = get_tenant_id(current_user)

    if rol == ADMIN_GLOBAL:
        return fondo

    if tenant_id is None or tenant_id != id_fondo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a este fondo.",
        )

    return fondo


async def _get_cupo_general(
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


@router.post(
    "/{id_fondo}/recargar",
    response_model=MovimientoRead,
    status_code=status.HTTP_201_CREATED,
)
async def recargar_fondo(
    id_fondo: int,
    payload: MovimientoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO)),
):
    await _ensure_fondo_access(db, current_user, id_fondo)
    cupo = await _get_cupo_general(db, id_fondo)

    cupo.valor_total += Decimal(str(payload.monto))
    cupo.valor_disponible += Decimal(str(payload.monto))

    movimiento = MovimientoCartera(
        id_fondo=id_fondo,
        tipo=TipoMovimiento.RECARGA,
        monto=payload.monto,
        descripcion=payload.descripcion,
    )
    db.add(movimiento)
    await registrar_auditoria(
        db,
        current_user,
        f"CARTERA_RECARGA;id_fondo={id_fondo};monto={payload.monto}",
    )
    await db.commit()
    await db.refresh(movimiento)

    return movimiento


@router.post(
    "/{id_fondo}/abonar",
    response_model=MovimientoRead,
    status_code=status.HTTP_201_CREATED,
)
async def abonar_fondo(
    id_fondo: int,
    payload: MovimientoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO)),
):
    await _ensure_fondo_access(db, current_user, id_fondo)
    cupo = await _get_cupo_general(db, id_fondo)

    cupo.valor_disponible += Decimal(str(payload.monto))

    movimiento = MovimientoCartera(
        id_fondo=id_fondo,
        tipo=TipoMovimiento.ABONO,
        monto=payload.monto,
        descripcion=payload.descripcion,
    )
    db.add(movimiento)
    await registrar_auditoria(
        db,
        current_user,
        f"CARTERA_ABONO;id_fondo={id_fondo};monto={payload.monto}",
    )
    await db.commit()
    await db.refresh(movimiento)

    return movimiento


@router.get(
    "/{id_fondo}/historial",
    response_model=list[MovimientoRead],
)
async def historial_fondo(
    id_fondo: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO)),
):
    await _ensure_fondo_access(db, current_user, id_fondo)

    result = await db.execute(
        select(MovimientoCartera)
        .where(MovimientoCartera.id_fondo == id_fondo)
        .order_by(MovimientoCartera.fecha.desc())
    )
    movimientos = result.scalars().all()
    return movimientos

