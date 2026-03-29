import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    id_fondo: int | None = None


class UserCreate(BaseModel):
    """Esquema para crear usuario. Solo Admin Global."""

    nombre: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=8)

    @field_validator("password")
    @classmethod
    def password_policy(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("La contraseña debe contener al menos una letra mayúscula.")
        if not re.search(r"\d", v):
            raise ValueError("La contraseña debe contener al menos un número.")
        return v

    id_rol: int = Field(..., description="ID del rol del usuario.")
    id_fondo: int | None = Field(default=None, description="ID del fondo (None para Admin Global).")
    fondos_asignados: list[int] = Field(
        default_factory=list,
        description="IDs de fondos para EJECUTIVO_COMERCIAL. Vacío para otros roles.",
    )


class UserUpdate(BaseModel):
    """Esquema para actualizar usuario."""

    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    id_fondo: int | None = None
    fondos_asignados: list[int] | None = Field(
        default=None,
        description="Si se envía, reemplaza TODOS los fondos del ejecutivo.",
    )


class UserRead(UserBase):
    id_usuario: int
    activo: bool = True
    fecha_creacion: datetime | None = None
    fecha_actualizacion: datetime | None = None
    fecha_eliminacion: datetime | None = None
    nombre_rol: str | None = None
    nombre_fondo: str | None = None
    fondos_asignados: list[dict] = Field(default_factory=list)

    @classmethod
    def model_validate(cls, obj, *, strict=None, from_attributes=None, context=None):
        instance = super().model_validate(
            obj,
            strict=strict,
            from_attributes=from_attributes if from_attributes is not None else True,
            context=context,
        )
        if hasattr(obj, "fondos_asignados") and obj.fondos_asignados:
            primera = obj.fondos_asignados[0]
            if hasattr(primera, "id_fondo"):
                instance.fondos_asignados = [
                    {"id_fondo": f.id_fondo, "nombre_fondo": f.nombre}
                    for f in obj.fondos_asignados
                ]
        return instance

    class Config:
        from_attributes = True


class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def new_password_policy(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("La contraseña debe contener al menos una letra mayúscula.")
        if not re.search(r"\d", v):
            raise ValueError("La contraseña debe contener al menos un número.")
        return v