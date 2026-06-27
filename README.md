# Localizalo.org

Consolida reportes de personas desaparecidas tras el terremoto de Venezuela 2026 desde múltiples fuentes, deduplica usando emparejamiento fonético, y exporta a PFIF 1.5.

## Cómo funciona

1. **Fuentes**: Cada plataforma expone un endpoint `GET /pfif`. El ETL acepta **XML** (PFIF 1.5) y **JSON** (array de objetos planos) — la fuente elige cuál le queda más fácil. El ETL negocia vía `Accept` y detecta el formato por `Content-Type` de la respuesta.
2. **ETL**: Un pipeline en Python corre cada 10 minutos vía GitHub Actions. Por cada fuente:
   - Recorre páginas con `updated_after`, `offset` y `limit`
   - Normaliza nombres (Double Metaphone) y ubicaciones (sinónimos curados en [`locations.yml`](./locations.yml))
   - Genera `person_record_id` determinístico = `sha256(phonetic_hash | location_normalized)[:16]`
   - Deduplica: mismo `person_record_id` → misma persona canónica; nombres fonéticamente similares + misma ubicación → merge como nota histórica
   - Colisiones de hash (falso positivo): desambigua con sufijo `-<discriminator>` y crea persona separada
3. **Reconciliación**: El job consolidator ejecuta `reconcile_duplicate_persons` (RPC en PostgreSQL) que detecta duplicados creados por carreras de ingesta paralela entre fuentes (typos que cambian el `phonetic_hash`) y fusiona el secundario en el primario.
4. **Almacenamiento**: Los datos canónicos viven en Supabase (PostgreSQL), schema `localize`.
5. **Exportación**: El consolidator genera el PFIF 1.5 unificado con todos los registros deduplicados y sus notas históricas, y lo sube a Supabase Storage como `/pfif/export.xml` (latest) y `/pfif/exports/export_<run_id>.xml` (versionado inmutable).

## Cómo ser una fuente

Implementa un endpoint HTTP público con esta firma:

```
GET /pfif?updated_after=<ISO 8601>&offset=<int>&limit=<int>
```

### Parámetros

| Parámetro | Tipo | Descripción |
|---|---|---|
| `updated_after` | string (ISO 8601) | **Requerido.** Solo devuelve registros actualizados después de esta fecha. Para el backfill inicial el ETL pasa `1970-01-01T00:00:00Z`. |
| `offset` | int | **Requerido.** Desplazamiento de registros (empieza en 0, incrementa de a 1000). |
| `limit` | int | **Requerido.** Máximo de registros por página (el ETL usa 1000). |

### Respuesta

El endpoint debe devolver **XML** o **JSON**. El ETL detecta el formato automáticamente por el `Content-Type` de la respuesta.

#### Opción A — PFIF 1.5 XML

`Content-Type: application/xml`

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

#### Opción B — JSON

`Content-Type: application/json`

Devuelves un array de objetos planos. Las llaves son las mismas que en XML, sin prefijo `pfif:`.

```json
[
  {
    "person_record_id": "midominio.com/a1b2c3",
    "full_name": "María Fernández",
    "given_name": "María",
    "family_name": "Fernández",
    "age": 30,
    "last_known_location": "Catia La Mar",
    "description": "Cabello negro, ojos marrones",
    "photo_url": "https://tudominio.com/fotos/123.jpg",
    "status": "missing",
    "source_date": "2026-06-25T13:58:00Z",
    "author_name": "Familiar"
  }
]
```

En ambos formatos, los campos `contacto`, `localizado_por`, `localizado_contacto`, `localizado_relacion` y `localizado_nota` son opcionales y se aceptan como campos extra.

En XML, los campos extra pueden ir como `<pfif:contacto>`, `<pfif:localizado_por>`, etc., o dentro de `<pfif:other>` con formato `Clave: valor | Clave: valor`.

### Paginación

El ETL itera `offset=0, 1000, 2000...` hasta recibir una respuesta con menos de `limit` registros. La respuesta vacía (`[]`) también termina la iteración. Entre páginas se aplica un `rate_limit_ms` configurable por fuente (default 100ms).

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
    rate_limit_ms: 100       # opcional, default 100
