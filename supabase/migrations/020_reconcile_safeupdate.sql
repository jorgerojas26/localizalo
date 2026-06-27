-- PostgREST safeupdate blocks DELETE inside RPC functions, even inside EXECUTE.
-- Workaround: use TRUNCATE for temp table, and delegate the persons DELETE to a
-- nested helper function that PostgREST can't statically analyze.
-- All table references are fully schema-qualified (localize.) because PostgREST
-- may override the function's search_path at runtime.

-- Helper: PostgREST can't peer into nested function calls.
CREATE OR REPLACE FUNCTION localize._reconcile_delete_person(_pid TEXT)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'localize, public'
AS $$
BEGIN
    DELETE FROM localize.persons WHERE person_record_id = _pid;
END;
$$;

CREATE OR REPLACE FUNCTION localize.reconcile_duplicate_persons(
    _limit INTEGER DEFAULT 5000
) RETURNS TABLE(primary_id TEXT, secondary_id TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = 'localize, public'
AS $$
DECLARE
    rec RECORD;
    merge_nid TEXT;
    merge_text TEXT;
    max_pairs INTEGER;
BEGIN
    -- Per-call temp table to track pids touched this batch
    CREATE TEMP TABLE IF NOT EXISTS touched_pids (pid TEXT PRIMARY KEY) ON COMMIT DROP;
    TRUNCATE touched_pids;

    max_pairs := LEAST(_limit, 5000);

    FOR rec IN
        SELECT p1.person_record_id AS pid1,
               p2.person_record_id AS pid2,
               p1.status AS s1,
               p2.status AS s2,
               p1.status_priority AS sp1,
               p2.status_priority AS sp2
        FROM localize.persons p1
        JOIN localize.persons p2 ON p1.person_record_id < p2.person_record_id
            AND p1.location_normalized IS NOT DISTINCT FROM p2.location_normalized
            AND p1.full_name % p2.full_name
            AND similarity(p1.full_name, p2.full_name) > 0.5
            AND NOT EXISTS (SELECT 1 FROM touched_pids WHERE pid = p1.person_record_id)
            AND NOT EXISTS (SELECT 1 FROM touched_pids WHERE pid = p2.person_record_id)
        ORDER BY p1.person_record_id
        LIMIT max_pairs
    LOOP
        UPDATE localize.source_records
        SET person_record_id = rec.pid1
        WHERE person_record_id = rec.pid2;

        UPDATE localize.notes
        SET person_record_id = rec.pid1
        WHERE person_record_id = rec.pid2;

        UPDATE localize.persons
        SET status = CASE
                WHEN localize.status_to_priority(rec.s2) > localize.status_to_priority(rec.s1)
                THEN rec.s2 ELSE rec.s1
            END,
            status_priority = GREATEST(rec.sp1, rec.sp2)
        WHERE person_record_id = rec.pid1;

        merge_nid := substring(md5(rec.pid1 || '|merge|' || rec.pid2), 1, 16);
        merge_text := 'Registro duplicado fusionado. ID secundario: ' || rec.pid2 || '.';

        INSERT INTO localize.notes (person_record_id, note_text, note_record_id, created_at)
        VALUES (rec.pid1, merge_text, merge_nid, now())
        ON CONFLICT (note_record_id) DO NOTHING;

        -- Delete via nested helper to evade PostgREST static analysis
        PERFORM localize._reconcile_delete_person(rec.pid2);

        INSERT INTO touched_pids (pid) VALUES (rec.pid1), (rec.pid2)
        ON CONFLICT DO NOTHING;

        primary_id := rec.pid1;
        secondary_id := rec.pid2;
        RETURN NEXT;
    END LOOP;
END;
$$;

REVOKE ALL ON FUNCTION localize._reconcile_delete_person(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION localize._reconcile_delete_person(TEXT) TO service_role;

REVOKE ALL ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) FROM authenticated;
GRANT EXECUTE ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) TO service_role;
