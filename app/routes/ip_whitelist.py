from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import registrar_auditoria
from app.core.dependencies import require_roles
from app.core import acciones
from app.core.roles import ADMIN_GLOBAL
from app.database.config import get_db
from app.models.ip_whitelist import IPWhitelist
from app.models.usuario import Usuario
from app.schemas.ip_whitelist import IPWhitelistCreate, IPWhitelistRead, IPWhitelistUpdate


router = APIRouter(prefix="/admin/ips", tags=["ip-whitelist"])


@router.post("/", response_model=IPWhitelistRead, status_code=status.HTTP_201_CREATED)
async def create_ip_whitelist(
    payload: IPWhitelistCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    Registra una nueva IP en la whitelist. Solo ADMIN_GLOBAL.
    """
    direccion_ip = (payload.direccion_ip or "").strip()
    if not direccion_ip or len(direccion_ip) > 45:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La dirección IP no es válida (vacía o más de 45 caracteres).",
        )

    existing = await db.execute(
        select(IPWhitelist).where(IPWhitelist.direccion_ip == direccion_ip)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta IP ya está registrada en la whitelist.",
        )

    try:
        ip_entrada = IPWhitelist(
            direccion_ip=direccion_ip,
            descripcion=payload.descripcion,
            activa=True,
            id_usuario_creador=current_user.id_usuario,
        )
        db.add(ip_entrada)
        await registrar_auditoria(db, current_user, acciones.CREAR_IP_WHITELIST)
        await db.commit()
        await db.refresh(ip_entrada)
        return ip_entrada
    except Exception:
        await db.rollback()
        raise


@router.get("/", response_model=list[IPWhitelistRead])
async def list_ip_whitelist(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    Lista todas las IPs registradas en la whitelist. Solo ADMIN_GLOBAL.
    """
    result = await db.execute(select(IPWhitelist).order_by(IPWhitelist.fecha_creacion.desc()))
    return result.scalars().all()


@router.patch("/{id_ip}", response_model=IPWhitelistRead)
async def update_ip_whitelist(
    id_ip: int,
    payload: IPWhitelistUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    Activar/desactivar o editar descripción de una IP. Solo ADMIN_GLOBAL.
    """
    result = await db.execute(select(IPWhitelist).where(IPWhitelist.id_ip == id_ip))
    ip_entrada = result.scalar_one_or_none()
    if ip_entrada is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP no encontrada en la whitelist.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ip_entrada, field, value)

    await registrar_auditoria(db, current_user, acciones.ACTUALIZAR_IP_WHITELIST)
    await db.commit()
    await db.refresh(ip_entrada)
    return ip_entrada


@router.delete("/{id_ip}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ip_whitelist(
    id_ip: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    Elimina físicamente una IP de la whitelist. Solo ADMIN_GLOBAL.
    """
    result = await db.execute(select(IPWhitelist).where(IPWhitelist.id_ip == id_ip))
    ip_entrada = result.scalar_one_or_none()
    if ip_entrada is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IP no encontrada en la whitelist.",
        )

    direccion_ip = ip_entrada.direccion_ip
    try:
        await db.delete(ip_entrada)
        await registrar_auditoria(db, current_user, acciones.ELIMINAR_IP_WHITELIST)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
