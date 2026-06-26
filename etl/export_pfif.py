import hashlib
import io
import re
from datetime import datetime, timezone

from etl import db

PFIF_NS = "http://zesty.ca/pfif/1.5"


_CONTROL_CHARS = re.compile('[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')


def _escape(s: str) -> str:
    s = _CONTROL_CHARS.sub('', s)
    s = s.replace('&', '&amp;')
    s = s.replace('<', '&lt;')
    s = s.replace('>', '&gt;')
    s = s.replace('"', '&quot;')
    s = s.replace("'", '&apos;')
    return s


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


def _add_xml(parts: list, tag: str, val):
    if val is not None and val != "":
        parts.append(f'    <{tag}>{_escape(str(val).strip())}</{tag}>')


def _person_xml(p: dict) -> str:
    parts = ['  <pfif:person>']
    _add_xml(parts, 'pfif:person_record_id', p.get('person_record_id'))
    _add_xml(parts, 'pfif:full_name', p.get('full_name'))
    _add_xml(parts, 'pfif:given_name', p.get('given_name'))
    _add_xml(parts, 'pfif:family_name', p.get('family_name'))
    _add_xml(parts, 'pfif:age', p.get('age'))
    _add_xml(parts, 'pfif:last_known_location', p.get('last_known_location'))
    _add_xml(parts, 'pfif:description', p.get('description'))
    _add_xml(parts, 'pfif:photo_url', p.get('photo_url'))
    _add_xml(parts, 'pfif:entry_date', _format_utc_iso(p.get("created_at")))
    _add_xml(parts, 'pfif:author_name', p.get('author_name'))
    parts.append('  </pfif:person>')
    return '\n'.join(parts)


def _note_xml(n: dict) -> str:
    # Fallback mirrors the calculation in main.py / db.compute_note_record_id
    note_id = n.get("note_record_id") or db.compute_note_record_id(
        n.get("person_record_id", ""), n.get("source_id") or "", n.get("external_id") or ""
    )
    parts = ['  <pfif:note>']
    _add_xml(parts, 'pfif:note_record_id', note_id)
    _add_xml(parts, 'pfif:person_record_id', n.get('person_record_id'))
    _add_xml(parts, 'pfif:text', n.get('note_text'))
    _add_xml(parts, 'pfif:author_name', n.get('author_name'))
    _add_xml(parts, 'pfif:status', n.get('status'))
    _add_xml(parts, 'pfif:source_date', n.get('source_date'))
    parts.append('  </pfif:note>')
    return '\n'.join(parts)


def export_pfif(person_pages, note_pages) -> str:
    buf = io.StringIO()
    buf.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    buf.write(f'<pfif:pfif xmlns:pfif="{PFIF_NS}">\n')

    for page in person_pages:
        for p in page:
            buf.write(_person_xml(p))
            buf.write('\n')

    for page in note_pages:
        for n in page:
            buf.write(_note_xml(n))
            buf.write('\n')

    buf.write('</pfif:pfif>\n')
    return buf.getvalue()
