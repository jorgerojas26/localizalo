import unicodedata

import Levenshtein
import phonetics

PHONETIC_THRESHOLD = 0.8
NAME_SIMILARITY_THRESHOLD = 0.9


def phonetic_hash(name: str) -> str:
    primary, alternate = phonetics.dmetaphone(name)
    return primary or alternate or ""


def _phonetic_closeness(name_a: str, name_b: str) -> float:
    """Best Levenshtein ratio between any pair of phonetic encodings."""
    meta_a = phonetics.dmetaphone(name_a)
    meta_b = phonetics.dmetaphone(name_b)
    scores = []
    for a in meta_a:
        if not a:
            continue
        for b in meta_b:
            if not b:
                continue
            scores.append(Levenshtein.ratio(a, b))
    return max(scores) if scores else 0.0


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def is_match(name_a: str, name_b: str) -> bool:
    """Two names match if phonetically close and actual strings are similar."""
    if _phonetic_closeness(name_a, name_b) < PHONETIC_THRESHOLD:
        return False
    a = _strip_accents(name_a.strip().lower())
    b = _strip_accents(name_b.strip().lower())
    return Levenshtein.ratio(a, b) >= NAME_SIMILARITY_THRESHOLD
