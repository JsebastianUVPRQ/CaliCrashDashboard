"""Aggregations and KPI helpers for dashboard views."""

from dataclasses import dataclass
from datetime import date

import pandas as pd

from src.config import TIME_BAND_ORDER, WEEKDAY_ORDER


@dataclass(frozen=True)
class DashboardKpis:
    """Key figures shown at the top of the dashboard."""

    total_accidents: int
    daily_average: float
    top_comuna: str
    top_intersection: str
    critical_hour: str
    weekly_trend: str
    weekly_trend_delta: float


def filter_accidents(
    accidents: pd.DataFrame,
    comunas: list[str] | None = None,
    direcciones: list[str] | None = None,
    franjas_horarias: list[str] | None = None,
    tipos_accidente: list[str] | None = None,
    gravedades: list[str] | None = None,
    date_range: tuple[date, date] | list[date] | None = None,
) -> pd.DataFrame:
    """Filter accidents by commune, address, time band, type, severity, and date."""
    filtered = accidents

    if comunas:
        filtered = filtered[filtered["comuna"].astype(str).isin(comunas)]

    if direcciones:
        filtered = filtered[filtered["interseccion"].astype(str).isin(direcciones)]

    if franjas_horarias:
        filtered = filtered[filtered["franja_horaria"].isin(franjas_horarias)]

    if tipos_accidente:
        filtered = filtered[filtered["tipo_accidente"].isin(tipos_accidente)]

    if gravedades:
        filtered = filtered[filtered["gravedad"].isin(gravedades)]

    if date_range:
        dates = filtered["fecha"].dt.date
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered = filtered[(dates >= start_date) & (dates <= end_date)]
        elif len(date_range) == 1:
            start_date = date_range[0]
            filtered = filtered[dates == start_date]

    return filtered.reset_index(drop=True)


def build_kpis(accidents: pd.DataFrame) -> DashboardKpis:
    """Build top-level dashboard KPIs from filtered accidents."""
    total = len(accidents)
    if accidents.empty:
        return DashboardKpis(
            total_accidents=0,
            daily_average=0.0,
            top_comuna="Sin datos",
            top_intersection="Sin datos",
            critical_hour="Sin datos",
            weekly_trend="Sin tendencia",
            weekly_trend_delta=0.0,
        )

    date_count = accidents["fecha"].dt.date.nunique()
    top_comuna = _top_value(accidents, "comuna")
    top_intersection = _top_value(accidents, "interseccion")
    critical_hour = _critical_hour(accidents)
    weekly_trend, weekly_trend_delta = _weekly_trend(accidents)

    return DashboardKpis(
        total_accidents=total,
        daily_average=total / max(date_count, 1),
        top_comuna=str(top_comuna),
        top_intersection=top_intersection,
        critical_hour=critical_hour,
        weekly_trend=weekly_trend,
        weekly_trend_delta=weekly_trend_delta,
    )


def aggregate_by_comuna(accidents: pd.DataFrame) -> pd.DataFrame:
    """Count accidents by commune in descending order."""
    return _count_by(accidents, "comuna")


def aggregate_by_intersection(accidents: pd.DataFrame) -> pd.DataFrame:
    """Count accidents by reported intersection/address in descending order."""
    return _count_by(accidents, "interseccion")


def aggregate_by_time_band(accidents: pd.DataFrame) -> pd.DataFrame:
    """Count accidents by time band using a human-readable order."""
    return _aggregate_sorted(accidents, "franja_horaria", TIME_BAND_ORDER)


def aggregate_by_vehicle_type(accidents: pd.DataFrame) -> pd.DataFrame:
    """Count accidents by vehicle type in descending order."""
    return _count_by(accidents, "tipo_vehiculo")


def aggregate_by_vehicle_and_severity(accidents: pd.DataFrame) -> pd.DataFrame:
    """Cross-tabulate accidents by vehicle type and severity."""
    columns = ["tipo_vehiculo", "gravedad", "accidentes"]
    if accidents.empty:
        return pd.DataFrame(columns=columns)

    values = accidents[["tipo_vehiculo", "gravedad"]].astype("string")
    known = accidents[_known_value_mask(values["tipo_vehiculo"])]
    if known.empty:
        return pd.DataFrame(columns=columns)

    return (
        known.groupby(["tipo_vehiculo", "gravedad"], dropna=False, observed=False)
        .size()
        .reset_index(name="accidentes")
        .sort_values("accidentes", ascending=False)
        .reset_index(drop=True)
    )


