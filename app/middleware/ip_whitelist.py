from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.database.config import AsyncSessionLocal
from app.models.ip_whitelist import IPWhitelist
from app.settings import settings


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not settings.ip_whitelist_activa:
            return await call_next(request)

        # Capturar IP real respetando proxies y Docker
        ip_real = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.client.host
        )

        # IPs de rescate nunca bloqueadas (configuradas en .env)
        ips_rescate = [ip.strip() for ip in settings.ips_rescate.split(",") if ip.strip()]
        if ip_real in ips_rescate:
            return await call_next(request)

        # Consultar whitelist en DB
        async with AsyncSessionLocal() as db:
            resultado = await db.execute(
                select(IPWhitelist).where(
                    IPWhitelist.direccion_ip == ip_real,
                    IPWhitelist.activa == True,
                )
            )
            ip_permitida = resultado.scalar_one_or_none()

        if not ip_permitida:
            return JSONResponse(
                status_code=403,
                content={"detail": f"Acceso denegado. IP no autorizada: {ip_real}"},
            )

        return await call_next(request)
