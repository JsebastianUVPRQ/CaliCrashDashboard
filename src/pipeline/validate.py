"""Data validation stage of the pipeline.

Validates raw data against the canonical schema and produces a
structured validation report with per-rule pass/fail results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from src.schema import ACCIDENT_SCHEMA, FATALITY_SCHEMA, Schema


@dataclass(frozen=True)
class ValidationResult:
    """Structured result of a validation run."""

    schema_name: str
    schema_version: str
    timestamp: str
    total_rows: int
    valid_rows: int
    dropped_rows: int
    column_errors: dict[str, list[str]] = field(default_factory=dict)
    null_counts: dict[str, int] = field(default_factory=dict)
    unique_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "dropped_rows": self.dropped_rows,
            "column_errors": self.column_errors,
            "null_counts": self.null_counts,
            "unique_counts": self.unique_counts,
        }


def _profile_columns(data: pd.DataFrame) -> tuple[dict[str, int], dict[str, int]]:
    """Compute null and unique counts for each column."""
    null_counts = {col: int(data[col].isna().sum()) for col in data.columns}
    unique_counts = {col: int(data[col].nunique(dropna=True)) for col in data.columns}
    return null_counts, unique_counts


def validate_accidents(data: pd.DataFrame) -> ValidationResult:
    """Validate raw accident data against the canonical accident schema."""
    return _validate(data, ACCIDENT_SCHEMA)


def validate_fatalities(data: pd.DataFrame) -> ValidationResult:
    """Validate raw fatality data against the canonical fatality schema."""
    return _validate(data, FATALITY_SCHEMA)


def _validate(data: pd.DataFrame, schema: Schema) -> ValidationResult:
    """Run schema validation and produce a structured report."""
    column_errors = schema.validate(data)
    null_counts, unique_counts = _profile_columns(data)

    # Count rows that would be dropped due to required column errors
    dropped = 0
    for col, errors in column_errors.items():
        if col in data.columns and any("missing" in e for e in errors):
            dropped += int(data[col].isna().sum())

    return ValidationResult(
        schema_name=schema.name,
        schema_version=schema.version,
        timestamp=datetime.now().isoformat(),
        total_rows=len(data),
        valid_rows=len(data) - dropped,
        dropped_rows=dropped,
        column_errors=column_errors,
        null_counts=null_counts,
        unique_counts=unique_counts,
    )