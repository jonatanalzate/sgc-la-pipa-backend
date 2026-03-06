from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.config import get_db, init_db
from app.middleware.ip_whitelist import IPWhitelistMiddleware
from app.routes import (
    asociados,
    auth,
    cupos,
    fondos,
    ip_whitelist,
    microcupos,
    usuarios,
    ventas,
    entregas,
    reportes,
    dashboard,
    auditoria,
    cartera,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa la base de datos (crea tablas si no existen)
    await init_db()
    yield


app = FastAPI(title="SGC La Pipa", lifespan=lifespan)
app.add_middleware(IPWhitelistMiddleware)


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Ejecuta SELECT 1 de forma asíncrona para validar la conexión a la DB.
    """
    result = await db.execute(text("SELECT 1"))
    value = result.scalar_one()
    return {"status": "ok", "db": value}


app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(fondos.router)
app.include_router(asociados.router)
app.include_router(cupos.router)
app.include_router(microcupos.router)
app.include_router(ventas.router)
app.include_router(entregas.router)
app.include_router(reportes.router)
app.include_router(dashboard.router)
app.include_router(auditoria.router)
app.include_router(ip_whitelist.router)
app.include_router(cartera.router)


