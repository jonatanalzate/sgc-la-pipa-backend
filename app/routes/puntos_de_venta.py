from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import acciones
from app.core.auditoria import registrar_auditoria
from app.core.dependencies import get_current_user, require_roles
from app.core.roles import (
    ADMIN_FONDO,
    ADMIN_GLOBAL,
    EJECUTIVO_COMERCIAL,
    TIENDA_OPERADOR,
)
from app.database.config import get_db
from app.models.punto_de_venta import PuntoDeVenta
from app.models.usuario import Usuario
from app.schemas.punto_de_venta import PuntoDeVentaCreate, PuntoDeVentaRead

router = APIRouter(prefix="/puntos-de-venta", tags=["puntos_de_venta"])


def _build_read(p: PuntoDeVenta) -> PuntoDeVentaRead:
    return PuntoDeVentaRead(
        id_punto_venta=p.id_punto_venta,
        nombre=p.nombre,
        direccion=p.direccion,
        activo=p.activo,
        ciudad=p.ciudad,
    )


@router.get("/", response_model=list[PuntoDeVentaRead])
async def list_puntos(
    db: AsyncSession = Depends(get_db),
    _: Usuario = Depends(
        require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR)
    ),
):
    result = await db.execute(select(PuntoDeVenta).order_by(PuntoDeVenta.id_punto_venta))
    puntos = result.scalars().all()
    return [_build_read(p) for p in puntos]


@router.post("/", response_model=PuntoDeVentaRead, status_code=status.HTTP_201_CREATED)
async def create_punto(
    payload: PuntoDeVentaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO)),
):
    punto = PuntoDeVenta(
        nombre=payload.nombre,
        direccion=payload.direccion,
        ciudad=payload.ciudad.strip(),
    )
    db.add(punto)
    await registrar_auditoria(db, current_user, acciones.CREAR_PUNTO_VENTA)
    await db.commit()
    await db.refresh(punto)
    return _build_read(punto)


@router.put("/{id_punto_venta}", response_model=PuntoDeVentaRead)
async def update_punto(
    id_punto_venta: int,
    payload: PuntoDeVentaCreate,
    db: AsyncSession = Depends(get_db),
    _: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO)),
):
    result = await db.execute(select(PuntoDeVenta).where(PuntoDeVenta.id_punto_venta == id_punto_venta))
    punto = result.scalar_one_or_none()
    if punto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Punto de venta no encontrado.")
    punto.nombre = payload.nombre
    punto.direccion = payload.direccion
    punto.ciudad = payload.ciudad.strip()
    await db.commit()
    await db.refresh(punto)
    return _build_read(punto)


@router.patch("/{id_punto_venta}/toggle-activo", response_model=PuntoDeVentaRead)
async def toggle_activo(
    id_punto_venta: int,
    db: AsyncSession = Depends(get_db),
    _: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO)),
):
    result = await db.execute(select(PuntoDeVenta).where(PuntoDeVenta.id_punto_venta == id_punto_venta))
    punto = result.scalar_one_or_none()
    if punto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Punto de venta no encontrado.")
    punto.activo = not punto.activo
    await db.commit()
    await db.refresh(punto)
    return _build_read(punto)
