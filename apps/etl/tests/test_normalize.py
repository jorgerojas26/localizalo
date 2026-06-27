from etl.normalize import normalize_location, strip_accents


def test_strip_accents_removes_diacritics():
    assert strip_accents("María José Fernández") == "Maria Jose Fernandez"


def test_normalize_location_lowercases_and_strips():
    assert normalize_location("  Catia La Mar  ") == "catia la mar"


def test_normalize_location_synonym_catia():
    assert normalize_location("Catita") == "catia la mar"


def test_normalize_location_synonym_catia_lower():
    assert normalize_location("catia") == "catia la mar"


def test_normalize_location_synonym_maxuto():
    assert normalize_location("Maxuto") == "macuto"


def test_normalize_location_partial_match():
    assert normalize_location("Edificio Costa Brava, Los Corales") == "edificio costa brava, los corales"


def test_normalize_location_no_synonym_match():
    assert normalize_location("Some Unknown Place") == "some unknown place"


def test_normalize_location_none():
    assert normalize_location(None) is None


def test_normalize_location_empty():
    assert normalize_location("") is None
