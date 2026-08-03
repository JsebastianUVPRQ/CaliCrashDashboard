# Statistical Methodology

## Model Specification

The dashboard fits a **Poisson regression model** (Generalized Linear Model) to estimate the expected daily frequency of traffic accidents in Cali, Colombia.

### Model Formula

```
accidentes ~ C(comuna) + C(franja_horaria)
```

with **exposure offset** `log(dias_observados)`.

### Variables

| Variable | Type | Description |
|---|---|---|
| `accidentes` | Count | Number of accidents in a comuna × time band group |
| `comuna` | Categorical | Comuna number (reference: first comuna alphabetically) |
| `franja_horaria` | Categorical (ordered) | Time band: `madrugada`, `mañana`, `tarde`, `noche` |
| `dias_observados` | Exposure | Number of unique days with data in the group |

### Interpretation

- **Coefficients** represent log-rate ratios relative to the reference category.
- **Rate ratios** (`exp(coef)`) indicate the multiplicative change in expected daily accident frequency.
- **Confidence intervals** (95%) are computed from the standard errors of the coefficients.
- **Significance stars**: `*` p < 0.05, `**` p < 0.01, `***` p < 0.001.

## Goodness-of-Fit Diagnostics

| Metric | Description |
|---|---|
| **Deviance** | Measure of model fit; lower is better |
| **Pearson χ²** | Sum of squared Pearson residuals |
| **AIC** | Akaike Information Criterion |
| **BIC** | Bayesian Information Criterion |
| **Overdispersion ratio** | Pearson χ² / residual degrees of freedom |

### Overdispersion

If the overdispersion ratio exceeds **1.5**, the Poisson assumption of variance = mean is violated. In this case, the dashboard flags the result and recommends a **Negative Binomial** model. The `model_family` field in the output reflects this recommendation.

## Likelihood Ratio Test

The model is compared against a **null (intercept-only) model** using a likelihood ratio test:

```
LR = 2 × (LL_full − LL_null)
```

The p-value is computed from a chi-squared distribution with `(n_params − 1)` degrees of freedom. A significant p-value (p < 0.05) indicates that the predictors (comuna, time band) significantly improve model fit over the null model.

## Risk Classification

Expected daily frequencies are classified into risk levels relative to the city-wide distribution:

| Level | Criterion |
|---|---|
| **Alto** | Rate ≥ 75th percentile |
| **Medio** | Rate ≥ median |
| **Bajo** | Rate < median |

## Assumptions and Limitations

1. **Poisson assumption**: The model assumes variance equals mean. Overdispersion is checked and reported.
2. **Independence**: Accidents are assumed to be independent events.
3. **Exposure**: The model uses observed days as exposure, not calendar days. This accounts for missing data periods.
4. **Data quality**: The model is only as good as the underlying data. Missing coordinates, unknown time bands, and incomplete records affect the estimates.
5. **Small sample sizes**: Groups with very few observed days may have unstable estimates.
6. **No spatial autocorrelation**: The model treats each comuna independently; spatial clustering is not modeled.