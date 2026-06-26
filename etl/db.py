import os
from datetime import datetime, timezone
from typing import Optional

from etl.dedup import is_match, phonetic_hash

_SCHEMA = "localize"


def get_client():
    from supabase import create_client

    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def _tbl(client, name: str):
    return client.schema(_SCHEMA).table(name)


def get_etl_state(client, source_id: str) -> Optional[str]:
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


def find_person_by_id(client, person_record_id: str) -> Optional[dict]:
    result = (
        _tbl(client, "persons")
        .select("*")
        .eq("person_record_id", person_record_id)
        .execute()
    )
    return result.data[0] if result.data else None


def find_person_by_phonetic_match(
    client, name: str, location: str
) -> Optional[dict]:
    if location is None:
        return None
    ph = phonetic_hash(name)
    result = (
        _tbl(client, "persons")
        .select("*")
        .eq("phonetic_hash", ph)
        .eq("location_normalized", location)
        .execute()
    )
    for candidate in result.data or []:
        if is_match(name, candidate["full_name"]):
            return candidate
    return None


def create_person(client, person: dict) -> None:
    _tbl(client, "persons").insert(person).execute()


def update_person(client, person_record_id: str, updates: dict) -> None:
    _tbl(client, "persons").update(updates).eq(
        "person_record_id", person_record_id
    ).execute()


def add_note(client, note: dict) -> None:
    _tbl(client, "notes").insert(note).execute()


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


def get_all_persons(client) -> list[dict]:
    records = []
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
        records.extend(result.data)
        if len(result.data) < page_size:
            break
        start += page_size
    return records


def get_all_notes(client) -> list[dict]:
    records = []
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
        records.extend(result.data)
        if len(result.data) < page_size:
            break
        start += page_size
    return records


def upload_pfif(client, xml_content: str) -> None:
    client.storage.from_("pfif").upload(
        "export.xml",
        xml_content.encode(),
        {"content-type": "application/xml", "upsert": "true"},
    )
