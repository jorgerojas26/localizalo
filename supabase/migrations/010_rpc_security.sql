-- Lock down SECURITY DEFINER RPC functions so the anon key cannot
-- invoke them to INSERT/UPDATE persons, notes, or source_records.
-- Only authenticated users (server-side with service_role) retain execute.
-- Also revoke DML on all tables from the anon role as a defensive belt.

-- 1. Revoke PUBLIC execute on atomic_upsert_person
REVOKE EXECUTE ON FUNCTION localize.atomic_upsert_person(
    TEXT, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT,
    TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ, TEXT, TEXT, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC;

-- 2. Revoke PUBLIC execute on atomic_merge_note
REVOKE EXECUTE ON FUNCTION localize.atomic_merge_note(
    TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC;

-- 3. Grant execute to authenticated (server-side callers) and service_role
GRANT EXECUTE ON FUNCTION localize.atomic_upsert_person(
    TEXT, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT,
    TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ, TEXT, TEXT, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT
) TO authenticated;

GRANT EXECUTE ON FUNCTION localize.atomic_upsert_person(
    TEXT, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT,
    TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ, TEXT, TEXT, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT
) TO service_role;

GRANT EXECUTE ON FUNCTION localize.atomic_merge_note(
    TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) TO authenticated;

GRANT EXECUTE ON FUNCTION localize.atomic_merge_note(
    TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) TO service_role;

-- 4. Revoke DML from anon role on all tables (SELECT remains via RLS policies)
REVOKE INSERT, UPDATE, DELETE ON localize.persons     FROM anon;
REVOKE INSERT, UPDATE, DELETE ON localize.notes       FROM anon;
REVOKE INSERT, UPDATE, DELETE ON localize.source_records FROM anon;
REVOKE INSERT, UPDATE, DELETE ON localize.etl_state   FROM anon;
REVOKE INSERT, UPDATE, DELETE ON localize.sources     FROM anon;
