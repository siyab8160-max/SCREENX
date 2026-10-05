# Module B — Step 6 Conformal Calibration Specification

**Document ID**: `SPEC-MODULE-B-STEP6-CAL-001`  
**Governing Standard**: SIH 2026 Problem Statement SIH26170  
**Phase**: Step 6 — Regime-Conditioned Conformal Calibration Specification  
**Model Core**: `Zero-Anchored Residual HistGBM` (Model E)  
**Status**: **APPROVED & SPECIFIED**

---

## 1. Calibration Methodology & Mathematical Principles

### A. Strict Three-Way Lot Separation
To guarantee statistical exchangeability and eliminate data snooping, historical lots `LOT01`–`LOT14` are partitioned into three disjoint cohorts:
1. **Model Fitting Partition**: `LOT01`–`LOT08` ($8$ lots, $N=578$ eligible series)  
   Used exclusively to compute training excess drift scales $\sigma_{\text{train}}(p)$ and fit the residual HistGBM regressors.
2. **Conformal Calibration Partition**: `LOT09`–`LOT12` ($4$ lots, $N=302$ eligible series)  
   Used exclusively to evaluate model nonconformity scores and compute empirical conformal quantiles $q_{1-\alpha}(p, k)$.
3. **Independent Validation Partition**: `LOT13`–`LOT14` ($2$ lots, $N=148$ eligible series)  
   Used exclusively for held-out empirical coverage and interval width verification.
4. **Final Holdout Partition**: `LOT21`–`LOT24` ($4$ lots, $N=320$ series)  
   **STRICTLY QUARANTINED, UNTOUCHED, UNCHANGED**.

---

## 2. Regime-Conditioned Conformal Interval Formulation

For component $i$ and electrical parameter $p$:

### Step 1: Regime Routing at $24\,\text{h}$
$$\Delta u_{i, \text{excess}} = (u_{i, 24\text{h}} - u_{i, 0\text{h}}) - \Delta u_{i, \text{lot}}$$
$$\text{Regime}_i = \begin{cases} \text{ZERO\_ANCHORED} & \text{if } |\Delta u_{i, \text{excess}}| \le \tau_p \\ \text{DRIFT\_MODEL} & \text{if } |\Delta u_{i, \text{excess}}| > \tau_p \end{cases}$$

### Step 2: Point Forecasting & Residual Inversion
$$\hat{u}_{i, 168\text{h}} = \begin{cases} u_{i, 24\text{h}} & \text{if Regime } = \text{ZERO\_ANCHORED} \\ u_{i, 24\text{h}} + \Delta\hat{u}_i & \text{if Regime } = \text{DRIFT\_MODEL} \end{cases}$$
$$\hat{y}_{i, 168\text{h}} = \phi_p^{-1}(\hat{u}_{i, 168\text{h}})$$

### Step 3: Nonconformity Scores on Calibration Set
For each calibration component $j \in \text{cal}_p$:
$$R_j = |u_{j, 168\text{h}} - \hat{u}_{j, 168\text{h}}|$$
Group calibration residuals by parameter $p$ and regime $k \in \{\text{ZERO\_ANCHORED}, \text{DRIFT\_MODEL}\}$:
$$\mathcal{R}_{p, k} = \{R_j : j \in \text{cal}_p, \text{Regime}_j = k\}, \quad N_{p, k} = |\mathcal{R}_{p, k}|$$

### Step 4: Finite-Sample Conformal Quantiles
For target miscoverage level $\alpha \in \{0.10, 0.05\}$ ($90\%$ and $95\%$ coverage):
$$p_{\text{rank}}(1-\alpha) = \min\left(1.0, \frac{\lceil (N_{p, k} + 1)(1 - \alpha) \rceil}{N_{p, k}}\right)$$
$$q_{1-\alpha}(p, k) = \text{Quantile}_{p_{\text{rank}}}(\mathcal{R}_{p, k})$$

