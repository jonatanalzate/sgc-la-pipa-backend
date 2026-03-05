import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.config import AsyncSessionLocal, init_db
from app.models.asociado import Asociado
from app.models.cupo_general import CupoGeneral
from app.models.fondo import Fondo
from app.models.microcupo import Microcupo, MicrocupoEstado
from app.models.rol import Rol
from app.models.usuario import Usuario
from app.models.venta import Venta
from app.core.security import hash_password
from seed import seed as seed_produccion


async def seed_dev() -> None:
    """
    Seed de desarrollo (solo local).
    - Reutiliza el seed de producción para roles y Sysadmin.
    - Agrega datos de prueba: fondos, usuarios, asociados, cupos y microcupos.
    """
    # Asegura estructura base (roles + sysadmin)
    await seed_produccion()

    # Datos adicionales de desarrollo
    async with AsyncSessionLocal() as session:  # type: AsyncSession
        # Roles necesarios
        result = await session.execute(
            select(Rol).where(Rol.nombre_rol == "ADMIN_GLOBAL")
        )
        rol_admin_global = result.scalar_one_or_none()

        result = await session.execute(
            select(Rol).where(Rol.nombre_rol == "ADMIN_FONDO")
        )
        rol_admin_fondo = result.scalar_one_or_none()

        result = await session.execute(
            select(Rol).where(Rol.nombre_rol == "TIENDA_OPERADOR")
        )
        rol_tienda_operador = result.scalar_one_or_none()

        # Fondo Demo
        result = await session.execute(select(Fondo).where(Fondo.nombre == "Fondo Demo"))
        fondo_demo = result.scalar_one_or_none()
        if fondo_demo is None:
            fondo_demo = Fondo(
                nombre="Fondo Demo",
                nit="900000001",
                estado=True,
            )
            session.add(fondo_demo)
            await session.flush()

        # Fondos adicionales de ejemplo (idempotentes)
        for nombre, nit in [
            ("Fondo Luker", "900000002"),
            ("Fondo Mabe", "900000003"),
        ]:
            result = await session.execute(select(Fondo).where(Fondo.nombre == nombre))
            fondo = result.scalar_one_or_none()
            if fondo is None:
                fondo = Fondo(nombre=nombre, nit=nit, estado=True)
                session.add(fondo)

        await session.flush()

        # Usuarios de prueba
        # 1. Admin Global (sin fondo)
        result = await session.execute(
            select(Usuario).where(Usuario.email == "admin@lapipa.com")
        )
        admin_user = result.scalar_one_or_none()
        if admin_user is None and rol_admin_global is not None:
            admin_user = Usuario(
                nombre="Admin Global",
                email="admin@lapipa.com",
                password_hash=hash_password("admin123"),
                id_rol=rol_admin_global.id_rol,
                id_fondo=None,
            )
            session.add(admin_user)

        # 2. Usuario de Fondo asociado a Fondo Demo
        result = await session.execute(
            select(Usuario).where(Usuario.email == "fondo@lapipa.com")
        )
        fondo_user = result.scalar_one_or_none()
        if fondo_user is None and rol_admin_fondo is not None:
            fondo_user = Usuario(
                nombre="Usuario Fondo Demo",
                email="fondo@lapipa.com",
                password_hash=hash_password("fondo123"),
                id_rol=rol_admin_fondo.id_rol,
                id_fondo=fondo_demo.id_fondo,
            )
            session.add(fondo_user)

        # 3. Operador de Tienda asociado a Fondo Demo
        result = await session.execute(
            select(Usuario).where(Usuario.email == "tienda@lapipa.com")
        )
        tienda_user = result.scalar_one_or_none()
        if tienda_user is None and rol_tienda_operador is not None:
            tienda_user = Usuario(
                nombre="Operador Tienda Demo",
                email="tienda@lapipa.com",
                password_hash=hash_password("tienda123"),
                id_rol=rol_tienda_operador.id_rol,
                id_fondo=fondo_demo.id_fondo,
            )
            session.add(tienda_user)

        await session.flush()

        # Cupo general del Fondo Demo
        result = await session.execute(
            select(CupoGeneral).where(CupoGeneral.id_fondo == fondo_demo.id_fondo)
        )
        cupo_general = result.scalar_one_or_none()
        if cupo_general is None:
            cupo_general = CupoGeneral(
                id_fondo=fondo_demo.id_fondo,
                valor_total=Decimal("1000000.00"),
                valor_disponible=Decimal("1000000.00"),
            )
            session.add(cupo_general)
            await session.flush()

        # Asociado de prueba
        result = await session.execute(
            select(Asociado).where(Asociado.documento == "SEED-ASOCIADO-0001")
        )
        asociado_demo = result.scalar_one_or_none()
        if asociado_demo is None:
            asociado_demo = Asociado(
                nombre="Asociado Demo Seed",
                documento="SEED-ASOCIADO-0001",
                id_fondo=fondo_demo.id_fondo,
                estado=True,
                activo=True,
            )
            session.add(asociado_demo)
            await session.flush()

        # 1. Microcupo en estado PENDIENTE (no afecta cupo general)
        result = await session.execute(
            select(Microcupo).where(
                Microcupo.producto_referencia == "SEED-MICROCUPO-PENDIENTE"
            )
        )
        microcupo_pendiente = result.scalar_one_or_none()
        if microcupo_pendiente is None:
            microcupo_pendiente = Microcupo(
                monto=Decimal("100000.00"),
                estado=MicrocupoEstado.PENDIENTE,
                fecha_vencimiento=datetime.now(timezone.utc) + timedelta(days=30),
                producto_referencia="SEED-MICROCUPO-PENDIENTE",
                id_asociado=asociado_demo.id_asociado,
            )
            session.add(microcupo_pendiente)

        # 2. Microcupo con venta asociada:
        #    flujo: PENDIENTE -> APROBADO (descuenta cupo) -> CONSUMIDO (venta)
        result = await session.execute(
            select(Microcupo).where(
                Microcupo.producto_referencia == "SEED-MICROCUPO-CONSUMIDO"
            )
        )
        microcupo_consumido = result.scalar_one_or_none()
        if microcupo_consumido is None:
            monto_consumido = Decimal("200000.00")

            # Asegurar que haya saldo suficiente antes de aprobar
            if cupo_general.valor_disponible < monto_consumido:
                diferencia = monto_consumido - cupo_general.valor_disponible
                cupo_general.valor_total += diferencia
                cupo_general.valor_disponible += diferencia

            # Crear en PENDIENTE
            microcupo_consumido = Microcupo(
                monto=monto_consumido,
                estado=MicrocupoEstado.PENDIENTE,
                fecha_vencimiento=datetime.now(timezone.utc) + timedelta(days=60),
                producto_referencia="SEED-MICROCUPO-CONSUMIDO",
                id_asociado=asociado_demo.id_asociado,
            )
            session.add(microcupo_consumido)
            await session.flush()

            # Aprobar: descontar del cupo general y pasar a APROBADO
            cupo_general.valor_disponible -= monto_consumido
            microcupo_consumido.estado = MicrocupoEstado.APROBADO

            # Crear venta: pasa a CONSUMIDO
            vendedor = tienda_user or fondo_user or admin_user
            venta = Venta(
                fecha=datetime.now(timezone.utc),
                valor_total=monto_consumido,
                producto_detalle="Venta demo microcupo consumido (seed)",
                id_microcupo=microcupo_consumido.id_microcupo,
                id_usuario_tienda=vendedor.id_usuario,
            )
            session.add(venta)
            microcupo_consumido.estado = MicrocupoEstado.CONSUMIDO

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_dev())

