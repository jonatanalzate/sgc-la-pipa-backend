from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.roles import (
    ADMIN_FONDO,
    ADMIN_GLOBAL,
    EJECUTIVO_COMERCIAL,
    TIENDA_OPERADOR,
    _get_rol_name,
)
from app.core.security import decode_token
from app.database.config import get_db
from app.models.usuario import Usuario


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except ValueError:
        raise credentials_exception

    email: str | None = payload.get("sub")
    if email is None:
        raise credentials_exception

    result = await db.execute(
        select(Usuario)
        .where(Usuario.email == email)
        .options(
            selectinload(Usuario.rol),
            selectinload(Usuario.fondos_asignados),
        )
    )
    user: Usuario | None = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.activo:
        raise credentials_exception

    return user


def get_tenant_id(user: Usuario) -> Optional[int]:
    """
    Devuelve el id_fondo efectivo para aplicar multi-tenancy.

    - Admin global: user.id_fondo es None -> acceso total (retorna None).
    - Usuario de fondo: retorna su id_fondo para filtrar consultas.
    """
    return user.id_fondo


async def get_tenant_ids(
    current_user: Annotated[Usuario, Depends(get_current_user)],
) -> list[int]:
    """
    Versión multi-fondo de get_tenant_id.

    Retorna:
      []          → ADMIN_GLOBAL (sin filtro, acceso total)
      [id1,id2,..]→ EJECUTIVO_COMERCIAL (fondos de tabla ejecutivo_fondos)
      [id_fondo]  → ADMIN_FONDO / TIENDA_OPERADOR (fondo único legacy)
    """
    rol = _get_rol_name(current_user)

    if rol == ADMIN_GLOBAL:
        return []

    if rol == EJECUTIVO_COMERCIAL:
        fondos = current_user.fondos_asignados or []
        ids = [f.id_fondo for f in fondos if hasattr(f, "id_fondo")]
        if not ids:
            # fallback al campo legacy mientras se migran los datos
            if current_user.id_fondo is not None:
                return [current_user.id_fondo]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El ejecutivo no tiene fondos asignados.",
            )
        return ids

    # ADMIN_FONDO, TIENDA_OPERADOR
    if current_user.id_fondo is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este recurso requiere estar asociado a un fondo.",
        )
    return [current_user.id_fondo]


def require_roles(*allowed_roles: str):
    """
    Dependencia que valida que el usuario tenga uno de los roles permitidos.

    Uso: current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL))
    """

    async def _check(
        current_user: Annotated[Usuario, Depends(get_current_user)],
    ) -> Usuario:
        rol = _get_rol_name(current_user)
        if rol not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rol '{rol}' no tiene permisos. Requerido: {', '.join(allowed_roles)}",
            )
        return current_user

    return _check


def require_fondo_user(
    current_user: Annotated[Usuario, Depends(get_current_user)],
) -> Usuario:
    """Valida que el usuario tenga id_fondo (o sea ADMIN_GLOBAL)."""
    if current_user.id_fondo is None and _get_rol_name(current_user) != ADMIN_GLOBAL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este recurso requiere estar asociado a un fondo.",
        )
    return current_user


def ensure_fondo_user(user: Usuario) -> int:
    """Valida que el usuario esté asociado a un fondo y retorna su id_fondo."""
    tenant_id = get_tenant_id(user)
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este recurso requiere estar asociado a un fondo.",
        )
    return tenant_id

