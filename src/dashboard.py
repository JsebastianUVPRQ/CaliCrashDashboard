"""Streamlit dashboard composition for the Cali crash dashboard.

Orchestrates data loading, sidebar filters and the story sections defined in
:mod:`src.dashboard_sections`; keeps rendering helpers in their sections.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.config import DATA_CANDIDATES, FATALITY_DATA_DIR, TIME_BAND_ORDER
from src.dashboard_sections import (
    render_composicion,
    render_detalle,
    render_fatal,
    render_mortalidad,
    render_resumen,
    render_riesgo,
    render_temporal,
    render_territorial,
)
from src.dashboard_sections.temporal import (
    TemporalSummary,
    _build_temporal_summary,
    _daily_counts,
    _daily_variation_label,
    _hourly_insight,
)
from src.dashboard_sections.ui import render_nav_bar, render_source_note
from src.etl import build_sample_accidents, normalize_accident_data, read_csv_flexible
from src.fallecidos import load_fatality_data
from src.mapa import build_accident_map
from src.metrics import filter_accidents, severity_filter_values
from src.theme import DASHBOARD_CSS


@dataclass(frozen=True)
class DashboardFilters:
    """Selected dashboard filters."""

    comunas: list[str]
    direcciones: list[str]
    franjas_horarias: list[str]
    tipos_accidente: list[str]
    gravedades: list[str]
    date_range: tuple[date, date] | list[date] | None
    show_heatmap: bool
    fatal_heat: bool


PRESET_SEVERITY = {
    "Solo fallecidos": "fatal",
    "Solo lesionados": "lesionado",
    "Solo daños": "daños",
}

NAV_CHIPS = [
    ("Resumen", "resumen"),
    ("Geografía", "geografia"),
    ("Temporal", "temporal"),
    ("Composición", "composicion"),
    ("Fatalidad", "fatalidad"),
    ("Vidas perdidas", "mortalidad"),
    ("Riesgos", "riesgos"),
]


def render_dashboard() -> None:
    """Render the full Streamlit app."""
    st.set_page_config(
        page_title="Siniestralidad vial — Cali",
        page_icon="🚦",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

    accidents, raw_accidents = _load_data_with_raw()
    fatalities = _load_fatalities()

    _render_header(accidents)
    if accidents.empty:
        st.warning("No hay registros válidos para visualizar.")
        st_folium(
            build_accident_map(accidents),
            use_container_width=True,
            height=560,
            key="mapa_vacio",
            returned_objects=[],
        )
        return

    filters = _render_filters(accidents)
    filtered = filter_accidents(
        accidents,
        comunas=filters.comunas,
        direcciones=filters.direcciones,
        franjas_horarias=filters.franjas_horarias,
        tipos_accidente=filters.tipos_accidente,
        gravedades=filters.gravedades,
        date_range=filters.date_range,
    )

    render_nav_bar(NAV_CHIPS)
    render_resumen(filtered)
    render_territorial(
        filtered,
        show_heatmap=filters.show_heatmap,
        fatal_heat=filters.fatal_heat,
    )
    render_temporal(filtered)
    render_composicion(filtered)
    render_fatal(filtered)
    render_mortalidad(fatalities)
    render_riesgo(filtered)
    render_detalle(filtered, accidents, raw_accidents, fatalities)
    render_source_note()


@st.cache_data(show_spinner=False)
def _load_data_with_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    for path in DATA_CANDIDATES:
        if path.exists():
            suffix = path.suffix.lower()
            if suffix == ".parquet":
                raw = pd.read_parquet(path)
            else:
                raw = read_csv_flexible(path)
            return normalize_accident_data(raw), raw

    sample = build_sample_accidents()
    return normalize_accident_data(sample), sample


@st.cache_data(show_spinner=False)
def _load_fatalities() -> pd.DataFrame:
    return load_fatality_data(FATALITY_DATA_DIR)


def _render_header(accidents: pd.DataFrame) -> None:
    min_date = accidents["fecha"].min().date() if not accidents.empty else "sin datos"
    max_date = accidents["fecha"].max().date() if not accidents.empty else "sin datos"
    st.markdown(
        f"""
        <section class="app-header">
            <div>
                <p class="eyebrow">Observatorio de movilidad urbana</p>
                <h1>Siniestralidad vial — Cali</h1>
            </div>
            <div class="date-range">{min_date} · {max_date}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_filters(accidents: pd.DataFrame) -> DashboardFilters:
    with st.sidebar:
        st.markdown("### Filtros")
        preset = st.radio(
            "Vista rápida",
            list(PRESET_SEVERITY) + ["Todo"],
            index=3,
            help="Atajo para enfocar la vista en una gravedad concreta.",
        )

        comunas = _sorted_known_unique(accidents, "comuna")
        selected_comunas = (
            st.multiselect("Comuna", comunas, default=comunas)
            if comunas
            else []
        )

        direcciones = _top_known_values(accidents, "interseccion", limit=250)
        selected_directions = st.multiselect(
            "Dirección / punto",
            direcciones,
            default=[],
            help="Dejar vacío para incluir todas las direcciones.",
        )

        available_bands = [
            band
            for band in TIME_BAND_ORDER
            if band in set(accidents["franja_horaria"].astype(str))
        ]
        selected_bands = st.multiselect(
            "Franja horaria",
            available_bands,
            default=available_bands,
        )

        tipos_accidente = _sorted_unique(accidents, "tipo_accidente")
        selected_types = st.multiselect(
            "Tipo de accidente",
            tipos_accidente,
            default=tipos_accidente,
        )

        if preset in PRESET_SEVERITY:
            preset_kind = PRESET_SEVERITY[preset]
            preset_values = severity_filter_values(accidents, preset_kind)
            st.multiselect(
                "Gravedad (fijada por vista rápida)",
                preset_values or ["(sin registros)"],
                default=preset_values,
                disabled=True,
            )
            selected_severities = preset_values
        else:
            gravedades = _sorted_unique(accidents, "gravedad")
            selected_severities = st.multiselect(
                "Gravedad",
                gravedades,
                default=gravedades,
            )

        min_date = accidents["fecha"].min().date()
        max_date = accidents["fecha"].max().date()
        selected_dates = st.date_input(
            "Rango de fechas",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        show_heatmap = st.toggle("Mapa de calor", value=True)
        fatal_heat = st.toggle(
            "Destacar calor de siniestros con fallecido",
            value=False,
            help="La capa de densidad usa únicamente los registros con fallecido.",
        )

        if st.button("Restablecer filtros", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    return DashboardFilters(
        comunas=selected_comunas,
        direcciones=selected_directions,
        franjas_horarias=selected_bands,
        tipos_accidente=selected_types,
        gravedades=selected_severities,
        date_range=selected_dates,
        show_heatmap=show_heatmap,
        fatal_heat=fatal_heat,
    )


def _sorted_unique(data: pd.DataFrame, column: str) -> list[str]:
    return sorted(data[column].dropna().astype(str).unique())


def _sorted_known_unique(data: pd.DataFrame, column: str) -> list[str]:
    if column not in data.columns:
        return []
    values = data[column].dropna().astype(str).str.strip()
    return sorted(values[_known_value_mask(values)].unique())


def _top_known_values(data: pd.DataFrame, column: str, limit: int) -> list[str]:
    if column not in data.columns:
        return []
    values = data[column].dropna().astype(str).str.strip()
    counts = values[_known_value_mask(values)].value_counts()
    return counts.head(limit).index.tolist()


def _known_value_mask(values: pd.Series) -> pd.Series:
    lowered = values.str.lower()
    return (
        values.ne("")
        & lowered.ne("sin dato")
        & lowered.ne("nan")
        & lowered.ne("none")
        & values.ne(".")
    )