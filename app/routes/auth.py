from datetime import timedelta

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

import time
from collections import defaultdict

_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_MAX = 5
_LOGIN_WINDOW = 60  # segundos

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
    # Rate limiting por email
    key = form_data.username.lower()
    now = time.time()
    _login_attempts[key] = [t for t in _login_attempts[key] if now - t < _LOGIN_WINDOW]
    if len(_login_attempts[key]) >= _LOGIN_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Espera 1 minuto e intenta de nuevo.",
        )
    _login_attempts[key].append(now)

    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await registrar_auditoria(db, user, LOGIN_EXITOSO)
    await db.commit()

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        subject=user.email,
        id_fondo=user.id_fondo,
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}

