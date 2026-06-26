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
        phonetic_hash, location_normalized, created_at, updated_at
    ) VALUES (
        _person_record_id, _full_name, _given_name, _family_name, _age,
        _last_known_location, _description, _photo_url, _status, _author_name,
        _phonetic_hash, _location_normalized, _created_at, _updated_at
    )
    ON CONFLICT (person_record_id) DO UPDATE SET
        full_name = EXCLUDED.full_name,
        given_name = EXCLUDED.given_name,
        family_name = EXCLUDED.family_name,
        age = EXCLUDED.age,
        last_known_location = EXCLUDED.last_known_location,
        description = EXCLUDED.description,
        photo_url = EXCLUDED.photo_url,
        status = EXCLUDED.status,
        author_name = EXCLUDED.author_name,
        phonetic_hash = EXCLUDED.phonetic_hash,
        location_normalized = EXCLUDED.location_normalized,
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
        source_date = EXCLUDED.source_date,
        contacto = EXCLUDED.contacto,
        localizado_por = EXCLUDED.localizado_por,
        localizado_contacto = EXCLUDED.localizado_contacto,
        localizado_relacion = EXCLUDED.localizado_relacion,
        localizado_nota = EXCLUDED.localizado_nota;

    RETURN _person_record_id;
END;
$$;
