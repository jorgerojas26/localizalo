import sys
from unittest.mock import Mock, patch
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
            "created_at": "2026-06-25T12:00:00Z",
        }
    ]
    xml = export_pfif([persons], [])
    root = fromstring(xml.encode())
    person = root.find(f".//{_ns('person')}")
    assert person is not None
    assert person.find(_ns("person_record_id")).text == "abc123"
    assert person.find(_ns("full_name")).text == "Maria Fernandez"
    assert person.find(_ns("entry_date")).text == "2026-06-25T12:00:00Z"


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
            "created_at": "2026-06-25T13:00:00Z",
        }
    ]
    xml = export_pfif([persons], [])
    root = fromstring(xml.encode())
    p = root.find(f".//{_ns('person')}")
    assert p.find(_ns("age")).text == "30"
    assert p.find(_ns("last_known_location")).text == "Catia La Mar"
    assert p.find(_ns("description")).text == "Cabello negro"
    assert p.find(_ns("photo_url")).text == "https://example.com/foto.jpg"
    assert p.find(_ns("entry_date")).text == "2026-06-25T13:00:00Z"


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


def test_person_xml_no_status():
    """Person element must NOT contain <pfif:status> (status lives on note)."""
    persons = [
        {
            "person_record_id": "abc123",
            "full_name": "Maria Fernandez",
            "status": "missing",
            "created_at": "2026-06-25T12:00:00Z",
        }
    ]
    xml = export_pfif([persons], [])
    root = fromstring(xml.encode())
    p = root.find(f".//{_ns('person')}")
    assert p.find(_ns("status")) is None


def test_person_xml_no_source_date():
    """Person element must NOT contain <pfif:source_date> (persons table has no source_date)."""
    persons = [
        {
            "person_record_id": "abc123",
            "full_name": "Maria Fernandez",
            "source_date": "2026-06-25T13:58:00Z",
            "created_at": "2026-06-25T12:00:00Z",
        }
    ]
    xml = export_pfif([persons], [])
    root = fromstring(xml.encode())
    p = root.find(f".//{_ns('person')}")
    assert p.find(_ns("source_date")) is None


def test_person_xml_entry_date_format():
    """entry_date must be UTC ISO-8601 with Z suffix, no microseconds."""
    persons = [
        {
            "person_record_id": "abc123",
            "full_name": "Maria Fernandez",
            "created_at": "2026-06-25T14:30:45.123456+00:00",
        }
    ]
    xml = export_pfif([persons], [])
    assert '<pfif:entry_date>2026-06-25T14:30:45Z</pfif:entry_date>' in xml


def test_note_fallback_three_args():
    """_note_xml fallback calls compute_note_record_id(person_id, source_id, external_id)."""
    from etl.export_pfif import _note_xml

    note = {
        "person_record_id": "pid123",
        "note_text": "test note",
        "source_id": "src1",
        "external_id": "ext1",
    }
    with patch("etl.export_pfif.db.compute_note_record_id", return_value="mocked_id") as mock_fn:
        xml = _note_xml(note)
        mock_fn.assert_called_once_with("pid123", "src1", "ext1")
        assert "mocked_id" in xml


def test_export_round_trip():
    """Full round-trip producing well-formed PFIF XML with persons and notes."""
    persons = [
        {
            "person_record_id": "abc123",
            "full_name": "Maria Fernandez",
            "given_name": "Maria",
            "family_name": "Fernandez",
            "created_at": "2026-06-25T12:00:00Z",
        }
    ]
    notes = [
        {
            "person_record_id": "abc123",
            "note_record_id": "note1",
            "note_text": "Test note",
            "author_name": "Tester",
            "source_id": "src1",
            "external_id": "ext1",
        }
    ]
    xml = export_pfif([persons], [notes])
    root = fromstring(xml.encode())
    assert root.tag == _ns("pfif")
    person_els = root.findall(_ns("person"))
    assert len(person_els) == 1
    note_els = root.findall(_ns("note"))
    assert len(note_els) == 1
    assert person_els[0].find(_ns("entry_date")).text == "2026-06-25T12:00:00Z"
    assert note_els[0].find(_ns("note_record_id")).text == "note1"


def test_export_module_runs_end_to_end_with_mock_db():
    from test_main import _mock_db

    client, state = _mock_db()
    orig_rpc = client.rpc

    def reconciling_rpc(func_name, params):
        if func_name == "reconcile_duplicate_persons":
            result = Mock()
            result.execute.return_value.data = []
            return result
        return orig_rpc(func_name, params)

    client.rpc = reconciling_rpc

    with patch("etl.export.db.get_client", return_value=client), \
         patch("etl.export.db.get_all_persons_paged") as mock_persons_paged, \
         patch("etl.export.db.get_all_notes_paged") as mock_notes_paged, \
         patch("etl.export.db.upload_pfif") as mock_upload, \
         patch("etl.export.db.count_persons", return_value=0), \
         patch("etl.export.db.count_notes", return_value=0), \
         patch("sys.argv", ["etl-export"]):
        mock_persons_paged.return_value = [[]]
        mock_notes_paged.return_value = [[]]

        from etl.export import main
        main()

    mock_upload.assert_called_once()
    xml_arg = mock_upload.call_args[0][1]
    assert "<?xml" in xml_arg
