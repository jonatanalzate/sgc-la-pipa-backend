import io
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import registrar_auditoria
from app.core.dependencies import (
    get_current_user,
    get_tenant_id,
    get_tenant_ids,
    require_roles,
    ensure_fondo_user,
)
from app.core.roles import (
    ADMIN_FONDO,
    ADMIN_GLOBAL,
    EJECUTIVO_COMERCIAL,
    TIENDA_OPERADOR,
    _get_rol_name,
)
from app.core import acciones
from app.database.config import get_db
from app.models.asociado import Asociado
from app.models.usuario import Usuario
from app.schemas.asociado import (
    AsociadoBatchCreate,
    AsociadoBulkUploadResult,
    AsociadoCreate,
    AsociadoRead,
    AsociadoUpdate,
)

MAX_ROWS_BULK_UPLOAD = 10_000
COLS_REQUIRED = {"nombre", "documento"}


router = APIRouter(prefix="/asociados", tags=["asociados"])


@router.get("/", response_model=list[AsociadoRead])
async def list_asociados(
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    rol = _get_rol_name(current_user)
    query = select(Asociado).where(Asociado.activo.is_(True))

    if rol == ADMIN_GLOBAL:
        pass  # sin filtro
    elif rol == TIENDA_OPERADOR:
        if tenant_ids:   # TIENDA_OPERADOR con fondo asignado
            query = query.where(Asociado.id_fondo.in_(tenant_ids))
        # TIENDA_OPERADOR sin fondo → ve todos (comportamiento actual preservado)
    else:
        # ADMIN_FONDO y EJECUTIVO_COMERCIAL
        if tenant_ids:
            query = query.where(Asociado.id_fondo.in_(tenant_ids))

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=AsociadoRead, status_code=status.HTTP_201_CREATED)
async def create_asociado(
    payload: AsociadoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
):
    """
    Crea un asociado individual vinculado al fondo del usuario autenticado.
    """
    tenant_id = ensure_fondo_user(current_user)

    asociado = Asociado(
        nombre=payload.nombre,
        documento=payload.documento,
        estado=True,
        activo=True,
        id_fondo=tenant_id,
    )
    db.add(asociado)
    await registrar_auditoria(db, current_user, acciones.CREAR_ASOCIADO)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un asociado con ese documento en este fondo.",
        )
    await db.refresh(asociado)
    return asociado


@router.get("/{id_asociado}", response_model=AsociadoRead)
async def get_asociado(
    id_asociado: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL, TIENDA_OPERADOR)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    Obtiene el detalle de un asociado.

    - Admin Global: puede ver cualquier asociado.
    - Usuario de fondo: solo asociados de su propio fondo.
    """
    query = select(Asociado).where(Asociado.id_asociado == id_asociado)
    if tenant_ids:
        query = query.where(Asociado.id_fondo.in_(tenant_ids))

    result = await db.execute(query)
    asociado = result.scalar_one_or_none()
    if asociado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asociado no encontrado.",
        )
    return asociado


@router.patch("/{id_asociado}", response_model=AsociadoRead)
async def update_asociado(
    id_asociado: int,
    payload: AsociadoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    Actualización parcial de un asociado (nombre, documento, estado).

    - Admin Global: puede actualizar cualquier asociado.
    - Usuario de fondo: solo asociados de su propio fondo.
    - Registra en Auditoria: ASOCIADO_ACTUALIZADO.
    """
    query = select(Asociado).where(Asociado.id_asociado == id_asociado)
    if tenant_ids:
        query = query.where(Asociado.id_fondo.in_(tenant_ids))

    result = await db.execute(query)
    asociado = result.scalar_one_or_none()
    if asociado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asociado no encontrado.",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if "documento" in update_data:
        existing = await db.execute(
            select(Asociado).where(
                Asociado.documento == update_data["documento"],
                Asociado.id_asociado != id_asociado,
                Asociado.id_fondo == asociado.id_fondo,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe otro asociado con ese documento en el fondo.",
            )

    for field, value in update_data.items():
        setattr(asociado, field, value)

    await registrar_auditoria(db, current_user, acciones.ACTUALIZAR_ASOCIADO)
    await db.commit()
    await db.refresh(asociado)
    return asociado


@router.delete("/{id_asociado}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asociado(
    id_asociado: int,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
    tenant_ids: list[int] = Depends(get_tenant_ids),
):
    """
    Borrado lógico: cambia activo a False. No elimina el registro.

    - Admin Global: puede desactivar cualquier asociado.
    - Usuario de fondo: solo asociados de su propio fondo.
    - Registra en Auditoria.
    """
    query = select(Asociado).where(Asociado.id_asociado == id_asociado)
    if tenant_ids:
        query = query.where(Asociado.id_fondo.in_(tenant_ids))

    result = await db.execute(query)
    asociado = result.scalar_one_or_none()
    if asociado is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asociado no encontrado.",
        )

    if not asociado.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El asociado ya está desactivado.",
        )

    asociado.activo = False
    asociado.fecha_eliminacion = datetime.now(timezone.utc)
    await registrar_auditoria(db, current_user, acciones.ELIMINAR_ASOCIADO)
    await db.commit()


