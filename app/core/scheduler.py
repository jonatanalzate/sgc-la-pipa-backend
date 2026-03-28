"""
Tareas periódicas con APScheduler (asyncio).
"""
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import update

from app.database.config import AsyncSessionLocal
from app.models.microcupo import Microcupo, MicrocupoEstado

scheduler = AsyncIOScheduler()


async def marcar_microcupos_vencidos() -> None:
    ahora = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        stmt = (
            update(Microcupo)
            .where(
                Microcupo.estado == MicrocupoEstado.APROBADO,
                Microcupo.fecha_vencimiento < ahora,
            )
            .values(estado=MicrocupoEstado.VENCIDO)
        )
        await session.execute(stmt)
        await session.commit()


def start_scheduler() -> None:
    scheduler.add_job(
        marcar_microcupos_vencidos,
        IntervalTrigger(hours=1),
        id="marcar_microcupos_vencidos",
        replace_existing=True,
    )
    scheduler.start()


def shutdown_scheduler() -> None:
    scheduler.shutdown(wait=False)
