"""
Script para añadir la columna 'activo' a las tablas usuarios, asociados y fondos.

Ejecutar desde la raíz del proyecto:
  python scripts/add_activo_column.py

O dentro del contenedor Docker:
  docker compose exec app python scripts/add_activo_column.py
"""
import asyncio
import os
import sys

# Añadir el directorio raíz al path para importar app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database.config import engine


async def add_activo_columns() -> None:
    """Añade la columna activo a las tablas si no existe."""
    tables = ["usuarios", "asociados", "fondos"]
    async with engine.begin() as conn:
        for table in tables:
            try:
                await conn.execute(text(f"""
                    ALTER TABLE {table}
                    ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE
                """))
                print(f"  Columna 'activo' añadida/verificada en {table}.")
            except Exception as e:
                print(f"  Tabla {table}: {e}")
                raise

    print("Migración completada: columnas 'activo' en usuarios, asociados y fondos.")


if __name__ == "__main__":
    asyncio.run(add_activo_columns())
