from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware

from fastapi import Depends, FastAPI

import logging
from app.core.scheduler import start_scheduler, shutdown_scheduler

logger = logging.getLogger(__name__)
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
    puntos_de_venta,
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
    await init_db()
    from seed import seed
    await seed()

    start_scheduler()
    logger.info("[scheduler] APScheduler iniciado.")

    yield

    shutdown_scheduler()
    logger.info("[scheduler] APScheduler detenido.")


app = FastAPI(title="SGC La Pipa", lifespan=lifespan)

import os

_frontend_url = os.getenv("FRONTEND_URL", "")
_allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://sgc-la-pipa-frontend-git-d0d82b-jonatan-rojas-alzates-projects.vercel.app",
    "https://sgc-la-pipa-frontend-svhh.vercel.app",
]
if _frontend_url and _frontend_url not in _allowed_origins:
    _allowed_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(puntos_de_venta.router)
app.include_router(entregas.router)
app.include_router(reportes.router)
app.include_router(dashboard.router)
app.include_router(auditoria.router)
app.include_router(ip_whitelist.router)
app.include_router(cartera.router)


