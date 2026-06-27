-- Fix reconcile_duplicate_persons timeout on large datasets.
-- Root cause: NULL location_normalized pairs (IS NOT DISTINCT FROM NULL)
-- produce a massive cross-product that can't use the trigram index efficiently.
-- Fix: exclude NULL locations, use % operator (can leverage GIN index),
-- and lower default batch size to 1000.

CREATE OR REPLACE FUNCTION localize.reconcile_duplicate_persons(
    _limit INTEGER DEFAULT 1000
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
    CREATE TEMP TABLE IF NOT EXISTS touched_pids (pid TEXT PRIMARY KEY) ON COMMIT DROP;
    TRUNCATE touched_pids;

    max_pairs := LEAST(_limit, 1000);

    -- Use pg_trgm % operator which can leverage the GIN trigram index.
    -- Exclude NULL location_normalized — two persons without known
    -- locations cannot be confidently reconciled.
    PERFORM set_config('pg_trgm.similarity_threshold', '0.5', false);

    FOR rec IN
        SELECT p1.person_record_id AS pid1,
               p2.person_record_id AS pid2,
               p1.status AS s1,
               p2.status AS s2,
               p1.status_priority AS sp1,
               p2.status_priority AS sp2
        FROM localize.persons p1
        JOIN localize.persons p2
            ON p1.person_record_id < p2.person_record_id
            AND p1.location_normalized = p2.location_normalized
            AND p1.location_normalized IS NOT NULL
            AND p1.full_name % p2.full_name
        WHERE NOT EXISTS (SELECT 1 FROM touched_pids WHERE pid = p1.person_record_id)
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

        PERFORM localize._reconcile_delete_person(rec.pid2);

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
