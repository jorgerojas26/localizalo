"""
Realistic PFIF 1.5 test data simulating Venezuela 2026 earthquake missing persons.

Two sources with intentional overlap to exercise:
- Same-source refresh (same external_id re-fetched with updated fields)
- Cross-source merge via same person_record_id (same phonetic_hash + location)
- Cross-source merge via trigram phonetic match (different phonetic_hash, close name)
- Phonetic edge cases: accents, ñ→ni, b↔v, s↔z, ll→y, silent h
- Location normalization (synonyms from locations.yml)
- Age handling, status priority, contacto in source_records
- Pagination (20+ records to span multiple pages with limit=5 in tests)

Records are ordered by source_date ascending to simulate chronological reporting.
"""

from datetime import datetime, timezone, timedelta


BASE = datetime(2026, 6, 15, 10, 0, 0, tzinfo=timezone.utc)

# Helper: incremental timestamps 30 minutes apart
def _ts(n: int) -> str:
    return (BASE + timedelta(minutes=30 * n)).isoformat()


# ============================================================
# Source 1: Cruz Roja Venezolana
# ============================================================
CRUZ_ROJA_RECORDS = [
    # 0: Basic person — exercises new person creation
    {
        "person_record_id": "crz-001",
        "entry_date": _ts(0),
        "author_name": "Cruz Roja Caracas",
        "full_name": "María González",
        "given_name": "María",
        "family_name": "González",
        "age": "34",
        "last_known_location": "Caracas",
        "description": "Vista por última vez en el sector San Bernardino.",
        "status": "missing",
        "source_date": _ts(0),
        "other": "Contacto: +58 414-1234567",
    },
    # 1: Full contact info — exercises source_record extra fields
    {
        "person_record_id": "crz-002",
        "entry_date": _ts(1),
        "author_name": "Cruz Roja Valencia",
        "full_name": "José Rodríguez",
        "given_name": "José",
        "family_name": "Rodríguez",
        "age": "45",
        "last_known_location": "Valencia",
        "description": "Desaparecido tras el derrumbe en la Urb. El Viñedo.",
        "photo_url": "https://example.com/fotos/jose_r.jpg",
        "status": "missing",
        "source_date": _ts(1),
        "other": (
            "Contacto: +58 412-9876543"
            " | Localizado por: María Rodríguez"
            " | Contacto localizador: +58 412-1112233"
            " | Relación: Hermana"
        ),
    },
    # 2: Name with ñ — exercises ñ→ni phonetic normalization
    {
        "person_record_id": "crz-003",
        "entry_date": _ts(2),
        "author_name": "Cruz Roja La Guaira",
        "full_name": "Carlos Peña",
        "given_name": "Carlos",
        "family_name": "Peña",
        "age": "28",
        "last_known_location": "La Guaira",
        "description": "Trabajaba en el puerto al momento del sismo.",
        "status": "missing",
        "source_date": _ts(2),
    },
    # 3: Minimal fields — exercises missing optional data path
    {
        "person_record_id": "crz-004",
        "entry_date": _ts(3),
        "author_name": "Cruz Roja Aragua",
        "full_name": "Ana Martínez",
        "given_name": "Ana",
        "family_name": "Martínez",
        "age": "19",
        "last_known_location": "Maracay",
        "status": "missing",
        "source_date": _ts(3),
    },
    # 4: With photo URL
    {
        "person_record_id": "crz-005",
        "entry_date": _ts(4),
        "author_name": "Cruz Roja Lara",
        "full_name": "Luis García",
        "given_name": "Luis",
        "family_name": "García",
        "age": "62",
        "last_known_location": "Barquisimeto",
        "description": "Adulto mayor, movilidad reducida.",
        "photo_url": "https://example.com/fotos/luis_g.jpg",
        "status": "missing",
        "source_date": _ts(4),
    },
    # 5: Child, found status
    {
        "person_record_id": "crz-006",
        "entry_date": _ts(5),
        "author_name": "Cruz Roja Mérida",
        "full_name": "Carmen Hernández",
        "given_name": "Carmen",
        "family_name": "Hernández",
        "age": "8",
        "last_known_location": "Mérida",
        "description": "Encontrada en refugio de la Plaza Bolívar.",
        "status": "found",
        "source_date": _ts(5),
        "other": "Localizado por: Defensa Civil Mérida | Nota: Reunida con sus padres.",
    },
    # 6: Deceased
    {
        "person_record_id": "crz-007",
        "entry_date": _ts(6),
        "author_name": "Cruz Roja Táchira",
        "full_name": "Pedro López",
        "given_name": "Pedro",
        "family_name": "López",
        "age": "55",
        "last_known_location": "San Cristóbal",
        "description": "Fallecido en el colapso del edificio Miranda.",
        "status": "deceased",
        "source_date": _ts(6),
    },
    # 7: With description
    {
        "person_record_id": "crz-008",
        "entry_date": _ts(7),
        "author_name": "Cruz Roja Sucre",
        "full_name": "Rosa Elena Castillo",
        "given_name": "Rosa Elena",
        "family_name": "Castillo",
        "age": "41",
        "last_known_location": "Cumaná",
        "description": "Vestía uniforme azul de enfermera. Cabello negro, 1.65m.",
        "status": "missing",
        "source_date": _ts(7),
    },
    # 8: Injured
    {
        "person_record_id": "crz-009",
        "entry_date": _ts(8),
        "author_name": "Cruz Roja Anzoátegui",
        "full_name": "Juan Carlos Morales",
        "given_name": "Juan Carlos",
        "family_name": "Morales",
        "age": "37",
        "last_known_location": "Puerto La Cruz",
        "description": "Herido en el derrumbe del hospital.",
        "status": "injured",
        "source_date": _ts(8),
    },
    # 9: b/v test for phonetics
    {
        "person_record_id": "crz-010",
        "entry_date": _ts(9),
        "author_name": "Cruz Roja Anzoátegui",
        "full_name": "Beatriz Vargas",
        "given_name": "Beatriz",
        "family_name": "Vargas",
        "age": "26",
        "last_known_location": "Barcelona",
        "description": "Desaparecida cerca del centro comercial.",
        "status": "missing",
        "source_date": _ts(9),
    },
    # 10: ll→y phonetic test
    {
        "person_record_id": "crz-011",
        "entry_date": _ts(10),
        "author_name": "Cruz Roja Miranda",
        "full_name": "Francisco Llano",
        "given_name": "Francisco",
        "family_name": "Llano",
        "age": "50",
        "last_known_location": "Los Teques",
        "description": "Trabajador de la alcaldía.",
        "status": "missing",
        "source_date": _ts(10),
    },
    # 11: s/z/c phonetics + location with synonym (Catia → Catia La Mar)
    {
        "person_record_id": "crz-012",
        "entry_date": _ts(11),
        "author_name": "Cruz Roja Vargas",
        "full_name": "Cecilia Zúñiga",
        "given_name": "Cecilia",
        "family_name": "Zúñiga",
        "age": "22",
        "last_known_location": "Catia La Mar",
        "description": "Estudiante de la UCV, campus Litoral.",
        "status": "missing",
        "source_date": _ts(11),
    },
    # 12: Same person as crz-001 but UPDATED — exercises same-source refresh
    #      Same person_record_id (crz-001), but fields changed: status updated + contacto added
    #      The ETL should detect same source + same external_id → upsert refresh
    {
        "person_record_id": "crz-001",
        "entry_date": _ts(12),
        "author_name": "Cruz Roja Caracas",
        "full_name": "María González",
        "given_name": "María",
        "family_name": "González",
        "age": "34",
        "last_known_location": "Caracas",
        "description": "Encontrada con vida en refugio de Catia. Recibiendo atención médica.",
        "status": "found",
        "source_date": _ts(12),
        "other": "Localizado por: Bomberos Caracas | Nota: Trasladada al Hospital Pérez Carreño.",
    },
    # 13: Another same-source update — same crz-002, different contacto
    {
        "person_record_id": "crz-002",
        "entry_date": _ts(13),
        "author_name": "Cruz Roja Valencia",
        "full_name": "José Rodríguez",
        "given_name": "José",
        "family_name": "Rodríguez",
        "age": "45",
        "last_known_location": "Valencia",
        "description": "Localizado en el hospital central. Condición estable.",
        "photo_url": "https://example.com/fotos/jose_r.jpg",
        "status": "found",
        "source_date": _ts(13),
        "other": (
            "Contacto: +58 414-5550000"
            " | Localizado por: Dr. Andrés Pereira"
            " | Contacto localizador: +58 412-1112233"
            " | Nota: Fractura de pierna, recuperándose."
        ),
    },
    # 14: New person after updates — added later (source_date > previous max)
    {
        "person_record_id": "crz-014",
        "entry_date": _ts(14),
        "author_name": "Cruz Roja Zulia",
        "full_name": "Fernando José Paredes",
        "given_name": "Fernando José",
        "family_name": "Paredes",
        "age": "31",
        "last_known_location": "Maracaibo",
        "description": "Desaparecido en el sector La Limpia.",
        "status": "missing",
        "source_date": _ts(14),
    },
    # 15: Person with same name but different location — should be DIFFERENT person
    {
        "person_record_id": "crz-015",
        "entry_date": _ts(15),
        "author_name": "Cruz Roja Miranda",
        "full_name": "María González",
        "given_name": "María",
        "family_name": "González",
        "age": "29",
        "last_known_location": "Petare",
        "description": "Desaparecida en el barrio José Félix Ribas.",
        "status": "missing",
        "source_date": _ts(15),
    },
]


