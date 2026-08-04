"""Build the curated named-places geocoding dictionary.

One-time data step. It ranks the free-text ``interseccion`` values that are
not grid intersections (clínicas, hospitales, estaciones, vías, centros
comerciales) by frequency and resolves their coordinates with the OSM
Nominatim API. The result is cached in
``data/processed/lugares_geocodificados.csv`` so the dashboard and the ETL
never need network access.

Output columns:
    normalizado  : normalized lookup key (used by ``src.geocode``)
    nombre       : original display name
    latitud, longitud : WGS84 coordinates

Usage:
    python scripts/build_lugares.py [--limit N]
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.geocode import (  # noqa: E402
    LUGARES_CSV,
    _IGNORED_TEXT_TERMS,
    normalize_intersection,
    parse_intersection,
)

PROCESSED_DIR = ROOT / "data" / "processed"
SOURCE_PARQUET = PROCESSED_DIR / "accidentes_limpios.parquet"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "vidas-en-la-via-lugares/1.0 (one-time fetch)"
REQUEST_DELAY_SECONDS = 1.1
ALLOWED_BOX = {"lat": (3.20, 3.60), "lon": (-76.75, -76.30)}

# Values that are never places (they are grid garbage or reachable by grid).
_GRID_MARKERS = (" KM", " KILOMETRO", "CARRERA ", "CALLE ", "AVENIDA ", "TV ", "DIAGONAL ")


def _nomad_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def nominatim_lookup(query: str) -> tuple[float, float] | None:
    """Resolve a place query to ``(lat, lon)`` inside the allowed box."""
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "co",
        "accept-language": "es",
    }
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30, context=_nomad_ctx()) as resp:
            results = json.load(resp)
    except Exception:  # noqa: BLE001
        return None
    if not results:
        return None
    lat = float(results[0]["lat"])
    lon = float(results[0]["lon"])
    if not (ALLOWED_BOX["lat"][0] <= lat <= ALLOWED_BOX["lat"][1]):
        return None
    if not (ALLOWED_BOX["lon"][0] <= lon <= ALLOWED_BOX["lon"][1]):
        return None
    return lat, lon


def _candidate_places(limit: int) -> list[tuple[str, int]]:
    """Rank named places (non-grid, non-garbage intersections) by frequency."""
    frame = pd.read_parquet(SOURCE_PARQUET)
    counts = frame["interseccion"].astype(str).value_counts()

    candidates: list[tuple[str, int]] = []
    for value, count in counts.items():
        norm = normalize_intersection(value)
        if not norm:
            continue
        if any(term in norm for term in _IGNORED_TEXT_TERMS):
            continue
        if parse_intersection(norm) is not None:
            continue
        if any(marker in norm for marker in _GRID_MARKERS):
            continue
        candidates.append((value, int(count)))
        if len(candidates) >= limit:
            break
    return candidates


def main() -> None:
    """Build and cache the places dictionary."""
    parser = argparse.ArgumentParser(description="Build lugares_geocodificados.csv")
    parser.add_argument("--limit", type=int, default=320, help="máximo de lugares a intentar")
    args = parser.parse_args()

    candidates = _candidate_places(args.limit)
    print(f"[candidates] {len(candidates)} lugares no-cuadrícula (top por frecuencia)")

    rows: list[dict[str, object]] = []
    resolved = 0
    for position, (value, count) in enumerate(candidates, start=1):
        norm = normalize_intersection(value)
        query = norm.replace(" CON ", ", ").lower().title().replace(",", ",") + ", Cali"
        point = nominatim_lookup(query)
        if point is not None:
            lat, lon = point
            rows.append(
                {
                    "normalizado": norm,
                    "nombre": value,
                    "frecuencia": count,
                    "latitud": lat,
                    "longitud": lon,
                }
            )
            resolved += 1
        if position % 25 == 0 or position == len(candidates):
            print(f"  [{position}/{len(candidates)}] resueltos={resolved}")
        time.sleep(REQUEST_DELAY_SECONDS)

    table = pd.DataFrame(rows).drop_duplicates(subset=["normalizado"], keep="first")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(LUGARES_CSV, index=False, encoding="utf-8")
    print(f"[save] {LUGARES_CSV} ({len(table)} lugares con coordenadas)")


if __name__ == "__main__":
    main()