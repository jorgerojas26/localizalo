-- Bulk variant of atomic_upsert_person. Accepts a JSONB array where each
-- element is {"person": {...}, "source_record": {...}}. Performs the same
-- first-writer-wins COALESCE logic as the single-record RPC, but operating on
-- the entire batch in two SQL statements (one for persons, one for source_records).
-- Returns JSONB {count: N}.

CREATE OR REPLACE FUNCTION localize.atomic_bulk_upsert_persons(
    _records JSONB
) RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    _count INTEGER;
BEGIN
    WITH person_data AS (
        SELECT
            r->'person'->>'person_record_id'   AS person_record_id,
            r->'person'->>'full_name'           AS full_name,
            r->'person'->>'given_name'          AS given_name,
            r->'person'->>'family_name'         AS family_name,
            (r->'person'->>'age')::INTEGER      AS age,
            r->'person'->>'last_known_location' AS last_known_location,
            r->'person'->>'description'         AS description,
            r->'person'->>'photo_url'           AS photo_url,
            r->'person'->>'status'              AS status,
            r->'person'->>'author_name'         AS author_name,
            r->'person'->>'phonetic_hash'       AS phonetic_hash,
            r->'person'->>'location_normalized' AS location_normalized,
            (r->'person'->>'created_at')::TIMESTAMPTZ   AS created_at,
            (r->'person'->>'updated_at')::TIMESTAMPTZ   AS updated_at
        FROM jsonb_array_elements(_records) AS r
    )
    INSERT INTO localize.persons (
        person_record_id, full_name, given_name, family_name, age,
        last_known_location, description, photo_url, status, author_name,
        phonetic_hash, location_normalized, created_at, updated_at, status_priority
    )
    SELECT
        person_record_id, full_name, given_name, family_name, age,
        last_known_location, description, photo_url, status, author_name,
        phonetic_hash, location_normalized, created_at, updated_at,
        localize.status_to_priority(status)
    FROM person_data
    ON CONFLICT (person_record_id) DO UPDATE SET
        full_name          = COALESCE(persons.full_name, EXCLUDED.full_name),
        given_name         = COALESCE(persons.given_name, EXCLUDED.given_name),
        family_name        = COALESCE(persons.family_name, EXCLUDED.family_name),
        age                = COALESCE(persons.age, EXCLUDED.age),
        last_known_location = COALESCE(persons.last_known_location, EXCLUDED.last_known_location),
        description        = COALESCE(persons.description, EXCLUDED.description),
        photo_url          = COALESCE(persons.photo_url, EXCLUDED.photo_url),
        status             = CASE
            WHEN localize.status_to_priority(EXCLUDED.status) >= persons.status_priority
            THEN EXCLUDED.status
            ELSE persons.status
        END,
        status_priority    = GREATEST(
            localize.status_to_priority(EXCLUDED.status),
            persons.status_priority
        ),
        author_name        = COALESCE(persons.author_name, EXCLUDED.author_name),
        phonetic_hash      = COALESCE(persons.phonetic_hash, EXCLUDED.phonetic_hash),
        location_normalized = COALESCE(persons.location_normalized, EXCLUDED.location_normalized),
        updated_at         = EXCLUDED.updated_at;

    GET DIAGNOSTICS _count = ROW_COUNT;

    WITH sr_data AS (
        SELECT
            r->'source_record'->>'person_record_id'   AS person_record_id,
            r->'source_record'->>'source_id'           AS source_id,
            r->'source_record'->>'external_id'         AS external_id,
            (r->'source_record'->>'source_date')::TIMESTAMPTZ  AS source_date,
            r->'source_record'->>'contacto'            AS contacto,
            r->'source_record'->>'localizado_por'      AS localizado_por,
            r->'source_record'->>'localizado_contacto' AS localizado_contacto,
            r->'source_record'->>'localizado_relacion' AS localizado_relacion,
            r->'source_record'->>'localizado_nota'     AS localizado_nota
        FROM jsonb_array_elements(_records) AS r
    )
    INSERT INTO localize.source_records (
        person_record_id, source_id, external_id, source_date,
        contacto, localizado_por, localizado_contacto,
        localizado_relacion, localizado_nota
    )
    SELECT
        person_record_id, source_id, external_id, source_date,
        contacto, localizado_por, localizado_contacto,
        localizado_relacion, localizado_nota
    FROM sr_data
    ON CONFLICT (source_id, external_id) DO UPDATE SET
        person_record_id   = EXCLUDED.person_record_id,
        source_date        = COALESCE(EXCLUDED.source_date, source_records.source_date),
        contacto           = COALESCE(EXCLUDED.contacto, source_records.contacto),
        localizado_por     = COALESCE(EXCLUDED.localizado_por, source_records.localizado_por),
        localizado_contacto = COALESCE(EXCLUDED.localizado_contacto, source_records.localizado_contacto),
        localizado_relacion = COALESCE(EXCLUDED.localizado_relacion, source_records.localizado_relacion),
        localizado_nota    = COALESCE(EXCLUDED.localizado_nota, source_records.localizado_nota);

    RETURN jsonb_build_object('persons_upserted', _count);
END;
$$;

-- Security: only service_role can execute
REVOKE EXECUTE ON FUNCTION localize.atomic_bulk_upsert_persons(JSONB) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION localize.atomic_bulk_upsert_persons(JSONB) FROM authenticated;
GRANT EXECUTE ON FUNCTION localize.atomic_bulk_upsert_persons(JSONB) TO service_role;
