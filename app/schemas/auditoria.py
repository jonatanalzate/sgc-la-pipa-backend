from datetime import datetime

from pydantic import BaseModel


class AuditoriaLogRead(BaseModel):
    """
    Registro de auditoría para consulta.
    """

    id_auditoria: int
    fecha: datetime
    accion: str
    id_usuario: int
    nombre_usuario: str
    id_fondo: int | None
    nombre_fondo: str | None


class AuditoriaLogFilters(BaseModel):
    """
    Filtros opcionales para la consulta de auditoría.
    """

    accion: str | None = None
    fecha_desde: datetime | None = None
    fecha_hasta: datetime | None = None

