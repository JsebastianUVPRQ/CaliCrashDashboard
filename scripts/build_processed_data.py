"""Build the combined processed accident dataset from raw Cali sources.

Combines the two official Cali datasets (siniestralidad 2016-2024 +
lesionados 2016-2025), normalizes them, deduplicates overlapping records,
geocodes every unique intersection and writes:

- ``data/processed/accidentes_limpios.parquet`` (records + coordinates)
- ``data/processed/geocoded_intersections.parquet`` (unique intersection
  lookup table with ``latitud``/``longitud``/``metodo``)
- ``data/processed/fallecidos_limpios.parquet`` (merged road fatalities)
- ``data/processed/fallecidos_reconciliados.csv`` (per-year cross-check)

Run ``python scripts/build_processed_data.py --fetch`` to first download the
official sources from datos.cali.gov.co (CKAN).
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.etl import normalize_accident_data, read_csv_flexible  # noqa: E402
from src.fallecidos import (  # noqa: E402
    SOURCE_CONSOLIDADO,
    SOURCE_SNAPSHOT,
    load_fatality_frames,
    merge_fatality_sources,
    reconcile_fatality_sources,
)
from src.geocode import (  # noqa: E402
    build_default_lugares,
    build_default_model,
    geocode_series,
)
from src import fetch as fetch_sources  # noqa: E402

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
FATALITY_DIR = Path("data/fallecidos")

SOURCES = [
    ("Siniestralidad 2016-2024", RAW_DIR / "cali_siniestralidad_2016_2024.csv"),
    ("Lesionados 2016-2025", RAW_DIR / "cali_lesionados_2016_2025.csv"),
]

COORD_COLUMNS = ("latitud", "longitud", "metodo_geo")


def geocode_dataset(combined: pd.DataFrame) -> pd.DataFrame:
    """Geocode the unique intersections and attach coordinates in place."""
    model = build_default_model()
    lugares = build_default_lugares()
    if model is None:
        print("[geocode] no hay anclas OSM; se omite la geolocalización")
        return combined

    unique_intersections = (
        combined["interseccion"].dropna().astype(str).drop_duplicates().reset_index(drop=True)
    )
    print(f"[geocode] {len(unique_intersections):,} intersecciones únicas")

    geocoded = geocode_series(unique_intersections, model=model, lugares=lugares)
    lookup = pd.concat(
        [unique_intersections.rename("interseccion"), geocoded.reset_index(drop=True)],
        axis=1,
    )
    lookup = lookup.rename(
        columns={"latitud": "latitud_geo", "longitud": "longitud_geo", "metodo": "metodo_geo"}
    )
    geocoded_path = PROCESSED_DIR / "geocoded_intersections.parquet"
    lookup.to_parquet(geocoded_path, index=False)
    print(f"[save] {geocoded_path} ({len(lookup):,} cruces geocodificados)")

    keyed = lookup.set_index("interseccion")
    merged = combined.merge(keyed, how="left", left_on="interseccion", right_index=True)
    # Keep original coordinates when the source already provided them.
    merged["latitud"] = merged["latitud"].fillna(merged["latitud_geo"])
    merged["longitud"] = merged["longitud"].fillna(merged["longitud_geo"])
    merged = merged.drop(columns=["latitud_geo", "longitud_geo"])
    return merged


def build_fatalities() -> pd.DataFrame:
    """Build merged fatality data and write parquet + reconciliation CSV."""
    consolidated, snapshots = load_fatality_frames(FATALITY_DIR)
    merged = merge_fatality_sources(
        [consolidated, snapshots],
        labels=[SOURCE_CONSOLIDADO, SOURCE_SNAPSHOT],
    )
    if merged.empty:
        print("[fallecidos] no hay registros de mortalidad en data/fallecidos/")
        return merged

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "fallecidos_limpios.parquet"
    merged.to_parquet(out_path, index=False)
    print(
        f"[save] {out_path} ({out_path.stat().st_size/1024:.1f} KB, "
        f"{len(merged):,} registros)"
    )

    reconciliation = reconcile_fatality_sources(
        [consolidated, snapshots],
        labels=[SOURCE_CONSOLIDADO, SOURCE_SNAPSHOT],
    )
    reconcile_path = PROCESSED_DIR / "fallecidos_reconciliados.csv"
    reconciliation.to_csv(reconcile_path, index=False, encoding="utf-8")
    print(f"[save] {reconcile_path} ({len(reconciliation)} años)")
    print("=== RECONCILIACIÓN DE FALLECIDOS (por año) ===")
    print(reconciliation.to_string(index=False))
    return merged


def main() -> None:
    """Run the build pipeline."""
    parser = argparse.ArgumentParser(description="Construye los datos procesados de Cali.")
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Descargar primero las fuentes oficiales desde datos.cali.gov.co (CKAN).",
    )
    args = parser.parse_args()

    if args.fetch:
        print("=== DESCARGA DE FUENTES (CKAN) ===")
        fetch_sources.fetch_all()

    frames = []
    stats = []
    for label, path in SOURCES:
        if not path.exists():
            print(f"[skip] {label}: {path} no existe")
            continue
        print(f"[read] {label}: {path}")
        raw = read_csv_flexible(path)
        clean = normalize_accident_data(raw)
        frames.append(clean)
        stats.append((label, len(raw), len(clean)))
        print(
            f"  raw={len(raw):,} -> clean={len(clean):,} "
            f"({len(clean)/max(len(raw),1)*100:.1f}%)"
        )

    if not frames:
        print("No hay fuentes disponibles en data/raw/")
        return

    combined = pd.concat(frames, ignore_index=True)

    # Deduplicate by the fields that define a unique accident event.
    # Código-based dedup happens in the raw frames when available;
    # here we remove exact repeated rows across sources.
    before = len(combined)
    combined = combined.drop_duplicates(
        subset=["fecha", "hora", "interseccion", "tipo_accidente", "gravedad"],
        keep="first",
    )
    print(
        f"[dedup] {before:,} -> {len(combined):,} "
        f"({(before-len(combined)):,} eliminadas)"
    )

    combined = geocode_dataset(combined)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "accidentes_limpios.parquet"
    combined.to_parquet(out_path, index=False)
    print(f"[save] {out_path} ({out_path.stat().st_size/1024**2:.1f} MB)")

    print("\n=== RESUMEN DEL DATASET PROCESADO ===")
    print(f"Registros totales: {len(combined):,}")
    print(
        f"Rango fechas: {combined['fecha'].min().date()} "
        f"-> {combined['fecha'].max().date()}"
    )
    print("Franjas horarias:", dict(combined["franja_horaria"].value_counts()))
    print("Gravedades (top 5):", combined["gravedad"].value_counts().head(5).to_dict())
    print(
        "Intersecciones únicas: ",
        combined["interseccion"].nunique(),
    )
    has_coords = combined[["latitud", "longitud"]].notna().all(axis=1)
    print(f"Cobertura de coordenadas: {has_coords.mean()*100:.1f}%")
    if "metodo_geo" in combined.columns:
        print("Métodos de geocodificación:", dict(combined["metodo_geo"].value_counts()))
    for label, raw_n, clean_n in stats:
        print(f"  {label}: {raw_n:,} -> {clean_n:,}")

    print("\n=== MORTALIDAD VIAL ===")
    build_fatalities()


if __name__ == "__main__":
    main()