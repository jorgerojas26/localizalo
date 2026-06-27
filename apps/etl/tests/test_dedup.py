from etl.dedup import phonetic_hash, is_match, is_full_match


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


def test_spanish_phonetic_key_with_enne():
    """ñ becomes ni in Spanish phonetic key (not stripped to n)."""
    from etl.dedup import _spanish_phonetic_key
    key_munoz = _spanish_phonetic_key("Muñoz")
    key_munioz = _spanish_phonetic_key("Munioz")
    assert key_munoz == key_munioz, f"{key_munoz} != {key_munioz}"
    assert "ni" in key_munoz


def test_is_match_with_enne():
    """Names with ñ match equivalents using ni replacement."""
    assert is_match("Muñoz", "Munioz") is True
    assert is_match("Peña", "Penia") is True


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


def test_is_full_match_same_name_same_age():
    assert is_full_match("Maria Fernandez", "Maria Fernandez", 25, 25) is True


def test_is_full_match_same_name_age_diff_3():
    assert is_full_match("Maria Fernandez", "Maria Fernandez", 25, 28) is False


def test_is_full_match_same_name_age_diff_2():
    assert is_full_match("Maria Fernandez", "Maria Fernandez", 25, 27) is True


def test_is_full_match_same_name_one_age_none():
    assert is_full_match("Maria Fernandez", "Maria Fernandez", 25, None) is True


def test_is_full_match_typo_matching_contacto():
    assert is_full_match("Maria Fernandez", "Maria Fernanez", None, None, "0412-123-4567", "04121234567") is True


def test_is_full_match_same_name_different_contacto():
    assert is_full_match("Maria Fernandez", "Maria Fernandez", None, None, "04121234567", "04129876543") is False


def test_is_full_match_one_contacto_none():
    assert is_full_match("Maria Fernandez", "Maria Fernanez", None, None, "04121234567", None) is True


def test_is_full_match_different_names():
    assert is_full_match("Maria Fernandez", "Juan Perez", 25, 30) is False
