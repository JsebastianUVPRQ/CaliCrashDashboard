"""Canonical schema definitions for the Cali crash dashboard.

This module defines the data contracts that all pipeline stages and
dashboard consumers reference. It is the single source of truth for
column names, dtypes, validation rules, and source mappings.
"""

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd


@dataclass(frozen=True)
class ColumnSpec:
    """Definition of a single canonical column."""

    name: str
    dtype: str
    required: bool = True
    description: str = ""
    aliases: tuple[str, ...] = ()
    validation: Callable[[pd.Series], pd.Series] | None = None


@dataclass(frozen=True)
class Schema:
    """A collection of column specifications forming a data contract."""

    name: str
    version: str
    columns: tuple[ColumnSpec, ...]

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(col.name for col in self.columns)

    @property
    def required_columns(self) -> tuple[str, ...]:
        return tuple(col.name for col in self.columns if col.required)

    def validate(self, data: pd.DataFrame) -> dict[str, list[str]]:
        """Validate a DataFrame against this schema.

        Returns a dict mapping column names to lists of validation errors.
        """
        errors: dict[str, list[str]] = {}
        for col in self.columns:
            if col.name not in data.columns:
                if col.required:
                    errors[col.name] = ["missing required column"]
                continue
            if col.validation is not None:
                try:
                    result = col.validation(data[col.name])
                    if not result.all():
                        count = int((~result).sum())
                        errors[col.name] = [f"{count} values failed validation"]
                except Exception as exc:
                    errors[col.name] = [f"validation raised: {exc}"]
        return errors


# --- Validation helpers -----------------------------------------------------


def _is_not_null(series: pd.Series) -> pd.Series:
    return series.notna()


def _is_within_cali_lat(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.isna() | numeric.between(3.0, 3.8)


def _is_within_cali_lon(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.isna() | numeric.between(-77.0, -76.0)


def _is_parseable_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").notna()


def _is_parseable_time(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series.astype(str), format="%H:%M", errors="coerce")
    return parsed.notna() | pd.to_numeric(series.astype(str).str.strip(), errors="coerce").notna()


# --- Canonical schemas ------------------------------------------------------


ACCIDENT_SCHEMA = Schema(
    name="accidentes",
    version="1.0.0",
    columns=(
        ColumnSpec("fecha", "datetime64[ns]", description="Incident date", validation=_is_parseable_date),
        ColumnSpec("hora", "object", description="Incident time (HH:MM)", validation=_is_parseable_time),
        ColumnSpec("latitud", "float64", description="WGS84 latitude", validation=_is_within_cali_lat),
        ColumnSpec("longitud", "float64", description="WGS84 longitude", validation=_is_within_cali_lon),
        ColumnSpec("comuna", "object", description="Comuna number or name"),
        ColumnSpec("barrio", "object", description="Neighborhood name"),
        ColumnSpec("tipo_accidente", "object", description="Accident type"),
        ColumnSpec("gravedad", "object", description="Severity level"),
        ColumnSpec("interseccion", "object", description="Intersection or address"),
        ColumnSpec("franja_horaria", "object", description="Derived time band"),
        ColumnSpec("dia_semana", "object", description="Derived weekday"),
        ColumnSpec("mes", "object", description="Derived month (YYYY-MM)"),
    ),
)

FATALITY_SCHEMA = Schema(
    name="fallecidos",
    version="1.0.0",
    columns=(
        ColumnSpec("ano", "int64", description="Year of incident"),
        ColumnSpec("mes", "int64", description="Month of incident (1-12)"),
        ColumnSpec("dia_semana", "object", description="Weekday name"),
        ColumnSpec("rango_3h", "object", description="3-hour time range"),
        ColumnSpec("rango_6h", "object", description="6-hour time range"),
        ColumnSpec("sexo", "object", description="Victim sex"),
        ColumnSpec("rango_edad", "object", description="Age range"),
        ColumnSpec("clase_accidente", "object", description="Crash class"),
        ColumnSpec("hipotesis", "object", description="Hypothesis"),
        ColumnSpec("total_fallecidos", "int64", description="Weighted fatality count"),
    ),
)