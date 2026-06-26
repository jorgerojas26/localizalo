import hashlib
from datetime import datetime, timezone
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

PFIF_NS = "http://zesty.ca/pfif/1.5"


def _add(parent: Element, tag: str, val: str | int | None) -> None:
    if val is not None and val != "":
        e = SubElement(parent, f"{{{PFIF_NS}}}{tag}")
        e.text = str(val).strip()


def _build_person(p: dict) -> Element:
    el = Element(f"{{{PFIF_NS}}}person")
    _add(el, "person_record_id", p.get("person_record_id"))
    _add(el, "full_name", p.get("full_name"))
    _add(el, "given_name", p.get("given_name"))
    _add(el, "family_name", p.get("family_name"))
    _add(el, "age", p.get("age"))
    _add(el, "last_known_location", p.get("last_known_location"))
    _add(el, "description", p.get("description"))
    _add(el, "photo_url", p.get("photo_url"))
    _add(el, "status", p.get("status"))
    _add(el, "source_date", p.get("source_date"))
    _add(el, "author_name", p.get("author_name"))
    return el


def _build_note(n: dict) -> Element:
    el = Element(f"{{{PFIF_NS}}}note")
    note_id = n.get("note_record_id") or hashlib.sha256(
        f"{n.get('person_record_id', '')}|{n.get('note_text', '')}|{n.get('source_date', '')}".encode()
    ).hexdigest()[:16]
    _add(el, "note_record_id", note_id)
    _add(el, "person_record_id", n.get("person_record_id"))
    _add(el, "text", n.get("note_text"))
    _add(el, "author_name", n.get("author_name"))
    _add(el, "status", n.get("status"))
    _add(el, "source_date", n.get("source_date"))
    return el


def export_pfif(persons: list[dict], notes: list[dict]) -> str:
    root = Element(f"{{{PFIF_NS}}}pfif")
    root.set("xmlns:pfif", PFIF_NS)

    for p in persons:
        root.append(_build_person(p))
    for n in notes:
        root.append(_build_note(n))

    rough = tostring(root, "utf-8")
    dom = minidom.parseString(rough)
    return dom.toprettyxml(indent="  ")
