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


def _spanish_phonetic_key(name: str) -> str:
    s = _strip_accents(name.strip().lower())
    s = s.replace('á', 'a').replace('é', 'e').replace('í', 'i')
    s = s.replace('ó', 'o').replace('ú', 'u').replace('ü', 'u')
    s = s.replace('ñ', 'ni')
    s = s.replace('ll', 'y')
    s = s.replace('ch', 'x')
    s = s.replace('rr', 'r')
    s = s.replace('h', '')
    s = s.replace('b', 'v')
    s = s.replace('z', 's')
    s = s.replace('c', 's')
    s = s.replace('g', 'j')
    result = []
    prev = None
    for c in s:
        if c != prev:
            result.append(c)
        prev = c
    return ''.join(result)


def _word_encodings(name: str) -> set:
    cleaned = _strip_accents(name.strip().lower())
    encodings = set()
    for word in cleaned.split():
        primary, alternate = phonetics.dmetaphone(word)
        if primary:
            encodings.add(primary)
        if alternate:
            encodings.add(alternate)
    return encodings


def _phonetic_closeness(name_a: str, name_b: str) -> float:
    encodings_a = _word_encodings(name_a)
    encodings_b = _word_encodings(name_b)
    if encodings_a and encodings_b and (encodings_a & encodings_b):
        return 1.0
    spa_a = _spanish_phonetic_key(name_a)
    spa_b = _spanish_phonetic_key(name_b)
    if spa_a and spa_b:
        if spa_a == spa_b:
            return 1.0
        return Levenshtein.ratio(spa_a, spa_b)
    return 0.0


def is_match(name_a: str, name_b: str) -> bool:
    if _phonetic_closeness(name_a, name_b) < PHONETIC_THRESHOLD:
        return False
    a = _strip_accents(name_a.strip().lower())
    b = _strip_accents(name_b.strip().lower())
    if Levenshtein.ratio(a, b) >= NAME_SIMILARITY_THRESHOLD:
        return True
    spa_a = _spanish_phonetic_key(name_a)
    spa_b = _spanish_phonetic_key(name_b)
    return spa_a and spa_b and Levenshtein.ratio(spa_a, spa_b) >= NAME_SIMILARITY_THRESHOLD
