"""Data loading and normalization for Cali traffic crash records."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

import pandas as pd


REQUIRED_COLUMNS = {
    "fecha",
    "hora",
    "latitud",
    "longitud",
    "comuna",
    "barrio",
    "tipo_accidente",
    "tipo_vehiculo",
    "gravedad",
    "interseccion",
}

COLUMN_ALIASES = {
    "date": "fecha",
    "fecha_accidente": "fecha",
    "fecha_hecho": "fecha",
    "hora_accidente": "hora",
    "hora_hecho": "hora",
    "latitude": "latitud",
    "lat": "latitud",
    "y": "latitud",
    "longitude": "longitud",
    "lon": "longitud",
    "lng": "longitud",
    "long": "longitud",
    "x": "longitud",
    "comuna_nombre": "comuna",
    "tipo": "tipo_accidente",
    "clase_accidente": "tipo_accidente",
    "tipo_confirmado_1": "tipo_accidente",
    "tipo_clase_de_accidente": "tipo_accidente",
    "tipo_clase_de_accidente_1": "tipo_accidente",
    "clase_de_accidente": "tipo_accidente",
    "clase_siniestro": "tipo_accidente",
    "vehiculo": "tipo_vehiculo",
    "tipo_vehiculo_1": "tipo_vehiculo",
    "tipo_de_vehiculo": "tipo_vehiculo",
    "tipo_vehiculo_involucrado": "tipo_vehiculo",
    "vehiculo_involucrado": "tipo_vehiculo",
    "clase_vehiculo": "tipo_vehiculo",
    "tipo_confirmado": "gravedad",
    "severidad": "gravedad",
    "gravedad_accidente": "gravedad",
    "gravedad_del_accidente": "gravedad",
    "cruce": "interseccion",
    "direccion": "interseccion",
    "direccion_reporte": "interseccion",
    "direccion_hecho": "interseccion",
}

CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
CSV_SEPARATORS = (None, ";", ",")

_TIME_BAND_BINS = [-1, 5, 11, 17, 23]
_TIME_BAND_LABELS = ["madrugada", "mañana", "tarde", "noche"]

WEEKDAY_NAMES = {
    0: "lunes",
    1: "martes",
    2: "miércoles",
    3: "jueves",
    4: "viernes",
    5: "sábado",
    6: "domingo",
}

CALI_LAT_RANGE = (3.0, 3.8)
CALI_LON_RANGE = (-77.0, -76.0)


@dataclass(frozen=True)
class DataQuality:
    total_raw: int
    total_clean: int
    null_fecha: int
    null_coords: int
    out_of_bounds: int


def load_accident_data(paths: Iterable[Path]) -> pd.DataFrame:
    """Load the first available accident dataset or return a small sample.

    Args:
        paths: Candidate file paths, ordered by preference. Supports CSV and Parquet.

    Returns:
        A normalized accident DataFrame ready for dashboard filters.
    """
    for path in paths:
        if path.exists():
            suffix = path.suffix.lower()
            if suffix == ".parquet":
                return normalize_accident_data(pd.read_parquet(path))
            return normalize_accident_data(read_csv_flexible(path))

    return normalize_accident_data(build_sample_accidents())


def read_csv_flexible(path_or_buffer: object) -> pd.DataFrame:
    """Read CSV data with common Cali source encodings and separators."""
    last_error: Exception | None = None
    for encoding in CSV_ENCODINGS:
        for separator in CSV_SEPARATORS:
            try:
                kwargs: dict[str, object] = {
                    "encoding": encoding,
                    "on_bad_lines": "skip",
                }
                if separator is None:
                    kwargs.update({"sep": None, "engine": "python"})
                else:
                    kwargs["sep"] = separator

                data = pd.read_csv(path_or_buffer, **kwargs)
                if len(data.columns) > 1 or separator == ",":
                    return data
            except Exception as exc:
                last_error = exc

            if hasattr(path_or_buffer, "seek"):
                path_or_buffer.seek(0)

    if last_error is not None:
        raise last_error
    raise ValueError("No fue posible leer el archivo CSV.")


def normalize_accident_data(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize accident fields, dates, coordinates, and derived columns."""
    normalized = _normalize_columns(data)
    normalized = _parse_and_validate(normalized)
    normalized = _derive_time_features(normalized)
    return normalized.sort_values("fecha").reset_index(drop=True)


