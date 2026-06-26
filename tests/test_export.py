from xml.etree.ElementTree import fromstring

from etl.export_pfif import export_pfif


PFIF_NS = "http://zesty.ca/pfif/1.5"


def _ns(tag: str) -> str:
    return f"{{{PFIF_NS}}}{tag}"


def test_export_empty():
    xml = export_pfif([], [])
    assert "<?xml" in xml
    assert "pfif" in xml


def test_export_single_person():
    persons = [
        {
            "person_record_id": "abc123",
            "full_name": "Maria Fernandez",
            "given_name": "Maria",
            "family_name": "Fernandez",
            "status": "missing",
        }
    ]
    xml = export_pfif([persons], [])
    root = fromstring(xml.encode())
    person = root.find(f".//{_ns('person')}")
    assert person is not None
    assert person.find(_ns("person_record_id")).text == "abc123"
    assert person.find(_ns("full_name")).text == "Maria Fernandez"


def test_export_person_with_all_fields():
    persons = [
        {
            "person_record_id": "abc123",
            "full_name": "Maria Fernandez",
            "given_name": "Maria",
            "family_name": "Fernandez",
            "age": 30,
            "last_known_location": "Catia La Mar",
            "description": "Cabello negro",
            "photo_url": "https://example.com/foto.jpg",
            "status": "missing",
            "source_date": "2026-06-25T13:58:00Z",
            "author_name": "Familiar",
        }
    ]
    xml = export_pfif([persons], [])
    root = fromstring(xml.encode())
    p = root.find(f".//{_ns('person')}")
    assert p.find(_ns("age")).text == "30"
    assert p.find(_ns("last_known_location")).text == "Catia La Mar"
    assert p.find(_ns("description")).text == "Cabello negro"
    assert p.find(_ns("photo_url")).text == "https://example.com/foto.jpg"


def test_export_escapes_control_characters():
    """Control characters must be stripped to produce valid XML 1.0."""
    persons = [
        {
            "person_record_id": "abc123",
            "full_name": "Maria Fernandez",
            "description": "Se\x00encuentra\x1Fbien",
        }
    ]
    xml = export_pfif([persons], [])
    assert "\x00" not in xml
    assert "\x1F" not in xml
    assert "encuentra" in xml
    assert "bien" in xml


def test_export_with_note():
    persons = [
        {
            "person_record_id": "abc123",
            "full_name": "Maria Fernandez",
            "given_name": "Maria",
            "family_name": "Fernandez",
            "status": "missing",
        }
    ]
    notes = [
        {
            "person_record_id": "abc123",
            "note_text": "También reportado por Fuente B",
            "author_name": "Fuente B",
            "source_date": "2026-06-25T14:00:00Z",
            "status": "found",
        }
    ]
    xml = export_pfif([persons], [notes])
    root = fromstring(xml.encode())
    note = root.find(f".//{_ns('note')}")
    assert note is not None
    assert note.find(_ns("note_record_id")) is not None
    assert note.find(_ns("text")).text == "También reportado por Fuente B"
