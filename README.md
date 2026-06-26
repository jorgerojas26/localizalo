# Localizalo.org

Consolida reportes de personas desaparecidas tras el terremoto de Venezuela 2026 desde múltiples fuentes, deduplica usando emparejamiento fonético, y exporta a PFIF 1.5.

## Cómo funciona

1. **Fuentes**: Cada plataforma expone un endpoint `GET /pfif`. El formato preferido es PFIF 1.5 XML (negociado vía `Accept: application/xml`); el ETL también acepta JSON para fuentes legacy (negociado por Content-Type).
2. **ETL**: Un pipeline en Python corre cada 10 minutos vía GitHub Actions. Por cada fuente:
   - Recorre páginas con `updated_after`, `page` y `limit`
   - Normaliza nombres (Double Metaphone) y ubicaciones (sinónimos curados)
   - Deduplica: mismo nombre fonético + misma ubicación → mismo `person_record_id`
    - Phonetic Match: cercanía fonética >= PHONETIC_THRESHOLD (0.8) Y (similitud Levenshtein del nombre >= NAME_SIMILARITY_THRESHOLD (0.9) O similitud Levenshtein de clave fonética española >= 0.9), más ubicación normalizada idéntica -> fusión bajo un person_record_id con nota histórica
3. **Almacenamiento**: Los datos canónicos viven en Supabase (PostgreSQL), schema `localize`.
4. **Exportación**: El job consolidator (`etl/export.py`) ejecuta reconciliación cruzada entre fuentes vía `reconcile_duplicate_persons`, genera el PFIF 1.5 consolidado con todos los registros deduplicados y sus notas históricas, y lo sube a Supabase Storage (`/pfif/export.xml`).

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

Formato preferido: PFIF 1.5 XML. El ETL negocia vía cabecera `Accept: application/xml`; si la fuente responde con `Content-Type: application/json`, el ETL tolera un array JSON plano como formato legacy.

Ejemplo con un solo registro en PFIF 1.5 XML:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<pfif:pfif xmlns:pfif="http://zesty.ca/pfif/1.5">
  <pfif:person>
    <pfif:person_record_id>midominio.com/a1b2c3</pfif:person_record_id>
    <pfif:full_name>María Fernández</pfif:full_name>
    <pfif:given_name>María</pfif:given_name>
    <pfif:family_name>Fernández</pfif:family_name>
    <pfif:age>30</pfif:age>
    <pfif:last_known_location>Catia La Mar</pfif:last_known_location>
    <pfif:description>Cabello negro, ojos marrones</pfif:description>
    <pfif:photo_url>https://tudominio.com/fotos/123.jpg</pfif:photo_url>
    <pfif:status>missing</pfif:status>
    <pfif:source_date>2026-06-25T13:58:00Z</pfif:source_date>
    <pfif:author_name>Familiar</pfif:author_name>
  </pfif:person>
</pfif:pfif>
```

Los campos adicionales (`contacto`, `localizado_por`, etc.) pueden incluirse como elementos `<pfif:contacto>`, etc., o dentro de `<pfif:other>`.

### Paginación

El ETL itera `page=1, 2, 3...` hasta que la respuesta contenga cero registros o menos elementos que `limit`.

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

## Semántica de notas históricas (merges)

Cuando dos registros de diferentes fuentes se consideran la misma persona vía Phonetic Match (cercanía fonética >= PHONETIC_THRESHOLD (0.8), similitud de nombre >= NAME_SIMILARITY_THRESHOLD (0.9) y misma ubicación normalizada), el ETL **no** crea una segunda persona canónica. En su lugar, el registro de la fuente secundaria se almacena como una nota histórica adjunta a la persona canónica existente, siguiendo el formato de `<pfif:note>`.

Cada nota se genera con el siguiente formato (producido por `_build_note_text`):

```
[namespace]: original_id=<external_id>
photo_url=<url>                      (si existe)
nota=<texto>                         (si existe)
```

Ejemplo:

```
[midominio.org]: original_id=midominio.org/a1b2c3
photo_url=https://tudominio.com/fotos/123.jpg
nota=Reportado como localizado en hospital de Valencia
```

### Comportamiento actual

- El campo `status` de la persona canónica **sí** se actualiza cuando una fuente secundaria reporta un estatus de mayor prioridad (deceased > found > injured > missing > unknown), tanto en `atomic_upsert_person` (colisión de person_record_id) como en `atomic_merge_note` (Phonetic Match). El orden de prioridad está definido por `status_to_priority` en la migración 012.
- Si el estatus reportado tiene igual o menor prioridad que el actual, el cambio queda únicamente en la nota histórica y no se propaga al registro canónico.
- Las notas deben tratarse como metadatos de procedencia / auditoría; el consumo de la nota es necesario para conocer estados alternativos reportados por otras fuentes.

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
- **Base de datos**: Supabase (PostgreSQL 15), schema `localize`. Migraciones en `db/migrations/`. Se usará la extensión `pg_trgm` para búsqueda difusa al optimizar el emparejamiento fonético.
- **Orquestación**: GitHub Actions (cron `*/10 * * * *`, matrix por fuente + consolidator)
- **Formato de exportación**: PFIF 1.5

### Seguridad

- Schema `localize` con RLS habilitado.
- Las tablas `persons`, `notes` y `source_records` tienen políticas SELECT público (lectura sin autenticación).
- Todos los RPC de escritura/mezcla (`atomic_upsert_person`, `atomic_merge_note`, `reconcile_duplicate_persons`) son SECURITY DEFINER. Su ejecución está restringida a los roles `authenticated` y `service_role`; los roles `anon` y `public` tienen el execute revocado (migraciones 010, 014).
- El ETL se conecta usando la clave `service_role` (vía `SUPABASE_SERVICE_KEY`) para invocar estos RPC.