def data_quality_report(raw: pd.DataFrame, cleaned: pd.DataFrame) -> DataQuality:
    """Compare raw input against cleaned output for quality metrics."""
    normalized = _normalize_columns(raw)
    parsed_dates = _parse_mixed_dates(normalized["fecha"])
    latitudes = pd.to_numeric(normalized["latitud"], errors="coerce")
    longitudes = pd.to_numeric(normalized["longitud"], errors="coerce")
    missing_coordinates = latitudes.isna() | longitudes.isna()
    has_coordinates = ~missing_coordinates
    out_of_bounds = has_coordinates & ~(
        latitudes.between(*CALI_LAT_RANGE) & longitudes.between(*CALI_LON_RANGE)
    )

    return DataQuality(
        total_raw=len(raw),
        total_clean=len(cleaned),
        null_fecha=int(parsed_dates.isna().sum()),
        null_coords=int(missing_coordinates.sum()),
        out_of_bounds=int(out_of_bounds.sum()),
    )


def assign_time_band(hour_value: object) -> str:
    """Return the Cali dashboard time band for a time-like value.

    Examples:
        ``assign_time_band("07:30")`` returns ``"mañana"``.
        ``assign_time_band("21")`` returns ``"noche"``.
    """
    hour = _extract_hour(hour_value)
    bands = [
        ("madrugada", 0, 5),
        ("mañana", 6, 11),
        ("tarde", 12, 17),
        ("noche", 18, 23),
    ]
    for band, start, end in bands:
        if start <= hour <= end:
            return band
    return "Sin dato"


def build_sample_accidents() -> pd.DataFrame:
    """Create a tiny Cali-centered sample for first-run dashboard validation."""
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
                "tipo_vehiculo": "Automóvil",
                "gravedad": "Solo daños",
                "interseccion": "Avenida 6N con Calle 21N",
            },
            {
                "fecha": "2025-01-05",
                "hora": "08:05",
                "latitud": 3.4550,
                "longitud": -76.5310,
                "comuna": "2",
                "barrio": "Santa Mónica",
                "tipo_accidente": "Choque",
                "tipo_vehiculo": "Motocicleta",
                "gravedad": "Herido",
                "interseccion": "Avenida 6N con Calle 30N",
            },
            {
                "fecha": "2025-01-05",
                "hora": "18:45",
                "latitud": 3.4206,
                "longitud": -76.5222,
                "comuna": "19",
                "barrio": "San Fernando",
                "tipo_accidente": "Atropello",
                "tipo_vehiculo": "Motocicleta",
                "gravedad": "Herido",
                "interseccion": "Calle 5 con Carrera 34",
            },
            {
                "fecha": "2025-01-06",
                "hora": "06:20",
                "latitud": 3.4218,
                "longitud": -76.5205,
                "comuna": "19",
                "barrio": "San Fernando",
                "tipo_accidente": "Caída de ocupante",
                "tipo_vehiculo": "Motocicleta",
                "gravedad": "Herido",
                "interseccion": "Calle 5 con Carrera 34",
            },
            {
                "fecha": "2025-01-06",
                "hora": "23:10",
                "latitud": 3.3731,
                "longitud": -76.5360,
                "comuna": "17",
                "barrio": "El Caney",
                "tipo_accidente": "Choque",
                "tipo_vehiculo": "Automóvil",
                "gravedad": "Solo daños",
                "interseccion": "Carrera 80 con Calle 42",
            },
            {
                "fecha": "2025-01-07",
                "hora": "13:40",
                "latitud": 3.3745,
                "longitud": -76.5385,
                "comuna": "17",
                "barrio": "Valle del Lili",
                "tipo_accidente": "Choque",
                "tipo_vehiculo": "Automóvil",
                "gravedad": "Solo daños",
                "interseccion": "Carrera 98 con Calle 25",
            },
            {
                "fecha": "2025-01-07",
                "hora": "17:15",
                "latitud": 3.4370,
                "longitud": -76.5233,
                "comuna": "3",
                "barrio": "San Nicolás",
                "tipo_accidente": "Atropello",
                "tipo_vehiculo": "Transporte público",
                "gravedad": "Herido",
                "interseccion": "Calle 15 con Carrera 8",
            },
            {
                "fecha": "2025-01-08",
                "hora": "01:35",
                "latitud": 3.4439,
                "longitud": -76.5074,
                "comuna": "8",
                "barrio": "Primitivo Crespo",
                "tipo_accidente": "Volcamiento",
                "tipo_vehiculo": "Automóvil",
                "gravedad": "Solo daños",
                "interseccion": "Autopista Sur con Carrera 23",
            },
            {
                "fecha": "2025-01-08",
                "hora": "19:25",
                "latitud": 3.3965,
                "longitud": -76.5487,
                "comuna": "18",
                "barrio": "Meléndez",
                "tipo_accidente": "Choque",
                "tipo_vehiculo": "Motocicleta",
                "gravedad": "Fatal",
                "interseccion": "Calle 5 con Carrera 94",
            },
        ]
    )


