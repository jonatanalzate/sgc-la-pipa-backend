import asyncio
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database.config import AsyncSessionLocal, init_db
from app.models.rol import Rol
from app.models.usuario import Usuario
from app.settings import settings

import logging
logger = logging.getLogger(__name__)


async def seed() -> None:
    """
    Seed de producción:
    - Crea idempotentemente los 4 roles:
      ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR
    - Crea idempotentemente el usuario Sysadmin inicial si hay credenciales en el entorno.
    """
    await init_db()

    async with AsyncSessionLocal() as session:  # type: AsyncSession
        # Roles base del sistema
        roles_requeridos = [
            "ADMIN_GLOBAL",
            "ADMIN_FONDO",
            "EJECUTIVO_COMERCIAL",
            "TIENDA_OPERADOR",
        ]
        roles_por_nombre: dict[str, Rol] = {}

        for nombre_rol in roles_requeridos:
            result = await session.execute(
                select(Rol).where(Rol.nombre_rol == nombre_rol)
            )
            rol = result.scalar_one_or_none()
            if rol is None:
                rol = Rol(nombre_rol=nombre_rol)
                session.add(rol)
            roles_por_nombre[nombre_rol] = rol

        await session.flush()  # asegurar IDs de roles

        # Usuario Sysadmin (ADMIN_GLOBAL, sin fondo)
        sysadmin_email: Optional[str] = settings.sysadmin_email
        sysadmin_password: Optional[str] = settings.sysadmin_password

        if not sysadmin_email or not sysadmin_password:
            logger.warning("[seed] Advertencia: SYSADMIN_EMAIL o SYSADMIN_PASSWORD no están definidas. No se creará el usuario Sysadmin.")
        else:
            result = await session.execute(
                select(Usuario).where(Usuario.email == sysadmin_email)
            )
            sysadmin_user = result.scalar_one_or_none()
            if sysadmin_user is None:
                rol_admin_global = roles_por_nombre["ADMIN_GLOBAL"]
                sysadmin_user = Usuario(
                    nombre="Sysadmin",
                    email=sysadmin_email,
                    password_hash=hash_password(sysadmin_password),
                    id_rol=rol_admin_global.id_rol,
                    id_fondo=None,
                )
                session.add(sysadmin_user)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())

