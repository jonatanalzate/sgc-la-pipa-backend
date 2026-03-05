from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    id_fondo: int | None = None


class UserCreate(BaseModel):
    """Esquema para crear usuario. Solo Admin Global."""

    nombre: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6)
    id_rol: int = Field(..., description="ID del rol del usuario.")
    id_fondo: int | None = Field(default=None, description="ID del fondo (None para Admin Global).")


class UserUpdate(BaseModel):
    """Esquema para actualizar usuario."""

    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    id_fondo: int | None = None


class UserRead(UserBase):
    id_usuario: int
    activo: bool = True
    fecha_creacion: datetime | None = None
    fecha_actualizacion: datetime | None = None
    fecha_eliminacion: datetime | None = None
    nombre_rol: str | None = None

    class Config:
        from_attributes = True


class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str