def _normalize_columns(data: pd.DataFrame) -> pd.DataFrame:
    renamed = data.rename(columns=_normalize_column_name)
    renamed = renamed.rename(columns=COLUMN_ALIASES)
    renamed = _coalesce_duplicate_columns(renamed)
    for column in REQUIRED_COLUMNS.difference(renamed.columns):
        renamed[column] = pd.NA
    return renamed


def _coalesce_duplicate_columns(data: pd.DataFrame) -> pd.DataFrame:
    """Merge duplicate normalized columns using the first meaningful value."""
    if not data.columns.duplicated().any():
        return data

    coalesced = pd.DataFrame(index=data.index)
    for column in dict.fromkeys(data.columns):
        same_name = data.loc[:, data.columns == column]
        if same_name.shape[1] == 1:
            coalesced[column] = same_name.iloc[:, 0]
            continue

        result = same_name.iloc[:, 0]
        for index in range(1, same_name.shape[1]):
            result = _prefer_known_values(result, same_name.iloc[:, index])
        coalesced[column] = result
    return coalesced


def _prefer_known_values(left: pd.Series, right: pd.Series) -> pd.Series:
    left_values = left.astype("string").str.strip()
    right_values = right.astype("string").str.strip()
    missing_left = left.isna() | left_values.isin(["", ".", "nan", "None", "none"])
    known_right = ~(right.isna() | right_values.isin(["", ".", "nan", "None", "none"]))
    return left.where(~(missing_left & known_right), right)


def _parse_and_validate(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    data["fecha"] = _parse_mixed_dates(data["fecha"])
    data["hora"] = data["hora"].fillna("00:00").astype(str)
    data["latitud"] = pd.to_numeric(data["latitud"], errors="coerce")
    data["longitud"] = pd.to_numeric(data["longitud"], errors="coerce")
    for column in [
        "comuna",
        "barrio",
        "tipo_accidente",
        "tipo_vehiculo",
        "gravedad",
        "interseccion",
    ]:
        data[column] = data[column].fillna("Sin dato").astype(str)
    data = data.dropna(subset=["fecha"])
    has_coordinates = data["latitud"].notna() & data["longitud"].notna()
    within_cali = data["latitud"].between(*CALI_LAT_RANGE) & data[
        "longitud"
    ].between(*CALI_LON_RANGE)
    return data[~has_coordinates | within_cali].copy()


def _derive_time_features(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()
    data["franja_horaria"] = _assign_time_band_vectorized(data["hora"])
    data["dia_semana"] = data["fecha"].dt.weekday.map(WEEKDAY_NAMES)
    data["mes"] = data["fecha"].dt.to_period("M").astype(str)
    return data


def _assign_time_band_vectorized(hours: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(hours, format="%H:%M", errors="coerce")
    hour_numeric = parsed.dt.hour
    mask = hour_numeric.isna()
    if mask.any():
        numeric = pd.to_numeric(hours[mask].astype(str).str.strip(), errors="coerce")
        hour_numeric = hour_numeric.copy()
        hour_numeric[mask] = numeric % 24
    hour_numeric = hour_numeric.fillna(-1)
    result = pd.cut(
        hour_numeric,
        bins=_TIME_BAND_BINS,
        labels=_TIME_BAND_LABELS,
        right=True,
    )
    return result.cat.add_categories(["Sin dato"]).fillna("Sin dato")


def _normalize_column_name(column: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(column).strip().lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", ascii_text)).strip("_")


def _parse_mixed_dates(values: pd.Series) -> pd.Series:
    """Parse source dates that mix day-first and month-first formats."""
    text_values = values.astype(str).str.strip()
    parsed = pd.to_datetime(text_values, errors="coerce", format="%Y-%m-%d")
    missing = parsed.isna()
    if missing.any():
        parsed = parsed.copy()
        parsed.loc[missing] = pd.to_datetime(
            text_values[missing],
            errors="coerce",
            dayfirst=True,
        )
        missing = parsed.isna()

    if missing.any():
        fallback = pd.to_datetime(
            text_values[missing],
            errors="coerce",
            dayfirst=False,
        )
        parsed = parsed.copy()
        parsed.loc[missing] = fallback
    return parsed


def _extract_hour(hour_value: object) -> int:
    text_value = str(hour_value).strip()
    parsed = pd.to_datetime(text_value, format="%H:%M", errors="coerce")
    if pd.isna(parsed):
        try:
            return int(float(text_value)) % 24
        except ValueError:
            pass
    if pd.isna(parsed):
        parsed = pd.to_datetime(text_value, errors="coerce")
    if pd.isna(parsed):
        return -1
    return int(parsed.hour)
