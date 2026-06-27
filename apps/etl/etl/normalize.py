import logging
import re
import unicodedata
from pathlib import Path

import yaml

_LOCATIONS_FILE = Path(__file__).resolve().parent.parent / "locations.yml"

def _load_synonyms() -> dict[str, str]:
    try:
        with open(_LOCATIONS_FILE) as f:
            data = yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as e:
        logging.getLogger(__name__).warning(
            "Could not load %s: %s. No location synonyms active.",
            _LOCATIONS_FILE,
            e,
        )
        return {}
    synonyms = {}
    for canonical, variants in data.get("canonical", {}).items():
        for v in variants:
            synonyms[v] = canonical
        synonyms[canonical] = canonical
    return synonyms

LOCATION_SYNONYMS = _load_synonyms()


def strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def normalize_location(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip().lower()
    s = strip_accents(s)
    s = re.sub(r"\s+", " ", s)
    if s in LOCATION_SYNONYMS:
        return LOCATION_SYNONYMS[s]
    return s
