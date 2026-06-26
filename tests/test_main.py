import hashlib
import os
import uuid
from unittest.mock import patch, Mock

os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "test-key"


def _mock_db():
    """Returns a mock Supabase client and a state dict."""
    state = {"persons": {}, "source_records": [], "notes": [], "etl_state": {}}

    def _table(name):
        tbl = Mock()

        def select(*cols, **kwargs):
            q = Mock()
            _items = state.get(name, {})
            if isinstance(_items, dict):
                q.execute.return_value.data = list(_items.values())
                q.execute.return_value.count = len(_items)
            else:
                q.execute.return_value.data = list(_items)
                q.execute.return_value.count = len(_items)

            def eq(k, v):
                q2 = Mock()
                items = state.get(name, {})
                if isinstance(items, dict):
                    filtered = [it for it in items.values() if it.get(k) == v]
                else:
                    filtered = [it for it in items if it.get(k) == v]
                q2.execute.return_value.data = filtered
                q2.eq = eq
                q2.limit = Mock(return_value=q2)
                q2.order = Mock(return_value=q2)
                q2.range = Mock(return_value=q2)
                return q2

            q.eq = eq
            q.range = Mock(return_value=q)
            q.limit = Mock(return_value=q)
            q.order = Mock(return_value=q)
            return q

        tbl.select = select

        def insert(items):
            if isinstance(items, list):
                for item in items:
                    _do_insert(name, item)
            else:
                _do_insert(name, items)
            result = Mock()
            result.execute.return_value.data = items if isinstance(items, list) else [items]
            return result

        tbl.insert = insert

        def upsert(items, on_conflict=None):
            if isinstance(items, list):
                for item in items:
                    _do_upsert(name, item, on_conflict)
            else:
                _do_upsert(name, items, on_conflict)
            result = Mock()
            result.execute.return_value.data = items if isinstance(items, list) else [items]
            return result

        tbl.upsert = upsert

        def update(updates):
            q = Mock()
            def eq(k, v):
                if name == "persons":
                    for pid, p in state["persons"].items():
                        if p.get(k) == v:
                            state["persons"][pid].update(updates)
                result = Mock()
                result.execute.return_value.data = [state["persons"].get(v, {})]
                return result
            q.eq = eq
            return q

        tbl.update = update

        return tbl

    def _do_insert(name, item):
        if name == "persons":
            state["persons"][item["person_record_id"]] = dict(item)
        elif name == "source_records":
            state["source_records"].append(dict(item))
        elif name == "notes":
            state["notes"].append(dict(item))
        elif name == "etl_state":
            state["etl_state"][item["source_id"]] = dict(item)

    def _do_upsert(name, item, on_conflict=None):
        if name == "persons":
            pid = item.get("person_record_id")
            if pid and pid in state["persons"]:
                state["persons"][pid].update(item)
            else:
                state["persons"][pid] = dict(item)
        elif name == "source_records":
            existing = None
            for sr in state["source_records"]:
                if sr.get("source_id") == item.get("source_id") and sr.get("external_id") == item.get("external_id"):
                    existing = sr
                    break
            if existing:
                existing.update(item)
            else:
                state["source_records"].append(dict(item))
        elif name == "notes":
            existing = None
            for note in state["notes"]:
                if note.get("note_record_id") == item.get("note_record_id"):
                    existing = note
                    break
            if existing:
                existing.update(item)
            else:
                state["notes"].append(dict(item))
        elif name == "etl_state":
            state["etl_state"][item["source_id"]] = dict(item)

    def rpc(func_name, params):
        result = Mock()
        if func_name == "trigram_match_persons":
            from etl.dedup import is_match as _is_match
            name = params["_name"]
            location = params.get("_location")
            limit = params.get("_limit", 50)
            candidates = []
            for p in state["persons"].values():
                if location is not None and p.get("location_normalized") != location:
                    continue
                if _is_match(name, p["full_name"]):
                    candidates.append(p)
            candidates.sort(key=lambda c: len(c.get("full_name", "")), reverse=True)
            result.execute.return_value.data = candidates[:limit]
        elif func_name == "atomic_upsert_person":
            person = {
                "person_record_id": params["_person_record_id"],
                "full_name": params["_full_name"],
                "given_name": params["_given_name"],
                "family_name": params["_family_name"],
                "age": params["_age"],
                "last_known_location": params["_last_known_location"],
                "description": params["_description"],
                "photo_url": params["_photo_url"],
                "status": params["_status"],
                "author_name": params["_author_name"],
                "phonetic_hash": params["_phonetic_hash"],
                "location_normalized": params["_location_normalized"],
                "created_at": params["_created_at"],
                "updated_at": params["_updated_at"],
            }
            pid = person["person_record_id"]
            if pid in state["persons"]:
                state["persons"][pid].update(person)
            else:
                state["persons"][pid] = person

            source_record = {
                "person_record_id": params["_person_record_id"],
                "source_id": params["_source_id"],
                "external_id": params["_external_id"],
                "source_date": params["_source_date"],
                "contacto": params["_contacto"],
                "localizado_por": params["_localizado_por"],
                "localizado_contacto": params["_localizado_contacto"],
                "localizado_relacion": params["_localizado_relacion"],
                "localizado_nota": params["_localizado_nota"],
            }
            existing_sr = None
            for sr in state["source_records"]:
                if sr.get("source_id") == source_record["source_id"] and sr.get("external_id") == source_record["external_id"]:
                    existing_sr = sr
                    break
            if existing_sr:
                existing_sr.update(source_record)
            else:
                state["source_records"].append(source_record)

            result.execute.return_value.data = [params["_person_record_id"]]
        elif func_name == "atomic_merge_note":
            source_record = {
                "person_record_id": params["_person_record_id"],
                "source_id": params["_source_id"],
                "external_id": params["_external_id"],
                "source_date": params["_source_date"],
                "contacto": params["_contacto"],
                "localizado_por": params["_localizado_por"],
                "localizado_contacto": params["_localizado_contacto"],
                "localizado_relacion": params["_localizado_relacion"],
                "localizado_nota": params["_localizado_nota"],
            }
            existing_sr = None
            for sr in state["source_records"]:
                if sr.get("source_id") == source_record["source_id"] and sr.get("external_id") == source_record["external_id"]:
                    existing_sr = sr
                    break
            if existing_sr:
                existing_sr.update(source_record)
            else:
                state["source_records"].append(source_record)

            note = {
                "person_record_id": params["_person_record_id"],
                "note_text": params["_note_text"],
                "author_name": params["_author_name"],
                "status": params["_status"],
                "source_date": params["_source_date"],
                "created_at": params["_created_at"],
                "note_record_id": params["_note_record_id"],
            }
            state["notes"].append(note)
        return result

    client = Mock()
    client.schema = Mock(return_value=Mock(table=_table))
    client.table = _table
    client.rpc = rpc
    client.storage = Mock()
    client.storage.from_.return_value.upload = Mock()

    return client, state


