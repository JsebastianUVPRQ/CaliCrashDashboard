import math
from pathlib import Path

import pandas as pd
import pytest

from src.etl import CALI_LAT_RANGE, CALI_LON_RANGE
from src.geocode import (
    ANCHORS_CSV,
    LUGARES_CSV,
    _method_of,
    _usable_place_key,
    build_default_lugares,
    build_default_model,
    calibrate_grid,
    canonical_key,
    geocode_intersection,
    geocode_series,
    normalize_intersection,
    parse_intersection,
    parse_via,
    load_lugares,
)

PROCESSED_CSV = Path("data/processed/geocoded_intersections.parquet")


def _in_range(lat: float | None, lon: float | None) -> bool:
    if lat is None or lon is None:
        return False
    return bool(
        CALI_LAT_RANGE[0] <= lat <= CALI_LAT_RANGE[1]
        and CALI_LON_RANGE[0] <= lon <= CALI_LON_RANGE[1]
    )


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------

def test_normalize_intersection_expands_abbreviations() -> None:
    assert normalize_intersection("CRA. 8 y CL 70") == "CARRERA 8 CON CALLE 70"


def test_normalize_intersection_removes_accents_and_uppercases() -> None:
    assert normalize_intersection("Calle 60 Con Avenida 3 Norte") == "CALLE 60 CON AVENIDA 3 NORTE"


def test_normalize_intersection_fixes_mojibake() -> None:
    assert normalize_intersection("CL?NICA COLOMBIA") == "CLINICA COLOMBIA"


def test_normalize_intersection_handles_connectors_and_punctuation() -> None:
    assert normalize_intersection("CALLE 70 & CARRERA 5") == "CALLE 70 CON CARRERA 5"
    assert normalize_intersection("Calle 25 - Carrera 109") == "CALLE 25 CON CARRERA 109"


def test_normalize_intersection_returns_empty_for_null() -> None:
    assert normalize_intersection(None) == ""
    assert normalize_intersection(pd.NA) == ""
    assert normalize_intersection(float("nan")) == ""


def test_normalize_intersection_keeps_letter_suffixes() -> None:
    assert normalize_intersection("Calle 70 con Carrera 1A5") == "CALLE 70 CON CARRERA 1A5"


# ---------------------------------------------------------------------------
# Parseo de vías
# ---------------------------------------------------------------------------

def test_parse_via_street_with_letter() -> None:
    assert parse_via("CARRERA 8 A") == ("CARRERA", 8, "A", "")


def test_parse_via_avenue_with_cardinal_suffix() -> None:
    assert parse_via("AVENIDA 3 NORTE") == ("AVENIDA", 3, "", "NORTE")


def test_parse_via_direction_letter_becomes_suffix() -> None:
    assert parse_via("AVENIDA 6N") == ("AVENIDA", 6, "", "NORTE")


def test_parse_via_rejects_unparseable_forms() -> None:
    assert parse_via("CARRERA") is None
    assert parse_via("RUTA 47") is None
    assert parse_via("") is None


def test_parse_intersection_returns_pair() -> None:
    parsed = parse_intersection("Calle 10 Con Carrera 39")
    assert parsed == (("CALLE", 10, "", ""), ("CARRERA", 39, "", ""))


def test_parse_intersection_rejects_named_places() -> None:
    assert parse_intersection("CLINICA COLOMBIA") is None


def test_parse_intersection_rejects_garbage() -> None:
    assert parse_intersection("Seleccione una opcion") is None
    assert parse_intersection("KM 12 VIA AL MAR") is None
    assert parse_intersection(None) is None


def test_canonical_key_is_order_independent() -> None:
    left = parse_intersection("Calle 10 Con Carrera 39")
    right = parse_intersection("Carrera 39 Con Calle 10")
    assert left is not None and right is not None
    assert canonical_key(left) == canonical_key(right)
    assert canonical_key(left) == "CALLE 10 CON CARRERA 39"


# ---------------------------------------------------------------------------
# Calibración y modelo por defecto
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not ANCHORS_CSV.exists(), reason="anclas OSM no disponibles")
def test_calibrate_grid_fits_zones_from_anchors() -> None:
    anchors = pd.read_csv(ANCHORS_CSV)
    model = calibrate_grid(anchors)
    assert model.n_anchors > 0
    assert model.anchor_map
    assert set(model.zones) >= {"", "NORTE", "SUR"}


@pytest.mark.skipif(not ANCHORS_CSV.exists(), reason="anclas OSM no disponibles")
def test_build_default_model_reads_cached_anchors() -> None:
    model = build_default_model()
    assert model is not None
    assert model.n_anchors > 1000