```

| Campo | Requerido | Descripción |
|---|---|---|
| `id` | Sí | Identificador único (guiones, sin espacios). |
| `name` | Sí | Nombre legible para humanos. |
| `namespace` | Sí | Dominio o prefijo para identificar tus registros en notas históricas. |
| `base_url` | Sí | URL raíz de tu API. El ETL llama a `{base_url}/pfif?updated_after=&offset=&limit=`. |
| `rate_limit_ms` | No | Milisegundos de espera entre requests paginados (default: 100). |

La matriz de GitHub Actions se genera automáticamente desde `sources.yml` — no necesitas editar el workflow. Solo agrega tu entrada y haz el PR.

Eso es todo. No necesitas escribir código Python ni entender el ETL.

## Cómo consumir los datos

Cada ciclo el ETL genera archivos PFIF 1.5 consolidados con todos los registros deduplicados y sus notas históricas, en **XML** y **JSON**. Las organizaciones humanitarias (Cruz Roja, Google Person Finder, etc.) pueden consumir cualquiera de los dos formatos.

| Formato | URL |
|---|---|
| XML | `https://insoelfklgcmshjpuhrb.supabase.co/storage/v1/object/public/pfif/export.xml` |
| JSON | `https://insoelfklgcmshjpuhrb.supabase.co/storage/v1/object/public/pfif/export.json` |

## Semántica de notas históricas (merges)

Cuando dos registros de diferentes fuentes se consideran la misma persona vía Phonetic Match (cercanía fonética >= PHONETIC_THRESHOLD (0.8), similitud de nombre >= NAME_SIMILARITY_THRESHOLD (0.9) y misma ubicación normalizada), el ETL **no** crea una segunda persona canónica. En su lugar, el registro de la fuente secundaria se almacena como una nota histórica adjunta a la persona canónica existente, siguiendo el formato de `<pfif:note>`.

Cada nota se genera con el siguiente formato (producido por `_build_note_text` en `etl/main.py`):

```
Registro también reportado por <namespace>. | ID original: <external_id>.
```

Campos adicionales si existen:

```
 | Foto: <photo_url>
 | Nota: <localizado_nota>
```

Ejemplo:

```
Registro también reportado por midominio.org. | ID original: midominio.org/a1b2c3. | Foto: https://tudominio.com/fotos/123.jpg | Nota: Reportado como localizado en hospital de Valencia
```

### Comportamiento actual

- El campo `status` de la persona canónica **sí** se actualiza cuando una fuente secundaria reporta un estatus de mayor prioridad (deceased > found > injured > missing > unknown), tanto en `atomic_upsert_person` (mismo `person_record_id`) como en `atomic_merge_note` (Phonetic Match). El orden de prioridad está definido por `status_to_priority` en la migración 012.
- Si el estatus reportado tiene igual o menor prioridad que el actual, el cambio queda únicamente en la nota histórica y no se propaga al registro canónico.
- Las notas deben tratarse como metadatos de procedencia / auditoría; el consumo de la nota es necesario para conocer estados alternativos reportados por otras fuentes.
- **First-writer-wins**: Los campos descriptivos (`full_name`, `given_name`, `family_name`, `age`, `description`, `photo_url`, `author_name`) siguen semántica first-writer-wins vía `COALESCE(persons.field, EXCLUDED.field)` en `atomic_upsert_person`. Una vez que un campo recibe un valor no-nulo de la primera fuente, fuentes posteriores no lo sobreescriben (migración 018). La excepción es `status` que escala por prioridad.

### Idempotencia y estrategia de watermark

- **`person_record_id` determinístico**: `sha256(phonetic_hash | location_normalized)[:16]`. Misma persona + misma ubicación → mismo ID siempre, entre todas las fuentes y ejecuciones.
- **`note_record_id` determinístico**: `sha256(person_record_id | source_id | external_id)[:16]`. Notas idempotentes vía `ON CONFLICT DO NOTHING`.
- **`source_records` idempotentes**: `ON CONFLICT (source_id, external_id) DO UPDATE`.
- **Watermark desde datos, no wall-clock**: El watermark `updated_after` se calcula como `max(source_date) - 1s` de los registros fetcheados, no del reloj del servidor. Esto evita pérdida de datos por TOCTOU si el fetch y el cómputo del watermark no son atómicos.
- **Watermark no avanza si hay errores**: Si algún record falla durante el procesamiento, el watermark **no** se actualiza. El siguiente ciclo re-fetchea la misma ventana (idempotente).
- **Fetch parcial no avanza watermark**: Si el fetch falla a mitad de la paginación, el ETL retorna sin avanzar el watermark. El siguiente ciclo reintenta desde el último watermark exitoso.

