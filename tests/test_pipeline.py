"""Tests for the data pipeline modules."""

import json
from pathlib import Path

import pandas as pd

from src.pipeline import (
    extract_accidents,
    extract_fatalities,
    load_processed_data,
    transform_accidents,
    transform_fatalities,
    validate_accidents,
    validate_fatalities,
    write_manifest,
)
from src.pipeline.extract import SourceInfo
from src.pipeline.validate import ValidationResult


def _sample_accident_raw() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "fecha": "2025-01-05",
                "hora": "07:30",
                "latitud": 3.4516,
                "longitud": -76.5320,
                "comuna": "2",
                "barrio": "Versalles",
                "tipo_accidente": "Choque",
                "gravedad": "Solo daños",
                "interseccion": "Avenida 6N con Calle 21N",
            }
        ]
    )


def test_extract_accidents_falls_back_to_sample() -> None:
    raw, source = extract_accidents(candidates=())

    assert source.source_type == "sample"
    assert len(raw) > 0
    assert source.row_count == len(raw)
    assert source.checksum


def test_extract_accidents_uses_uploaded_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "accidents.csv"
    _sample_accident_raw().to_csv(csv_path, index=False)

    with csv_path.open("rb") as f:
        raw, source = extract_accidents(uploaded_file=f)

    assert source.source_type == "upload"
    assert len(raw) == 1


def test_validate_accidents_reports_issues() -> None:
    raw = _sample_accident_raw()
    result = validate_accidents(raw)

    assert result.total_rows == 1
    assert result.valid_rows == 1
    assert result.schema_name == "accidentes"


def test_transform_accidents_derives_columns() -> None:
    raw = _sample_accident_raw()
    result = transform_accidents(raw)

    assert "franja_horaria" in result.columns
    assert "dia_semana" in result.columns
    assert "mes" in result.columns
    assert result.loc[0, "franja_horaria"] == "mañana"


def test_extract_fatalities_from_empty_dir(tmp_path: Path) -> None:
    raw, source = extract_fatalities(tmp_path)

    assert raw.empty
    assert source.row_count == 0


def test_validate_fatalities_handles_data() -> None:
    data = pd.DataFrame(
        {
            "ano": [2024, 2025],
            "mes": [11, 3],
            "dia_semana": ["domingo", "lunes"],
            "rango_3h": ["21:00 A 23:59", "00:00 A 02:59"],
            "rango_6h": ["18:00 A 23:59", "00:00 A 05:59"],
            "sexo": ["HOMBRE", "MUJER"],
            "rango_edad": ["[20,25)", "[30,35)"],
            "clase_accidente": ["CHOQUE", "ATROPELLO"],
            "hipotesis": ["SIN INFORMACIÓN", "SIN INFORMACIÓN"],
            "total_fallecidos": [2, 1],
        }
    )
    result = validate_fatalities(data)

    assert result.total_rows == 2
    assert result.valid_rows == 2


def test_load_processed_data_writes_parquet_and_schema(tmp_path: Path) -> None:
    data = _sample_accident_raw()
    output = tmp_path / "accidentes.parquet"

    load_processed_data(data, output, "test_schema", "1.0.0")

    assert output.exists()
    schema_path = output.with_suffix(".schema.json")
    assert schema_path.exists()
    metadata = json.loads(schema_path.read_text(encoding="utf-8"))
    assert metadata["schema_name"] == "test_schema"
    assert metadata["schema_version"] == "1.0.0"


def test_write_manifest_records_lineage(tmp_path: Path) -> None:
    source = SourceInfo(
        source_type="local",
        source_path="data/test.csv",
        checksum="abc123",
        row_count=10,
        column_count=3,
    )
    validation = ValidationResult(
        schema_name="test",
        schema_version="1.0.0",
        timestamp="2026-01-01T00:00:00",
        total_rows=10,
        valid_rows=9,
        dropped_rows=1,
    )
    manifest_path = tmp_path / "manifest.json"

    write_manifest(manifest_path, source, validation, {"accidentes": "data/a.parquet"})

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source"]["row_count"] == 10
    assert manifest["validation"]["valid_rows"] == 9
    assert manifest["outputs"]["accidentes"] == "data/a.parquet"