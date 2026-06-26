# Localizalo.org

Consolida reportes de personas desaparecidas tras el terremoto de Venezuela 2026 desde múltiples fuentes, deduplica usando emparejamiento fonético, y exporta a PFIF 1.5.

## Cómo funciona

1. **Fuentes**: Cada plataforma expone un endpoint `GET /pfif` que devuelve JSON con sus reportes.
2. **ETL**: Un pipeline en Python corre cada 10 minutos vía GitHub Actions. Por cada fuente:
   - Recorre páginas con `updated_after`, `page` y `limit`
   - Normaliza nombres (Double Metaphone) y ubicaciones (sinónimos curados)
   - Deduplica: mismo nombre fonético + misma ubicación → mismo `person_record_id`
   - Si la similitud fonética es >90 % y la ubicación coincide, fusiona automáticamente bajo un mismo ID y agrega los datos de la fuente secundaria como nota histórica
3. **Almacenamiento**: Los datos canónicos viven en Supabase (PostgreSQL), schema `localize`.
4. **Exportación**: Cada ciclo genera PFIF 1.5 consolidado y lo sube a Supabase Storage (`/pfif/export.xml`).

## Cómo ser una fuente

Implementa un endpoint HTTP público con esta firma:

```
GET /pfif?updated_after=<ISO 8601>&page=<int>&limit=<int>
```

### Parámetros

| Parámetro | Tipo | Descripción |
|---|---|---|
| `updated_after` | string (ISO 8601) | **Requerido.** Solo devuelve registros actualizados después de esta fecha. Para backfill el ETL pasa `1970-01-01T00:00:00Z`. |
| `page` | int | **Requerido.** Número de página (empieza en 1). |
| `limit` | int | **Requerido.** Máximo de registros por página. |

### Respuesta

Array JSON plano. Ejemplo:

```json
[
  {
    "external_id": "midominio.com/a1b2c3",
    "full_name": "María Fernández",
    "given_name": "María",
    "family_name": "Fernández",
    "age": 30,
    "last_known_location": "Catia La Mar",
    "description": "Cabello negro, ojos marrones",
    "photo_url": "https://tudominio.com/fotos/123.jpg",
    "status": "missing",
    "source_date": "2026-06-25T13:58:00Z",
    "author_name": "Familiar",
    "contacto": "+58 412-1234567",
    "localizado_por": null,
    "localizado_contacto": null,
    "localizado_relacion": null,
    "localizado_nota": null
  }
]
```

### Paginación

El ETL itera `page=1, 2, 3...` hasta que el array devuelto esté vacío o tenga menos elementos que `limit`.

### Campo `status`

| Valor | Significado |
|---|---|
| `missing` | Desaparecido, sin noticias |
| `found` | Localizado sano y salvo |
| `deceased` | Fallecido |
| `injured` | Herido / en hospital |
| `unknown` | Estado desconocido |

### Requisitos técnicos

- **CORS**: El endpoint debe ser accesible desde GitHub Actions (cualquier User-Agent).
- **Tiempo de respuesta**: Preferiblemente <5s para una página de 100 registros.
- **Ordenamiento**: Los registros deben devolverse ordenados por `updatedAt` ascendente, para que `updated_after` funcione correctamente.

## Registrarse como fuente

Haz un PR a este repositorio agregando tu fuente en [`sources.yml`](./sources.yml):

```yaml
sources:
  - id: mi-plataforma
    name: Mi Plataforma
    namespace: miplataforma.org
    base_url: https://api.miplataforma.org
```

| Campo | Descripción |
|---|---|
| `id` | Identificador único (guiones, sin espacios). Se usa en la matriz de GitHub Actions. |
| `name` | Nombre legible para humanos. |
| `namespace` | Dominio o prefijo para identificar tus registros en notas históricas. |
| `base_url` | URL raíz de tu API. El ETL llama a `{base_url}/pfif?updated_after=&page=&limit=`. |

Además, agrega tu `id` al array `matrix.source` en [`.github/workflows/etl.yml`](./.github/workflows/etl.yml).

Eso es todo. No necesitas escribir código Python ni entender el ETL.

## Cómo consumir los datos

Cada ciclo el ETL genera un archivo PFIF 1.5 consolidado con todos los registros deduplicados y sus notas históricas. Las organizaciones humanitarias (Cruz Roja, Google Person Finder, etc.) consumen este archivo para integrar los datos en sus plataformas.

La URL de descarga se publicará en este README cuando el sistema esté en producción.

## Migraciones

Las migraciones están en `db/migrations/`. Aplicarlas en orden numérico.

### Con psql

```bash
for f in db/migrations/*.sql; do
  psql "$DATABASE_URL" -f "$f"
done
```

### Con Supabase CLI

```bash
supabase db push
```

## Stack

- **ETL**: Python 3.12 + httpx + phonetics + python-Levenshtein
- **Base de datos**: Supabase (PostgreSQL 15), schema `localize`. Migraciones en `db/migrations/`.
- **Orquestación**: GitHub Actions (cron `*/10 * * * *`, matrix por fuente)
- **Formato de exportación**: PFIF 1.5

