from etl.sources.loader import load_sources, get_source, list_source_ids


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


def test_list_source_ids():
    ids = list_source_ids()
    assert "desaparecidos-terremoto-api" in ids
