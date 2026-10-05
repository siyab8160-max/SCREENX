# Final Holdout Governance Record: Redesigned Module B

**Document ID**: `GOV-MODULE-B-FINAL-HOLDOUT-001`  
**Governing Standard**: SIH 2026 Problem Statement SIH26170  
**Phase**: Step 1 — Final Holdout Reservation & Quarantine  
**Status**: **SEALED / DEVELOPMENT-INACCESSIBLE**  
**Creation Timestamp**: 2026-10-05T11:08:53Z UTC  
**Primary Holdout Location**: `data/evaluation/final_holdout/`  

---

## 1. Purpose and Rationale

This governance record documents the formal creation, cryptographic sealing, and permanent reservation of a new, genuinely untouched final holdout cohort (`LOT21`–`LOT24`) for the redesigned Module B temporal drift prognostic pipeline.

Prior evaluation phases in the Module B progression utilized:
- **Phase B1–B3**: Initial training cohorts (`LOT01`–`LOT08`).
- **Phase B4**: Split-conformal calibration partitioning (`LOT01`–`LOT06` proper train, `LOT07`–`LOT08` conformal calibration, `LOT09`–`LOT10` validation).
- **Phase B5**: Single-pass test evaluation on `LOT11`–`LOT14` ($N=320$ series).
- **Phase B6 / B6.6**: Final validation evaluation on `LOT15`–`LOT18`, with dedicated equipment/common-mode stress evaluation on `LOT19`–`LOT20`.

Under strict machine learning governance and anti-snooping rules, once a cohort has been revealed, evaluated, or reported, it is permanently ineligible as a fresh holdout for subsequent model iterations. The B6.6 holdout (`LOT15`–`LOT18`) and stress cohort (`LOT19`–`LOT20`) are therefore retired and contaminated with respect to the redesigned Module B.

---

## 2. Cohort Exclusion Audit

Every previously defined lot in the project's historical progression has been audited and permanently excluded from the fresh holdout:

| Cohort | Exact Lots | Historical Role | Ineligibility Rationale |
| :--- | :--- | :--- | :--- |
| **B1–B4 Proper Train** | `LOT01`–`LOT06` | Supervised model fitting | In-sample training exposure |
| **B4 Conformal Calibration** | `LOT07`–`LOT08` | Residual calibration ($Q_{1-\alpha}$) | Uncertainty quantile fitting exposure |
| **B4/B5 Validation** | `LOT09`–`LOT10` | Model selection & hyperparameter tuning | Validation tuning exposure |
| **B5 Final Test** | `LOT11`–`LOT14` | Phase B5 single-pass test evaluation | Previous reported test claims |
| **B6.6 Validation** | `LOT15`–`LOT18` | Phase B6.6 fresh validation cohort | Revealed and analyzed in B6.6 |
| **B6.6 Stress Cohort** | `LOT19`–`LOT20` | Equipment/common-mode stress cohort | Evaluated in B6.6 stress tests |
| **Unified Phase 2F** | `LOT_S01`–`LOT_W01` | Phase 2F benchmark freeze | Seen during Module A empirical screening |
| **Unified Phase 4B** | `LOT_CAL_001`–`050` | Phase 4B calibration partition | Used in Phase 5 LOLO and regression fit |
| **Unified Phase 4B** | `LOT_VAL_001`–`025` | Phase 4B validation partition | Used in Phase 5 model selection |
| **Unified Phase 4B** | `LOT_EVAL_001`–`025`| Phase 4B final evaluation partition | Evaluated in Phase 5 final evaluation |
| **Prototype Benchmark**| `L01`–`L14` | Early prototype synthetic dataset | Legacy synthetic testbed |

---

## 3. Selected Fresh Holdout Cohort

The newly selected and sealed holdout consists of four fresh manufacturing lots:

