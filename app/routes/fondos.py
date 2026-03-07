import io
from fastapi import File, UploadFile
from app.schemas.fondo import FondoCreate, FondoRead, FondoUpdate, FondoCargaMasivaResult
import pandas as pd

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auditoria import registrar_auditoria
from app.core.dependencies import get_current_user, get_tenant_id, require_roles
from app.core.roles import ADMIN_FONDO, ADMIN_GLOBAL, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR
from app.core import acciones
from app.database.config import get_db
from app.models.cupo_general import CupoGeneral
from app.models.fondo import Fondo
from app.models.usuario import Usuario
from app.schemas.fondo import FondoCreate, FondoRead, FondoUpdate


router = APIRouter(prefix="/fondos", tags=["fondos"])


@router.post("/", response_model=FondoRead, status_code=status.HTTP_201_CREATED)
async def create_fondo(
    payload: FondoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    Crea un nuevo fondo y su CupoGeneral inicial en 0.

    Solo ADMIN_GLOBAL.
    """
    # Validar que el NIT no exista
    result = await db.execute(select(Fondo).where(Fondo.nit == payload.nit))
    existing = result.scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un fondo con ese NIT.",
        )

    fondo = Fondo(
        nombre=payload.nombre,
        nit=payload.nit,
        estado=True,
        activo=True,
    )
    db.add(fondo)
    await db.flush()  # para obtener id_fondo

    cupo_general = CupoGeneral(
        id_fondo=fondo.id_fondo,
        valor_total=0.0,
        valor_disponible=0.0,
    )
    db.add(cupo_general)

    await registrar_auditoria(db, current_user, acciones.CREAR_FONDO)
    await db.commit()
    await db.refresh(fondo)
    return fondo


@router.get("/", response_model=list[FondoRead])
async def list_fondos(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR)),
):
    """
    Lista de fondos:

    - Admin Global: ve todos los fondos.
    - Usuario de fondo: solo ve su propio fondo.
    """
    tenant_id = get_tenant_id(current_user)

    query = select(Fondo).where(Fondo.activo.is_(True))
    if tenant_id is not None:
        query = query.where(Fondo.id_fondo == tenant_id)

    result = await db.execute(query)
    fondos = result.scalars().all()
    return fondos


@router.get("/{id_fondo}", response_model=FondoRead)
async def get_fondo(
    id_fondo: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR)),
):
    tenant_id = get_tenant_id(current_user)
    result = await db.execute(select(Fondo).where(Fondo.id_fondo == id_fondo, Fondo.activo.is_(True)))
    fondo = result.scalar_one_or_none()
    if fondo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fondo no encontrado.")
    if tenant_id is not None and fondo.id_fondo != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso a este fondo.")
    return fondo


@router.patch("/{id_fondo}", response_model=FondoRead)
async def update_fondo(
    id_fondo: int,
    payload: FondoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    Actualiza los datos de un fondo (nombre, nit, estado, id_ejecutivo). Solo ADMIN_GLOBAL.
    """

    result = await db.execute(select(Fondo).where(Fondo.id_fondo == id_fondo))
    fondo = result.scalar_one_or_none()
    if fondo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fondo no encontrado.",
        )

    update_data = payload.model_dump(exclude_unset=True)

    id_ejecutivo = update_data.get("id_ejecutivo")
    if "id_ejecutivo" in update_data and id_ejecutivo is not None:
        result_ejecutivo = await db.execute(
            select(Usuario)
            .where(Usuario.id_usuario == id_ejecutivo)
            .options(selectinload(Usuario.rol))
        )
        ejecutivo = result_ejecutivo.scalar_one_or_none()
        if (
            ejecutivo is None
            or ejecutivo.rol is None
            or ejecutivo.rol.nombre_rol != EJECUTIVO_COMERCIAL
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario no existe o no tiene rol de Ejecutivo Comercial.",
            )

    for field, value in update_data.items():
        setattr(fondo, field, value)

    if "id_ejecutivo" in update_data and id_ejecutivo is not None:
        await registrar_auditoria(
            db,
            current_user,
            f"FONDO_EJECUTIVO_ASIGNADO;id_fondo={id_fondo};id_ejecutivo={id_ejecutivo}",
        )

    try:
        await registrar_auditoria(db, current_user, acciones.ACTUALIZAR_FONDO)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    await db.refresh(fondo)
    return fondo


@router.delete("/{id_fondo}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fondo(
    id_fondo: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    """
    Borrado lógico: cambia activo a False. Solo ADMIN_GLOBAL. Registra Auditoria.
    """

    result = await db.execute(select(Fondo).where(Fondo.id_fondo == id_fondo))
    fondo = result.scalar_one_or_none()
    if fondo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fondo no encontrado.",
        )

    if not fondo.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El fondo ya está desactivado.",
        )

    fondo.activo = False
    fondo.fecha_eliminacion = datetime.now(timezone.utc)
    await registrar_auditoria(db, current_user, acciones.ELIMINAR_FONDO)
    await db.commit()

@router.post(
    "/carga-masiva-archivo",
    response_model=FondoCargaMasivaResult,
    status_code=status.HTTP_200_OK,
)
async def carga_masiva_fondos(
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL)),
):
    contenido = await archivo.read()
    try:
        if archivo.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contenido))
        else:
            df = pd.read_excel(io.BytesIO(contenido))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo leer el archivo. Verifica el formato.",
        )

    if "nombre" not in df.columns or "nit" not in df.columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe tener las columnas: nombre y nit.",
        )

    creados = 0
    errores = 0
    detalle_errores = []

    for _, row in df.iterrows():
        nombre = str(row["nombre"]).strip()
        nit = str(row["nit"]).strip()

        if not nombre or not nit:
            errores += 1
            detalle_errores.append(f"Fila vacía: nombre='{nombre}' nit='{nit}'")
            continue

        result = await db.execute(select(Fondo).where(Fondo.nit == nit))
        if result.scalar_one_or_none() is not None:
            errores += 1
            detalle_errores.append(f"NIT duplicado: {nit}")
            continue

        fondo = Fondo(nombre=nombre, nit=nit, estado=True, activo=True)
        db.add(fondo)
        await db.flush()
        cupo = CupoGeneral(
            id_fondo=fondo.id_fondo,
            valor_total=0.0,
            valor_disponible=0.0,
        )
        db.add(cupo)
        creados += 1

    await registrar_auditoria(db, current_user, acciones.CREAR_FONDO)
    await db.commit()

    return FondoCargaMasivaResult(
        creados=creados,
        errores=errores,
        detalle_errores=detalle_errores,
    )