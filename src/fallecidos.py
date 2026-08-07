"""ETL and aggregations for road fatality records."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.etl import read_csv_flexible


FATALITY_COLUMNS = {
    "Departamento",
    "Municipio",
    "EstadoVictima",
    "AnoHecho",
    "MesOCurrencia",
    "DiaOcurrencia",
    "Rango3horas",
    "Rango6horas",
    "Sexo",
    "RangoEdad",
    "ClaseAccidente",
    "Hipotesis",
    "ActorVial",
    "TotalRegistros",
}

# Columns of the official "Consolidado de muertes en accidentes de tránsito en
# Cali" (datos.cali.gov.co). One row per person killed on the road.
CONSOLIDADO_COLUMNS = {
    "SEXO",
    "EDAD",
    "HORA HECHO",
    "FECHA HECHO",
    "FECHA FALL.",
    "CONDICION",
}

NORMALIZED_COLUMNS = [
    "ano",
    "mes",
    "dia_semana",
    "rango_3h",
    "rango_6h",
    "sexo",
    "rango_edad",
    "clase_accidente",
    "hipotesis",
    "actor_vial",
    "total_fallecidos",
]

SOURCE_CONSOLIDADO = "consolidado_ckan"
SOURCE_SNAPSHOT = "inmlcf_snapshot"

# Road-user condition -> aproximación a la clase de siniestro (el consolidado
# solo registra la condición del fallecido, no la clase del accidente).
CONDICION_CLASE = {
    "PEATON": "ATROPELLO",
    "PEATÓN": "ATROPELLO",
    "CICLISTA": "CHOQUE",
    "MOTOCICLISTA": "CHOQUE",
    "PARRILLERO": "CHOQUE",
    "PASAJERO DE AUTO": "CHOQUE",
    "CONDUCTOR": "CHOQUE",
    "JINETE": "CHOQUE",
}

# Columns that uniquely identify a fatality event. The three snapshot files
# (datos-desestructurados_a/b/c.csv) overlap significantly; records appearing
# in multiple snapshots must be deduplicated to avoid inflating counts.
FATALITY_DEDUP_KEY = [
    "Departamento",
    "Municipio",
    "AnoHecho",
    "MesOCurrencia",
    "DiaOcurrencia",
    "Rango3horas",
    "Rango6horas",
    "Sexo",
    "RangoEdad",
    "ClaseAccidente",
    "Hipotesis",
    "DiagnosticoTopografico",
    "CondicionVictima",
    "ActorVial",
    "UsuarioVia",
    "Zona",
    "ObjetoColision",
    "TipoVehiculoGrupo",
    "TipoServicio",
    "EstadoVia",
    "ActividadVictima",
    "CausaMuerte",
    "CondicionLugar",
    "Muerte30Dias",
]

MONTHS = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}

WEEKDAY_BY_CODE = {
    "1": "lunes",
    "2": "martes",
    "3": "miércoles",
    "4": "jueves",
    "5": "viernes",
    "6": "sábado",
    "7": "domingo",
}


@dataclass(frozen=True)
class FatalityKpis:
    """Summary indicators for Cali fatality records."""

    total_fatalities: int
    top_year: str
    top_time_range: str
    top_crash_class: str


def load_fatality_data(directory: Path) -> pd.DataFrame:
    """Load and normalize all fatality CSV files from a directory.

    Supports two formats side by side:

    - The official CKAN "Consolidado de muertes en accidentes de tránsito en
      Cali" (person-level records, ``CONSOLIDADO_COLUMNS``).
    - The INMLCF snapshot files (aggregated rows, ``FATALITY_COLUMNS``).

    Both formats are normalized to the same contract and merged preferring,
    for each year, the source that documents the most months (the CKAN
    consolidado wins ties because it is the municipal official registry).
    """
    consolidated, snapshots = load_fatality_frames(directory)
    return merge_fatality_sources(
        [consolidated, snapshots],
        labels=[SOURCE_CONSOLIDADO, SOURCE_SNAPSHOT],
    )


def load_fatality_frames(directory: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and normalize the two fatality sources separately.

    Args:
        directory: Folder holding the fatality CSV files.

    Returns:
        A tuple ``(consolidado, snapshots)`` with the normalized CKAN
        consolidado and the normalized INMLCF snapshots (may be empty).
    """
    files = sorted(directory.glob("*.csv")) if directory.exists() else []
    consolidado_frames: list[pd.DataFrame] = []
    snapshot_frames: list[pd.DataFrame] = []
    for file in files:
        raw = read_csv_flexible(file)
        if _is_consolidado_format(raw):
            consolidado_frames.append(raw)
        else:
            snapshot_frames.append(raw)

    if consolidado_frames:
        consolidated = _deduplicate_fatality_records(
            pd.concat(consolidado_frames, ignore_index=True)
        )
        consolidated = _normalize_consolidado_fatalities(consolidated)
    else:
        consolidated = _empty_fatalities()

    if snapshot_frames:
        snapshots = _deduplicate_fatality_records(
            pd.concat(snapshot_frames, ignore_index=True)
        )
        snapshots = normalize_fatality_data(snapshots)
    else:
        snapshots = _empty_fatalities()

    return consolidated, snapshots


