# Module B — Step 2 Baseline Ablation & Diagnostic Report

**Document ID**: `ABL-MODULE-B-STEP2-001`  
**Governing Standard**: SIH 2026 Problem Statement SIH26170  
**Phase**: Step 2 — Baseline Ablation & Empirical Diagnostics  
**Status**: **DIAGNOSTIC COMPLETED — NEXT PHASE PLANNING**  
**Execution Timestamp**: `2026-10-05T13:31:33Z UTC`  
**Evaluation Scope**: Module B development ablation — not final holdout validation.  
**Evaluated Cohorts**:
- **Primary Held-Out Validation Cohort**: `LOT13`–`LOT14` ($N=160$ total series, $N=148$ predictable/eligible, $N=12$ insufficient data).
- **Extended Development Benchmark**: `LOT01`–`LOT12` ($N=960$ series) & Full Historical Cohort `LOT01`–`LOT14` ($N=1{,}120$ series, $N=1{,}028$ predictable/eligible, $N=92$ insufficient data).
- **Generator**: `SyntheticBurnInGenerator` (`sih26170.synthetic.burnin_generator`, version `v2.0.0`, mode: `stress`, master seed: `20260918`).

---

## 1. Absolute Final-Holdout Firewall Verification

In strict compliance with the Phase 2 Firewall protocol:
- **`LOT21`–`LOT24` were strictly firewalled**: Zero records from `LOT21`, `LOT22`, `LOT23`, or `LOT24` were loaded, generated, evaluated, or referenced during this analysis.
- **Quarantined directory untouched**: The sealed directory [`data/evaluation/final_holdout/`](file:///Users/jiyakaushik/Desktop/SIH26170_UNIFIED%202/data/evaluation/final_holdout/) was cryptographically checked and verified to remain 100% bit-for-bit identical to its pre-experimental baseline:

| File | Expected SHA-256 Digest | Verified Status |
| :--- | :--- | :---: |
| `observations.csv` | `c042b363dcc7eab5dbc89826062db38550d036b1ead67f229d2f87ee839b996e` | **BIT-FOR-BIT IDENTICAL** |
| `ground_truth.csv` | `1bf1e74fda33cedad445e5c1d38049174c3319b9b4d0f9a27499a25d92268372` | **BIT-FOR-BIT IDENTICAL** |
| `manifest.json` | `1a4bee77deba47364777022470d382514744a28d62363a01967638dff83534d8` | **BIT-FOR-BIT IDENTICAL** |
| `generator_config_snapshot.json` | `c3add1814c7847c8aa5ae19b1918ed051d6c384a8188cfeac9697c20c48ca247` | **BIT-FOR-BIT IDENTICAL** |
| `provenance.json` | `d50eba338784dbd61d795a8ff39eb181e7534bf1a7297679c9f93c3ca022929d` | **BIT-FOR-BIT IDENTICAL** |

- **No Retraining or Tuning**: Production models were evaluated strictly as frozen immutable objects. Zero model parameters, coefficients, weights, thresholds, or uncertainties were modified or re-fitted.
- **Two-Stage Freeze Compliance**: Predictions were generated exclusively from observations available at $\le 24\,\text{h}$, cryptographically hashed (`217a00bc794a057fceb58bec8cb052d8e8bb96022d73d92af1e435a96ad63ec0`), and frozen prior to joining ground truth labels at $168\,\text{h}$.

---

## 2. Evaluated Models

Three prognostic models were compared on identical out-of-fold series:

1. **Model 1: Current Production Ridge (`Current Ridge`)**:
   - Topology: Decoupled parameter-specific Ridge regression models ($\lambda = 1.0$) operating on transformed bivariate coordinates $[u_0, u_{24}] \to \hat{u}_{168}$.
   - Exact frozen parameters:
     - $I_{\text{DSS}}$: $\beta = [0.002340, 0.465704, 0.491824]$, $\sigma_{\text{eff}} = 0.107709\,\mu\text{A}$, $u = \ln(y)$
     - $V_{\text{GS(th)}}$: $\beta = [0.101616, 0.469557, 0.496202]$, $\sigma_{\text{eff}} = 0.030482\,\text{V}$, $u = y$
     - $R_{\text{DS(on)}}$: $\beta = [0.221650, 0.472113, 0.471580]$, $\sigma_{\text{eff}} = 0.018490\,\text{m}\Omega$, $u = \ln(y)$
     - $I_{\text{GSS}}$: $\beta = [0.325747, 0.394075, 0.381621]$, $\sigma_{\text{eff}} = 0.313915\,\text{nA}$, $u = \text{asinh}(y / 1.0\,\text{nA})$
   - Numerical safety policy: If $|u_{\text{pred}}| > 10.0$ or non-finite, fall back deterministically to Carry-Forward ($v_{24}$).
2. **Model 2: Carry-Forward Baseline (`Carry-Forward`)**:
   - Persistence baseline: $\hat{y}_{168} = v_{24}$.
   - Strictly preserves missing data contract (no artificial imputation).
3. **Model 3: Linear Extrapolation (`Linear Extrapolation`)**:
   - Canonical implementation (`TwoPointLinearModel` from [`src/sih26170/prognostics/baselines.py`](file:///Users/jiyakaushik/Desktop/SIH26170_UNIFIED%202/src/sih26170/prognostics/baselines.py)):
     $$u_{\text{slope}} = \frac{u_{24} - u_0}{24}, \quad \hat{u}_{168} = u_0 + u_{\text{slope}} \times 168 = u_{24} + 6 \times (u_{24} - u_0)$$
     mapped monotonically back to physical units via $\phi^{-1}(\hat{u})$.

---

## 3. Overall Performance Summary

Point forecast metrics evaluated across all eligible series ($N=148$ for validation cohort; $N=1{,}028$ for full benchmark cohort). Units are physical native units.

### 3.1 Primary Held-Out Validation Cohort (`LOT13`–`LOT14`, $N=148$)

| Model | Evaluated Series ($N$) | Physical MAE | Physical RMSE | Median AE | Signed Bias | NMAE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Carry-Forward** | 148 | **4.1304** | **8.1582** | **0.4888** | -3.8537 | **0.2325** |
| **Current Ridge** | 148 | 4.1330 | 8.2513 | 0.4953 | -3.9362 | 0.2326 |
| **Linear Extrapolation** | 148 | 11.2968 | 49.9050 | 1.8018 | +3.5874 | 0.6358 |

### 3.2 Full Extended Historical Cohort (`LOT01`–`LOT14`, $N=1{,}028$)

| Model | Evaluated Series ($N$) | Physical MAE | Physical RMSE | Median AE | Signed Bias | NMAE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Carry-Forward** | 1,028 | **5.3815** | **13.0587** | 0.5764 | -5.1619 | **0.2825** |
| **Current Ridge** | 1,028 | 5.4134 | 13.1718 | **0.5390** | -5.2196 | 0.2842 |
| **Linear Extrapolation** | 1,028 | 12.1902 | 61.2378 | 1.6502 | +1.2709 | 0.6399 |

> [!NOTE]
> In aggregate physical MAE, **Carry-Forward edges out Current Ridge** ($4.1304$ vs $4.1330$ on validation; $5.3815$ vs $5.4134$ overall). Linear Extrapolation performs very poorly in aggregate ($2.3\times$ higher MAE, $4.7\times$ higher RMSE) due to massive variance explosion when extrapolating early measurement noise.

---

## 4. Parameter-Level Performance Breakdown

### 4.1 Validation Cohort (`LOT13`–`LOT14`)

| Parameter | Native Unit | Model | $N$ | MAE | RMSE | Median AE | Signed Bias | NMAE |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **$I_{\text{DSS}}$** | $\mu\text{A}$ | **Carry-Forward** | 37 | **0.7890** | **1.2686** | **0.0529** | -0.7693 | **0.5360** |
| | | Current Ridge | 37 | 0.7962 | 1.2794 | 0.0569 | -0.7718 | 0.5409 |
| | | Linear Extrapolation | 37 | 1.1318 | 2.0321 | 0.4387 | -0.1105 | 0.7690 |
| **$V_{\text{GS(th)}}$** | $\text{V}$ | **Carry-Forward** | 35 | **0.1799** | **0.2749** | **0.0324** | -0.1643 | **0.0546** |
| | | Current Ridge | 35 | 0.1877 | 0.2893 | 0.0349 | -0.1804 | 0.0570 |
| | | Linear Extrapolation | 35 | 0.1994 | 0.2573 | 0.1711 | -0.0303 | 0.0605 |
| **$R_{\text{DS(on)}}$** | $\text{m}\Omega$ | **Carry-Forward** | 37 | **8.3798** | **12.3721** | 1.2909 | -7.9162 | **0.1461** |
| | | Current Ridge | 37 | 8.4618 | 12.5605 | **1.1401** | -8.0609 | 0.1476 |
| | | Linear Extrapolation | 37 | 8.9053 | 11.1810 | 6.4078 | -4.3110 | 0.1553 |
| **$I_{\text{GSS}}$** | $\text{nA}$ | **Current Ridge** | 39 | **6.7325** | 10.3472 | **1.4437** | -6.3956 | **0.7765** |
| | | Carry-Forward | 39 | 6.8142 | **10.2839** | 2.2256 | -6.2366 | 0.7859 |
| | | Linear Extrapolation | 39 | 33.1687 | 96.5846 | 10.4489 | +17.8357 | 3.8255 |

### 4.2 Full Extended Historical Cohort (`LOT01`–`LOT14`)

| Parameter | Native Unit | Model | $N$ | MAE | RMSE | Median AE | Signed Bias | NMAE |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **$I_{\text{DSS}}$** | $\mu\text{A}$ | Carry-Forward | 258 | **0.9962** | **1.7883** | 0.0952 | -0.9648 | **0.6453** |
| | | Current Ridge | 258 | 1.0014 | 1.7976 | **0.0934** | -0.9616 | 0.6487 |
| | | Linear Extrapolation | 258 | 1.1417 | 1.9947 | 0.5338 | -0.3896 | 0.7396 |
| **$V_{\text{GS(th)}}$** | $\text{V}$ | Carry-Forward | 253 | **0.2232** | 0.3458 | 0.0374 | -0.2086 | **0.0684** |
| | | Current Ridge | 253 | 0.2288 | 0.3562 | **0.0372** | -0.2187 | 0.0701 |
| | | Linear Extrapolation | 253 | 0.2533 | **0.3351** | 0.1908 | -0.1185 | 0.0776 |
| **$R_{\text{DS(on)}}$** | $\text{m}\Omega$ | Carry-Forward | 261 | **9.1329** | 14.1133 | 1.2909 | -8.6554 | **0.1591** |
| | | Current Ridge | 261 | 9.2080 | 14.2822 | **1.1925** | -8.7377 | 0.1604 |
| | | Linear Extrapolation | 261 | 9.8776 | **13.3744** | 6.2219 | -5.3183 | 0.1720 |
| **$I_{\text{GSS}}$** | $\text{nA}$ | Carry-Forward | 256 | **11.0744** | **21.8716** | 2.1193 | -10.7253 | **0.8400** |
| | | Current Ridge | 256 | 11.1149 | 22.0307 | **1.8881** | -10.8663 | 0.8431 |
| | | Linear Extrapolation | 256 | 37.4798 | 121.9523 | 9.1230 | +11.0353 | 2.8430 |

---

## 5. Scenario-Level Evaluation

Evaluation stratified by the actual benchmark scenarios present in the repository (Full Cohort $N=1{,}028$ eligible series):

| Scenario Label | Total Series ($N$) | Eligible ($N$) | Carry-Forward MAE | Current Ridge MAE | Linear Extrap MAE | Best Model |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`stable`** | 453 | 453 | 0.3476 | **0.3096** | 4.6427 | **Current Ridge** |
| **`high_but_stable`** | 90 | 90 | 0.5031 | **0.4677** | 19.1706 | **Current Ridge** |
| **`linear_drift`** | 115 | 115 | **11.9485** | 12.4100 | 25.5048 | **Carry-Forward** |
| **`accelerating_drift`** | 141 | 141 | **14.3610** | 14.4057 | 15.5794 | **Carry-Forward** |
| **`subtle_abrupt_change`** | 91 | 91 | 10.5011 | **10.4186** | 13.3553 | **Current Ridge** |
| **`equipment_common_mode`**| 48 | 48 | 0.4341 | **0.4232** | 28.3822 | **Current Ridge** |
| **`mixed_compound`** | 70 | 70 | 12.2957 | 12.2531 | **11.9653** | **Linear Extrapolation** |
| **`insufficient_data`** | 74 | 0 | — | — | — | *Safely Excluded* |
| **`missing_observations`** | 38 | 20 | **4.6670** | 4.9062 | 7.9010 | **Carry-Forward** |

### Key Scenario Takeaways:
1. **Ridge wins on stationary regimes**: On `stable` ($N=453$), Ridge achieves $\text{MAE} = 0.3096$, beating Carry-Forward ($0.3476$) by $+10.95\%$. On `high_but_stable` ($N=90$), Ridge achieves $\text{MAE} = 0.4677$, beating Carry-Forward ($0.5031$) by $+7.04\%$.
2. **Carry-Forward wins on active drift**: On `linear_drift` ($N=115$), Carry-Forward wins ($11.9485$ vs $12.4100$). On `accelerating_drift` ($N=141$), Carry-Forward wins ($14.3610$ vs $14.4057$).
3. **Linear Extrapolation explodes on stationary regimes**: On `high_but_stable`, Linear Extrapolation yields $\text{MAE} = 19.17$ ($38\times$ worse than Ridge); on `equipment_common_mode`, it yields $\text{MAE} = 28.38$ ($67\times$ worse than Ridge).

---

## 6. Screening-Relevant Threshold Analysis

Detection of future threshold breaches at $168\,\text{h}$ from $\le 24\,\text{h}$ observations:

### 6.1 Validation Cohort (`LOT13`–`LOT14`)

| Model | Parameter | Target Threshold | TP | FP | TN | FN | Precision | Recall | Specificity | F1 Score |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Current Ridge** | $R_{\text{DS(on)}}$ | $> 60.0\,\text{m}\Omega$ (Screening Margin) | 1 | 0 | 24 | **12** | 100.0% | **7.69%** | 100.0% | 0.1429 |
| **Carry-Forward** | $R_{\text{DS(on)}}$ | $> 60.0\,\text{m}\Omega$ (Screening Margin) | 1 | 0 | 24 | **12** | 100.0% | **7.69%** | 100.0% | 0.1429 |
| **Linear Extrap** | $R_{\text{DS(on)}}$ | $> 60.0\,\text{m}\Omega$ (Screening Margin) | **4** | 6 | 18 | 9 | 40.0% | **30.77%** | 75.0% | **0.3478** |
| **Current Ridge** | $R_{\text{DS(on)}}$ | $> 65.0\,\text{m}\Omega$ (Spec Ceiling) | 0 | 0 | 27 | **10** | 0.0% | **0.0%** | 100.0% | 0.0000 |
| **Carry-Forward** | $R_{\text{DS(on)}}$ | $> 65.0\,\text{m}\Omega$ (Spec Ceiling) | 0 | 0 | 27 | **10** | 0.0% | **0.0%** | 100.0% | 0.0000 |
| **Linear Extrap** | $R_{\text{DS(on)}}$ | $> 65.0\,\text{m}\Omega$ (Spec Ceiling) | **2** | 1 | 26 | 8 | 66.7% | **20.0%** | 96.3% | **0.3077** |
| **Current Ridge** | $I_{\text{DSS}}$ | $> 10.0\,\mu\text{A}$ (Spec Ceiling) | 0 | 0 | 37 | 0 | N/A | 100.0% | 100.0% | N/A |
| **Carry-Forward** | $I_{\text{DSS}}$ | $> 10.0\,\mu\text{A}$ (Spec Ceiling) | 0 | 0 | 37 | 0 | N/A | 100.0% | 100.0% | N/A |
| **Linear Extrap** | $I_{\text{DSS}}$ | $> 10.0\,\mu\text{A}$ (Spec Ceiling) | 0 | 1 | 36 | 0 | 0.0% | 100.0% | 97.3% | 0.0000 |

### 6.2 Full Extended Historical Cohort (`LOT01`–`LOT14`)

| Model | Parameter | Target Threshold | TP | FP | TN | FN | Precision | Recall | Specificity | F1 Score |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Current Ridge** | $R_{\text{DS(on)}}$ | $> 60.0\,\text{m}\Omega$ (Screening Margin) | 4 | 0 | 161 | **96** | 100.0% | **4.00%** | 100.0% | 0.0769 |
| **Carry-Forward** | $R_{\text{DS(on)}}$ | $> 60.0\,\text{m}\Omega$ (Screening Margin) | 5 | 0 | 161 | **95** | 100.0% | **5.00%** | 100.0% | 0.0952 |
| **Linear Extrap** | $R_{\text{DS(on)}}$ | $> 60.0\,\text{m}\Omega$ (Screening Margin) | **28** | 21 | 140 | 72 | 57.1% | **28.00%** | 87.0% | **0.3758** |
| **Current Ridge** | $R_{\text{DS(on)}}$ | $> 65.0\,\text{m}\Omega$ (Spec Ceiling) | 0 | 0 | 188 | **73** | 0.0% | **0.00%** | 100.0% | 0.0000 |
| **Carry-Forward** | $R_{\text{DS(on)}}$ | $> 65.0\,\text{m}\Omega$ (Spec Ceiling) | 0 | 1 | 187 | **73** | 0.0% | **0.00%** | 99.5% | 0.0000 |
| **Linear Extrap** | $R_{\text{DS(on)}}$ | $> 65.0\,\text{m}\Omega$ (Spec Ceiling) | **15** | 13 | 175 | 58 | 53.6% | **20.55%** | 93.1% | **0.2970** |
| **Current Ridge** | $I_{\text{DSS}}$ | $> 10.0\,\mu\text{A}$ (Spec Ceiling) | 0 | 0 | 257 | **1** | 0.0% | **0.00%** | 100.0% | 0.0000 |
| **Carry-Forward** | $I_{\text{DSS}}$ | $> 10.0\,\mu\text{A}$ (Spec Ceiling) | 0 | 0 | 257 | **1** | 0.0% | **0.00%** | 100.0% | 0.0000 |
| **Linear Extrap** | $I_{\text{DSS}}$ | $> 10.0\,\mu\text{A}$ (Spec Ceiling) | 0 | 2 | 255 | **1** | 0.0% | **0.00%** | 99.2% | 0.0000 |
| **Current Ridge** | $V_{\text{GS(th)}}$ | $> 4.0\,\text{V}$ or $< 2.0\,\text{V}$ | 0 | 0 | 249 | **4** | 0.0% | **0.00%** | 100.0% | 0.0000 |
| **Carry-Forward** | $V_{\text{GS(th)}}$ | $> 4.0\,\text{V}$ or $< 2.0\,\text{V}$ | 0 | 0 | 249 | **4** | 0.0% | **0.00%** | 100.0% | 0.0000 |
| **Linear Extrap** | $V_{\text{GS(th)}}$ | $> 4.0\,\text{V}$ or $< 2.0\,\text{V}$ | **1** | 2 | 247 | 3 | 33.3% | **25.00%** | 99.2% | **0.2857** |
| **Current Ridge** | $I_{\text{GSS}}$ | $> 100.0\,\text{nA}$ (Spec Limits) | 0 | 0 | 253 | **3** | 0.0% | **0.00%** | 100.0% | 0.0000 |
| **Carry-Forward** | $I_{\text{GSS}}$ | $> 100.0\,\text{nA}$ (Spec Limits) | 0 | 0 | 253 | **3** | 0.0% | **0.00%** | 100.0% | 0.0000 |
| **Linear Extrap** | $I_{\text{GSS}}$ | $> 100.0\,\text{nA}$ (Spec Limits) | **1** | 15 | 238 | 2 | 6.25% | **33.33%** | 94.1% | **0.1053** |

> [!WARNING]
> **CRITICAL SCREENING BLIND SPOT REVEALED**:
> Across 100 actual $R_{\text{DS(on)}} > 60\,\text{m}\Omega$ screening breaches in the benchmark:
> - **Current Ridge produces 96 FALSE NEGATIVES (96.0% miss rate, Recall = 4.0%)!**
> - **Carry-Forward produces 95 FALSE NEGATIVES (95.0% miss rate, Recall = 5.0%)!**
> - On the hard specification ceiling ($R_{\text{DS(on)}} > 65\,\text{m}\Omega$, 73 true breaches), **Current Ridge has ZERO True Positives (0.0% Recall, 73 False Negatives)**.
> - Linear Extrapolation detected 28 breaches ($28.0\%$ Recall), demonstrating that a forward-projecting trajectory signal exists in early data, but Current Ridge completely dampens it.

---

## 7. Stable vs. Abnormal / Drifting Analysis

Direct comparison of model errors on stationary vs non-stationary populations:

| Population Group | Included Scenarios | Series ($N$) | Carry-Forward MAE | Current Ridge MAE | Linear Extrap MAE | Ridge vs CF $\Delta$ | Ridge % Improvement |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Stable Population** | `stable`, `high_but_stable` | 543 | 0.3734 | **0.3358** | 7.0506 | -0.0376 | **+10.07% (Ridge wins)** |
| **Abnormal Population**| `linear_drift`, `accelerating_drift`, `subtle_abrupt_change`, `mixed_compound` | 417 | **12.5067** | 12.6239 | 17.2246 | +0.1172 | **-0.94% (CF wins)** |
| **Pure Drifting Only** | `linear_drift`, `accelerating_drift` | 256 | **13.2773** | 13.5092 | 20.0381 | +0.2319 | **-1.75% (CF wins)** |

---

## 8. Empirical Test of the “Stable Dominance” Hypothesis

The scientific hypothesis stated:
> *“Carry-forward may win aggregate MAE because most components are stable.”*

The empirical audit yielded the following numerical findings:

1. **Proportion of Population**:
   - Out of $1{,}028$ eligible series, **$543$ series ($52.82\%$)** belong to the stationary population (`stable` + `high_but_stable`).
   - The remaining **$485$ series ($47.18\%$)** are non-stationary (drifting, abrupt, compound, or common-mode).
2. **Error Contribution**:
   - The $543$ stable series contribute only **$3.67\%$** of Carry-Forward's total absolute error ($202.8$ out of $5{,}532.2$ total sum of AE).
   - The $543$ stable series contribute only **$3.28\%$** of Current Ridge's total absolute error ($182.3$ out of $5{,}565.0$ total sum of AE).
   - Over **$96.3\%$ of all forecasting error** in Module B comes from the $47.2\%$ abnormal/drifting/abrupt trajectories!
3. **Hypothesis Verdict**:
   - **THE HYPOTHESIS IS REFUTED BY THE DATA**:
     - Carry-Forward does **not** win aggregate MAE because stable components dominate.
     - In fact, **Current Ridge WINS on stable components** (Ridge MAE $0.3358$ vs CF $0.3734$).
     - Carry-Forward wins aggregate MAE because **Current Ridge is worse than Carry-Forward on drifting/abnormal components** ($12.6239$ vs $12.5067$), and error magnitudes on drifting components ($12.5$ to $13.5$) are **$35\times$ larger** than on stable components ($0.35$)!

---

## 9. Early-Drift Bucket Analysis

Series partitioned into four quartiles based strictly on information available by $24\,\text{h}$ ($\Delta_u = |u_{24} - u_0|$):
- Quartile boundaries: $Q_{25} = 0.01664$, $Q_{50} = 0.04291$, $Q_{75} = 0.14192$.

| Early Drift Bucket | Transformed Drift $|\Delta_u|$ Range | Series ($N$) | Carry-Forward MAE | Current Ridge MAE | Linear Extrap MAE | Best Model |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Q1: Very Low Early Drift** | $[0.0000, 0.0166)$ | 257 | 5.1170 | **5.0765** | 5.7510 | **Current Ridge** |
| **Q2: Low Early Drift** | $[0.0166, 0.0429)$ | 257 | **4.5753** | 4.5939 | 5.4713 | **Carry-Forward** |
| **Q3: Moderate Early Drift** | $[0.0429, 0.1419)$ | 257 | 4.7081 | 4.8246 | **4.1268** | **Linear Extrapolation** |
| **Q4: High Early Drift** | $[0.1419, \infty)$ | 257 | **7.1258** | 7.1584 | 33.4116 | **Carry-Forward** |

### Critical Finding on Early Drift:
- In **Q3 (Moderate Early Drift)**, Linear Extrapolation achieves the lowest MAE ($4.1268$ vs $4.7081$ CF vs $4.8246$ Ridge). When early drift is distinct from noise but not yet extreme, forward slope projection adds genuine prognostic value!
- In **Q4 (High Early Drift)**, unconstrained Linear Extrapolation diverges drastically ($\text{MAE} = 33.41$) due to over-extrapolating abrupt steps, common-mode excursions, and noise spikes.

---

## 10. Equipment-Common-Mode Diagnostic

Evaluation on the $N=48$ series subjected to common-mode chamber thermal shifts at $24\,\text{h}$:
- **Carry-Forward MAE**: $0.4341$
- **Current Ridge MAE**: **$0.4232$**
- **Linear Extrapolation MAE**: **$28.3822$** ($67\times$ worse!)

### Diagnostic Finding:
- Linear Extrapolation catastrophically misinterprets chamber shifts as permanent device-level degradation rate, extrapolating the 24h step forward to 168h and creating massive false alarms.
- Current Ridge dampens the excursion ($\beta_1 \approx 0.47, \beta_2 \approx 0.47$ acts as a shrinkage smoother), but **it has zero peer-lot awareness**. It cannot determine whether the 24h delta was experienced by all devices in the chamber or only by this specific device.

---

## 11. Top Error Analysis

The 5 largest absolute errors across the benchmark:

### 11.1 Current Ridge Top 5 Errors

| Component ID | Lot ID | Parameter | Scenario | Actual $168\,\text{h}$ | Ridge Forecast | Absolute Error | Failure Mechanism |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| `LOT01_C03` | `LOT01` | $I_{\text{GSS}}$ | `linear_drift` | $146.92\,\text{nA}$ | $3.05\,\text{nA}$ | **$143.87\,\text{nA}$** | Severe under-prediction of steep drift |
| `LOT10_C18` | `LOT10` | $I_{\text{GSS}}$ | `accelerating_drift`| $114.59\,\text{nA}$ | $2.30\,\text{nA}$ | **$112.29\,\text{nA}$** | Nonlinear wearout curvature uncaptured |
| `LOT01_C16` | `LOT01` | $I_{\text{GSS}}$ | `accelerating_drift`| $109.33\,\text{nA}$ | $2.57\,\text{nA}$ | **$106.76\,\text{nA}$** | Nonlinear wearout curvature uncaptured |
| `LOT09_C05` | `LOT09` | $I_{\text{GSS}}$ | `linear_drift` | $88.13\,\text{nA}$ | $3.70\,\text{nA}$ | **$84.43\,\text{nA}$** | Shrinkage pulls prediction back to $v_0$ |
| `LOT01_C20` | `LOT01` | $I_{\text{GSS}}$ | `linear_drift` | $76.27\,\text{nA}$ | $3.96\,\text{nA}$ | **$72.31\,\text{nA}$** | Shrinkage pulls prediction back to $v_0$ |

### 11.2 Error Concentration Findings:
1. **Parameter**: Extreme errors are heavily concentrated in **$I_{\text{GSS}}$** (gate leakage) and **$R_{\text{DS(on)}}$** (on-resistance).
2. **Scenario**: Errors are exclusively concentrated in **`accelerating_drift`** and **`linear_drift`**.
3. **Directionality**: Current Ridge's signed bias is overwhelmingly **negative** ($-5.22$ overall, $-8.74\,\text{m}\Omega$ on $R_{\text{DS(on)}}$, $-10.87\,\text{nA}$ on $I_{\text{GSS}}$), indicating systematic **severe under-forecasting** of degradation trajectories.

---

## 12. Numerical Answers to Key Decision Questions

### Q1. Does current Ridge beat carry-forward overall?
**NO.** On the held-out validation cohort, Carry-Forward achieves $\text{MAE} = 4.1304$ vs Current Ridge $\text{MAE} = 4.1330$. Across the full historical cohort, Carry-Forward achieves $\text{MAE} = 5.3815$ vs Current Ridge $\text{MAE} = 5.4134$.

### Q2. Does Ridge beat carry-forward on stable cases?
**YES.** On the stable population (`stable` + `high_but_stable`, $N=543$), Current Ridge achieves $\text{MAE} = 0.3358$ vs Carry-Forward $\text{MAE} = 0.3734$, an improvement of **$+10.07\%$**.

### Q3. Does Ridge beat carry-forward on abnormal/drifting cases?
**NO.** On the abnormal population ($N=417$), Carry-Forward achieves $\text{MAE} = 12.5067$ vs Current Ridge $\text{MAE} = 12.6239$ (Ridge is **$0.94\%$ worse**). On pure drifting trajectories ($N=256$), Carry-Forward achieves $\text{MAE} = 13.2773$ vs Current Ridge $\text{MAE} = 13.5092$ (Ridge is **$1.75\%$ worse**).

### Q4. Does carry-forward clearly outperform Ridge on stable cases?
**NO.** Carry-forward is strictly worse than Ridge on stable cases ($0.3734$ vs $0.3358$). Ridge's balanced coefficients ($\beta_1 \approx 0.47, \beta_2 \approx 0.47$) act as an effective noise filter on stationary trajectories.

### Q5. Does linear extrapolation add useful information?
**YES, BUT ONLY CONDITIONALLY.** Unconstrained linear extrapolation has catastrophic variance overall ($\text{MAE} = 12.19$, $\text{RMSE} = 61.24$). However, in the moderate early-drift regime ($Q_3$: $0.043 \le |\Delta_u| < 0.142$), Linear Extrapolation achieves the lowest MAE ($4.1268$ vs $4.7081$ CF vs $4.8246$ Ridge). Furthermore, on $R_{\text{DS(on)}} > 60\,\text{m}\Omega$ threshold detection, Linear Extrapolation achieves $28.0\%$ Recall ($28$ True Positives) whereas Current Ridge achieves only $4.0\%$ Recall ($4$ True Positives, $96$ False Negatives).

### Q6. Which scenario is currently weakest?
**`accelerating_drift`** (MAE $= 14.41\,\text{units}$, Signed Bias $= -14.41$), followed closely by **`linear_drift`** (MAE $= 12.41\,\text{units}$, Signed Bias $= -12.41$). Current Ridge has near-zero predictive power for identifying accelerating degradation.

### Q7. Which parameter is currently weakest?
**$R_{\text{DS(on)}}$** is weakest operationally (4% recall on screening threshold, 0% recall on specification ceiling, producing 96 and 73 False Negatives respectively). In absolute residual dispersion, **$I_{\text{GSS}}$** is weakest (Validation RMSE $= 10.35\,\text{nA}$, Bias $= -6.40\,\text{nA}$).

### Q8. Where are false negatives concentrated?
False negatives are concentrated almost entirely in **$R_{\text{DS(on)}}$ degradation trajectories** (`linear_drift`, `accelerating_drift`, and `mixed_compound`), where components cross $60.0\,\text{m}\Omega$ or $65.0\,\text{m}\Omega$ at $168\,\text{h}$, but Ridge's shrinkage pulls the $24\,\text{h}$ prediction back down toward the $0\,\text{h}$ baseline.

### Q9. Is there evidence that LOO lot-context features should be tested?
**YES, STRONGLY.** The equipment common-mode diagnostic proved that linear models confuse chamber-level temperature steps with device-level drift ($28.38\,\text{MAE}$ on common mode), while Ridge dampens them only by dampening ALL drift. Incorporating Leave-One-Out (LOO) lot-mean and lot-median context ($\Delta_{\text{excess}} = \Delta u_i - \text{median}_{j \neq i}(\Delta u_j)$) is mathematically necessary to isolate true component excess drift from contemporaneous chamber/lot effects.

### Q10. Is there evidence that a shallow nonlinear model should be tested?
**YES.** Accelerating drift exhibits quadratic/supralinear kinetics ($t^2$) where linear models produce systematic under-prediction bias ($-14.4\,\text{units}$). A shallow gradient-boosted tree (or polynomial terms) is necessary to capture non-linear degradation paths.

### Q11. Is there evidence that gated forecasting should be tested?
**NO (FOR NAIVE GATING).** The naive hypothesis *"use Carry-Forward for stable parts and Current Ridge for drifting parts"* is completely invalidated by the data, because Ridge actually beats Carry-Forward on stable parts, while Ridge is worse than Carry-Forward on drifting parts. Gating Carry-Forward with Current Ridge would worsen performance. Gating is only viable if paired with a new expert that actually outperforms on drift.

---

## 13. Architectural Decisions & Classifications

| Component | Status | Empirical Rationale |
| :--- | :---: | :--- |
| **Current Ridge** | **INVESTIGATE / DEFICIENT** | Excellent stationary noise filter (+10% on stable), but fundamentally fails as an anomaly prognosticator (96% False Negative rate on $R_{\text{DS(on)}}$ screening threshold). |
| **Carry-Forward** | **BASELINE ONLY** | Strong persistence baseline, but possesses zero forward-drift capability and produces 95% False Negatives on screening thresholds. |
| **Linear Extrapolation** | **REGULATED COMPONENT** | Unusable as an unconstrained forecaster (blows up on noise), but contains the only forward-projecting slope signal that detected threshold breaches (28 TP). |
| **Gated Model (Naive CF vs Ridge)** | **DO NOT TEST** | Data contradicts the gating premise: Ridge wins on stable, CF wins on drift. |
| **LOO Lot-Context Features** | **TEST NEXT (HIGHEST PRIORITY)** | Essential to isolate true component excess drift from lot-wide common mode and baseline lot variation. |
| **Shallow Nonlinear Model** | **TEST AFTER LOT-CONTEXT** | Required to address the severe under-prediction bias on `accelerating_drift`, but must operate on clean lot-context features. |

---

## 14. Current Biggest Module B Weakness Statement

> **The current Module B Ridge model is fundamentally an in-sample stationary smoother rather than an anomaly prognosticator: its shrinkage coefficients ($\beta_1 \approx 0.47, \beta_2 \approx 0.47$) pull 24h readings back toward the 0h baseline, causing a catastrophic 96% False Negative rate (4% recall) on future $R_{\text{DS(on)}}$ screening threshold breaches.**

---

## 15. Next Engineering Step

> **Step 3: Implement and evaluate Leave-One-Out (LOO) lot-context features (`u_excess_24h = u_24 - loo_lot_median_24h` and `lot_drift_slope`) on the development cohort (`LOT01`–`LOT12` / `LOT13`–`LOT14`) to give the prognostic model the ability to distinguish true device degradation from lot-level and equipment common-mode variations.**

---

## 16. Reproducibility & Governance Audit

- **Script Executed**: [`scratch/run_step2_analysis.py`](file:///Users/jiyakaushik/Desktop/SIH26170_UNIFIED%202/scratch/run_step2_analysis.py)
- **Machine-Readable Artifacts Generated**:
  - Baseline Results Table: [`reports/module_b_step2_baseline_results.csv`](file:///Users/jiyakaushik/Desktop/SIH26170_UNIFIED%202/reports/module_b_step2_baseline_results.csv)
  - Threshold Results Table: [`reports/module_b_step2_threshold_results.csv`](file:///Users/jiyakaushik/Desktop/SIH26170_UNIFIED%202/reports/module_b_step2_threshold_results.csv)
- **LOT21–LOT24 Accessed?**: **NO**
- **Final Holdout Altered?**: **NO** (SHA-256 verified)
- **Models Retrained?**: **NO**
- **Module A Modified?**: **NO**
- **Step 3 Started?**: **NO**
