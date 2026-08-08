"""Temporal patterns section: daily trend, hourly, weekday and monthly views."""

from dataclasses import dataclass
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.charts import bar_h, combo_bar_line, line_trend
from src.dashboard_sections.ui import render_section_header
from src.metrics import aggregate_by_hour, aggregate_by_weekday
from src.theme import ACCENT, DATA, MUTED, PANEL, TEXT, style_figure


MONTH_ABBR_ES = {
    1: "ene",
    2: "feb",
    3: "mar",
    4: "abr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "ago",
    9: "sep",
    10: "oct",
    11: "nov",
    12: "dic",
}


@dataclass(frozen=True)
class TemporalSummary:
    """Narrative indicators for temporal accident patterns."""

    total_accidents: int
    daily_average: float
    critical_hour: str
    critical_hour_count: int
    critical_day: str
    critical_day_count: int
    daily_variation: str
    hourly_insight: str
    daily_insight: str


def render_temporal(accidents: pd.DataFrame) -> None:
    """Render the temporal patterns section."""
    render_section_header(
        "temporal",
        "Patrones temporales",
        "Cuándo ocurren los siniestros",
        "Distribución de los siniestros filtrados por día, hora y mes, con la "
        "franja crítica del período.",
    )

    hourly = aggregate_by_hour(accidents)
    daily = _daily_counts(accidents)
    summary = _build_temporal_summary(accidents, hourly, daily)
    _render_temporal_kpis(summary)

    trend_col, hour_col = st.columns((1.35, 1), gap="large")

    with trend_col:
        st.markdown('<h3 class="panel-title">Tendencia diaria</h3>', unsafe_allow_html=True)
        fig = _daily_trend_figure(daily)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        _render_chart_note(summary.daily_insight, "daily-insight")

    with hour_col:
        st.markdown('<h3 class="panel-title">Distribución por hora</h3>', unsafe_allow_html=True)
        fig = bar_h(
            hourly,
            category="hora_dia",
            value="accidentes",
            color=ACCENT,
            height=260,
        )
        fig.update_layout(
            yaxis_title="Accidentes",
            xaxis_title="Hora",
        )
        fig.update_xaxes(tickmode="array", tickvals=list(range(0, 24, 4)))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        _render_chart_note(summary.hourly_insight, "hourly-insight")

    weekday_col, month_col = st.columns(2, gap="large")

    with weekday_col:
        st.markdown('<h3 class="panel-title">Siniestros por día de la semana</h3>', unsafe_allow_html=True)
        weekday = aggregate_by_weekday(accidents)
        if weekday.empty:
            st.info("Sin datos de día de la semana para mostrar.")
        else:
            fig = bar_h(
                weekday,
                category="dia_semana",
                value="accidentes",
                color=DATA,
                height=240,
            )
            fig.update_layout(yaxis_title="Accidentes")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with month_col:
        st.markdown('<h3 class="panel-title">Evolución mensual</h3>', unsafe_allow_html=True)
        monthly = _monthly_counts(accidents)
        if monthly.empty:
            st.info("Sin datos mensuales para mostrar.")
        else:
            fig = combo_bar_line(
                monthly,
                x="mes_dt",
                bar_col="accidentes",
                line_col="promedio_3m",
                bar_color=ACCENT,
                line_color=DATA,
                height=240,
            )
            fig.update_layout(yaxis_title="Accidentes")
            fig.update_xaxes(
                tickformat="%b %Y",
                nticks=min(len(monthly), 6),
            )
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _daily_trend_figure(daily: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=daily["dia"],
            y=daily["accidentes"],
            mode="lines+markers",
            line={"color": ACCENT, "width": 3},
            marker={"color": "#f97316", "size": 7},
            fill="tozeroy",
            fillcolor="rgba(245, 158, 11, 0.12)",
        )
    )
    max_daily = max(int(daily["accidentes"].max()), 1) if not daily.empty else 1
    fig.update_layout(
        height=260,
        margin={"l": 8, "r": 8, "t": 8, "b": 2},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Outfit, sans-serif", "color": "#d8dee9", "size": 12},
        yaxis_title="Accidentes",
        xaxis_title="Día",
        showlegend=False,
    )
    fig.update_xaxes(
        gridcolor="rgba(148, 163, 184, 0.16)",
        tickformat="%d/%m",
        ticklabelmode="period",
        nticks=min(len(daily), 6) if not daily.empty else 3,
        zeroline=False,
    )
    fig.update_yaxes(
        gridcolor="rgba(148, 163, 184, 0.10)",
        range=[0, max_daily * 1.18],
        zeroline=False,
    )
    return fig


def _monthly_counts(accidents: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        accidents.assign(periodo=accidents["fecha"].dt.to_period("M"))
        .groupby("periodo", observed=False)
        .size()
        .reset_index(name="accidentes")
        .sort_values("periodo")
    )
    if monthly.empty:
        return monthly
    monthly["mes_dt"] = monthly["periodo"].dt.to_timestamp()
    monthly["promedio_3m"] = monthly["accidentes"].rolling(3, min_periods=1).mean()
    return monthly


def _daily_counts(accidents: pd.DataFrame) -> pd.DataFrame:
    return (
        accidents.assign(dia=accidents["fecha"].dt.floor("D"))
        .groupby("dia")
        .size()
        .reset_index(name="accidentes")
    )


