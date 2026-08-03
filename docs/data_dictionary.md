# Data Dictionary

## Accidentes (`accidentes_limpios.parquet`)

| Column | Type | Required | Description | Source Mapping |
|---|---|---|---|---|
| `fecha` | `datetime64[ns]` | Yes | Incident date | `date`, `fecha_accidente`, `fecha_hecho` |
| `hora` | `object` | Yes | Incident time (HH:MM) | `hora_accidente`, `hora_hecho` |
| `latitud` | `float64` | Yes | WGS84 latitude (3.0–3.8) | `latitude`, `lat`, `y` |
| `longitud` | `float64` | Yes | WGS84 longitude (-77.0–-76.0) | `longitude`, `lon`, `lng`, `long`, `x` |
| `comuna` | `object` | Yes | Comuna number or name | `comuna_nombre` |
| `barrio` | `object` | Yes | Neighborhood name | — |
| `tipo_accidente` | `object` | Yes | Accident type | `tipo`, `clase_accidente`, `tipo_confirmado_1`, etc. |
| `gravedad` | `object` | Yes | Severity level | `tipo_confirmado`, `severidad`, `gravedad_accidente` |
| `interseccion` | `object` | Yes | Intersection or address | `cruce`, `direccion`, `direccion_reporte`, `direccion_hecho` |
| `franja_horaria` | `object` | No (derived) | Time band: `madrugada`, `mañana`, `tarde`, `noche`, `Sin dato` | Derived from `hora` |
| `dia_semana` | `object` | No (derived) | Weekday in Spanish | Derived from `fecha` |
| `mes` | `object` | No (derived) | Month as `YYYY-MM` | Derived from `fecha` |

### Validation Rules

- **`fecha`**: Must be parseable as a date. Invalid dates are dropped.
- **`hora`**: Must be parseable as `HH:MM` or a numeric hour. Invalid values default to `00:00`.
- **`latitud`/`longitud`**: Must be numeric and within Cali bounds. Records with coordinates outside Cali are dropped; records with missing coordinates are kept (they can still be analyzed by comuna/address).
- **`comuna`, `barrio`, `tipo_accidente`, `gravedad`, `interseccion`**: Missing values are filled with `"Sin dato"`.

### Time Band Definition

| Band | Hours |
|---|---|
| `madrugada` | 00:00–05:59 |
| `mañana` | 06:00–11:59 |
| `tarde` | 12:00–17:59 |
| `noche` | 18:00–23:59 |

---

## Fallecidos (`fallecidos_limpios.parquet`)

| Column | Type | Required | Description |
|---|---|---|---|
| `ano` | `int64` | Yes | Year of incident |
| `mes` | `int64` | Yes | Month of incident (1–12) |
| `dia_semana` | `object` | Yes | Weekday name in Spanish |
| `rango_3h` | `object` | Yes | 3-hour time range (e.g., `"21:00 A 23:59"`) |
| `rango_6h` | `object` | Yes | 6-hour time range |
| `sexo` | `object` | Yes | Victim sex (`HOMBRE`, `MUJER`) |
| `rango_edad` | `object` | Yes | Age range (e.g., `"[20,25)"`) |
| `clase_accidente` | `object` | Yes | Crash class (e.g., `CHOQUE`, `ATROPELLO`) |
| `hipotesis` | `object` | Yes | Hypothesis |
| `total_fallecidos` | `int64` | Yes | Weighted fatality count |

### Source Notes

- Data comes from the **Fondo de Prevención Vial** (Fondo de Prevención Vial) via the **Observatorio Nacional de Seguridad Vial**.
- Files are semicolon-separated (`;`) with UTF-8 BOM encoding.
- Only records where `Departamento == "VALLE DEL CAUCA"` and `Municipio == "CALI"` are kept.
- The `-1` sentinel value in `Rango3horas`, `Rango6horas`, and other fields is mapped to `"Sin información"`.
- **Deduplication**: The three snapshot files (`datos-desestructurados_a/b/c.csv`) overlap significantly. Records are deduplicated on 24 identifying columns, keeping the most complete record per event.