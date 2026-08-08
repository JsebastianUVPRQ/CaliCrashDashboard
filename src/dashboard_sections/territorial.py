"""Territorial section: dangerous crossings ranking and concentration map."""

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.charts import stacked_bar_h
from src.dashboard_sections.ui import render_empty_state, render_section_header
from src.mapa import build_accident_map
from src.metrics import aggregate_by_intersection, canonical_severity, fatal_mask


def render_territorial(
    accidents: pd.DataFrame,
    *,
    show_heatmap: bool = True,
    fatal_heat: bool = False,
) -> None:
    """Render the most dangerous intersections section."""
    render_section_header(
        "geografia",
        "Geografía del siniestro",
        "Cruces peligrosos",
        "Ranking de las intersecciones con más registros y su mapa de concentración.",
    )

    by_intersection = aggregate_by_intersection(accidents)
    if by_intersection.empty:
        render_empty_state(
            "No hay direcciones válidas para analizar cruces peligrosos.",
            [
                "Revisar los filtros actuales.",
                "O ampliar la cobertura de direcciones en la fuente de datos.",
            ],
        )
        return

    has_geocoded = _has_geocoded_points(accidents)
    has_fatal = bool(fatal_mask(accidents).any())
    heat_scope = "fatal" if (fatal_heat and has_fatal) else "all"

    rank_col, map_col = st.columns((1.1, 2), gap="large")

    with rank_col:
        st.markdown('<h3 class="panel-title">Top 15 cruces</h3>', unsafe_allow_html=True)
        top = by_intersection.head(15).copy()
        total = int(top["accidentes"].sum())
        top["participacion"] = (top["accidentes"] / total * 100).map(
            lambda value: f"{value:.1f}%"
        )

        st.dataframe(
            top[["interseccion", "accidentes", "participacion"]],
            hide_index=True,
            width="stretch",
            column_config={
                "interseccion": st.column_config.TextColumn("Intersección"),
                "accidentes": st.column_config.ProgressColumn(
                    "Accidentes",
                    format="%d",
                    min_value=0,
                    max_value=int(top["accidentes"].max()) if not top.empty else 1,
                ),
                "participacion": st.column_config.TextColumn("Participación"),
            },
        )

        severity_by_hotspot = _severity_breakdown(accidents, by_intersection.head(5))
        if not severity_by_hotspot.empty:
            st.markdown('<h3 class="panel-title">Gravedad en el top 5</h3>', unsafe_allow_html=True)
            fig = stacked_bar_h(
                severity_by_hotspot,
                category="interseccion",
                value="accidentes",
                color_col="gravedad",
                height=240,
            )
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with map_col:
        st.markdown('<h3 class="panel-title">Mapa de concentración</h3>', unsafe_allow_html=True)
        if has_geocoded:
            accident_map = build_accident_map(
                accidents,
                show_heatmap=show_heatmap,
                heat_scope=heat_scope,
            )
            st_folium(
                accident_map,
                use_container_width=True,
                height=480,
                key="mapa_hotspots",
                returned_objects=[],
            )
        else:
            st.info(
                "La fuente actual no trae coordenadas. "
                "El ranking de cruces se calcula por dirección reportada."
            )


def _severity_breakdown(
    accidents: pd.DataFrame, top_intersections: pd.DataFrame
) -> pd.DataFrame:
    """Break down canonical severity counts for the given intersections."""
    columns = ["interseccion", "gravedad", "accidentes"]
    if accidents.empty or top_intersections.empty:
        return pd.DataFrame(columns=columns)

    top_names = set(top_intersections["interseccion"].astype(str))
    subset = accidents[accidents["interseccion"].astype(str).isin(top_names)]
    if subset.empty:
        return pd.DataFrame(columns=columns)

    grouped = subset.assign(gravedad=canonical_severity(subset["gravedad"])).dropna(
        subset=["gravedad"]
    )
    if grouped.empty:
        return pd.DataFrame(columns=columns)

    return (
        grouped.groupby(["interseccion", "gravedad"], dropna=False, observed=False)
        .size()
        .reset_index(name="accidentes")
        .sort_values("accidentes", ascending=False)
        .reset_index(drop=True)
    )


def _has_geocoded_points(accidents: pd.DataFrame) -> bool:
    if accidents.empty or {"latitud", "longitud"}.difference(accidents.columns):
        return False
    return bool(accidents[["latitud", "longitud"]].dropna().shape[0])