def _mock_extra(state):
    """Return mock functions for patching db.source_record_exists,
    db.update_etl_state_watermark, and db.compute_note_record_id."""
    sre_mock = Mock(side_effect=lambda c, pid, sid, eid: any(
        sr.get("person_record_id") == pid
        and sr.get("source_id") == sid
        and sr.get("external_id") == eid
        for sr in state["source_records"]
    ))
    water_mock = Mock(side_effect=lambda c, sid, wm, rid: state["etl_state"].update(
        {sid: {"source_id": sid, "last_run": wm, "run_id": rid}}
    ))
    note_id_mock = Mock(side_effect=lambda pid, sid, eid: f"note-{pid}-{sid}-{eid}")
    return sre_mock, water_mock, note_id_mock


def test_first_run_creates_person():
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):
        mock_fetch.return_value = [
            {
                "external_id": "p123",
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
                "contacto": "04121234567",
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        from etl.main import run
        run("desaparecidos-terremoto-api")

    assert len(state["persons"]) == 1
    pid = list(state["persons"].keys())[0]
    assert state["persons"][pid]["full_name"] == "Maria Fernandez"
    assert state["persons"][pid]["status"] == "missing"
    assert state["persons"][pid]["age"] == 30
    assert state["persons"][pid]["last_known_location"] == "Catia La Mar"


def test_second_run_updates_existing():
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):
        mock_fetch.return_value = [
            {
                "external_id": "p123",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": 30,
                "last_known_location": "Catia La Mar",
                "description": "Cabello negro",
                "photo_url": "https://example.com/foto.jpg",
                "status": "found",
                "source_date": "2026-06-25T14:00:00Z",
                "author_name": "Familiar",
                "contacto": "04121234567",
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]

        from etl.main import run
        run("desaparecidos-terremoto-api")
        run("desaparecidos-terremoto-api")

    assert len(state["persons"]) == 1
    pid = list(state["persons"].keys())[0]
    assert state["persons"][pid]["status"] == "found"


def test_deterministic_dedup_person_record_id():
    """Same name+location = same person_record_id -> updated, not duplicated."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):
        mock_fetch.return_value = [
            {
                "external_id": "p1",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": 30,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "missing",
                "source_date": None,
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]

        from etl.main import run
        run("desaparecidos-terremoto-api")

        mock_fetch.return_value = [
            {
                "external_id": "p1",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": 30,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "found",
                "source_date": None,
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]

        run("desaparecidos-terremoto-api")

    assert len(state["persons"]) == 1
    pid = list(state["persons"].keys())[0]
    assert state["persons"][pid]["status"] == "found"
    assert len(state["notes"]) == 0


def test_phonetic_match_with_different_names_same_location():
    """If phonetic hash differs but names are phonetically similar + location match -> merge under one ID."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):
        mock_fetch.return_value = [
            {
                "external_id": "p1",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": None,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "missing",
                "source_date": None,
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        from etl.main import run
        run("desaparecidos-terremoto-api")

        # Same location, typo in name -> different DM key, but is_match > 0.9
        mock_fetch.return_value = [
            {
                "external_id": "p2",
                "full_name": "Maria Fernanez",
                "given_name": "Maria",
                "family_name": "Fernanez",
                "age": None,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "missing",
                "source_date": None,
                "author_name": None,
                "contacto": "04129876543",
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        run("desaparecidos-terremoto-api")

    assert len(state["persons"]) == 1
    pid = list(state["persons"].keys())[0]
    assert len(state["notes"]) == 1
    note = state["notes"][0]
    assert note["person_record_id"] == pid


def test_phonetic_match_no_location_merges():
    """Record without last_known_location merges with existing person by trigram match."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):
        mock_fetch.return_value = [
            {
                "external_id": "p1",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": None,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "missing",
                "source_date": None,
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        from etl.main import run
        run("desaparecidos-terremoto-api")

        mock_fetch.return_value = [
            {
                "external_id": "p2",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": None,
                "last_known_location": None,
                "description": "",
                "photo_url": "",
                "status": "missing",
                "source_date": None,
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        run("desaparecidos-terremoto-api")

    assert len(state["persons"]) == 1
    assert len(state["notes"]) == 1


# --- New tests for bugs #1, #2, #10, #14 ---


def test_watermark_advances_by_max_source_date():
    """Bug #1: Watermark = max(source_date) - 1s, not wall-clock now."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):
        mock_fetch.return_value = [
            {
                "external_id": "p1",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": 30,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "missing",
                "source_date": "2026-06-25T13:58:00Z",
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        from etl.main import run
        run("desaparecidos-terremoto-api")

    # Watermark should be max(source_date) - 1s
    assert "desaparecidos-terremoto-api" in state["etl_state"]
    wm = state["etl_state"]["desaparecidos-terremoto-api"]["last_run"]
    # 2026-06-25T13:58:00Z - 1s = 2026-06-25T13:57:59+00:00
    assert wm == "2026-06-25T13:57:59+00:00"


def test_watermark_multiple_source_dates_uses_max():
    """Bug #1: With records having different source_dates, watermark uses the max."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):
        mock_fetch.return_value = [
            {
                "external_id": "p1",
                "full_name": "Maria Fernandez",
                "last_known_location": "Caracas",
                "source_date": "2026-06-25T10:00:00Z",
                "status": "missing",
            },
            {
                "external_id": "p2",
                "full_name": "Juan Perez",
                "last_known_location": "Valencia",
                "source_date": "2026-06-25T14:30:00Z",
                "status": "missing",
            },
            {
                "external_id": "p3",
                "full_name": "Ana Lopez",
                "last_known_location": "Maracay",
                "source_date": "2026-06-25T12:15:00Z",
                "status": "missing",
            },
        ]
        from etl.main import run
        run("desaparecidos-terremoto-api")

    wm = state["etl_state"]["desaparecidos-terremoto-api"]["last_run"]
    # Max source_date is 2026-06-25T14:30:00Z, minus 1s
    assert wm == "2026-06-25T14:29:59+00:00"


def test_watermark_stays_at_last_run_when_no_valid_source_date():
    """Bug #1: If no records have valid source_date, watermark stays at last_run."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):
        mock_fetch.return_value = [
            {
                "external_id": "p1",
                "full_name": "Maria Fernandez",
                "last_known_location": "Caracas",
                "source_date": None,
                "status": "missing",
            },
            {
                "external_id": "p2",
                "full_name": "Juan Perez",
                "last_known_location": "Valencia",
                "source_date": "invalid-date",
                "status": "missing",
            },
        ]
        from etl.main import run
        run("desaparecidos-terremoto-api")

        # No valid source_dates, so watermark should NOT advance from the default "1970-..."
        # Last_run was "1970-01-01T00:00:00Z", watermark stays at that
        wm = state["etl_state"]["desaparecidos-terremoto-api"]["last_run"]
        assert wm == "1970-01-01T00:00:00Z"


def test_watermark_no_changes_branch_also_uses_source_date():
    """Bug #1: No-changes branch advances to max(source_date), not wall-clock."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):
        # First run: create records so follow-up runs hit 'same source' refresh
        mock_fetch.return_value = [
            {
                "external_id": "p1",
                "full_name": "Maria Fernandez",
                "last_known_location": "Caracas",
                "source_date": "2026-06-25T10:00:00Z",
                "status": "missing",
            },
        ]
        from etl.main import run
        run("desaparecidos-terremoto-api")

        # Second run: same record, no changes (same_source refresh doesn't count as 'change'
        # for the no-changes check if it hits else branch... actually it hits the existing
        # -> same_source -> upsert path which increments stats.updated. So for a true
        # no-changes test we send a record that was already fully processed.
        # Actually, sending the same record again will hit existing -> same_source -> upsert
        # which updates stats.updated=1, so the no-changes branch is NOT taken.
        # To test the no-changes watermark, send 0 records (empty fetch).
        mock_fetch.return_value = []
        run("desaparecidos-terremoto-api")

    # The second run had 0 records -> watermark = last_run (no advance from previous)
    wm = state["etl_state"]["desaparecidos-terremoto-api"]["last_run"]
    # From the first run: max source_date "2026-06-25T10:00:00Z" - 1s
    assert wm == "2026-06-25T09:59:59+00:00"


def test_watermark_not_advanced_on_errors():
    """Bug #1: When errors > 0, watermark is NOT advanced."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):
        mock_fetch.return_value = [
            {
                "external_id": "p_bad",
                "full_name": "",  # Missing full_name will cause error later
                "last_known_location": "Caracas",
                "source_date": "2026-06-25T10:00:00Z",
                "status": "missing",
            },
            {
                "external_id": "p_good",
                "full_name": "Maria Fernandez",
                "last_known_location": "Caracas",
                "source_date": "2026-06-25T10:00:00Z",
                "status": "missing",
            },
        ]
        from etl.main import run

        # We need an error in processing. Force the first record to raise.
        # The record has full_name="" which will cause KeyError in record["full_name"].
        # But sanitize_record in loader.py would have filtered it already...
        # Let's just make a record that passes sanitize but fails on phonetic_hash.
        mock_fetch.return_value = [
            {
                "external_id": "p_bad",
                "full_name": "Some Name",
                "last_known_location": "Caracas",
                "source_date": "2026-06-25T10:00:00Z",
                "status": "missing",
            },
        ]

        # Force an error on the first record by making phonetic_hash raise
        with patch("etl.main.phonetic_hash", side_effect=ValueError("forced error")):
            try:
                run("desaparecidos-terremoto-api")
            except SystemExit:
                pass  # 100% error rate triggers sys.exit(1) — that's fine

    # Watermark should NOT have been set (etl_state remains empty)
    assert "desaparecidos-terremoto-api" not in state["etl_state"]


def test_existing_same_source_refreshes_person():
    """Bug #2: existing + is_match True + same_source -> atomic_upsert_person (refresh)."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):
        # First run: create a person
        mock_fetch.return_value = [
            {
                "external_id": "p1",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": 30,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "missing",
                "source_date": "2026-06-25T10:00:00Z",
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        from etl.main import run
        run("desaparecidos-terremoto-api")

        # Second run: same source, same external_id, updated status
        mock_fetch.return_value = [
            {
                "external_id": "p1",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": 30,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "found",
                "source_date": "2026-06-25T11:00:00Z",
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        run("desaparecidos-terremoto-api")

    # Should still be one person, status updated to "found"
    assert len(state["persons"]) == 1
    pid = list(state["persons"].keys())[0]
    assert state["persons"][pid]["status"] == "found"
    # No notes should have been added (refresh path does not add notes)
    assert len(state["notes"]) == 0


def test_existing_cross_source_merges_as_note():
    """Bug #2: existing + is_match True + cross_source -> atomic_merge_note (no person upsert)."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    # We need two different sources. The loader mock needs get_source to work.
    # We'll patch get_source to return configs with different namespace.
    from etl.main import run

    # First source creates the person
    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id), \
         patch("etl.main.get_source") as mock_get_source:
        mock_get_source.return_value = {
            "id": "source-a",
            "name": "Source A",
            "namespace": "source-a.org",
            "base_url": "https://source-a.example.com",
        }
        mock_fetch.return_value = [
            {
                "external_id": "sa-001",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": 30,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "missing",
                "source_date": "2026-06-25T10:00:00Z",
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        run("source-a")

    # Second source has the same pid (same name+location) but different external_id
    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id), \
         patch("etl.main.get_source") as mock_get_source:
        mock_get_source.return_value = {
            "id": "source-b",
            "name": "Source B",
            "namespace": "source-b.org",
            "base_url": "https://source-b.example.com",
        }
        mock_fetch.return_value = [
            {
                "external_id": "sb-001",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": 30,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "found",
                "source_date": "2026-06-25T12:00:00Z",
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        run("source-b")

    # Only one person should exist (the original from source-a)
    assert len(state["persons"]) == 1
    # A note should have been added for the cross-source merge
    assert len(state["notes"]) == 1
    note = state["notes"][0]
    assert "source-b.org" in note["note_text"]
    # Person should still have "missing" status (not overwritten by source-b)
    pid = list(state["persons"].keys())[0]
    assert state["persons"][pid]["status"] == "missing"


def test_existing_false_positive_pid_discriminator():
    """Bug #2: existing + is_match False -> pid gets -<discriminator> suffix, new person created."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    # We'll patch phonetic_hash to make two different names produce the same
    # hash, creating a pid collision.
    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id), \
         patch("etl.main.phonetic_hash", return_value="collisionhash"):

        # First record
        mock_fetch.return_value = [
            {
                "external_id": "p1",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": 30,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "missing",
                "source_date": "2026-06-25T10:00:00Z",
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        from etl.main import run
        run("desaparecidos-terremoto-api")

    # Check the first person's pid (deterministic from "collisionhash" + location)
    expected_pid_base = hashlib.sha256(
        "collisionhash|catia la mar".encode()
    ).hexdigest()[:16]
    assert expected_pid_base in state["persons"]
    assert state["persons"][expected_pid_base]["full_name"] == "Maria Fernandez"

    # Second record with different name (is_match will be False) but same
    # phonetic_hash patch -> same pid base -> collision
    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id), \
         patch("etl.main.phonetic_hash", return_value="collisionhash"):

        mock_fetch.return_value = [
            {
                "external_id": "p2",
                "full_name": "Jose Lopez",
                "given_name": "Jose",
                "family_name": "Lopez",
                "age": 25,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "missing",
                "source_date": "2026-06-25T11:00:00Z",
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        run("desaparecidos-terremoto-api")

    # Should be 2 persons now (the original + one with discriminator suffix)
    assert len(state["persons"]) == 2

    # The new person should have a suffixed pid
    discriminator = hashlib.sha256(
        "desaparecidos-terremoto-api|p2".encode()
    ).hexdigest()[:8]
    expected_suffixed_pid = f"{expected_pid_base}-{discriminator}"
    assert expected_suffixed_pid in state["persons"]
    assert state["persons"][expected_suffixed_pid]["full_name"] == "Jose Lopez"

    # Original person should be unchanged
    assert state["persons"][expected_pid_base]["full_name"] == "Maria Fernandez"
    assert state["persons"][expected_pid_base]["age"] == 30


def test_no_per_source_pfif_upload():
    """Bug #10: run() does NOT call upload_pfif or export_pfif."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id), \
         patch("etl.main.db.upload_pfif") as mock_upload:

        mock_fetch.return_value = [
            {
                "external_id": "p1",
                "full_name": "Maria Fernandez",
                "given_name": "Maria",
                "family_name": "Fernandez",
                "age": 30,
                "last_known_location": "Catia La Mar",
                "description": "",
                "photo_url": "",
                "status": "missing",
                "source_date": "2026-06-25T10:00:00Z",
                "author_name": None,
                "contacto": None,
                "localizado_por": None,
                "localizado_contacto": None,
                "localizado_relacion": None,
                "localizado_nota": None,
            }
        ]
        from etl.main import run
        run("desaparecidos-terremoto-api")

    mock_upload.assert_not_called()


def test_fetch_runtime_error_does_not_crash_or_advance_watermark():
    """Bug #14: RuntimeError from source_fetch does not crash; watermark NOT advanced."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):

        mock_fetch.side_effect = RuntimeError("Connection refused after page 2")

        from etl.main import run
        run("desaparecidos-terremoto-api")

    # No persons should have been created
    assert len(state["persons"]) == 0
    # Watermark should NOT have been set
    assert "desaparecidos-terremoto-api" not in state["etl_state"]
    # update_etl_state_watermark should not have been called
    water.assert_not_called()


def test_no_changes_branch_with_zero_records():
    """When 0 records are fetched, watermark stays at last_run (no advance)."""
    client, state = _mock_db()
    sre, water, note_id = _mock_extra(state)

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch, \
         patch("etl.main.db.source_record_exists", sre), \
         patch("etl.main.db.update_etl_state_watermark", water), \
         patch("etl.main.db.compute_note_record_id", note_id):

        mock_fetch.return_value = []
        from etl.main import run
        run("desaparecidos-terremoto-api")

    # No records -> watermark stays at default last_run
        assert "desaparecidos-terremoto-api" in state["etl_state"]
        wm = state["etl_state"]["desaparecidos-terremoto-api"]["last_run"]
        assert wm == "1970-01-01T00:00:00Z"
