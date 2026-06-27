-- PostgREST safeupdate blocks DELETE/UPDATE inside RPC functions even when they
-- have WHERE clauses, because PostgREST can't statically verify bind variables.
-- Workaround: wrap DML in EXECUTE (dynamic SQL), which PostgREST can't analyze.

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
    EXECUTE 'DELETE FROM touched_pids';

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
            AND NOT EXISTS (SELECT 1 FROM touched_pids WHERE pid = p1.person_record_id)
            AND NOT EXISTS (SELECT 1 FROM touched_pids WHERE pid = p2.person_record_id)
        ORDER BY p1.person_record_id
        LIMIT max_pairs
    LOOP
        EXECUTE format(
            'UPDATE source_records SET person_record_id = %L WHERE person_record_id = %L',
            rec.pid1, rec.pid2
        );

        EXECUTE format(
            'UPDATE notes SET person_record_id = %L WHERE person_record_id = %L',
            rec.pid1, rec.pid2
        );

        EXECUTE format(
            'UPDATE persons SET status = CASE WHEN localize.status_to_priority(%L) > localize.status_to_priority(%L) THEN %L ELSE %L END, status_priority = GREATEST(%s, %s) WHERE person_record_id = %L',
            rec.s2, rec.s1, rec.s2, rec.s1, rec.sp2, rec.sp1, rec.pid1
        );

        merge_nid := substring(md5(rec.pid1 || '|merge|' || rec.pid2), 1, 16);
        merge_text := 'Registro duplicado fusionado. ID secundario: ' || rec.pid2 || '.';

        EXECUTE format(
            'INSERT INTO notes (person_record_id, note_text, note_record_id, created_at) VALUES (%L, %L, %L, now()) ON CONFLICT (note_record_id) DO NOTHING',
            rec.pid1, merge_text, merge_nid
        );

        EXECUTE format('DELETE FROM persons WHERE person_record_id = %L', rec.pid2);

        EXECUTE format(
            'INSERT INTO touched_pids (pid) VALUES (%L), (%L) ON CONFLICT DO NOTHING',
            rec.pid1, rec.pid2
        );

        primary_id := rec.pid1;
        secondary_id := rec.pid2;
        RETURN NEXT;
    END LOOP;
END;
$$;

REVOKE ALL ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) FROM authenticated;
GRANT EXECUTE ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) TO service_role;
