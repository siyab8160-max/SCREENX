# SIH26170 — Proposed Solution Draft
## AI-Driven Anomaly Detection in Component Burn-In & Screening

**Status:** Rough draft for internal team use. This is a *design proposal*, not a validated system. Every claim below is tagged as **[SOURCED]**, **[ASSUMPTION]**, or **[DESIGN CHOICE]** so the team always knows what still needs evidence before the demo can be called realistic.

---

## 1. Framing Statement (what we are actually building)

> A lot-aware, explainable screening and early-warning platform for high-reliability electronic component burn-in, using a board-level assembly (DC-DC converter / power supply unit / electronic control board) or, alternatively, a packaged-MMIC/MMIC-module test context, robust statistical anomaly detection (Module A), early-to-late degradation prediction with uncertainty (Module B), and full provenance tracking for every synthetic or assumed value.

We are explicitly **not** claiming to predict real ISRO mission failures. We are claiming to build **decision support for QA inspectors** that flags components deserving a second look, and shows its work.

---

## 2. Assumptions Register

Every assumption here is a placeholder until real ISRO evidence replaces it. This table is the single most important artifact in the draft — keep it updated and show it to judges proactively; it demonstrates rigor rather than guesswork.

| # | Assumption | Status | Why we need it | What would replace it |
|---|---|---|---|---|
| A1 | Test article is a **board-level high-reliability electronic assembly** (e.g. DC-DC converter, power supply unit, or electronic control board) — **primary framing as of this update**; packaged MMIC/MMIC-module retained as a secondary/alternative framing | **[ASSUMPTION — mentor-informed]**, best-supported by public ISRO procurement docs (MMIC framing) plus domain-expert judgment (board-level framing, see A14) | Determines which parameters are physically meaningful; board-level framing better explains why Iddq-like current, leakage current, AND propagation delay would plausibly co-exist on one test article (digital controller + power stage + timing paths on one board), which a single MMIC does not naturally explain | ISRO SME confirmation or actual test article spec |
| A2 | Burn-in temperature = 125°C | **[SOURCED]** — appears across multiple ISRO screening specs | Anchors the thermal-stress model | N/A — reasonably safe to keep |
| A3 | Burn-in duration = 168h (with checkpoints at 0/24/96/168h) | **[ASSUMPTION]** — 168h and 240h both appear in ISRO docs; the exact checkpoint schedule is not confirmed anywhere public | Defines Module B's input/output structure | ISRO test procedure document or SME input |
| A4 | Parameters measured together: leakage current, Iddq-like current, propagation delay | **[ASSUMPTION]** — PS states this as an *example*, not a confirmed measurement set; more physically plausible under the board-level framing (A1) than under a single-MMIC framing | Determines what "parameter_name" values exist in the schema | Confirmed parameter list per component family |
| A5 | Lot size / number of components per lot | **[ASSUMPTION]** — set arbitrarily (e.g. 20–50 units/lot) for synthetic data generation | Needed for lot-relative statistics to be meaningful | Real or SME-estimated lot sizes |
| A6 | Latent-defect rate in a lot (~2–5%) | **[ASSUMPTION]** — arbitrary, used only for synthetic data | Needed to generate labeled synthetic anomalies | Real historical reject-rate data, if shareable |
| A7 | Measurement noise magnitude (~1–3% of nominal value) | **[ASSUMPTION]** | Needed so synthetic "normal" variation looks realistic | Instrument repeatability spec |
| A8 | Drift/degradation shapes (linear, accelerating, abrupt-step) are the relevant failure trajectory classes | **[DESIGN CHOICE]**, loosely grounded in general reliability literature (BTI/HCI/TDDB-style behavior) | Needed to build a non-trivial Module B target | Real aging data or literature specific to the chosen component |
| A9 | Safety slope / drift boundary for early rejection | **[DESIGN CHOICE]** — placeholder threshold, tunable | Needed for Module B's flag logic | ISRO drift-limit table (some public docs show ±1dB / ±10% examples for *specific* parameters — not transferable without evidence) |
| A10 | No confirmed real failure labels exist in our dataset | **[SOURCED]** (absence confirmed via public search) | Governs what claims we can make about "accuracy" | A labeled real or ISRO-provided dataset |
| A11 | Correlation between production rework/build history and defect risk | **[SOURCED]** — published ML-for-ESS precedent uses rework count as a predictor of screening need (IEEE, *Dynamic Environmental Stress Screening Using Machine Learning*, doc #9153583) | Justifies adding a non-electrical covariate to the generator, not just electrical drift | Real production/rework logs, if shareable |
| A12 | Burn-in physics parameters (activation energy ranges, Arrhenius-style acceleration) | **[DESIGN CHOICE]**, can be anchored to **JEDEC JESD22-A108** (published industry standard for temperature/bias burn-in test method) rather than invented from scratch | Needed so the degradation-path generator isn't purely arbitrary | Direct calibration against JESD22-A108 parameters or ISRO-specific equivalent |
| A13 | Dataset strategy: synthetic generator as primary; **NASA Ames Prognostics Center of Excellence "MOSFET Thermal Overstress Aging Data Set"** for structural validation only (dimensionless normalized curves $z(t) = R_{\text{ds(on)}}(t) / R_{\text{ds(on)}}(0)$ for temporal degradation-shape analysis and forecasting/extrapolation validation). Never implies physical conversion $R_{\text{ds(on)}} \to \text{leakage\_current}$ or populates canonical electrical fields | **[STRUCTURAL VALIDATION ONLY — NOT PHYSICAL CONVERSION TO LEAKAGE]** — real dataset, confirmed via independent search (Celaya, Saxena, Saha, Goebel; six power MOSFETs aged under thermal overstress). Used structurally to validate relative temporal degradation shapes; must NEVER populate leakage_current or unrelated physical fields | Precludes physical overclaiming; ensures empirical validation of drift models is structurally grounded without pseudo-physics | An ISRO-provided or ISRO-representative dataset |
| A14 | Mentor consultation (Sri Ramyaa S, propulsion/power-electronics background) suggested spacecraft avionics and power electronics — specifically DC-DC converters, power supply units, and electronic control boards — as the area worth investigating for this PS, while explicitly declining to name one specific component without knowing exact ISRO testing requirements | **[EXPERT JUDGMENT — non-binding]** — a domain-adjacent mentor's informed opinion, not a primary source or ISRO confirmation | Directly informs A1's revised framing; also supports "identify component before finalizing parameters" as the right first step, consistent with our own earlier research conclusion | Direct ISRO SME confirmation, or a mentor with confirmed subject-matter expertise in this exact test program |
| A15 | Our explanations will describe statistical evidence only (residual level, slope, persistence, z-scores) and will **never** name a specific physical failure mechanism (e.g. "gate oxide breakdown," "electromigration") unless we have mechanism-level evidence for the specific component | **[DESIGN CHOICE — guardrail]**, added after reviewing a competitor's pitch language that implied physics-of-failure root-cause attribution without supporting evidence | Prevents us from overclaiming causal diagnosis we cannot support; keeps explanations defensible under judge questioning | Confirmed failure-mode data for the actual chosen component |
| A16 | Lesson from competitor audit: never map a real dataset's raw values directly into our schema's units without an explicit, documented conversion step | **[SOURCED]** — a competitor repo (AEGIS) was found to map NASA C-MAPSS turbofan sensor values (e.g. ~1600K jet-engine temperatures) directly into fields labeled `leakage_current` (µA) against a 50µA limit, producing a reported negative R² and near-universal false rejections | Any secondary real dataset we use (A13) must be rescaled/normalized with a stated method, and clearly labeled in the UI as a physics sanity check, not a value-for-value substitute | N/A — this is a process rule for our own generator/adapter code |
| A17 | Benchmark evaluation chain against competitor methods (reproducible execution of `benchmark_vs_competitors.py` on frozen dataset `data/synthetic/` with master seed 20260916) | **[REPRODUCIBLE BENCHMARK EVIDENCE CHAIN]** — benchmark artifact, script, configuration, seed, dataset version, and metrics recorded as an end-to-end reproducibility chain. Figures may only be reported after the actual script is independently rerun and its output inspected. Benchmark numbers must never be quoted from promotional prose alone and are never described as forecasts or predictions | Prevents citing unverified or promotional claims; ensures benchmark evidence is strictly reproducible and transparent | An independently verified benchmark run with immutable artifact and script provenance |
| A18 | Industry precedent for multidimensional dynamic part average testing: **US Patent US12007428B2**, *"Systems and methods for multidimensional dynamic part average testing"*, Advantest Corporation | **[SOURCED / VERIFIED — RESOLVED]** — verified existence and relevance via USPTO/Google Patents lookup. Confirms multidimensional/dynamic PAT-style robust statistical screening is an existing industry approach in semiconductor test. Does NOT validate our implementation or establish algorithm novelty; cited strictly as verified industry precedent | Sourced precedent establishing that dynamic/multidimensional PAT is recognized in high-reliability semiconductor screening | Verified patent publication (US12007428B2) |

**Rule for the team:** if a number appears anywhere in the code (a threshold, a noise level, a drift rate) and it isn't in this table with a source, add it to this table before merging.

---

## 3. Evidence Requirements — what would make this usable for *real* testing

This section lists what we would need to obtain, from ISRO or elsewhere, to move this from "hackathon-plausible" to "operationally credible." Presenting this list to judges is itself a strength — it shows you understand the gap between a prototype and a deployable tool.

### 3.1 Data evidence
- Anonymized sample CSV or schema of an actual burn-in test log (even a redacted single lot)
- Confirmed parameter list per component family (which parameters are actually co-measured)
- Actual measurement checkpoint schedule (is it really 0/24/96/168h, or continuous logging?)
- Instrument resolution and repeatability specs, to calibrate realistic noise
- At least a handful of confirmed "rejected" or "flagged" units, to validate that anomaly definitions align with real QA judgment

### 3.2 Domain evidence
- Confirmed absolute specification limits for the parameters used
- Confirmed drift-acceptance formulas (e.g., ISRO's ±1dB / ±10% style limits) mapped to the *correct* parameters
- SME confirmation of which degradation mechanisms are plausible for the chosen component (so Module B's synthetic trajectories aren't inventing physics)
- Lot/wafer/die traceability conventions actually used, so the schema matches real workflows
- Confirmation (or correction) of the mentor-suggested board-level framing (A1/A14) against actual ISRO testing requirements — currently the best-informed guess we have, but explicitly flagged by the mentor herself as non-binding

### 3.3 Validation evidence
- A small holdout of real (or ISRO-representative) data to sanity-check that synthetic-trained models transfer at all
- QA inspector review of sample flags — do the explanations make sense to a human reviewer?
- Sign-off on what statuses are acceptable outputs (e.g., is "HOLD FOR RETEST" acceptable, or must the system be binary pass/fail?)

**Until this evidence exists**, every dashboard screen and every report we generate should visibly label results as based on real data, ISRO-sourced specification, design assumption, or synthetic simulation — no exceptions. This labeling is a core feature, not an afterthought.

### 3.4 Dataset strategy for the current prototype (locked in)

- **Primary dataset:** our own synthetic generator (Section 4/5), fully documented, with hidden ground-truth trajectory classes used only for evaluation.
- **Secondary dataset:** NASA Ames Prognostics Center of Excellence **MOSFET Thermal Overstress Aging Data Set** (six power MOSFETs, real electrical degradation — ON-state resistance rising with die-attach degradation under thermal stress), used narrowly to sanity-check that Module B's early→late prediction approach behaves sensibly on *real* degradation curves. Always labeled "physics sanity check — not ISRO validation" wherever it appears, and **never** value-mapped directly into our schema's units without an explicit, documented conversion (see Assumption A16 — a competitor's unconverted C-MAPSS-to-leakage-current mapping is the cautionary example).
- **Explicitly not used for v1:** UCI SECOM (not longitudinal — doesn't match the repeated-measurement structure), Minitab leakage dataset (population-level censored data, not per-component trajectories), NASA C-MAPSS (wrong domain — turbofan sensor data has no defensible unit mapping to semiconductor electrical parameters).

---

## 4. Proposed System Architecture

```
                        ┌─────────────────────────────┐
                        │   Raw Test Data (CSV/API)    │
                        │  component/lot/parameter/    │
                        │  time/value/temperature/     │
                        │  rework_count/test_channel   │
                        └──────────────┬───────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │   Preprocessing & Validation  │
                        │  - unit/range checks          │
                        │  - missingness tracking        │
                        │  - lot/component split BEFORE │
                        │    fitting any statistics      │
                        │  - "as-of" contract: no stat   │
                        │    may see data past its       │
                        │    own checkpoint               │
                        └──────────────┬───────────────┘
                     ┌─────────────────┴─────────────────┐
                     ▼                                     ▼
        ┌─────────────────────────────┐     ┌─────────────────────────────┐
        │          Module A            │     │          Module B            │
        │   Dynamic Outlier Detect     │     │      Drift Predictor         │
        │  1. absolute-limit HARD GATE │     │  1. baseline extrapolation   │
        │     (veto, never blended)    │     │  2. GBM regression (per-lot) │
        │  2. leave-one-out robust lot │     │     w/ leakage guard on      │
        │     baseline (median/MAD in  │     │     96h/168h features        │
        │     log space, MAD floored)  │◄────┤  3. prediction interval      │
        │  3. decomposition:           │     │  4. safety-slope compare     │
        │     x(t)=μ_lot(t)+b_i+g_i(t)+ε│     │     → early-rejection flag   │
        │     b_i → PEER status        │     └──────────────┬───────────────┘
        │     g_i(t) → TREND status    │                    │ residual (predicted
        │  4. conformal calibration    │                    │ vs actual at 168h)
        │     on max|g_i(t)|           │◄───────────────────┘ fed back as an
        │  5. three-way fused decision │        independent Module A signal
        │  + secondary layers: coincidence rules, per-lot Isolation Forest,  │
        │  equipment-fault discrimination, rework-history covariate          │
        └──────────────┬───────────────────────────────────────────────────┘
                                        ▼
                        ┌─────────────────────────────┐
                        │        Risk Fusion Layer      │
                        │  PASS / PASS-MONITOR / REVIEW │
                        │  HOLD-FOR-RETEST / REJECT      │
                        │  EQUIPMENT HOLD / INSUFFICIENT │
                        │  DATA / OUT-OF-DISTRIBUTION    │
                        └──────────────┬───────────────┘
                                       ▼
                        ┌─────────────────────────────┐
                        │   Explainability Layer         │
                        │  - which score(s) triggered it │
                        │  - SHAP breakdown (secondary)  │
                        │  - provenance tag (real/synth) │
                        │  - plain-language QA reason     │
                        └──────────────┬───────────────┘
                                       ▼
                        ┌─────────────────────────────┐
                        │      QA Dashboard (UI)         │
                        └─────────────────────────────┘
```

---

## 5. Technology Stack (proposed)

| Layer | Technology | Why |
|---|---|---|
| Data generation & processing | Python, pandas, numpy | Standard, fast to prototype |
| Module A statistics | scipy, scikit-learn (robust covariance, Isolation Forest fit per-lot, LOF) | Well-understood, explainable baselines |
| Module A multivariate | Mahalanobis distance (custom) / Hotelling's T² / per-lot Isolation Forest | Explainable, matches SPC practice engineers already trust |
| Module B regression | XGBoost or LightGBM, fit per lot, with hard-coded feature block-list for 96h/168h | Strong on small tabular data, SHAP-compatible; leakage guard is structural, not conventional |
| Module B intervals | Quantile regression (LightGBM quantile objective) or bootstrap residuals | Avoids false-precision point estimates |
| Explainability | SHAP TreeExplainer (secondary), plus rule-based natural-language generator (primary) | QA inspectors need engineering reasoning, not just feature importances |
| Evaluation metrics | F2 score (Module A headline), MAE + interval coverage (Module B), scrap-rate tracking | F2 directly encodes the PS's FN-averse requirement as one number |
| Synthetic data generator | Custom Python simulator (lot effect + component baseline + temperature response + degradation path + rework covariate + noise), physics grounded in JEDEC JESD22-A108 where possible | No public ISRO dataset exists; must be built, documented, and anchored to a real standard where feasible |
| Real-data sanity check | NASA Ames MOSFET Thermal Overstress Aging dataset (secondary only, clearly labeled, converted via a documented unit mapping — never a raw value swap) | Grounds Module B's early→late approach in real semiconductor degradation physics without overclaiming ISRO relevance; upgraded from NASA IGBT for a closer domain match |
| Dashboard | Streamlit (fastest for hackathon) or React + Plotly Dash (more polished demo) | Needs trajectory plots, risk cards, provenance tags; **adopt AEGIS's per-layer score breakdown UI pattern** (spec/lot/trend/ML/prediction shown separately) and its downloadable engineering-report concept, regardless of which stack we build it in |
| Threshold configuration | Externalized thresholds/weights via a small settings store (file-based config or lightweight DB), not hardcoded constants | **Adopted from AEGIS** — even though their underlying formulas were unsourced, exposing thresholds as editable configuration (rather than buried in code) is good practice we should match, on top of actually sourcing/justifying the values in our assumptions register |
| Validation | Lot-level and component-level train/test splits, generator-shift testing | Prevents data leakage and overclaiming |

---

## 6. Competitive Landscape & Technical Positioning

Public repositories targeting SIH26170 exhibit distinct methodological approaches. Rather than asserting broad or unsubstantiated generalities, our technical positioning explicitly categorizes existing industry and competitor paradigms:

### 6.1 Paradigm Differentiation: Mean/Std vs. Dynamic Robust Screening

1. **MAVERICK / AEGIS Paradigm (Parametric Gaussian Screening)**:
   - Relies primarily on classical sample mean ($\mu$) and sample standard deviation ($\sigma$) limit boundaries (e.g. $\mu \pm 3\sigma$).
   - *Technical Limitation*: Sample mean and standard deviation have a theoretical breakdown point of 0% ($\epsilon^* = 0$). In contaminated production lots containing multiple out-of-spec or drifting components, the mean is pulled and standard deviation is inflated, causing severe statistical masking (false negatives).
   - In several implementations, temporal causality was compromised via whole-dataset lookaheads or unvalidated unit mappings (e.g. C-MAPSS turbofan values mapped into microampere electrical fields).

2. **ASTRA-IC Paradigm (Dynamic PAT & Robust Outlier Detection)**:
   - Recognizes Dynamic Part Average Testing (DPAT), utilizing median and Median Absolute Deviation (MAD), Modified Z-scores, and threshold-based robust outlier detection.
   - *Crucial Project Guardrail*: We **DO NOT** claim *"competitors use mean/std while we use robust MAD"* as a universal differentiator. ASTRA-IC already demonstrates the use of median/MAD-based robust statistics.
   - Competitor rankings, synthetic leaderboards, and unverified "winner" claims are strictly rejected.

### 6.2 Architectural Hypotheses (Candidate Differentiators)

Our technical differentiation is based on structural system architecture, preserved as specific engineering hypotheses to be validated through controlled experimentation:

1. **Leave-One-Out Lot Reference**: Computing lot median and MAD strictly excluding the target device under evaluation ($j \ne i$), preventing self-contamination and leverage distortion in small lots ($N \sim 15\text{--}30$).
2. **Explicit Baseline-vs-Temporal-Deviation Decomposition**: Formally separating initial lot departure at $t=0$ ($b_i$) from temporal degradation drift ($g_i(t)$) within a mathematically consistent statistical space (log space for positive parameters, normalized by robust baseline scale).
3. **Separate Multi-Channel Evidence**: Explicitly distinguishing absolute limit status, peer outlier status, temporal trend status, and equipment common-mode status rather than collapsing them into a single opaque anomaly score.
4. **"As-Of" Temporal Integrity**: Structural contract ensuring that no model, scaler, baseline, or calibration cutoff at checkpoint $T$ ever accesses observations where $t > T$.
5. **Conformal Calibration vs. Fixed Cutoffs**: Conformal-style quantile calibration on known-normal verification devices to bound false-alarm rates ($\alpha$), avoiding brittle universal heuristics across disparate component families.
6. **Explicit Equipment / Common-Mode Discrimination**: Channel/instrument clustering to isolate shared test-fixture artifacts (`EQUIPMENT HOLD`) from genuine component-level physical degradation.
7. **Reproducible Audit Trail**: Immutable raw telemetry preservation (LOG-020) paired with cryptographic-style frozen screening configuration snapshots (`ScreeningRun`).

*Note: These seven distinctions represent architectural hypotheses and design choices, not proven advantages, until experimentally evaluated under controlled benchmark conditions.*
