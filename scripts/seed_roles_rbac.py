"""
Script para crear/actualizar roles RBAC y usuarios de prueba.

Ejecutar: docker compose exec app python scripts/seed_roles_rbac.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.database.config import AsyncSessionLocal, init_db
from app.models.fondo import Fondo
from app.models.rol import Rol
from app.models.usuario import Usuario

ROLES_RBAC = ["ADMIN_GLOBAL", "EJECUTIVO_COMERCIAL", "ADMIN_FONDO", "TIENDA_OPERADOR"]


async def seed_roles_rbac() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        # Primero migrar roles antiguos (Admin -> ADMIN_GLOBAL, Fondo -> ADMIN_FONDO)
        for old, new in [("Admin", "ADMIN_GLOBAL"), ("Fondo", "ADMIN_FONDO")]:
            result = await session.execute(select(Rol).where(Rol.nombre_rol == old))
            r = result.scalar_one_or_none()
            if r is not None:
                r.nombre_rol = new
                print(f"  Rol migrado: {old} -> {new}")

        await session.flush()

        # Crear roles que no existan
        for nombre in ROLES_RBAC:
            result = await session.execute(select(Rol).where(Rol.nombre_rol == nombre))
            if result.scalar_one_or_none() is None:
                session.add(Rol(nombre_rol=nombre))
                print(f"  Rol creado: {nombre}")

        await session.flush()

        # Asegurar Fondo Demo
        result = await session.execute(select(Fondo).where(Fondo.nombre == "Fondo Demo"))
        fondo_demo = result.scalar_one_or_none()
        if fondo_demo is None:
            from app.models.cupo_general import CupoGeneral

            fondo_demo = Fondo(
                nombre="Fondo Demo",
                nit="900000001",
                estado=True,
                activo=True,
            )
            session.add(fondo_demo)
            await session.flush()
            session.add(
                CupoGeneral(
                    id_fondo=fondo_demo.id_fondo,
                    valor_total=0.0,
                    valor_disponible=0.0,
                )
            )
            await session.flush()
            print("  Fondo Demo creado")

        # Obtener IDs de roles
        rol_admin = (await session.execute(select(Rol).where(Rol.nombre_rol == "ADMIN_GLOBAL"))).scalar_one_or_none()
        rol_fondo = (await session.execute(select(Rol).where(Rol.nombre_rol == "ADMIN_FONDO"))).scalar_one_or_none()
        rol_tienda = (await session.execute(select(Rol).where(Rol.nombre_rol == "TIENDA_OPERADOR"))).scalar_one_or_none()

        if rol_admin is None or rol_fondo is None:
            print("  Error: Roles ADMIN_GLOBAL o ADMIN_FONDO no encontrados")
            await session.rollback()
            return

        # Admin Global
        result = await session.execute(select(Usuario).where(Usuario.email == "admin@lapipa.com"))
        admin_user = result.scalar_one_or_none()
        if admin_user is None:
            admin_user = Usuario(
                nombre="Admin Global",
                email="admin@lapipa.com",
                password_hash=hash_password("admin123"),
                id_rol=rol_admin.id_rol,
                id_fondo=None,
                activo=True,
            )
            session.add(admin_user)
            print("  Usuario creado: admin@lapipa.com (ADMIN_GLOBAL)")
        else:
            admin_user.id_rol = rol_admin.id_rol
            admin_user.id_fondo = None
            print("  Usuario actualizado: admin@lapipa.com -> ADMIN_GLOBAL")

        # Admin Fondo
        result = await session.execute(select(Usuario).where(Usuario.email == "fondo@lapipa.com"))
        fondo_user = result.scalar_one_or_none()
        if fondo_user is None and fondo_demo:
            fondo_user = Usuario(
                nombre="Admin Fondo Demo",
                email="fondo@lapipa.com",
                password_hash=hash_password("fondo123"),
                id_rol=rol_fondo.id_rol,
                id_fondo=fondo_demo.id_fondo,
                activo=True,
            )
            session.add(fondo_user)
            print("  Usuario creado: fondo@lapipa.com (ADMIN_FONDO)")
        elif fondo_user and fondo_demo:
            fondo_user.id_rol = rol_fondo.id_rol
            fondo_user.id_fondo = fondo_demo.id_fondo
            print("  Usuario actualizado: fondo@lapipa.com -> ADMIN_FONDO")

        # Tienda Operador (opcional, para pruebas)
        result = await session.execute(select(Usuario).where(Usuario.email == "tienda@lapipa.com"))
        tienda_user = result.scalar_one_or_none()
        if tienda_user is None and fondo_demo and rol_tienda:
            tienda_user = Usuario(
                nombre="Tienda Demo",
                email="tienda@lapipa.com",
                password_hash=hash_password("tienda123"),
                id_rol=rol_tienda.id_rol,
                id_fondo=fondo_demo.id_fondo,
                activo=True,
            )
            session.add(tienda_user)
            print("  Usuario creado: tienda@lapipa.com (TIENDA_OPERADOR)")

        await session.commit()
        print("Seed RBAC completado.")


if __name__ == "__main__":
    asyncio.run(seed_roles_rbac())
