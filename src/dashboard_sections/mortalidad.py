"""Mortality section: the lives lost to road crashes in Cali.

Presents the final result of the mortality registry (one row per person
killed): totals, yearly series, year×month heatmap, time-of-day profile,
crash class and victim profile. No source comparison or pipeline detail.
"""

from html import escape

import pandas as pd
import streamlit as st

from src.charts import bar_h, heat_yearly_monthly, line_trend
from src.dashboard_sections.ui import (
    render_caveat,
    render_empty_state,
    render_kpi_cards,
    render_section_header,
    render_source_note,
)
from src.fallecidos import (
    aggregate_fatalities_by_crash_class,
    aggregate_fatalities_by_time_range,
    aggregate_fatalities_by_year,
    build_fatality_kpis,
)
from src.theme import MUTED, RISK


def render_mortalidad(fatalities: pd.DataFrame) -> None:
    """Render the mortality (lives lost) section with final results only."""
    render_section_header(
        "mortalidad",
        "Mortalidad vial",
        "Vidas perdidas en la vía",
        "Registro oficial de personas fallecidas en siniestros viales en Cali. "
        "Cada persona cuenta una vez, según el consolidado municipal.",
    )

    if fatalities.empty:
        render_empty_state(
            "No se encontraron registros de mortalidad para Cali.",
            [
                "Verificar que el archivo de mortalidad esté cargado.",
                "Revisar el rango temporal disponible.",
            ],
        )
        return

    kpis = build_fatality_kpis(fatalities)
    cards = [
        ("Total de vidas perdidas", f"{kpis.total_fatalities:,}", "Personas fallecidas", "kpi-risk"),
        ("Año crítico", str(kpis.top_year), "Mayor número de fallecidos", ""),
        ("Franja más crítica", str(kpis.top_time_range), "Horario de mayor riesgo", ""),
        ("Siniestro más frecuente", str(kpis.top_crash_class), "Clase con más víctimas", ""),
    ]
    render_kpi_cards(cards)

    yearly_col, monthly_col = st.columns((1.2, 1), gap="large")

    with yearly_col:
        st.markdown('<h3 class="panel-title">Vidas perdidas por año</h3>', unsafe_allow_html=True)
        yearly = aggregate_fatalities_by_year(fatalities).sort_values("Año")
        fig = line_trend(yearly, x="Año", y="fallecidos", color=RISK, height=300)
        fig.update_layout(yaxis_title="Fallecidos")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with monthly_col:
        st.markdown('<h3 class="panel-title">Estacionalidad año × mes</h3>', unsafe_allow_html=True)
        matrix = _year_month_matrix(fatalities)
        if matrix.size:
            fig = heat_yearly_monthly(matrix, height=320)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("Sin datos de estacionalidad para mostrar.")

    time_col, kind_col = st.columns(2, gap="large")

    with time_col:
        st.markdown('<h3 class="panel-title">Por franja horaria (3 horas)</h3>', unsafe_allow_html=True)
        by_time = aggregate_fatalities_by_time_range(fatalities).head(8)
        if by_time.empty:
            st.info("Sin datos de horario para mostrar.")
        else:
            fig = bar_h(by_time, category="rango_3h", value="fallecidos", color=RISK, height=280)
            fig.update_layout(xaxis_title="Fallecidos")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with kind_col:
        st.markdown('<h3 class="panel-title">Clase de siniestro</h3>', unsafe_allow_html=True)
        crash_class = aggregate_fatalities_by_crash_class(fatalities).head(8)
        if crash_class.empty:
            st.info("Sin datos de clase de siniestro para mostrar.")
        else:
            fig = bar_h(
                crash_class,
                category="clase_accidente",
                value="fallecidos",
                color=MUTED,
                height=280,
            )
            fig.update_layout(xaxis_title="Fallecidos")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.markdown('<h3 class="panel-title">Perfil de las personas fallecidas</h3>', unsafe_allow_html=True)
    sex_col, age_col, actor_col = st.columns(3, gap="large")

    with sex_col:
        _render_profile_chart(_weighted_profile(fatalities, "sexo"), "Por sexo")
    with age_col:
        _render_profile_chart(_weighted_profile(fatalities, "rango_edad").head(8), "Por rango de edad")
    with actor_col:
        _render_profile_chart(_weighted_profile(fatalities, "actor_vial").head(8), "Por condición en la vía")

    render_caveat(
        "Los registros de mortalidad se contabilizan por persona fallecida en el "
        "registro oficial, no por comuna: esta sección no es filtrable por zona."
    )
    render_source_note(
        "Fuente: consolidado de muertes en accidentes de tránsito (datos.cali.gov.co) e INMLCF."
    )


def _year_month_matrix(fatalities: pd.DataFrame) -> pd.DataFrame:
    if fatalities.empty:
        return pd.DataFrame()
    matrix = (
        fatalities.pivot_table(
            index="ano",
            columns="mes",
            values="total_fallecidos",
            aggfunc="sum",
            fill_value=0,
        )
        .reindex(columns=range(1, 13), fill_value=0)
        .sort_index()
    )
    return matrix


def _weighted_profile(fatalities: pd.DataFrame, column: str) -> pd.DataFrame:
    """Count persons by a profile column, weighting aggregated rows."""
    if fatalities.empty or column not in fatalities.columns:
        return pd.DataFrame(columns=[column, "fallecidos"])
    known = fatalities[
        fatalities[column].notna() & (fatalities[column].astype(str) != "Sin información")
    ]
    if known.empty:
        return pd.DataFrame(columns=[column, "fallecidos"])
    return (
        known.groupby(column, dropna=False, observed=False)["total_fallecidos"]
        .sum()
        .reset_index(name="fallecidos")
        .sort_values("fallecidos", ascending=False)
        .reset_index(drop=True)
    )


def _render_profile_chart(frame: pd.DataFrame, title: str) -> None:
    """Small horizontal bar for a victim-profile dimension."""
    st.markdown(f'<p class="panel-title-stub">{escape(title)}</p>', unsafe_allow_html=True)
    if frame.empty:
        st.info("Sin información suficiente.")
        return
    fig = bar_h(frame, category=frame.columns[0], value="fallecidos", color=RISK, height=250)
    fig.update_layout(xaxis_title="Fallecidos")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})