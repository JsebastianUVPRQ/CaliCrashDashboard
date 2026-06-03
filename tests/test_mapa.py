import pandas as pd
import pydeck as pdk

from src.mapa import (
    build_accident_deck,
    prepare_cluster_map_data,
    prepare_deck_map_data,
)


def _sample_accidents() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fecha": pd.to_datetime(["2025-01-01", "2025-01-02", None]),
            "hora": ["08:15", "21:30", "10:00"],
            "latitud": [3.45, None, 3.43],
            "longitud": [-76.53, -76.52, -76.51],
            "comuna": ["2", "17", "Sin dato"],
            "barrio": ["Granada", "El Limonar", None],
            "tipo_accidente": ["Choque", "Atropello", "Volcamiento"],
            "gravedad": ["Solo daños", "Herido", "Fatal"],
        }
    )


def test_prepare_deck_map_data_filters_null_coordinates_and_serializes_dates() -> None:
    result = prepare_deck_map_data(_sample_accidents())

    assert len(result) == 2
    assert result["fecha"].tolist() == ["2025-01-01", "Sin dato"]
    assert result["latitud"].notna().all()
    assert result["longitud"].notna().all()
    assert result.columns.tolist() == [
        "latitud",
        "longitud",
        "comuna",
        "barrio",
        "tipo_accidente",
        "gravedad",
        "fecha",
        "hora",
        "color",
        "point_color",
        "tooltip_title",
        "tooltip_detail",
    ]


def test_prepare_deck_map_data_assigns_colors_by_severity() -> None:
    result = prepare_deck_map_data(_sample_accidents())

    assert result.loc[0, "color"] == [56, 189, 248, 190]
    assert result.loc[1, "color"] == [239, 68, 68, 210]
    assert result.loc[0, "point_color"] == [56, 189, 248, 115]


def test_prepare_cluster_map_data_aggregates_nearby_points() -> None:
    map_data = prepare_deck_map_data(
        pd.DataFrame(
            {
                "fecha": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-01"]),
                "hora": ["08:00", "08:05", "09:00"],
                "latitud": [3.4500, 3.4505, 3.5000],
                "longitud": [-76.5300, -76.5305, -76.5000],
                "comuna": ["2", "2", "4"],
                "barrio": ["A", "A", "B"],
                "tipo_accidente": ["Choque", "Choque", "Atropello"],
                "gravedad": ["Solo daños", "Solo daños", "Herido"],
            }
        )
    )

    result = prepare_cluster_map_data(map_data)

    assert result["accidentes"].tolist() == [2, 1]
    assert result.loc[0, "cluster_label"] == "2"
    assert result.loc[0, "cluster_radius"] >= result.loc[1, "cluster_radius"]


def test_build_accident_deck_returns_heatmap_points_clusters_and_zone_labels() -> None:
    result = build_accident_deck(_sample_accidents(), show_heatmap=True)

    assert isinstance(result, pdk.Deck)
    assert [layer.type for layer in result.layers] == [
        "HeatmapLayer",
        "ScatterplotLayer",
        "ScatterplotLayer",
        "TextLayer",
        "TextLayer",
    ]


def test_build_accident_deck_can_disable_heatmap() -> None:
    result = build_accident_deck(_sample_accidents(), show_heatmap=False)

    assert [layer.type for layer in result.layers] == [
        "ScatterplotLayer",
        "ScatterplotLayer",
        "TextLayer",
        "TextLayer",
    ]


def test_build_accident_deck_handles_empty_data() -> None:
    result = build_accident_deck(_sample_accidents().iloc[0:0])

    assert isinstance(result, pdk.Deck)
    assert [layer.type for layer in result.layers] == ["TextLayer"]
