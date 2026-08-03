"""Tests for the Poisson GLM frequency model."""

import pandas as pd

from src.stats import fit_frequency_model


def _sample_accidents() -> pd.DataFrame:
    """Create a small but meaningful dataset for model fitting."""
    dates = pd.to_datetime(
        [
            "2025-01-01",
            "2025-01-01",
            "2025-01-01",
            "2025-01-02",
            "2025-01-02",
            "2025-01-03",
            "2025-01-03",
            "2025-01-03",
            "2025-01-04",
            "2025-01-04",
        ]
    )
    comunas = ["2", "2", "2", "2", "17", "17", "17", "2", "17", "2"]
    bands = [
        "mañana",
        "mañana",
        "noche",
        "mañana",
        "noche",
        "noche",
        "tarde",
        "noche",
        "mañana",
        "tarde",
    ]
    return pd.DataFrame(
        {
            "fecha": dates,
            "comuna": comunas,
            "franja_horaria": bands,
        }
    )


def test_fit_frequency_model_returns_expected_structure() -> None:
    result = fit_frequency_model(_sample_accidents())

    assert result.coefficients is not None
    assert not result.coefficients.empty
    assert set(
        ["termino", "coeficiente", "error_estandar", "z", "p_valor", "significancia"]
    ).issubset(result.coefficients.columns)

    assert result.expected_frequencies is not None
    assert not result.expected_frequencies.empty
    assert set(
        ["comuna", "franja_horaria", "accidentes", "dias_observados", "frecuencia_diaria_esperada"]
    ).issubset(result.expected_frequencies.columns)

    assert result.n_observations > 0
    assert result.deviance > 0
    assert result.aic > 0
    # BIC can be negative for small samples; it just needs to be finite
    assert result.bic != float("inf")
    assert result.bic != float("-inf")
    assert result.overdispersion_ratio > 0
    assert result.model_family in ("Poisson", "NegativeBinomial")


def test_fit_frequency_model_expected_frequencies_positive() -> None:
    result = fit_frequency_model(_sample_accidents())

    assert (result.expected_frequencies["frecuencia_diaria_esperada"] > 0).all()
    assert (
        result.expected_frequencies["intervalo_superior"]
        >= result.expected_frequencies["frecuencia_diaria_esperada"]
    ).all()
    assert (result.expected_frequencies["intervalo_inferior"] >= 0).all()


def test_fit_frequency_model_handles_empty_data() -> None:
    result = fit_frequency_model(pd.DataFrame())

    assert result.coefficients.empty
    assert result.expected_frequencies.empty
    assert result.n_observations == 0


def test_fit_frequency_model_handles_missing_columns() -> None:
    data = pd.DataFrame({"fecha": pd.to_datetime(["2025-01-01"])})

    result = fit_frequency_model(data)

    assert result.coefficients.empty
    assert result.n_observations == 0


def test_fit_frequency_model_risk_labels() -> None:
    result = fit_frequency_model(_sample_accidents())

    valid_labels = {"bajo", "medio", "alto"}
    assert set(result.expected_frequencies["nivel_riesgo"]).issubset(valid_labels)
    assert not result.expected_frequencies["nivel_riesgo"].isna().any()


def test_fit_frequency_model_to_dict() -> None:
    result = fit_frequency_model(_sample_accidents())
    data = result.to_dict()

    assert data["n_observations"] > 0
    assert data["aic"] > 0
    assert "model_family" in data
    assert "formula" in data
    assert "is_overdispersed" in data