def _build_temporal_summary(
    accidents: pd.DataFrame,
    hourly: pd.DataFrame,
    daily: pd.DataFrame,
) -> TemporalSummary:
    total = len(accidents)
    if total == 0 or daily.empty:
        return TemporalSummary(
            total_accidents=0,
            daily_average=0.0,
            critical_hour="Sin datos",
            critical_hour_count=0,
            critical_day="Sin datos",
            critical_day_count=0,
            daily_variation="Sin tendencia",
            hourly_insight="No hay accidentes para interpretar con los filtros actuales.",
            daily_insight="No hay registros diarios para analizar en el periodo seleccionado.",
        )

    critical_hour_row = hourly.sort_values(
        ["accidentes", "hora_dia"],
        ascending=[False, True],
    ).iloc[0]
    critical_hour = int(critical_hour_row["hora_dia"])
    critical_hour_count = int(critical_hour_row["accidentes"])

    critical_day_row = daily.sort_values(
        ["accidentes", "dia"],
        ascending=[False, True],
    ).iloc[0]
    critical_day = pd.Timestamp(critical_day_row["dia"])
    critical_day_count = int(critical_day_row["accidentes"])
    daily_average = total / max(len(daily), 1)
    daily_variation = _daily_variation_label(daily)

    return TemporalSummary(
        total_accidents=total,
        daily_average=daily_average,
        critical_hour=f"{critical_hour:02d}:00",
        critical_hour_count=critical_hour_count,
        critical_day=_format_day_label(critical_day),
        critical_day_count=critical_day_count,
        daily_variation=daily_variation,
        hourly_insight=_hourly_insight(hourly, total),
        daily_insight=_daily_insight(daily, daily_average, daily_variation),
    )


def _render_temporal_kpis(summary: TemporalSummary) -> None:
    cards = [
        ("Accidentes", f"{summary.total_accidents:,}", "Registros filtrados"),
        ("Promedio diario", f"{summary.daily_average:.1f}", "Accidentes por día"),
        ("Hora crítica", summary.critical_hour, f"{summary.critical_hour_count} registros"),
        ("Día crítico", summary.critical_day, f"{summary.critical_day_count} registros"),
    ]
    card_html = "".join(
        (
            '<article class="temporal-kpi">'
            f"<span>{escape(label)}</span>"
            f"<strong>{escape(value)}</strong>"
            f"<small>{escape(caption)}</small>"
            "</article>"
        )
        for label, value, caption in cards
    )
    st.markdown(
        f'<section class="temporal-kpi-strip">{card_html}</section>',
        unsafe_allow_html=True,
    )


def _render_chart_note(message: str, key: str) -> None:
    st.markdown(
        f'<div class="chart-note" data-note="{key}">{escape(message)}</div>',
        unsafe_allow_html=True,
    )


def _hourly_insight(hourly: pd.DataFrame, total: int) -> str:
    if total == 0 or hourly.empty:
        return "No hay datos suficientes para identificar una concentración horaria."

    max_count = int(hourly["accidentes"].max())
    if max_count == 0:
        return "No hay datos suficientes para identificar una concentración horaria."

    active_hours = hourly[hourly["accidentes"].gt(0)]
    peak_hours = active_hours[active_hours["accidentes"].eq(max_count)]["hora_dia"].astype(int)
    share = max_count / total
    if len(peak_hours) > 3 or share < 0.2:
        return "La distribución horaria no presenta un patrón dominante; los eventos están dispersos durante el día."

    if len(peak_hours) == 1:
        hour = int(peak_hours.iloc[0])
        return f"La mayor frecuencia se observa a las {hour:02d}:00, con {max_count} accidentes registrados."

    formatted = ", ".join(f"{int(hour):02d}:00" for hour in peak_hours.tolist())
    return f"Las horas con mayor frecuencia son {formatted}, cada una con {max_count} accidentes registrados."


def _daily_insight(
    daily: pd.DataFrame,
    daily_average: float,
    daily_variation: str,
) -> str:
    if daily.empty:
        return "No hay registros diarios para analizar en el periodo seleccionado."

    max_row = daily.sort_values(["accidentes", "dia"], ascending=[False, True]).iloc[0]
    max_day = _format_day_label(pd.Timestamp(max_row["dia"]))
    max_count = int(max_row["accidentes"])
    if len(daily) == 1:
        return f"El periodo filtrado contiene un solo día: {max_day}, con {max_count} accidentes."

    return (
        f"La tendencia diaria se mantiene {daily_variation.lower()}; el máximo fue "
        f"{max_day} con {max_count} accidentes, frente a un promedio de {daily_average:.1f}."
    )


def _daily_variation_label(daily: pd.DataFrame) -> str:
    if len(daily) < 2:
        return "Sin tendencia"

    first = float(daily.iloc[0]["accidentes"])
    last = float(daily.iloc[-1]["accidentes"])
    if first == 0:
        delta = 100.0 if last > 0 else 0.0
    else:
        delta = ((last - first) / first) * 100

    if abs(delta) < 10:
        return "Estable"
    if delta > 0:
        return "Al alza"
    return "A la baja"


def _format_day_label(value: pd.Timestamp) -> str:
    month = MONTH_ABBR_ES.get(value.month, f"{value.month:02d}")
    return f"{value.day:02d} {month} {value.year}"