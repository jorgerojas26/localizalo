import os

from etl.dedup import is_match

_SCHEMA = "localize"


def get_client():
    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def _tbl(client, name: str):
    return client.schema(_SCHEMA).table(name)


def get_etl_state(client, source_id: str) -> str | None:
    result = (
        _tbl(client, "etl_state")
        .select("last_run")
        .eq("source_id", source_id)
        .execute()
    )
    if result.data:
        return result.data[0].get("last_run")
    return None


def upsert_source_record(client, record: dict) -> None:
    _tbl(client, "source_records").upsert(
        record, on_conflict=["source_id", "external_id"]
    ).execute()


def find_person_by_id(client, person_record_id: str) -> dict | None:
    result = (
        _tbl(client, "persons")
        .select("*")
        .eq("person_record_id", person_record_id)
        .execute()
    )
    return result.data[0] if result.data else None


def find_person_by_phonetic_match(
    client, name: str, location: str
) -> dict | None:
    if location is None:
        return None
    result = (
        _tbl(client, "persons")
        .select("*")
        .eq("location_normalized", location)
        .execute()
    )
    for candidate in result.data or []:
        if is_match(name, candidate["full_name"]):
            return candidate
    return None


def create_person(client, person: dict) -> None:
    _tbl(client, "persons").insert(person).execute()


def atomic_upsert_person(client, person: dict, source_record: dict) -> str:
    result = client.rpc("atomic_upsert_person", {
        "_person_record_id": person["person_record_id"],
        "_full_name": person["full_name"],
        "_given_name": person.get("given_name"),
        "_family_name": person.get("family_name"),
        "_age": person.get("age"),
        "_last_known_location": person.get("last_known_location"),
        "_description": person.get("description"),
        "_photo_url": person.get("photo_url"),
        "_status": person.get("status", "unknown"),
        "_author_name": person.get("author_name"),
        "_phonetic_hash": person.get("phonetic_hash"),
        "_location_normalized": person.get("location_normalized"),
        "_created_at": person.get("created_at"),
        "_updated_at": person.get("updated_at"),
        "_source_id": source_record["source_id"],
        "_external_id": source_record["external_id"],
        "_source_date": source_record.get("source_date"),
        "_contacto": source_record.get("contacto"),
        "_localizado_por": source_record.get("localizado_por"),
        "_localizado_contacto": source_record.get("localizado_contacto"),
        "_localizado_relacion": source_record.get("localizado_relacion"),
        "_localizado_nota": source_record.get("localizado_nota"),
    }).execute()
    return result.data[0] if result.data else None


def update_person(client, person_record_id: str, updates: dict) -> None:
    _tbl(client, "persons").update(updates).eq(
        "person_record_id", person_record_id
    ).execute()


def add_note(client, note: dict) -> None:
    _tbl(client, "notes").upsert(note, on_conflict=["note_record_id"]).execute()


def update_etl_state(client, source_id: str, last_run: str) -> None:
    _tbl(client, "etl_state").upsert(
        {"source_id": source_id, "last_run": last_run},
        on_conflict=["source_id"],
    ).execute()


def update_etl_state_run(client, source_id: str, last_run: str, run_id: str) -> None:
    _tbl(client, "etl_state").upsert(
        {"source_id": source_id, "last_run": last_run, "run_id": run_id},
        on_conflict=["source_id"],
    ).execute()


def get_all_persons_paged(client):
    start = 0
    page_size = 1000
    while True:
        result = (
            _tbl(client, "persons")
            .select("*")
            .range(start, start + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        yield result.data
        if len(result.data) < page_size:
            break
        start += page_size


def get_all_notes_paged(client):
    start = 0
    page_size = 1000
    while True:
        result = (
            _tbl(client, "notes")
            .select("*")
            .range(start, start + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        yield result.data
        if len(result.data) < page_size:
            break
        start += page_size


def get_all_persons(client) -> list[dict]:
    records = []
    for page in get_all_persons_paged(client):
        records.extend(page)
    return records


def get_all_notes(client) -> list[dict]:
    records = []
    for page in get_all_notes_paged(client):
        records.extend(page)
    return records


def count_persons(client) -> int:
    result = _tbl(client, "persons").select("*", count="exact").limit(1).execute()
    return result.count


def count_notes(client) -> int:
    result = _tbl(client, "notes").select("*", count="exact").limit(1).execute()
    return result.count


def upload_pfif(client, xml_content: str, run_id: str) -> None:
    content = xml_content.encode()
    bucket = client.storage.from_("pfif")

    # Versioned export — never overwritten (immutable per run)
    bucket.upload(
        f"exports/export_{run_id}.xml",
        content,
        {"content-type": "application/xml"},
    )

    # Latest symlink — always points to current
    bucket.upload(
        "export.xml",
        content,
        {"content-type": "application/xml", "upsert": "true"},
    )
