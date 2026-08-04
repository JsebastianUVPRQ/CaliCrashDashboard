"""Geocoding for Cali intersections.

The module resolves the free-text ``interseccion`` field of the crash
dashboard into WGS84 coordinates using three layers:

1. **Exact OSM anchors** (``data/processed/anclas_osm.csv``): real
   intersection coordinates fetched once from OpenStreetMap for the
   numbered street grid of Cali.
2. **Per-zone affine grid**: ``calibrate_grid`` fits ``lat = f(x, y)``
   and ``lon = g(x, y)`` on the anchors, one affine per cardinal zone
   (main, NORTE, SUR, ESTE, OESTE, ORIENTE). The grid axes are the
   street numbers: calles/transversales run along ``x`` and
   carreras/diagonales/avenidas along ``y``.
3. **Curated places** (``data/processed/lugares_geocodificados.csv``):
   named places (clínicas, hospitales, estaciones, vías) looked up by a
   normalized name.

Coordinates are validated against the Cali bounding box
(``CALI_LAT_RANGE`` / ``CALI_LON_RANGE``) before being returned.

No extra dependencies beyond ``pandas``/``numpy`` (already transitively
required by pandas) and the standard library.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

import numpy as np
import pandas as pd

from src.etl import CALI_LAT_RANGE, CALI_LON_RANGE


StreetSegment = tuple[str, int, str, str]  # (tipo, número, letra, sufijo)
ParsedIntersection = tuple[StreetSegment, StreetSegment]

Location = tuple[float, float]  # (lat, lon)


PROCESSED_DIR = Path("data/processed")
ANCHORS_CSV = PROCESSED_DIR / "anclas_osm.csv"
LUGARES_CSV = PROCESSED_DIR / "lugares_geocodificados.csv"

_STREET_TYPES = (
    "CALLE",
    "CARRERA",
    "AVENIDA",
    "DIAGONAL",
    "TRANSVERSAL",
    "AUTOPISTA",
)

# Axis used by the affine grid. This is only *hinted* by street type: the
# final (x, y) assignment is decided empirically per zone via
# ``_grid_axis_candidates`` because diagonals/transversales switch role.
_ZONE_WORDS = ("NORTE", "SUR", "ORIENTE", "ESTE", "OESTE")
_DIR_LETTERS = {"N": "NORTE", "S": "SUR", "E": "ORIENTE", "O": "OESTE"}

# Extended Cali city-area box used to keep affine extrapolation in check.
_GRID_FIT_BBOX = {
    "lat": (3.28, 3.56),
    "lon": (-76.70, -76.38),
}

_MOJIBAKE = {
    "CL?NICA": "CLINICA",
    "SIM?N": "SIMON",
    "V?A": "VIA",
    "JARD?N": "JARDIN",
    "FUNDACI?N": "FUNDACION",
    "DIRECCI?N": "DIRECCION",
    "SALUD?": "SALUDA",
    "??": "",
}

_ABBREVIATIONS = {
    "CLL": "CALLE",
    "CL": "CALLE",
    "CRA": "CARRERA",
    "CR": "CARRERA",
    "KR": "CARRERA",
    "AVE": "AVENIDA",
    "AVDA": "AVENIDA",
    "AV": "AVENIDA",
    "DG": "DIAGONAL",
    "DGNL": "DIAGONAL",
    "TV": "TRANSVERSAL",
    "TRV": "TRANSVERSAL",
    "AUTO": "AUTOPISTA",
}

# Junk tokens that never correspond to a geocodable point.
_IGNORED_TEXT_TERMS = (
    "SELECCIONE",
    "SELECCION",
    "KILOMETRO",
    "KM ",
    "NO APLICA",
    "INGRESE",
    "POR FAVOR",
)

_VIA_RE = re.compile(
    r"^(?P<tipo>CALLE|CARRERA|AVENIDA|DIAGONAL|TRANSVERSAL|AUTOPISTA)\s+"
    r"(?P<num>\d{1,4})\s*"
    r"(?P<let>[A-Z]{1,2})?\s*"
    r"(?P<sub>\d{1,4})?\s*"
    r"(?P<suf>NORTE|SUR|ORIENTE|ESTE|OESTE)?\s*"
    r"(?P<bis>BIS)?\s*$"
)


def strip_accents(text: str) -> str:
    """Remove diacritics, translating them to their ASCII base letter."""
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def normalize_intersection(text: object) -> str:
    """Canonical uppercase text for an intersection expression.

    Handles accents, mojibake (``CL?NICA``), abbreviations (``CL``,
    ``CRA``, ``AV``), separators (``y``, ``e``, ``&``, ``/``) and
    redundant whitespace. Returns an empty string for ``None``/NaN input.

    Examples:
        ``normalize_intersection("Calle 10 Con Carrera 39")``
            -> ``"CALLE 10 CON CARRERA 39"``
        ``normalize_intersection("CRA. 8 y CL 70")``
            -> ``"CARRERA 8 CON CALLE 70"``
        ``normalize_intersection("CL?NICA COLOMBIA")`` -> ``"CLINICA COLOMBIA"``
    """
    if text is None or pd.isna(text):
        return ""

    value = strip_accents(str(text)).upper()

    for source, target in _MOJIBAKE.items():
        value = value.replace(source, target)
    value = value.replace("?", " ")

    value = value.replace(".", " ")
    value = re.sub(r"[-/&|,;():]+", " ", value)

    tokens = value.split()
    expanded = [_ABBREVIATIONS.get(token, token) for token in tokens]
    value = " ".join(expanded)

    # Map standalone separators to CON, keeping letter suffixes (e.g. A in
    # "CARRERA 8 A") untouched.
    value = re.sub(r"\b(Y|E|Y)\b", "CON", value)
    value = re.sub(r"\bCON(?: CON)+\b", "CON", value)

    # Recover pairs that lost their connector ("CALLE 70 CARRERA 5" or
    # "CALLE 25 & CARRERA 109" after punctuation cleanup).
    value = re.sub(
        r"\b(\d[0-9A-Z]*)\s+(CARRERA|CALLE|AVENIDA|DIAGONAL|TRANSVERSAL|AUTOPISTA)\b",
        r"\1 CON \2",
        value,
    )
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_via(text: str) -> StreetSegment | None:
    """Parse one street token into ``(tipo, número, letra, sufijo)``.

    ``letra`` is a sub-street marker (``A`` in ``CARRERA 8 A``) and
    ``sufijo`` a cardinal zone (``NORTE`` in ``AVENIDA 3 NORTE``). A
    direction letter glued to the number (``AVENIDA 6N``) is promoted to
    the suffix. Returns ``None`` when the token is not a numbered vía.

    Examples:
        ``parse_via("CARRERA 8 A")`` -> ``("CARRERA", 8, "A", "")``
        ``parse_via("AVENIDA 3 NORTE")`` -> ``("AVENIDA", 3, "", "NORTE")``
        ``parse_via("CARRERA 26I3")`` -> ``None``
    """
    match = _VIA_RE.match(text.strip().upper())
    if not match:
        return None

    tipo = match.group("tipo")
    numero = int(match.group("num"))
    letra = match.group("let") or ""
    sufijo = match.group("suf") or ""

    direction = _DIR_LETTERS.get(letra)
    if direction is not None and not sufijo:
        sufijo = direction
        letra = ""

    return tipo, numero, letra, sufijo


def parse_intersection(text: object) -> ParsedIntersection | None:
    """Parse a free-text intersection into two street segments.

    Returns ``((tipo, numero, letra, sufijo), (tipo, numero, letra,
    sufijo))`` or ``None`` when the text is not a pair of numbered vías
    (named places, ``KM 12 VIA AL MAR``, ``Seleccione...``, garbage).

    Examples:
        ``parse_intersection("Calle 10 Con Carrera 39")`` returns a pair.
        ``parse_intersection("CLINICA COLOMBIA")`` returns ``None``.
    """
    normalized = normalize_intersection(text)
    if not normalized or " CON " not in normalized:
        return None

    parts = [part.strip() for part in normalized.split(" CON ") if part.strip()]
    # Ignore a trailing bare number ("Carrera 7 y 8" -> keep "Carrera 7").
    while len(parts) > 2 and re.fullmatch(r"\d{1,4}", parts[-1]) and parse_via(parts[-2]) is not None:
        parts.pop()
    if len(parts) != 2:
        return None

    left = parse_via(parts[0])
    right = parse_via(parts[1])
    if left is None or right is None:
        return None

    return left, right


def canonical_key(parsed: ParsedIntersection) -> str:
    """Order-independent canonical string for an intersection pair.

    ``("CALLE", 70, ...)`` + ``("CARRERA", 8, ...)`` is sorted so that
    both ``"Calle 70 con Carrera 8"`` and ``"Carrera 8 con Calle 70"``
    produce ``"CALLE 70 CON CARRERA 8"``.
    """
    if parsed is None:
        return ""

    def _segment_label(segment: StreetSegment) -> str:
        tipo, numero, letra, sufijo = segment
        label = f"{tipo} {numero}{letra or ''}"
        if sufijo:
            label += f" {sufijo}"
        return label

    left, right = parsed
    return " CON ".join(sorted((_segment_label(left), _segment_label(right))))


def _grid_axis_candidates(
    parsed: ParsedIntersection,
) -> list[tuple[StreetSegment, StreetSegment]]:
    """Candidate (x, y) grid assignments for a parsed pair.

    Diagonal/transversal streets change role by zone, so every ordered
    pair is tried and the first one that falls inside a calibrated zone
    and the Cali range wins (see :func:`_grid_point`).
    """
    left, right = parsed
    candidates: list[tuple[StreetSegment, StreetSegment]] = []
    for first in (left, right):
        for second in (left, right):
            if first is second:
                continue
            pair = (first, second)
            if pair not in candidates:
                candidates.append(pair)
    return candidates


def _calibration_xy(parsed: ParsedIntersection) -> tuple[StreetSegment, StreetSegment]:
    """Deterministic (x, y) used to place anchors while fitting."""
    def _score(pair: tuple[StreetSegment, StreetSegment]) -> int:
        x_segment, y_segment = pair
        return (1 if x_segment[0] == "CALLE" else 0) + (1 if y_segment[0] == "CARRERA" else 0)

    return max(_grid_axis_candidates(parsed), key=_score)


def _zone_of(parsed: ParsedIntersection) -> str:
    """Cardinal zone of an intersection, from the suffixed street."""
    left, right = parsed
    for segment in (left, right):
        if segment[3] in _ZONE_WORDS:
            return segment[3]
    return ""


def _grid_x(x_segment: StreetSegment) -> float:
    """Grid coordinate along x for a street segment (number + light letter offset)."""
    _, numero, letra, _ = x_segment
    offset = {"A": 0.25, "B": 0.5, "C": 0.75}.get(letra, 0.0)
    return float(numero) + offset


def _grid_y(y_segment: StreetSegment) -> float:
    """Grid coordinate along y for a street segment."""
    _, numero, letra, _ = y_segment
    offset = {"A": 0.25, "B": 0.5, "C": 0.75}.get(letra, 0.0)
    return float(numero) + offset


@dataclass(frozen=True)
class GridModel:
    """Affine grid model with exact anchors and per-zone calibrations.

    ``zones`` maps a cardinal zone to ``(beta_lat, beta_lon)`` affine
    coefficient triples and ``bounds`` stores the fitted ``(x, y)`` box
    per zone used to reject wild extrapolation.
    """

    anchor_map: dict[str, Location]
    zones: dict[str, tuple[np.ndarray, np.ndarray]]
    bounds: dict[str, tuple[float, float, float, float]]
    n_anchors: int


def calibrate_grid(anchors: pd.DataFrame) -> GridModel:
    """Fit the per-zone affine grid from OSM anchor intersections.

    Args:
        anchors: DataFrame with ``via_a``, ``via_b``, ``latitud`` and
            ``longitud`` columns (see ``data/processed/anclas_osm.csv``).

    Returns:
        A calibrated :class:`GridModel` combining the exact anchor lookup
        and the per-zone affine regression.
    """
    rows: list[dict[str, object]] = []
    for _, raw in anchors.iterrows():
        left = parse_via(str(raw["via_a"]))
        right = parse_via(str(raw["via_b"]))
        if left is None or right is None:
            continue
        parsed: ParsedIntersection = (left, right)
        x_segment, y_segment = _calibration_xy(parsed)
        rows.append(
            {
                "x": _grid_x(x_segment),
                "y": _grid_y(y_segment),
                "zone": _zone_of(parsed),
                "lat": float(raw["latitud"]),
                "lon": float(raw["longitud"]),
                "canonical": canonical_key(parsed),
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("No se pudieron calibrar anclas: ninguna vía numérica válida")

    # Exact lookup: prefer the Cali-core duplicate when the same
    # intersection appears in several places (e.g. Yumbo vs Cali).
    core = frame[frame["lat"].between(*_GRID_FIT_BBOX["lat"]) & frame["lon"].between(*_GRID_FIT_BBOX["lon"])]
    anchor_map: dict[str, Location] = {}
    for _, row in frame.iterrows():
        anchor_map.setdefault(str(row["canonical"]), (float(row["lat"]), float(row["lon"])))
    for _, row in core.iterrows():
        anchor_map[str(row["canonical"])] = (float(row["lat"]), float(row["lon"]))

    zones: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    bounds: dict[str, tuple[float, float, float, float]] = {}
    for zone, sub in frame.groupby("zone"):
        fitted, beta_lat, beta_lon = _robust_affine(sub)
        if beta_lat is None:
            continue
        zones[zone] = (beta_lat, beta_lon)
        bounds[zone] = _fit_bounds(fitted)

    return GridModel(
        anchor_map=anchor_map,
        zones=zones,
        bounds=bounds,
        n_anchors=len(frame),
    )


def _fit_bounds(sub: pd.DataFrame) -> tuple[float, float, float, float]:
    """Bounding box of fitted (x, y) points with a safety margin."""
    margin_x = 12.0
    margin_y = 12.0
    return (
        float(sub["x"].min()) - margin_x,
        float(sub["x"].max()) + margin_x,
        float(sub["y"].min()) - margin_y,
        float(sub["y"].max()) + margin_y,
    )


def _robust_affine(sub: pd.DataFrame) -> tuple[pd.DataFrame | None, np.ndarray | None, np.ndarray | None]:
    """Least-squares affine per zone with iterative MAD outlier removal."""
    data = sub.copy()
    for _ in range(6):
        if len(data) < 6:
            return None, None, None
        x_matrix = np.column_stack([np.ones(len(data)), data["x"], data["y"]])
        beta_lat = np.linalg.lstsq(x_matrix, data["lat"].values, rcond=None)[0]
        beta_lon = np.linalg.lstsq(x_matrix, data["lon"].values, rcond=None)[0]
        lat_resid = data["lat"].values - x_matrix @ beta_lat
        lon_resid = data["lon"].values - x_matrix @ beta_lon
        distance = np.hypot(lat_resid * 110.0, lon_resid * 100.0)
        median = np.median(distance)
        spread = np.median(np.abs(distance - median))
        keep = distance <= max(6.0 * spread, 6.0 * 0.006 + median)
        if int(keep.sum()) == len(data):
            break
        data = data[keep]

    x_matrix = np.column_stack([np.ones(len(data)), data["x"], data["y"]])
    beta_lat = np.linalg.lstsq(x_matrix, data["lat"].values, rcond=None)[0]
    beta_lon = np.linalg.lstsq(x_matrix, data["lon"].values, rcond=None)[0]
    return data, beta_lat, beta_lon


def _in_range(lat: float, lon: float) -> bool:
    """Whether a point falls inside the Cali bounding box."""
    return bool(
        CALI_LAT_RANGE[0] <= lat <= CALI_LAT_RANGE[1]
        and CALI_LON_RANGE[0] <= lon <= CALI_LON_RANGE[1]
    )


def _grid_point(model: GridModel, parsed: ParsedIntersection) -> Location | None:
    """Apply the per-zone affine grid to a parsed intersection.

    Tries every ordered (x, y) assignment and returns the first whose
    result falls inside a calibrated zone box and the Cali range.
    """
    zone = _zone_of(parsed)
    if zone not in model.zones:
        zone = ""
    calibration = model.zones.get(zone)
    box = model.bounds.get(zone, model.bounds.get(""))
    if calibration is None or box is None:
        return None

    beta_lat, beta_lon = calibration
    for x_segment, y_segment in _grid_axis_candidates(parsed):
        x = _grid_x(x_segment)
        y = _grid_y(y_segment)
        if not (box[0] <= x <= box[1] and box[2] <= y <= box[3]):
            continue
        lat = float(beta_lat[0] + beta_lat[1] * x + beta_lat[2] * y)
        lon = float(beta_lon[0] + beta_lon[1] * x + beta_lon[2] * y)
        if _in_range(lat, lon):
            return lat, lon
    return None


def load_lugares(path: Path | None = None) -> dict[str, Location]:
    """Load the curated named-places dictionary keyed by normalized name."""
    source = path or LUGARES_CSV
    if not source.exists():
        return {}
    try:
        table = pd.read_csv(source, encoding="utf-8-sig")
    except Exception:  # noqa: BLE001
        return {}
    result: dict[str, Location] = {}
    for _, row in table[["normalizado", "latitud", "longitud"]].dropna().iterrows():
        key = normalize_intersection(str(row["normalizado"]))
        if not _usable_place_key(key):
            continue
        if _in_range(float(row["latitud"]), float(row["longitud"])):
            result[key] = (float(row["latitud"]), float(row["longitud"]))
    return result


def _usable_place_key(key: str) -> bool:
    """Whether a normalized name can be used as a place lookup key.

    Rejects empty names, bare street types (``CALLE``) and very short
    tokens that would over-match grid texts via the contains fallback.
    """
    if not key:
        return False
    if key in _STREET_TYPES or key.startswith(tuple(f"{tipo} " for tipo in _STREET_TYPES)):
        return False
    return len(key) >= 5


def _lookup_lugar(lugares: dict[str, Location], text: str) -> Location | None:
    """Exact normalized lookup, then a longest-key contains-based fallback."""
    normalized = normalize_intersection(text)
    if not normalized:
        return None
    if normalized in lugares:
        return lugares[normalized]

    lowered = normalized.lower()
    best_key = ""
    for key in lugares:
        if len(key) > len(best_key):
            key_lower = key.lower()
            if key_lower and (key_lower in lowered or lowered in key_lower):
                best_key = key
    if best_key:
        return lugares[best_key]
    return None


def geocode_intersection(
    text: object,
    model: GridModel | None = None,
    lugares: dict[str, Location] | None = None,
) -> Location | None:
    """Geocode one intersection text into ``(lat, lon)`` or ``None``.

    Priority: exact curated place -> exact OSM anchor -> per-zone affine
    grid -> contains-based place lookup. Grid resolutions always win over
    the fuzzy place fallback so that ``"calle 10 con carrera 39"`` never
    lands on a nearby clinic.

    Examples:
        ``geocode_intersection("Calle 10 Con Carrera 39", model, lugares)``
            returns the real anchor coordinate.
        ``geocode_intersection("CLINICA COLOMBIA", model, lugares)``
            returns the curated clinic coordinate.
        ``geocode_intersection("KM 12 VIA AL MAR", model, lugares)``
            returns ``None``.
    """
    normalized = normalize_intersection(text)
    if not normalized:
        return None

    if any(term in normalized for term in _IGNORED_TEXT_TERMS):
        return None

    if lugares:
        exact = lugares.get(normalized)
        if exact is not None:
            return exact

    if model is not None:
        parsed = parse_intersection(normalized)
        if parsed is not None:
            canonical = canonical_key(parsed)
            anchor = model.anchor_map.get(canonical)
            if anchor is not None:
                return anchor
            point = _grid_point(model, parsed)
            if point is not None:
                return point

    if lugares:
        point = _lookup_lugar(lugares, normalized)
        if point is not None:
            return point

    return None


def geocode_series(
    intersecciones: pd.Series | list[str],
    model: GridModel | None = None,
    lugares: dict[str, Location] | None = None,
) -> pd.DataFrame:
    """Vectorized geocoding of a series of intersection texts.

    Returns a DataFrame aligned with the input index with columns
    ``latitud``, ``longitud`` and ``metodo`` (values: ``ancla``, ``cuadricula``,
    ``lugar`` or empty). Points outside the Cali range are dropped.

    Examples:
        ``geocode_series(df["interseccion"], model, lugares)`` returns one
        row per input, with ``None``-free coordinates only for the
        intersections that could be resolved inside Cali.
    """
    series = pd.Series(intersecciones) if not isinstance(intersecciones, pd.Series) else intersecciones

    unique_texts = series.dropna().unique()
    resolved: dict[str, tuple[float, float, str]] = {}
    for text in unique_texts:
        point = geocode_intersection(text, model=model, lugares=lugares)
        if point is None:
            continue
        lat, lon = point
        if not _in_range(lat, lon):
            continue
        followed = _method_of(text, model, lugares)
        resolved[str(text)] = (lat, lon, followed)

    latitudes: list[float | None] = []
    longitudes: list[float | None] = []
    methods: list[str] = []
    for text in series:
        hit = resolved.get(str(text))
        if hit is None:
            latitudes.append(None)
            longitudes.append(None)
            methods.append("")
        else:
            latitudes.append(hit[0])
            longitudes.append(hit[1])
            methods.append(hit[2])

    return pd.DataFrame(
        {"latitud": latitudes, "longitud": longitudes, "metodo": methods},
        index=series.index,
    )


def _method_of(text: str, model: GridModel | None, lugares: dict[str, Location] | None) -> str:
    """Tag the resolution method for reporting/telemetry."""
    normalized = normalize_intersection(text)
    if lugares and lugares.get(normalized) is not None:
        return "lugar"
    if model is not None:
        parsed = parse_intersection(normalized)
        if parsed is not None:
            if model.anchor_map.get(canonical_key(parsed)) is not None:
                return "ancla"
            if _grid_point(model, parsed) is not None:
                return "cuadricula"
    if lugares and _lookup_lugar(lugares, normalized) is not None:
        return "lugar"
    return ""


def build_default_model() -> GridModel | None:
    """Build the grid model from the cached OSM anchors when available."""
    if not ANCHORS_CSV.exists():
        return None
    anchors = pd.read_csv(ANCHORS_CSV)
    return calibrate_grid(anchors)


def build_default_lugares() -> dict[str, Location]:
    """Load the curated places dictionary, falling back to an empty map."""
    return load_lugares(LUGARES_CSV)