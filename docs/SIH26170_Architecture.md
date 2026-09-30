# SIH26170 — Architecture Document
## AI-Driven Anomaly Detection in Component Burn-In & Screening

**Version:** v1 (build-ready)
**Companion document:** `SIH26170_PRD.md` (requirements/acceptance criteria)

---

## 1. System Overview

```
Raw/synthetic burn-in data (component / lot / parameter / t / value)
        │
        ▼
Preprocessing & Validation
  - unit/range checks, missingness tracking
  - lot/component split BEFORE fitting any statistics
  - "as-of" contract enforced: no statistic may see data past its own checkpoint
        │
   ┌────┴─────────────────────────────┐
   ▼                                   ▼
Module A                            Module B
Dynamic Outlier Detection           Drift Predictor
   │                                   │
   └──────────► Risk Fusion Layer ◄────┘
                       │
                       ▼
               Explainability Layer
                       │
                       ▼
                QA Dashboard (UI)
```

## 2. Canonical Data Schema (long format)

```text
component_id
lot_id
parameter_name          # e.g. leakage_current, iddq, propagation_delay
elapsed_hours           # 0, 24, 96, 168 (Assumption A3)
value
unit
temperature_C
test_condition
instrument_id           # optional — enables equipment-fault discrimination
channel_id              # optional — enables equipment-fault discrimination
measurement_quality
rework_count            # Assumption A11 covariate
absolute_limit_low
absolute_limit_high
source_type             # "synthetic" | "real" | "assumption"
```

**Synthetic-only ground truth fields (never fed to the model, evaluation-only):**
```text
trajectory_class        # stable | high_but_stable | lot_outlier | linear_drift | accelerating_drift | abrupt_failure
first_abnormal_hour
abnormal_by_24h
abnormal_by_96h
abnormal_by_168h
```

## 3. Module A — Detailed Design

### 3.1 The "as-of" contract (hard requirement, tested)

```python
def analyze(component_id: str, as_of_hours: int) -> DecisionRecord:
    """
    Every statistic computed inside this call — lot median, MAD, scalers,
    calibration thresholds — must use only rows where elapsed_hours <= as_of_hours,
    for both the target device and its peer/reference population.
    """
```

### 3.2 Layer 1 — Absolute limit hard gate

Deterministic screening gate executed first:
```python
if value < absolute_limit_low or value > absolute_limit_high:
    absolute_status = "BREACH"
    decision = "REJECT"   # non-negotiable hard gate veto, never blended with statistical scores
else:
    absolute_status = "PASS"
```

### 3.3 Layer 2 — Leave-one-out robust lot baseline

For parameter `p`, lot `l`, checkpoint `t`, excluding target device `i`:
```python
# Statistical representation space:
# z = ln(x) for positive parameters (e.g. leakage_current, iddq)
# z = x     for linear parameters (e.g. propagation_delay)

# Leave-one-out peer statistics:
mu_lot(t) = median({z_j(t) for j in lot_l, j != i})
mad_lot(t) = median(|z_j(t) - mu_lot(t)| for j in lot_l, j != i)
robust_scale(t) = max(1.4826 * mad_lot(t), NOISE_FLOOR)   # A7: measurement noise floor
```

### 3.4 Layer 3 — Robust Decomposition (Consistent Statistical Space)

Both initial peer offset $b_i$ and temporal drift deviation $g_i(t)$ are evaluated in a mathematically consistent statistical space normalized by the baseline lot scale $\sigma_0$:
```python
# Baseline scale at t=0
sigma_0 = robust_scale(0)

# Initial departure from lot baseline at t=0 -> peer_status
b_i = (z_i(0) - mu_lot(0)) / sigma_0

# Temporal departure beyond lot trend -> trend_status
# Identity: g_i(0) == 0.0 identically
delta_i(t) = (z_i(t) - mu_lot(t)) - (z_i(0) - mu_lot(0))
g_i(t) = delta_i(t) / sigma_0

# Equivalent linear decomposition:
# z_i(t) = mu_lot(t) + sigma_0 * (b_i + g_i(t))
```

