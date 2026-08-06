"""Fetch the latest official Cali accident/fatality datasets from CKAN.

Usage:
    python scripts/fetch_sources.py            # skip unchanged snapshots
    python scripts/fetch_sources.py --force    # re-download everything

Writes lineage metadata to ``data/raw/manifiesto_linaje.json``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fetch import SOURCES, fetch_all  # noqa: E402


def main() -> None:
    """Parse arguments, fetch and summarize the download."""
    parser = argparse.ArgumentParser(description="Descarga datasets oficiales de Cali (CKAN).")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-descargar aunque el snapshot local ya coincida.",
    )
    args = parser.parse_args()

    try:
        manifest = fetch_all(force=args.force)
    except Exception as exc:  # network failures must not corrupt local data
        print(f"[error] No fue posible actualizar las fuentes: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n=== ESTADO DE FUENTES ===")
    for source in SOURCES:
        record = manifest.get(source.resource_id, {})
        status = "descargado" if record else "sin descarga"
        size = f"{record['size_bytes'] / 1024 / 1024:.1f} MB" if record.get("size_bytes") else "-"
        print(f"  {source.label:<38} {status:>10}  ({size})")
    print(f"Manifiesto: data/raw/manifiesto_linaje.json")


if __name__ == "__main__":
    main()