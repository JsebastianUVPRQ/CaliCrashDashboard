"""Build the combined processed accident dataset from raw Cali sources.

Combines the two official Cali datasets (siniestralidad 2016-2024 +
lesionados 2016-2025), normalizes them, deduplicates overlapping records
and writes a compact Parquet file to ``data/processed/accidentes_limpios.parquet``.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.etl import normalize_accident_data, read_csv_flexible  # noqa: E402

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")

SOURCES = [
    ("Siniestralidad 2016-2024", RAW_DIR / "cali_siniestralidad_2016_2024.csv"),
    ("Lesionados 2016-2025", RAW_DIR / "cali_lesionados_2016_2025.csv"),
]


def main() -> None:
    """Run the build pipeline."""
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
    for label, raw_n, clean_n in stats:
        print(f"  {label}: {raw_n:,} -> {clean_n:,}")


if __name__ == "__main__":
    main()