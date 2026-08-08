"""Technical detail section: import quality control and data exports."""

import pandas as pd
import streamlit as st

from src.config import FATALITY_DATA_DIR
from src.etl import data_quality_report
from src.fallecidos import load_fatality_frames, reconcile_fatality_sources


def render_detalle(
    filtered: pd.DataFrame,
    clean_full: pd.DataFrame,
    raw_full: pd.DataFrame,
    fatalities: pd.DataFrame,
) -> None:
    """Render the collapsed technical detail with quality checks and exports."""
    with st.expander("Ver detalle técnico y control de calidad", expanded=False):
        st.markdown("### Control de calidad de importación")
        quality = data_quality_report(raw_full, clean_full)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Registros cargados", f"{quality.total_raw:,}")
        col2.metric("Registros válidos", f"{quality.total_clean:,}")
        col3.metric("Fechas inválidas", f"{quality.null_fecha:,}")
        col4.metric(
            "Coordenadas inválidas (o fuera de Cali)",
            f"{quality.null_coords + quality.out_of_bounds:,}",
        )

        if quality.out_of_bounds > 0:
            st.caption(
                f"ℹ️ {quality.out_of_bounds:,} registros fueron filtrados por estar "
                "fuera de los límites geográficos de Cali."
            )

        st.write("---")
        st.markdown("### Descargas")
        export_col, _spacer = st.columns(2)
        with export_col:
            st.download_button(
                "Descargar datos filtrados (CSV)",
                data=filtered.to_csv(index=False).encode("utf-8"),
                file_name="siniestros_filtrados.csv",
                mime="text/csv",
            )

        if not fatalities.empty:
            st.markdown("#### Registro de mortalidad (personas fallecidas)")
            consolidated, snapshots = load_fatality_frames(FATALITY_DATA_DIR)
            reconciliation = reconcile_fatality_sources(
                [consolidated, snapshots]
            )
            st.dataframe(reconciliation, hide_index=True, width="stretch")
            st.download_button(
                "Descargar mortalidad filtrada (CSV)",
                data=fatalities.to_csv(index=False).encode("utf-8"),
                file_name="mortalidad_filtrada.csv",
                mime="text/csv",
            )