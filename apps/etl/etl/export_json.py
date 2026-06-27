"""JSON export of canonical persons with embedded notes.

Maps the same fields as the source PFIF contract into a flat JSON array,
where each person object contains a ``notes`` array of its notes.
This doubles as a reference implementation for sources implementing
``GET /pfif``.
"""

import json
from collections import defaultdict
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
        "status": p.get("status"),
        "entry_date": _format_utc_iso(p.get("created_at")),
        "source_date": p.get("source_date"),
        "author_name": p.get("author_name"),
    }


def _note_dict(n: dict) -> dict:
    # Fallback mirrors the calculation in main.py / db.compute_note_record_id
    note_id = n.get("note_record_id") or db.compute_note_record_id(
        n.get("person_record_id", ""), n.get("source_id") or "", n.get("external_id") or ""
    )
    return {
        "note_record_id": note_id,
        "text": n.get("note_text"),
        "author_name": n.get("author_name"),
        "status": n.get("status"),
        "source_date": n.get("source_date"),
    }


def export_json(person_pages, note_pages) -> str:
    """Build a JSON string as a flat array of persons with embedded notes.

    *person_pages* and *note_pages* are iterables of pages (lists of dicts),
    matching the output of ``db.get_all_persons_paged`` / ``db.get_all_notes_paged``.

    Returns a JSON array matching the source PFIF contract format,
    where each person object includes a ``notes`` array.
    """
    # Build lookup: person_record_id -> list of note dicts
    notes_by_person: dict[str, list[dict]] = defaultdict(list)

    for page in note_pages:
        for n in page:
            pid = n.get("person_record_id")
            if pid:
                notes_by_person[pid].append(_note_dict(n))

    persons = []
    for page in person_pages:
        for p in page:
            person = _person_dict(p)
            pid = person["person_record_id"]
            person["notes"] = notes_by_person.get(pid, [])
            persons.append(person)

    return json.dumps(persons, ensure_ascii=False, separators=(",", ":"))
