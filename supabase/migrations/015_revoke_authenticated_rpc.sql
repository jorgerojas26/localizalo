-- Revoke EXECUTE on destructive RPCs from authenticated role.
-- Only service_role (server-side ETL key) may run write/merge RPCs.
-- anon AND authenticated are blocked (RLS already blocks anon DML from
-- migration 010; this closes the SECURITY DEFINER bypass for any logged-in
-- non-service user).
-- trigram_match_persons is a STABLE read-only function and remains accessible.

-- 1. atomic_upsert_person (22 params)
REVOKE EXECUTE ON FUNCTION localize.atomic_upsert_person(
    TEXT, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT,
    TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ, TEXT, TEXT, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT
) FROM authenticated;

-- 2. atomic_merge_note (14 params)
REVOKE EXECUTE ON FUNCTION localize.atomic_merge_note(
    TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) FROM authenticated;

-- 3. reconcile_duplicate_persons (1 INTEGER param)
REVOKE EXECUTE ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) FROM authenticated;

-- 4. Re-grant to service_role to be safe
GRANT EXECUTE ON FUNCTION localize.atomic_upsert_person(
    TEXT, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT,
    TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ, TEXT, TEXT, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT
) TO service_role;

GRANT EXECUTE ON FUNCTION localize.atomic_merge_note(
    TEXT, TEXT, TEXT, TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) TO service_role;

GRANT EXECUTE ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) TO service_role;
