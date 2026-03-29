from datetime import datetime, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
import resend
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


@router.post("/solicitar-reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def solicitar_reset_password(
    email: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Genera un token de reset y envía email via Resend.
    Siempre retorna 204 aunque el email no exista (seguridad).
    """
    from datetime import datetime, timezone, timedelta

    result = await db.execute(
        select(Usuario).where(Usuario.email == email.lower())
    )
    user: Usuario | None = result.scalar_one_or_none()

    if user is None or not user.activo:
        return

    token = str(uuid.uuid4())
    expira = datetime.now(timezone.utc) + timedelta(hours=2)

    user.reset_token = token
    user.reset_token_expira = expira
    await db.commit()

    import os
    print(f"RESEND_KEY presente: {bool(settings.resend_api_key)}", flush=True)
    print(f"RESEND env directo: {bool(os.environ.get('RESEND_API_KEY'))}", flush=True)
    print(f"TODAS LAS VARS: {[k for k in os.environ.keys() if 'RESEND' in k.upper() or 'FRONT' in k.upper()]}", flush=True)
    print(f"FRONTEND_URL: {settings.frontend_url}", flush=True)
    print(f"Enviando email a: {user.email}", flush=True)
    if settings.resend_api_key:
        resend.api_key = settings.resend_api_key
        reset_url = f"{settings.frontend_url}/reset-password?token={token}"
        try:
            params = {
                "from": "onboarding@resend.dev",
                "to": [user.email],
                "subject": "Recuperación de contraseña - SGC La Pipa",
                "html": f"""
                <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                    <h2 style="color: #085692;">SGC La Pipa</h2>
                    <p>Hola <strong>{user.nombre}</strong>,</p>
                    <p>Recibimos una solicitud para restablecer tu contraseña.</p>
                    <p>
                        <a href="{reset_url}"
                           style="display:inline-block;background:#085692;color:white;
                                  padding:10px 20px;border-radius:6px;text-decoration:none;
                                  font-size:14px;">
                            Restablecer contraseña
                        </a>
                    </p>
                    <p style="color:#666;font-size:12px;">
                        Este enlace expira en 2 horas.<br>
                        Si no solicitaste esto, ignora este email.
                    </p>
                </div>
                """,
            }
            resend.Emails.send(params)
        except Exception as e:
            print(f"ERROR RESEND: {e}", flush=True)


@router.post("/confirmar-reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def confirmar_reset_password(
    token: str,
    nueva_password: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Valida el token y actualiza la contraseña.
    """
    from datetime import datetime, timezone
    from app.core.security import hash_password

    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Usuario).where(
            Usuario.reset_token == token,
            Usuario.reset_token_expira > now,
            Usuario.activo.is_(True),
        )
    )
    user: Usuario | None = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido o expirado.",
        )

    if len(nueva_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña debe tener al menos 6 caracteres.",
        )

    user.password_hash = hash_password(nueva_password)
    user.reset_token = None
    user.reset_token_expira = None
    user.intentos_fallidos = 0
    user.bloqueado_hasta = None
    user.bloqueado_permanente = False
    await db.commit()

