# Data Pipeline

## Overview

The pipeline runs a reproducible ETL (Extract → Validate → Transform → Load) process over accident and fatality data. It produces processed Parquet files with schema metadata and a manifest recording source lineage and validation results.

```
raw data → extract → validate → transform → load → data/processed/*.parquet
                                                   ↘ manifest.json
```

## Usage

```bash
# Run the full pipeline (accidents + fatalities)
python scripts/run_pipeline.py

# Specify a custom output directory
python scripts/run_pipeline.py --output data/processed/

# Or via Make
make pipeline
```

## Pipeline Stages

### 1. Extract (`src/pipeline/extract.py`)

**Purpose:** Discover and load raw data from the first available source.

**Accident sources (in priority order):**

| Priority | Source | Description |
|---|---|---|
| 1 | Uploaded file | Streamlit file uploader |
| 2 | `data/processed/accidentes_limpios.parquet` | Previous pipeline output |
| 3 | `data/processed/accidentes_limpios.csv` | Previous pipeline output |
| 4 | `data/processed/accidentes_cali_ampliados.csv` | Extended dataset |
| 5 | `data/processed/accidentes_ampliados.csv` | Extended dataset |
| 6 | `data/raw/accidentes.csv` | Raw snapshot |
| 7 | `data/raw/cali_lesionados_2016_2025.csv` | Open data portal |
| 8 | `data/raw/cali_siniestralidad_2016_2024.csv` | Open data portal |
| 9 | Built-in sample | 9-row sample for UI validation |

**Fatality sources:** All `*.csv` files in `data/fallecidos/` are concatenated and **deduplicated** using a 24-column composite key.

### 2. Validate (`src/pipeline/validate.py`)

**Purpose:** Validate raw data against the canonical schema and produce a structured validation report.

- Checks for missing required columns
- Applies per-column validation rules (date parseability, coordinate bounds, etc.)
- Computes null and unique counts per column
- Produces a `ValidationResult` with total/valid/dropped row counts

### 3. Transform (`src/pipeline/transform.py`)

**Purpose:** Clean, normalize, and derive features.

**Accidents:**
- Column name normalization and aliasing
- Date parsing (handles mixed day-first/month-first formats)
- Coordinate coercion and Cali bounds filtering
- `franja_horaria`, `dia_semana`, `mes` feature derivation

**Fatalities:**
- Cali/Valle del Cauca filtering
- Month and weekday name extraction
- `-1` sentinel → `"Sin información"` mapping
- Weighted fatality count parsing

### 4. Load (`src/pipeline/load.py`)

**Purpose:** Write processed data with lineage metadata.

- **Parquet** with schema metadata (`.schema.json` alongside)
- **Manifest** (`manifest.json`) recording:
  - Source type, path, checksum, row/column counts
  - Validation results (total/valid/dropped)
  - Output file paths
  - Pipeline version and timestamp

## Schema Contracts (`src/schema.py`)

The schema registry defines the canonical column contracts:

- `ACCIDENT_SCHEMA` — 12 columns (9 required + 3 derived)
- `FATALITY_SCHEMA` — 10 columns

Each `ColumnSpec` defines: name, dtype, required flag, description, aliases, and an optional validation function.

## Output Files

| File | Description |
|---|---|
| `data/processed/accidentes_limpios.parquet` | Cleaned accident data |
| `data/processed/accidentes_limpios.schema.json` | Schema metadata for accidents |
| `data/processed/fallecidos_limpios.parquet` | Cleaned fatality data |
| `data/processed/fallecidos_limpios.schema.json` | Schema metadata for fatalities |
| `data/processed/manifest.json` | Pipeline manifest with lineage and validation |

## Adding a New Source

1. Add the file path to `DATA_CANDIDATES` in `src/config.py` (for accidents)
2. Or drop a CSV in `data/fallecidos/` (for fatalities)
3. The pipeline automatically discovers it on the next run

## Adding a New Validation Rule

1. Add a validation helper function in `src/schema.py`
2. Reference it in the appropriate `ColumnSpec`
3. Re-run the pipeline and check the validation report