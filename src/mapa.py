"""Folium map builders for Cali traffic crash records."""

from html import escape

import folium
import pandas as pd
from folium.plugins import HeatMap
from folium.plugins import MarkerCluster

from src.config import CALI_CENTER
from src.metrics import fatal_mask
from src.theme import MUTED, SEVERITY_RAMP_ORDER, severity_color


def build_accident_map(
    accidents: pd.DataFrame,
    *,
    show_heatmap: bool = True,
    heat_scope: str = "all",
) -> folium.Map:
    """Build an interactive map centered in Cali with accident markers.

    Args:
        accidents: Normalized accident records with ``latitud``/``longitud``.
        show_heatmap: Render the density heat layer.
        heat_scope: ``"all"`` or ``"fatal"`` (heat over fatal records only).

    Returns:
        A Folium map with a severity-colored marker cluster and a legend.
    """
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
        if heat_scope == "fatal":
            heat_points = geocoded_accidents.loc[
                fatal_mask(geocoded_accidents), ["latitud", "longitud"]
            ].values.tolist()
        else:
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

    # Sample markers if dataset is large to prevent browser freeze/crash
    marker_data = geocoded_accidents
    if len(marker_data) > 1500:
        marker_data = marker_data.sample(n=min(1500, len(marker_data)), random_state=42)

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
            fill_color=severity_color(accident.gravedad),
            fill_opacity=0.84,
            popup=popup,
        ).add_to(marker_cluster)

    folium.LayerControl().add_to(crash_map)
    _add_severity_legend(crash_map)
    return crash_map


def _add_severity_legend(crash_map: folium.Map) -> None:
    """Inject a compact severity legend into the map corner."""
    items = "".join(
        f'<li><span style="background:{severity_color(label)}"></span>{escape(label)}</li>'
        for label in SEVERITY_RAMP_ORDER
    )
    html = f"""
    <div style="
        position: absolute; left: 10px; bottom: 24px; z-index: 800;
        background: rgba(15, 23, 42, 0.94);
        border: 1px solid rgba(148, 163, 184, 0.3);
        border-radius: 8px; padding: 8px 12px;
        font-family: Inter, Segoe UI, sans-serif; font-size: 11px;
        color: #e2e8f0; box-shadow: 0 10px 24px rgba(0,0,0,.35);
    ">
        <div style="font-weight:700; margin-bottom:5px; color:#94a3b8;
                    text-transform:uppercase; font-size:10px; letter-spacing:.06em;">
            Gravedad
        </div>
        <ul style="list-style:none; margin:0; padding:0;">
            {items}
        </ul>
    </div>
    """
    crash_map.get_root().html.add_child(folium.Element(html))


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