**Edge Case & Numerical Handling Policies**:
- **Non-positive observations ($x \le 0$)**: Raw telemetry is strictly preserved without flooring or fabrication (LOG-020). For log-mode parameters, the record is flagged as ineligible for direct log transform and returns `peer_status = INSUFFICIENT_DATA`, `trend_status = INSUFFICIENT_DATA`.
- **Zero MAD ($\text{MAD} = 0$)**: Automatically bounded below by `NOISE_FLOOR` (`peer_scale = max(1.4826 * mad, noise_floor)`), preventing division by zero.
- **Insufficient peer population ($N < \text{min\_peers}$)**: Returns `INSUFFICIENT_DATA` without guessing or falling back to population-wide statistics.
- **Missing baseline ($x_i(0) = \text{None}$)**: Returns `trend_status = INSUFFICIENT_DATA`.
- **Non-finite values (NaN, $\pm\infty$)**: Flagged as invalid input and returns `INSUFFICIENT_DATA`.

### 3.5 Layer 4 — Conformal-style calibration

Quantile calibration on known-normal verification devices:
```python
threshold = quantile(calibration_scores_known_normal, 1 - alpha)
```

### 3.6 Layer 5 — Multi-parameter coincidence rule

Secondary multivariate check detecting simultaneous subtle shifts across multiple parameters:
```python
# Evaluates whether 2 or more parameters exhibit simultaneous drift (|g_i,p(t)| >= threshold_coincidence)
# even if no single parameter breaches the Layer 4 univariate threshold.
```

### 3.7 Layer 6 — Per-lot Isolation Forest

Detects non-linear multi-parameter interaction anomalies fit strictly per-lot to prevent cross-lot distribution leakage.

### 3.8 Layer 7 — Equipment-fault discriminator

Clusters anomalies by shared chamber, socket, test channel, or operator (`channel_id`, `instrument_id`). If anomalous behavior correlates with shared test hardware rather than device identity, assigns disposition `EQUIPMENT HOLD` rather than scrapping functional silicon.

### 3.9 Layer 8 — Residual-as-signal feedback

Integrates Module B's 168h forecast residual back into Module A:
```python
# If observed value at 168h deviates substantially from Module B's early prediction (t=24h/96h):
# residual_168h = |x_actual(168h) - x_pred(168h)|
# Large residual feeds back as an independent anomaly flag.
```

## 4. Module B — Detailed Design

### 4.1 Feature block-list (structural, not conventional)

```python
FORBIDDEN_FEATURES = {"value_96h", "value_168h", "future_lot_stats"}
```

### 4.2 Baseline ladder
1. Carry-forward: `x̂_168 = x_24`
2. Linear extrapolation: `x̂_168 = x_24 + slope * (168-24)`, `slope = (x_24-x_0)/24`
3. Per-lot gradient-boosted regression (XGBoost/LightGBM) on `{x_0, x_24, slope, temperature, parameter_name, rework_count}`
4. Prediction interval via quantile regression or residual bootstrap

### 4.3 Explainability Unit Lineage & QA Engineering Card

To prevent unit-lineage bugs and cross-parameter forecast contamination, all explainability outputs must adhere to the `QACard` and `ParameterForecast` contracts (`schema.py`):

1. **Explicit Parameter & Unit Scoping**: Every forecast must specify `parameter_name` and `unit`. A forecast produced in `mA` (e.g. for `iddq`) cannot be bound to a card displaying `leakage_current` in `uA`.
2. **Mutual Unit Consistency**: The explainability card must make:
   - Observed value & unit
   - Absolute limit & unit
   - Forecast & unit
   - Prediction interval & unit
   explicit and mutually consistent.
3. **Hard-Gate Integrity Guarantee**: If an observed value breaches specification limits, `absolute_status` must evaluate to `BREACH` and `decision_state` must evaluate to `REJECT`. It cannot claim `PASS` on the card.
4. **Multi-Channel Evidence Separation**: The card presents `absolute_status`, `peer_status`, `trend_status`, and `decision_state` as distinct channels with plain-language engineering rationale, preventing single-score conflation.

## 5. Repository Structure

```text
sih26170/
├── configs/
│   ├── prototype.yaml
│   └── parameters.yaml
├── data/
│   ├── raw/
│   ├── synthetic/
│   └── processed/
├── src/sih26170/
│   ├── schema.py
│   ├── validation.py
│   ├── synthetic.py          # Phase 2
│   ├── reference.py          # Phase 3
│   ├── residuals.py          # Phase 3
│   ├── module_a.py           # Phase 3
│   ├── module_b.py           # Phase 5
│   ├── decisions.py          # Phase 3/5
│   ├── explanations.py       # Phase 6
│   └── evaluation.py         # Phase 6
├── tests/
│   ├── test_schema.py
│   ├── test_synthetic.py
│   ├── test_reference.py
│   ├── test_residuals.py
│   ├── test_leakage.py
│   └── test_ps_acceptance.py
├── experiments/
└── dashboard/
    └── streamlit_app.py
```
