BEGIN;

-- 1) Crear un nuevo tipo enum con los valores correctos (en minúsculas, como en el código)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type
        WHERE typname = 'microcupo_estado_new'
    ) THEN
        CREATE TYPE microcupo_estado_new AS ENUM (
            'pendiente',
            'aprobado',
            'consumido',
            'vencido',
            'denegado'
        );
    END IF;
END
$$;

-- 2) Cambiar temporalmente la columna a text para poder limpiar datos
ALTER TABLE microcupos
    ALTER COLUMN estado TYPE text
    USING estado::text;

-- 3) Normalizar valores viejos a los nuevos esperados por la app
UPDATE microcupos
SET estado = LOWER(estado);

-- 3.1) Asegurarnos de que cualquier variante de 'disponible' pase a 'aprobado'
UPDATE microcupos
SET estado = 'aprobado'
WHERE estado IN ('disponible', 'DISPONIBLE');

-- 4) Volver a convertir la columna al nuevo enum limpio
ALTER TABLE microcupos
    ALTER COLUMN estado TYPE microcupo_estado_new
    USING estado::microcupo_estado_new;

-- 5) Eliminar el tipo viejo y renombrar el nuevo al nombre original
DROP TYPE IF EXISTS microcupo_estado;

ALTER TYPE microcupo_estado_new RENAME TO microcupo_estado;

COMMIT;