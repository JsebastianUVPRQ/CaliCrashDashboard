"""Executive summary: KPI strip and insight band."""

import pandas as pd

from src.dashboard_sections.ui import render_insight_band, render_kpi_cards
from src.insights import build_focus_insights
from src.metrics import build_kpis, fatal_injury_counts
from src.theme import fmt_pct


def render_resumen(accidents: pd.DataFrame) -> None:
    """Render the summary strip (KPI cards) and the insight band."""
    kpis = build_kpis(accidents)
    fatal, injured, _other = fatal_injury_counts(accidents)
    total = len(accidents)

    share_fatal = (fatal / total * 100) if total else 0.0
    delta = kpis.weekly_trend_delta
    trend_caption = (
        f"{delta:+.0f}% vs. período previo" if delta else "0% vs. período previo"
    )

    territorial_label = "Comuna crítica"
    territorial_value = kpis.top_comuna
    if kpis.top_comuna == "Sin datos" and kpis.top_intersection != "Sin datos":
        territorial_label = "Punto crítico"
        territorial_value = kpis.top_intersection

    cards = [
        ("Total siniestros", f"{total:,}", "Registros filtrados", ""),
        ("Con fallecido", f"{fatal:,}", f"{fmt_pct(share_fatal)} del total", "kpi-risk"),
        ("Con lesionado", f"{injured:,}", "Gravedad con heridos", "kpi-well"),
        (territorial_label, territorial_value, "Mayor concentración", ""),
        ("Hora crítica", kpis.critical_hour, "Pico observado", ""),
        ("Tendencia semanal", kpis.weekly_trend, trend_caption, ""),
    ]
    render_kpi_cards(cards)

    insights = build_focus_insights(accidents)
    if insights:
        labels = ["Concentración", "Territorio", "Tendencia"]
        render_insight_band(list(zip(labels, insights)))