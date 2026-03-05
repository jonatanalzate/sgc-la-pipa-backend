BEGIN;

-- 1) Renombrar el tipo actual a *_old para poder recrearlo
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_type
        WHERE typname = 'microcupo_estado'
    ) THEN
        ALTER TYPE microcupo_estado RENAME TO microcupo_estado_old;
    END IF;
END
$$;

-- 2) Crear el tipo nuevo con los valores EXACTAMENTE como los espera SQLAlchemy:
--    PENDIENTE, APROBADO, CONSUMIDO, VENCIDO, DENEGADO
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type
        WHERE typname = 'microcupo_estado'
    ) THEN
        CREATE TYPE microcupo_estado AS ENUM (
            'PENDIENTE',
            'APROBADO',
            'CONSUMIDO',
            'VENCIDO',
            'DENEGADO'
        );
    END IF;
END
$$;

-- 3) Pasar la columna a TEXT usando el tipo viejo (si aún existe)
ALTER TABLE microcupos
    ALTER COLUMN estado TYPE text
    USING estado::text;

-- 4) Normalizar los valores actuales a mayúsculas y mapear nombres antiguos

-- 4.1) Normalizar todo a mayúsculas
UPDATE microcupos
SET estado = UPPER(estado);

-- 4.2) Mapear posibles restos de 'DISPONIBLE' a 'APROBADO'
UPDATE microcupos
SET estado = 'APROBADO'
WHERE estado = 'DISPONIBLE';

-- 5) Volver a convertir la columna al nuevo enum microcupo_estado (en mayúsculas)
ALTER TABLE microcupos
    ALTER COLUMN estado TYPE microcupo_estado
    USING estado::microcupo_estado;

-- 6) Limpiar tipos viejos auxiliares si quedaron
DROP TYPE IF EXISTS microcupo_estado_old;
DROP TYPE IF EXISTS microcupo_estado_new;

COMMIT;