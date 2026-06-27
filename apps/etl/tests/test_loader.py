from etl.sources.loader import load_sources, get_source, list_source_ids, sanitize_record


def test_load_sources_returns_list():
    sources = load_sources()
    assert isinstance(sources, list)
    assert len(sources) > 0


def test_get_source_returns_config():
    src = get_source("desaparecidos-terremoto-api")
    assert src["id"] == "desaparecidos-terremoto-api"
    assert "base_url" in src
    assert "namespace" in src
    assert "name" in src


def test_get_source_unknown():
    from etl.sources.loader import get_source

    try:
        get_source("nonexistent")
        assert False, "Should have raised"
    except ValueError:
        pass


def test_sanitize_record_accepts_valid_iso_date():
    record = {
        "external_id": "p1",
        "full_name": "Test Person",
        "source_date": "2026-06-25T13:58:00Z",
    }
    result = sanitize_record(record)
    assert result is not None
    assert result["source_date"] == "2026-06-25T13:58:00Z"


def test_sanitize_record_rejects_invalid_date():
    record = {
        "external_id": "p1",
        "full_name": "Test Person",
        "source_date": "not-a-date",
    }
    result = sanitize_record(record)
    assert result is not None
    assert result["source_date"] is None


def test_sanitize_record_handles_int_timestamp():
    record = {
        "external_id": "p1",
        "full_name": "Test Person",
        "source_date": 1719700000000,
    }
    result = sanitize_record(record)
    assert result is not None
    assert result["source_date"] is not None


def test_sanitize_record_rejects_invalid_photo_url():
    record = {
        "external_id": "p1",
        "full_name": "Test Person",
        "photo_url": "not-a-url",
    }
    result = sanitize_record(record)
    assert result is not None
    assert result["photo_url"] is None


def test_sanitize_record_none_photo_url_passes():
    record = {
        "external_id": "p1",
        "full_name": "Test Person",
        "photo_url": None,
    }
    result = sanitize_record(record)
    assert result is not None


def test_list_source_ids():
    ids = list_source_ids()
    assert "desaparecidos-terremoto-api" in ids