### Carreras de ingesta paralela y reconciliación

Cuando dos fuentes A y B se ejecutan concurrentemente (cada 10 min en jobs paralelos de GitHub Actions), pueden procesar a la misma persona simultáneamente. Si un typo en una fuente cambia el `phonetic_hash`, cada fuente genera un `person_record_id` distinto para la misma persona → dos registros canónicos duplicados.

El consolidator ejecuta después de todos los jobs de fuente y llama a `reconcile_duplicate_persons` repetidamente hasta que no queden pares por fusionar. El algoritmo:

1. Encuentra pares con misma ubicación normalizada y nombres trigram-similares (`similarity > 0.5`)
2. Reasigna `source_records` y `notes` del secundario al primario
3. Promueve el status de mayor prioridad al primario
4. Inserta nota de auditoría documentando la fusión
5. Elimina el registro secundario

La función procesa pares disjuntos por lote (sin transitividad) para evitar fusiones incorrectas en cadena.

### Monitoreo

- **Sentry**: El ETL reporta excepciones a Sentry vía `SENTRY_DSN`. Errores de fetch y fallos de procesamiento por registro se capturan sin detener el pipeline.
- **Errores de fetch**: Si el fetch falla (red, timeout), el ETL registra el error en Sentry y retorna sin avanzar el watermark. El error **no** causa fallo del job de CI (soft fail) — el siguiente ciclo (10 min después) reintenta automáticamente.
- **Errores de registro**: Si un registro individual falla (ej. nombre inválido), se omite y se incrementa el contador de errores. Si la tasa de error supera el 10% de los registros fetcheados, el job termina con `exit(1)`.
- **Resumen JSON**: Cada ejecución emite un resumen estructurado con conteos de creados, actualizados, mergeados, notas agregadas y errores.

### Limitaciones conocidas

- **Detección de colisión de `person_record_id`**: `is_full_match` usa nombre, edad y contacto para distinguir colisiones de hash. Como la tabla `persons` no tiene columna `contacto` (está en `source_records`), el chequeo de contacto no actúa como discriminador. Solo nombre y edad pueden diferenciar una colisión real. En la práctica esto es extremadamente improbable porque requiere mismo `phonetic_hash` + misma ubicación + mismo nombre + edad similar para dos personas distintas.
- **Registros sin ubicación**: Cuando un registro no tiene `last_known_location`, el phonetic match se ejecuta sin filtro de ubicación, lo que puede producir matches contra cualquier persona con nombre fonéticamente similar. Se recomienda que las fuentes siempre provean ubicación.

## Migraciones

Las migraciones están en `supabase/migrations/`. Aplicarlas en orden numérico.

### Con psql

```bash
for f in supabase/migrations/*.sql; do
  psql "$DATABASE_URL" -f "$f"
done
```

### Con Supabase CLI

```bash
supabase db push
```

## Stack

- **ETL**: Python 3.12 + httpx + phonetics + python-Levenshtein
- **Base de datos**: Supabase (PostgreSQL 15), schema `localize`. Migraciones en `supabase/migrations/`. Se usará la extensión `pg_trgm` para búsqueda difusa al optimizar el emparejamiento fonético.
- **Orquestación**: GitHub Actions (cron `*/10 * * * *`, matrix por fuente + consolidator)
- **Formato de exportación**: PFIF 1.5

### Seguridad

- Schema `localize` con RLS habilitado.
- Las tablas `persons`, `notes` y `source_records` tienen políticas SELECT público (lectura sin autenticación).
- Todos los RPC de escritura/mezcla (`atomic_upsert_person`, `atomic_merge_note`, `reconcile_duplicate_persons`) son SECURITY DEFINER. Su ejecución está restringida a los roles `authenticated` y `service_role`; los roles `anon` y `public` tienen el execute revocado (migraciones 010, 014).
- El ETL se conecta usando la clave `service_role` (vía `SUPABASE_SERVICE_KEY`) para invocar estos RPC.

