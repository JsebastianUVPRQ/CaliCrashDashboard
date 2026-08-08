"""Fatal-accident section: focused analysis of records with fatalities."""

import pandas as pd
import streamlit as st

from src.charts import bar_h, line_trend
from src.dashboard_sections.ui import render_empty_state, render_section_header
from src.metrics import aggregate_by_hour, fatal_mask
from src.theme import RISK


def render_fatal(accidents: pd.DataFrame) -> None:
    """Render the focused view of siniestros with at least one fatality."""
    render_section_header(
        "fatalidad",
        "Capítulo especial",
        "Siniestros con fallecido",
        "Enfoque sobre los registros cuya gravedad reporta al menos una persona "
        "fallecida en el punto del siniestro.",
    )

    fatal = accidents[fatal_mask(accidents)]
    if fatal.empty:
        render_empty_state(
            "No hay siniestros con fallecido para el conjunto filtrado.",
            [
                "Revisar los filtros de comuna y fechas.",
                "En la panorámica completa hay 2.891 registros de esta gravedad (2016–2024).",
            ],
        )
        return

    total = int(len(fatal))
    rendered_total = f"{total:,}"

    kpi_row = st.columns(3)
    kpi_row[0].metric("Registros con fallecido", rendered_total)
    kpi_row[1].metric(
        "Año con más casos",
        _top_year(fatal),
    )
    kpi_row[2].metric(
        "Hora más crítica",
        _top_hour(fatal),
    )

    year_col, hour_col = st.columns(2, gap="large")

    with year_col:
        st.markdown('<h3 class="panel-title">Por año</h3>', unsafe_allow_html=True)
        yearly = (
            fatal.assign(ano=fatal["fecha"].dt.year)
            .groupby("ano", observed=False)
            .size()
            .reset_index(name="accidentes")
            .sort_values("ano")
        )
        if not yearly.empty:
            fig = bar_h(
                yearly,
                category="ano",
                value="accidentes",
                color=RISK,
                height=280,
            )
            fig.update_layout(yaxis_title="Registros")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with hour_col:
        st.markdown('<h3 class="panel-title">Por hora del día</h3>', unsafe_allow_html=True)
        hourly = aggregate_by_hour(fatal)
        fig = bar_h(
            hourly[hourly["accidentes"].gt(0)],
            category="hora_dia",
            value="accidentes",
            color=RISK,
            height=280,
        )
        fig.update_layout(yaxis_title="Registros")
        fig.update_xaxes(tickmode="array", tickvals=list(range(0, 24, 4)))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    comuna_col, _spacer = st.columns((1.6, 1), gap="large")
    with comuna_col:
        st.markdown('<h3 class="panel-title">Concentración por comuna</h3>', unsafe_allow_html=True)
        by_comuna = (
            fatal.groupby("comuna", dropna=False, observed=False)
            .size()
            .reset_index(name="accidentes")
            .sort_values("accidentes", ascending=False)
            .head(10)
        )
        if by_comuna.empty:
            st.info("Sin comuna registrada para los siniestros fatales.")
        else:
            fig = bar_h(
                by_comuna.iloc[::-1],
                category="comuna",
                value="accidentes",
                color=RISK,
                height=280,
            )
            fig.update_layout(yaxis_title="Registros")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _top_year(fatal: pd.DataFrame) -> str:
    if fatal.empty:
        return "Sin datos"
    counts = fatal["fecha"].dt.year.value_counts()
    return str(counts.idxmax())


def _top_hour(fatal: pd.DataFrame) -> str:
    hourly = aggregate_by_hour(fatal)
    if hourly["accidentes"].sum() == 0:
        return "Sin datos"
    hour = int(hourly.sort_values(["accidentes", "hora_dia"], ascending=[False, True]).iloc[0]["hora_dia"])
    return f"{hour:02d}:00"