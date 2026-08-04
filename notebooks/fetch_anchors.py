"""Fetch numbered-street intersection anchors for Cali from OpenStreetMap.

One-time build script (disposable). It queries the Overpass API for named
streets inside the Cali bbox, finds nodes shared by two or more street ways
and writes ``data/processed/anclas_osm.csv`` so that downstream builds never
need to hit the network again.

Output columns:
    interseccion : raw pair of street names, e.g. "CRA. 5 | CL. 12"
    via_a, via_b : raw street names that meet at the node
    latitud, longitud : WGS84 coordinates of the shared node

Usage:
    python notebooks/fetch_anchors.py
"""

from __future__ import annotations

import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROCESSED_DIR = ROOT / "data" / "processed"

CALI_BBOX = (3.28, -76.70, 3.56, -76.38)  # min_lat, min_lon, max_lat, max_lon

OVERPASS_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

USER_AGENT = "vidas-en-la-via-anchors/1.0 (one-time fetch)"

# Street names that look like grid vías: prefix abbreviation + a number.
_VIAS_RE = re.compile(
    r"^(CALLE|CLL|CL|CARRERA|CRA|CR|KR|AVENIDA|AVE|AV|AVDA|"
    r"DIAGONAL|DG|DGNL|TRANSVERSAL|TV|TRV|AUTOPISTA|AUTO)\b",
    re.IGNORECASE,
)

_HIGHWAYS_MAIN = "^(primary|secondary|tertiary|trunk)$"
_HIGHWAYS_GRID = "^(residential|unclassified)$"

_QUERY_MAIN = """
[out:json][timeout:300];
way["name"~"^(CALLE|CLL|CL|CARRERA|CRA|CR|KR|AVENIDA|AVE|AV|AVDA|DIAGONAL|DG|DGNL|TRANSVERSAL|TV|TRV|AUTOPISTA|AUTO)",i]
    ["highway"~"^(primary|secondary|tertiary|trunk)$"]
    ({min_lat},{min_lon},{max_lat},{max_lon});
out body qt;
>;
out skel qt;
"""

_QUERY_GRID = """
[out:json][timeout:300];
way["name"~"^(CALLE|CLL|CL|CARRERA|CRA|CR|KR|AVENIDA|AVE|AV|AVDA|DIAGONAL|DG|DGNL|TRANSVERSAL|TV|TRV|AUTOPISTA|AUTO)",i]
    ["highway"~"^(residential|unclassified)$"]
    ({min_lat},{min_lon},{max_lat},{max_lon});
out body qt;
>;
out skel qt;
"""


def _query_overpass(query: str) -> dict:
    """POST the query to the first mirror that answers."""
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    payload = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last_error: Exception | None = None
    for mirror in OVERPASS_MIRRORS:
        request = urllib.request.Request(
            mirror, data=payload, headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(
                request, timeout=300, context=ssl_ctx
            ) as response:
                return json.load(response)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(f"[warn] fallo en {mirror}: {exc!r}")
    raise RuntimeError(f"No fue posible consultar Overpass: {last_error!r}")


def _street_token(name: str) -> str:
    """Return the street token (e.g. ``CL``) or empty when not a vía."""
    if not name or "CON" in name.upper():
        return ""
    match = _VIAS_RE.match(name.strip())
    if not match:
        return ""
    token = match.group(1).upper()
    if not re.search(r"\d", name):
        return ""
    return token


def main() -> None:
    """Run the fetch and write anclas_osm.csv."""
    ways: dict[int, dict] = {}
    nodes: dict[int, dict] = {}
    for label, template in (("malla principal", _QUERY_MAIN), ("malla secundaria", _QUERY_GRID)):
        query = template.format(
            min_lat=CALI_BBOX[0],
            min_lon=CALI_BBOX[1],
            max_lat=CALI_BBOX[2],
            max_lon=CALI_BBOX[3],
        )
        print(f"[query] vías {label} de Cali...")
        started = time.monotonic()
        data = _query_overpass(query)
        print(f"[query] respuesta en {time.monotonic() - started:.1f}s")

        for element in data.get("elements", []):
            if element.get("type") == "way":
                ways[element["id"]] = element
            elif element.get("type") == "node":
                nodes[element["id"]] = element

    print(f"[ok] {len(ways):,} vías nombradas, {len(nodes):,} nodos")

    named_ways = {
        way_id: way
        for way_id, way in ways.items()
        if way.get("tags", {}).get("name") and _street_token(way["tags"]["name"])
    }
    print(f"[ok] {len(named_ways):,} vías de la malla numerada")

    node_ways: dict[int, list[int]] = {}
    for way_id, way in named_ways.items():
        for node_id in way.get("nodes", []):
            node_ways.setdefault(node_id, []).append(way_id)

    seen: set[tuple[str, str]] = set()
    rows: list[tuple[str, str, str, float, float]] = []
    for node_id, way_ids in node_ways.items():
        if len(way_ids) < 2:
            continue
        node = nodes.get(node_id)
        if node is None:
            continue
        tokens = sorted({_street_token(ways[w]["tags"]["name"]) for w in way_ids})
        if len(tokens) < 2:
            continue
        names = sorted(
            {ways[w]["tags"]["name"].strip() for w in way_ids}, key=str.casefold
        )
        pair = tuple(names[:2])
        if pair in seen:
            continue
        seen.add(pair)
        rows.append(
            (
                " | ".join(pair),
                pair[0],
                pair[1],
                float(node["lat"]),
                float(node["lon"]),
            )
        )

    rows.sort(key=lambda row: (row[1].casefold(), row[2].casefold()))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "anclas_osm.csv"
    header = "interseccion,via_a,via_b,latitud,longitud\n"
    with out_path.open("w", encoding="utf-8") as handle:
        handle.write(header)
        for row in rows:
            handle.write(",".join(f'"{value}"' for value in row) + "\n")

    print(f"[save] {out_path} ({len(rows):,} intersecciones únicas)")
    print("[done] ejecutar scripts/build_processed_data.py para regenerar el dataset")


if __name__ == "__main__":
    main()