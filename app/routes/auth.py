from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import registrar_auditoria
from app.core.acciones import LOGIN_EXITOSO
from app.core.security import create_access_token, verify_password
from app.database.config import get_db
from app.models.usuario import Usuario
from app.schemas.auth import Token
from app.settings import settings

_MAX_INTENTOS_TEMPORALES = 3
_BLOQUEO_MINUTOS = 15
_MAX_INTENTOS_PERMANENTE = 6  # 3 intentos + desbloqueo + 3 intentos más

router = APIRouter(prefix="/auth", tags=["auth"])


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> Usuario | None:
    result = await db.execute(select(Usuario).where(Usuario.email == email))
    user: Usuario | None = result.scalar_one_or_none()
    if user is None:
        return None
    if not user.activo:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    # Buscar usuario por email
    result = await db.execute(
        select(Usuario).where(Usuario.email == form_data.username.lower())
    )
    user: Usuario | None = result.scalar_one_or_none()

    # Si el usuario existe, verificar bloqueos antes de validar password
    if user is not None:
        # Bloqueo permanente
        if user.bloqueado_permanente:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cuenta bloqueada permanentemente. Contacta al administrador.",
            )

        # Bloqueo temporal activo
        if user.bloqueado_hasta is not None and user.bloqueado_hasta > now:
            minutos_restantes = int(
                (user.bloqueado_hasta - now).total_seconds() / 60
            ) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Cuenta bloqueada temporalmente. Intenta en {minutos_restantes} minuto(s).",
            )

        # Si el bloqueo temporal ya expiró, resetear contador
        if user.bloqueado_hasta is not None and user.bloqueado_hasta <= now:
            user.bloqueado_hasta = None
            user.intentos_fallidos = 0

    # Validar credenciales
    user_autenticado = await authenticate_user(
        db, form_data.username.lower(), form_data.password
    )

    if user_autenticado is None:
        # Registrar intento fallido si el usuario existe
        if user is not None and user.activo:
            user.intentos_fallidos += 1

            if user.intentos_fallidos >= _MAX_INTENTOS_PERMANENTE:
                # Bloqueo permanente
                user.bloqueado_permanente = True
                user.bloqueado_hasta = None
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cuenta bloqueada permanentemente por múltiples intentos fallidos. Contacta al administrador.",
                )
            if user.intentos_fallidos >= _MAX_INTENTOS_TEMPORALES:
                # Bloqueo temporal
                user.bloqueado_hasta = now + timedelta(minutes=_BLOQUEO_MINUTOS)
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Demasiados intentos fallidos. Cuenta bloqueada por {_BLOQUEO_MINUTOS} minutos.",
                )

            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Login exitoso - resetear contadores
    user_autenticado.intentos_fallidos = 0
    user_autenticado.bloqueado_hasta = None

    await registrar_auditoria(db, user_autenticado, LOGIN_EXITOSO)
    await db.commit()

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        subject=user_autenticado.email,
        id_fondo=user_autenticado.id_fondo,
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}

