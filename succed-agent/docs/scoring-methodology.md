# Scoring methodology (v1)

All weights, thresholds and caps are in `config/scoring/*.yaml`. This page explains the reasoning behind them. **v1 values are modelling hypotheses** derived from Altos Andes' published criteria and from search fund research. They are not empirically fitted.

## Evidence base and limitations

| Input | Source | Use in v1 | Limitation |
|---|---|---|---|
| Acquisition rate ~58% all-time; ~half of 2021–24 cohorts acquired; ~20-month search; median 2024–25 deal ~$16M | Stanford GSB 2026 Search Fund Study (US & Canada, 862 funds) | Baseline for the returns model; urgency of the in-search alerts | US/Canada only; pooled; survivorship |
| First LOI by ~month 6 for successful searchers vs ~month 8 for those who failed | IESE International Search Funds 2026 (492 funds, 48 countries) | `lo_alert_month: 6` | Correlation, not causation |
| EV US$10–30M; profitable; low capex; recurring customers; no distress, single-customer or owner dependence | altosandescapital.com (read 2026-11-26) | Company Score dimensions and knock-outs | Public criteria only; EBITDA band and equity cap are hypotheses |
| 33.9% IRR / 4.75x (US); 30% / 2.8x (international) | Stanford 2026; IESE 2026 | Context only, never a target | Skewed by outliers |

## Searcher Score

- Seven dimensions rated 0–5 with evidence; weights 25/15/20/10/10/10/10.
- Unevidenced ratings count as **0** and widen the confidence interval. This makes a missing reference cost the searcher, rather than letting the AI "fill it in".
- Factual caps prevent an eloquent thesis from scoring high when the facts disagree, for example when the addressable universe is below 300 or runway is below 24 months.
- Protected attributes are rejected by both config validation and the engine.

## Company Score

- Piecewise-linear sub-scores (0–1) per dimension, weighted to 100.
- Missing data scores 0 for that input, and confidence half-width = 3 + 20 × (1 − completeness).
- Knock-outs cap the score or route the company elsewhere; they are always listed in the output.
- Low-confidence scores must clear the matching gate on their **lower bound**.

## Fit Index

- Gate: Searcher ≥ 70 and Company ≥ 70.
- Holds: the company is outside the thesis geographies, or thesis match < 0.6.
- Components: thesis 35 · operator–lever match 20 · syndicate capacity 15 · quality 20 · semantic similarity 10.

## Calibration (learning loop)

- Uses L2 logistic regression of outcome on dimension scores (minimum 30 outcomes), and reports AUC for the current weights against fitted weights.
- Suggestions are shrunk 50% toward the partner-set weights, and a partner must publish them as a new version.
- Recommended outcome labels: searcher → acquired within 30 months; company → reached LOI; later, exit MOIC ≥ 2x.
