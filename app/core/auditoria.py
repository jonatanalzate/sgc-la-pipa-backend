from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auditoria import Auditoria
from app.models.usuario import Usuario


async def registrar_auditoria(
    db: AsyncSession,
    usuario: Usuario,
    accion: str,
) -> None:
    entrada = Auditoria(
        fecha=datetime.now(timezone.utc),
        accion=accion,
        id_usuario=usuario.id_usuario,
    )
    db.add(entrada)
    # NO hacer commit aquí. El commit lo maneja el endpoint que llama esta función.

