-- Promote canonical Person status when a secondary Source reports a higher-priority status
-- (deceased > found > injured > missing > unknown).
-- Adds a computed status_priority column and updates both RPC functions.

ALTER TABLE localize.persons ADD COLUMN IF NOT EXISTS status_priority INTEGER NOT NULL DEFAULT 0;

CREATE OR REPLACE FUNCTION localize.status_to_priority(_status TEXT)
RETURNS INTEGER
LANGUAGE sql IMMUTABLE
AS $$
    SELECT CASE _status
        WHEN 'deceased' THEN 4
        WHEN 'found'    THEN 3
        WHEN 'injured'  THEN 2
        WHEN 'missing'  THEN 1
        ELSE 0
    END;
$$;

UPDATE localize.persons SET status_priority = localize.status_to_priority(status);

CREATE INDEX IF NOT EXISTS idx_persons_status_priority ON localize.persons(status_priority);

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
        full_name = COALESCE(EXCLUDED.full_name, persons.full_name),
        given_name = COALESCE(EXCLUDED.given_name, persons.given_name),
        family_name = COALESCE(EXCLUDED.family_name, persons.family_name),
        age = COALESCE(EXCLUDED.age, persons.age),
        last_known_location = COALESCE(EXCLUDED.last_known_location, persons.last_known_location),
        description = COALESCE(EXCLUDED.description, persons.description),
        photo_url = COALESCE(EXCLUDED.photo_url, persons.photo_url),
        status = CASE WHEN localize.status_to_priority(_status) >= persons.status_priority THEN _status ELSE persons.status END,
        status_priority = GREATEST(localize.status_to_priority(_status), persons.status_priority),
        author_name = COALESCE(EXCLUDED.author_name, persons.author_name),
        phonetic_hash = COALESCE(EXCLUDED.phonetic_hash, persons.phonetic_hash),
        location_normalized = COALESCE(EXCLUDED.location_normalized, persons.location_normalized),
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

CREATE OR REPLACE FUNCTION localize.atomic_merge_note(
    _person_record_id TEXT,
    _note_record_id TEXT,
    _note_text TEXT,
    _author_name TEXT,
    _status TEXT,
    _source_date TIMESTAMPTZ,
    _created_at TIMESTAMPTZ,
    _source_id TEXT,
    _external_id TEXT,
    _contacto TEXT,
    _localizado_por TEXT,
    _localizado_contacto TEXT,
    _localizado_relacion TEXT,
    _localizado_nota TEXT
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
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

    INSERT INTO localize.notes (
        person_record_id, note_text, author_name, status, source_date, created_at, note_record_id
    ) VALUES (
        _person_record_id, _note_text, _author_name, _status, _source_date, _created_at, _note_record_id
    )
    ON CONFLICT (note_record_id) DO NOTHING;

    UPDATE localize.persons
    SET status = _status,
        status_priority = localize.status_to_priority(_status),
        updated_at = _created_at
    WHERE person_record_id = _person_record_id
      AND localize.status_to_priority(_status) > persons.status_priority;
END;
$$;
