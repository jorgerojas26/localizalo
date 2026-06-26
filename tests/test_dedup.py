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


def test_phonetic_hash_spanish_fallback():
    """Names that produce no DM keys fall back to Spanish phonetic key."""
    h = phonetic_hash("W")
    assert isinstance(h, str)
    assert len(h) == 16  # SHA256 hex[:16] length
    # Verify it went through Spanish key path (not raw SHA256)
    import hashlib
    assert h == hashlib.sha256(b"spa:w").hexdigest()[:16]


def test_phonetic_hash_purely_numeric():
    h = phonetic_hash("12345")
    assert isinstance(h, str)
    assert len(h) == 16


def test_phonetic_hash_numeric_name():
    h = phonetic_hash("12345")
    assert isinstance(h, str)
    assert len(h) == 16  # sha256 hex[:16]
    # Two different numeric "names" should get different hashes
    assert phonetic_hash("12345") != phonetic_hash("67890")


def test_is_match_christina_cristina():
    assert is_match("Christina", "Cristina") is True


def test_is_match_jose_josefina():
    assert is_match("Jose", "Josefina") is False


def test_is_match_spanish_bv():
    assert is_match("Victor Blanco", "Bictor Vlanco") is True


def test_is_match_spanish_seseo():
    assert is_match("Cesar", "Sesar") is True


def test_is_match_spanish_ll_y():
    assert is_match("Camilla", "Camiya") is True


def test_is_match_spanish_silent_h():
    assert is_match("Hernandez", "Ernandes") is True


def test_is_match_spanish_different_names():
    assert is_match("Carlos", "Carmen") is False
