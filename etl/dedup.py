import hashlib
import unicodedata

import Levenshtein
import phonetics

PHONETIC_THRESHOLD = 0.8
NAME_SIMILARITY_THRESHOLD = 0.9


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def phonetic_hash(name: str) -> str:
    cleaned = _strip_accents(name.strip().lower())
    primary, alternate = phonetics.dmetaphone(cleaned)
    if primary or alternate:
        return primary or alternate
    return hashlib.sha256(name.encode()).hexdigest()[:16]


def _phonetic_closeness(name_a: str, name_b: str) -> float:
    """Best Levenshtein ratio between any pair of phonetic encodings."""
    meta_a = phonetics.dmetaphone(_strip_accents(name_a.strip().lower()))
    meta_b = phonetics.dmetaphone(_strip_accents(name_b.strip().lower()))
    encodings_a = {e for e in meta_a if e}
    encodings_b = {e for e in meta_b if e}
    if not encodings_a or not encodings_b:
        return 0.0
    return max(
        Levenshtein.ratio(ea, eb)
        for ea in encodings_a
        for eb in encodings_b
    )


def is_match(name_a: str, name_b: str) -> bool:
    """Two names match if phonetically close and actual strings are similar."""
    if _phonetic_closeness(name_a, name_b) < PHONETIC_THRESHOLD:
        return False
    a = _strip_accents(name_a.strip().lower())
    b = _strip_accents(name_b.strip().lower())
    return Levenshtein.ratio(a, b) >= NAME_SIMILARITY_THRESHOLD
