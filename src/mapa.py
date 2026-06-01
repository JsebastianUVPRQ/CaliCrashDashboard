"""Folium map builders for Cali traffic crash records."""

from html import escape

import folium
import pandas as pd
from folium.plugins import HeatMap
from folium.plugins import MarkerCluster

from src.config import CALI_CENTER


def build_accident_map(
    accidents: pd.DataFrame,
    show_heatmap: bool = True,
    max_markers: int = 20000,
) -> folium.Map:
    """Build an interactive map centered in Cali with accident markers."""
    crash_map = folium.Map(
        location=CALI_CENTER,
        zoom_start=12,
        tiles="CartoDB dark_matter",
        control_scale=True,
    )

    if accidents.empty:
        return crash_map

    geocoded_accidents = accidents.dropna(subset=["latitud", "longitud"])
    if geocoded_accidents.empty:
        _add_missing_coordinates_notice(crash_map, len(accidents))
        folium.LayerControl().add_to(crash_map)
        return crash_map

    if show_heatmap:
        heat_points = geocoded_accidents[["latitud", "longitud"]].values.tolist()
        if heat_points:
            HeatMap(
                heat_points,
                name="Densidad",
                radius=20,
                blur=18,
                min_opacity=0.18,
                gradient={
                    0.20: "#38bdf8",
                    0.45: "#22c55e",
                    0.70: "#f59e0b",
                    1.00: "#ef4444",
                },
            ).add_to(crash_map)

    marker_cluster = MarkerCluster(name="Accidentes").add_to(crash_map)
    
    marker_data = geocoded_accidents
    if len(marker_data) > max_markers:
        marker_data = marker_data.sample(n=max_markers, random_state=42)

    for accident in marker_data.itertuples(index=False):
        popup = folium.Popup(
            _popup_html(
                comuna=str(accident.comuna),
                barrio=str(accident.barrio),
                tipo=str(accident.tipo_accidente),
                gravedad=str(accident.gravedad),
                fecha=str(accident.fecha.date()),
                hora=str(accident.hora),
            ),
            max_width=280,
        )
        folium.CircleMarker(
            location=(float(accident.latitud), float(accident.longitud)),
            radius=4,
            color="#0f172a",
            weight=1,
            fill=True,
            fill_color="#f59e0b",
            fill_opacity=0.84,
            popup=popup,
        ).add_to(marker_cluster)

    folium.LayerControl().add_to(crash_map)
    return crash_map


def _add_missing_coordinates_notice(crash_map: folium.Map, total_records: int) -> None:
    """Show a visible map state when records are not geocoded."""
    folium.Marker(
        location=CALI_CENTER,
        icon=folium.DivIcon(
            html=f"""
            <div style="
                background: rgba(15, 23, 42, 0.94);
                border: 1px solid rgba(245, 158, 11, 0.55);
                border-left: 4px solid #f59e0b;
                border-radius: 8px;
                color: #f8fafc;
                font-family: Inter, Segoe UI, sans-serif;
                line-height: 1.35;
                padding: 12px 14px;
                width: 280px;
                box-shadow: 0 12px 30px rgba(0,0,0,.35);
            ">
                <strong>Mapa sin puntos georreferenciados</strong>
                <div style="color:#cbd5e1; font-size:12px; margin-top:4px;">
                    Los {total_records:,} registros filtrados no tienen latitud/longitud.
                    Las métricas se calculan, pero el mapa requiere coordenadas.
                </div>
            </div>
            """,
        ),
    ).add_to(crash_map)


def _popup_html(
    comuna: str,
    barrio: str,
    tipo: str,
    gravedad: str,
    fecha: str,
    hora: str,
) -> str:
    safe_tipo = escape(tipo)
    safe_fecha = escape(fecha)
    safe_hora = escape(hora)
    safe_comuna = escape(comuna)
    safe_barrio = escape(barrio)
    safe_gravedad = escape(gravedad)

    return f"""
    <div style="font-family: Inter, Segoe UI, sans-serif; min-width: 190px;">
        <div style="font-weight: 700; font-size: 14px; margin-bottom: 6px;">
            {safe_tipo}
        </div>
        <div style="color: #475569; font-size: 12px; margin-bottom: 6px;">
            {safe_fecha} · {safe_hora}
        </div>
        <div style="font-size: 12px;">Comuna <strong>{safe_comuna}</strong></div>
        <div style="font-size: 12px;">Barrio: {safe_barrio}</div>
        <div style="font-size: 12px;">Gravedad: {safe_gravedad}</div>
    </div>
    """
