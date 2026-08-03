"""Command-line entry point for the data pipeline.

Usage:
    python scripts/run_pipeline.py [--output DIR] [--source local|upload]

Runs the full ETL pipeline: extract → validate → transform → load,
writing processed Parquet files and a manifest.json to the output directory.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import (
    extract_accidents,
    extract_fatalities,
    load_processed_data,
    transform_accidents,
    transform_fatalities,
    validate_accidents,
    validate_fatalities,
    write_manifest,
)
from src.schema import ACCIDENT_SCHEMA, FATALITY_SCHEMA


def run_pipeline(output_dir: Path) -> None:
    """Run the full ETL pipeline for accidents and fatalities.

    Args:
        output_dir: Directory to write processed data and manifest.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Accidents ---
    print("=== Accident pipeline ===")
    raw_accidents, accident_source = extract_accidents()
    print(f"  Extracted: {accident_source.row_count:,} rows from {accident_source.source_type}")

    accident_validation = validate_accidents(raw_accidents)
    print(f"  Validated: {accident_validation.valid_rows:,} valid / {accident_validation.total_rows:,} total")
    if accident_validation.column_errors:
        for col, errors in accident_validation.column_errors.items():
            print(f"    {col}: {', '.join(errors)}")

    clean_accidents = transform_accidents(raw_accidents)
    accident_output = output_dir / "accidentes_limpios.parquet"
    load_processed_data(
        clean_accidents,
        accident_output,
        schema_name=ACCIDENT_SCHEMA.name,
        schema_version=ACCIDENT_SCHEMA.version,
    )
    print(f"  Wrote: {accident_output} ({len(clean_accidents)} rows)")

    # --- Fatalities ---
    print("\n=== Fatality pipeline ===")
    raw_fatalities, fatality_source = extract_fatalities()
    print(f"  Extracted: {len(raw_fatalities)} rows from {fatality_source.source_path}")

    fatality_validation = validate_fatalities(raw_fatalities)
    print(f"  Validated: {fatality_validation.valid_rows:,} valid / {fatality_validation.total_rows:,} total")

    clean_fatalities = transform_fatalities(raw_fatalities)
    fatality_output = output_dir / "fallecidos_limpios.parquet"
    load_processed_data(
        clean_fatalities,
        fatality_output,
        schema_name=FATALITY_SCHEMA.name,
        schema_version=FATALITY_SCHEMA.version,
    )
    print(f"  Wrote: {fatality_output} ({len(clean_fatalities)} rows)")

    # --- Manifest ---
    manifest_path = output_dir / "manifest.json"
    write_manifest(
        manifest_path,
        source=accident_source,
        validation=accident_validation,
        output_files={
            "accidentes": str(accident_output),
            "fallecidos": str(fatality_output),
        },
    )
    print(f"\nManifest: {manifest_path}")


def main() -> None:
    """Parse CLI arguments and run the pipeline."""
    parser = argparse.ArgumentParser(description="Run the Cali crash data pipeline")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed"),
        help="Output directory for processed data (default: data/processed)",
    )
    args = parser.parse_args()

    run_pipeline(args.output)


if __name__ == "__main__":
    main()