### Step 5: Physical Interval Construction
In transformed space:
$$\hat{u}_{i, 168\text{h}}^{\text{lower}} = \hat{u}_{i, 168\text{h}} - q_{1-\alpha}(p, k), \quad \hat{u}_{i, 168\text{h}}^{\text{upper}} = \hat{u}_{i, 168\text{h}} + q_{1-\alpha}(p, k)$$
In physical space (monotonic inverse transformation):
$$\hat{y}_{i, 168\text{h}}^{\text{lower}} = \phi_p^{-1}\left(\hat{u}_{i, 168\text{h}}^{\text{lower}}\right), \quad \hat{y}_{i, 168\text{h}}^{\text{upper}} = \phi_p^{-1}\left(\hat{u}_{i, 168\text{h}}^{\text{upper}}\right)$$

Because $\phi_p^{-1}$ is strictly monotonic increasing for all physical parameters:
$$\hat{y}_{i, 168\text{h}}^{\text{lower}} \le \hat{y}_{i, 168\text{h}} \le \hat{y}_{i, 168\text{h}}^{\text{upper}}$$
is unconditionally guaranteed.

---

## 3. Exact Calibration Lookup Table (Frozen Parameters)

These quantiles were derived strictly on `LOT09`–`LOT12` ($N=302$) with forecasters fitted on `LOT01`–`LOT08` ($N=578$):

| Parameter ($p$) | Transformation $\phi(y)$ | Regime ($k$) | Calibration $N_{p, k}$ | Median Residual $|R_u|$ | 90% Half-Width ($q_{0.90}$) | 95% Half-Width ($q_{0.95}$) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **IDSS** | $\log_{10}(y + 10^{-12})$ | `ZERO_ANCHORED` | 21 | 0.1101 | **1.7310** | **1.7755** |
| | | `DRIFT_MODEL` | 58 | 0.5833 | **1.4267** | **1.5214** |
| **VGS(th)** | Identity ($y$) | `ZERO_ANCHORED` | 28 | 0.0392 | **0.6756** | **0.7520** |
| | | `DRIFT_MODEL` | 44 | 0.2053 | **0.4499** | **0.5395** |
| **RDS(on)** | $\ln(y)$ | `ZERO_ANCHORED` | 32 | 0.0328 | **0.4717** | **0.5697** |
| | | `DRIFT_MODEL` | 45 | 0.1344 | **0.3664** | **0.3785** |
| **IGSS** | $\text{asinh}(y / 1.0)$ | `ZERO_ANCHORED` | 30 | 0.9913 | **3.1734** | **3.9965** |
| | | `DRIFT_MODEL` | 44 | 1.0691 | **1.9384** | **2.1800** |

---

## 4. Downstream QA Decision-Support Specification

The conformal calibration engine outputs the following fields per component:

```json
{
  "component_id": "LOT13_COMP04",
  "parameter_name": "RDS(on)",
  "predicted_value": 52.41,
  "regime": "DRIFT_MODEL",
  "lower_90": 36.33,
  "upper_90": 75.59,
  "width_90": 39.26,
  "lower_95": 35.89,
  "upper_95": 76.51,
  "width_95": 40.62,
  "advisory_60": "crosses_60",
  "advisory_65": "crosses_65"
}
```

### Advisory QA Flag Rules for $R_{\text{DS(on)}}$:
1. **`entirely_below_threshold`**: $\hat{y}_{168}^{\text{upper}} < \text{threshold}$  
   *QA Interpretation*: High confidence that component will not breach threshold. Pass screening safely.
2. **`crosses_threshold`**: $\hat{y}_{168}^{\text{lower}} \le \text{threshold} \le \hat{y}_{168}^{\text{upper}}$  
   *QA Interpretation*: Component carries statistically meaningful breach risk within calibrated confidence level. Route to secondary screening or manual engineer review.
3. **`entirely_above_threshold`**: $\hat{y}_{168}^{\text{lower}} > \text{threshold}$  
   *QA Interpretation*: High confidence of terminal breach. Reject immediately.
