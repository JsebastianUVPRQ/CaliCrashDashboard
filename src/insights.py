"""Narrative insight helpers for the dashboard."""

import pandas as pd


def build_insights(accidents: pd.DataFrame) -> list[str]:
    """Build up to three short narrative insights from filtered accidents."""
    if accidents.empty:
        return []

    insights = [
        _dominant_comuna(accidents),
        _dominant_time_band(accidents),
        _dominant_severity(accidents),
    ]
    return [insight for insight in insights if insight][:3]


def _dominant_comuna(accidents: pd.DataFrame) -> str:
    counts = _known_value_counts(accidents, "comuna")
    if counts.empty:
        return _dominant_intersection(accidents)

    comuna = counts.idxmax()
    percentage = counts.max() / counts.sum() * 100
    return (
        f"La comuna {comuna} concentra "
        f"{_format_percentage(percentage)} de los accidentes con comuna registrada."
    )


def _dominant_intersection(accidents: pd.DataFrame) -> str:
    counts = _known_value_counts(accidents, "interseccion")
    if counts.empty:
        return "No hay dirección válida en los datos cargados para distribuir el riesgo territorial."

    intersection = counts.idxmax()
    percentage = counts.max() / counts.sum() * 100
    return (
        f"El punto {intersection} concentra "
        f"{_format_percentage(percentage)} de los accidentes con dirección registrada."
    )


def _dominant_time_band(accidents: pd.DataFrame) -> str:
    counts = _known_value_counts(accidents, "franja_horaria")
    if counts.empty:
        return "No hay horas válidas suficientes para identificar una franja crítica."

    band = counts.idxmax()
    percentage = counts.max() / counts.sum() * 100
    return f"La franja {band} domina el riesgo con {_format_percentage(percentage)} de los casos."


def _dominant_severity(accidents: pd.DataFrame) -> str:
    if "gravedad" not in accidents.columns:
        return ""

    severity_counts = _known_value_counts(accidents, "gravedad")
    if severity_counts.empty:
        return ""

    severity = severity_counts.idxmax()
    percentage = severity_counts.max() / severity_counts.sum() * 100
    return (
        f"La gravedad más frecuente es {severity.lower()}, "
        f"presente en {_format_percentage(percentage)} de registros."
    )


def _format_percentage(value: float) -> str:
    if 0 < value < 1:
        return f"{value:.1f}%"
    return f"{value:.0f}%"


def _known_value_counts(accidents: pd.DataFrame, column: str) -> pd.Series:
    if column not in accidents.columns:
        return pd.Series(dtype="int64")

    values = accidents[column].dropna().astype(str).str.strip()
    values = values[
        values.ne("")
        & values.str.lower().ne("sin dato")
        & values.str.lower().ne("nan")
        & values.str.lower().ne("none")
        & values.ne(".")
    ]
    return values.value_counts()


def build_focus_insights(accidents: pd.DataFrame) -> list[str]:
    """Build the executive summary band: fatal focus, territorial and trend.

    Unlike :func:`build_insights`, this adds a severity-0: "Con fallecido"
    concentration insight and a weekly-trend insight on top of the
    territorial one. Returns an empty list when there is no data.
    """
    if accidents.empty:
        return []

    insights = [
        _fatal_concentration(accidents),
        _dominant_comuna(accidents),
        _weekly_trend_insight(accidents),
    ]
    return [insight for insight in insights if insight][:3]


def _fatal_concentration(accidents: pd.DataFrame) -> str:
    if "gravedad" not in accidents.columns:
        return ""
    try:
        from src.metrics import fatal_mask
    except ImportError:  # pragma: no cover - defensive fallback
        return ""

    fatal = int(fatal_mask(accidents).sum())
    if fatal == 0:
        return "En el período filtrado no se registraron siniestros con fallecido."

    total = len(accidents)
    share = fatal / total * 100
    return (
        f"{fatal:,} siniestros con fallecido en el período filtrado, "
        f"equivalentes al {_format_percentage(share)} del total."
    )


def _weekly_trend_insight(accidents: pd.DataFrame) -> str:
    try:
        from src.metrics import build_kpis
    except ImportError:  # pragma: no cover - defensive fallback
        return ""

    kpis = build_kpis(accidents)
    if kpis.weekly_trend == "Sin tendencia":
        return "No hay suficientes días de observación para definir una tendencia."
    direction = {"Estable": "se mantiene estable", "Al alza": "va en aumento", "A la baja": "va a la baja"}.get(
        kpis.weekly_trend, kpis.weekly_trend.lower()
    )
    return f"La tendencia reciente {direction} ({kpis.weekly_trend_delta:+.0f}% vs. período previo)."
