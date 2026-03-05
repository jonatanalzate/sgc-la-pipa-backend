-- Migración de campos de trazabilidad
-- PostgreSQL 15

BEGIN;

-- 1. Agregar columnas nuevas si no existen
ALTER TABLE ventas ADD COLUMN IF NOT EXISTS id_asociado INTEGER;
ALTER TABLE ventas ADD COLUMN IF NOT EXISTS id_fondo INTEGER;
ALTER TABLE microcupos ADD COLUMN IF NOT EXISTS id_fondo INTEGER;
ALTER TABLE entregas ADD COLUMN IF NOT EXISTS id_fondo INTEGER;

-- 2. Poblar ventas con id_asociado e id_fondo
UPDATE ventas v
SET id_asociado = a.id_asociado,
    id_fondo = a.id_fondo
FROM microcupos m
JOIN asociados a ON m.id_asociado = a.id_asociado
WHERE v.id_microcupo = m.id_microcupo;

-- 3. Poblar microcupos con id_fondo
UPDATE microcupos m
SET id_fondo = a.id_fondo
FROM asociados a
WHERE m.id_asociado = a.id_asociado;

-- 4. Poblar entregas con id_fondo
UPDATE entregas e
SET id_fondo = a.id_fondo
FROM ventas v
JOIN microcupos m ON v.id_microcupo = m.id_microcupo
JOIN asociados a ON m.id_asociado = a.id_asociado
WHERE e.id_venta = v.id_venta;

-- 5. Agregar constraints NOT NULL después de poblar
ALTER TABLE ventas ALTER COLUMN id_asociado SET NOT NULL;
ALTER TABLE ventas ALTER COLUMN id_fondo SET NOT NULL;
ALTER TABLE microcupos ALTER COLUMN id_fondo SET NOT NULL;
ALTER TABLE entregas ALTER COLUMN id_fondo SET NOT NULL;

COMMIT;

