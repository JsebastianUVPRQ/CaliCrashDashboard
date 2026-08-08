"""Composition section: vehicle, accident type and severity distribution."""

import pandas as pd
import streamlit as st

from src.charts import bar_h, stacked_bar_h
from src.dashboard_sections.ui import render_section_header
from src.metrics import (
    aggregate_by_vehicle_and_severity,
    aggregate_by_vehicle_type,
    canonical_severity,
    severity_counts,
)
from src.theme import ACCENT, DATA, severity_color


def render_composicion(accidents: pd.DataFrame) -> None:
    """Render vehicle type, accident type and severity composition."""
    render_section_header(
        "composicion",
        "Composición del parque afectado",
        "Qué se ve involucrado y con qué gravedad",
        "Tipos de vehículo, clases de siniestro y severidad de los registros filtrados.",
    )

    if "tipo_vehiculo" not in accidents.columns:
        st.info("El dataset actual no incluye la columna tipo_vehiculo.")
        return

    vehicle_col, type_col = st.columns(2, gap="large")

    with vehicle_col:
        st.markdown(
            '<h3 class="panel-title">Siniestros por tipo de vehículo</h3>',
            unsafe_allow_html=True,
        )
        by_vehicle = aggregate_by_vehicle_type(accidents).head(10)
        if by_vehicle.empty:
            st.info("Sin datos de vehículo para mostrar.")
        else:
            fig = bar_h(
                by_vehicle,
                category="tipo_vehiculo",
                value="accidentes",
                color=DATA,
                height=300,
            )
            fig.update_layout(yaxis_title="Accidentes")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

        st.markdown(
            '<h3 class="panel-title">Vehículo × Gravedad</h3>',
            unsafe_allow_html=True,
        )
        vehicle_severity = _canonical_vehicle_severity(accidents)
        if vehicle_severity.empty:
            st.info("Sin datos de vehículo × gravedad para mostrar.")
        else:
            fig = stacked_bar_h(
                vehicle_severity,
                category="tipo_vehiculo",
                value="accidentes",
                color_col="gravedad",
                height=280,
            )
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with type_col:
        st.markdown(
            '<h3 class="panel-title">Siniestros por tipo de suceso</h3>',
            unsafe_allow_html=True,
        )
        if "tipo_accidente" in accidents.columns:
            by_type = (
                accidents.groupby("tipo_accidente", dropna=False, observed=False)
                .size()
                .reset_index(name="accidentes")
                .sort_values("accidentes", ascending=False)
                .head(10)
            )
            if by_type.empty:
                st.info("Sin datos de tipo de siniestro para mostrar.")
            else:
                fig = bar_h(
                    by_type,
                    category="tipo_accidente",
                    value="accidentes",
                    color=ACCENT,
                    height=300,
                )
                fig.update_layout(yaxis_title="Accidentes")
                st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        else:
            st.info("El dataset actual no incluye la columna tipo_accidente.")

        st.markdown(
            '<h3 class="panel-title">Distribución por gravedad</h3>',
            unsafe_allow_html=True,
        )
        by_severity = severity_counts(accidents)
        if by_severity.empty:
            st.info("Sin datos de gravedad para mostrar.")
        else:
            _render_severity_breakdown(accidents, by_severity)


def _canonical_vehicle_severity(accidents: pd.DataFrame) -> pd.DataFrame:
    """Vehicle × canonical severity with the full severity ramp."""
    columns = ["tipo_vehiculo", "gravedad", "accidentes"]
    if accidents.empty:
        return pd.DataFrame(columns=columns)

    known = accidents[accidents["tipo_vehiculo"].notna()].copy()
    if known.empty:
        return pd.DataFrame(columns=columns)
    known["gravedad"] = canonical_severity(known["gravedad"])
    known = known.dropna(subset=["gravedad"])
    if known.empty:
        return pd.DataFrame(columns=columns)

    return (
        known.groupby(["tipo_vehiculo", "gravedad"], dropna=False, observed=False)
        .size()
        .reset_index(name="accidentes")
        .sort_values(["accidentes", "tipo_vehiculo"], ascending=False)
        .reset_index(drop=True)
    )


def _render_severity_breakdown(accidents: pd.DataFrame, by_severity: pd.DataFrame) -> None:
    """Severity bar with fixed ramp colors (readable across hues)."""
    fig = bar_h(
        by_severity,
        category="gravedad",
        value="accidentes",
        color=None,
        height=280,
    )
    fig.update_layout(yaxis_title="Accidentes")
    fig.update_traces(
        marker_color=[
            severity_color(label) for label in by_severity["gravedad"].astype(str)
        ]
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})