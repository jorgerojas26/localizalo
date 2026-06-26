#!/usr/bin/env python3
"""Convert fetched JSON lines to PFIF 1.5 XML."""

import json
import sys
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

PFIF_NS = 'http://zesty.ca/pfif/1.5'

def status_pfif(s):
    """Map estado to PFIF status."""
    s = (s or '').strip().lower()
    if s == 'localizado':
        return 'found'
    if s == 'fallecido':
        return 'deceased'
    if s == 'herido':
        return 'injured'
    return 'missing' if s else 'unknown'

def ms_to_iso(ms):
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

def add(p, tag, val):
    if val is not None and val != '':
        e = SubElement(p, f'{{{PFIF_NS}}}{tag}')
        e.text = str(val).strip()

def json_to_pfif(rec):
    p = Element(f'{{{PFIF_NS}}}person')

    add(p, 'person_record_id', rec.get('id'))
    add(p, 'full_name', rec.get('nombre'))
    parts = (rec.get('nombre') or '').strip().split(None, 1)
    if len(parts) > 0:
        add(p, 'given_name', parts[0])
    if len(parts) > 1:
        add(p, 'family_name', parts[1])
    add(p, 'age', rec.get('edad'))
    add(p, 'last_known_location', rec.get('ubicacion'))
    add(p, 'description', rec.get('descripcion'))
    add(p, 'photo_url', rec.get('foto'))
    add(p, 'status', status_pfif(rec.get('estado')))

    add(p, 'source_date', ms_to_iso(rec.get('createdAt')))

    maybe = []
    if rec.get('contacto'):
        maybe.append('Contacto: ' + rec['contacto'])
    if rec.get('localizadoPor'):
        maybe.append('Localizado por: ' + rec['localizadoPor'])
        add(p, 'author_name', rec['localizadoPor'])
    if rec.get('localizadoContacto'):
        maybe.append('Contacto localizador: ' + rec['localizadoContacto'])
    if rec.get('localizadoRelacion'):
        maybe.append('Relación: ' + rec['localizadoRelacion'])
    if rec.get('localizadoNota'):
        maybe.append('Nota: ' + rec['localizadoNota'])
    if maybe:
        add(p, 'other', ' | '.join(maybe))

    return p

def main():
    infile = sys.argv[1] if len(sys.argv) > 1 else '/dev/stdin'

    root = Element(f'{{{PFIF_NS}}}pfif')
    root.set('xmlns:pfif', PFIF_NS)

    with open(infile) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            root.append(json_to_pfif(rec))

    rough = tostring(root, 'utf-8')
    dom = minidom.parseString(rough)
    print(dom.toprettyxml(indent='  '))

if __name__ == '__main__':
    main()
