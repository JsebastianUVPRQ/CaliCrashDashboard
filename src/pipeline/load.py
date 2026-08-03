"""Data loading stage of the pipeline.

Writes processed data to Parquet with schema metadata and produces a
manifest.json recording source lineage, validation results, and timestamps.
"""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.pipeline.extract import SourceInfo
from src.pipeline.validate import ValidationResult


def load_processed_data(
    data: pd.DataFrame,
    output_path: Path,
    schema_name: str,
    schema_version: str,
) -> None:
    """Write processed data to Parquet with schema metadata.

    Args:
        data: Processed DataFrame to persist.
        output_path: Destination Parquet file path.
        schema_name: Canonical schema name.
        schema_version: Canonical schema version.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_parquet(output_path, index=False)

    # Write schema metadata alongside the data
    metadata_path = output_path.with_suffix(".schema.json")
    metadata = {
        "schema_name": schema_name,
        "schema_version": schema_version,
        "columns": list(data.columns),
        "dtypes": {col: str(dtype) for col, dtype in data.dtypes.items()},
        "written_at": datetime.now().isoformat(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")


def write_manifest(
    manifest_path: Path,
    source: SourceInfo,
    validation: ValidationResult,
    output_files: dict[str, str],
) -> None:
    """Write a pipeline manifest recording source lineage and validation.

    Args:
        manifest_path: Destination manifest JSON path.
        source: Source metadata from the extract stage.
        validation: Validation result from the validate stage.
        output_files: Mapping of dataset name to output file path.
    """
    manifest = {
        "pipeline_version": "1.0.0",
        "generated_at": datetime.now().isoformat(),
        "source": asdict(source),
        "validation": validation.to_dict(),
        "outputs": output_files,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")