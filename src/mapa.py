"""Map builders for Cali traffic crash records."""

from html import escape

import folium
import pandas as pd
import pydeck as pdk
from folium.plugins import HeatMap
from folium.plugins import MarkerCluster

from src.config import CALI_CENTER

MAP_COLUMNS = [
    "latitud",
    "longitud",
    "comuna",
    "barrio",
    "tipo_accidente",
    "gravedad",
    "fecha",
    "hora",
]

DECK_MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
CLUSTER_CELL_DEGREES = 0.006
ZONE_LABELS = pd.DataFrame(
    [
        {"zona": "Norte", "latitud": 3.500, "longitud": -76.515},
        {"zona": "Oeste / Ladera", "latitud": 3.455, "longitud": -76.590},
        {"zona": "Centro", "latitud": 3.451, "longitud": -76.535},
        {"zona": "Oriente", "latitud": 3.455, "longitud": -76.495},
        {"zona": "Distrito Aguablanca", "latitud": 3.425, "longitud": -76.475},
        {"zona": "Sur", "latitud": 3.382, "longitud": -76.532},
        {"zona": "Pance", "latitud": 3.340, "longitud": -76.555},
    ]
)


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


def build_accident_deck(
    accidents: pd.DataFrame,
    show_heatmap: bool = True,
) -> pdk.Deck:
    """Build a WebGL accident map using all filtered geocoded points."""
    map_data = prepare_deck_map_data(accidents)
    cluster_data = prepare_cluster_map_data(map_data)
    layers: list[pdk.Layer] = []

    if not map_data.empty and show_heatmap:
        heatmap_data = map_data[["latitud", "longitud"]]
        layers.append(
            pdk.Layer(
                "HeatmapLayer",
                data=heatmap_data,
                get_position="[longitud, latitud]",
                aggregation="SUM",
                get_weight=1,
                radius_pixels=45,
                intensity=1,
                threshold=0.05,
                pickable=False,
                opacity=0.32,
            )
        )

    if not map_data.empty:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=map_data,
                get_position="[longitud, latitud]",
                get_fill_color="point_color",
                get_radius=26,
                radius_min_pixels=1,
                radius_max_pixels=5,
                stroked=False,
                filled=True,
                pickable=True,
                auto_highlight=True,
            )
        )

    if not cluster_data.empty:
        layers.extend(
            [
                pdk.Layer(
                    "ScatterplotLayer",
                    data=cluster_data,
                    get_position="[longitud, latitud]",
                    get_fill_color="cluster_color",
                    get_line_color=[248, 250, 252, 195],
                    get_radius="cluster_radius",
                    radius_min_pixels=12,
                    radius_max_pixels=52,
                    line_width_min_pixels=1,
                    stroked=True,
                    filled=True,
                    pickable=True,
                    auto_highlight=True,
                ),
                pdk.Layer(
                    "TextLayer",
                    data=cluster_data[cluster_data["accidentes"].ge(8)],
                    get_position="[longitud, latitud]",
                    get_text="cluster_label",
                    get_color=[15, 23, 42, 245],
                    get_size=13,
                    get_alignment_baseline="'center'",
                    get_text_anchor="'middle'",
                    pickable=False,
                ),
            ]
        )

    layers.append(
        pdk.Layer(
            "TextLayer",
            data=ZONE_LABELS,
            get_position="[longitud, latitud]",
            get_text="zona",
            get_color=[226, 232, 240, 220],
            get_size=15,
            get_alignment_baseline="'center'",
            get_text_anchor="'middle'",
            get_background_color=[15, 23, 42, 150],
            background=True,
            background_padding=[7, 4],
            pickable=False,
        )
    )

    return pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            latitude=CALI_CENTER[0],
            longitude=CALI_CENTER[1],
            zoom=11.5,
            pitch=0,
        ),
        map_style=DECK_MAP_STYLE,
        tooltip={
            "html": (
                "<b>{tooltip_title}</b><br/>"
                "{tooltip_detail}"
            ),
            "style": {
                "backgroundColor": "rgba(15, 23, 42, 0.94)",
                "color": "#f8fafc",
                "fontFamily": "Inter, Segoe UI, sans-serif",
                "fontSize": "12px",
                "padding": "10px",
            },
        },
    )


