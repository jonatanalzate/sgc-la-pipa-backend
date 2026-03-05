"""
Matriz de Roles (RBAC) - Control de acceso basado en roles.

Roles disponibles:
- ADMIN_GLOBAL: Acceso total. Creación de fondos, recarga de cupos, usuarios.
- EJECUTIVO_COMERCIAL: Gestión operativa de fondo (asociados, microcupos, ventas, entregas).
- ADMIN_FONDO: Gestión completa de su fondo + dashboard financiero.
- TIENDA_OPERADOR: Solo POST ventas, POST entregas, GET asociados (búsqueda).
"""

from app.models.usuario import Usuario

# Nombres de roles en BD (deben coincidir con Rol.nombre_rol)
ADMIN_GLOBAL = "ADMIN_GLOBAL"
EJECUTIVO_COMERCIAL = "EJECUTIVO_COMERCIAL"
ADMIN_FONDO = "ADMIN_FONDO"
TIENDA_OPERADOR = "TIENDA_OPERADOR"

ALL_ROLES = (ADMIN_GLOBAL, EJECUTIVO_COMERCIAL, ADMIN_FONDO, TIENDA_OPERADOR)


def _get_rol_name(user: Usuario) -> str:
    """Obtiene el nombre del rol del usuario."""
    if user.rol is None:
        return ""
    return user.rol.nombre_rol or ""
