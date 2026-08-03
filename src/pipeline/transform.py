"""Data transformation stage of the pipeline.

Applies cleaning, normalization, and feature derivation to raw data,
producing canonical DataFrames that conform to the schema contracts.
"""

import pandas as pd

from src.etl import normalize_accident_data
from src.fallecidos import normalize_fatality_data


def transform_accidents(raw: pd.DataFrame) -> pd.DataFrame:
    """Transform raw accident data into canonical form.

    Args:
        raw: Raw accident DataFrame from the extract stage.

    Returns:
        A normalized DataFrame with derived features (franja_horaria,
        dia_semana, mes) and validated coordinates.
    """
    return normalize_accident_data(raw)


def transform_fatalities(raw: pd.DataFrame) -> pd.DataFrame:
    """Transform raw fatality data into canonical form.

    Args:
        raw: Raw concatenated fatality DataFrame from the extract stage.

    Returns:
        A normalized DataFrame filtered to Cali records with derived
        columns (ano, mes, dia_semana, rango_3h, etc.).
    """
    return normalize_fatality_data(raw)