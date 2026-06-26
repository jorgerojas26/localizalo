from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SourceRecord:
    external_id: str
    full_name: str
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    age: Optional[int] = None
    last_known_location: Optional[str] = None
    description: Optional[str] = None
    photo_url: Optional[str] = None
    status: str = "unknown"
    source_date: Optional[str] = None
    author_name: Optional[str] = None
    contacto: Optional[str] = None
    localizado_por: Optional[str] = None
    localizado_contacto: Optional[str] = None
    localizado_relacion: Optional[str] = None
    localizado_nota: Optional[str] = None
