import os
import uuid
from unittest.mock import patch, Mock

os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "test-key"


def _mock_db():
    """Returns a mock Supabase client and a dict to track state."""
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
                return q2
            
            q.eq = eq
            q.range = Mock(return_value=q)
            q.limit = Mock(return_value=q)
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
        if func_name == "atomic_upsert_person":
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
        return result

    client = Mock()
    client.schema = Mock(return_value=Mock(table=_table))
    client.table = _table
    client.rpc = rpc
    client.storage = Mock()
    client.storage.from_.return_value.upload = Mock()
    return client, state


def test_first_run_creates_person():
    client, state = _mock_db()

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch:
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

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch:
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
    """Same name+location = same person_record_id → updated, not duplicated."""
    client, state = _mock_db()

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch:
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
    """If phonetic hash differs but names are phonetically similar + location match → merge under one ID."""
    client, state = _mock_db()

    with patch("etl.main.db.get_client", return_value=client), \
         patch("etl.main.source_fetch") as mock_fetch:
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

        # Same location, typo in name → different DM key, but is_match > 0.9
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