@router.post(
    "/carga-masiva-json",
    response_model=list[AsociadoRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_asociados_batch(
    payload: list[AsociadoBatchCreate],
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
):
    """
    Carga masiva de asociados para el fondo del usuario autenticado.
    """
    tenant_id = ensure_fondo_user(current_user)

    asociados = [
        Asociado(
            nombre=item.nombre,
            documento=item.documento,
            estado=True,
            activo=True,
            id_fondo=tenant_id,
        )
        for item in payload
    ]

    db.add_all(asociados)
    await registrar_auditoria(db, current_user, acciones.CARGA_MASIVA_EXITOSA)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Uno o más documentos ya existen en este fondo.",
        )

    # Refrescar para asegurar que los IDs estén poblados
    for asociado in asociados:
        await db.refresh(asociado)

    return asociados


@router.post(
    "/carga-masiva-archivo",
    response_model=AsociadoBulkUploadResult,
    status_code=status.HTTP_201_CREATED,
)
async def bulk_upload_asociados(
    file: UploadFile = File(..., description="Archivo .xlsx o .csv con columnas nombre y documento"),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_roles(ADMIN_GLOBAL, ADMIN_FONDO, EJECUTIVO_COMERCIAL)),
):
    """
    Carga masiva de asociados desde archivo Excel (.xlsx) o CSV.

    - Columnas obligatorias: nombre, documento (case-insensitive).
    - Valida que el documento no esté duplicado en el mismo fondo.
    - Si una fila tiene error, se salta y se reporta en detalles_errores.
    - Asigna automáticamente el id_fondo del usuario que sube.
    - Registra auditoría "CARGA_MASIVA_EXITOSA" con la cantidad creada.
    """
    tenant_id = ensure_fondo_user(current_user)

    # Validar tipo de archivo
    filename = (file.filename or "").lower()
    if not filename.endswith((".xlsx", ".csv")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se aceptan archivos .xlsx o .csv.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío.",
        )

    try:
        if filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        else:
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8", on_bad_lines="skip")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo leer el archivo: {str(e)}",
        ) from e

    if len(df) > MAX_ROWS_BULK_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El archivo excede el máximo de {MAX_ROWS_BULK_UPLOAD} filas.",
        )

    # Normalizar nombres de columnas (minúsculas, strip)
    df.columns = [str(c).strip().lower() for c in df.columns]

    missing = COLS_REQUIRED - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Faltan columnas obligatorias: {', '.join(sorted(missing))}. Requeridas: nombre, documento.",
        )

    # Obtener documentos existentes en el fondo (solo activos)
    docs_result = await db.execute(
        select(Asociado.documento).where(
            Asociado.id_fondo == tenant_id,
            Asociado.activo.is_(True),
        )
    )
    docs_existentes = {str(r[0]).strip() for r in docs_result.all()}

    creados = 0
    detalles_errores: list[str] = []
    documentos_en_archivo: set[str] = set()

    try:
        for idx, row in df.iterrows():
            fila_num = int(idx) + 2  # Excel: fila 1 = headers, fila 2 = primer dato
            nombre_raw = row.get("nombre")
            documento_raw = row.get("documento")

            # Validar campos obligatorios
            nombre = None if pd.isna(nombre_raw) else str(nombre_raw).strip()
            documento = None if pd.isna(documento_raw) else str(documento_raw).strip()

            if not nombre or not documento:
                detalles_errores.append(
                    f"Fila {fila_num}: nombre y documento son obligatorios."
                )
                continue

            if len(nombre) < 3 or len(nombre) > 150:
                detalles_errores.append(
                    f"Fila {fila_num}: nombre debe tener entre 3 y 150 caracteres."
                )
                continue

            if len(documento) < 3 or len(documento) > 50:
                detalles_errores.append(
                    f"Fila {fila_num}: documento debe tener entre 3 y 50 caracteres."
                )
                continue

            # Duplicado dentro del archivo
            if documento in documentos_en_archivo:
                detalles_errores.append(
                    f"Fila {fila_num}: documento '{documento}' duplicado en el archivo."
                )
                continue

            # Duplicado en el fondo
            if documento in docs_existentes:
                detalles_errores.append(
                    f"Fila {fila_num}: documento '{documento}' ya existe en el fondo."
                )
                continue

            documentos_en_archivo.add(documento)
            docs_existentes.add(documento)

            asociado = Asociado(
                nombre=nombre,
                documento=documento,
                estado=True,
                activo=True,
                id_fondo=tenant_id,
            )
            db.add(asociado)
            await db.flush()
            creados += 1

        if creados > 0:
            await registrar_auditoria(db, current_user, acciones.CARGA_MASIVA_EXITOSA)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return AsociadoBulkUploadResult(
        creados=creados,
        errores=len(detalles_errores),
        detalles_errores=detalles_errores,
    )


