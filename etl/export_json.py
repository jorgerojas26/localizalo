"""JSON export of canonical persons and notes.

Maps the same fields as the PFIF XML export into a flat
``{"persons": [...], "notes": [...]}`` JSON structure.
"""

import json
from datetime import datetime, timezone

from etl import db


def _format_utc_iso(val) -> str | None:
    """Format a datetime or ISO string to YYYY-MM-DDTHH:MM:SSZ."""
    if val is None:
        return None
    if isinstance(val, datetime):
        dt = val
    elif isinstance(val, str):
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
    else:
        return str(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _person_dict(p: dict) -> dict:
    return {
        "person_record_id": p.get("person_record_id"),
        "full_name": p.get("full_name"),
        "given_name": p.get("given_name"),
        "family_name": p.get("family_name"),
        "age": p.get("age"),
        "last_known_location": p.get("last_known_location"),
        "description": p.get("description"),
        "photo_url": p.get("photo_url"),
        "entry_date": _format_utc_iso(p.get("created_at")),
        "author_name": p.get("author_name"),
    }


def _note_dict(n: dict) -> dict:
    # Fallback mirrors the calculation in main.py / db.compute_note_record_id
    note_id = n.get("note_record_id") or db.compute_note_record_id(
        n.get("person_record_id", ""), n.get("source_id") or "", n.get("external_id") or ""
    )
    return {
        "note_record_id": note_id,
        "person_record_id": n.get("person_record_id"),
        "text": n.get("note_text"),
        "author_name": n.get("author_name"),
        "status": n.get("status"),
        "source_date": n.get("source_date"),
    }


def export_json(person_pages, note_pages) -> str:
    """Build a JSON string of all persons and notes.

    *person_pages* and *note_pages* are iterables of pages (lists of dicts),
    matching the output of ``db.get_all_persons_paged`` / ``db.get_all_notes_paged``.
    """
    persons = []
    notes = []

    for page in person_pages:
        for p in page:
            persons.append(_person_dict(p))

    for page in note_pages:
        for n in page:
            notes.append(_note_dict(n))

    return json.dumps(
        {"persons": persons, "notes": notes},
        ensure_ascii=False,
        indent=2,
    )