# ============================================================
# Source 2: Protección Civil Venezuela
# ============================================================
PROTECCION_CIVIL_RECORDS = [
    # 0: Cross-source overlap with crz-001 (María González, Caracas)
    #     Same phonetic_hash + location → same pid → cross-source merge via Path A
    {
        "person_record_id": "pcv-001",
        "entry_date": _ts(16),
        "author_name": "Protección Civil Caracas",
        "full_name": "María González",
        "given_name": "María",
        "family_name": "González",
        "age": "34",
        "last_known_location": "Caracas",
        "description": "Reportada por familiares en la parroquia San Juan.",
        "status": "missing",
        "source_date": _ts(16),
        "other": "Contacto: +58 424-7654321",
    },
    # 1: Cross-source overlap with crz-002 (José Rodríguez, Valencia)
    #     Accent dropped: "José" → phonetic same as "Jose"
    #     Same pid → cross-source merge
    {
        "person_record_id": "pcv-002",
        "entry_date": _ts(17),
        "author_name": "Protección Civil Carabobo",
        "full_name": "Jose Rodríguez",
        "given_name": "Jose",
        "family_name": "Rodríguez",
        "age": "45",
        "last_known_location": "Valencia",
        "description": "Reportado por compañeros de trabajo.",
        "status": "missing",
        "source_date": _ts(17),
    },
    # 2: Cross-source overlap with crz-003 (Carlos Peña, La Guaira)
    #     ñ→n spelling — same phonetic hash
    {
        "person_record_id": "pcv-003",
        "entry_date": _ts(18),
        "author_name": "Protección Civil Vargas",
        "full_name": "Carlos Pena",
        "given_name": "Carlos",
        "family_name": "Pena",
        "age": "28",
        "last_known_location": "La Guaira",
        "description": "Visto por última vez cerca del terminal de pasajeros.",
        "status": "missing",
        "source_date": _ts(18),
    },
    # 3: Cross-source overlap with crz-004 (Ana Martínez, Maracay)
    #     Same name, same location
    {
        "person_record_id": "pcv-004",
        "entry_date": _ts(19),
        "author_name": "Protección Civil Aragua",
        "full_name": "Ana Martínez",
        "given_name": "Ana",
        "family_name": "Martínez",
        "age": "19",
        "last_known_location": "Maracay",
        "description": "Estudiante de la UPEL Maracay.",
        "status": "missing",
        "source_date": _ts(19),
    },
    # 4: Cross-source overlap with crz-010 (Beatriz Vargas, Barcelona)
    #     B/V variation — same phonetic, cross-source merge
    {
        "person_record_id": "pcv-005",
        "entry_date": _ts(20),
        "author_name": "Protección Civil Anzoátegui",
        "full_name": "Beatriz Bargas",
        "given_name": "Beatriz",
        "family_name": "Bargas",
        "age": "26",
        "last_known_location": "Barcelona",
        "description": "Reportada por vecinos del sector El Morro.",
        "status": "missing",
        "source_date": _ts(20),
    },
    # 5: Unique person — exercises new person creation from source 2
    {
        "person_record_id": "pcv-006",
        "entry_date": _ts(21),
        "author_name": "Protección Civil Lara",
        "full_name": "Roberto Silva",
        "given_name": "Roberto",
        "family_name": "Silva",
        "age": "42",
        "last_known_location": "Carora",
        "description": "Comerciante del mercado municipal.",
        "status": "missing",
        "source_date": _ts(21),
    },
    # 6: Unique person
    {
        "person_record_id": "pcv-007",
        "entry_date": _ts(22),
        "author_name": "Protección Civil Falcón",
        "full_name": "Diana Fuentes",
        "given_name": "Diana",
        "family_name": "Fuentes",
        "age": "55",
        "last_known_location": "Punto Fijo",
        "description": "Desaparecida tras el colapso de la refinería.",
        "status": "missing",
        "source_date": _ts(22),
    },
    # 7: Unique person — with accents
    {
        "person_record_id": "pcv-008",
        "entry_date": _ts(23),
        "author_name": "Protección Civil Yaracuy",
        "full_name": "Miguel Ángel Rojas",
        "given_name": "Miguel Ángel",
        "family_name": "Rojas",
        "age": "38",
        "last_known_location": "San Felipe",
        "description": "Bombero voluntario.",
        "photo_url": "https://example.com/fotos/miguel_r.jpg",
        "status": "found",
        "source_date": _ts(23),
        "other": "Localizado por: Cruz Roja Yaracuy | Nota: Ayudando en labores de rescate.",
    },
    # 8: Cross-source overlap with crz-012 (Cecilia Zúñiga, Catia La Mar)
    #     s/z/c variation: "Cecilia Zúñiga" vs "Sesilia Suñiga"
    #     Different phonetic hash → trigram match (Path B)
    {
        "person_record_id": "pcv-009",
        "entry_date": _ts(24),
        "author_name": "Protección Civil Vargas",
        "full_name": "Sesilia Suñiga",
        "given_name": "Sesilia",
        "family_name": "Suñiga",
        "age": "22",
        "last_known_location": "Catia La Mar",
        "description": "Reportada por compañeros de la UCV.",
        "status": "missing",
        "source_date": _ts(24),
    },
    # 9: Unique person
    {
        "person_record_id": "pcv-010",
        "entry_date": _ts(25),
        "author_name": "Protección Civil Monagas",
        "full_name": "Teresa Castillo",
        "given_name": "Teresa",
        "family_name": "Castillo",
        "age": "63",
        "last_known_location": "Maturín",
        "description": "Jubilada, reside en la urbanización Juanico.",
        "status": "missing",
        "source_date": _ts(25),
    },
    # 10: PID collision with crz-005 (Luis García, Barquisimeto, age 62)
    #     "Luis Karkia" produces the same Double Metaphone code as "Luis García"
    #     (dmetaphone → LSKRK for both) but is_match("Luis Karkia", "Luis García")
    #     returns False (Levenshtein ratio ≈ 0.82 < 0.9, spa_key ratio ≈ 0.82 < 0.9).
    #     Same phonetic_hash + same location → same pid → find_person_by_id hits.
    #     is_full_match returns False → Path A1 pid disambiguation → new person created.
    {
        "person_record_id": "pcv-011",
        "entry_date": _ts(26),
        "author_name": "Protección Civil Lara",
        "full_name": "Luis Karkia",
        "given_name": "Luis",
        "family_name": "Karkia",
        "age": "50",
        "last_known_location": "Barquisimeto",
        "description": "Reportado por familiares en el sector La Carucieña.",
        "status": "missing",
        "source_date": _ts(26),
    },
]

# All records keyed by source_id
ALL_RECORDS = {
    "cruz-roja-ve": CRUZ_ROJA_RECORDS,
    "proteccion-civil-ve": PROTECCION_CIVIL_RECORDS,
}