def prepare_deck_map_data(accidents: pd.DataFrame) -> pd.DataFrame:
    """Return serializable, geocoded accident data for PyDeck layers."""
    if accidents.empty or {"latitud", "longitud"}.difference(accidents.columns):
        return pd.DataFrame(columns=[*MAP_COLUMNS, "color"])

    available_columns = [column for column in MAP_COLUMNS if column in accidents.columns]
    map_data = accidents.dropna(subset=["latitud", "longitud"])[available_columns].copy()
    if map_data.empty:
        return pd.DataFrame(columns=[*MAP_COLUMNS, "color"])

    for column in MAP_COLUMNS:
        if column not in map_data.columns:
            map_data[column] = "Sin dato"

    map_data["latitud"] = pd.to_numeric(map_data["latitud"], errors="coerce")
    map_data["longitud"] = pd.to_numeric(map_data["longitud"], errors="coerce")
    map_data = map_data.dropna(subset=["latitud", "longitud"]).reset_index(drop=True)
    if map_data.empty:
        return pd.DataFrame(columns=[*MAP_COLUMNS, "color"])

    map_data["fecha"] = pd.to_datetime(
        map_data["fecha"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")
    map_data["fecha"] = map_data["fecha"].fillna("Sin dato")
    text_columns = ["comuna", "barrio", "tipo_accidente", "gravedad", "hora"]
    for column in text_columns:
        map_data[column] = map_data[column].fillna("Sin dato").astype(str)

    map_data["color"] = map_data["gravedad"].map(_severity_color).tolist()
    map_data["point_color"] = map_data["gravedad"].map(_point_color).tolist()
    map_data["tooltip_title"] = map_data["tipo_accidente"]
    map_data["tooltip_detail"] = (
        map_data["fecha"]
        + " · "
        + map_data["hora"]
        + "<br/>Comuna <b>"
        + map_data["comuna"]
        + "</b><br/>Barrio: "
        + map_data["barrio"]
        + "<br/>Gravedad: "
        + map_data["gravedad"]
    )
    return map_data[
        [
            *MAP_COLUMNS,
            "color",
            "point_color",
            "tooltip_title",
            "tooltip_detail",
        ]
    ]


def prepare_cluster_map_data(map_data: pd.DataFrame) -> pd.DataFrame:
    """Aggregate accidents into readable fixed-grid clusters for the default view."""
    columns = [
        "latitud",
        "longitud",
        "accidentes",
        "cluster_label",
        "cluster_radius",
        "cluster_color",
        "tooltip_title",
        "tooltip_detail",
    ]
    if map_data.empty:
        return pd.DataFrame(columns=columns)

    clustered = map_data.assign(
        lat_cell=(map_data["latitud"] / CLUSTER_CELL_DEGREES).round(),
        lon_cell=(map_data["longitud"] / CLUSTER_CELL_DEGREES).round(),
    )
    grouped = (
        clustered.groupby(["lat_cell", "lon_cell"], as_index=False)
        .agg(
            latitud=("latitud", "mean"),
            longitud=("longitud", "mean"),
            accidentes=("latitud", "size"),
        )
        .sort_values("accidentes", ascending=False)
        .reset_index(drop=True)
    )
    grouped["cluster_label"] = grouped["accidentes"].map(_format_cluster_label)
    grouped["cluster_radius"] = grouped["accidentes"].map(_cluster_radius)
    grouped["cluster_color"] = grouped["accidentes"].map(_cluster_color).tolist()
    grouped["tooltip_title"] = grouped["accidentes"].map(
        lambda count: f"{count:,} accidentes"
    )
    grouped["tooltip_detail"] = (
        "Cluster territorial de aproximadamente 650 m. "
        "Acercar el zoom separa los puntos individuales de esta zona."
    )
    return grouped[columns]


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


def _severity_color(value: object) -> list[int]:
    severity = str(value).lower()
    if any(token in severity for token in ["muert", "fatal", "fallecid"]):
        return [239, 68, 68, 210]
    if any(token in severity for token in ["herid", "lesion"]):
        return [245, 158, 11, 205]
    if any(token in severity for token in ["daño", "dano", "material"]):
        return [56, 189, 248, 190]
    return [148, 163, 184, 170]


def _point_color(value: object) -> list[int]:
    red, green, blue, _ = _severity_color(value)
    return [red, green, blue, 115]


def _cluster_radius(count: int) -> int:
    return int(min(980, max(120, 75 + (float(count) ** 0.5 * 18))))


def _cluster_color(count: int) -> list[int]:
    if count >= 1000:
        return [239, 68, 68, 205]
    if count >= 350:
        return [245, 158, 11, 205]
    if count >= 100:
        return [34, 197, 94, 190]
    return [56, 189, 248, 180]


def _format_cluster_label(count: int) -> str:
    if count >= 1000:
        return f"{count / 1000:.1f}k"
    return str(count)
