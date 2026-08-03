"""Data extraction stage of the pipeline.

Discovers and loads raw data from local files, remote URLs, or uploaded
buffers. Records source metadata (path, checksum, row count) for lineage.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import DATA_CANDIDATES, FATALITY_DATA_DIR
from src.etl import read_csv_flexible
from src.fallecidos import _read_fatality_files


@dataclass(frozen=True)
class SourceInfo:
    """Metadata about a data source."""

    source_type: str  # "local", "remote", "upload", "sample"
    source_path: str
    checksum: str
    row_count: int
    column_count: int


def _checksum(data: pd.DataFrame) -> str:
    """Compute a stable checksum of a DataFrame's contents."""
    return sha256(pd.util.hash_pandas_object(data, index=True).values.tobytes()).hexdigest()


def extract_accidents(
    uploaded_file: Any | None = None,
    candidates: tuple[Path, ...] = DATA_CANDIDATES,
) -> tuple[pd.DataFrame, SourceInfo]:
    """Extract raw accident data from the first available source.

    Priority: uploaded file > local candidates > sample data.

    Args:
        uploaded_file: Optional uploaded file-like object.
        candidates: Ordered tuple of local file paths to try.

    Returns:
        A tuple of (raw DataFrame, source metadata).
    """
    if uploaded_file is not None:
        raw = read_csv_flexible(uploaded_file)
        return raw, SourceInfo(
            source_type="upload",
            source_path="uploaded_file",
            checksum=_checksum(raw),
            row_count=len(raw),
            column_count=len(raw.columns),
        )

    for path in candidates:
        if path.exists():
            suffix = path.suffix.lower()
            if suffix == ".parquet":
                raw = pd.read_parquet(path)
            else:
                raw = read_csv_flexible(path)
            return raw, SourceInfo(
                source_type="local",
                source_path=str(path),
                checksum=_checksum(raw),
                row_count=len(raw),
                column_count=len(raw.columns),
            )

    from src.etl import build_sample_accidents

    sample = build_sample_accidents()
    return sample, SourceInfo(
        source_type="sample",
        source_path="builtin_sample",
        checksum=_checksum(sample),
        row_count=len(sample),
        column_count=len(sample.columns),
    )


def extract_fatalities(directory: Path = FATALITY_DATA_DIR) -> tuple[pd.DataFrame, SourceInfo]:
    """Extract raw fatality data from all CSV files in a directory.

    Args:
        directory: Directory containing fatality CSV snapshots.

    Returns:
        A tuple of (raw concatenated DataFrame, source metadata).
    """
    files = sorted(directory.glob("*.csv")) if directory.exists() else []
    combined = _read_fatality_files(files)
    return combined, SourceInfo(
        source_type="local",
        source_path=str(directory),
        checksum=_checksum(combined),
        row_count=len(combined),
        column_count=len(combined.columns),
    )
