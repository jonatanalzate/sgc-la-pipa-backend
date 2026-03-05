BEGIN;

-- 1) Agregar valor 'pendiente' al enum microcupo_estado si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'microcupo_estado'
          AND e.enumlabel = 'pendiente'
    ) THEN
        ALTER TYPE microcupo_estado ADD VALUE 'pendiente';
    END IF;
END
$$;

-- 2) Agregar valor 'denegado' al enum microcupo_estado si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'microcupo_estado'
          AND e.enumlabel = 'denegado'
    ) THEN
        ALTER TYPE microcupo_estado ADD VALUE 'denegado';
    END IF;
END
$$;

-- 3) Renombrar valor 'disponible' -> 'aprobado' si aún existe
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'microcupo_estado'
          AND e.enumlabel = 'disponible'
    ) THEN
        ALTER TYPE microcupo_estado RENAME VALUE 'disponible' TO 'aprobado';
    END IF;
END
$$;

COMMIT;