def aggregate_by_weekday(accidents: pd.DataFrame) -> pd.DataFrame:
    """Count accidents by weekday using Monday-first order in Spanish."""
    return _aggregate_sorted(accidents, "dia_semana", WEEKDAY_ORDER)


def aggregate_by_hour(accidents: pd.DataFrame) -> pd.DataFrame:
    """Count accidents by hour of day, including empty hours."""
    columns = ["hora_dia", "accidentes"]
    if accidents.empty:
        return pd.DataFrame({"hora_dia": range(24), "accidentes": [0] * 24})[columns]

    hours = _hour_series(accidents["hora"])
    counts = (
        hours.dropna()
        .astype(int)
        .value_counts()
        .reindex(range(24), fill_value=0)
        .rename_axis("hora_dia")
        .reset_index(name="accidentes")
    )
    return counts[columns]


def _aggregate_sorted(
    accidents: pd.DataFrame, column: str, order: list[str]
) -> pd.DataFrame:
    counts = _count_by(accidents, column)
    counts["sort_order"] = counts[column].map(
        {value: index for index, value in enumerate(order)}
    )
    return counts.sort_values(["sort_order", column]).drop(columns="sort_order")


def _count_by(accidents: pd.DataFrame, column: str) -> pd.DataFrame:
    if accidents.empty or column not in accidents.columns:
        return pd.DataFrame(columns=[column, "accidentes"])

    values = accidents[column].astype("string").str.strip()
    known = accidents[_known_value_mask(values)]
    if known.empty:
        return pd.DataFrame(columns=[column, "accidentes"])

    return (
        known.groupby(column, dropna=False, observed=False)
        .size()
        .reset_index(name="accidentes")
        .sort_values("accidentes", ascending=False)
        .reset_index(drop=True)
    )


def _top_value(accidents: pd.DataFrame, column: str) -> str:
    if column not in accidents.columns:
        return "Sin datos"

    values = accidents[column].dropna().astype(str).str.strip()
    values = values[_known_value_mask(values)]
    if values.empty:
        return "Sin datos"
    return str(values.value_counts().idxmax())


def _known_value_mask(values: pd.Series) -> pd.Series:
    lowered = values.str.lower()
    return (
        values.notna()
        & values.ne("")
        & lowered.ne("sin dato")
        & lowered.ne("nan")
        & lowered.ne("none")
        & values.ne(".")
    )


def _critical_hour(accidents: pd.DataFrame) -> str:
    counts = aggregate_by_hour(accidents)
    if counts["accidentes"].sum() == 0:
        return "Sin datos"
    sorted_counts = counts.sort_values(
        ["accidentes", "hora_dia"],
        ascending=[False, True],
    )
    hour = int(sorted_counts.iloc[0]["hora_dia"])
    return f"{hour:02d}:00"


def _weekly_trend(accidents: pd.DataFrame) -> tuple[str, float]:
    daily = (
        accidents.assign(dia=accidents["fecha"].dt.date)
        .groupby("dia")
        .size()
        .sort_index()
    )
    if len(daily) < 2:
        return "Sin tendencia", 0.0

    if len(daily) >= 14:
        # Compare last 7 days vs previous 7 days for a real weekly trend
        first_period = daily.iloc[-14:-7]
        second_period = daily.iloc[-7:]
    else:
        # Fallback to splitting the period in half for short ranges
        split_index = len(daily) // 2
        first_period = daily.iloc[:split_index]
        second_period = daily.iloc[split_index:]

    first_average = float(first_period.mean())
    second_average = float(second_period.mean())
    if first_average == 0:
        delta = 100.0 if second_average > 0 else 0.0
    else:
        delta = ((second_average - first_average) / first_average) * 100

    if abs(delta) < 5:
        return "Estable", delta
    if delta > 0:
        return "Al alza", delta
    return "A la baja", delta


def _hour_series(hours: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(hours.astype(str), format="%H:%M", errors="coerce")
    result = parsed.dt.hour.astype("float")
    missing = result.isna()
    if missing.any():
        numeric = pd.to_numeric(hours[missing].astype(str).str.strip(), errors="coerce")
        result.loc[missing] = numeric % 24
    return result
