from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import registrar_auditoria
from app.core.dependencies import get_current_user, get_tenant_id, require_roles
from app.core import acciones
from app.core.roles import ADMIN_GLOBAL, EJECUTIVO_COMERCIAL
from app.core.security import hash_password, verify_password
from app.database.config import get_db
from app.models.rol import Rol
from app.models.usuario import Usuario
from app.models.ejecutivo_fondos import EjecutivoFondo
from app.schemas.user import UserCreate, UserPasswordChange, UserRead, UserUpdate


router = APIRouter(prefix="/usuarios", tags=["usuarios"])


async def _sync_fondos_ejecutivo(
    db: AsyncSession,
    id_usuario: int,
    fondos_ids: list[int],
) -> None:
    """Reemplaza la asignación completa de fondos de un ejecutivo."""
    await db.execute(
        sa_delete(EjecutivoFondo).where(
            EjecutivoFondo.id_usuario == id_usuario
        )
    )
    for id_fondo in fondos_ids:
        db.add(EjecutivoFondo(id_usuario=id_usuario, id_fondo=id_fondo))


@router.get("/", response_model=list[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
    activo_only: bool = True,
):
    """
    Lista usuarios. Solo Admin Global.

    - Por defecto solo devuelve activo==True.
    """
    query = select(Usuario).options(selectinload(Usuario.rol))
    if activo_only:
        query = query.where(Usuario.activo.is_(True))
    result = await db.execute(query)
    usuarios = result.scalars().all()
    return [
        UserRead(
            id_usuario=u.id_usuario,
            nombre=u.nombre,
            email=u.email,
            id_fondo=u.id_fondo,
            activo=u.activo,
            fecha_creacion=u.fecha_creacion,
            fecha_actualizacion=u.fecha_actualizacion,
            fecha_eliminacion=u.fecha_eliminacion,
            nombre_rol=u.rol.nombre_rol if u.rol else None,
        )
        for u in usuarios
    ]

@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    Crea un nuevo usuario. Solo Admin Global.

    - id_fondo=None para Admin Global, o id del fondo para usuario de fondo.
    """
    result = await db.execute(select(Usuario).where(Usuario.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un usuario con ese email.",
        )

    result = await db.execute(select(Rol).where(Rol.id_rol == payload.id_rol))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rol no encontrado.",
        )

    usuario = Usuario(
        nombre=payload.nombre,
        email=payload.email,
        password_hash=hash_password(payload.password),
        id_rol=payload.id_rol,
        id_fondo=payload.id_fondo,
        activo=True,
    )
    db.add(usuario)
    await db.flush()

    # id_rol == 3 corresponde a EJECUTIVO_COMERCIAL
    if payload.id_rol == 3 and payload.fondos_asignados:
        await _sync_fondos_ejecutivo(db, usuario.id_usuario, payload.fondos_asignados)

    await registrar_auditoria(db, current_user, acciones.CREAR_USUARIO)
    await db.commit()
    await db.refresh(usuario)
    result = await db.execute(
        select(Usuario)
        .options(selectinload(Usuario.rol))
        .where(Usuario.id_usuario == usuario.id_usuario)
    )
    usuario_con_rol = result.scalar_one()
    return UserRead(
        id_usuario=usuario_con_rol.id_usuario,
        nombre=usuario_con_rol.nombre,
        email=usuario_con_rol.email,
        id_fondo=usuario_con_rol.id_fondo,
        activo=usuario_con_rol.activo,
        fecha_creacion=usuario_con_rol.fecha_creacion,
        fecha_actualizacion=usuario_con_rol.fecha_actualizacion,
        fecha_eliminacion=usuario_con_rol.fecha_eliminacion,
        nombre_rol=usuario_con_rol.rol.nombre_rol if usuario_con_rol.rol else None,
    )

@router.put("/{id_usuario}", response_model=UserRead)
async def update_user(
    id_usuario: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    Actualiza los datos de un usuario.

    - Admin Global: puede actualizar cualquier usuario.
    - Usuario de fondo: solo su propio perfil (id_usuario == current_user.id_usuario).
    """
    result = await db.execute(select(Usuario).where(Usuario.id_usuario == id_usuario))
    usuario = result.scalar_one_or_none()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if "email" in update_data:
        existing = await db.execute(
            select(Usuario).where(
                Usuario.email == update_data["email"],
                Usuario.id_usuario != id_usuario,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe otro usuario con ese email.",
            )

    fondos_asignados = update_data.pop("fondos_asignados", None)

    for field, value in update_data.items():
        setattr(usuario, field, value)

    from app.core.roles import _get_rol_name

    # id_rol == 3 corresponde a EJECUTIVO_COMERCIAL
    # Usamos usuario.id_rol que es un campo simple (no lazy)
    if usuario.id_rol == 3 and fondos_asignados is not None:
        await _sync_fondos_ejecutivo(db, id_usuario, fondos_asignados)

    await registrar_auditoria(db, current_user, acciones.ACTUALIZAR_USUARIO)
    await db.commit()
    await db.refresh(usuario)
    result = await db.execute(
        select(Usuario)
        .options(selectinload(Usuario.rol))
        .where(Usuario.id_usuario == usuario.id_usuario)
    )
    usuario_con_rol = result.scalar_one()
    return UserRead(
        id_usuario=usuario_con_rol.id_usuario,
        nombre=usuario_con_rol.nombre,
        email=usuario_con_rol.email,
        id_fondo=usuario_con_rol.id_fondo,
        activo=usuario_con_rol.activo,
        fecha_creacion=usuario_con_rol.fecha_creacion,
        fecha_actualizacion=usuario_con_rol.fecha_actualizacion,
        fecha_eliminacion=usuario_con_rol.fecha_eliminacion,
        nombre_rol=usuario_con_rol.rol.nombre_rol if usuario_con_rol.rol else None,
    )


@router.delete("/{id_usuario}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    id_usuario: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    Borrado lógico: cambia activo a False. No elimina el registro.

    - Solo Admin Global puede desactivar usuarios.
    - Registra en Auditoria.
    """
    result = await db.execute(select(Usuario).where(Usuario.id_usuario == id_usuario))
    usuario = result.scalar_one_or_none()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    if not usuario.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario ya está desactivado.",
        )

    usuario.activo = False
    usuario.fecha_eliminacion = datetime.now(timezone.utc)
    await registrar_auditoria(db, current_user, acciones.ELIMINAR_USUARIO)
    await db.commit()


@router.get("/perfil", response_model=UserRead)
async def read_users_me(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Usuario)
        .options(selectinload(Usuario.rol))
        .where(Usuario.id_usuario == current_user.id_usuario)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    return UserRead(
        id_usuario=user.id_usuario,
        nombre=user.nombre,
        email=user.email,
        id_fondo=user.id_fondo,
        activo=user.activo,
        fecha_creacion=user.fecha_creacion,
        fecha_actualizacion=user.fecha_actualizacion,
        fecha_eliminacion=user.fecha_eliminacion,
        nombre_rol=user.rol.nombre_rol if user.rol else None,
    )


@router.patch("/perfil/contrasena", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: UserPasswordChange,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(payload.new_password)
    await registrar_auditoria(db, current_user, acciones.CAMBIO_CONTRASENA)
    await db.commit()
