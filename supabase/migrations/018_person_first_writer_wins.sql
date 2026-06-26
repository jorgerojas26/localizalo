-- Change ON CONFLICT upsert for Person descriptive fields from last-writer-wins
-- (COALESCE(EXCLUDED.field, persons.field)) to first-writer-wins
-- (COALESCE(persons.field, EXCLUDED.field)). Once a non-null value is set by the
-- first source, later sources cannot overwrite it.
-- KEEP the existing status/status_priority priority-based logic.
-- KEEP updated_at = EXCLUDED.updated_at (refresh touch time).

CREATE OR REPLACE FUNCTION localize.atomic_upsert_person(
    _person_record_id TEXT,
    _full_name TEXT,
    _given_name TEXT,
    _family_name TEXT,
    _age INTEGER,
    _last_known_location TEXT,
    _description TEXT,
    _photo_url TEXT,
    _status TEXT,
    _author_name TEXT,
    _phonetic_hash TEXT,
    _location_normalized TEXT,
    _created_at TIMESTAMPTZ,
    _updated_at TIMESTAMPTZ,
    _source_id TEXT,
    _external_id TEXT,
    _source_date TIMESTAMPTZ,
    _contacto TEXT,
    _localizado_por TEXT,
    _localizado_contacto TEXT,
    _localizado_relacion TEXT,
    _localizado_nota TEXT
) RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    INSERT INTO localize.persons (
        person_record_id, full_name, given_name, family_name, age,
        last_known_location, description, photo_url, status, author_name,
        phonetic_hash, location_normalized, created_at, updated_at,
        status_priority
    ) VALUES (
        _person_record_id, _full_name, _given_name, _family_name, _age,
        _last_known_location, _description, _photo_url, _status, _author_name,
        _phonetic_hash, _location_normalized, _created_at, _updated_at,
        localize.status_to_priority(_status)
    )
    ON CONFLICT (person_record_id) DO UPDATE SET
        full_name = COALESCE(persons.full_name, EXCLUDED.full_name),
        given_name = COALESCE(persons.given_name, EXCLUDED.given_name),
        family_name = COALESCE(persons.family_name, EXCLUDED.family_name),
        age = COALESCE(persons.age, EXCLUDED.age),
        last_known_location = COALESCE(persons.last_known_location, EXCLUDED.last_known_location),
        description = COALESCE(persons.description, EXCLUDED.description),
        photo_url = COALESCE(persons.photo_url, EXCLUDED.photo_url),
        status = CASE WHEN localize.status_to_priority(_status) >= persons.status_priority THEN _status ELSE persons.status END,
        status_priority = GREATEST(localize.status_to_priority(_status), persons.status_priority),
        author_name = COALESCE(persons.author_name, EXCLUDED.author_name),
        phonetic_hash = COALESCE(persons.phonetic_hash, EXCLUDED.phonetic_hash),
        location_normalized = COALESCE(persons.location_normalized, EXCLUDED.location_normalized),
        updated_at = EXCLUDED.updated_at;

    INSERT INTO localize.source_records (
        person_record_id, source_id, external_id, source_date,
        contacto, localizado_por, localizado_contacto,
        localizado_relacion, localizado_nota
    ) VALUES (
        _person_record_id, _source_id, _external_id, _source_date,
        _contacto, _localizado_por, _localizado_contacto,
        _localizado_relacion, _localizado_nota
    )
    ON CONFLICT (source_id, external_id) DO UPDATE SET
        person_record_id = EXCLUDED.person_record_id,
        source_date = COALESCE(EXCLUDED.source_date, source_records.source_date),
        contacto = COALESCE(EXCLUDED.contacto, source_records.contacto),
        localizado_por = COALESCE(EXCLUDED.localizado_por, source_records.localizado_por),
        localizado_contacto = COALESCE(EXCLUDED.localizado_contacto, source_records.localizado_contacto),
        localizado_relacion = COALESCE(EXCLUDED.localizado_relacion, source_records.localizado_relacion),
        localizado_nota = COALESCE(EXCLUDED.localizado_nota, source_records.localizado_nota);

    RETURN _person_record_id;
END;
$$;

REVOKE EXECUTE ON FUNCTION localize.atomic_upsert_person(
    TEXT, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT,
    TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ, TEXT, TEXT, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC;

REVOKE EXECUTE ON FUNCTION localize.atomic_upsert_person(
    TEXT, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT,
    TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ, TEXT, TEXT, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT
) FROM authenticated;

GRANT EXECUTE ON FUNCTION localize.atomic_upsert_person(
    TEXT, TEXT, TEXT, TEXT, INTEGER, TEXT, TEXT, TEXT, TEXT, TEXT,
    TEXT, TEXT, TIMESTAMPTZ, TIMESTAMPTZ, TEXT, TEXT, TIMESTAMPTZ,
    TEXT, TEXT, TEXT, TEXT, TEXT
) TO service_role;
