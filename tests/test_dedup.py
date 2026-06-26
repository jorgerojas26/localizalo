from etl.dedup import phonetic_hash, is_match


def test_phonetic_hash_returns_string():
    h = phonetic_hash("Maria Fernandez")
    assert isinstance(h, str)
    assert len(h) > 0


def test_phonetic_hash_deterministic():
    assert phonetic_hash("Maria Fernandez") == phonetic_hash("Maria Fernandez")


def test_phonetic_hash_same_for_accents():
    a = phonetic_hash("Maria Fernandez")
    b = phonetic_hash("María Fernández")
    assert a == b


def test_is_match_same_name():
    assert is_match("Maria Fernandez", "Maria Fernandez") is True


def test_is_match_with_accents():
    assert is_match("Maria Fernandez", "María Fernández") is True


def test_is_match_typo():
    assert is_match("Maria Fernandez", "Maria Fernanez") is True


def test_is_match_different_names():
    assert is_match("Maria Fernandez", "Juan Perez") is False
