"""Poisson regression model for accident frequency.

Fits a Poisson GLM to accident counts per comuna and time band, using
observed days as an exposure offset. Reports coefficients, standard
errors, p-values, confidence intervals, and goodness-of-fit metrics.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from src.config import TIME_BAND_ORDER

_Z_SCORE = 1.96


@dataclass(frozen=True)
class FrequencyModelResult:
    """Results of a fitted Poisson frequency model."""

    coefficients: pd.DataFrame
    expected_frequencies: pd.DataFrame
    n_observations: int
    n_groups: int
    deviance: float
    pearson_chi2: float
    aic: float
    bic: float
    overdispersion_ratio: float
    is_overdispersed: bool
    model_family: str
    likelihood_ratio_p: float
    formula: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "n_observations": self.n_observations,
            "n_groups": self.n_groups,
            "deviance": self.deviance,
            "pearson_chi2": self.pearson_chi2,
            "aic": self.aic,
            "bic": self.bic,
            "overdispersion_ratio": self.overdispersion_ratio,
            "is_overdispersed": self.is_overdispersed,
            "model_family": self.model_family,
            "likelihood_ratio_p": self.likelihood_ratio_p,
            "formula": self.formula,
        }


def _significance_stars(p_value: float) -> str:
    """Convert a p-value to significance stars."""
    if p_value < 0.001:
        return "***"
    if p_value < 0.01:
        return "**"
    if p_value < 0.05:
        return "*"
    return ""


def _format_p_value(p_value: float) -> str:
    if p_value < 0.001:
        return "<0.001"
    return f"{p_value:.4f}"


def fit_frequency_model(accidents: pd.DataFrame) -> FrequencyModelResult:
    """Fit a Poisson GLM for expected daily accident frequency.

    The model predicts accident counts per comuna and time band using
    ``log(dias_observados)`` as an exposure offset. Coefficients represent
    log-rate ratios relative to the reference category.

    Args:
        accidents: Normalized accident DataFrame with columns ``fecha``,
            ``comuna``, and ``franja_horaria``.

    Returns:
        A ``FrequencyModelResult`` with coefficient estimates, expected
        frequencies, and goodness-of-fit diagnostics.
    """
    required = {"fecha", "comuna", "franja_horaria"}
    if accidents.empty or not required.issubset(accidents.columns):
        return _empty_result(accidents)

    # Aggregate counts and observed days per comuna x time band
    grouped = (
        accidents.groupby(["comuna", "franja_horaria"], dropna=False, observed=False)
        .agg(
            accidentes=("fecha", "count"),
            dias_observados=("fecha", lambda col: col.dt.date.nunique()),
        )
        .reset_index()
    )

    # Drop groups with zero observed days
    grouped = grouped[grouped["dias_observados"].gt(0)].copy()

    # Convert time band to ordered categorical for sensible reference level
    band_order = [b for b in TIME_BAND_ORDER if b in set(grouped["franja_horaria"])]
    grouped["franja_horaria"] = pd.Categorical(
        grouped["franja_horaria"],
        categories=band_order,
        ordered=True,
    )

    # Exposure = log(days observed)
    grouped["exposure"] = np.log(grouped["dias_observados"])

    formula = "accidentes ~ C(comuna) + C(franja_horaria)"
    try:
        model = smf.glm(
            formula=formula,
            data=grouped,
            family=sm.families.Poisson(),
            offset=grouped["exposure"],
        )
        fit = model.fit()
    except Exception:
        # Fall back to intercept-only model if the full model fails to converge
        model = smf.glm(
            "accidentes ~ 1",
            data=grouped,
            family=sm.families.Poisson(),
            offset=grouped["exposure"],
        )
        fit = model.fit()
        formula = "accidentes ~ 1"

    # Extract coefficients
    params = fit.params
    conf_int = fit.conf_int()
    pvalues = fit.pvalues

    coef_rows = []
    for name in params.index:
        coef = float(params[name])
        ci_lower, ci_upper = conf_int.loc[name].tolist()
        p_value = float(pvalues[name])
        coef_rows.append(
            {
                "termino": name,
                "coeficiente": coef,
                "error_estandar": float(fit.bse[name]),
                "z": float(fit.tvalues[name]),
                "p_valor": p_value,
                "p_formateado": _format_p_value(p_value),
                "significancia": _significance_stars(p_value),
                "ic_inferior": float(ci_lower),
                "ic_superior": float(ci_upper),
                "razon_tasa": float(np.exp(coef)),
                "razon_tasa_ic_inf": float(np.exp(ci_lower)),
                "razon_tasa_ic_sup": float(np.exp(ci_upper)),
            }
        )
    coefficients = pd.DataFrame(coef_rows)

    # Expected frequencies per group with confidence intervals
    fitted_values = fit.predict(grouped, which="mean")
    se_pred = np.sqrt(fit.get_prediction(grouped).var_pred_mean)

    expected = grouped[["comuna", "franja_horaria", "accidentes", "dias_observados"]].copy()
    expected["frecuencia_diaria_esperada"] = fitted_values / grouped["dias_observados"]
    expected["intervalo_inferior"] = (
        fitted_values - _Z_SCORE * se_pred
    ) / grouped["dias_observados"]
    expected["intervalo_superior"] = (
        fitted_values + _Z_SCORE * se_pred
    ) / grouped["dias_observados"]
    expected["intervalo_inferior"] = expected["intervalo_inferior"].clip(lower=0)

    # Risk levels based on the city-wide median
    median_rate = expected["frecuencia_diaria_esperada"].median()
    upper_quartile = expected["frecuencia_diaria_esperada"].quantile(0.75)
    expected["nivel_riesgo"] = expected["frecuencia_diaria_esperada"].map(
        lambda rate: _risk_label(rate, median_rate, upper_quartile)
    )

    expected = expected.sort_values(
        ["frecuencia_diaria_esperada", "accidentes"],
        ascending=False,
    ).reset_index(drop=True)

    # Goodness-of-fit metrics
    deviance = float(fit.deviance)
    pearson_chi2 = float((fit.resid_pearson**2).sum())
    n_params = len(params)
    n_obs = len(grouped)
    df_resid = max(n_obs - n_params, 1)
    overdispersion = pearson_chi2 / df_resid if df_resid > 0 else 1.0

    # Likelihood ratio test: full model vs null model
    try:
        null_model = smf.glm(
            "accidentes ~ 1",
            data=grouped,
            family=sm.families.Poisson(),
            offset=grouped["exposure"],
        )
        null_fit = null_model.fit()
        lr_stat = 2 * (fit.llf - null_fit.llf)
        from scipy.stats import chi2

        lr_df = max(n_params - 1, 1)
        lr_p = float(chi2.sf(lr_stat, lr_df))
    except Exception:
        lr_p = float("nan")

    return FrequencyModelResult(
        coefficients=coefficients,
        expected_frequencies=expected,
        n_observations=n_obs,
        n_groups=n_obs,
        deviance=deviance,
        pearson_chi2=pearson_chi2,
        aic=float(fit.aic),
        bic=float(fit.bic),
        overdispersion_ratio=overdispersion,
        is_overdispersed=overdispersion > 1.5,
        model_family=("NegativeBinomial" if overdispersion > 1.5 else "Poisson"),
        likelihood_ratio_p=lr_p,
        formula=formula,
    )


def _risk_label(rate: float, median_rate: float, upper_quartile: float) -> str:
    """Classify risk as low, medium, or high relative to city distribution."""
    if rate >= upper_quartile:
        return "alto"
    if rate >= median_rate:
        return "medio"
    return "bajo"


def _empty_result(accidents: pd.DataFrame) -> FrequencyModelResult:
    """Return an empty result for empty or invalid input data."""
    empty_coefs = pd.DataFrame(
        columns=[
            "termino",
            "coeficiente",
            "error_estandar",
            "z",
            "p_valor",
            "p_formateado",
            "significancia",
            "ic_inferior",
            "ic_superior",
            "razon_tasa",
            "razon_tasa_ic_inf",
            "razon_tasa_ic_sup",
        ]
    )
    empty_expected = pd.DataFrame(
        columns=[
            "comuna",
            "franja_horaria",
            "accidentes",
            "dias_observados",
            "frecuencia_diaria_esperada",
            "intervalo_inferior",
            "intervalo_superior",
            "nivel_riesgo",
        ]
    )
    return FrequencyModelResult(
        coefficients=empty_coefs,
        expected_frequencies=empty_expected,
        n_observations=0,
        n_groups=0,
        deviance=0.0,
        pearson_chi2=0.0,
        aic=0.0,
        bic=0.0,
        overdispersion_ratio=1.0,
        is_overdispersed=False,
        model_family="Poisson",
        likelihood_ratio_p=float("nan"),
        formula="",
    )