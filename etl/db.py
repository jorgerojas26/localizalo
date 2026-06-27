import functools
import hashlib
import os
import time

import httpx

from etl.dedup import is_match

_SCHEMA = "localize"


def get_client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment"
        )
    return create_client(url, key)


def _tbl(client, name: str):
    return client.schema(_SCHEMA).table(name)


def _is_transient(e: Exception) -> bool:
    """Return True if e is a transient network/HTTP error worth retrying."""
    if isinstance(e, (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.RemoteProtocolError,
        httpx.ReadError,
        httpx.WriteError,
    )):
        return True
    if hasattr(e, 'code') and isinstance(e.code, int) and 500 <= e.code < 600:
        return True
    return False


def _retry(max_attempts=3, base_delay=1.0):
    """Retry a Supabase operation on transient errors."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if not _is_transient(e):
                        raise
                    last_error = e
                    if attempt < max_attempts - 1:
                        time.sleep(base_delay * (2 ** attempt))
            raise last_error
        return wrapper
    return decorator


def compute_note_record_id(person_record_id: str, source_id: str, external_id: str) -> str:
    return hashlib.sha256(
        f"{person_record_id}|{source_id}|{external_id}".encode()
    ).hexdigest()[:16]


@_retry()
def ensure_source_exists(client, source_id: str, name: str, namespace: str) -> None:
    _tbl(client, "sources").upsert(
        {"id": source_id, "name": name, "namespace": namespace},
        on_conflict=["id"],
    ).execute()


@_retry()
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


@_retry()
def upsert_source_record(client, record: dict) -> None:
    _tbl(client, "source_records").upsert(
        record, on_conflict=["source_id", "external_id"]
    ).execute()


@_retry()
def source_record_exists(client, person_record_id: str, source_id: str, external_id: str) -> bool:
    result = (
        _tbl(client, "source_records")
        .select("id")
        .eq("person_record_id", person_record_id)
        .eq("source_id", source_id)
        .eq("external_id", external_id)
        .limit(1)
        .execute()
    )
    return bool(result.data)


@_retry()
def find_person_by_id(client, person_record_id: str) -> dict | None:
    result = (
        _tbl(client, "persons")
        .select("*")
        .eq("person_record_id", person_record_id)
        .execute()
    )
    return result.data[0] if result.data else None


@_retry()
def find_person_by_phonetic_match(
    client, name: str, location: str
) -> dict | None:
    from etl.dedup import phonetic_hash
    primary_hash = phonetic_hash(name)

    # Fast path: exact phonetic_hash + same location = very likely match
    result = (
        _tbl(client, "persons")
        .select("*")
        .eq("location_normalized", location)
        .eq("phonetic_hash", primary_hash)
        .execute()
    )
    for candidate in result.data or []:
        if is_match(name, candidate["full_name"]):
            return candidate

    # Trigram-based fuzzy match via server-side RPC
    result = client.schema(_SCHEMA).rpc("trigram_match_persons", {
        "_name": name,
        "_location": location,
        "_limit": 50,
    }).execute()
    for candidate in result.data or []:
        if candidate.get("phonetic_hash") == primary_hash:
            continue  # already checked above
        if is_match(name, candidate["full_name"]):
            return candidate
    return None


@_retry()
def create_person(client, person: dict) -> None:
    _tbl(client, "persons").insert(person).execute()


@_retry()
def atomic_upsert_person(client, person: dict, source_record: dict) -> str:
    result = client.schema(_SCHEMA).rpc("atomic_upsert_person", {
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


@_retry()
def update_person(client, person_record_id: str, updates: dict) -> None:
    _tbl(client, "persons").update(updates).eq(
        "person_record_id", person_record_id
    ).execute()


@_retry()
def add_note(client, note: dict) -> None:
    _tbl(client, "notes").upsert(note, on_conflict=["note_record_id"]).execute()


@_retry()
def atomic_merge_note(client, note: dict, source_record: dict) -> None:
    client.schema(_SCHEMA).rpc("atomic_merge_note", {
        "_person_record_id": note["person_record_id"],
        "_note_record_id": note["note_record_id"],
        "_note_text": note["note_text"],
        "_author_name": note.get("author_name"),
        "_status": note.get("status"),
        "_source_date": note.get("source_date"),
        "_created_at": note.get("created_at"),
        "_source_id": source_record["source_id"],
        "_external_id": source_record["external_id"],
        "_source_date": source_record.get("source_date"),
        "_contacto": source_record.get("contacto"),
        "_localizado_por": source_record.get("localizado_por"),
        "_localizado_contacto": source_record.get("localizado_contacto"),
        "_localizado_relacion": source_record.get("localizado_relacion"),
        "_localizado_nota": source_record.get("localizado_nota"),
    }).execute()


@_retry()
def update_etl_state_run(client, source_id: str, last_run: str, run_id: str) -> None:
    """Deprecated: use update_etl_state_watermark instead."""
    _tbl(client, "etl_state").upsert(
        {"source_id": source_id, "last_run": last_run, "run_id": run_id},
        on_conflict=["source_id"],
    ).execute()


@_retry()
def update_etl_state_watermark(client, source_id: str, watermark: str, run_id: str) -> None:
    _tbl(client, "etl_state").upsert(
        {"source_id": source_id, "last_run": watermark, "run_id": run_id},
        on_conflict=["source_id"],
    ).execute()


@_retry()
def get_all_persons_paged(client):
    start = 0
    page_size = 1000
    while True:
        result = (
            _tbl(client, "persons")
            .select("*")
            .order("person_record_id")
            .range(start, start + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        yield result.data
        if len(result.data) < page_size:
            break
        start += page_size


@_retry()
def get_all_notes_paged(client):
    start = 0
    page_size = 1000
    while True:
        result = (
            _tbl(client, "notes")
            .select("*")
            .order("note_record_id")
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


@_retry()
def count_persons(client) -> int:
    result = _tbl(client, "persons").select("*", count="exact").limit(1).execute()
    return result.count


@_retry()
def count_notes(client) -> int:
    result = _tbl(client, "notes").select("*", count="exact").limit(1).execute()
    return result.count


@_retry()
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
    # NOTE: upsert must be a string "true" because storage3 FileOptions
    #       TypedDict defines it as str (HTTP header x-upsert).
    bucket.upload(
        "export.xml",
        content,
        {"content-type": "application/xml", "upsert": "true"},
    )
