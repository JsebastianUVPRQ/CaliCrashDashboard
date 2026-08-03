# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Data Sources                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ data/raw/    │  │ data/        │  │ Remoto (URLs)    │  │
│  │ accidentes   │  │ fallecidos/  │  │ datos.cali.gov.co│  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────┘  │
└─────────┼──────────────────┼────────────────────────────────┘
          │                  │
          ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                       ETL Pipeline                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ extract  │→ │ validate │→ │transform │→ │  load    │     │
│  │ .py      │  │ .py      │  │ .py      │  │ .py      │     │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │
│                            schema.py (data contract)         │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
                  ┌───────────────────────┐
                  │  data/processed/      │
                  │  *.parquet + manifest │
                  └───────────┬───────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit Dashboard                     │
│  app.py → src/dashboard.py (UI composition)                 │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ src/metrics.py   → KPIs, filters, aggregations       │   │
│  │ src/insights.py  → Narrative insights                │   │
│  │ src/mapa.py      → Folium map (heatmap + clusters)   │   │
│  │ src/stats/       → Poisson GLM + diagnostics         │   │
│  │ src/fallecidos.py→ Fatality ETL/aggregations         │   │
│  │ src/config.py    → Shared configuration              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Module Responsibilities

### Entry Point

| Module | Responsibility |
|---|---|
| `app.py` | Thin Streamlit entry point; delegates to `src/dashboard.py` |

### Core Modules (`src/`)

| Module | Responsibility |
|---|---|
| `config.py` | Shared constants: data paths, Cali center, category orders, thresholds |
| `schema.py` | Canonical data contracts: column specs, validation rules |
| `dashboard.py` | Streamlit UI composition: header, filters, KPIs, map, charts, model panel |
| `etl.py` | Accident data loading, normalization, feature derivation |
| `fallecidos.py` | Fatality ETL, normalization, deduplication, aggregations |
| `insights.py` | Auto-generated narrative insights |
| `mapa.py` | Folium map builders (heatmap, marker clusters, popups) |
| `metrics.py` | KPIs, filters, aggregations by comuna/hour/band/weekday |
| `modelo.py` | Legacy baseline frequency estimation (Poisson CI) |

### Pipeline Package (`src/pipeline/`)

| Module | Responsibility |
|---|---|
| `extract.py` | Source discovery and raw data loading |
| `validate.py` | Schema validation and structured reports |
| `transform.py` | Cleaning, normalization, feature derivation |
| `load.py` | Parquet + manifest persistence |

### Statistics Package (`src/stats/`)

| Module | Responsibility |
|---|---|
| `frequency_model.py` | Poisson GLM with coefficients, CIs, significance, diagnostics |

### Scripts

| File | Responsibility |
|---|---|
| `scripts/run_pipeline.py` | CLI entry point for the ETL pipeline |

### Tests (`tests/`)

| File | Coverage |
|---|---|
| `test_etl.py` | Accident ETL: normalization, time bands, quality report |
| `test_metrics.py` | KPIs, filters, aggregations, weekly trends |
| `test_modelo.py` | Baseline frequency estimation |
| `test_fallecidos.py` | Fatality ETL, KPIs, aggregations, deduplication |
| `test_insights.py` | Narrative insight generation |
| `test_dashboard_temporal.py` | Temporal summary and insights |
| `test_pipeline.py` | Pipeline stages: extract, validate, transform, load |
| `test_stats.py` | Poisson GLM model |

## Data Flow

1. **Data ingestion** — Raw data is extracted from local files, uploaded files, or (optionally) remote URLs.
2. **Validation** — Raw data is validated against the canonical schema. Validation errors and null/unique counts are recorded.
3. **Transformation** — Data is cleaned: column aliasing, date parsing, coordinate validation, feature derivation.
4. **Persistence** — Processed data is written to Parquet with schema metadata. A manifest records source lineage, checksums, and validation results.
5. **Dashboard consumption** — The Streamlit app loads processed data (with fallbacks) and renders the UI using metrics, insights, map, and statistical model modules.

## Configuration

The `pyproject.toml` defines:

- **Build system**: setuptools
- **Dependencies**: pandas, numpy, streamlit, folium, streamlit-folium, plotly, statsmodels
- **Dev dependencies**: pytest, ruff, mypy, black, pre-commit
- **Tool configuration**: ruff lint rules, mypy strict mode, pytest paths, black formatting