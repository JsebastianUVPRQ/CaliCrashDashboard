"""Tests for canonical severity helpers and fatal-accident handling."""

import pandas as pd

from src.metrics import (
    canonical_severity,
    fatal_injury_counts,
    fatal_mask,
    severity_counts,
    severity_filter_values,
)


def _accidents() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fecha": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-03"]),
            "hora": ["08:00", "09:00", "10:00", "11:00"],
            "comuna": ["2", "2", "17", "17"],
            "gravedad": [
                "Con fallecido",
                "Con fallecido (Foraneo)",
                "Con lesionado",
                "Solo daños",
            ],
        }
    )


def test_canonical_severity_maps_fatal_variants() -> None:
    series = pd.Series(
        ["Con fallecido", "Con fallecido (Foraneo)", "Fatal", "Muerto en la vía"]
    )

    result = canonical_severity(series)

    assert (result == "Con fallecido").all()


def test_canonical_severity_maps_injury_and_damage() -> None:
    series = pd.Series(["Con lesionado", "Herido", "Solo daños", "Solo Daños"])

    result = canonical_severity(series)

    assert result.tolist() == ["Con lesionado", "Con lesionado", "Solo daños", "Solo daños"]


def test_severity_counts_fixed_order() -> None:
    result = severity_counts(_accidents())

    assert result["gravedad"].tolist() == ["Solo daños", "Con lesionado", "Con fallecido"]
    assert result["accidentes"].tolist() == [1, 1, 2]


def test_fatal_mask_and_counts() -> None:
    frame = _accidents()
    fatal = int(fatal_mask(frame).sum())
    fatal, injured, _other = fatal_injury_counts(frame)

    assert fatal == 2
    assert injured == 1


def test_severity_filter_values_targets_fatal_kind() -> None:
    frame = _accidents()
    frame.loc[3, "gravedad"] = "Fatal"

    values = severity_filter_values(frame, "fatal")

    assert "Con fallecido" in values
    assert "Con fallecido (Foraneo)" in values
    assert values == sorted(values)