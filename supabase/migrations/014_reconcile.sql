-- Cross-source reconciliation of duplicate persons created by parallel ingest races.
-- When sources A and B run concurrently, each computes a distinct person_record_id
-- for the same person (typo changes phonetic_hash). This function finds those
-- duplicate pairs and merges the secondary into the primary.

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
BEGIN
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
        ORDER BY p1.person_record_id
        LIMIT _limit
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

        primary_id := rec.pid1;
        secondary_id := rec.pid2;
        RETURN NEXT;
    END LOOP;
END;
$$;

REVOKE ALL ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION localize.reconcile_duplicate_persons(INTEGER) TO service_role;