def _is_consolidado_format(data: pd.DataFrame) -> bool:
    """Detect the official CKAN fatality consolidado by its column names."""
    if data.empty:
        return False
    return CONSOLIDADO_COLUMNS.issubset(set(data.columns))


def _normalize_consolidado_fatalities(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize the CKAN consolidado into the shared fatality contract.

    Each row is one person: ``SEXO;EDAD;HORA HECHO;FECHA HECHO;FECHA FALL.;
    CONDICION``. The event date prefers ``FECHA HECHO`` and falls back to
    ``FECHA FALL.`` when the former is missing.
    """
    if data.empty:
        return _empty_fatalities()

    normalized = data.copy()
    for column in CONSOLIDADO_COLUMNS.difference(normalized.columns):
        normalized[column] = pd.NA

    hecho = _parse_consolidado_date(normalized["FECHA HECHO"])
    fall = _parse_consolidado_date(normalized["FECHA FALL."])
    event_date = hecho.fillna(fall)

    horas = _parse_consolidado_hour(normalized["HORA HECHO"])
    rango_3h = _consolidado_time_range(horas, width=3)
    rango_6h = _consolidado_time_range(horas, width=6)

    sexos = normalized["SEXO"].astype(str).str.strip().str.upper()
    condiciones = normalized["CONDICION"].astype(str).str.strip().str.upper()

    normalized["ano"] = event_date.dt.year
    normalized["mes"] = event_date.dt.month
    normalized["dia_semana"] = event_date.dt.weekday.map(
        lambda weekday: WEEKDAY_BY_CODE.get(str(weekday + 1))
    )
    normalized["rango_3h"] = rango_3h
    normalized["rango_6h"] = rango_6h
    normalized["sexo"] = sexos.map({"MASCULINO": "HOMBRE", "FEMENINO": "MUJER", "FEMENINA": "MUJER"}).fillna("Sin información")
    normalized["rango_edad"] = _consolidado_age_band(normalized["EDAD"])
    normalized["clase_accidente"] = condiciones.map(CONDICION_CLASE).fillna("Sin información")
    normalized["hipotesis"] = "Sin información"
    normalized["actor_vial"] = condiciones.replace({"SIN DATO": "Sin información"})
    normalized["total_fallecidos"] = 1

    normalized = normalized.dropna(subset=["ano", "mes"])
    normalized["ano"] = normalized["ano"].astype(int)
    normalized["mes"] = normalized["mes"].astype(int)
    return normalized[NORMALIZED_COLUMNS].reset_index(drop=True)


def _parse_consolidado_date(values: pd.Series) -> pd.Series:
    """Parse day-first dates, treating "." as missing."""
    text = values.astype(str).str.strip().replace(".", pd.NA)
    return pd.to_datetime(text, dayfirst=True, errors="coerce")


def _parse_consolidado_hour(values: pd.Series) -> pd.Series:
    """Parse ``HH:MM`` / ``H:MM`` hours; "." becomes NaN."""
    text = values.astype(str).str.strip().replace(".", pd.NA)
    parsed = pd.to_datetime(text, format="%H:%M", errors="coerce")
    return parsed.dt.hour.fillna(-1).astype(int)


def _consolidado_time_range(hours: pd.Series, *, width: int) -> pd.Series:
    """Map integer hours to ``"HH:00 A HH:59"`` bands of the given width."""
    start = (hours // width) * width
    valid = hours >= 0
    labels = pd.Series("Sin información", index=hours.index, dtype="object")
    labels[valid] = (
        start[valid].map("{:02d}:00".format) + " A " + (start[valid] + width - 1).map("{:02d}:59".format)
    )
    return labels


def _consolidado_age_band(values: pd.Series) -> pd.Series:
    """Map raw ages (int, ``"35-45"``, ``"2M"``, ``"23h"``) to age bands."""
    text = values.astype(str).str.strip()

    def band(value: str) -> str:
        if value in {".", "SIN DATO", "NAN"}:
            return "Sin información"
        if value.isdigit():
            age = int(value)
            return f"[{age // 5 * 5},{age // 5 * 5 + 5})"
        if "-" in value:
            low, _, high = value.partition("-")
            if low.isdigit() and high.isdigit():
                return f"[{low},{high})"
        return "[0,1)"

    return text.map(band)


def merge_fatality_sources(
    frames: list[pd.DataFrame], labels: list[str] | None = None
) -> pd.DataFrame:
    """Merge normalized fatality frames choosing the best source per year.

    For each year the source documenting the most distinct months wins; the
    CKAN consolidado (official municipal registry) breaks ties. The chosen
    source is recorded in a ``fuente`` column.

    Args:
        frames: Normalized fatality DataFrames (same contract columns).
        labels: Source labels, one per frame. Defaults to
            ``consolidado_ckan`` / ``inmlcf_snapshot`` in order.

    Returns:
        A merged DataFrame with a ``fuente`` column added.
    """
    if labels is None:
        labels = [SOURCE_CONSOLIDADO, SOURCE_SNAPSHOT][: len(frames)]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return _empty_fatalities()

    combined = pd.concat(
        (frame.assign(fuente=label) for frame, label in zip(frames, labels)),
        ignore_index=True,
    )
    combined = combined[combined["ano"].notna() & combined["mes"].notna()].copy()
    if combined.empty:
        return _empty_fatalities()

    coverage = (
        combined.groupby(["fuente", "ano"], observed=False)["mes"]
        .nunique()
        .rename("meses")
        .reset_index()
    )
    coverage["prioridad"] = coverage["fuente"].map(
        {SOURCE_CONSOLIDADO: 1, SOURCE_SNAPSHOT: 0}
    )
    best = coverage.sort_values(["ano", "meses", "prioridad"], ascending=False)
    winners = best.drop_duplicates(subset="ano", keep="first")
    chosen = set(zip(winners["fuente"], winners["ano"]))
    keys = list(zip(combined["fuente"], combined["ano"]))
    keep = combined[[key in chosen for key in keys]]
    return keep.reset_index(drop=True)


def reconcile_fatality_sources(
    frames: list[pd.DataFrame], labels: list[str] | None = None
) -> pd.DataFrame:
    """Per-year fatality counts by source for cross-validation.

    Args:
        frames: Normalized fatality DataFrames from different sources.
        labels: Source labels, one per frame. Defaults to
            ``consolidado_ckan`` / ``inmlcf_snapshot`` in order.

    Returns:
        A DataFrame with one row per year: total, consolidado CKAN and
        INMLCF snapshot counts.
    """
    if labels is None:
        labels = [SOURCE_CONSOLIDADO, SOURCE_SNAPSHOT][: len(frames)]
    counts: dict[int, dict[str, int]] = {}
    for frame, label in zip(frames, labels):
        if frame.empty:
            continue
        for year, total in (
            frame.groupby("ano")["total_fallecidos"].sum().to_dict().items()
        ):
            row = counts.setdefault(int(year), {})
            row[label] = int(total)

    rows = []
    for year in sorted(counts):
        row = counts[year]
        rows.append(
            {
                "ano": year,
                "consolidado_ckan": row.get(SOURCE_CONSOLIDADO, 0),
                "inmlcf_snapshot": row.get(SOURCE_SNAPSHOT, 0),
                "total": sum(row.values()),
            }
        )
    return pd.DataFrame(rows, columns=["ano", "consolidado_ckan", "inmlcf_snapshot", "total"])


def normalize_fatality_data(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize fatality records and keep only Cali, Valle del Cauca."""
    if data.empty:
        return _empty_fatalities()

    normalized = data.copy()
    for column in FATALITY_COLUMNS.difference(normalized.columns):
        normalized[column] = pd.NA

    normalized["Departamento"] = normalized["Departamento"].fillna("").astype(str)
    normalized["Municipio"] = normalized["Municipio"].fillna("").astype(str)
    normalized = normalized[
        normalized["Departamento"].map(_normalize_text).eq("VALLE DEL CAUCA")
        & normalized["Municipio"].map(_normalize_text).eq("CALI")
    ].copy()

    if normalized.empty:
        return _empty_fatalities()

    normalized["ano"] = pd.to_numeric(normalized["AnoHecho"], errors="coerce")
    normalized["mes"] = normalized["MesOCurrencia"].map(_extract_month)
    normalized["dia_semana"] = normalized["DiaOcurrencia"].map(_extract_weekday)
    normalized["rango_3h"] = _clean_text_column(normalized["Rango3horas"])
    normalized["rango_6h"] = _clean_text_column(normalized["Rango6horas"])
    normalized["sexo"] = _clean_text_column(normalized["Sexo"])
    normalized["rango_edad"] = _clean_text_column(normalized["RangoEdad"])
    normalized["clase_accidente"] = _clean_text_column(normalized["ClaseAccidente"])
    normalized["hipotesis"] = _clean_text_column(normalized["Hipotesis"])
    normalized["actor_vial"] = _clean_text_column(normalized["ActorVial"])
    normalized["total_fallecidos"] = pd.to_numeric(
        normalized["TotalRegistros"],
        errors="coerce",
    ).fillna(1)

    columns = [
        "ano",
        "mes",
        "dia_semana",
        "rango_3h",
        "rango_6h",
        "sexo",
        "rango_edad",
        "clase_accidente",
        "hipotesis",
        "actor_vial",
        "total_fallecidos",
    ]
    normalized = normalized.dropna(subset=["ano", "mes"])
    normalized["ano"] = normalized["ano"].astype(int)
    normalized["mes"] = normalized["mes"].astype(int)
    return normalized[columns].reset_index(drop=True)


def build_fatality_kpis(fatalities: pd.DataFrame) -> FatalityKpis:
    """Build top-level indicators for fatality records."""
    if fatalities.empty:
        return FatalityKpis(
            total_fatalities=0,
            top_year="Sin datos",
            top_time_range="Sin datos",
            top_crash_class="Sin datos",
        )

    return FatalityKpis(
        total_fatalities=int(fatalities["total_fallecidos"].sum()),
        top_year=str(_top_weighted_value(fatalities, "ano")),
        top_time_range=str(_top_weighted_value(fatalities, "rango_3h")),
        top_crash_class=str(_top_weighted_value(fatalities, "clase_accidente")),
    )


def aggregate_fatalities_by_year(fatalities: pd.DataFrame) -> pd.DataFrame:
    """Aggregate fatality counts by year."""
    return _weighted_count(fatalities, "ano").rename(columns={"ano": "Año"})


def aggregate_fatalities_by_time_range(fatalities: pd.DataFrame) -> pd.DataFrame:
    """Aggregate fatality counts by 3-hour range."""
    return _weighted_count(fatalities, "rango_3h")


def aggregate_fatalities_by_crash_class(fatalities: pd.DataFrame) -> pd.DataFrame:
    """Aggregate fatality counts by crash class."""
    return _weighted_count(fatalities, "clase_accidente")


def _read_fatality_files(files: Iterable[Path]) -> pd.DataFrame:
    frames = [
        read_csv_flexible(file)
        for file in files
    ]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return _deduplicate_fatality_records(combined)


def _deduplicate_fatality_records(data: pd.DataFrame) -> pd.DataFrame:
    """Remove records that appear in multiple snapshot files.

    The fatality CSVs are partial snapshots of the same underlying dataset
    taken at different times. A single fatality event can appear in several
    files with identical identifying fields. This function keeps the most
    complete record for each event (fewest missing values), preferring the
    first occurrence on ties.

    Args:
        data: Raw concatenated fatality records from all snapshot files.

    Returns:
        A deduplicated DataFrame with the same columns as ``data``.
    """
    if data.empty:
        return data

    available_key = [col for col in FATALITY_DEDUP_KEY if col in data.columns]
    if not available_key:
        return data

    # Count missing values per row to prefer the most complete record.
    completeness = data[available_key].isna().sum(axis=1)
    data = data.assign(_completeness=completeness)

    # Fill missing values with a sentinel so records that differ only by
    # missing fields still match during deduplication.
    dedup_view = data[available_key].fillna("__MISSING__")

    deduplicated = (
        data.assign(_dedup_key=dedup_view.astype(str).agg("|".join, axis=1))
        .sort_values("_completeness")
        .drop_duplicates(subset="_dedup_key", keep="first")
        .sort_index()
        .drop(columns=["_completeness", "_dedup_key"])
        .reset_index(drop=True)
    )
    return deduplicated


def _weighted_count(data: pd.DataFrame, column: str) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame(columns=[column, "fallecidos"])
    return (
        data.groupby(column, dropna=False)["total_fallecidos"]
        .sum()
        .reset_index(name="fallecidos")
        .sort_values("fallecidos", ascending=False)
        .reset_index(drop=True)
    )


def _top_weighted_value(data: pd.DataFrame, column: str) -> object:
    counts = _weighted_count(data, column)
    counts = counts[~counts[column].astype(str).isin(["Sin información", "-1"])]
    if counts.empty:
        return "Sin datos"
    return counts.iloc[0][column]


def _clean_text_column(series: pd.Series) -> pd.Series:
    cleaned = series.fillna("Sin información").astype(str).str.strip()
    return cleaned.replace({"-1": "Sin información", "": "Sin información"})


def _extract_month(value: object) -> int | None:
    text = _normalize_text(str(value).split(".", maxsplit=1)[-1])
    return MONTHS.get(text)


def _extract_weekday(value: object) -> str:
    parts = str(value).split(".", maxsplit=1)
    code = parts[0].strip()
    if code in WEEKDAY_BY_CODE:
        return WEEKDAY_BY_CODE[code]

    # Try parsing by name directly if the numeric prefix is missing
    normalized = _normalize_text(value)
    name_map = {
        "LUNES": "lunes",
        "MARTES": "martes",
        "MIERCOLES": "miércoles",
        "MIÉRCOLES": "miércoles",
        "JUEVES": "jueves",
        "VIERNES": "viernes",
        "SABADO": "sábado",
        "SÁBADO": "sábado",
        "DOMINGO": "domingo",
    }
    for key, name in name_map.items():
        if key in normalized:
            return name

    return "Sin información"


def _normalize_text(value: object) -> str:
    return str(value).strip().upper()


def _empty_fatalities() -> pd.DataFrame:
    return pd.DataFrame(columns=NORMALIZED_COLUMNS)
