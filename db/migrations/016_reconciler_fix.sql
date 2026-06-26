-- Fix snapshot+transitivity bug and unbounded loop in reconcile_duplicate_persons.
-- The old code took a single snapshot with LIMIT and iterated; if the snapshot
-- contained pairs (A,B) and (B,C), after merging (A,B) B is deleted, then the
-- (B,C) iteration moves C's source_records to A even though A and C may NOT match.
--
-- Fix: use a temp table touched_pids to prevent the same pid appearing as both
-- primary and secondary in one batch. Each pid can be touched only once per call.
-- The outer while loop in etl/export.py reconcile() retries until empty.

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
    DELETE FROM touched_pids;

    max_pairs := LEAST(_limit, 5000);

    FOR rec IN
        SELECT p1.person_record_id AS pid1,
               p2.person_record_id AS pid2,
               p1.status AS s1,
               p2.status AS s2,
               p1.status_priority AS sp1,
               p2.status_priority AS sp2
        FROM persons p1
        JOIN persons p2 ON p1.person_record_id < p2.person_record_id
            AND p1.location_normalized IS NOT DISTINCT FROM p2.location_normalized
            AND p1.full_name % p2.full_name
            AND similarity(p1.full_name, p2.full_name) > 0.5
            AND p1.person_record_id NOT IN (SELECT pid FROM touched_pids)
            AND p2.person_record_id NOT IN (SELECT pid FROM touched_pids)
        ORDER BY p1.person_record_id
        LIMIT max_pairs
    LOOP
        UPDATE source_records
        SET person_record_id = rec.pid1
        WHERE person_record_id = rec.pid2;

        UPDATE notes
        SET person_record_id = rec.pid1
        WHERE person_record_id = rec.pid2;

        UPDATE persons
        SET status = CASE
                WHEN localize.status_to_priority(rec.s2) > localize.status_to_priority(rec.s1)
                THEN rec.s2 ELSE rec.s1
            END,
            status_priority = GREATEST(rec.sp1, rec.sp2)
        WHERE person_record_id = rec.pid1;

        merge_nid := substring(md5(rec.pid1 || '|merge|' || rec.pid2), 1, 16);
        merge_text := 'Registro duplicado fusionado. ID secundario: ' || rec.pid2 || '.';

        INSERT INTO notes (person_record_id, note_text, note_record_id, created_at)
        VALUES (rec.pid1, merge_text, merge_nid, now())
        ON CONFLICT (note_record_id) DO NOTHING;

        DELETE FROM persons WHERE person_record_id = rec.pid2;

        INSERT INTO touched_pids (pid) VALUES (rec.pid1), (rec.pid2)
        ON CONFLICT DO NOTHING;

        primary_id := rec.pid1;
        secondary_id := rec.pid2;
        RETURN NEXT;
    END LOOP;
END;
$$;

REVOKE ALL ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) FROM authenticated;
GRANT EXECUTE ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) TO service_role;
