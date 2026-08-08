"""Risk model section: expected daily frequency by commune and time band."""

import pandas as pd
import streamlit as st

from src.charts import risk_matrix
from src.dashboard_sections.ui import render_empty_state, render_section_header, render_source_note
from src.modelo import estimate_frequency


def render_riesgo(accidents: pd.DataFrame) -> None:
    """Render the risk model section (observational baseline)."""
    render_section_header(
        "riesgos",
        "Modelo de frecuencia",
        "Riesgo esperado por zona y franja horaria",
        "Frecuencia diaria esperada por comuna y franja horaria, estimada con un "
        "modelo de Poisson sobre promedios históricos del período filtrado "
        "(intervalo de confianza del 95 %).",
    )

    frequency = estimate_frequency(accidents)
    if frequency.empty:
        render_empty_state(
            "No hay suficiente información para modelar la frecuencia esperada.",
            [
                "Revisar los filtros de comuna y fechas.",
                "El modelo requiere al menos una comuna con fechas válidas.",
            ],
        )
        return

    fig = risk_matrix(
        frequency,
        index="comuna",
        columns="franja_horaria",
        values="frecuencia_diaria_esperada",
    )
    fig.update_layout(xaxis_title="Franja horaria", yaxis_title="Comuna")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    legend_col, _note_col = st.columns((1, 2), gap="large")
    with legend_col:
        st.markdown(
            f"""
            <div class="severity-key">
                <span><span class="swatch" style="background:#152238"></span>bajo</span>
                <span><span class="swatch" style="background:#f59e0b"></span>medio</span>
                <span><span class="swatch" style="background:#ef4444"></span>alto</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("Ver tabla de frecuencias por comuna y franja", expanded=False):
        st.dataframe(
            frequency,
            hide_index=True,
            width="stretch",
            column_config={
                "comuna": st.column_config.TextColumn("Comuna"),
                "franja_horaria": st.column_config.TextColumn("Franja horaria"),
                "accidentes_observados": st.column_config.NumberColumn("Observados", format="%d"),
                "dias_observados": st.column_config.NumberColumn("Días", format="%d"),
                "frecuencia_diaria_esperada": st.column_config.NumberColumn(
                    "Frecuencia diaria", format="%.2f"
                ),
                "intervalo_inferior": st.column_config.NumberColumn("IC 95 % inf.", format="%.2f"),
                "intervalo_superior": st.column_config.NumberColumn("IC 95 % sup.", format="%.2f"),
                "nivel_riesgo": st.column_config.TextColumn("Nivel de riesgo"),
            },
        )
        st.download_button(
            "Descargar estimación (CSV)",
            data=frequency.to_csv(index=False).encode("utf-8"),
            file_name="frecuencia_esperada.csv",
            mime="text/csv",
        )

    render_source_note(
        "Modelo base de referencia: promedio histórico con intervalo de confianza "
        "Poisson; no constituye un pronóstico."
    )