- **Lots**: `LOT21`, `LOT22`, `LOT23`, `LOT24`
- **Total Lots**: $4$
- **Components per Lot**: $20$
- **Total Components**: $80$ (`LOT21_C01`–`LOT21_C20`, `LOT22_C01`–`LOT22_C20`, `LOT23_C01`–`LOT23_C20`, `LOT24_C01`–`LOT24_C20`)
- **Total Evaluated Series**: $320$ ($80\text{ components} \times 4\text{ parameters}$)
- **Canonical Parameters**: `IDSS` ($\mu\text{A}$), `VGS(th)` ($\text{V}$), `RDS(on)` ($\text{m}\Omega$), `IGSS` ($\text{nA}$)
- **Checkpoints**: $0\text{h}$, $24\text{h}$, $96\text{h}$, $168\text{h}$
- **Burn-In Temperature**: $125.0^\circ\text{C}$
- **Generator**: `SyntheticBurnInGenerator` (`sih26170.synthetic.burnin_generator`)
- **Generator Version**: `v2.0.0`
- **Generation Mode**: `stress`
- **Master Seed**: `20261005` (brand-new deterministic integer seed)

---

## 4. Why the New Holdout Qualifies as Untouched

1. **Lot Disjointness**:
   $$\{\text{LOT21}, \text{LOT22}, \text{LOT23}, \text{LOT24}\} \cap \{\text{All Historical Lots}\} = \emptyset$$
2. **Component Disjointness**:
   $$\{\text{Component IDs of LOT21–LOT24}\} \cap \{\text{Historical Component IDs}\} = \emptyset$$
3. **Never Used in Training**: Zero models (Ridge, Huber, GBM, Tree, or Baseline) have fitted coefficients on these lots.
4. **Never Used in Calibration**: Zero non-conformity residuals or conformal quantiles have been evaluated on these lots.
5. **Never Used in Validation**: Zero hyperparameter sweeps or feature selection decisions have accessed these lots.
6. **Never Used in Tuning**: Zero decision thresholds, gating thresholds, or uncertainty scaling factors have been tuned on these lots.
7. **Never Used in Prior Evaluation**: These lots appear in zero prior reports, logs, or benchmark result summaries.
8. **No Documentation Contamination**: Neither `LOT21`, `LOT22`, `LOT23`, nor `LOT24` have previously been cited as targets or test sets.

---

## 5. Cryptographic Hashes & Integrity

All files in `data/evaluation/final_holdout/` have been verified with SHA-256 digests recorded in `checksums.sha256`:

| Artifact | File Path | SHA-256 Digest |
| :--- | :--- | :--- |
| **Observations** | `data/evaluation/final_holdout/observations.csv` | `c042b363dcc7eab5dbc89826062db38550d036b1ead67f229d2f87ee839b996e` |
| **Ground Truth** | `data/evaluation/final_holdout/ground_truth.csv` | `1bf1e74fda33cedad445e5c1d38049174c3319b9b4d0f9a27499a25d92268372` |
| **Manifest** | `data/evaluation/final_holdout/manifest.json` | `1a4bee77deba47364777022470d382514744a28d62363a01967638dff83534d8` |
| **Config Snapshot** | `data/evaluation/final_holdout/generator_config_snapshot.json` | `c3add1814c7847c8aa5ae19b1918ed051d6c384a8188cfeac9697c20c48ca247` |
| **Provenance** | `data/evaluation/final_holdout/provenance.json` | `771bb8faea3a7ee288591ef1fc5773177894a7e937d57a256f6ba50567e91d84` |

---

## 6. Access and Quarantine Rules

1. **Strict Development Inaccessibility**: This holdout must **NEVER** be accessed during feature engineering, model architecture exploration, hyperparameter tuning, model family selection (Ridge vs. Huber vs. GBM), uncertainty method calibration, or threshold determination.
2. **Wildcard Shielding**: Programmatic checks (`tests/prognostics/test_final_holdout_independence.py`) confirm that no training or evaluation script uses directory globbing or unconstrained iteration to load CSV files from `data/evaluation/final_holdout/`.
3. **One-Time Evaluation Protocol**: This holdout may be unlocked strictly **ONCE** for final single-pass evaluation after the redesigned Module B model architecture and pipeline are completely frozen and committed to the repository.