# ---------------------------------------------------------------------------
# Diccionario de lugares
# ---------------------------------------------------------------------------

def test_usable_place_key_filters_street_types_and_short_names() -> None:
    assert not _usable_place_key("CALLE")
    assert not _usable_place_key("CALLE 70 CON CARRERA 5")
    assert not _usable_place_key("")
    assert not _usable_place_key("CALLE 5")
    assert _usable_place_key("CLINICA COLOMBIA")
    assert _usable_place_key("UNIVERSIDAD DEL VALLE")


def test_method_of_tags_exact_place() -> None:
    lugares = {"CLINICA COLOMBIA": (3.4149, -76.5381)}
    assert _method_of("CLINICA COLOMBIA", None, lugares) == "lugar"


def test_method_of_prefers_grid_over_fuzzy_place() -> None:
    lugares = {"UNIVERSIDAD": (3.37, -76.53)}
    assert _method_of("CALLE 70 CON CARRERA 5", None, lugares) != "lugar"


def test_load_lugares_from_csv_when_available() -> None:
    lugares = load_lugares(LUGARES_CSV) if LUGARES_CSV.exists() else {}
    assert isinstance(lugares, dict)
    if lugares:
        for lat, lon in lugares.values():
            assert _in_range(lat, lon)


# ---------------------------------------------------------------------------
# Geocodificación de una intersección
# ---------------------------------------------------------------------------

def test_geocode_intersection_resolves_exact_place() -> None:
    lugares = {"CLINICA COLOMBIA": (3.4149, -76.5381)}
    point = geocode_intersection("CLINICA COLOMBIA", lugares=lugares)
    assert point == (pytest.approx(3.4149), pytest.approx(-76.5381))


def test_geocode_intersection_resolves_anchor_exactly() -> None:
    model = build_default_model()
    if model is None:
        pytest.skip("anclas OSM no disponibles")
    point = geocode_intersection("Carrera 56 Con Calle 1 A", model=model)
    assert point is not None
    assert _in_range(*point)


def test_geocode_intersection_resolves_grid_fallback() -> None:
    model = build_default_model()
    if model is None:
        pytest.skip("anclas OSM no disponibles")
    point = geocode_intersection("Avenida 2 Con Calle 12", model=model)
    assert point is not None
    assert _in_range(*point)
    assert _method_of("Avenida 2 Con Calle 12", model, None) == "cuadricula"


def test_geocode_intersection_uses_contains_place_fallback() -> None:
    lugares = {"UNIVERSIDAD": (3.37, -76.53)}
    point = geocode_intersection("UNIVERSIDAD DEL VALLE", lugares=lugares)
    assert point == (pytest.approx(3.37), pytest.approx(-76.53))


def test_geocode_intersection_rejects_garbage() -> None:
    model = build_default_model()
    lugares = build_default_lugares()
    assert geocode_intersection("KM 12 VIA AL MAR", model, lugares) is None
    assert geocode_intersection("Seleccione una opcion", model, lugares) is None
    assert geocode_intersection(None, model, lugares) is None


def test_geocode_intersection_supports_mixed_case_input() -> None:
    point = geocode_intersection("cl?nica colombia", lugares={"CLINICA COLOMBIA": (3.4149, -76.5381)})
    assert point is not None


# ---------------------------------------------------------------------------
# Serie y cobertura real del dataset
# ---------------------------------------------------------------------------

def test_geocode_series_aligns_index_and_tags_methods() -> None:
    model = build_default_model()
    series = pd.Series(["Carrera 56 Con Calle 1 A", "Seleccione una opcion"])
    result = geocode_series(series, model=model, lugares=None)
    assert list(result.index) == [0, 1]
    assert list(result.columns) == ["latitud", "longitud", "metodo"]
    assert result.loc[0, "metodo"] == "ancla"
    assert math.isnan(result.loc[1, "latitud"])
    assert result.loc[1, "metodo"] == ""


@pytest.mark.skipif(not PROCESSED_CSV.exists(), reason="parquet de cruces no disponible")
def test_dataset_coverage_of_unique_intersections() -> None:
    table = pd.read_parquet(PROCESSED_CSV)
    unique = table["interseccion"].dropna()
    resolved = table["latitud_geo"].notna()
    coverage = resolved.sum() / len(unique)
    assert coverage >= 0.75


@pytest.mark.skipif(not PROCESSED_CSV.exists(), reason="parquet de cruces no disponible")
def test_dataset_record_weighted_coverage() -> None:
    accidents = pd.read_parquet("data/processed/accidentes_limpios.parquet")
    coverage = accidents[["latitud", "longitud"]].notna().all(axis=1).mean()
    assert coverage >= 0.78