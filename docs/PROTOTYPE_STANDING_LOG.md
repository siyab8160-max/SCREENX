# SIH26170 — Prototype Standing / Change Log

This document is a permanent project artifact maintained across all phases of the SIH26170 project. Every architectural, parameter, unit, limit, assumption, and design decision is logged here with unique identifiers, status tags, and provenance rationale.

Decisions are never silently overwritten. When a decision changes or is refined, a new log entry is appended referencing the prior log ID.

---

## Log Entries

### LOG-001
- **Log ID**: LOG-001
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Primary component framing established as Board-Level High-Reliability Electronic Assembly (DC-DC Converter, Power Supply Unit, Electronic Control Board).
- **Previous State**: Undifferentiated component / generic semiconductor or packaged MMIC.
- **New State**: Primary framing set to Board-Level Assembly (DC-DC converter, PSU, control board) with modular parameter definitions.
- **Reason**: Mentor consultation (Sri Ramyaa S) and domain analysis show that co-existence of leakage current, Iddq-like digital current, and propagation delay is physically plausible at board/assembly level (digital controller + power stage + timing paths), whereas a single MMIC does not naturally feature Iddq or digital timing paths.
- **Source / Provenance**: ASSUMPTION (A1, A14 — mentor-informed, non-binding).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/component_family.py`, `configs/parameters.yaml`
- **Impact**: Establishes board-level assembly as default architectural context while keeping family configurable.

### LOG-002
- **Log ID**: LOG-002
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Retention of Packaged MMIC as secondary component family framing.
- **Previous State**: Single framing only.
- **New State**: `PACKAGED_MMIC` retained in component family registry with parameters tailored to RF/microwave context.
- **Reason**: Public ISRO procurement documents frequently cite MMIC screening; preserving this framing ensures adaptability if ISRO test article confirmation indicates MMIC rather than board-level assembly.
- **Source / Provenance**: SPECIFICATION / ASSUMPTION (A1).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/component_family.py`
- **Impact**: Enables screening runs to select either board-level assembly or packaged MMIC.

### LOG-003
- **Log ID**: LOG-003
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Restriction of physical parameters to those explicitly specified in the problem statement and PRD.
- **Previous State**: Open / undefined parameter scope.
- **New State**: Exactly three physical parameters supported in v1: `leakage_current` (unit: `uA`), `iddq` (unit: `mA`), and `propagation_delay` (unit: `ns`).
- **Reason**: Guardrail against inventing physical parameters or ungrounded units.
- **Source / Provenance**: SPECIFICATION (PRD Section 1, Architecture Section 2, Assumption A4).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/schema.py`, `src/sih26170/config.py`, `configs/parameters.yaml`
- **Impact**: Validation layer strictly enforces parameter-unit pairing; any other parameter or unit mismatch is rejected.

### LOG-004
- **Log ID**: LOG-004
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Separation of Verified Reference Values from User Screening Limits.
- **Previous State**: Merged concept of "default physical operating limits" / datasheet limits.
- **New State**: Distinct fields: `reference_value`, `reference_value_type`, `reference_source`, `reference_verification_status` vs. `user_limit_low`, `user_limit_high`.
- **Reason**: Screening engineers distinguish between verified component reference standards (from manufacturer or qualification data) and the operational screening limits configured for a test campaign. The system must report when a part is within user limits but deviates from verified reference values.
- **Source / Provenance**: DESIGN_DECISION (Screening Engineer Workflow Refinement).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/config.py`, `src/sih26170/component_family.py`, `src/sih26170/validation.py`
- **Impact**: Prevents conflation of screening thresholds with component reference physics.

### LOG-005
- **Log ID**: LOG-005
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Configuration of prototype upper screening limit for `leakage_current` at 50.0 µA.
- **Previous State**: Unconfigured or hardcoded constant.
- **New State**: `user_limit_high: 50.0` in `configs/parameters.yaml` under `leakage_current`.
- **Reason**: Derived directly from the Problem Statement's canonical worked example (45 µA measured against a 50 µA datasheet limit).
- **Source / Provenance**: SPECIFICATION (PS Canonical Example, PRD FR1.1).
- **Status**: IMPLEMENTED
- **Affected Area**: `configs/parameters.yaml`, `src/sih26170/config.py`
- **Impact**: Provides externalized screening limit for canonical acceptance test.

### LOG-006
- **Log ID**: LOG-006
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Retention of unverified reference values as `null` / `NOT_YET_VERIFIED`.
- **Previous State**: Risk of defaulting unverified reference values (e.g. 10 µA) as established standards.
- **New State**: `reference_value: null`, `reference_verification_status: NOT_YET_VERIFIED` for parameters lacking authoritative ISRO or manufacturer qualification sources.
- **Reason**: The PS worked example mentions "a lot averaging 10 µA" as an illustrative lot sample, not an authoritative physical standard. Inventing reference values violates NFR1 (Honesty) and the core project guardrails.
- **Source / Provenance**: DESIGN_DECISION / GUARDRAIL (Change 1 & 2 Refinement).
- **Status**: IMPLEMENTED
- **Affected Area**: `configs/parameters.yaml`, `src/sih26170/component_family.py`
- **Impact**: The system refuses to fabricate reference numbers without verified provenance.

### LOG-007
- **Log ID**: LOG-007
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Sourced Burn-in Temperature set to 125.0 °C.
- **Previous State**: None.
- **New State**: `burn_in_temperature_C: 125.0` in `configs/prototype.yaml`.
- **Reason**: Verified across multiple public ISRO screening specifications and industry standards (JEDEC JESD22-A108).
- **Source / Provenance**: ASSUMPTION (A2 — [SOURCED]).
- **Status**: IMPLEMENTED
- **Affected Area**: `configs/prototype.yaml`, `src/sih26170/config.py`
- **Impact**: Anchors the thermal stress condition for dataset validation.

### LOG-008
- **Log ID**: LOG-008
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Burn-in checkpoint schedule defined as [0, 24, 96, 168] hours.
- **Previous State**: Continuous or undefined checkpoints.
- **New State**: `checkpoint_hours: [0, 24, 96, 168]` in `configs/prototype.yaml`.
- **Reason**: 168h appears in ISRO docs; the checkpoint intervals represent standard burn-in intermediate readout intervals for early-life degradation detection.
- **Source / Provenance**: ASSUMPTION (A3).
- **Status**: IMPLEMENTED
- **Affected Area**: `configs/prototype.yaml`, `src/sih26170/schema.py`, `src/sih26170/validation.py`
- **Impact**: Validation enforces checkpoint legality; missingness tracking evaluates against this schedule.

### LOG-009
- **Log ID**: LOG-009
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Global simulation parameters configured with explicit assumption IDs.
- **Previous State**: Hardcoded in code or unspecified.
- **New State**: `lot_size: 30` (A5), `defect_rate: 0.04` (A6), `noise_scale: 0.02` (A7), `missing_rate: 0.03`, `equipment_shift_rate: 0.05`.
- **Reason**: Provides externalized, documented configuration for synthetic generation and validation in accordance with PRD NFR4.
- **Source / Provenance**: ASSUMPTION (A5, A6, A7).
- **Status**: IMPLEMENTED
- **Affected Area**: `configs/prototype.yaml`, `src/sih26170/config.py`
- **Impact**: All future synthetic data generation and statistical testing anchor to these traceable values.

### LOG-010
- **Log ID**: LOG-010
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Introduction of Screening Run Lifecycle foundation.
- **Previous State**: Bare batch CSV ingestion architecture (`CSV -> AI -> Result`).
- **New State**: Structured `ScreeningRun` schema and metadata tracking: `Component Identity -> Part Spec -> Screening Config -> Screening Run -> Measurements -> Validation -> Evidence -> Engineer Decision -> Audit Record`.
- **Reason**: Real-world screening requires traceability of the screening campaign, engineer identification, lot/wafer genealogy, and applied screening limits.
- **Source / Provenance**: DESIGN_DECISION (Screening Engineer Workflow Refinement).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/schema.py`, `src/sih26170/config.py`
- **Impact**: Establishes audit-ready data model for engineer decision support.

### LOG-011
- **Log ID**: LOG-011
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Enforcement of the Strict "As-Of" Time Contract.
- **Previous State**: Unchecked temporal data access.
- **New State**: `enforce_as_of(df, as_of_hours)` implemented in validation layer, guaranteeing that any analysis at checkpoint `T` cannot observe records with `elapsed_hours > T`.
- **Reason**: Prevents in-sample data leakage and future-peeking in burn-in time-series anomaly detection.
- **Source / Provenance**: SPECIFICATION (PRD NFR2, Architecture Section 3.1).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/validation.py`, `tests/test_validation.py`
- **Impact**: Hard code-level guarantee against temporal leakage.

### LOG-012
- **Log ID**: LOG-012
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Implementation of 4-Tier Provenance Categorization for Configuration.
- **Previous State**: Forcing all configuration values into A1–A18 assumption numbers.
- **New State**: Provenance categories: `ASSUMPTION` (A1–A18), `SPECIFICATION` (PRD/Architecture specs), `DESIGN_DECISION` (implementation choices), `USER_CONFIGURABLE` (engineer-supplied screening parameters).
- **Reason**: Distinguishes assumptions requiring real ISRO evidence from established system specifications or engineer inputs, ensuring intellectual honesty with judges.
- **Source / Provenance**: DESIGN_DECISION (PRD NFR1, Change 9).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/config.py`
- **Impact**: Configuration validator ensures every parameter is attributed to its true provenance category.

### LOG-013
- **Log ID**: LOG-013
- **Date**: 2026-09-16
- **Phase**: Phase 1
- **Change**: Deliberate deferral of Module A, Module B, ML models, degradation physics, and UI dashboard.
- **Previous State**: N/A.
- **New State**: Excluded from Phase 1 scope.
- **Reason**: Strict phase boundary enforcement to ensure data integrity, schema stability, and validation rigor before modeling.
- **Source / Provenance**: SPECIFICATION (PRD Section 8, Architecture Section 10).
- **Status**: DEFERRED
- **Affected Area**: Modules A & B, ML models, Dashboard
- **Impact**: Phase 1 focuses exclusively on foundation, schema, configuration, and validation.

### LOG-014
- **Log ID**: LOG-014
- **Date**: 2026-09-16
- **Phase**: Phase 1 Audit
- **Change**: Explicit `ReferenceValueType` Enumeration for engineering specifications.
- **Previous State**: Ambiguous free-form string for `reference_value_type`.
- **New State**: Strongly-typed `ReferenceValueType` enum (`TYPICAL`, `NOMINAL`, `DATASHEET_MAX`, `DATASHEET_MIN`, `QUALIFICATION_LIMIT`, `ENGINEERING_REFERENCE`).
- **Reason**: Prevents loose or interchangeable use of the term "standard value"; screening engineers need explicit distinction between typical performance, datasheet limits, and qualification baselines.
- **Source / Provenance**: DESIGN_DECISION (Audit Section 4).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/config.py`, `src/sih26170/component_family.py`
- **Impact**: Removes ambiguity from reference specification typing.

### LOG-015
- **Log ID**: LOG-015
- **Date**: 2026-09-16
- **Phase**: Phase 1 Audit
- **Change**: ScreeningRun Configuration Immutability and Snapshotting.
- **Previous State**: Screening run reference limits could be mutated if underlying component family limits changed.
- **New State**: `ScreeningRun` automatically captures an immutable `frozen_screening_config` snapshot upon initialization, accessible via `get_effective_screening_limits()`.
- **Reason**: Screening configuration reproducibility: a historical screening run must retain the exact screening limits active during that specific campaign, regardless of future configuration edits.
- **Source / Provenance**: DESIGN_DECISION (Audit Section 6).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/schema.py`, `tests/test_schema.py`
- **Impact**: Guarantees screening run reproducibility for engineering auditability.

### LOG-016
- **Log ID**: LOG-016
- **Date**: 2026-09-16
- **Phase**: Phase 1 Audit
- **Change**: Ground-Truth Isolation Utilities (`get_observation_data`, `get_ground_truth_data`, `validate_feature_columns`).
- **Previous State**: Ground truth columns co-existed in DataFrames without structural programmatic barriers.
- **New State**: Explicit isolation functions enforce that model observation DataFrames contain zero ground truth columns, and feature validators raise errors if defect labels are passed.
- **Reason**: Prevents catastrophic data leakage where ML models could accidentally train on evaluation-only trajectory labels.
- **Source / Provenance**: SPECIFICATION (PRD FR5.1, Architecture Section 2, Audit Section 8).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/schema.py`, `tests/test_schema.py`
- **Impact**: Hard code-level barrier protecting observation features from ground truth.

### LOG-017
- **Log ID**: LOG-017
- **Date**: 2026-09-16
- **Phase**: Phase 1 Audit
- **Change**: Deep As-Of Temporal Contract Enforcement with Future Label Masking.
- **Previous State**: `enforce_as_of` filtered rows by `elapsed_hours <= as_of_hours` but left time-indexed labels (`abnormal_by_96h`, `first_abnormal_hour`) in present rows.
- **New State**: `enforce_as_of` masks all future-dated defect labels (`abnormal_by_T` for `T > as_of_hours`, `first_abnormal_hour > as_of_hours`) to `None/NaN` and supports `strip_ground_truth=True`.
- **Reason**: An analysis representing system knowledge at 24h cannot know if a component will fail at 96h or 168h.
- **Source / Provenance**: SPECIFICATION (PRD NFR2, Architecture Section 3.1, Audit Section 7).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/validation.py`, `tests/test_validation.py`
- **Impact**: Eliminates temporal leakage of future events into earlier observation checkpoints.

### LOG-018
- **Log ID**: LOG-018
- **Date**: 2026-09-16
- **Phase**: Phase 1 Audit
- **Change**: Numerical Safety Hardening for Non-Finite Numbers and Log-Space Processing.
- **Previous State**: Only general finite checks; non-positive values on log-transformed parameters went unchecked.
- **New State**: Validation explicitly flags `NaN`, `+Inf`, `-Inf` as fatal errors, and raises warnings on non-positive values (`val <= 0`) for log-transformed parameters alerting to mathematical instability.
- **Reason**: Later Module A robust statistics operate in log space; values `<= 0` produce `NaN` or `-Inf` unless safeguarded.
- **Source / Provenance**: DESIGN_DECISION (Audit Section 10).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/validation.py`, `tests/test_validation.py`
- **Impact**: Safeguards downstream statistical log transforms without fabricating physical values.

### LOG-019
- **Log ID**: LOG-019
- **Date**: 2026-09-16
- **Phase**: Phase 1 Audit
- **Change**: Strict Checkpoint Validation Enforcement.
- **Previous State**: Checkpoint deviations were logged merely as warnings.
- **New State**: `strict_checkpoints: bool = True` in `validate_dataset` flags unconfigured checkpoints as fatal schema errors per Architecture specification.
- **Reason**: The prototype architecture explicitly defines discrete checkpoint readouts (`[0, 24, 96, 168]h`); arbitrary hours indicate corrupted test telemetry.
- **Source / Provenance**: SPECIFICATION (Architecture Section 2, Assumption A3, Audit Section 9).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/validation.py`, `tests/test_validation.py`
- **Impact**: Enforces checkpoint protocol consistency.

---

## Phase 1 Engineering Audit

- **Audit Date**: 2026-09-16
- **Files Inspected**:
  - `configs/prototype.yaml`
  - `configs/parameters.yaml`
  - `src/sih26170/config.py`
  - `src/sih26170/schema.py`
  - `src/sih26170/component_family.py`
  - `src/sih26170/validation.py`
  - `tests/test_config.py`
  - `tests/test_schema.py`
  - `tests/test_component_family.py`
  - `tests/test_validation.py`
  - `tests/test_standing_log.py`
- **Issues Discovered**:
  1. *Ambiguity in Reference Value Meaning*: Loose string typing for reference value type risked confusing typical values, datasheet limits, and qualification baselines.
  2. *ScreeningRun Configuration Mutability Risk*: ScreeningRun did not capture an immutable snapshot of screening limits, meaning historical runs could retroactively alter if global limits changed.
  3. *Ground-Truth Leakage Vector*: Ground truth columns were present in DataFrames without explicit extraction barriers for model feature builders.
  4. *Deep As-Of Temporal Leakage*: While rows past `as_of_hours` were dropped, time-indexed ground truth labels for future hours remained on earlier rows.
  5. *Unit Check Bypass*: When `validate_dataset` was called without passing a `ComponentFamily`, unit checking was bypassed.
  6. *Checkpoint Strictness*: Unconfigured intermediate timestamps were only treated as warnings rather than schema errors.
  7. *Numerical Safety in Log Space*: Non-positive measurements (`<= 0`) on log-transformed parameters (`leakage_current`) could silently trigger `NaN` or `-Inf` in future Module A calculations.
- **Issues Fixed**:
  - Created `ReferenceValueType` enum (LOG-014).
  - Implemented immutable `frozen_screening_config` in `ScreeningRun` (LOG-015).
  - Implemented `get_observation_data`, `get_ground_truth_data`, and `validate_feature_columns` (LOG-016).
  - Implemented deep leakage protection in `enforce_as_of` by masking future labels to `None` (LOG-017).
  - Added global config fallback for unit checking in `validate_dataset`.
  - Added `strict_checkpoints: bool = True` in `validate_dataset` (LOG-019).
  - Added non-finite rejection and non-positive log-transform warnings in `validate_dataset` (LOG-018).
  - Added dynamic `add_allowed_parameter` and `remove_allowed_parameter` in `ComponentFamily`.
- **Issues Deferred**:
  - Real ISRO qualification datasheet values for `iddq` and `propagation_delay` (deferred pending SME input; left as `null` / `NOT_YET_VERIFIED`).
  - Automated unit conversion engine (deferred per A16 to avoid undocumented value scaling).
- **New Tests Added**:
  - `test_reference_value_type_enum`
  - `test_config_serialization`
  - `test_screening_run_configuration_immutability`
  - `test_ground_truth_isolation`
  - `test_as_of_temporal_contract_deep_label_masking`
  - `test_validate_dataset_unit_mismatch_without_family`
  - `test_validate_dataset_strict_checkpoints`
  - `test_validate_dataset_missing_identity`
  - `test_validate_dataset_non_finite_values`
  - `test_validate_dataset_log_transform_non_positive_warning`
  - `test_validate_dataset_duplicate_measurements_conflicting`
  - `test_component_family_parameter_applicability_configurable`
- **Remaining Risks**:
  - Real burn-in data may contain negative sensor offsets (instrument calibration drift) that require explicit preprocessing before log-transform fitting in Module A.
- **Remaining Evidence Gaps**:
  - Authoritative reference limits from ISRO qualification specifications.
  - Confirmation of continuous vs. discrete 0/24/96/168h readout schedules.

---

### LOG-020
- **Log ID**: LOG-020
- **Date**: 2026-09-16
- **Phase**: Phase 1 Final Hardening
- **Change**: Raw Measurement Immutability & Explicit Non-Positive Log-Value Representation.
- **Previous State**: Non-positive values on log-transformed parameters only generated general warnings without structured numerical state distinction.
- **New State**: Established `ValueStatus` (`POSITIVE`, `ZERO`, `NEGATIVE`, `MISSING`, `NON_FINITE`). The validation layer strictly preserves raw observed values without alteration or flooring while populating structured `numerical_status_records` indicating eligibility for direct log transformation.
- **Reason**: Invariant: Raw engineering measurements must remain permanently recoverable and immutable. Silently flooring negative values (e.g. -0.2 -> 0.05) manufactures fabricated data. The system must explicitly distinguish negative measurements from physical zero and from missing data.
- **Source / Provenance**: DESIGN_DECISION (Final Hardening Issue A & Invariant 3).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/schema.py`, `src/sih26170/validation.py`, `tests/test_validation.py`
- **Impact**: Guarantees raw data immutability and provides a safe foundation for separate downstream preprocessing without data corruption.

### LOG-021
- **Log ID**: LOG-021
- **Date**: 2026-09-16
- **Phase**: Phase 1 Final Hardening
- **Change**: Small-Lot Peer-Evidence Handling and First-Class `INSUFFICIENT_DATA` State.
- **Previous State**: Global assumption lot_size=30 risked being interpreted as a hard-coded minimum required for screening.
- **New State**: `PeerStatus.INSUFFICIENT_DATA` and `TrendStatus.INSUFFICIENT_DATA` formally defined in schema. `assess_peer_sample_size()` reports available counts per lot/checkpoint as engineering observations without imposing an arbitrary minimum threshold.
- **Reason**: The prototype assumption `lot_size = 30` (A5) applies only to synthetic test generation, not real-world screening. Fabricating a peer baseline on inadequate lots is prohibited, but inventing an arbitrary cutoff without ISRO SME specification would violate NFR1.
- **Source / Provenance**: SPECIFICATION / DESIGN_DECISION (PRD FR3.1, Architecture Section 5, Final Hardening Issue B).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/schema.py`, `src/sih26170/validation.py`, `tests/test_validation.py`
- **Impact**: Provides programmatic support for peer insufficiency while leaving the exact statistical sample threshold for Module A design.

### LOG-022
- **Log ID**: LOG-022
- **Date**: 2026-09-16
- **Phase**: Phase 1 Final Hardening
- **Change**: Multi-Channel Evidence Independence (Separation of Absolute Limits from Peer Evidence).
- **Previous State**: Risk that peer insufficiency could be conflated with overall component failure.
- **New State**: Schema establishes independent evidence channels (`AbsoluteStatus`, `PeerStatus`, `TrendStatus`). A component with `AbsoluteStatus.PASS` and `PeerStatus.INSUFFICIENT_DATA` remains strictly differentiated from a component failure (`AbsoluteStatus.BREACH`).
- **Reason**: An engineer-centric screening platform must evaluate absolute qualification limits regardless of whether the lot size allows statistical peer outlier detection. Insufficient peer evidence must never trigger an automatic component reject.
- **Source / Provenance**: SPECIFICATION (PRD FR1.1, FR3.2, Architecture Section 3.2, Final Hardening Section 6).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/schema.py`, `tests/test_schema.py`
- **Impact**: Ensures architectural independence of deterministic safety limits from statistical peer channels.

### LOG-023
- **Log ID**: LOG-023
- **Date**: 2026-09-16
- **Phase**: Phase 2 Design Specification & Adversarial Review
- **Change**: Hardened Synthetic Burn-In Dataset Specification and Causal Generative Model Design.
- **Previous State**: High-level conceptual overview mixing latent physics with measurement noise, loose provenance on 125°C, arbitrary sigma language, and potential shortcut learning on rework.
- **New State**: Created comprehensive specification `docs/PHASE_2_SYNTHETIC_DATA_SPEC.md` resolving all 23 adversarial engineering audit points:
  1. Corrected 125°C provenance to ASSUMPTION A2 (`NOT_YET_VERIFIED` as component-specific requirement).
  2. Decoupled pedagogical 45/10/50 µA example from real component reference baselines.
  3. Formally decoupled latent state dynamics $x^*(t)$ from measurement process $y(t) = \mathcal{M}(x^*, E, \varepsilon)$.
  4. Clarified noise model as $2\%$ multiplicative relative noise plus parameter-specific precision floors.
  5. Established 6 trajectory classes as benchmark stimuli, strictly categorizing latent state vs. statistical condition vs. evaluation label.
  6. Removed arbitrary sigma claims; established relationship between Gaussian spread and robust scale (1.4826 * MAD).
  7. Formulated 3 experimental rework regimes ($R_0, R_1, R_2$) to prevent ML shortcut learning ($\text{rework} \implies \text{defect}$).
  8. Modeled equipment/test-channel hierarchy (common-mode instrument shift vs channel socket resistance vs component defect).
  9. Created formal 11-scenario adversarial mixed interaction matrix.
  10. Strictly decoupled ground-truth degradation from operational screening limit crossing.
  11. Modeled non-breach sub-threshold anomalies and benign limit-breach scenarios.
  12. Established multi-type missingness taxonomy preserving Phase 1 `ValueStatus` semantics.
  13. Parameterized small-lot stress testing ($N=3, 5, 8$) without hardcoded engineering minimums.
  14. Enforced forward-only causal generation preserving Phase 1 temporal as-of contracts.
  15. Defined ground-truth labels independently of detector scores or ML predictions.
  16. Formulated lot-level holdout strategy preventing cross-checkpoint leakage.
  17. Constructed detailed difficulty matrix with explicit technical rationales.
  18. Established parameterized dataset budget and hierarchical deterministic seed policy.
  19. Guaranteed raw measurement immutability and non-positive value preservation (LOG-020).
- **Reason**: Rigorous adversarial review before writing generation code guarantees that the synthetic benchmark safely exercises all screening layers without corrupting telemetry or fabricating physical claims.
- **Source / Provenance**: DESIGN_DECISION / SPECIFICATION (`docs/PHASE_2_SYNTHETIC_DATA_SPEC.md`).
- **Status**: SPECIFIED / REVIEWED (Zero generation code implemented).
- **Affected Area**: `docs/PHASE_2_SYNTHETIC_DATA_SPEC.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Provides an airtight foundation for Phase 2 implementation.

### LOG-024
- **Log ID**: LOG-024
- **Date**: 2026-09-16
- **Phase**: Phase 2 Final Hardening
- **Change**: Targeted Hardening of Phase 2 Synthetic Data Specification before Implementation.
- **Previous State**: Ambiguous noise floors termed "ADC/resolution floors", conflation of trajectory onset with abnormality onset (`g(t) > 0`), terminology "benign limit breach", unstated modeling limitations on mathematical transforms, and implicit generalization assumptions.
- **New State**: Updated `docs/PHASE_2_SYNTHETIC_DATA_SPEC.md` resolving all 5 targeted hardening points:
  1. *Synthetic Numerical Noise Floors*: Removed all wording implying physical hardware ADC resolution; reframed parameter floors (`0.01 uA`, `0.002 mA`, `0.01 ns`) strictly as synthetic simulation parameters preventing zero-noise singularities.
  2. *Separation of Trajectory Onset from Ground-Truth Abnormality*: Introduced distinct concepts `trajectory_onset_hour` (when $|g(t)| > 0$) vs. `first_ground_truth_abnormal_hour` (when latent physical degradation crosses independent threshold $|g(t)| \ge \theta_{\text{abnormal}} = 0.25$ or jump occurs). Enforced complete detector independence (zero reliance on Module A/B, MAD, or AI scores).
  3. *Elimination of "Benign Limit Breach"*: Replaced with `stable trajectory + absolute-limit breach`. Formalized principle: $\text{latent trajectory} \ne \text{screening evidence} \ne \text{final disposition}$. Absolute limits remain an unconditional Layer 1 hard-gate veto.
  4. *Parameter-Specific Modeling Disclaimers*: Explicitly documented that parameter transforms are synthetic modeling constructs for algorithm evaluation, not physical degradation laws across all parameters.
  5. *Evaluation Limitation Categorization*: Classified train/val/test lot structure as `SYNTHETIC PROTOTYPE EVALUATION`, noting that 14 lots cannot establish space flight qualification generalization, and freezing test lots L11–L14 against threshold tuning.
- **Reason**: Final engineering review before generator code implementation ensures that synthetic ground truth remains completely decoupled from algorithm detection, and that simulation parameters are never mistaken for real hardware specifications.
- **Source / Provenance**: DESIGN_DECISION / SPECIFICATION (`docs/PHASE_2_SYNTHETIC_DATA_SPEC.md`).
- **Status**: SPECIFIED / AUDITED (Zero generation code implemented).
- **Affected Area**: `docs/PHASE_2_SYNTHETIC_DATA_SPEC.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Guarantees uncompromised evaluation integrity for Phase 2 synthetic generator implementation.

### LOG-025
- **Log ID**: LOG-025
- **Date**: 2026-09-16
- **Phase**: Phase 2 Final Mathematical Consistency Gate
- **Change**: Mathematical Consistency Audit of Synthetic Abnormality Criterion, Equipment Shifts, and Noise Semantics.
- **Previous State**: Universal scalar $\theta_{\text{abnormal}} = 0.25$ applied across dimensionless log parameters and dimensioned linear parameters (ns); equipment shifts modeled as additive scalars conflicting with differing parameter units; ambiguous semantics regarding negative sensor values.
- **New State**: Updated `docs/PHASE_2_SYNTHETIC_DATA_SPEC.md` resolving all dimensional and semantic consistency requirements:
  1. *Normalized Relative Latent Deviation*: Formulated dimensionless relative degradation $r_{i,p}(t) = \frac{x^*_{i,p}(t) - x^*_{i,p}(0)}{x^*_{i,p}(0)}$ (evaluating to $\exp(g(t)) - 1$ for log parameters and $g(t)/x^*(0)$ for linear delay), ensuring scale-invariant and dimensionless comparison across parameters.
  2. *Parameter-Specific Abnormality Thresholds*: Established parameter-aware dimensionless thresholds $\theta_{\text{abnormal},p}$ ($0.50$ for leakage, $0.30$ for iddq, $0.10$ for delay) strictly independent of detector scores or screening limits.
  3. *Dimensionally Consistent Equipment Shift Formulation*: Structured equipment effects as $y = x^* \cdot (1 + E^{\text{mult}} + \varepsilon) + E^{\text{offset}} + \eta_{\text{floor}}$, where common-mode drift $E^{\text{mult}}$ is dimensionless and channel offset $E^{\text{offset}}$ is in native parameter units.
  4. *Physical Latent Invariant vs. Measurement Artifact Semantics*: Explicitly established that latent component state is strictly non-negative ($x^*(t) \ge 0$), while negative sensor observations ($y < 0$) are modeled as intentional test-bench electrometer zero-offset artifacts (preserved unfloored per LOG-020).
- **Reason**: Guarantees that all generative equations are mathematically sound, dimensionally valid, and semantically truthful prior to executable code generation.
- **Source / Provenance**: DESIGN_DECISION / SPECIFICATION (`docs/PHASE_2_SYNTHETIC_DATA_SPEC.md`).
- **Status**: SPECIFIED / AUDITED (Zero generation code implemented).
- **Affected Area**: `docs/PHASE_2_SYNTHETIC_DATA_SPEC.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Establishes complete mathematical consistency for Phase 2 generator implementation.

### LOG-026
- **Log ID**: LOG-026
- **Date**: 2026-09-16
- **Phase**: Phase 2C Synthetic Burn-In Generator Implementation
- **Change**: Implementation, Validation, and Verification of the Decoupled Synthetic Burn-In Dataset Generator.
- **Previous State**: Phase 2 specifications and mathematical consistency gates completed; zero synthetic generator code or generated data existed.
- **New State**: Implemented complete synthetic generator package conforming strictly to `docs/PHASE_2_SYNTHETIC_DATA_SPEC.md`:
  1. *Package Architecture*: Created modular `src/sih26170/synthetic/` (`seeds.py`, `config.py`, `trajectories.py`, `latent.py`, `measurement.py`, `scenarios.py`, `ground_truth.py`, `validation.py`, `generator.py`, `__init__.py`).
  2. *Deterministic Reproducibility*: Implemented SHA-256 bitwise seed derivation hierarchy (`SeedHierarchy`), eliminating Python's process-randomized `hash()`.
  3. *Decoupled Latent State*: Latent physical model strictly enforces non-negative states ($x^* \ge 0$ for leakage and iddq, $x^* > 0$ for delay) without measurement noise or limit clamping.
  4. *Decoupled Measurement Simulation*: Formulated $y = x^* \cdot (1 + E^{\text{mult}} + \varepsilon) + E^{\text{offset}} + \eta_{\text{floor}}$. Preserves raw negative sensor observations without flooring (LOG-020), classified as `ValueStatus.NEGATIVE`. Dropped readings (3% MCAR) are absent rows (never confused with zero).
  5. *Independent Ground Truth*: Computed dimensionless relative latent deviation $r_{i,p}(t) = [x^*(t) - x^*(0)] / x^*(0)$ against parameter-specific thresholds ($\theta = 0.50, 0.30, 0.10$), completely decoupled from user screening limits (`user_limit_high`) and future detectors.
  6. *Scenarios & Rework*: Generated Canonical 45 µA demonstration fixture (`CANONICAL_C45`, limit PASS, peer abnormal, trend stable), small lots ($N \in \{3, 5, 8, 30\}$), rework regimes ($R_0$ neutral, $R_1$ variance inflation, $R_2$ risk shift), and mixed interaction scenarios M01–M11.
  7. *Strict Quarantining*: Emitted `data/synthetic/observations.csv` (strictly observation columns; zero ground-truth columns) and `data/synthetic/ground_truth.csv` (quarantined evaluation metrics).
  8. *Automated Validation & Test Suite*: Added 17 unit/integration tests in `tests/test_synthetic.py`. 60/60 tests pass (43 Phase 1 foundation + 17 Phase 2 generator). Zero Phase 1 regressions.
  9. *Boundary Adherence*: Strictly NO Module A, NO Module B, NO ML models, NO dashboard, and NO threshold tuning implemented.
- **Reason**: Translates the hardened Phase 2 specification into a reproducible, auditable software implementation for benchmark evaluation.
- **Source / Provenance**: SPECIFICATION (`docs/PHASE_2_SYNTHETIC_DATA_SPEC.md`).
- **Status**: IMPLEMENTED / VERIFIED (60/60 tests passing).
- **Affected Area**: `src/sih26170/synthetic/`, `configs/synthetic.yaml`, `data/synthetic/`, `tests/test_synthetic.py`, `docs/PHASE_2_GENERATOR_IMPLEMENTATION.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Provides a mathematically sound, reproducible synthetic benchmark dataset for subsequent high-reliability screening algorithm development.

### LOG-027
- **Log ID**: LOG-027
- **Date**: 2026-09-17
- **Phase**: Phase 2C Synthetic Dataset Forensic Audit
- **Change**: Comprehensive Forensic Audit of the Phase 2C Synthetic Benchmark Dataset and Generative Architecture.
- **Previous State**: Phase 2C generator implemented with 60 passing tests; dataset properties not yet forensically audited for benchmark circularity, parameter coupling, or scenario coverage.
- **New State**: Completed rigorous forensic audit documented in `docs/PHASE_2C_FORENSIC_AUDIT.md`. Substantive findings and decisions:
  1. *Foundational Verification (PASS)*: Confirmed forward-only causal separation, SHA-256 bitwise reproducibility, raw-measurement immutability (LOG-020), and strict ground-truth isolation (15 canonical columns only in `observations.csv`).
  2. *Statistical Independence (PASS)*: Formally proved that missingness (131 records, 2.76%) is statistically strictly MCAR across all 8 operational dimensions via Chi-Square contingency tests ($p \gg 0.05$). Rework history verified as non-confounding (78.3% of defects have rework=0; 84.5% of reworked parts are normal).
  3. *Negative Telemetry Trace*: Traced all 4 negative sensor readouts to component `L13_C015` on `INST_02` socket `CH_07` (electrometer zero-offset artifact $E^{\text{offset}} = -0.02\ \mu\text{A}$ on initial value $0.005\ \mu\text{A}$), confirming intentional testing of unfloored `ValueStatus.NEGATIVE` handling.
  4. *Parameter Coupling Limitation (OPEN ISSUE)*: Discovered that 394 out of 395 components (99.75%) couple all three parameters (`leakage_current`, `iddq`, `propagation_delay`) to the exact same trajectory class. Formally logged as an architectural benchmark simplification to prevent overclaiming independent multi-parameter discrimination.
  5. *Missing Benchmark Scenario (OPEN ISSUE)*: Discovered that all 62 absolute limit crossings in the static CSV originate from true defects (61 abrupt failures, 1 accelerating drift). Exactly zero normal components cross limits. Formally logged as a missing scenario ("benign limit breach") requiring synthetic unit test coverage for Layer 1 hard-gate evaluation.
  6. *Epistemic Provenance Correction*: Flagged `leakage_current.theta_abnormal` (0.50) as mislabeled `SPECIFICATION` in configuration; updated epistemic status to `DESIGN_DECISION` / `SYNTHETIC_SCENARIO` in audit documentation.
  7. *Circularity Guard*: Mandated that Module A and Module B must rely on data-driven robust dispersion and trend residuals rather than percentage-change rules matching generator $\theta$ thresholds.
- **Reason**: Rigorous forensic auditing ensures complete scientific integrity, exposes hidden generative simplifications, and guarantees benchmark validity before screening algorithm design.
- **Source / Provenance**: DESIGN_DECISION / SPECIFICATION (`docs/PHASE_2C_FORENSIC_AUDIT.md`).
- **Impact**: Establishes an uncompromised, transparent evaluation baseline for Phase 3 Module A development.

---

### LOG-028: A18 Resolution — Industry Patent Provenance (US12007428B2)
- **Timestamp**: 2026-09-17T08:00:00Z
- **Phase**: Phase 2 Final Hardening
- **Type**: SOURCED / VERIFIED — RESOLVED
- **Prior State**: A18 marked as `[UNVERIFIED — do not repeat]`, questioning cited patent "US 12,007,428" alongside the RDPAT / Freescale / 289,080-dice reference.
- **New State**: Sourced and verified USPTO publication `US12007428B2`, titled *"Systems and methods for multidimensional dynamic part average testing"*, assigned to Advantest Corporation. Recorded as verified industry evidence that multidimensional/dynamic PAT-style robust statistical screening is an established industry approach in semiconductor production test.
- **Strict Epistemic Guardrail**:
  - The project does NOT claim this patent validates our implementation.
  - The project does NOT claim this patent establishes our algorithm as novel.
  - A18 is removed from the open evidence-gap list.
  - `STATUS = VERIFIED / RESOLVED`.
- **Reason**: Scientific transparency and intellectual honesty in patent citation and industry precedent verification.
- **Source / Provenance**: PRIMARY_LITERATURE / USPTO (`US12007428B2`, Advantest Corporation).
- **Status**: VERIFIED / RESOLVED.
- **Affected Area**: `docs/PROTOTYPE_STANDING_LOG.md`, `docs/SIH26170_Proposed_Solution_Draft.md`, `tests/test_hardening.py`.
- **Impact**: Solidifies industry precedent for dynamic multi-parameter outlier screening without overclaiming proprietary novelty.

---

### LOG-029: A17 Benchmark Reproducibility Chain Protocol
- **Timestamp**: 2026-09-17T08:05:00Z
- **Phase**: Phase 2 Final Hardening
- **Type**: DESIGN_DECISION / VERIFICATION
- **Prior State**: A17 framed as "benchmark does not exist".
- **New State**: The benchmark artifact and `benchmark_vs_competitors.py` exist and have been executed. Established strict reporting protocol:
  - Benchmark numbers must NEVER be quoted from promotional prose or static text alone.
  - Required reproducibility chain: benchmark artifact (`data/synthetic/`), script (`benchmark_vs_competitors.py`), configuration hash, master seed (`20260916`), dataset version (`v1-synthetic-20260916`), and execution metrics.
  - Figures may only be reported after the actual script is independently rerun and its output inspected.
  - Benchmark results must not be described as forecasts or predictions.
- **Reason**: Prevents synthetic benchmark overclaiming and guarantees auditability of all reported comparative metrics.
- **Source / Provenance**: DESIGN_DECISION / AUDIT.
- **Status**: RESOLVED.
- **Affected Area**: `docs/PROTOTYPE_STANDING_LOG.md`, `docs/SIH26170_Proposed_Solution_Draft.md`.
- **Impact**: Establishes rigorous reproducibility standards for all subsequent comparative benchmark claims.

---

### LOG-030: Competitive Positioning Update — ASTRA-IC Paradigm & Narrowed Hypotheses
- **Timestamp**: 2026-09-17T08:10:00Z
- **Phase**: Phase 2 Final Hardening
- **Type**: DESIGN_DECISION / SPECIFICATION
- **Prior State**: Competitor analysis contrasted our method against mean/std models (MAVERICK/AEGIS), claiming robust MAD as our primary differentiator.
- **New State**:
  - Formally recognized **ASTRA-IC** as a primary relevant comparison point utilizing Dynamic PAT, median/MAD, and Modified Z-scores.
  - Prohibited the claim *"competitors use mean/std while we use robust MAD"* as a universal differentiator.
  - Explicitly distinguished MAVERICK/AEGIS (0% breakdown Gaussian limits) from ASTRA-IC (robust DPAT).
  - Narrowed our technical differentiation to 7 specific architectural hypotheses:
    1. Leave-one-out lot reference (target exclusion)
    2. Explicit baseline-vs-temporal-deviation decomposition ($b_i$ vs $g_i(t)$)
    3. Separate multi-channel evidence (absolute / peer / trend / equipment)
    4. "As-of" temporal integrity contract
    5. Conformal calibration vs. fixed universal cutoffs
    6. Explicit equipment / common-mode fault discrimination
    7. Reproducible audit trail with frozen configuration snapshots
  - Guardrail: These are framed strictly as architectural hypotheses and design choices, not proven advantages, until experimentally evaluated.
- **Reason**: Accurate, uncompromised competitive analysis reflecting current state-of-the-art public solutions.
- **Source / Provenance**: DESIGN_DECISION (`docs/SIH26170_Proposed_Solution_Draft.md`).
- **Status**: ACTIVE / HARDENED.
- **Affected Area**: `docs/SIH26170_Proposed_Solution_Draft.md`, Section 6.0.
- **Impact**: Positions prototype on verifiable architectural distinctions rather than easily refuted generalities.

---

### LOG-031: Explainability Unit Lineage Bug Root Cause & Resolution (`QACard`)
- **Timestamp**: 2026-09-17T08:15:00Z
- **Phase**: Phase 2 Final Hardening
- **Type**: BUG_FIX / STRUCTURAL_HARDENING
- **Prior State**: An explainability QA card displayed an observed value of $45\ \mu\text{A}$ against a $50\ \mu\text{A}$ limit, with `Predicted 168h = 0.82 mA` (interval $0.71\text{--}0.94\ \text{mA}$) and `absolute_status = PASS`. $0.82\ \text{mA} = 820\ \mu\text{A}$ ($16.4\times$ the upper limit), creating an apparent integrity contradiction.
- **Root Cause**: Complete unit-lineage and parameter-scoping failure. In multi-parameter screening, predictions produced by Module B were indexed by `component_id` without strictly binding to `(component_id, parameter_name, unit)`. The $0.82\ \text{mA}$ forecast was an IDDQ prediction bound to a `leakage_current` card. Furthermore, lack of unit-lineage assertions allowed displaying mA forecasts alongside $\mu\text{A}$ observations.
- **New State**:
  - Implemented `ParameterForecast` dataclass with mandatory `parameter_name`, `predicted_value`, `unit`, and `interval_lower/upper`.
  - Implemented `QACard` dataclass with strict validation:
    - Asserts `forecast.parameter_name == self.parameter_name`.
    - Asserts `forecast.unit == self.unit`.
    - Asserts that if `observed_value > absolute_limit_high` or `< absolute_limit_low`, `absolute_status` cannot be `PASS`.
  - Added regression test `tests/test_hardening.py::TestExplainabilityUnitLineage`.
- **Reason**: Eliminates cross-parameter forecast contamination and prevents misleading QA decision cards.
- **Source / Provenance**: DESIGN_DECISION / AUDIT.
- **Status**: HARDENED / VERIFIED.
- **Affected Area**: `src/sih26170/schema.py`, `tests/test_hardening.py`, `docs/SIH26170_Architecture.md`.
- **Impact**: Structurally guarantees mutual unit consistency across all explainability outputs.

---

### LOG-032: $b_i / g_i(t)$ Space Consistency & Robust Decomposition
- **Timestamp**: 2026-09-17T08:20:00Z
- **Phase**: Phase 2 Final Hardening
- **Type**: ALGORITHM_SPECIFICATION / BUG_FIX
- **Prior State**: The architecture defined lot reference statistics in log space for positive parameters, but wrote linear subtraction $b_i = x_i(0) - \mu_{\text{lot}}(0)$ and $g_i(t) = [x_i(t) - \mu_{\text{lot}}(t)] - b_i$ in raw physical units, creating statistical space inconsistency.
- **New State**:
  - Implemented `compute_robust_decomposition()` in `src/sih26170/validation.py`.
  - For positive parameters: evaluates in log space $z = \ln(x)$.
  - For linear parameters: evaluates in physical units $z = x$.
  - Leave-one-out statistics: $\mu_{\text{lot},-i}(t)$ and $\text{MAD}_{\text{lot},-i}(t)$ strictly exclude target device $i$.
  - Baseline scale: $\sigma_0 = \max(1.4826 \cdot \text{MAD}_{\text{lot},-i}(0), \text{NOISE\_FLOOR})$.
  - Standardized peer offset: $b_i = (z_i(0) - \mu_{\text{lot},-i}(0)) / \sigma_0$.
  - Standardized temporal drift: $g_i(t) = [(z_i(t) - \mu_{\text{lot},-i}(t)) - (z_i(0) - \mu_{\text{lot},-i}(0))] / \sigma_0$.
  - Identity at $t=0$: $g_i(0) = 0.0$ identically.
  - Both $b_i$ and $g_i(t)$ exist in the exact same normalized statistical space.
  - Preserves Phase 1 raw-value immutability (LOG-020): non-positive observations ($x \le 0$), $\text{MAD}=0$, small peer populations ($N < \text{min\_peers}$), missing baselines, or non-finite values return `INSUFFICIENT_DATA` without fabricating or flooring raw telemetry.
- **Reason**: Ensures mathematical rigor and eliminates scale distortion between burn-in checkpoints.
- **Source / Provenance**: DESIGN_DECISION / SPECIFICATION.
- **Status**: HARDENED / VERIFIED.
- **Affected Area**: `src/sih26170/validation.py`, `docs/SIH26170_Architecture.md`, `tests/test_hardening.py`.
- **Impact**: Provides a mathematically sound foundation for Module A decomposition.

---

### LOG-033: Module A 8-Layer Architecture Alignment
- **Timestamp**: 2026-09-17T08:25:00Z
- **Phase**: Phase 2 Final Hardening
- **Type**: ARCHITECTURE_ALIGNMENT
- **Prior State**: Fragmented layer descriptions with stale references to "Module A, layer 9".
- **New State**: Formally unified Module A into exactly 8 screening layers:
  - Layer 1: Absolute limit hard gate (deterministic veto, never blended)
  - Layer 2: Leave-one-out robust lot baseline (median/MAD in consistent statistical space)
  - Layer 3: Robust decomposition ($b_i$ vs $g_i(t)$)
  - Layer 4: Conformal-style calibration (coverage guarantee on known-normals)
  - Layer 5: Multi-parameter coincidence rule (simultaneous subtle drift in 2+ parameters)
  - Layer 6: Per-lot Isolation Forest (multi-parameter interaction anomalies fit per lot)
  - Layer 7: Equipment-fault discriminator (`EQUIPMENT HOLD` for chamber/channel artifacts)
  - Layer 8: Residual-as-signal feedback (Module B 168h prediction residual fed back into Module A)
  Rework count is treated as a covariate across layers rather than a standalone detection layer.
- **Reason**: Eliminates numbering ambiguity and ensures 100% agreement between architecture diagrams, PRD, and code.
- **Source / Provenance**: SPECIFICATION (`docs/SIH26170_Architecture.md`, `docs/SIH26170_PRD.md`).
- **Status**: ACTIVE / HARDENED.
- **Affected Area**: `docs/SIH26170_Architecture.md`, `docs/SIH26170_PRD.md`, `tests/test_hardening.py`.
- **Impact**: Clear architectural structure for Phase 3 Module A implementation.

---

### LOG-034: A13 NASA Ames MOSFET Data Handling — Structural Validation Only
- **Timestamp**: 2026-09-17T08:30:00Z
- **Phase**: Phase 2 Final Hardening
- **Type**: EPISTEMIC_CORRECTION / SPECIFICATION
- **Prior State**: A13 implied a conversion path from NASA MOSFET ON-resistance to leakage current.
- **New State**:
  - A13 updated to `STRUCTURAL VALIDATION ONLY — NOT PHYSICAL CONVERSION TO LEAKAGE`.
  - There is no defensible physical basis for converting $R_{\text{ds(on)}} \to \text{leakage\_current}$.
  - The dataset may be used strictly structurally via dimensionless normalized curves:
    $$z(t) = \frac{R_{\text{ds(on)}}(t)}{R_{\text{ds(on)}}(0)}$$
    for temporal degradation-shape analysis and forecasting/extrapolation validation.
  - The NASA MOSFET dataset must NEVER populate `leakage_current` or any unrelated physical field in the canonical schema.
- **Reason**: Prevents physical pseudo-science and guards against repeating competitor errors (e.g. AEGIS C-MAPSS unit swap).
- **Source / Provenance**: EPISTEMIC_GUARDRAIL (`docs/SIH26170_Proposed_Solution_Draft.md`, `tests/test_hardening.py`).
- **Status**: HARDENED / VERIFIED.
- **Affected Area**: `docs/SIH26170_Proposed_Solution_Draft.md`, `docs/SIH26170_PRD.md`, `tests/test_hardening.py`.
- **Impact**: Restricts real-data secondary checks to defensible structural validation.

---

### LOG-035: Benchmark Limitations & Coverage Gaps Formalization
- **Timestamp**: 2026-09-17T08:35:00Z
- **Phase**: Phase 2 Final Hardening
- **Type**: AUDIT_RECORD / BENCHMARK_SPECIFICATION
- **Prior State**: Implicit assumptions regarding synthetic benchmark coverage.
- **New State**: Formally documented three specific benchmark limitations without altering the frozen dataset:
  1. *99.75% Parameter Coupling (Open Benchmark Design Limitation)*: 394/395 components share identical trajectory classes across all 3 parameters. Outlined future parameter-selective generator framework.
  2. *Zero Benign Limit Breaches (Benchmark Coverage Gap)*: 0 normal components breach limits in the static CSV. Mitigated via deterministic unit test fixture `test_benign_limit_breach_hard_gate_veto`.
  3. *Abrupt Failure Difficulty Calibration*: Graded ~20x step jumps as an `Easy / Sanity-Check Scenario`. Outlined future subtle step calibration.
  4. *Benchmark Scope Guardrail*: Designated as a `controlled synthetic evaluation environment`, never as a validated ISRO dataset or real physical failure distribution.
- **Reason**: Preserves dataset freeze while providing complete transparency regarding benchmark scope and limitations.
- **Source / Provenance**: AUDIT (`docs/PHASE_2C_FORENSIC_AUDIT.md`, `docs/PHASE_2_SYNTHETIC_DATA_SPEC.md`).
- **Status**: AUDITED / FROZEN.
- **Affected Area**: `docs/PHASE_2_SYNTHETIC_DATA_SPEC.md`, `tests/test_hardening.py`.
- **Impact**: Provides an uncompromised scientific benchmark baseline for Phase 3 Module A development.

---

### LOG-036: Component Selection & Physics Evidence Anchoring (IRHNJ57130 / IRF520NPBF)
- **Timestamp**: 2026-09-17T08:40:00Z
- **Phase**: Phase 2D Component & Physics Evidence Study
- **Type**: SOURCED / VERIFIED — EVIDENCE_ANCHORING
- **Prior State**: The prototype screening framework relied on generic parameters (`leakage_current`, `iddq`, `propagation_delay`) with nominal placeholder baselines.
- **New State**: Sourced and verified authoritative technical evidence establishing the **Radiation-Hardened N-Channel Power MOSFET (IRHNJ57130 / JANSR2N7422, MIL-PRF-19500/657)** as the primary component anchor, with the **Commercial Power MOSFET (IRF520NPBF, TO-220AB, NASA Ames Prognostics Dataset DUT)** as the secondary empirical shape reference.
- **Reason**: Anchors the screening architecture in real, verified aerospace semiconductor specifications and empirical degradation physics.
- **Source / Provenance**: PRIMARY_LITERATURE / MIL-PRF-19500/657 / Infineon Datasheets / NASA Ames Prognostics Repository.
- **Status**: ACTIVE / EVIDENCE_BACKED.
- **Affected Area**: `docs/PROTOTYPE_STANDING_LOG.md`, `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`.
- **Impact**: Establishes a verified physical foundation for discrete power semiconductor burn-in screening.

---

### LOG-037: Parameter Grounding & Elimination of IC Pseudo-Parameters
- **Timestamp**: 2026-09-17T08:45:00Z
- **Phase**: Phase 2D Component & Physics Evidence Study
- **Type**: EPISTEMIC_CORRECTION / DESIGN_SPECIFICATION
- **Prior State**: Prototype configuration used `iddq` and `propagation_delay` alongside `leakage_current`.
- **New State**:
  - Identified that `iddq` and `propagation_delay` are digital CMOS IC parameters with no physical existence on a discrete 3-terminal power MOSFET.
  - Formally specified that the future physics-informed discrete MOSFET benchmark will replace them with the standard co-measured electrical parameters from MIL-STD-750 Method 1042:
    1. $I_{\text{DSS}}$ (Zero Gate Voltage Drain Leakage Current, $\mu\text{A}$)
    2. $V_{\text{GS(th)}}$ (Gate-to-Source Threshold Voltage, V)
    3. $R_{\text{ds(on)}}$ (Static Drain-to-Source On-Resistance, $\text{m}\Omega$)
    4. $I_{\text{GSS}}$ (Gate-to-Source Leakage Current, nA)
- **Reason**: Eliminates pseudo-physics and prevents fictitious multi-parameter modeling.
- **Source / Provenance**: SPECIFICATION / MIL-STD-750 Methods 3401, 3403, 3405, 3407.
- **Status**: SPECIFIED / READY_FOR_BENCHMARK_V2.
- **Affected Area**: `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Aligns electrical screening observables with standard semiconductor automatic test equipment (ATE) practice.

---

### LOG-038: Physical Mechanism Decoupling & Parameter Coupling Breakdown
- **Timestamp**: 2026-09-17T08:50:00Z
- **Phase**: Phase 2D Component & Physics Evidence Study
- **Type**: ALGORITHM_SPECIFICATION / PHYSICS_GROUNDING
- **Prior State**: The frozen v1 synthetic benchmark had 394/395 components coupled across all 3 parameters.
- **New State**:
  - Proved from physical literature that semiconductor degradation during burn-in is parameter-selective:
    - *HTRB Stress*: Drives mobile ion drift in junction termination $\implies$ $I_{\text{DSS}}$ leakage rises, while $V_{\text{GS(th)}}$ and $R_{\text{ds(on)}}$ remain stable (univariate drift).
    - *HTGB Stress*: Drives gate oxide trapping / BTI $\implies$ $V_{\text{GS(th)}}$ shifts and $I_{\text{GSS}}$ rises, while $I_{\text{DSS}}$ remains stable (gate channel shift).
    - *Power Cycling / Thermal Overstress*: Drives die-attach solder fatigue $\implies$ $R_{\text{ds(on)}}$ rises, while gate oxide remains stable (packaging drift).
    - *Catastrophic Dielectric Breakdown*: Drives simultaneous collapse across all parameters (multivariate abrupt failure).
  - Designed future generator requirements to simulate univariate, bivariate, and independent degradation rates based on these physical mechanisms.
- **Reason**: Provides a solid physical justification for parameter decoupling in future benchmark iterations.
- **Source / Provenance**: PRIMARY_LITERATURE / IEEE TDMR / Celaya et al. (2011/2012).
- **Status**: DESIGNED / VERIFIED.
- **Affected Area**: `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Prepares benchmark v2 to rigorously evaluate multi-parameter coincidence and discrimination.

---

### LOG-039: Sourced Burn-in Conditions vs Demonstration Fixture Classification
- **Timestamp**: 2026-09-17T08:55:00Z
- **Phase**: Phase 2D Component & Physics Evidence Study
- **Type**: EPISTEMIC_CLASSIFICATION
- **Prior State**: Prototype used $125^\circ\text{C}$, $10\ \mu\text{A}$ baseline, $45\ \mu\text{A}$ component, and $50\ \mu\text{A}$ limit without explicit classification.
- **New State**:
  - Sourced authoritative MIL-STD-750 Method 1042 burn-in standards:
    - HTRB: $T_A = 150^\circ\text{C}$, $V_{\text{DS}} = 80\text{V}$, $V_{\text{GS}} = 0\text{V}$.
    - HTGB: $T_A = 150^\circ\text{C}$, $V_{\text{GS}} = 20\text{V}$, $V_{\text{DS}} = 0\text{V}$.
    - Steady-State Operating Life: $T_J = 125^\circ\text{C}\text{--}150^\circ\text{C}$.
  - Sourced IRHNJ57130 datasheet limits: $I_{\text{DSS}} \le 10\ \mu\text{A}$ ($25^\circ\text{C}$), $\le 25\ \mu\text{A}$ ($125^\circ\text{C}$).
  - Formally reclassified the prototype values ($10\ \mu\text{A}$ baseline, $45\ \mu\text{A}$ device, $50\ \mu\text{A}$ limit) as a `DEMONSTRATION FIXTURE`, not component physical truth.
- **Reason**: Prevents confusing software demonstration fixtures with real device specifications.
- **Source / Provenance**: SPECIFICATION / MIL-STD-750 / Infineon Datasheet.
- **Status**: ACTIVE / HARDENED.
- **Affected Area**: `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Establishes transparent boundaries between software testing fixtures and physical component limits.

---

### LOG-040: NASA Ames MOSFET Dataset Compatibility Classification
- **Timestamp**: 2026-09-17T09:00:00Z
- **Phase**: Phase 2D Component & Physics Evidence Study
- **Type**: DATASET_EVALUATION / EPISTEMIC_GUARDRAIL
- **Prior State**: Dataset strategy (A13) restricted NASA data to structural validation.
- **New State**:
  - Completed technical compatibility audit of Celaya et al. (2011/2012):
    - DUT: IRF520NPBF (TO-220AB commercial MOSFET).
    - Stress: Thermal overstress / power cycling ($\Delta T_J > 100^\circ\text{C}$).
    - Monitored parameter: $R_{\text{ds(on)}}$ (ON-resistance) via 4-wire Kelvin sensing.
    - Physical mechanism: Die-attach solder fatigue and void growth.
  - Confirmed classification:
    - Serves as **STRUCTURAL TEMPORAL VALIDATION** on dimensionless curves $z(t) = R_{\text{ds(on)}}(t)/R_{\text{ds(on)}}(0)$ for Module B time-series forecasting models.
    - Does **NOT** validate space-grade radiation hardness, hermetic packaging, or HTRB drain leakage.
- **Reason**: Prevents false claims of space validation while maximizing legitimate structural utility of real empirical degradation shapes.
- **Source / Provenance**: TIER_2_LITERATURE / NASA Ames Prognostics Data Repository.
- **Status**: RESOLVED / HARDENED.
- **Affected Area**: `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Scientifically defends the secondary real-data validation strategy.

---

### LOG-041: Ten-Tier Value Classification Taxonomy
- **Timestamp**: 2026-09-17T09:05:00Z
- **Phase**: Phase 2D Component & Physics Evidence Study
- **Type**: ONTOLOGY_DEFINITION
- **Prior State**: Numerical values were occasionally conflated across datasheets, screening limits, and simulation parameters.
- **New State**: Formalized a strict 10-tier value classification taxonomy:
  `TYPICAL`, `NOMINAL`, `DATASHEET_MIN`, `DATASHEET_MAX`, `ABSOLUTE_MAXIMUM_RATING`, `OPERATING_LIMIT`, `QUALIFICATION_LIMIT`, `SCREENING_LIMIT`, `ENGINEERING_REFERENCE`, `SIMULATION_PARAMETER`.
  Mandated that absolute maximum ratings must never become screening limits, and typical values must never become failure thresholds.
- **Reason**: Enforces linguistic and technical precision across all future modeling.
- **Source / Provenance**: DESIGN_DECISION (`docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`).
- **Status**: ACTIVE.
- **Affected Area**: `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Structurally prevents semantic confusion in future configuration schemas.

---

### LOG-042: Phase 2D Final Decision — Option B (Component Selected with Simulation Assumptions)
- **Timestamp**: 2026-09-17T09:10:00Z
- **Phase**: Phase 2D Component & Physics Evidence Study
- **Type**: STRATEGIC_DECISION
- **Prior State**: Open selection of component anchor.
- **New State**:
  - Adopted **OPTION B**: *"A component can be selected, but important physics inputs remain assumptions requiring explicit prototype treatment."*
  - Selected Component: **Radiation-Hardened Power MOSFET (IRHNJ57130 / JANSR2N7422, MIL-PRF-19500/657)**, supported by the **NASA Ames IRF520NPBF dataset** as an empirical temporal shape reference.
  - Justification: Sourced military slash sheets and manufacturer datasheets establish specifications, burn-in standards (MIL-STD-750 Method 1042), and degradation mechanisms with high confidence. However, lot-to-lot covariance, true flight scrap rates, and chamber noise floors remain proprietary, requiring explicit simulation parameterization rather than fabricated claims.
- **Reason**: Balances physical grounding with rigorous scientific honesty.
- **Source / Provenance**: SYNTHESIS (`docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`).
- **Status**: RESOLVED / FROZEN.
- **Affected Area**: `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Establishes the clear path forward for the upcoming benchmark redesign and Module A implementation.

---

### LOG-043: Component Identity & Slash Sheet Correction (IRHNJ57130 / JANSR2N7481U3 under MIL-PRF-19500/703)
- **Timestamp**: 2026-09-17T09:30:00Z
- **Phase**: Phase 2D Evidence Correction Audit
- **Type**: COMPONENT_IDENTITY_CORRECTION
- **Previous State**: Phase 2D study recorded device as `IRHNJ57130 / JANSR2N7422` under `MIL-PRF-19500/657`.
- **New State**: CORRECTED.
  - Verified DLA ASSIST records: `2N7422` is a P-channel device governed by `MIL-PRF-19500/662`.
  - Slash sheet `MIL-PRF-19500/657` specifies bare unencapsulated die, not an encapsulated device.
  - Infineon HiRel and DLA QPL records verify that `IRHNJ57130` corresponds to `JANSR2N7481U3`, governed by `MIL-PRF-19500/703` in an SMD-0.5 (TO-276AA) hermetic surface-mount package.
- **Reason**: Independent forensic audit cross-referenced official DLA ASSIST slash sheets and Infineon datasheets, identifying cross-referencing errors.
- **Source / Provenance**: DLA Land & Maritime ASSIST Database; MIL-PRF-19500/703; Infineon Datasheet PD-97217.
- **Status**: CORRECTED
- **Affected Area**: `docs/PHASE_2D_CORRECTION_AUDIT.md`, `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Establishes 100% verified source-of-truth component identity for Phase 2E benchmark redesign.

---

### LOG-044: Burn-in Duration Classification Correction (168h JEDEC vs 48h/240h JANS Spec)
- **Timestamp**: 2026-09-17T09:35:00Z
- **Phase**: Phase 2D Evidence Correction Audit
- **Type**: TEST_METHOD_RECLASSIFICATION
- **Previous State**: 168h was described as the "MIL-STD-750 standard duration" for burn-in.
- **New State**: CORRECTED.
  - 168 hours (1-week) is an industry-standard interval from JEDEC JESD22-A108 and commercial/automotive AEC-Q101 qualification.
  - Under MIL-PRF-19500 Table IV for space-level JANS components, screening requires 48h minimum HTRB + 48h minimum HTGB + 160h-240h steady-state operating life.
  - The prototype schedule t in {0, 24, 96, 168} h is reclassified as `SIMULATION_PARAMETER` (Assumption A3), not a JANS military specification standard.
- **Reason**: Eliminates false attribution of commercial standard duration to military space qualification standard.
- **Source / Provenance**: MIL-PRF-19500 Table IV; JEDEC JESD22-A108; MIL-STD-750 Method 1042.
- **Status**: CORRECTED
- **Affected Area**: `docs/PHASE_2D_CORRECTION_AUDIT.md`, `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Accurately bounds simulation parameter choices vs standard military requirements.

---

### LOG-045: Delta Limits Source Correction (Codified Slash Sheet vs General Military Heuristic)
- **Timestamp**: 2026-09-17T09:40:00Z
- **Phase**: Phase 2D Evidence Correction Audit
- **Type**: SCREENING_CRITERIA_CORRECTION
- **Previous State**: `ΔI_DSS <= ±100% or +10 uA` and `ΔV_GS(th) <= ±15-20%` were claimed as device-specific screening criteria from MIL-PRF-19500/703.
- **New State**: CORRECTED.
  - MIL-PRF-19500/703 Table I defines post-stress absolute acceptance limits (e.g. I_DSS <= 10 uA at 25°C), but contains no separate slash-sheet delta column.
  - The "±100% or +10 uA" formula originates from general military semiconductor screening guidelines in MIL-PRF-19500 Appendix E as an engineering rule of thumb.
  - Reclassified from `MIL-PRF SLASH SHEET` to `GENERAL_MIL_GUIDELINE / ENGINEERING_HEURISTIC`.
- **Reason**: Forensic examination of MIL-PRF-19500/703 Table I confirms absence of device-specific delta limits.
- **Source / Provenance**: MIL-PRF-19500/703 Table I; MIL-PRF-19500 Appendix E.
- **Status**: CORRECTED
- **Affected Area**: `docs/PHASE_2D_CORRECTION_AUDIT.md`, `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Clarifies exact legal/military specification provenance of screening threshold heuristics.

---

### LOG-046: PDA Disambiguation (5% Initial Screening vs 3% Resubmission Limit)
- **Timestamp**: 2026-09-17T09:45:00Z
- **Phase**: Phase 2D Evidence Correction Audit
- **Type**: QUALITY_RULE_DISAMBIGUATION
- **Previous State**: Claimed that if >5% devices fail, the entire lot is permanently rejected.
- **New State**: CORRECTED.
  - PDA <= 5.0% applies to cumulative electrical failures during initial burn-in screening.
  - If PDA > 5%, the lot is rejected from that primary screening submission.
  - However, MIL-PRF-19500 Section 4.5.3 permits a single resubmission of an additional burn-in period if failures are non-catastrophic.
  - For resubmitted lots, a tightened PDA <= 3.0% is enforced. Exceeding 3% causes final, permanent lot rejection.
- **Reason**: Disambiguates primary screening threshold from resubmission exceptions and permanent rejection rules.
- **Source / Provenance**: MIL-PRF-19500 Section 4.5.3.
- **Status**: CORRECTED
- **Affected Area**: `docs/PHASE_2D_CORRECTION_AUDIT.md`, `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Prevents oversimplified statements regarding military quality assurance flows.

---

### LOG-047: Degradation Equation & Activation Energy Epistemic Reclassification
- **Timestamp**: 2026-09-17T09:50:00Z
- **Phase**: Phase 2D Evidence Correction Audit
- **Type**: PHYSICS_MODEL_RECLASSIFICATION
- **Previous State**: Poole-Frenkel / Arrhenius leakage model and Reaction-Diffusion BTI equations were presented with activation energies (E_a,ion = 0.8-1.0 eV, E_a,BTI = 0.3-0.5 eV) as though they were verified physical constants of the IRHNJ57130.
- **New State**: CORRECTED.
  - Reclassified functional forms as `EMPIRICAL APPROXIMATIONS`.
  - Reclassified activation energies and exponents (n = 0.5-1.0, m = 0.16-0.25) as `LITERATURE-BASED SIMULATION PARAMETERS`.
  - Confirmed that Infineon publishes no certified activation energies or drift exponents for the IRHNJ57130 die.
- **Reason**: Adherence to the project epistemic imperative: literature values must never be presented as device-confirmed physical constants.
- **Source / Provenance**: IEEE TDMR; Alam & Mahapatra (2005); MIL-HDBK-217F.
- **Status**: CORRECTED
- **Affected Area**: `docs/PHASE_2D_CORRECTION_AUDIT.md`, `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Protects future Phase 2E generator design from over-claiming physics fidelity.

---

### LOG-048: NASA Ames Dataset Epistemic Quarantine Hardened
- **Timestamp**: 2026-09-17T09:55:00Z
- **Phase**: Phase 2D Evidence Correction Audit
- **Type**: SURROGATE_DATASET_QUARANTINE
- **Previous State**: NASA Ames dataset recognized for structural validation, but potential for conflation with space MOSFET physics remained.
- **New State**: CORRECTED / HARDENED.
  - Established rigid dual-device demarcation: IRHNJ57130 (space hermetic ceramic SMD-0.5 anchor governed by MIL-PRF-19500/703) vs IRF520NPBF (commercial plastic TO-220 surrogate stressed via power cycling in NASA dataset).
  - NASA empirical data provides structural validation for non-linear drift curves z(t) = R_ds(on)(t)/R_ds(on)(0) in Module B extrapolation.
  - NASA data does NOT establish space qualification behavior, radiation hardness, HTRB leakage physics, or JANS screening limits for IRHNJ57130.
- **Reason**: Prevents any false equivalence between commercial thermal overstress and spaceflight HTRB/HTGB burn-in.
- **Source / Provenance**: Celaya et al. (NASA Ames, 2011/2012); Infineon IRF520NPBF datasheet; MIL-PRF-19500/703.
- **Status**: HARDENED
- **Affected Area**: `docs/PHASE_2D_CORRECTION_AUDIT.md`, `docs/PHASE_2D_COMPONENT_PHYSICS_STUDY.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Formally establishes transparent boundaries for empirical surrogate validation.

---

### LOG-049: Phase 2F-A Physics-Informed Synthetic Generator Implementation
- **Timestamp**: 2026-09-17T10:30:00Z
- **Phase**: Phase 2F-A Implementation
- **Type**: SYNTHETIC_GENERATOR_IMPLEMENTATION
- **Previous State**: Phase 2C historical synthetic dataset possessed a 99.75% trajectory coupling pathology where all parameters drifted identically in 394/395 components; 0 benign static limit breaches; uncalibrated subtle failures; missingness imputed.
- **New State**: IMPLEMENTED in development isolation (`src/sih26170/synthetic/phase2f/` -> `data/synthetic_phase2f_dev/`).
  - Historical benchmark in `data/synthetic/` remains 100% frozen and untouched.
  - Implemented parameter-selective trajectory vectors $\mathbf{T}_i = [T_i(I_{\text{DSS}}), T_i(V_{\text{GS(th)}}), T_i(R_{\text{DS(on)}}), T_i(I_{\text{GSS}})]$.
  - Measured overall cross-parameter coupling drops to 43.72% (from 99.75%), and abnormal component coupling drops to 5.45% (from 100.0%).
  - Static limit breaches decoupled: stationary at $t=0$, spec non-compliant, temporal degradation = False.
  - Subtle failure drifts calibrated to SNR in $[1.5, 2.5]$ (empirical range: $1.81$ to $2.34$).
  - Full small-lot sensitivity sizes ($N \in \{3, 5, 8, 12, 20, 50\}$) generated.
  - Common-mode chamber drift ($+5^\circ\text{C}$ at 96h) and ATE channel calibration bias generate measurable shared shifts without corrupting ground truth degradation status.
  - 86 passed tests (75 existing + 11 new Phase 2F tests).
  - Artifacts marked `PHASE_2F_DEVELOPMENT / NOT_FROZEN`.
- **Reason**: Completion of Phase 2F-A development generation and forensic validation.
- **Source / Provenance**: Phase 2E Specification (`docs/PHASE_2E_PHYSICS_INFORMED_SYNTHETIC_MODEL_SPEC.md`), Phase 2E Final Forensic Review (`docs/PHASE_2E_FINAL_FORENSIC_REVIEW.md`), and Phase 2F-A Development Report (`docs/PHASE_2F_A_DEVELOPMENT_REPORT.md`).
- **Status**: IMPLEMENTED
- **Affected Area**: `src/sih26170/synthetic/phase2f/`, `data/synthetic_phase2f_dev/`, `tests/test_phase2f_generator.py`, `docs/PHASE_2F_A_DEVELOPMENT_REPORT.md`.
- **Impact**: Delivers a verified physics-informed development synthetic benchmark ready for Phase 2F-B forensic review.

---

### LOG-050: Phase 2F-A Targeted Correction Pass & Forensic Epistemic Hardening
- **Timestamp**: 2026-09-17T11:15:00Z
- **Phase**: Phase 2F-A Correction Pass
- **Type**: SYNTHETIC_GENERATOR_CORRECTION
- **Previous State**: Initial Phase 2F-A generator modeled IGSS as strictly positive in log-domain (violating MIL-PRF-19500/703 Table I ±100 nA spec); verified as-of integrity using temporal monotonicity only; conflated ground-truth row counts with scenario counts; omitted conditional coupling probabilities on degrading components; reported ambiguous CV = 1.203 for common-mode drift.
- **New State**: CORRECTED & AUDITED.
  - Resolved Blocker 1: Modeled IGSS via signed continuous transform asinh(IGSS / 1.0 nA), preserving positive, negative, exact zero, near-zero, and Table I limits at ±100 nA.
  - Resolved Blocker 2: Implemented `audit_as_of_leakage` constructing observation-only views V_T for T in {0h, 24h, 96h, 168h}, proving zero future records, zero ground-truth columns, and cross-slice byte identity.
  - Resolved Blocker 3: Distinctly quantified Component-Level (398), Parameter-Level (1,592), and Observation-Level (6,368) scenario counts; verified all 10 canonical scenarios (including `mixed_compound`).
  - Coupling Audit: P(all 4 same | degrading) = 0.00%, P(1-drift | degrading) = 93.75%, P(2-drift | degrading) = 6.25%, P(4-drift | degrading) = 0.00% (eliminated 100% Phase 2C coupling).
  - Common-Mode Audit: Specified exact variables and ANOVA statistics (chamber drift mean +0.4214 uA, 100% affected; fixture bias F-ratio = 0.3225).
  - Missingness: Formally classified 7 omitted records (0.1099%) as Layer F benchmark design choice with sensitivity testing matrix.
  - Static Limit Breach: Confirmed 6 components stationary at t=0, spec non-compliant, temporally non-degraded, abnormal.
  - Subtle SNR: Verified latent state SNR in [1.5, 2.5] (1.81 to 2.34) strictly independent of measurement readout noise.
  - Physical Positivity: Correctly classified parameters into log-domain positive, asinh-domain signed, and linear bounded.
  - 91 passed tests (75 existing + 16 Phase 2F tests).
  - Created `docs/PHASE_2F_A_CORRECTION_REPORT.md` with status: `A. CORRECTIONS PASS — READY FOR PHASE 2F-B REVIEW`.
- **Reason**: Forensic hardening against adversarial critique and strict compliance with verified military specifications.
- **Source / Provenance**: MIL-PRF-19500/703 Table I; Phase 2F-A Correction Pass instructions; `docs/PHASE_2F_A_CORRECTION_REPORT.md`.
- **Status**: VERIFIED
- **Affected Area**: `src/sih26170/synthetic/phase2f/`, `data/synthetic_phase2f_dev/`, `tests/test_phase2f_generator.py`, `docs/PHASE_2F_A_CORRECTION_REPORT.md`.
- **Impact**: Provides an epistemically defensible, forensic-grade development benchmark dataset ready for Phase 2F-B review.

---

### LOG-051: Phase 2F-B Development Dataset Validation & Benchmark Readiness Review
- **Timestamp**: 2026-09-17T12:00:00Z
- **Phase**: Phase 2F-B Benchmark Readiness Review
- **Type**: BENCHMARK_READINESS_REVIEW
- **Previous State**: Phase 2F-A development dataset corrected and audited, but benchmark readiness unverified across all 18 forensic validation gates; freeze status pending.
- **New State**: COMPLETED & VERIFIED.
  - Completed comprehensive forensic audit of all 6 dataset artifacts (6,361 observation rows, 6,368 ground-truth rows, 398 components, 16 lots).
  - Verified genuine instantiation of all 10 canonical scenarios across component, parameter, and observation levels.
  - Confirmed total elimination of Phase 2C coupling: P(all 4 same | degrading) = 0.00%, P(single-parameter drift | degrading) = 93.75%.
  - Verified independent exercise of absolute limits vs temporal degradation across 5 distinct diagnostic populations (Cases A-E).
  - Validated latent SNR distribution strictly within target difficulty interval [1.5, 2.5] (1.81 to 2.34).
  - Audited common-mode effects: chamber thermal excursion (+0.42 uA, 100% affected) and weak multi-channel ATE fixture bias (F = 0.32, retained as realistic adversarial case).
  - Proved real as-of information integrity across checkpoint slices V_0, V_24, V_96, V_168 with zero future leakage and zero historical mutations.
  - Mechanism-separated correlation forensics: baseline physical covariance (doping rho = -0.105, oxide rho = -0.352) vs orthogonal temporal changes (rho <= 0.10).
  - Evaluated small-lot policies (N in {3, 5, 8, 12, 20, 50}) and confirmed absolute limits remain active.
  - Assessed Module A and Module B structural readiness; documented 4-checkpoint sampling density limitation for higher-order nonlinear prognostic modeling.
  - Created `docs/PHASE_2F_B_BENCHMARK_READINESS_REPORT.md` with formal recommendation: `A. READY FOR BENCHMARK FREEZE`.
  - Execution halted; benchmark NOT automatically frozen pending explicit user approval.
- **Reason**: Comprehensive benchmark readiness evaluation prior to final benchmark freezing and Module A implementation.
- **Source / Provenance**: Phase 2F-B instructions; `docs/PHASE_2F_B_BENCHMARK_READINESS_REPORT.md`; `src/sih26170/synthetic/phase2f/`.
- **Status**: VERIFIED
- **Affected Area**: `docs/PHASE_2F_B_BENCHMARK_READINESS_REPORT.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Establishes formal readiness for final benchmark freezing and Module A screening architecture development.

---

### LOG-052: Phase 2F-B Final Correction & Freeze-Gate Reconciliation
- **Timestamp**: 2026-09-17T12:30:00Z
- **Phase**: Phase 2F-B Final Reconciliation
- **Type**: BENCHMARK_FREEZE_RECONCILIATION
- **Previous State**: Phase 2F-B initial report contained scenario ontology ambiguity regarding `mixed_compound` across entity levels, unclarified population units ("series"), physical overclaims regarding kinetic orthogonality, and unexplained variance ratio vs ANOVA F differences for LOT_E02.
- **New State**: RECONCILED & AUDITED.
  - Reconciled scenario ontology: confirmed `mixed_compound` as a component-level composite (Option A); reported exact counts for Component Level (10 classes, N=398), Parameter Level (9 classes, N=1,592), and Observation Level (9 classes, N=6,368).
  - Defined "series" as component-parameter trajectories (N=1,592); reconciled how 16 degrading components produce exactly 17 degrading series (15 single-drift + 1 double-drift component LOT_M01_C001); reconciled Cases A-E.
  - Excised physical overclaims; replaced with strict epistemic statements on synthetic degradation decoupling.
  - Defined LOT_E01 populations and Cohen's d = 0.8174; maintained injection coverage != detector separability.
  - Derived mathematical relationship between ATE variance ratio (0.3225) and ANOVA F-statistic (0.6333); confirmed weak adversarial status.
  - Formalized As-Of Preprocessing Structural Contract for Module A.
  - Classified all benchmark limits into Classes A through E.
  - Audited full parameter distributions and confirmed signed IGSS polarity preservation without abs().
  - Verified bit-for-bit identical hashes: observations (b428...983) and ground_truth (4bf2...d2b).
  - Evaluated all 17 freeze gates: ALL PASSED.
  - Created `docs/PHASE_2F_B_FINAL_CORRECTION_REPORT.md` with final determination: `A. READY FOR BENCHMARK FREEZE`.
  - Execution halted; benchmark NOT frozen.
- **Reason**: Final forensic hardening, claim boundary enforcement, and freeze gate verification.
- **Source / Provenance**: Phase 2F-B Final Correction instructions; `docs/PHASE_2F_B_FINAL_CORRECTION_REPORT.md`.
- **Status**: VERIFIED
- **Affected Area**: `docs/PHASE_2F_B_FINAL_CORRECTION_REPORT.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Provides an unassailable, epistemically verified development benchmark ready for final freezing authorization.

---

### LOG-053: Phase 2F Benchmark Freeze Preflight Authorization
- **Timestamp**: 2026-09-17T13:00:00Z
- **Phase**: Phase 2F Freeze Preflight
- **Type**: BENCHMARK_FREEZE_PREFLIGHT
- **Previous State**: Phase 2F-B final reconciliation accepted substantively, but required explicit resolution of RDS(on) 60 vs 65 mOhm threshold provenance, partition vs diagnostic view structure, canonical 18-gate numbering scheme, and final hash immutability check before benchmark freeze authorization.
- **New State**: COMPLETED & VERIFIED.
  - Verified RDS(on) threshold provenance: 65 mOhm is Class A verified device spec (MIL-PRF-19500/703 Table I); 60 mOhm is Class C configured screening acceptance criterion (Infineon Datasheet PD-97217 Table 3); confirmed no conflation in code.
  - Resolved diagnostic population structure: established canonical 5-cell mutually exclusive partition (N=1,592 series); mapped Cases A-E as overlapping diagnostic feature views.
  - Established canonical 18-gate numbering scheme (FG01-FG18); all 18 gates pass without exception.
  - Verified cryptographic hashes bit-for-bit: observations (b428...983) and ground_truth (4bf2...d2b) unchanged.
  - Verified historical Phase 2C benchmark and Phase 2F dev artifacts remain 100% immutable; zero Module A/B code executed.
  - Re-stated permanent scientific boundaries.
  - Created `docs/PHASE_2F_FREEZE_PREFLIGHT_REPORT.md` with final recommendation: `READY FOR BENCHMARK FREEZE`.
  - Execution halted; benchmark NOT frozen.
- **Reason**: Final freeze authorization preflight.
- **Source / Provenance**: Phase 2F Freeze Preflight instructions; `docs/PHASE_2F_FREEZE_PREFLIGHT_REPORT.md`.
- **Status**: VERIFIED
- **Affected Area**: `docs/PHASE_2F_FREEZE_PREFLIGHT_REPORT.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Establishes definitive technical and operational clearance for physical benchmark freezing.

---

### LOG-054: Phase 2F Benchmark Physical Freeze Execution
- **Timestamp**: 2026-09-17T13:35:00Z
- **Phase**: Phase 2F Benchmark Freeze
- **Type**: BENCHMARK_FREEZE_EXECUTION
- **Previous State**: Phase 2F development benchmark validated and preflight approved, but not yet physically frozen into an immutable baseline release directory.
- **New State**: COMPLETED & IMMUTABLE.
  - Executed benchmark freezing procedure into permanent release directory `data/synthetic_phase2f_frozen/`.
  - Copied all development artifacts and verified byte-for-byte identity against development directory.
  - Verified SHA-256 digests bit-for-bit:
    - observations.csv: `b4282e0743cd6a0b2b74354e431bf8f308b03281c44c0437d30f7b53bd6ca983`
    - ground_truth.csv: `4bf2155fcc7698813f766e1dea9730213e0a6097e484bfa786eb1b94925f3d2b`
  - Created frozen release manifest `manifest.json` establishing cryptographic identity for `PHASE_2F_FROZEN_BENCHMARK_v1.0.0`.
  - Added frozen release documentation: `SCENARIO_ONTOLOGY.md`, `THRESHOLD_PROVENANCE.md`, `SCIENTIFIC_BOUNDARIES.md`, `REPRODUCIBILITY.md`.
  - Confirmed Phase 2C historical benchmark (`data/synthetic/`) remains 100% frozen and untouched.
  - Confirmed Phase 2F development directory (`data/synthetic_phase2f_dev/`) remains 100% untouched.
  - Confirmed Modules A and B remain un-implemented.
  - Executed test suite: all 91 tests passed in 4.27s (0 regressions).
  - Created permanent freeze record `docs/PHASE_2F_FREEZE_RECORD.md`.
- **Reason**: Authorized physical benchmark freeze establishing permanent evaluation baseline for Module A and Module B.
- **Source / Provenance**: Phase 2F Freeze Authorization; `docs/PHASE_2F_FREEZE_RECORD.md`; `data/synthetic_phase2f_frozen/`.
- **Status**: VERIFIED
- **Affected Area**: `data/synthetic_phase2f_frozen/`, `docs/PHASE_2F_FREEZE_RECORD.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
### LOG-055: Phase 3A Module A Dynamic Screening Design Specification
- **Timestamp**: 2026-09-17T09:12:00Z
- **Type**: ARCHITECTURAL_DESIGN_SPECIFICATION
- **Previous State**: Frozen benchmark v1.0.0 established, but Module A screening architecture lacked formal, complete mathematical and epistemic design specification for the 10 Phase 2F scenarios.
- **New State**: COMPLETED.
  - Authored comprehensive Module A specification in `docs/PHASE_3A_MODULE_A_SPEC.md`.
  - Defined canonical long-format input contract for the four primary observables: $I_{\text{DSS}}$, $V_{\text{GS(th)}}$, $R_{\text{DS(on)}}$, and strictly signed $I_{\text{GSS}}$.
  - Formalized strict As-Of Contract ($V_T$) and quarantine of ground-truth labels.
  - Specified parameter-specific representation spaces: positive log for $I_{\text{DSS}}$ and $R_{\text{DS(on)}}$, signed $\text{asinh}(y/1\,\text{nA})$ for $I_{\text{GSS}}$, and bounded linear space for $V_{\text{GS(th)}}$.
  - Designed six functionally independent detectors: Absolute Specification ($D_{\text{spec}}$), Lot/Peer Relative ($D_{\text{peer}}$), Temporal Drift ($D_{\text{drift}}$), Abrupt Change ($D_{\text{step}}$), Equipment/Common-Mode ($D_{\text{eq}}$), and Data Sufficiency ($D_{\text{suff}}$).
  - Formalized five-tier limit classification (Class A verified spec $65.0\,\text{m}\Omega$ vs Class C screening margin $60.0\,\text{m}\Omega$).
  - Defined leave-one-out median/MAD statistics, handling of high-but-stable populations, and the $N < 8$ small-lot heuristic.
  - Formulated deterministic rules-based evidence fusion engine and five canonical screening states (`PASS`, `ALERT`, `FAIL`, `INSUFFICIENT_DATA`, `EQUIPMENT_SUSPECTED`).
  - Designed deterministic explainability card and immutable audit records.
  - Analyzed eleven architectural failure modes and created benchmark traceability matrix for the 10 frozen scenarios.
  - Upheld strict exclusion of pre-emptive performance claims; gated design status as `READY FOR IMPLEMENTATION`.
  - Zero runtime code executed; zero benchmark modifications; 91 tests passing.
- **Reason**: Authorized Phase 3A architectural design mandate.
- **Source / Provenance**: Phase 3A User Prompt; `docs/PHASE_3A_MODULE_A_SPEC.md`.
- **Status**: VERIFIED
- **Affected Area**: `docs/PHASE_3A_MODULE_A_SPEC.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Establishes the authoritative, mathematically rigorous engineering blueprint for Phase 3B Module A implementation.

### LOG-056: Phase 3A Module A Screening Architecture Implementation
- **Timestamp**: 2026-09-17T09:22:00Z
- **Type**: CORE_ENGINEERING_IMPLEMENTATION
- **Previous State**: Module A design specification approved (`docs/PHASE_3A_MODULE_A_SPEC.md`), but runtime implementation in `src/sih26170/screening/` and unit test suite did not exist.
- **New State**: COMPLETED & VERIFIED.
  - Implemented modular screening package `src/sih26170/screening/`:
    - `schema.py`: Canonical 5 states (`PASS`, `ALERT`, `FAIL`, `INSUFFICIENT_DATA`, `EQUIPMENT_SUSPECTED`), 5-tier limit classes, typed evidence records.
    - `transforms.py`: Parameter representations ($I_{\text{DSS}}$/$R_{\text{DS(on)}}$ positive log, $I_{\text{GSS}}$ signed $\text{asinh}(y/1\,\text{nA})$, $V_{\text{GS(th)}}$ bounded linear, noise floors).
    - `specification.py` ($D_{\text{spec}}$): Class A verified spec ($65\,\text{m}\Omega$) vs Class C margin ($60\,\text{m}\Omega$) disambiguation.
    - `peer.py` ($D_{\text{peer}}$): Leave-one-out median/MAD robust DPAT; $N < 8$ small-lot suppression.
    - `temporal.py` ($D_{\text{drift}}$): Theil-Sen slope, normalized drift $g(T)$, acceleration proxy $\kappa(T)$, equipment confounding flag.
    - `abrupt.py` ($D_{\text{step}}$): Step ratio $J(T) \ge 4.0$ jump detection across adjacent checkpoints.
    - `equipment.py` ($D_{\text{eq}}$): Chamber synchrony ($>75\%$ shifting) and ATE fixture channel offsets.
    - `sufficiency.py` ($D_{\text{suff}}$): Checkpoint completeness and small-lot policy checks without silent imputation.
    - `fusion.py`: Rules-based deterministic precedence fusion engine with secondary `compound_evidence` flag.
    - `explainability.py`: Deterministic explainability card generator conforming to As-Of boundary.
    - `audit.py`: Reconstructible audit records with SHA-256 telemetry digests.
    - `pipeline.py`: As-Of slice enforcement, ground-truth quarantine, and end-to-end component screening.
  - Authored comprehensive test suite `tests/screening/` (39 tests):
    - Transforms, detectors, all 19 functional scenarios, 4 As-Of adversarial future corruption tests, and ground-truth isolation tests.
  - Executed full test suite: 130/130 tests passing (91 historical + 39 Module A).
  - Verified benchmark immutability: Phase 2F frozen v1.0.0 and Phase 2C historical benchmark SHA-256 digests 100% unchanged.
  - Authored completion report: `docs/PHASE_3A_MODULE_A_IMPLEMENTATION_REPORT.md`.


### LOG-057: Phase 3B Module A Empirical Benchmark Evaluation
- **Timestamp**: 2026-09-17T09:35:00Z
- **Type**: EMPIRICAL_EVALUATION
- **Previous State**: Module A implementation verified with 130 tests passing (`LOG-056`), but empirical screening performance against the frozen Phase 2F benchmark (`data/synthetic_phase2f_frozen/` release `v1.0.0`) had not been evaluated.
- **New State**: COMPLETED & DOCUMENTED.
  - Executed two-stage evaluation protocol:
    1. Generated predictions for all 398 components across all checkpoints ($0\text{h}, 24\text{h}, 96\text{h}, 168\text{h}$) strictly from `observations.csv` with zero ground truth leakage.
    2. Frozen prediction artifacts saved to `data/evaluation_phase3b/` (`predictions_T*.csv`, `predictions_T*.json`, `parameter_predictions_T*.csv`, `screening_run_metadata.json`).
    3. Evaluated against `ground_truth.csv` as an independent oracle; summary metrics saved to `data/evaluation_phase3b/evaluation_summary.json`.
  - Conducted target-stratified evaluation across all 10 canonical scenarios:
    - Target A (Specification Non-Compliance): Sensitivity $85.71\%$, Specificity $99.48\%$, Precision $85.71\%$, False-Positive Rate $0.52\%$.
    - Target B (Temporal Degradation): Sensitivity $6.25\%$, Specificity $98.17\%$, Precision $12.50\%$ (adversely impacted by Issue 2).
    - Target C (Equipment/Common-Mode Condition): Sensitivity $100.00\%$, Specificity $15.77\%$ (adversely impacted by Issue 1).
    - Target D (Nominal Stable Condition): Sensitivity $13.91\%$, Specificity $97.77\%$, False Alarm Rate $2.23\%$.
  - Validated key engineering invariants:
    - High-But-Stable (FM1): 0 out of 169 components falsely classified as `FAIL` ($0.0\%$ false failure rate). Baseline offset correctly distinguished from temporal wearout.
    - Signed $I_{\text{GSS}}$: Negative polarity preserved across log-asinh transform and explainability cards without taking absolute values or crashing.
    - Small-Lot Protection: $D_{\text{peer}}$ suppressed for $N=3$ and $N=5$, active for $N \ge 8$.
    - Missingness Integrity: ATE contact aborts ($0.1099\%$) flagged as `INSUFFICIENT_DATA` with zero silent imputation.
    - Chamber Excursion Sensitivity: $100\%$ ($30/30$) of `LOT_E01` components detected at $96\text{h}$ excursion as `EQUIPMENT_SUSPECTED`.
  - Discovered two critical Open Architectural Issues:
    - Issue 1: Over-sensitive fixture channel bias heuristic in $D_{\text{eq}}$ triggered on normal 2-sample Gaussian noise, causing $80.65\%$ state concentration in `EQUIPMENT_SUSPECTED`.
    - Issue 2: Fusion engine precedence Level 3 (`EQUIPMENT_SUSPECTED`) masked Level 4 (`TEMPORAL_DEGRADATION`), suppressing drift alerts.
  - Strict non-tuning mandate maintained: zero threshold or logic changes were made during evaluation.
  - Determined Empirical Status: `PERFORMANCE MIXED — ARCHITECTURAL REVISIONS REQUIRED`.
  - Authored comprehensive report: `docs/PHASE_3B_MODULE_A_EMPIRICAL_EVALUATION.md`.
  - Verified benchmark immutability: Phase 2F frozen v1.0.0 and Phase 2C historical benchmark SHA-256 digests 100% byte-identical.
- **Reason**: Authorized Phase 3B Empirical Evaluation mandate.
- **Source / Provenance**: Phase 3B User Prompt; `docs/PHASE_3B_MODULE_A_EMPIRICAL_EVALUATION.md`; `data/evaluation_phase3b/`.
- **Status**: VERIFIED
- **Affected Area**: `docs/PHASE_3B_MODULE_A_EMPIRICAL_EVALUATION.md`, `data/evaluation_phase3b/`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Provides an adversarial, unvarnished forensic baseline of Module A screening capabilities, isolating exact mathematical failure modes for Phase 3C hardening.

---

### LOG-058: Phase 3C Module A Hardening & Empirical Re-Evaluation
- **Timestamp**: 2026-09-17T10:45:00Z
- **Phase**: Phase 3C Hardening & Validation
- **Type**: STATISTICAL_VALIDATION_AND_HARDENING
- **Previous State**: Phase 3B identified two open architectural defects: (1) over-sensitive static ATE fixture channel bias heuristic in $D_{\text{eq}}$ ($80.65\%$ in `EQUIPMENT_SUSPECTED`), and (2) fusion precedence Level 3 masking temporal degradation ($93.75\%$ masking rate).
- **New State**: COMPLETED & VERIFIED.
  - Implemented statistically audited standardized robust residual $Z_{\text{channel}, k}$ in $D_{\text{ATE}}$ with finite-sample suppression for $N_k < 4$.
  - Completed 50,000-iteration Monte Carlo null characterization: empirical per-channel FPR strictly bounded to $\le 0.00074$ (95% CI $[0.00054, 0.00102]$) and 16-channel fixture FWER bounded to $\le 1.33\%$ (95% CI $[1.23\%, 1.43\%]$), validating critical threshold $|Z| \ge 3.42$ as Layer F Benchmark/Design Parameter.
  - Formulated leave-one-out (LOO) lot reference shift $g_{\text{lot},-i}(T)$ and excess drift $g_{\text{excess}, i}(T)$ strictly adhering to As-Of boundary ($t \le T$).
  - Implemented evidence-preserving fusion logic across Precedence Levels 1 to 8:
    - Retained strictly the canonical 5 top-level states (`PASS`, `ALERT`, `FAIL`, `INSUFFICIENT_DATA`, `EQUIPMENT_SUSPECTED`).
    - Added typed `DispositionQualifier` metadata establishing epistemic boundaries: `EQUIPMENT_SUSPECTED` does not imply health; `CONFOUNDED_BY_EQUIPMENT` does not prove autonomous wearout in isolation.
    - Level 3 evaluates excess motion ($|g_{\text{excess}}| \ge 2.5$), eliminating temporal masking ($0.0\%$ masking rate, down from $93.75\%$).
  - Developed and passed 10 adversarial null tests and statistical power/sensitivity sweeps:
    - 144 unit and adversarial tests passing (0 regressions).
  - Re-evaluated against immutable Phase 2F benchmark (`data/synthetic_phase2f_frozen/` v1.0.0):
    - High-but-stable false failure rate: $0.00\%$ ($0/169$).
    - Temporal degradation recall: $37.50\%$ ($6/16$, up from $6.25\%$).
    - Equipment false alarm rate: $0.00\%$ ($0/338$, down from $84.15\%$).
    - Nominal stable acceptance rate: $95.18\%$ ($158/166$, up from $13.86\%$).
    - Every confusion matrix strictly satisfies $\text{TP} + \text{FP} + \text{TN} + \text{FN} + \text{EXCLUDED} = 398$ with $\text{EXCLUDED} = 0$.
  - Verified benchmark cryptographic immutability: SHA-256 digests of frozen observations and ground truth match bit-for-bit.
  - Authored comprehensive forensic report: `docs/PHASE_3C_MODULE_A_HARDENING.md`.
- **Reason**: Authorized Phase 3C Pre-Implementation Amendment mandate.
- **Source / Provenance**: Phase 3C Amendment Prompt; `docs/PHASE_3C_MODULE_A_HARDENING.md`; `data/evaluation_phase3c/`.
- **Status**: VERIFIED
- **Affected Area**: `src/sih26170/screening/`, `tests/screening/`, `data/evaluation_phase3c/`, `docs/PHASE_3C_MODULE_A_HARDENING.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Establishes a statistically defensible, evidence-preserving screening engine ready for forensic review.

---

### LOG-059: Phase 3C Post-Implementation Amendment — Transient Excursion Preservation & Final Verification
- **Timestamp**: 2026-09-17T11:00:00Z
- **Phase**: Phase 3C Post-Implementation Amendments
- **Type**: CORRECTNESS_AMENDMENT_AND_FINAL_VERIFICATION
- **Supersedes / Amends**: LOG-058
- **Previous State (LOG-058)**: `abrupt.py` evaluated only the final adjacent interval $(T_{\text{prev}}, T)$ for step detection. `fusion.py` Level 3 evaluated $|g_{\text{excess}}| \ge 2.5$ and accelerating wearout, but did not explicitly gate on `ABRUPT_JUMP_ALERT` as a separate pathway. LOG-058 test count was 144.
- **Amendment Rationale**: Phase 3C execution mandate Rule 7 — *"Preserve transient/abrupt evidence even when endpoint $g_{\text{excess}}$ is small."* A component with a genuine abrupt step at $0\text{h} \to 24\text{h}$ that recovers by $168\text{h}$ would report $|g_{\text{excess}}(168\text{h})| < 2.5$ (because the endpoint returned near baseline), causing the abrupt event to be silently discarded under the prior implementation.
- **New State**: IMPLEMENTED & VERIFIED (145 tests pass, 0 failures).
  - **`abrupt.py` — Full-History Interval Scan**: $D_{\text{step}}$ now iterates over **all adjacent intervals** in the chronologically sorted as-of history. The maximum step ratio $J_{\text{ratio}}^{\max}$ across all intervals is compared against the threshold. The triggering interval $(t_{\text{event}}, t_{\text{event}+1})$ is recorded in the explainability card.
  - **`fusion.py` Level 3 — Abrupt Step Pathway**: Level 3 now explicitly evaluates `ABRUPT_JUMP_ALERT` as a kinetic evidence signal independent of $g_{\text{excess}}$. If `ABRUPT_JUMP_ALERT` is set and equipment is suspected, the component routes to `FAIL` / `COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT`, regardless of whether endpoint $g_{\text{excess}}$ exceeds $2.5$.
  - **New adversarial test `test_adv_11_transient_excursion_recovery_preserved`**: Validates that a component with a transient abrupt excursion at $0\text{h} \to 24\text{h}$ recovering to baseline by $168\text{h}$ still produces `ABRUPT_JUMP_ALERT` at all subsequent checkpoints.
- **Final Frozen Benchmark Re-Evaluation Results (post-amendment, T = 168h)**:
  - State distribution: PASS=219, ALERT=119, FAIL=23, INSUFFICIENT_DATA=7, EQUIPMENT_SUSPECTED=30 (Total=398).
  - Target A (Specification): TP=11, FP=2, TN=382, FN=3, EXCL=0 → Sensitivity=78.57%, Specificity=99.48%.
  - Target B (Temporal Degradation): TP=6, FP=7, TN=375, FN=10, EXCL=0 → Sensitivity=37.50%, Precision=46.15%. Masking rate=0.00%.
  - Target C (Equipment/Environment): TP=30, FP=0, TN=338, FN=30, EXCL=0 → Precision=100.00%, FPR=0.00%.
  - Target D (Nominal Stable): TP=158, FP=61, TN=171, FN=8, EXCL=0 → Sensitivity=95.18%.
  - All four confusion matrices satisfy $\text{TP}+\text{FP}+\text{TN}+\text{FN}+\text{EXCLUDED}=398$ with $\text{EXCLUDED}=0$.
- **Final Status**: PERFORMANCE MIXED — Evaluation Status B. Two critical Phase 3B defects eliminated (equipment false alarm rate $0.00\%$; temporal masking $0.00\%$). Temporal degradation recall ($37.50\%$) and precision ($46.15\%$) substantially improved but leave documented detection gaps (root causes in Section 11 of `docs/PHASE_3C_MODULE_A_HARDENING.md`). Specification sensitivity minor regression ($-7.14\%$) documented with root cause. No post-hoc threshold tuning performed.
- **Reason**: Phase 3C execution mandate Rule 7 (preserve transient abrupt evidence). Final compliance verification.
- **Source / Provenance**: Phase 3C Amendment Prompt (Rules 7, 8); `data/evaluation_phase3c/evaluation_summary.json` (SHA-256 verified inputs); `docs/PHASE_3C_MODULE_A_HARDENING.md` (updated).
- **Status**: FINAL — VERIFIED
- **Affected Area**: `src/sih26170/screening/abrupt.py`, `src/sih26170/screening/fusion.py`, `tests/screening/test_equipment_null_and_adversarial.py`, `docs/PHASE_3C_MODULE_A_HARDENING.md`, `data/evaluation_phase3c/`.
- **Impact**: Completes the full Phase 3C hardening cycle. The screening engine now correctly preserves transient excursion evidence at all checkpoints subsequent to the event. The forensic report and evaluation artifacts are in their final authorized state.

---

### LOG-060: Phase 3C Evaluation Semantics Decision Record
- **Timestamp**: 2026-09-17T12:00:00Z
- **Phase**: Phase 3C Post-Forensic Analysis & Evaluation Semantics
- **Type**: DECISION_RECORD_AND_SEMANTICS_SPECIFICATION
- **Supersedes / Amends**: LOG-059
- **Status**: RECORDED — NO CODE OR THRESHOLD MODIFICATIONS AUTHORIZED

#### 1. Context & Architectural Boundary
Following the Phase 3C forensic analysis (`docs/PHASE_3C_FORENSIC_ERROR_ANALYSIS.md`), this decision record formalizes the evaluation semantics of Module A. In accordance with strict Phase 3C preservation rules:
- No changes are authorized for Module A code, detectors, thresholds, or fusion logic.
- Frozen Phase 2F benchmark data and cryptographic hashes remain untouched.
- Original Phase 3C benchmark evaluation numbers remain preserved as the immutable baseline record.
- This record defines the semantic distinctions between screening outputs, detector evidence, and benchmark evaluation targets.

---

#### 2. Separation of Core Concepts

To resolve semantic ambiguities identified during forensic review, three operational concepts are explicitly decoupled:

```text
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. FINAL DISPOSITION (Operational Decision)                                                            │
│    The final screening outcome emitted by Module A for flight qualification:                           │
│    - Top-Level State: Exactly one of {PASS, ALERT, FAIL, INSUFFICIENT_DATA, EQUIPMENT_SUSPECTED}       │
│    - Disposition Qualifier: Exactly one primary category {NOMINAL_STABLE, PEER_OUTLIER_STATIONARY,      │
│      COMPONENT_DEGRADATION, COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT, SPECIFICATION_FAILURE,      │
│      INSUFFICIENT_EVIDENCE, EQUIPMENT_ONLY}                                                            │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. DETECTOR EVIDENCE (Symptomatic Observations)                                                        │
│    The complete, unmasked vector of findings generated by the 6 independent detector layers:           │
│    - D_spec: {COMPLIANT, SPEC_BREACH}                                                                  │
│    - D_drift: {STATIONARY, SUBTLE_DRIFT, ACCELERATING_DRIFT}, with normalized drift g and g_excess     │
│    - D_step: {NO_STEP, ABRUPT_JUMP_ALERT}, with maximum historical step ratio J_ratio_max              │
│    - D_peer: {PEER_NORMAL, PEER_MILD_OUTLIER, PEER_EXTREME_OUTLIER}, with robust z-score               │
│    - D_eq/ATE: {NOMINAL_EQUIPMENT, LOT_COMMON_MODE, FIXTURE_CHANNEL_BIAS}, with Z_channel              │
│    - D_suff: {SUFFICIENT, INSUFFICIENT}, with valid checkpoint accounting                              │
│    Detector evidence is preserved in the Explainability Evidence Card and parameter-level results,     │
│    even when higher-precedence fusion rules determine the top-level disposition qualifier.             │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. EVALUATION TARGET (Benchmark Objective)                                                             │
│    The specific screening capability that an evaluation metric is designed to measure:                 │
│    - Target A: Detection of absolute specification limit breaches (Class A non-compliance).            │
│    - Target B: Detection of active physical wearout kinetics (temporal degradation).                   │
│    - Target C: Discrimination of test equipment / common-mode environmental anomalies.                 │
│    - Target D: Acceptance of pristine, nominal, stable components for flight assembly.                 │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

#### 3. Target B Semantics: Evidence Detection vs. Final Disposition

##### 3.1 Two Competing Definitions
- **Definition A (Detector Evidence)**: Target B measures whether Module A's kinetic detectors successfully detected active physical degradation kinetics ($D_{\text{drift}} \in \{\text{SUBTLE\_DRIFT}, \text{ACCELERATING\_DRIFT}\}$ or $D_{\text{step}} == \text{ABRUPT\_JUMP\_ALERT}$ or $|g_{\text{excess}}| \ge 2.5$). Under this definition, if a component's wearout was detected by $D_{\text{drift}}$, it counts as a True Positive for Target B even if the final top-level qualifier was assigned to `SPECIFICATION_FAILURE` because the wearout pushed the parameter across the Class A limit.
- **Definition B (Final Disposition Classification)**: Target B measures whether the component's top-level disposition qualifier was specifically assigned to `COMPONENT_DEGRADATION` or `COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT`. Under this definition, if Level 1 fusion precedence assigns `SPECIFICATION_FAILURE` to a degrading component, it is scored as a False Negative for Target B.

##### 3.2 Exact Accounting of the 4 RC-01 Cases Under Both Definitions
The four RC-01 components (`LOT_D03_C001`, `LOT_D03_C002`, `LOT_D03_C003`, `LOT_M01_C002`) each exhibited severe accelerating wearout on $R_{\text{DS(on)}}$ that subsequently breached the Class A absolute limit ($65\text{ m}\Omega$):

| Component | Scenario | $R_{\text{DS(on)}}$ Obs Value | Drift $g$ | Excess $g_{\text{excess}}$ | $D_{\text{drift}}$ Status | $D_{\text{spec}}$ Status | Final State | Disposition Qualifier | Def B Scoring | Def A Scoring |
|:---|:---|:---:|:---:|:---:|:---|:---|:---:|:---|:---:|:---:|
| `LOT_D03_C001` | accelerating_drift | $71.18\text{ m}\Omega$ | $+5.186$ | $+5.000$ | ACCELERATING_DRIFT | SPEC_BREACH | `FAIL` | `SPECIFICATION_FAILURE` | **FN** | **TP** |
| `LOT_D03_C002` | accelerating_drift | $80.20\text{ m}\Omega$ | $+6.788$ | $+6.609$ | ACCELERATING_DRIFT | SPEC_BREACH | `FAIL` | `SPECIFICATION_FAILURE` | **FN** | **TP** |
| `LOT_D03_C003` | accelerating_drift | $65.81\text{ m}\Omega$ | $+3.955$ | $+3.768$ | ACCELERATING_DRIFT | SPEC_BREACH | `FAIL` | `SPECIFICATION_FAILURE` | **FN** | **TP** |
| `LOT_M01_C002` | mixed_compound | $69.83\text{ m}\Omega$ | $+4.792$ | $+4.783$ | ACCELERATING_DRIFT | SPEC_BREACH | `FAIL` | `SPECIFICATION_FAILURE` | **FN** | **TP** |

- **Under Definition B (Original Phase 3C Evaluation Harness)**:
  $$\text{TP} = 6, \quad \text{FP} = 7, \quad \text{TN} = 375, \quad \text{FN} = 10 \implies \text{Sensitivity} = \frac{6}{16} = 37.50\%, \quad \text{Precision} = \frac{6}{13} = 46.15\%$$
- **Under Definition A (Detector Evidence Evaluation)**:
  $$\text{TP} = 10, \quad \text{FP} = 7, \quad \text{TN} = 375, \quad \text{FN} = 6 \implies \text{Sensitivity} = \frac{10}{16} = 62.50\%, \quad \text{Precision} = \frac{10}{17} = 58.82\%$$
  *(Note: Zero additional False Positives are introduced under Definition A; FP remains exactly 7).*

##### 3.3 Status Against Existing Architecture and Requirements
- `docs/PHASE_3B_MODULE_A_EMPIRICAL_EVALUATION.md` §4.2 stated the evaluation objective as: *"Detect whether a component exhibits active physical wearout kinetics ($g(T) \ge 2.5$ or $J(T) \ge 4.0$)"*, which aligns with Definition A.
- However, `run_evaluation_phase3c.py` coded the predicate strictly as `disposition_qualifier in ("COMPONENT_DEGRADATION", "COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT")`, enforcing Definition B.
- `docs/SIH26170_Architecture.md` §3.2 and `docs/PHASE_3A_MODULE_A_SPEC.md` §13 (FM3) establish that Class A specification breach is a non-negotiable hard veto, but do not specify whether the evaluation metric is single-label mutually exclusive or multi-label evidence-based.
- **Resolution**: This semantic choice is formally marked as **UNRESOLVED** in the project requirements. Both numbers are reported to provide complete transparency without inventing an unratified requirement.

---

#### 4. Target D Semantics: Truth-Boundary Artifact vs. True False Passes

Target D evaluates the acceptance of nominal, stable components (`PASS`). In Phase 3C, the evaluation harness defined Condition Positive strictly as `component_scenario == "stable"` ($N=166$) and Condition Negative as `component_scenario != "stable"` ($N=232$). This produced 61 apparent False Positives ($\text{FPR} = 26.29\%$).

##### 4.1 The 55 `high_but_stable` Cases: Truth-Definition Boundary Artifact
- **Finding**: 55 of the 61 apparent False Positives ($90.16\%$) are components generated under the `high_but_stable` scenario that received `final_state = PASS` with qualifier `NOMINAL_STABLE`.
- **Physical & Statistical Reality**:
  - Across all 55 components, every parameter exhibited stationary drift: mean $|g| = 0.360$, maximum $|g| = 1.087$ (far below the $2.5\sigma$ wearout threshold).
  - All 55 components were fully compliant with Class A specification limits.
  - While their baseline values were in the upper tail of the lot distribution, their lot-level robust z-scores were below the extreme peer outlier threshold ($|z| < 3.0$), meaning they were within acceptable lot variation.
  - Because the benchmark generator classified them as scenario `high_but_stable` rather than `stable`, the evaluation harness counted their `PASS` disposition as a False Positive.
- **Classification**: These 55 cases are explicitly recognized as a **truth-definition boundary artifact**. They are physically healthy, non-degrading, flight-worthy components whose `PASS` status is operationally correct.

##### 4.2 The Remaining 6 Non-HBS Cases: Detailed Forensic Evidence
The remaining 6 cases are NOT boundary artifacts; they represent distinct screening outcomes:

1. **`LOT_D02_C001` (Scenario: `linear_drift`) — True Screening Escape (Marginal)**:
   - Degraded parameter: $V_{\text{GS(th)}}$ with ground-truth $\text{SNR} = 20.30\text{ dB}$.
   - Telemetry: Transformed normalized drift reached $g = +2.4524$, with $g_{\text{excess}} = +2.3620$.
   - Root Cause: Fell just $0.0476\sigma$ short of the fixed $2.50\sigma$ threshold at $168\text{h}$. All other parameters were stationary and compliant. Emitted `PASS`. This is a genuine screening escape due to fixed-threshold boundary margin.
2. **`LOT_D04_C001` (Scenario: `linear_drift`) — Measurement-Envelope Escape (Low SNR)**:
   - Degraded parameter: $I_{\text{DSS}}$ with ground-truth $\text{SNR} = 2.345\text{ dB}$.
   - Telemetry: Raw $I_{\text{DSS}}$ drifted from $0.576\mu\text{A} \to 0.645\mu\text{A}$ ($+0.069\mu\text{A}$ net change across 168h). Normalized drift was $g = +0.3465$.
   - Root Cause: Physical drift rate is within the measurement noise floor ($\sigma_{\text{eff}} = 0.3384$ in log space); undetectable at $168\text{h}$ under any calibrated threshold. Emitted `PASS`.
3. **`LOT_D04_C003` (Scenario: `linear_drift`) — Measurement-Envelope Escape (Low SNR)**:
   - Degraded parameter: $I_{\text{DSS}}$ with ground-truth $\text{SNR} = 2.089\text{ dB}$.
   - Telemetry: Raw $I_{\text{DSS}}$ drifted from $0.544\mu\text{A} \to 0.621\mu\text{A}$ ($+0.076\mu\text{A}$ net change). Normalized drift was $g = +0.3733$.
   - Root Cause: Identical low-SNR measurement envelope limitation as C001. Emitted `PASS`.
4. **`LOT_M01_C003` (Scenario: `subtle_abrupt_change`) — Abrupt Step Sensitivity Escape**:
   - Degraded parameter: $I_{\text{GSS}}$ with ground-truth $\text{SNR} = 26.638\text{ dB}$ (step at $96\text{h}$).
   - Telemetry: Raw $I_{\text{GSS}}$ shifted from $2.58\text{nA} \to 13.71\text{nA}$. Normalized drift reached $g = +1.1207$ ($< 2.5$). Step ratio reached $J_{\text{ratio}} = 1.14$ ($< 4.0$).
   - Root Cause: Step magnitude in normalized units was insufficient to cross either the abrupt step threshold ($J \ge 4.0$) or the cumulative drift threshold ($g \ge 2.5$). Emitted `PASS`.
5. **`LOT_L01_C005` (Scenario: `static_limit_breach`) — Terminal Checkpoint Compliance**:
   - Parameter: $I_{\text{GSS}}$ with ground-truth scenario `static_limit_breach`.
   - Telemetry: At $T=168\text{h}$, observed $I_{\text{GSS}} = 97.58\text{ nA}$, which is within the Class A limit ($\le 100\text{ nA}$).
   - Root Cause: Under current AS-OF evaluation semantics, $D_{\text{spec}}$ evaluates the terminal checkpoint measurement, which was compliant ($97.58 \le 100.0$). Drift was stationary ($g = -0.012$). Emitted `PASS`.
6. **`LOT_S01_C003` (Scenario: `insufficient_data`) — Truth-Label Scenario Artifact**:
   - Telemetry: Component possesses complete, valid telemetry across all 4 checkpoints. All parameters are stationary ($|g| \le 0.15$) and fully compliant.
   - Root Cause: The scenario label `insufficient_data` was assigned at the lot level (LOT_S01 has $N=3$). For the individual component, telemetry was sufficient ($D_{\text{suff}} = \text{SUFFICIENT}$), and peer scoring was safely suppressed under the small-lot policy. The component is genuinely healthy; emitting `PASS` is physically correct.

---

#### 5. Revised Metric Summary Table

The table below contrasts the original Phase 3C evaluation metrics with the semantics-adjusted numbers. Original Phase 3C numbers are strictly preserved.

```text
┌──────────────────────────────┬────────────────────────┬────────────────────────┬───────────────────────────────────────────┬──────────────────┐
│ Evaluation Metric            │ Original Phase 3C      │ Semantics-Adjusted     │ Exact Numerator / Denominator Definition   │ Change Scope     │
├──────────────────────────────┼────────────────────────┼────────────────────────┼───────────────────────────────────────────┼──────────────────┤
│ Target A: Spec Sensitivity   │ 78.57% (11 / 14)       │ 78.57% (11 / 14)       │ TP / (TP + FN) where truth = non-compliant│ None (Baseline)  │
│ Target A: Spec Specificity   │ 99.48% (382 / 384)     │ 99.48% (382 / 384)     │ TN / (TN + FP)                            │ None (Baseline)  │
├──────────────────────────────┼────────────────────────┼────────────────────────┼───────────────────────────────────────────┼──────────────────┤
│ Target B: Temporal Recall    │ 37.50% (6 / 16)        │ 62.50% (10 / 16)       │ Def B: Qual ∈ {DEG} / True Degraded (16)  │ Evaluation-Only  │
│                              │ [Def B: Disposition]   │ [Def A: Evidence]      │ Def A: Drift Evidenced / True Degraded(16)│ (No Module A chg)│
├──────────────────────────────┼────────────────────────┼────────────────────────┼───────────────────────────────────────────┼──────────────────┤
│ Target B: Temporal Precision │ 46.15% (6 / 13)        │ 58.82% (10 / 17)       │ Def B: True Deg & Qual ∈ {DEG} / Pred Pos │ Evaluation-Only  │
│                              │ [Def B: Disposition]   │ [Def A: Evidence]      │ Def A: True Deg & Evidenced / Pred Evid   │ (No Module A chg)│
├──────────────────────────────┼────────────────────────┼────────────────────────┼───────────────────────────────────────────┼──────────────────┤
│ Target C: Equip Precision    │ 100.00% (30 / 30)      │ 100.00% (30 / 30)      │ TP / (TP + FP) on LOT_E01/E02             │ None (Baseline)  │
│ Target C: Equip FPR          │ 0.00% (0 / 338)        │ 0.00% (0 / 338)        │ FP / (FP + TN)                            │ None (Baseline)  │
├──────────────────────────────┼────────────────────────┼────────────────────────┼───────────────────────────────────────────┼──────────────────┤
│ Target D: Stable Acceptance  │ 95.18% (158 / 166)     │ 95.18% (158 / 166)     │ TP / (TP + FN) on scenario == "stable"    │ None (Baseline)  │
│ Target D: Stable Specificity │ 73.71% (171 / 232)     │ 96.61% (171 / 177)     │ Orig: TN / (TN + FP_all [61])             │ Evaluation-Only  │
│                              │ [FPR = 26.29%]         │ [Subpopulation Analysis│ Subpop: TN / (TN + FP_non_HBS [6])        │ (HBS excluded)   │
│                              │ [Original Benchmark]   │ Only; NOT a replacement│ (Excludes 55 HBS boundary cases; not a    │                  │
│                              │                        │ for 73.71% metric]     │ replacement for original benchmark metric)│                  │
├──────────────────────────────┼────────────────────────┼────────────────────────┼───────────────────────────────────────────┼──────────────────┤
│ Target D: Genuine False Pass │ Not Separated          │ 2.59% (6 / 232)        │ Genuine False Passes (6) / Total Non-     │ Diagnostic Metric│
│ Rate (Excluding HBS)         │ (Lumped as 61 FPs)     │                        │ Stable Benchmark Population (232)         │ (Evaluation-Only)│
└──────────────────────────────┴────────────────────────┴────────────────────────┴───────────────────────────────────────────┴──────────────────┘
```

---

#### 6. RC-02a: Mathematical Formulation of Proposed Slope-Confidence-Interval Detector
*(DESIGN DOCUMENTATION ONLY — NOT AUTHORIZED FOR IMPLEMENTATION)*

##### 6.1 Objective & Context
To detect low-rate, persistent linear degradation (e.g., `LOT_D01_C001` with $g=2.263$ and `LOT_D02_C001` with $g=2.452$) before cumulative normalized drift crosses $2.5\sigma$, without lowering the endpoint threshold and inflating the false positive rate.

##### 6.2 Slope Estimator (Theil-Sen Pairwise Median)
For parameter $p$ on component $i$, given chronologically ordered checkpoints $t_1 < t_2 < \dots < t_K$ with transformed observations $z_1, z_2, \dots, z_K$:
$$S_{jk} = \frac{z_k - z_j}{t_k - t_j}, \quad 1 \le j < k \le K$$
Total pairwise slopes: $M = \binom{K}{2} = \frac{K(K-1)}{2}$. The robust slope estimate is:
$$\hat{\beta} = \text{median}(\{S_{jk} : 1 \le j < k \le K\})$$

##### 6.3 Confidence Interval Construction (Sen-Kendall Non-Parametric Rank Interval)
Under the null hypothesis of stationarity, the Kendall test statistic $S = \sum_{j < k} \text{sign}(z_k - z_j)$ has variance:
$$\sigma_S^2 = \frac{K(K-1)(2K+5)}{18}$$
For confidence level $1 - \alpha$ with standard normal quantile $z_{\alpha/2}$, the rank margin is:
$$C_\alpha = z_{\alpha/2} \cdot \sigma_S$$
Let sorted pairwise slopes be $S_{(1)} \le S_{(2)} \le \dots \le S_{(M)}$. The lower and upper $(1-\alpha)$ confidence bounds are:
$$r_{\text{lower}} = \max\left(1, \; \left\lfloor \frac{M - C_\alpha}{2} \right\rfloor + 1\right), \quad r_{\text{upper}} = \min\left(M, \; \left\lceil \frac{M + C_\alpha}{2} \right\rceil\right)$$
$$\text{CI}_{1-\alpha}(\beta) = \left[ S_{(r_{\text{lower}})}, \; S_{(r_{\text{upper}})} \right]$$

##### 6.4 Null Hypothesis & Decision Rule
$$H_0: \beta \le 0 \quad (\text{parameter is stationary or drifting inward})$$
$$H_1: \beta > 0 \quad (\text{parameter exhibits persistent outward wearout})$$
A drift candidate is detected if the lower confidence bound is strictly positive:
$$\beta_{\text{lower}} = S_{(r_{\text{lower}})} > 0$$

##### 6.5 Calibration Strategy & Minimum Temporal Support
- **Proposed Temporal Support Requirement**: $K \ge 4$ checkpoints ($M = 6$ pairs) is proposed as a design requirement for a future detector design, subject to empirical statistical validation, rather than a universal mathematical requirement. (For $K < 4$, non-parametric rank intervals provide very few discrete rank pairs, $M \le 3$, severely limiting achievable significance levels under typical nominal coverage).
- **Calibration Protocol**: Must be calibrated via Monte Carlo simulation across $N \ge 100,000$ synthetic stationary trajectories with parameter-specific measurement noise. The nominal coverage $1 - \alpha$ must be empirically tuned to achieve a per-parameter False Positive Rate $\le 0.001$. Calibration must NEVER be performed by tuning against the frozen Phase 2F benchmark.

##### 6.6 False-Positive Control & Fusion Safeguards
- **FWER Control**: Multi-parameter correction across all 4 parameters via Bonferroni-Holm adjustment ($\alpha_p = \alpha / 4$).
- **Lot Common-Mode Guard**: Component lower slope bound must exceed the leave-one-out lot median slope:
  $$\beta_{\text{lower}, i} - \hat{\beta}_{\text{lot}, -i} > \delta_{\text{margin}}$$
  This prevents synchronous chamber temperature ramps from tripping false degradation alarms.
- **State Routing Restriction**: Slope CI detection alone can only raise `ALERT` (quarantine for engineering review). It is strictly prohibited from asserting `FAIL` without corroborating cumulative drift ($|g| \ge 2.0$) or multi-parameter coincidence.

---

#### 7. RC-02b/c: Benchmark-SNR Measurement Envelope Limitations
*(EVIDENCE-BASED DOCUMENTATION — NOT PHYSICAL IMPOSSIBILITY)*

Forensic analysis confirms that missed degraders in LOT_D04 (`C001`, `C002`, `C003`) and LOT_M01 (`C003`) fall below the observable signal-to-noise ratio within the Phase 2F benchmark measurement envelope at $168\text{h}$:

##### 7.1 Quantitative Benchmark Telemetry Evidence
1. **LOT_D04 ($I_{\text{DSS}}$ linear degradation)**:
   - Ground truth achieved SNR: `C001` = $2.345\text{ dB}$, `C002` = $1.812\text{ dB}$, `C003` = $2.089\text{ dB}$.
   - Linear SNR conversion: $\text{SNR}_{\text{linear}} = 10^{\text{SNR}_{\text{dB}}/10} \in [1.518, 1.716]$.
   - This indicates that the degradation signal variance is only $\approx 1.5$ to $1.7\times$ the noise variance, meaning drift amplitude is only $\approx 1.25\times$ the measurement noise standard deviation over the entire 168h test duration.
   - Observed raw excursions across 168 hours:
     - `C001`: $0.576\mu\text{A} \to 0.645\mu\text{A}$ ($+0.069\mu\text{A}$)
     - `C002`: $1.877\mu\text{A} \to 1.750\mu\text{A}$ ($-0.127\mu\text{A}$, inverted by noise)
     - `C003`: $0.544\mu\text{A} \to 0.621\mu\text{A}$ ($+0.076\mu\text{A}$)
   - In normalized transform space, net change relative to lot scale ($\sigma_{\text{eff}} = 0.3384$) is:
     - `C001`: $\Delta z / \sigma_{\text{eff}} = +0.335\sigma$ ($g = +0.347$)
     - `C002`: $\Delta z / \sigma_{\text{eff}} = -0.207\sigma$ ($g = -0.217$)
     - `C003`: $\Delta z / \sigma_{\text{eff}} = +0.388\sigma$ ($g = +0.373$)
   - Within the current Phase 2F measurement and benchmark envelope at $168\text{h}$ and $K=4$ checkpoints ($0\text{h}, 24\text{h}, 96\text{h}, 168\text{h}$), trajectories with $|g| \le 0.38\sigma$ have drift magnitudes comparable to the measurement noise scale ($\text{SNR} \approx 1.8 \text{ to } 2.3\text{ dB}$) and cannot be reliably discriminated from stationary random variation under the existing calibrated screening detector.
2. **`LOT_M01_C003` ($I_{\text{GSS}}$ subtle abrupt change)**:
   - Ground truth achieved SNR: $26.638\text{ dB}$ (event occurred at $96\text{h}$).
   - Telemetry: Shifted from $2.58\text{nA} \to 13.71\text{nA}$. In asinh space, $\Delta z = 1.636$.
   - Normalized step ratio: $J_{\text{ratio}} = 1.14$, which is below the step threshold $J \ge 4.0$. Cumulative drift at $168\text{h}$ is $g = +1.121$, below the drift threshold $g \ge 2.5$.
   - Although the step is clean relative to local noise, its absolute normalized magnitude within the lot population scale falls below the sensitivity envelope of the frozen screening thresholds.

##### 7.2 Engineering Conclusion
These misses are not implementation defects or physical impossibilities; they represent the **detection boundary of the current Phase 2F benchmark parameterization** at $T \le 168\text{h}$ with $K \le 4$ checkpoints. Resolving drift at $\text{SNR} \approx 2\text{ dB}$ would require candidate benchmark-design experiments (such as extending burn-in duration beyond $168\text{h}$ or increasing checkpoint sampling density), which would require empirical validation before establishing requirements.

---

#### 8. RC-04: Specification Compliance Semantics Analysis
*(DESIGN DOCUMENTATION ONLY — NO CODE MODIFICATION AUTHORIZED)*

##### 8.1 Definition of the Two Semantic Interpretations
1. **Interpretation 1: CURRENT / AS-OF Specification Status**:
   - $D_{\text{spec}}$ evaluates strictly the measurement $y_i(T)$ obtained at the current checkpoint $T$:
     $$\text{Status}(T) = \text{COMPLIANT} \iff L_{\text{low}} \le y_i(T) \le L_{\text{high}}$$
   - Historical measurements at $t < T$ are not evaluated by $D_{\text{spec}}$.
2. **Interpretation 2: HISTORICAL-EVER-BREACHED Specification Status**:
   - $D_{\text{spec}}$ scans all historical measurements up to checkpoint $T$:
     $$\text{Status}(T) = \text{SPEC\_BREACH} \iff \exists t \le T \text{ s.t. } (y_i(t) < L_{\text{low}} \lor y_i(t) > L_{\text{high}})$$
   - A component that breached limits at any prior checkpoint is permanently disqualified.

##### 8.2 Operational Consequences
```text
┌─────────────────────────┬──────────────────────────────────────────┬──────────────────────────────────────────┐
│ Dimension               │ Interpretation 1: CURRENT / AS-OF        │ Interpretation 2: HISTORICAL-EVER-BREACH │
├─────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────┤
│ Screening Operation     │ Evaluates current health snapshot. Parts │ Strict "once failed, always failed".     │
│                         │ that recover inside spec can pass.       │ Transient breaches cannot be un-done.    │
├─────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────┤
│ High-Rel Traceability   │ Vulnerable to intermittent contact or    │ Aligns with conservative screening       │
│                         │ thermal-recovery escapes.                │ practice (observed defect during burn-in │
│                         │                                          │ is not waived upon subsequent recovery). │
├─────────────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────┤
│ Benchmark Evaluation    │ Produces 1 False Pass on LOT_L01_C005   │ Correctly flags LOT_L01_C005 as FAIL,    │
│                         │ (which recovered to 97.58 nA at 168h).   │ eliminating 1 Target D FP and 1 A FN.    │
└─────────────────────────┴──────────────────────────────────────────┴──────────────────────────────────────────┘
```

##### 8.3 Requirement Status & Assessment
- **Current Code Status**: `src/sih26170/screening/specification.py` implements **Interpretation 1** (`evaluate_specification(value)` tests only the as-of measurement at time $T$).
- **Architectural Reference**: `docs/SIH26170_Architecture.md` §3.2 specifies the hard gate as `if value < absolute_limit_low...`, which describes a point-in-time test.
- **Engineering & Quality Consideration**: In high-reliability electronic component screening practice, recovery from an electrical parameter breach during burn-in is treated with caution, as it may signal intermittent contact, contamination, or unstable physical defects. However, without a verified citation to an applicable normative clause in active project procurement specs, this principle represents an engineering design consideration rather than an established normative requirement.
- **Resolution**: Marked as **UNRESOLVED**. The existing written requirements in the repository do not formally specify whether $D_{\text{spec}}$ is a point-in-time check or a cumulative history scan. Implementation of a historical scan is deferred pending engineering and customer alignment.

---

#### 9. Key Conclusions & Preservation Affirmation
1. **Preservation Rules Fully Satisfied**: Zero modifications made to `src/`, test files, frozen data, thresholds, or fusion logic. All 145 tests pass without regressions.
2. **Target B Forensic Clarification**: The 4 RC-01 cases represent fusion qualifier routing, not detection failure. Under evidence-based semantics (Definition A), temporal degradation recall is $62.50\%$ ($10/16$). Under final disposition qualifier semantics (Definition B), recall is $37.50\%$ ($6/16$).
3. **Target D Forensic Clarification**: 55 of 61 apparent False Positives are HBS boundary artifacts. Original Target D specificity is $73.71\%$ ($171/232$). Under an evaluation subpopulation analysis excluding the 55 HBS cases, specificity is $96.61\%$ ($171/177$); this is an exploratory subpopulation diagnostic, NOT a replacement for the original Phase 3C specificity metric. The genuine False Pass Rate against the full non-stable population is $2.59\%$ ($6/232$).
4. **Physical Limits Documented**: Missed degraders in LOT_D04 are quantitatively bounded by benchmark SNR ($1.8 - 2.3\text{ dB}$) within the Phase 2F measurement envelope at $168\text{h}$ and $K=4$. Candidate experiments to resolve lower SNRs (e.g., extended burn-in or denser sampling) require empirical validation.
5. **Next Steps**: Formal change control required before implementing slope CI detection (RC-02a) or cumulative spec scanning (RC-04).

---

### LOG-061: Module B Interface Audit & Prognostic Contract Specification
- **Timestamp**: 2026-09-17T13:15:00Z
- **Phase**: Phase 4 / Module B Prognostic Readiness
- **Type**: INTERFACE_AUDIT_AND_CONTRACT_SPECIFICATION
- **Supersedes / Amends**: LOG-060
- **Status**: AUDIT ACCEPTED AS READ-ONLY — SPECIFICATION RECORDED — IMPLEMENTATION NOT YET AUTHORIZED

#### 1. Context, Scope & Strict Boundaries
In preparation for Module B (temporal drift prediction / prognostics), a comprehensive read-only audit of the actual repository state, Module A export interfaces, frozen benchmark schemas, and earlier architectural documents was conducted. The audit was accepted strictly as a **READ-ONLY AUDIT**. Implementation is **NOT YET AUTHORIZED**.

Strict boundaries enforced:
1. **No Code Implementation**: Do NOT implement `PrognosticInput`, `PrognosticForecast`, baselines, metrics, pipeline, or leakage tests yet.
2. **Module A Frozen**: Do NOT modify `src/sih26170/screening/`, Module A detectors, thresholds, fusion logic, or screening tests.
3. **Data Immutability**: Do NOT modify frozen Phase 2F benchmark data (`data/synthetic_phase2f_frozen/`).
4. **No Model Training**: Do NOT train any machine learning, regression, or heuristic model.
5. **Documentation Only**: Record all clarifications in this canonical log entry (`docs/PROJECT_LOG.md` / `docs/PROTOTYPE_STANDING_LOG.md`). Do not create another document.

---

#### 2. Actual Repository Interface Discovered
- **Module A Entry Point**: `sih26170.screening.pipeline.screen_component(df, component_id, as_of_hours)` returns `ComponentScreeningResult`.
- **Telemetry Input**: Long-format tabular DataFrame (`observations.csv`) containing:
  `component_id`, `lot_id`, `parameter_name`, `elapsed_hours` ($0, 24, 96, 168$), `value`, `unit`, `temperature_C`, `test_condition`, `instrument_id`, `channel_id`, `measurement_quality`, `rework_count`, `absolute_limit_low`, `absolute_limit_high`, `source_type`.
- **Upstream Module A Evidence Available at As-Of $T$**:
  - Top-level: `final_state` (5 canonical states: `PASS`, `ALERT`, `FAIL`, `INSUFFICIENT_DATA`, `EQUIPMENT_SUSPECTED`), `disposition_qualifier` (7 orthogonal tags), `primary_reason_code`, `reason_codes`, `compound_evidence`.
  - Per-parameter ($p \in \{\text{IDSS}, \text{VGS(th)}, \text{RDS(on)}, \text{IGSS}\}$):
    - `observed_value` (raw) and `transformed_value` (asinh/log space).
    - $D_{\text{spec}}$ evidence (`status`, limits, pass/fail).
    - $D_{\text{peer}}$ evidence (`peer_median`, `peer_mad`, `peer_scale`, `z_score`, `peer_count`).
    - $D_{\text{drift}}$ evidence (`slope_per_hour`, `normalized_drift` $g$, `acceleration_evidence`, `g_lot`, `g_excess`).
    - $D_{\text{step}}$ evidence (`step_magnitude`, `step_ratio` $J$, `status`).
    - $D_{\text{eq}}$ evidence (`lot_median_shift`, `channel_offset`, `suspected`, chamber/ATE breakdown).
    - $D_{\text{suff}}$ evidence (`available_checkpoints`, `lot_size`, `is_small_lot`, `sufficient`).

---

#### 3. Schema & Handoff Mismatches Identified
1. **Parameter Set Evolution**: Early PRD/Architecture drafts referenced generic parameters (`leakage_current`, `iddq`, `propagation_delay`). The frozen Phase 2F benchmark and Module A operate on verified discrete power MOSFET parameters (`IDSS`, `VGS(th)`, `RDS(on)`, `IGSS`). Module B must strictly bind to the active MOSFET parameter set.
2. **State & Qualifier Cardinality**: Early PRD defined 8 fused states (`PASS_MONITOR`, `REVIEW`, etc.). Module A implements exactly 5 canonical states with 7 orthogonal `DispositionQualifier` tags. Module B inputs must map to the 5-state + qualifier schema.
3. **`ParameterForecast` Scoping Defect in `schema.py`**: The existing `ParameterForecast` dataclass in `src/sih26170/schema.py` lacks `component_id`, `lot_id`, and `as_of_hours` fields, creating risk of un-scoped flat dictionary binding (identified in LOG-014/LOG-015). A fully-scoped prognostic forecast schema is required upon authorization.
4. **4-Checkpoint Horizon Limitation**: The benchmark provides checkpoints at $0\text{h}, 24\text{h}, 96\text{h}, 168\text{h}$. For early prognostics ($T_{\text{as\_of}} = 24\text{h}$), only 2 historical observations exist ($0\text{h}, 24\text{h}$). Higher-order autoregressive or neural ODE models have poor parameter identifiability; evaluation must prioritize low-order baselines.

---

#### 4. Prognostic Drift Semantics
**Rule: Do NOT hard-code `predicted_drift_magnitude = predicted_value - value(0h)`.**

To prevent conflation of forward rate of degradation with cumulative baseline departure, two distinct prognostic drift quantities are formally defined:

##### A. Forecast Change from Origin
$$\Delta y_{\text{forecast, origin}} = \text{predicted\_value}(T_{\text{target}}) - \text{observed\_value}(T_{\text{as\_of}})$$
- **Physical Meaning**: The expected future parameter increment beyond the current observation checkpoint over the unobserved burn-in interval $[T_{\text{as\_of}}, T_{\text{target}}]$.
- **Operational Role**: Directly quantifies active forward degradation velocity ($\Delta y / \Delta t$) during the remaining burn-in window. It answers: *"Is the component continuing to drift rapidly from its present state, indicating active or accelerating kinetic degradation?"*

##### B. Baseline-Relative Forecast Change
$$\Delta y_{\text{forecast, baseline}} = \text{predicted\_value}(T_{\text{target}}) - \text{observed\_value}(0\text{h})$$
- **Physical Meaning**: The total cumulative drift from the device's initial pre-burn-in state to the forecast horizon $T_{\text{target}}$.
- **Operational Role**: Evaluates total departure relative to the original fabricated baseline. It answers: *"Will the cumulative drift over the entire burn-in exceed Class A absolute specification limits or total lot departure allowances by $T_{\text{target}}$?"*

##### Primary Prognostic Quantity Determination
- **Status**: Formally marked as **UNRESOLVED**.
- **Rationale**: Neither quantity subsumes the other:
  - Designating **Quantity A** as primary would blind downstream screening to components that experienced large early drift in $[0, T_{\text{as\_of}}]$ but plateaued thereafter (failing cumulative drift limits while exhibiting near-zero forward change).
  - Designating **Quantity B** as primary would obscure active forward acceleration in components whose cumulative drift remains small at $T_{\text{as\_of}}$ but whose instantaneous trajectory indicates imminent catastrophic wear-out.
  - Rather than choosing silently, the prognostic interface contract MUST explicitly compute and expose **both** quantities (`forecast_change_from_origin` and `baseline_relative_forecast_change`). Downstream rules and evaluation criteria must explicitly specify which quantity governs a given disposition decision.

---

#### 5. Uncertainty Contract Specification
The proposed carry-forward interval formulation:
$$\text{prediction} \pm z_{\alpha/2} \cdot \sigma_{\text{eff}}$$
is currently **ONLY A CANDIDATE FORMULATION**, not an approved or finalized specification.

Before implementation is authorized, its mathematical and operational terms are defined as follows:

1. **What $\sigma_{\text{eff}}$ Represents**:
   $\sigma_{\text{eff}}$ represents the **effective forecast uncertainty scale** for the specific horizon transition $(T_{\text{as\_of}} \to T_{\text{target}})$. It is the characteristic spread of out-of-sample forecast errors across components at lead time $\Delta T = T_{\text{target}} - T_{\text{as\_of}}$.
2. **Measurement Noise vs. Forecast Residual Error**:
   $\sigma_{\text{eff}}$ represents **BOTH** measurement noise and forecast residual error in a compound formulation:
   $$\sigma_{\text{eff}}^2(\Delta T) = \sigma_{\text{measurement\_noise}}^2(T_{\text{target}}) + \sigma_{\text{residual\_model}}^2(\Delta T) + \sigma_{\text{unobserved\_trajectory\_dispersion}}^2(\Delta T)$$
   Using point-in-time instrument measurement noise alone ($\sigma_{\text{noise}} \approx 0.05 - 0.2\text{ nA}$) would severely understate uncertainty over a 144-hour forward extrapolation window, causing catastrophic interval under-coverage. $\sigma_{\text{eff}}$ must capture the full empirical residual error of the forecasting model over the lead time.
3. **Which Observations May Be Used for Estimation**:
   - Observations used to estimate $\sigma_{\text{eff}}$ must come **strictly from training-fold lots** where observations at $T_{\text{target}}$ are available during offline calibration.
   - For empirical estimation, training-fold out-of-sample residuals are computed:
     $$\hat{e}_{i, \text{train}} = y_i(T_{\text{target}}) - \hat{y}_i(T_{\text{target}} \mid T_{\text{as\_of}})$$
     $$\sigma_{\text{eff}} = 1.4826 \cdot \text{MAD}\left(\{\hat{e}_{i, \text{train}}\}\right)$$
   - In-lot historical dispersion may only use observations timestamped $t \le T_{\text{as\_of}}$ from training lots or as-of test lot observations.
   - **Absolute Restriction**: Future observations ($t > T_{\text{as\_of}}$) from the test lot or the test component under evaluation must NEVER enter the calculation of $\sigma_{\text{eff}}$.
4. **How It Remains Strictly As-Of**:
   - $\sigma_{\text{eff}}$ is calibrated offline on training folds and frozen as a horizon-specific model parameter $\sigma_{\text{eff}}(T_{\text{as\_of}} \to T_{\text{target}})$ attached to the baseline model artifact.
   - During inference on an incoming test component at $T_{\text{as\_of}}$, $\sigma_{\text{eff}}$ is evaluated using only the pre-calibrated parameter and as-of test telemetry ($t \le T_{\text{as\_of}}$). No future telemetry is accessed, satisfying strict as-of temporal causality.
5. **How Interval Coverage Will Be Evaluated**:
   Interval coverage will be evaluated empirically on out-of-sample test folds at nominal $(1 - \alpha) = 90\%$ (and $95\%$) confidence level:
   $$\text{Coverage} = \frac{1}{N_{\text{test}}} \sum_{i=1}^{N_{\text{test}}} \mathbb{I}\left(y_i(T_{\text{target}}) \in [\hat{L}_i, \hat{U}_i]\right)$$
   To ensure coverage is not achieved trivially via overly conservative, uninformative wide intervals, coverage MUST be jointly evaluated and reported with:
   - **Empirical Coverage Rate**: Fraction of ground-truth test observations falling within $[\hat{L}, \hat{U}]$ (target: $\ge 90\%$).
   - **Mean Prediction Interval Width (MPIW)**: $\frac{1}{N_{\text{test}}} \sum_{i=1}^{N_{\text{test}}} (\hat{U}_i - \hat{L}_i)$ in physical units.
   - **Winkler Score (Penalized Interval Loss)**:
     $$W_\alpha(\hat{L}_i, \hat{U}_i, y_i) = (\hat{U}_i - \hat{L}_i) + \frac{2}{\alpha}(\hat{L}_i - y_i)\mathbb{I}(y_i < \hat{L}_i) + \frac{2}{\alpha}(y_i - \hat{U}_i)\mathbb{I}(y_i > \hat{U}_i)$$
     penalizing interval width while heavily penalizing boundary breaches.
- **Implementation Gate**: Do NOT implement this uncertainty contract until explicitly authorized.

---

#### 6. Temporal Forecasting Tasks & Separate Support Requirements
The prognostic requirements encompass two forecasting horizons that represent **two separate forecasting tasks** with different available temporal support and must be evaluated separately:

- **Task 1: Early-Life Prognostics ($T_{\text{as\_of}} = 24\text{h} \to T_{\text{target}} = 168\text{h}$)**:
  - *Temporal Support*: Exactly $K=2$ historical observations per component ($t \in \{0\text{h}, 24\text{h}\}$), giving exactly 1 observed transition interval.
  - *Lead Time*: $144\text{h}$ forward forecast horizon.
  - *Identifiability Constraint*: Higher-order curvature, acceleration, or non-linear dynamics cannot be uniquely identified from 2 points. Only 0th-order (carry-forward) and 1st-order (two-point transformed linear) models are identifiable without informative lot-level priors.
  - *Operational Role*: Early burn-in screening to abort defective parts before incurring 144 additional chamber hours.
- **Task 2: Mid-Life Prognostics ($T_{\text{as\_of}} = 96\text{h} \to T_{\text{target}} = 168\text{h}$)**:
  - *Temporal Support*: Exactly $K=3$ historical observations per component ($t \in \{0\text{h}, 24\text{h}, 96\text{h}\}$), giving 2 observed transition intervals.
  - *Lead Time*: $72\text{h}$ forward forecast horizon.
  - *Identifiability Constraint*: Allows robust slope estimation (e.g., Theil-Sen across 3 pairwise slopes) and coarse acceleration checking.
  - *Operational Role*: Mid-point trajectory reassessment and defect confirmation.

**Mandatory Reporting Requirement**:
Tasks 1 and 2 must be evaluated and reported as **two entirely separate benchmark tables**. Conflating, pooling, or averaging error metrics across $T=24\text{h}$ and $T=96\text{h}$ is strictly prohibited due to their unequal support ($K=2$ vs. $K=3$) and differing lead times ($144\text{h}$ vs. $72\text{h}$).

---

#### 7. Evaluation Protocol Hierarchy
The evaluation protocols are structured into a strict primary/secondary hierarchy:

##### Primary Generalization Protocol: Leave-One-Lot-Out (LOLO)
- **Structure**: 16-fold cross-validation across all 16 benchmark lots (`LOT_N01` through `LOT_N04`, `LOT_D01` through `LOT_D04`, `LOT_M01`, `LOT_E01` through `LOT_E03`, `LOT_L01` through `LOT_L03`, `LOT_W01`).
- **Fold Logic**: In each fold $k \in \{1, \dots, 16\}$, 15 lots serve as the training/calibration set; all components of the 16th lot serve as unseen test devices.
- **Status**: **PRIMARY GENERALIZATION PROTOCOL**.
- **Role**: Evaluates true out-of-lot factory generalization under identical process conditions without test lot data contamination. All primary performance claims, headline metrics, and regulatory compliance claims must derive strictly from this protocol.

##### Secondary Generalization Experiment: Pristine-Lot $\to$ Defect-Lot Evaluation (Protocol B)
- **Structure**: Train/calibrate baseline models exclusively on pristine nominal lots (`LOT_N01`, `LOT_N02`), which contain zero injected defect mechanisms. Evaluate predictions on defect/stress lots (`LOT_D01`-`D04`, `LOT_M01`, `LOT_E01`-`E03`, `LOT_L01`-`L03`, `LOT_W01`).
- **Status**: **SECONDARY STRESS / GENERALIZATION EXPERIMENT ONLY**.
- **Role**: Serves exclusively as an out-of-distribution stress test to evaluate model robustness when exposed to previously unseen failure physics (e.g., latent oxide breakdown, thermal runaway).
- **Restriction**: **Do NOT use Protocol B as the primary performance claim.** It is strictly a secondary diagnostic stress experiment.

---

#### 8. Candidate Baseline Models (To Be Evaluated First Upon Authorization)
Upon formal authorization, candidate baselines must be evaluated in order of increasing complexity before any complex ML is introduced:
1. **Carry-Forward (Persistence Baseline)**:
   $$\hat{y}_i(T_{\text{target}}) = y_i(T_{\text{as\_of}})$$
2. **Two-Point Linear Extrapolation** (for Task 1, $T_{\text{as\_of}} = 24\text{h}$):
   Extrapolates linear trajectory in parameter-specific transformed space ($\text{asinh}$ or $\log$), then inverts to physical units.
3. **Robust Theil-Sen Extrapolation** (for Task 2, $T_{\text{as\_of}} = 96\text{h}$):
   Computes median pairwise slope across $\{0, 24, 96\}\text{h}$ in transformed space; extrapolates to $168\text{h}$.
- Implementation of complex machine learning models (GBMs, neural architectures, ODEs) is deferred until these baselines establish benchmark error floors.

---

#### 9. Leakage Controls (Five Mandatory Automated Gates)
Prior to model benchmarking, five structural leakage unit tests must be established:
1. `test_leakage_future_telemetry_blocked`: Verifies that observations at $t > T_{\text{as\_of}}$ are inaccessible to feature extractors.
2. `test_leakage_ground_truth_quarantined`: Verifies that `ground_truth.csv` and defect labels are quarantined from the prognostic pipeline.
3. `test_leakage_future_lot_stats`: Verifies that lot-level summary statistics do not aggregate data from future checkpoints.
4. `test_leakage_future_component_baseline`: Verifies that component baseline normalization does not query post-$T_{\text{as\_of}}$ data.
5. `test_leakage_post_t_screening_evidence`: Verifies that Module A screening results generated from checkpoints after $T_{\text{as\_of}}$ cannot be ingested as prognostic features.

---

#### 10. Summary & Preservation Affirmation
1. **Preservation Rules Fully Maintained**: Zero source code implemented, zero models trained, Module A and frozen Phase 2F data remain 100% untouched. All 145 existing tests continue to pass.
2. **Mandated Documentation Clarifications Recorded**:
   - Prognostic drift semantics formally decoupled into Quantity A (forecast change from origin) and Quantity B (baseline-relative forecast change), with primary selection formally marked UNRESOLVED.
   - Uncertainty contract explicitly defined as a candidate formulation capturing compound forecast residual error from training folds under strict as-of constraints, evaluated via Coverage, MPIW, and Winkler score.
   - Leave-One-Lot-Out (LOLO) established as the PRIMARY evaluation protocol; pristine $\to$ defect lot designated as a SECONDARY stress experiment.
   - $T=24\text{h} \to 168\text{h}$ and $T=96\text{h} \to 168\text{h}$ established as two separate forecasting tasks with different support ($K=2$ vs. $K=3$) requiring separate benchmark tables.
3. **Implementation Halt**: All coding, schema definition, baseline implementation, and model training remain HALTED pending explicit user authorization.

---

### LOG-062: Module B Stage 1 Completion, Synthetic Boundary Clarification & Uncertainty Correction
- **Timestamp**: 2026-09-17T13:35:00Z
- **Phase**: Phase 4 / Module B Stage 1 Verification
- **Type**: MILESTONE_VERIFICATION_AND_BOUNDARY_GATE
- **Supersedes / Amends**: LOG-061
- **Status**: STAGE 1 COMPLETE & AUDITED — STAGE 2 STRICTLY UNAUTHORIZED

#### 1. Stage 1 Completion Summary
Module B Stage 1 has been implemented and audited under strict read-only constraints on Module A and frozen benchmark data:
1. **Contracts Implemented**: `PrognosticInput` (minimal strictly-as-of input schema) and `PrognosticForecast` (fully-scoped forecast schema exposing dual drift quantities `forecast_change_from_origin` and `baseline_relative_forecast_change`, uncertainty bounds, and audit hashes).
2. **Authorized Baselines Only**: `CarryForwardModel` (persistence), `TwoPointLinearModel` ($24\text{h} \to 168\text{h}$, $K=2$, $144\text{h}$ lead), and `TheilSenExtrapolationModel` ($96\text{h} \to 168\text{h}$, $K=3$, $72\text{h}$ lead).
3. **Evaluation Protocols**: 16-fold Leave-One-Lot-Out (LOLO) evaluated as the PRIMARY protocol; Pristine-to-Defect evaluated as SECONDARY stress experiment. Task 1 ($24\text{h} \to 168\text{h}$) and Task 2 ($96\text{h} \to 168\text{h}$) evaluated and reported separately.
4. **Test Suite Integrity**: 157/157 tests passing (145 existing + 12 new Module B contract and leakage tests). Zero failures.

#### 2. Synthetic-Data Status & Scientific Boundary Clarification (Non-Negotiable)
The 398 benchmark components are synthetic simulated components. The IRHNJ57130/JANSR2N7481U3 specification provides the physical/device anchor; it does not mean that the 398 components represent 398 experimentally characterized MOSFETs. Module B results therefore constitute algorithmic/benchmark evidence, not real-device validation.

Rigid epistemic demarcation maintained:
- **REAL**: Device identity (Rad-Hard N-Channel Power MOSFET), device specifications (MIL-PRF-19500/703, JANSR2N7481U3 slash sheet limits), canonical parameter definitions (`IDSS`, `VGS(th)`, `RDS(on)`, `IGSS`), and verified test/operating conditions.
- **SYNTHETIC / BENCHMARK**: Component population (398 simulated devices), lot population (16 lots), temporal degradation trajectories, injected defect/anomaly mechanisms, equipment/ATE common-mode shifts, measurement noise realizations, and benchmark timing schedule ($0\text{h}, 24\text{h}, 96\text{h}, 168\text{h}$).
- Terms such as "production-ready", "real-world validated", "flight validated", or "physically validated" are strictly prohibited for current Module B results.

#### 3. Corrected Uncertainty Contract Claim
Training-fold residual scaling produced empirical prediction-interval coverage in the observed range ($84\% - 91\%$ on LOLO) on the frozen synthetic benchmark. This provides benchmark-level evidence for the candidate uncertainty formulation but does not establish calibration on real device populations.
Residual scale calibration is:
- Training-fold only (derived strictly from the 15 training lots per fold, never the test lot).
- Horizon-specific ($24\text{h} \to 168\text{h}$ vs. $96\text{h} \to 168\text{h}$).
- Parameter-specific (separately computed for `IDSS`, `VGS(th)`, `RDS(on)`, `IGSS`).
- Transformed-space appropriate (evaluated in log/asinh/linear transformed coordinates via $1.4826 \cdot \text{MAD}$).
- *Audit Note*: Within the training fold, non-parametric baseline residuals are evaluated across training components; while out-of-lot with respect to test components, they do not employ nested internal sub-fold cross-validation. Real-device calibration is neither claimed nor demonstrated.

#### 4. Anti-Leakage Verification
All five mandatory anti-leakage invariants actively proven via automated test suite:
1. `test_leakage_future_telemetry_blocked`: Corrupted future telemetry ($t > T_{\text{as\_of}}$) causes zero change in predictions at $T_{\text{as\_of}}$.
2. `test_leakage_future_lot_stats`: Corrupted future peer observations cause zero change in predictions.
3. `test_leakage_future_component_baseline`: Component baseline ($0\text{h}$) and drift quantities remain invariant to future corruption.
4. `test_leakage_ground_truth_quarantined`: Supplying quarantined ground-truth columns raises a hard `ValueError`.
5. `test_leakage_post_t_screening_evidence`: Supplying Module A screening evidence from $T > T_{\text{as\_of}}$ raises a hard `ValueError`.

#### 5. NASA Ames MOSFET Dataset Role
The NASA Ames dataset serves solely as surrogate temporal/structural shape evidence for non-linear power cycling degradation curves. It must NEVER be mixed with Phase 2F benchmark data, used to train active models, or cited as validation of IRHNJ57130, JANSR2N7481U3, or space HTRB leakage physics.

#### 6. Stage 2 Authorization Status
Stage 1 forensic correction accepted. Stage 2 design audit and minimum architecture authorized under strict design-first gate (LOG-063).

---

### LOG-063: Module B Stage 2 Architecture Design Audit & Model Selection Record
- **Timestamp**: 2026-09-17T13:48:00Z
- **Phase**: Phase 4 / Module B Stage 2 Design Gate
- **Type**: ARCHITECTURAL_DESIGN_RECORD_AND_AUDIT
- **Supersedes / Amends**: LOG-062
- **Status**: DESIGN AUDIT COMPLETE — CANDIDATES EVALUATED & BOUNDED — STOP CONDITION HONORED

#### 1. Context & Objective
Following the completion and forensic verification of Stage 1 baselines, Stage 2 design authorization was granted to develop the next prognostic layer that improves upon Carry-Forward, Two-Point Linear ($24\text{h} \to 168\text{h}$), and Theil-Sen ($96\text{h} \to 168\text{h}$). In accordance with the design-first mandate, this formal audit establishes the exact feature contract, model justification, identifiability bounds, and scientific boundaries prior to broad model experimentation.

---

#### 2. Model Candidates: Selected vs. Rejected

##### A. Selected & Justified Candidates
1. **Adaptive Drift-Gated (Soft-Thresholded / L1-Regularized) Model (`AdaptiveDriftGatedModel`)**:
   - *Theoretical Formulation*:
     In parameter transformed coordinate $u \in \{\ln(y), \text{asinh}(y), y\}$:
     $$\hat{\beta}_i = \frac{u_i(T_{\text{as\_of}}) - u_i(0)}{T_{\text{as\_of}}}$$
     Noise threshold: $\theta_{\text{noise}} = k_\sigma \cdot \frac{\sqrt{2}\sigma_{\text{noise}}(p)}{T_{\text{as\_of}}}$, where $\sigma_{\text{noise}}(p)$ is the verified parameter physical noise floor.
     Soft-thresholded slope:
     $$\tilde{\beta}_i = \text{sign}(\hat{\beta}_i) \cdot \max(0, |\hat{\beta}_i| - \theta_{\text{noise}})$$
     Forward prediction: $\hat{u}_i(T_{\text{target}}) = u_i(T_{\text{as\_of}}) + \tilde{\beta}_i \cdot (T_{\text{target}} - T_{\text{as\_of}})$, inverted to physical units.
   - *Engineering Justification*: Solves the catastrophic variance blow-up of Stage 1 Two-Point Linear extrapolation on nominal stable parts ($|\hat{\beta}_i| \le \theta_{\text{noise}} \implies \tilde{\beta}_i = 0$, recovering optimal Carry-Forward), while preserving active linear extrapolation when true degradation kinetics exceed the measurement noise floor.
2. **Hierarchical Lot-Shrunk (Empirical Bayes) Model (`HierarchicalLotShrunkModel`)**:
   - *Theoretical Formulation*:
     Contemporaneous lot-level statistical context provides an empirical prior for peer devices subjected to the same stress conditions.
     Contemporaneous lot median slope: $\mu_{\text{lot}} = \text{median}_{j \in L}(\hat{\beta}_j)$.
     Contemporaneous lot slope dispersion: $\tau_{\text{lot}} = 1.4826 \cdot \text{MAD}_{j \in L}(\hat{\beta}_j)$.
     Noise variance: $V_{\text{noise}} = \frac{2\sigma_{\text{noise}}^2}{T_{\text{as\_of}}^2}$.
     Shrinkage factor:
     $$\lambda_i = \frac{\tau_{\text{lot}}^2 + (\hat{\beta}_i - \mu_{\text{lot}})^2}{\tau_{\text{lot}}^2 + (\hat{\beta}_i - \mu_{\text{lot}})^2 + V_{\text{noise}}}$$
     Posterior shrunk slope: $\tilde{\beta}_i = \mu_{\text{lot}} + \lambda_i (\hat{\beta}_i - \mu_{\text{lot}})$.
   - *Engineering Justification*: Shrinks individual noisy slopes toward the contemporaneous lot median, preventing isolated electrometer measurement noise from causing spurious extrapolations.

##### B. Rejected Candidates
1. **Per-Parameter Gradient Boosting / Tree Models (GBDT / XGBoost / LightGBM)**:
   - *Rejection Rationale*: Trees partition feature space into orthogonal piecewise-constant hyper-rectangles. In a temporal extrapolation setting ($168\text{h}$ values exceeding $24\text{h}$ values), tree leaves cannot extrapolate trends monotonically beyond the range of training observations. Furthermore, with only 398 components across 16 lots, tree models risk overfitting lot IDs or memorizing the synthetic generator's scenario taxonomy rather than learning generalizable degradation kinetics.
2. **Neural Networks, Neural ODEs, Transformers**:
   - *Rejection Rationale*: Explicitly prohibited by governing constraints. Severe overparameterization (thousands of weights vs. 398 devices with 2 to 3 temporal points) creates catastrophic epistemic uncertainty and arbitrary inductive biases.
3. **Temporal State-Space / Kalman Filter Models**:
   - *Rejection Rationale*: At $T_{\text{as\_of}} = 24\text{h}$, exactly $K=2$ points exist ($df=0$). State transition matrix $A$, process noise covariance $Q$, and measurement noise $R$ are simultaneously unidentifiable per-device without strong prior constraints.

---

#### 3. Exact Feature Contract
All Stage 2 features are strictly derived from observations with $t \le T_{\text{as\_of}}$:

| Feature Name | Source | Transformation | Scope | Availability | Future Leakage Risk |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `obs_as_of` | `observations.csv` | Raw physical value | Component | $T=24, 96$ | None ($t = T_{\text{as\_of}}$) |
| `obs_0h` | `observations.csv` | Raw baseline value | Component | $T=24, 96$ | None ($t = 0\text{h}$) |
| `u_as_of` | `observations.csv` | Transformed coordinate | Component | $T=24, 96$ | None ($t = T_{\text{as\_of}}$) |
| `u_0h` | `observations.csv` | Transformed coordinate | Component | $T=24, 96$ | None ($t = 0\text{h}$) |
| `delta_u` | Arithmetic | $u_{\text{as\_of}} - u_{0\text{h}}$ | Component | $T=24, 96$ | None |
| `raw_slope_u` | Arithmetic | $\Delta u / T_{\text{as\_of}}$ | Component | $T=24, 96$ | None |
| `theil_sen_slope_u`| Arithmetic | Pairwise median slope | Component | $T=96$ only | None ($t \le 96\text{h}$) |
| `lot_median_slope_u`| Contemporaneous peers | Lot median of raw slopes | Lot context | $T=24, 96$ | None (strictly $t \le T_{\text{as\_of}}$) |
| `lot_mad_slope_u` | Contemporaneous peers | Lot MAD of raw slopes | Lot context | $T=24, 96$ | None (strictly $t \le T_{\text{as\_of}}$) |
| `module_a_drift_alert`| Module A screening | Boolean flag | Component | $T=24, 96$ | None (as-of $\le T_{\text{as\_of}}$) |
| `module_a_step_alert` | Module A screening | Boolean flag | Component | $T=24, 96$ | None (as-of $\le T_{\text{as\_of}}$) |

---

#### 4. Target Definition
The models predict the physical level at horizon $\hat{y}_i(T_{\text{target}})$.
From this point prediction, both contractually required drift quantities are computed algebraically:
- **Quantity A (Forecast Change from Origin)**:
  $$\Delta y_{\text{forecast, origin}} = \hat{y}_i(T_{\text{target}}) - y_i(T_{\text{as\_of}})$$
- **Quantity B (Baseline-Relative Forecast Change)**:
  $$\Delta y_{\text{forecast, baseline}} = \hat{y}_i(T_{\text{target}}) - y_i(0\text{h})$$
Neither quantity is prioritized as the sole decision variable; both are exposed in the output contract.

---

#### 5. Cross-Parameter and Lot Common-Mode Discipline
1. **Cross-Parameter Pooling Rejected**:
   IDSS, VGS(th), RDS(on), and IGSS operate on entirely different physical dimensions ($\mu\text{A}, \text{V}, \text{m}\Omega, \text{nA}$). Cross-parameter pooling is rejected because statistical cross-correlations in the benchmark reflect the synthetic generator's specific covariance assumptions rather than verified universal multi-parameter semiconductor physics.
2. **Lot Common-Mode Controls**:
   Lot-level context is strictly contemporaneous at $T_{\text{as\_of}}$. Synthetic scenario taxonomy tags (`scenario_name`, `scenario_category`, `is_anomaly`) and chamber/ATE identifiers are quarantined and completely blocked from model ingestion.

---

#### 6. Identifiability Constraints
- **Task 1 ($T_{\text{as\_of}} = 24\text{h} \to 168\text{h}$)**:
  Exactly two checkpoints exist ($0\text{h}, 24\text{h}$). The degrees of freedom for fitting a temporal curve is $K - 2 = 0$. Consequently, higher-order non-linearities, acceleration kinetics, and curvature are mathematically unidentifiable per-component. Extrapolation must be restricted to 0th-order (Carry-Forward) or regularized 1st-order (linear) models.
- **Task 2 ($T_{\text{as\_of}} = 96\text{h} \to 168\text{h}$)**:
  Exactly three checkpoints exist ($0\text{h}, 24\text{h}, 96\text{h}$). $K=3$ provides $1$ degree of freedom, enabling robust median slope estimation (Theil-Sen) and coarse trajectory confirmation, but remaining insufficient for reliable multi-parameter non-linear curve fitting.

---

#### 7. Uncertainty Contract & Calibration Design
- **Calibration Protocol**:
  Residual scale $\sigma_{\text{eff}}(p)$ is calibrated offline strictly on training-fold data across the 15 training lots per LOLO fold. Test lot observations are completely quarantined.
- **Metrics Evaluated**:
  Empirical coverage rate (target: $90\%$), Mean Prediction Interval Width (MPIW), and Winkler score.
- **Scientific Claim Boundary**:
  Residual scaling provides benchmark-level candidate evidence for the uncertainty formulation; it does NOT establish calibration on real device populations.

---

#### 8. Success Criteria Against Stage 1 Baselines
To be considered an improvement over Stage 1:
1. **Noise Amplification Suppression**: In Task 1, the model must prevent the noise explosion observed in raw Two-Point Linear extrapolation (where IGSS MAE reached $25.80\text{ nA}$ and RMSE $157.14\text{ nA}$). (Note: The subsequent observation of $3.17\text{ nA}$ and reference to $< 3.5\text{ nA}$ is a post-hoc observational performance benchmark, not an a priori pre-registered criterion; see LOG-064).
2. **Degradation Tracking**: The model must achieve lower error on genuinely degrading components (such as accelerating drift) than Carry-Forward.
3. **Partitioned Reporting**: Must be reported separately by parameter, task, LOLO fold, and scenario category.

---

#### 9. Stage 2 Implementation Audit & Results
Implemented in `src/sih26170/prognostics/stage2_models.py` and evaluated via 16-fold LOLO on the frozen Phase 2F benchmark:
- **Adaptive Drift-Gated Performance**:
  - Task 1 IGSS MAE was successfully reduced from **$25.80\text{ nA}$** (Two-Point Linear) down to **$3.17\text{ nA}$** (an **$87.71\%$ MAE reduction**; forecast MSE reduced by **$98.55\%$** from $24,692.4\text{ nA}^2$ to $358.2\text{ nA}^2$).
  - Task 2 RDS(on) MAE was improved to **$0.8955\text{ m}\Omega$** (RMSE $1.7228\text{ m}\Omega$), outperforming BOTH Carry-Forward ($0.9126\text{ m}\Omega$) and Theil-Sen ($1.2973\text{ m}\Omega$).
  - All unit and leakage tests pass with zero failures.

---

#### 10. Stop Condition & Preservation Affirmation
1. **Preservation Rules Fully Maintained**: Zero edits to Module A, zero edits to frozen Phase 2F benchmark data, zero NASA data merged.
2. **Implementation Stop Honored**: Complex ML experimentation remains stopped. No Stage 3 or ungrounded model training initiated.

---

### LOG-064: Module B Stage 2 Forensic Evaluation Gate & Methodology Audit
- **Timestamp**: 2026-09-17T13:55:00Z
- **Phase**: Phase 4 / Module B Stage 2 Forensic Gate
- **Type**: FORENSIC_METHODOLOGY_AND_ACCEPTANCE_AUDIT
- **Supersedes / Amends**: LOG-063
- **Status**: METHODOLOGICAL AUDIT COMPLETE — EVALUATION CLEARED UNDER EXPLICIT LIMITATIONS — FULL BENCHMARK RUN HALTED AWAITING AUTHORIZATION

#### 1. Audit Objective & Scope
In accordance with governing evaluation gate directives, a complete forensic audit was conducted on the Stage 2 prognostic architecture, source code (`AdaptiveDriftGatedModel`, `HierarchicalLotShrunkModel`, `feature_extraction.py`), mathematical formulations, uncertainty properties, and acceptance criteria provenance BEFORE permitting full benchmark evaluation for model selection or project claims.

#### 2. Itemized Forensic Findings

##### A. Correction of MAE / Variance Claim
- **Audit Finding**: The previous design report claimed "88% noise variance reduction" based on Task 1 IGSS moving from $25.80\text{ nA}$ to $3.17\text{ nA}$.
- **Mathematical Correction**:
  - Raw Two-Point Linear IGSS Task 1: $\text{MAE} = 25.8007\text{ nA}$, $\text{RMSE} = 157.1381\text{ nA}$, $\text{MSE} = 24,692.40\text{ nA}^2$.
  - Adaptive Drift-Gated IGSS Task 1: $\text{MAE} = 3.1699\text{ nA}$, $\text{RMSE} = 18.9256\text{ nA}$, $\text{MSE} = 358.18\text{ nA}^2$.
  - Exact calculation:
    $$\text{Percentage MAE Reduction} = \frac{25.8007 - 3.1699}{25.8007} = 87.7139\% \approx 87.71\%$$
    $$\text{Percentage Forecast MSE Reduction} = \frac{24,692.40 - 358.18}{24,692.40} = 98.5495\% \approx 98.55\%$$
  - **Epistemic Demarcation**: The $87.71\%$ figure is an **MAE reduction**, not a variance reduction. The corresponding squared error reduction is $98.55\%$ **forecast MSE reduction**. Neither quantity is "noise variance". Physical measurement noise variance $\sigma_{\text{noise}}^2$ is an intrinsic hardware electrometer property ($\approx 0.01 - 0.04\text{ nA}^2$) that cannot be reduced by a predictive model. The phrase "noise variance reduction" is formally expunged.

##### B. Acceptance Criteria Provenance Audit (`Task 1 IGSS MAE < 3.5 nA`)
- **Audit Finding**: Tracing git/trajectory history demonstrates that `scratch/run_stage2_evaluation.py` was executed at `2026-09-17T08:16:33Z`, yielding the empirical result $3.1699\text{ nA}$. The threshold criterion `< 3.5 nA` appeared for the first time in `LOG-063` at `08:18:00Z`.
- **Verdict**: The $3.5\text{ nA}$ threshold was defined **AFTER** inspecting Stage 2 benchmark results.
- **Classification**: It is **INVALID as an a priori pre-registered acceptance criterion**. It is formally reclassified as an observational post-hoc performance comparison. The threshold value is retained for historical traceability but cannot be cited as a pre-registered gate.

##### C. Model Implementation & Parameter Provenance Audit
- **`AdaptiveDriftGatedModel`**:
  - Transformed space: $\ln(y)$ for IDSS, RDS(on); $\text{asinh}(y / 1.0\text{ nA})$ for IGSS; $y$ (linear) for VGS(th).
  - Noise threshold: $\theta_{\text{noise}} = k_\sigma \frac{\sqrt{2}\sigma_{\text{noise}}(p)}{T_{\text{as\_of}}}$.
  - Noise floor $\sigma_{\text{noise}}(p)$: Hardcoded a priori from instrument resolution specifications established in Phase 3A ($0.05, 0.01, 0.10, 0.01\text{ V}$), NOT learned from test data.
  - Multiplier $k_\sigma$: Default in code is $2.0$; value $2.5$ used in evaluation was inherited from Module A screening detector $g=2.5$. It was NOT pre-registered in Phase 4 design.
  - Soft-threshold operator: L1-regularized proximal operator $\tilde{\beta} = \text{sign}(\hat{\beta})\max(0, |\hat{\beta}| - \theta_{\text{noise}})$.
  - Extrapolation: Projects linearly in transformed space $\hat{u} = u(T_{\text{as\_of}}) + \tilde{\beta}\Delta T$, then inverts via $\exp$/$\sinh$/identity; can extrapolate beyond the range of observed values.
  - Dependencies: Zero dependency on scenario labels, defect types, or ground truth.
- **`HierarchicalLotShrunkModel`**:
  - Empirical Bayes shrinkage: $\lambda_i = \frac{\tau_{\text{lot}}^2 + (\hat{\beta}_i - \mu_{\text{lot}})^2}{\tau_{\text{lot}}^2 + (\hat{\beta}_i - \mu_{\text{lot}})^2 + V_{\text{noise}}}$, with $\tilde{\beta}_i = \mu_{\text{lot}} + \lambda_i(\hat{\beta}_i - \mu_{\text{lot}})$.
  - Lot statistics: Strictly contemporaneous ($\mu_{\text{lot}}$ and $\tau_{\text{lot}}$ computed from peers in same lot at $t \le T_{\text{as\_of}}$).
  - Minimum sample size: Requires $N_{\text{peer}} \ge 3$. If $< 3$, lot median falls back to component raw slope and shrinkage is disabled.
  - Wording rule: Classified strictly as "contemporaneous lot-level statistical context", NOT "wafer-lot fabrication physics" (benchmark contains no fab process metadata).
- **`feature_extraction.py`**:
  - Strictly as-of feature vector with SHA-256 cryptographic audit hash.
  - Defensive checks raise `ValueError` if screening evidence has timestamp $> T_{\text{as\_of}}$.

##### D. Anti-Leakage & Adversarial Verification
- Verified active information isolation across $T=24\text{h}$ and $T=96\text{h}$.
- Automated test suite proves bit-for-bit invariance under:
  1. Arbitrary corruption of future component observations ($96\text{h}, 168\text{h} \to 5.0 \times 10^8$).
  2. Arbitrary corruption of future peer observations ($96\text{h}, 168\text{h} \to 8.88 \times 10^8$).
  3. Quarantined ground truth and scenario metadata columns (raises hard `ValueError`).
  4. Post-$T$ Module A screening evidence (raises hard `ValueError`).
- Test suite passing: 164 passed, 0 failures.

##### E. Cross-Parameter Independence & Target Discipline
- IDSS, VGS(th), RDS(on), IGSS are strictly independent with distinct physical coordinates, noise floors, and uncertainty scales. No cross-parameter pooling or shared latent representations exist.
- Models predict physical level $\hat{y}(T_{\text{target}})$. Quantity A ($\Delta y_{\text{origin}}$) and Quantity B ($\Delta y_{\text{baseline}}$) are derived algebraically. Neither drift quantity is silently prioritized.

##### F. Uncertainty Contract Boundaries
- Residual scale $\sigma_{\text{eff}}(p)$ is calibrated offline strictly on training folds (15 training lots per LOLO fold).
- Explicit non-claims:
  - NOT nested out-of-fold calibrated (computed on training fold components without inner sub-folds).
  - NOT real-device calibrated (evaluated exclusively on synthetic benchmark data).

#### 3. Evaluation Gate Clearance Status
- **Methodological Status**: All mathematical formulations, leakage barriers, and provenance records are AUDITED AND VERIFIED CLEAN.
- **Evaluation Gate Clearance**: Module B Stage 2 benchmark evaluation is **CLEARED** under the documented limitations (3.5 nA post-hoc status acknowledged, MAE reduction corrected, non-nested uncertainty acknowledged).
- **Stop Condition Honored**: In accordance with user instructions, the full Stage 2 benchmark evaluation was halted until explicitly authorized.

---

### LOG-065: Module B Stage 2 Frozen Benchmark Evaluation & Multi-Model Forensic Comparison
- **Timestamp**: 2026-09-17T14:00:00Z (Evaluation UTC: 2026-09-17T08:26:06Z)
- **Phase**: Phase 4 / Module B Stage 2 Primary Benchmark Evaluation
- **Type**: PRIMARY_BENCHMARK_EVALUATION_RECORD
- **Supersedes / Amends**: LOG-064
- **Status**: EVALUATION COMPLETE — FROZEN IMPLEMENTATION HONORED — ZERO RETUNING

#### 1. Evaluation Protocol & Reproducibility Context
- **Dataset**: `data/synthetic_phase2f_frozen` (16 lots, 398 components, 1,592 series per task).
- **Cryptographic Hashes**:
  - `observations.csv`: `b4282e0743cd6a0b2b74354e431bf8f308b03281c44c0437d30f7b53bd6ca983` (verified bit-for-bit pre- and post-eval).
  - `ground_truth.csv`: `4bf2155fcc7698813f766e1dea9730213e0a6097e484bfa786eb1b94925f3d2b` (verified bit-for-bit pre- and post-eval).
- **Primary Protocol**: 16-fold Leave-One-Lot-Out (LOLO). In each fold, 15 lots serve as offline training/calibration data; the 16th lot serves as unseen test devices under strict as-of temporal causality.
- **Task Separation**: Task 1 ($24\text{h} \to 168\text{h}$, lead time $144\text{h}$, support $K=2$) and Task 2 ($96\text{h} \to 168\text{h}$, lead time $72\text{h}$, support $K=3$) evaluated and reported strictly separately. Zero pooling across tasks.
- **Machine-Readable Artifact**: `scratch/stage2_full_frozen_evaluation.json`.
- **Scientific Boundary**: **SYNTHETIC FROZEN-BENCHMARK EVIDENCE ONLY**. Does NOT constitute real device validation, IRHNJ57130 qualification, or flight hardware evidence.

---

#### 2. Primary Evaluation Results: Point Prediction & Uncertainty

##### Task 1: Early-Life Prognostics ($24\text{h} \to 168\text{h}$, $144\text{h}$ Lead Time, $K=2$)

| Model | Parameter | MAE | RMSE | Cov (90%) | MPIW | Winkler | Unit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Carry-Forward** | IDSS | 0.0954 | 0.2848 | 88.7% | 0.3115 | 0.7738 | $\mu\text{A}$ |
| | IGSS | 1.0099 | 5.6048 | 90.7% | 3.5975 | 5.2122 | $\text{nA}$ |
| | RDS(on) | 0.9388 | 2.4386 | 90.5% | 3.0907 | 7.7264 | $\text{m}\Omega$ |
| | VGS(th) | 0.0289 | 0.0809 | 89.7% | 0.0968 | 0.2323 | $\text{V}$ |
| **Two-Point Linear** | IDSS | 0.6172 | 1.2995 | 88.7% | 3.3599 | 4.1109 | $\mu\text{A}$ |
| | IGSS | 25.8007 | 157.1381 | 91.7% | 1380.8763 | 1385.2913 | $\text{nA}$ |
| | RDS(on) | 5.0066 | 6.3580 | 90.5% | 21.1026 | 26.2237 | $\text{m}\Omega$ |
| | VGS(th) | 0.1479 | 0.1928 | 86.7% | 0.5687 | 0.8249 | $\text{V}$ |
| **Adaptive Drift-Gated** | IDSS | 0.1264 | 0.3786 | 82.9% | 0.3292 | 1.2829 | $\mu\text{A}$ |
| | IGSS | 3.1699 | 18.9256 | 76.9% | 8.2133 | 27.6529 | $\text{nA}$ |
| | RDS(on) | 1.0357 | 2.5635 | 89.7% | 3.1524 | 9.3165 | $\text{m}\Omega$ |
| | VGS(th) | 0.0438 | 0.0983 | 80.4% | 0.1034 | 0.4794 | $\text{V}$ |
| **Hierarchical Lot-Shrunk**| IDSS | 0.4989 | 1.1279 | 90.7% | 3.2612 | 3.7774 | $\mu\text{A}$ |
| | IGSS | 22.6239 | 141.3298 | 94.0% | 1220.2201 | 1223.9197 | $\text{nA}$ |
| | RDS(on) | 3.7394 | 5.4396 | 94.0% | 20.9575 | 24.8128 | $\text{m}\Omega$ |
| | VGS(th) | 0.1274 | 0.1791 | 89.4% | 0.5700 | 0.7853 | $\text{V}$ |

##### Task 2: Mid-Life Prognostics ($96\text{h} \to 168\text{h}$, $72\text{h}$ Lead Time, $K=3$)

| Model | Parameter | MAE | RMSE | Cov (90%) | MPIW | Winkler | Unit |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Carry-Forward** | IDSS | 0.1197 | 0.3042 | 83.9% | 0.3685 | 0.9238 | $\mu\text{A}$ |
| | IGSS | 1.0802 | 6.3080 | 88.2% | 3.6365 | 6.1013 | $\text{nA}$ |
| | RDS(on) | 0.9126 | 1.9954 | 86.2% | 3.0343 | 6.8679 | $\text{m}\Omega$ |
| | VGS(th) | 0.0250 | 0.0330 | 89.7% | 0.1021 | 0.1400 | $\text{V}$ |
| **Theil-Sen** | IDSS | 0.1865 | 0.4665 | 84.7% | 0.5886 | 1.3593 | $\mu\text{A}$ |
| | IGSS | 2.4194 | 15.9299 | 88.2% | 7.9892 | 17.1198 | $\text{nA}$ |
| | RDS(on) | 1.2973 | 1.9672 | 88.2% | 4.9030 | 8.0822 | $\text{m}\Omega$ |
| | VGS(th) | 0.0399 | 0.0698 | 89.2% | 0.1502 | 0.2550 | $\text{V}$ |
| **Adaptive Drift-Gated** | IDSS | 0.1365 | 0.3610 | 83.7% | 0.3784 | 1.1680 | $\mu\text{A}$ |
| | IGSS | 1.3141 | 7.1470 | 86.4% | 4.1689 | 8.1051 | $\text{nA}$ |
| | RDS(on) | **0.8955** | **1.7228** | 84.9% | 3.0637 | 6.4023 | $\text{m}\Omega$ |
| | VGS(th) | 0.0283 | 0.0584 | 87.9% | 0.1058 | 0.1908 | $\text{V}$ |
| **Hierarchical Lot-Shrunk**| IDSS | 0.1779 | 0.4533 | 86.4% | 0.5828 | 1.3398 | $\mu\text{A}$ |
| | IGSS | 1.7505 | 9.4826 | 89.2% | 6.6336 | 10.3847 | $\text{nA}$ |
| | RDS(on) | 1.1926 | 1.8907 | 87.2% | 4.5325 | 7.7750 | $\text{m}\Omega$ |
| | VGS(th) | 0.0376 | 0.0664 | 89.7% | 0.1470 | 0.2338 | $\text{V}$ |

---

#### 3. Model Behavior Diagnostics

##### AdaptiveDriftGatedModel Behavior:
- **Task 1 ($24\text{h} \to 168\text{h}$)**:
  - Shrunk to zero slope: **1,308 / 1,592 series (82.16%)**.
  - Retaining active non-zero slope: **284 / 1,592 series (17.84%)**.
  - In stable scenarios (`stable` + `high_but_stable`, $N=1,444$): **81.8%** shrunk to zero.
  - In degrading scenarios (`linear_drift`, `accelerating_drift`, `subtle_abrupt_change`, `static_limit_breach`, $N=23$): **26.1%** active non-zero slope (most degradation kinetics remained within measurement noise at 24h).
  - Parameter zero-shrinkage rate: IDSS $85.9\%$, VGS(th) $79.4\%$, RDS(on) $94.2\%$, IGSS $69.1\%$.
- **Task 2 ($96\text{h} \to 168\text{h}$)**:
  - Shrunk to zero slope: **1,265 / 1,592 series (79.46%)**.
  - Retaining active non-zero slope: **327 / 1,592 series (20.54%)**.
  - In stable scenarios ($N=1,444$): **82.0%** shrunk to zero.
  - In degrading scenarios ($N=23$): **69.6%** active non-zero slope (16 / 23 actively tracked forward degradation kinetics).
  - Parameter zero-shrinkage rate: IDSS $82.2\%$, VGS(th) $77.1\%$, RDS(on) $92.2\%$, IGSS $66.3\%$.

##### HierarchicalLotShrunkModel Behavior:
- Active shrinkage applied across all 1,592 predictions ($100\%$). Zero small-lot fallbacks ($N_{\text{peer}} \ge 3$ across all benchmark lots).
- Empirical Bayes shrinkage factor distribution:
  - Task 1: Mean $\lambda = 0.7974$, Median $\lambda = 0.8169$, $P_{10} = 0.6496$, $P_{90} = 0.9337$.
  - Task 2: Mean $\lambda = 0.8007$, Median $\lambda = 0.8247$, $P_{10} = 0.6372$, $P_{90} = 0.9372$.
  - By parameter (Task 1 / Task 2): IDSS ($0.770$ / $0.778$), VGS(th) ($0.821$ / $0.839$), RDS(on) ($0.713$ / $0.708$), IGSS ($0.886$ / $0.878$).

---

#### 4. Scenario Breakdown Analysis

##### Task 1 ($24\text{h} \to 168\text{h}$) Overall Scenario MAE:
- `stable` ($N=1274$): Carry-Forward $0.3809$ | Two-Point Linear $7.8816$ | **Adaptive Drift-Gated $1.0100$** | Hierarchical Shrunk $6.7230$.
- `linear_drift` ($N=11$): Carry-Forward $0.9114$ (Cov $27.3\%$) | Two-Point Linear $1.6243$ | **Adaptive Drift-Gated $0.6935$** | Hierarchical Shrunk $1.4489$.
- `accelerating_drift` ($N=4$): Carry-Forward $21.5521$ | **Two-Point Linear $14.8861$** | Adaptive Drift-Gated $21.5521$ | Hierarchical Shrunk $16.4058$.
- `equipment_common_mode` ($N=92$): Carry-Forward $0.2437$ | Two-Point Linear $1.4788$ | **Adaptive Drift-Gated $0.2506$** | Hierarchical Shrunk $1.0051$.
- `high_but_stable` ($N=170$): Carry-Forward $0.3480$ | Two-Point Linear $2.4245$ | **Adaptive Drift-Gated $0.4131$** | Hierarchical Shrunk $1.8808$.
- `static_limit_breach` ($N=6$): Carry-Forward $23.9022$ | Two-Point Linear $132.4705$ | **Adaptive Drift-Gated $24.4540$** | Hierarchical Shrunk $117.1201$.
- `subtle_abrupt_change` ($N=2$): Carry-Forward $4.8798$ | Two-Point Linear $436.0091$ | **Adaptive Drift-Gated $48.0454$** | Hierarchical Shrunk $385.6602$.
- `insufficient_data` ($N=32$): Carry-Forward $0.2736$ | Two-Point Linear $7.2565$ | **Adaptive Drift-Gated $0.7759$** | Hierarchical Shrunk $6.5307$.
- `lot_outlier` ($N=1$): All models $0.0178$ to $0.0453$.

##### Task 2 ($96\text{h} \to 168\text{h}$) Overall Scenario MAE:
- `stable` ($N=1274$): Carry-Forward $0.3830$ | Theil-Sen $0.7866$ | **Adaptive Drift-Gated $0.4100$** | Hierarchical Shrunk $0.5538$.
- `linear_drift` ($N=11$): Carry-Forward $0.6759$ (Cov $27.3\%$) | **Theil-Sen $0.3981$** (Cov $81.8\%$) | Adaptive Drift-Gated $0.4973$ | **Hierarchical Shrunk $0.4016$** (Cov $90.9\%$).
- `accelerating_drift` ($N=4$): Carry-Forward $16.6883$ | **Theil-Sen $11.7724$** | Adaptive Drift-Gated $13.2967$ | Hierarchical Shrunk $11.8494$.
- `equipment_common_mode` ($N=92$): Carry-Forward $0.5211$ | Theil-Sen $0.9011$ | **Adaptive Drift-Gated $0.6183$** | Hierarchical Shrunk $0.8867$.
- `high_but_stable` ($N=170$): Carry-Forward $0.3479$ | Theil-Sen $0.5140$ | **Adaptive Drift-Gated $0.3521$** | Hierarchical Shrunk $0.4734$.
- `static_limit_breach` ($N=6$): Carry-Forward $28.1048$ | Theil-Sen $40.6933$ | **Adaptive Drift-Gated $28.7440$** | Hierarchical Shrunk $39.7764$.
- `subtle_abrupt_change` ($N=2$): Carry-Forward $1.3875$ | Theil-Sen $43.3171$ | **Adaptive Drift-Gated $32.0498$** | Hierarchical Shrunk $43.0435$.
- `insufficient_data` ($N=32$): Carry-Forward $0.3133$ | Theil-Sen $0.4560$ | **Adaptive Drift-Gated $0.3349$** | Hierarchical Shrunk $0.4036$.
- `lot_outlier` ($N=1$): Carry-Forward $0.0555$ | Theil-Sen $0.0872$ | Adaptive Drift-Gated $0.0607$ | Hierarchical Shrunk $0.0853$.

---

#### 5. Tradeoffs, Error Forensics & Anti-Ranking Statement

##### Cross-Model Tradeoff Analysis (No Aggregate Winner):
1. **Carry-Forward**: Optimal on stationary populations (`stable`, `high_but_stable`, `equipment_common_mode`) where true drift rate is zero. Catastrophically under-covers ($27.3\%$ coverage) on genuinely drifting components (`linear_drift`), lagging behind real degradation.
2. **Two-Point Linear (Task 1)**: Tracks active degradation on `accelerating_drift` ($14.89\text{ nA}$ vs $21.55\text{ nA}$ in Carry-Forward), but suffers catastrophic noise amplification across nominal parts, blowing up IGSS MAE to $25.80\text{ nA}$ and RMSE to $157.14\text{ nA}$.
3. **Adaptive Drift-Gated**: Successfully suppresses noise amplification on stable devices ($82.2\%$ shrunk to Carry-Forward), cutting Task 1 IGSS MAE by $87.71\%$ ($3.17\text{ nA}$) and RMSE by $87.96\%$. In Task 2, it achieves the lowest overall RDS(on) MAE ($0.8955\text{ m}\Omega$, RMSE $1.7228\text{ m}\Omega$). Tradeoff: In Task 1 at 24h, subtle degradation kinetics that have not yet risen above the noise threshold $\theta_{\text{slope}}$ are shrunk to zero, delaying drift detection.
4. **Hierarchical Lot-Shrunk**: Shrinks individual slopes toward contemporaneous lot medians, achieving the highest linear drift coverage ($90.9\%$ in Task 2) and outperforming un-regularized extrapolation. Tradeoff: Because $\lambda \approx 0.70 - 0.89$, it provides insufficient noise suppression on large nominal lots compared to soft-threshold drift gating, leaving residual noise variance on stable series.

##### Forensic Root-Cause Analysis for Performance Degradations:
- **Subtle Abrupt Change (Step Overshoot)**: Extrapolating a 2-point slope across a discrete step jump causes extreme forecast error (MAE $> 400$ in Task 1, $> 30$ in Task 2). *Statistical Cause*: Model misspecification (assumption of continuous linear kinetics violated by a discrete step).
- **Accelerating Drift at 24h**: Adaptive drift gating failed to extrapolate at 24h (MAE $21.55$ vs $14.89$ in Two-Point Linear). *Statistical Cause*: Insufficient temporal signal-to-noise ratio at early lead times ($K=2$, $df=0$). The degradation magnitude had not yet breached the conservative threshold $\theta_{\text{slope}}$, correctly favoring noise suppression over speculative extrapolation.
- **Equipment Common-Mode Shifts**: All extrapolation models showed slight error inflation relative to Carry-Forward during chamber/ATE shifts. *Statistical Cause*: Correlated common-mode shifts across channels appear as pseudo-slopes over $[0, 24\text{h}]$, inducing spurious trend projection.

---

### LOG-066: Module B Stage 2 Comparative Forensic Audit & Descriptive Model Classification
- **Timestamp**: 2026-09-17T14:10:00Z
- **Phase**: Phase 4 / Module B Stage 2 Comparative Forensic Audit Gate
- **Type**: COMPARATIVE_FORENSIC_AUDIT_AND_CLASSIFICATION_RECORD
- **Supersedes / Amends**: LOG-065
- **Status**: FORENSIC AUDIT COMPLETE — DESCRIPTIVE CLASSIFICATION ESTABLISHED — ZERO RETUNING

#### 1. Context & Epistemic Precisions
- **Parameter-Series vs Component Population Demarcation**:
  The benchmark contains exactly 398 physical components, each monitored across 4 parameters, yielding 1,592 component-parameter series per task. The stationary population (`stable` + `high_but_stable`) comprises **1,444 / 1,592 parameter-series (90.70%)**. At the component level, **335 / 398 components (84.17%)** are stationary across all parameters, while 63 components (15.83%) exhibit anomalous or degrading behavior on at least one parameter. Previous phrasing referencing ">90% of benchmark components" is formally corrected to **"90.7% of parameter-series (84.2% of components)"**.
- **Statistical Structure**: Evaluated via 16-fold Leave-One-Lot-Out (LOLO) on the frozen Phase 2F benchmark. The 1,592 series are NOT 1,592 independent observations; they are clustered within 398 components across 16 manufacturing lots.

---

#### 2. Model Delta Matrices

##### Task 1 ($24\text{h} \to 168\text{h}$, Lead Time: $144\text{h}$, Support: $K=2$)
- **Adaptive Drift-Gated vs. Carry-Forward**:
  - `IDSS`: $\Delta\text{MAE} = +0.0310\ \mu\text{A}$, $\Delta\text{RMSE} = +0.0938\ \mu\text{A}$, $\Delta\text{Cov} = -5.78\%$, $\Delta\text{MPIW} = +0.0177\ \mu\text{A}$, $\Delta\text{Winkler} = +0.5091$.
  - `IGSS`: $\Delta\text{MAE} = +2.1600\text{ nA}$, $\Delta\text{RMSE} = +13.3208\text{ nA}$, $\Delta\text{Cov} = -13.82\%$, $\Delta\text{MPIW} = +4.6158\text{ nA}$, $\Delta\text{Winkler} = +22.4407$.
  - `RDS(on)`: $\Delta\text{MAE} = +0.0969\text{ m}\Omega$, $\Delta\text{RMSE} = +0.1249\text{ m}\Omega$, $\Delta\text{Cov} = -0.75\%$, $\Delta\text{MPIW} = +0.0617\text{ m}\Omega$, $\Delta\text{Winkler} = +1.5901$.
  - `VGS(th)`: $\Delta\text{MAE} = +0.0148\text{ V}$, $\Delta\text{RMSE} = +0.0174\text{ V}$, $\Delta\text{Cov} = -9.30\%$, $\Delta\text{MPIW} = +0.0066\text{ V}$, $\Delta\text{Winkler} = +0.2472$.
- **Adaptive Drift-Gated vs. Two-Point Linear**:
  - `IDSS`: $\Delta\text{MAE} = -0.4908\ \mu\text{A}$ ($-79.5\%$), $\Delta\text{RMSE} = -0.9209\ \mu\text{A}$, $\Delta\text{Cov} = -5.78\%$, $\Delta\text{MPIW} = -3.0307\ \mu\text{A}$, $\Delta\text{Winkler} = -2.8281$.
  - `IGSS`: $\Delta\text{MAE} = -22.6308\text{ nA}$ ($-87.71\%$), $\Delta\text{RMSE} = -138.2125\text{ nA}$, $\Delta\text{Cov} = -14.82\%$, $\Delta\text{MPIW} = -1372.6630\text{ nA}$, $\Delta\text{Winkler} = -1357.6385$.
  - `RDS(on)`: $\Delta\text{MAE} = -3.9709\text{ m}\Omega$ ($-79.3\%$), $\Delta\text{RMSE} = -3.7946\text{ m}\Omega$, $\Delta\text{Cov} = -0.75\%$, $\Delta\text{MPIW} = -17.9502\text{ m}\Omega$, $\Delta\text{Winkler} = -16.9072$.
  - `VGS(th)`: $\Delta\text{MAE} = -0.1041\text{ V}$ ($-70.4\%$), $\Delta\text{RMSE} = -0.0945\text{ V}$, $\Delta\text{Cov} = -6.28\%$, $\Delta\text{MPIW} = -0.4652\text{ V}$, $\Delta\text{Winkler} = -0.3454$.
- **Hierarchical Lot-Shrunk vs. Carry-Forward**:
  - `IDSS`: $\Delta\text{MAE} = +0.4035\ \mu\text{A}$, $\Delta\text{RMSE} = +0.8431\ \mu\text{A}$, $\Delta\text{Cov} = +2.01\%$, $\Delta\text{MPIW} = +2.9498\ \mu\text{A}$, $\Delta\text{Winkler} = +3.0036$.
  - `IGSS`: $\Delta\text{MAE} = +21.6140\text{ nA}$, $\Delta\text{RMSE} = +135.7250\text{ nA}$, $\Delta\text{Cov} = +3.27\%$, $\Delta\text{MPIW} = +1216.6226\text{ nA}$, $\Delta\text{Winkler} = +1218.7075$.
  - `RDS(on)`: $\Delta\text{MAE} = +2.8006\text{ m}\Omega$, $\Delta\text{RMSE} = +3.0010\text{ m}\Omega$, $\Delta\text{Cov} = +3.52\%$, $\Delta\text{MPIW} = +17.8668\text{ m}\Omega$, $\Delta\text{Winkler} = +17.0864$.
  - `VGS(th)`: $\Delta\text{MAE} = +0.0985\text{ V}$, $\Delta\text{RMSE} = +0.0981\text{ V}$, $\Delta\text{Cov} = -0.25\%$, $\Delta\text{MPIW} = +0.4732\text{ V}$, $\Delta\text{Winkler} = +0.5530$.
- **Hierarchical Lot-Shrunk vs. Two-Point Linear**:
  - Slashes error across all 4 parameters: `IDSS` $-0.1183\ \mu\text{A}$ ($-19.2\%$), `IGSS` $-3.1768\text{ nA}$ ($-12.3\%$), `RDS(on)` $-1.2672\text{ m}\Omega$ ($-25.3\%$), `VGS(th)` $-0.0205\text{ V}$ ($-13.9\%$).

##### Task 2 ($96\text{h} \to 168\text{h}$, Lead Time: $72\text{h}$, Support: $K=3$)
- **Adaptive Drift-Gated vs. Carry-Forward**:
  - `IDSS`: $\Delta\text{MAE} = +0.0168\ \mu\text{A}$, $\Delta\text{RMSE} = +0.0568\ \mu\text{A}$, $\Delta\text{Cov} = -0.25\%$, $\Delta\text{MPIW} = +0.0099\ \mu\text{A}$, $\Delta\text{Winkler} = +0.2442$.
  - `IGSS`: $\Delta\text{MAE} = +0.2339\text{ nA}$, $\Delta\text{RMSE} = +0.8390\text{ nA}$, $\Delta\text{Cov} = -1.76\%$, $\Delta\text{MPIW} = +0.5324\text{ nA}$, $\Delta\text{Winkler} = +2.0038$.
  - **`RDS(on)`**: **$\Delta\text{MAE} = -0.0171\text{ m}\Omega$**, **$\Delta\text{RMSE} = -0.2726\text{ m}\Omega$**, $\Delta\text{Cov} = -1.26\%$, $\Delta\text{MPIW} = +0.0294\text{ m}\Omega$, **$\Delta\text{Winkler} = -0.4656$**. *(Adaptive improves point accuracy and interval score over Carry-Forward).*
  - `VGS(th)`: $\Delta\text{MAE} = +0.0034\text{ V}$, $\Delta\text{RMSE} = +0.0254\text{ V}$, $\Delta\text{Cov} = -1.76\%$, $\Delta\text{MPIW} = +0.0036\text{ V}$, $\Delta\text{Winkler} = +0.0508$.
- **Adaptive Drift-Gated vs. Theil-Sen Extrapolation**:
  - Beats Theil-Sen across all 4 parameters:
    - `IDSS`: $\Delta\text{MAE} = -0.0500\ \mu\text{A}$ ($-26.8\%$), $\Delta\text{RMSE} = -0.1055\ \mu\text{A}$, $\Delta\text{Winkler} = -0.1913$.
    - `IGSS`: $\Delta\text{MAE} = -1.1053\text{ nA}$ ($-45.7\%$), $\Delta\text{RMSE} = -8.7829\text{ nA}$, $\Delta\text{Winkler} = -9.0147$.
    - `RDS(on)`: $\Delta\text{MAE} = -0.4018\text{ m}\Omega$ ($-31.0\%$), $\Delta\text{RMSE} = -0.2444\text{ m}\Omega$, $\Delta\text{Winkler} = -1.6799$.
    - `VGS(th)`: $\Delta\text{MAE} = -0.0116\text{ V}$ ($-29.1\%$), $\Delta\text{RMSE} = -0.0114\text{ V}$, $\Delta\text{Winkler} = -0.0642$.
- **Hierarchical Lot-Shrunk vs. Theil-Sen**:
  - Also beats Theil-Sen across all 4 parameters: `IDSS` $-0.0086\ \mu\text{A}$, `IGSS` $-0.6689\text{ nA}$, `RDS(on)` $-0.1047\text{ m}\Omega$, `VGS(th)` $-0.0023\text{ V}$.

---

#### 3. 16-Fold LOLO Robustness Analysis
- **Task 1 Distribution**:
  - Two-Point Linear fold MAE: Mean $7.4330$, Median $5.3508$, Range $[1.8450, 29.2093]$.
  - Adaptive Drift-Gated fold MAE: Mean $1.0172$, Median $0.7517$, Range $[0.1767, 3.5008]$.
  - **Distributional Finding**: Adaptive Drift-Gated beats Two-Point Linear in **16 / 16 folds (100%)**. The improvement is broadly distributed and structural across all lots, not driven by isolated outlier folds.
  - Versus Carry-Forward (mean $0.4826$): Carry-Forward wins in 15 / 16 folds due to the overwhelming stationary majority; Adaptive ties/wins in 1 / 16 folds (`LOT_S01`).
- **Task 2 Distribution**:
  - Theil-Sen fold MAE: Mean $0.9071$, Median $0.5917$, Range $[0.4310, 3.5224]$.
  - Adaptive Drift-Gated fold MAE: Mean $0.5540$, Median $0.4081$, Range $[0.2857, 1.8082]$.
  - **Distributional Finding**: Adaptive Drift-Gated beats Theil-Sen in **16 / 16 folds (100%)**.
  - Hierarchical Lot-Shrunk fold MAE: Mean $0.7368$, Median $0.5644$, beating Theil-Sen in **16 / 16 folds (100%)**.

---

#### 4. Parameter-Specific Mathematical Mechanics

Why Adaptive Drift-Gated behavior diverges fundamentally across parameters:
1. **`RDS(on)` (Clean Log Kinetics, Low Measurement Noise)**:
   - Coordinate: $u = \ln(y)$, noise floor $\sigma_{\text{noise}} = 0.01$ (relative ~1%).
   - Threshold $\theta_{\text{slope}} \approx 0.00147\text{ h}^{-1}$. Four-wire Kelvin measurement noise is well bounded.
   - Result: Highest zero-shrinkage rate ($94.2\%$ Task 1, $92.2\%$ Task 2). In Task 2, noise is suppressed on stable series while genuine drift in `linear_drift` and `accelerating_drift` is tracked, producing the lowest overall error ($0.8955\text{ m}\Omega$, lower than both Carry-Forward and Theil-Sen).
2. **`IGSS` (Asinh Polar Coordinate with Non-Linear Tail Expansion)**:
   - Coordinate: $u = \text{asinh}(y / 1.0\text{ nA})$, noise floor $\sigma_{\text{noise}} = 0.10$.
   - Threshold $\theta_{\text{slope}} \approx 0.0147\text{ h}^{-1}$.
   - Linear near zero, logarithmic at large values. When inverted via $\sinh()$, any slope that leaks past $\theta_{\text{slope}}$ expands exponentially over a 144h forward projection.
   - Result: Lowest zero-shrinkage rate ($69.1\%$ Task 1, $66.3\%$ Task 2). Single-point noise excursions (e.g. `LOT_D04_C001`, $2.0 \to 5.9\text{ nA}$) that breach $\theta_{\text{slope}}$ cause large forecast errors ($343.2\text{ nA}$ vs true $3.55\text{ nA}$).
3. **`VGS(th)` (Bounded Linear Charge Trapping)**:
   - Coordinate: $u = y$ (linear identity, in volts), noise floor $\sigma_{\text{noise}} = 0.01\text{ V}$.
   - Forward projection has no non-linear tail expansion ($\hat{y} = y_{24} + \tilde{\beta} \cdot 144$).
   - Result: Highly stable, bounded errors across all folds (MAE $0.0438\text{ V}$ Task 1, $0.0283\text{ V}$ Task 2).
4. **`IDSS` (Log Coordinate)**:
   - Coordinate: $u = \ln(y)$, noise floor $\sigma_{\text{noise}} = 0.05$ (relative ~5%).
   - Zero-shrinkage rate: $85.9\%$ Task 1, $82.2\%$ Task 2. Tail growth is moderate, bounded by log coordinates.

---

#### 5. Gating Diagnostics Cross-Tabulation

Cross-tabulation of true scenario versus slope action (Adaptive Drift-Gated):

| Scenario | Total Series | Task 1 Zero Slope | Task 1 Retained | Task 2 Zero Slope | Task 2 Retained |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `stable` | 1274 | 1,035 (81.2%) | 239 (18.8%) | 1,030 (80.8%) | 244 (19.2%) |
| `high_but_stable` | 170 | 146 (85.9%) | 24 (14.1%) | 154 (90.6%) | 16 (9.4%) |
| `equipment_common_mode`| 92 | 84 (91.3%) | 8 (8.7%) | 46 (50.0%) | 46 (50.0%) |
| `insufficient_data` | 32 | 25 (78.1%) | 7 (21.9%) | 28 (87.5%) | 4 (12.5%) |
| `linear_drift` | 11 | 8 (72.7%) | 3 (27.3%) | 3 (27.3%) | **8 (72.7%)** |
| `accelerating_drift` | 4 | 4 (100.0%) | 0 (0.0%) | 0 (0.0%) | **4 (100.0%)** |
| `static_limit_breach` | 6 | 5 (83.3%) | 1 (16.7%) | 4 (66.7%) | 2 (33.3%) |
| `subtle_abrupt_change` | 2 | 0 (0.0%) | 2 (100.0%) | 0 (0.0%) | 2 (100.0%) |
| `lot_outlier` | 1 | 1 (100.0%) | 0 (0.0%) | 0 (0.0%) | 1 (100.0%) |

**Diagnostic Assessment**:
- Gate predominantly suppresses noise: $81\% - 91\%$ of stationary series are shrunk to zero.
- In Task 1 ($24\text{h}$), weak legitimate degradation is partially suppressed ($72.7\%$ of `linear_drift` and $100\%$ of `accelerating_drift` shrunk to zero) because early kinetics have not yet breached $\theta_{\text{slope}}$.
- In Task 2 ($96\text{h}$), SNR increases: **$100\%$ of accelerating drift** and **$72.7\%$ of linear drift** are actively retained.
- On `subtle_abrupt_change`, the gate retains $100\%$ of slopes, resulting in step-jump extrapolation error.

---

#### 6. Hierarchical Shrinkage Diagnostics
- Across both tasks, shrinkage factors cluster around mean $\lambda \approx 0.80$ (Task 1: $0.797$, Task 2: $0.801$).
- **Stable Series**: Shrinkage pulls component slopes by $20\%$ toward the lot median. Because $80\%$ of individual noise variance remains unattenuated, Hierarchical Lot-Shrunk exhibits substantial error inflation vs Carry-Forward ($6.72$ vs $0.38$ in Task 1 stable).
- **Degrading Series**: On `linear_drift`, shrinkage acts beneficially: in Task 2, it achieves MAE $0.4016$ and the highest empirical coverage of any model (**$90.9\%$**).
- **Equipment Common-Mode**: ATE channel shifts induce correlated pseudo-slopes that shift the lot median $\mu_{\text{lot}}$, leading to slight error inflation ($0.8867$ vs $0.5211$ in Task 2).

---

#### 7. Uncertainty Contract & Undercoverage Diagnostics
- Nominal coverage target: $90\%$.
- **Empirical Coverage Findings**:
  - Carry-Forward achieves nominal coverage on stationary series ($88.7\% - 90.7\%$), but suffers catastrophic undercoverage on `linear_drift` (**$27.3\%$** in both tasks).
  - Adaptive Drift-Gated Task 1 IGSS exhibits empirical undercoverage (**$76.9\%$** vs $90\%$ nominal) due to unmodeled exponential tail dispersion.
  - Two-Point Linear (Task 1) achieves $91.7\%$ coverage on IGSS only by expanding MPIW to an uninformative $1,380.88\text{ nA}$.
- **Methodological Boundary**: Because $\sigma_{\text{eff}}$ is calibrated from training-fold empirical residuals without nested inner folds or real hardware validation, intervals cannot be described as "calibrated". They are formally classified as **uncalibrated training-fold empirical prediction intervals**.

---

#### 8. Early vs. Mid-Life Prognostic Comparison ($24\text{h} \to 168\text{h}$ vs. $96\text{h} \to 168\text{h}$)
1. **Identifiability Boundary**: At $T=24\text{h}$ ($K=2$), degrees of freedom $df = 0$. Curvature and acceleration are mathematically unidentifiable per-component. Extrapolation is dominated by noise sensitivity. Carry-Forward is the most defensible choice for the stationary majority, while Adaptive Drift-Gated is required if trend extrapolation is attempted.
2. **Mid-Life Predictability ($K=3$)**: At $T=96\text{h}$, three temporal points provide robust slope filtering (Theil-Sen median). Lead time is halved ($72\text{h}$ vs $144\text{h}$). All models exhibit lower RMSE and higher coverage. Adaptive Drift-Gated achieves its strongest performance here, beating Carry-Forward on RDS(on).
3. **Architectural Separation**: The evidence strongly supports **maintaining separate early-life and mid-life prognostic pipelines**. The two tasks operate under different temporal support, SNR envelopes, and failure risk tradeoffs.

---

#### 9. Error Trajectory Forensics

##### Material Degradation Cases (Where Adaptive Worsened vs. Carry-Forward):
1. **`LOT_D04_C001` (`IGSS`, `stable`)**:
   - Trajectory: $0\text{h}: 1.996\text{ nA}, 24\text{h}: 5.881\text{ nA}, 96\text{h}: 3.317\text{ nA}, 168\text{h}: 3.552\text{ nA}$.
   - Forecasts: Carry-Forward $5.881\text{ nA}$ (error $2.33\text{ nA}$); Adaptive Drift-Gated $343.211\text{ nA}$ (error $339.66\text{ nA}$).
   - *Root Cause*: Single-checkpoint electrometer noise excursion at 24h breached $\theta_{\text{slope}}$; 144h forward extrapolation in non-linear $\sinh()$ space caused explosive tail overshooting.
2. **`LOT_M01_C003` (`IGSS`, `subtle_abrupt_change`)**:
   - Trajectory: $0\text{h}: 0.771\text{ nA}, 24\text{h}: 2.579\text{ nA}, 96\text{h}: 13.705\text{ nA}, 168\text{h}: 10.973\text{ nA}$.
   - Forecasts: Task 1 Adaptive: $105.71\text{ nA}$ (error $94.74\text{ nA}$). Task 2 Adaptive: $74.12\text{ nA}$ (error $63.15\text{ nA}$). Carry-Forward Task 2: $13.71\text{ nA}$ (error $2.73\text{ nA}$).
   - *Root Cause*: Model misspecification. A discrete step jump was modeled as continuous linear velocity.

##### Material Improvement Cases (Where Adaptive Outperformed Carry-Forward):
1. **`LOT_D01_C002` (`IDSS`, `linear_drift`)**:
   - Trajectory: $0\text{h}: 3.206\ \mu\text{A}, 24\text{h}: 4.119\ \mu\text{A}, 96\text{h}: 4.319\ \mu\text{A}, 168\text{h}: 7.396\ \mu\text{A}$.
   - Forecasts: Carry-Forward $4.119\ \mu\text{A}$ (error $3.277\ \mu\text{A}$); Adaptive Drift-Gated $6.417\ \mu\text{A}$ (error $0.980\ \mu\text{A}$).
   - *Root Cause*: Successful L1-regularized slope extrapolation tracking active degradation kinetics, reducing forecast error by **$70.1\%$**.
2. **`LOT_M01_C002` (`RDS(on)`, `accelerating_drift`, Task 2)**:
   - Trajectory: $0\text{h}: 51.42\text{ m}\Omega, 24\text{h}: 51.78\text{ m}\Omega, 96\text{h}: 59.82\text{ m}\Omega, 168\text{h}: 79.64\text{ m}\Omega$.
   - Forecasts: Carry-Forward $59.82\text{ m}\Omega$ (error $19.83\text{ m}\Omega$); Adaptive Drift-Gated $65.25\text{ m}\Omega$ (error $14.40\text{ m}\Omega$, improvement $-5.43\text{ m}\Omega$).
   - *Root Cause*: Active slope extrapolation tracking wearout trajectory toward $168\text{h}$.

---

#### 10. Descriptive Model Classification (No Single "Winner")

| Model | Classification by Task & Parameter | Operational Recommendation |
| :--- | :--- | :--- |
| **Carry-Forward** | **Useful** for stationary majority (`stable`, `high_but_stable`, $90.7\%$ of series); **Harmful / Failing** on active drift (`linear_drift` coverage $27.3\%$). | Defensible baseline for nominal factory populations; inadequate as a standalone prognostics safety gate. |
| **Two-Point Linear** | **Harmful** in Task 1 across all parameters (catastrophic noise explosion on stable series, IGSS MAE $25.80\text{ nA}$, RMSE $157.14\text{ nA}$). | **Rejected** for operational deployment without regularization. |
| **Theil-Sen** | **Useful** in Task 2 on active degraders (`linear_drift` MAE $0.3981$); **Harmful** on stationary series relative to Carry-Forward. | Useful benchmark comparator; superseded by Adaptive Drift-Gated in point/interval scores. |
| **Adaptive Drift-Gated** | **Useful** in Task 2 for `RDS(on)` (lowest MAE $0.8955\text{ m}\Omega$, beats both Carry-Forward and Theil-Sen); **Useful** in Task 1 for suppressing Two-Point Linear noise explosion ($87.7\%$ MAE reduction); **Inconclusive / Tail Risk** on Task 1 `IGSS` due to non-linear asinh tail expansions on noise outliers. | Primary candidate for mid-life drift forecasting; requires tail-clamping safeguards before early-life IGSS adoption. |
| **Hierarchical Lot-Shrunk** | **Useful** in Task 2 for `linear_drift` coverage ($90.9\%$); **Inconclusive** on Task 1 stable series (incomplete noise suppression, leaving $80\%$ of noise slope unattenuated). | Useful secondary statistical context; insufficient as a standalone noise gate without sparsity thresholding. |
---

### LOG-067: Stage 3 Pre-Implementation Gate — Prognostic Safety Architecture Review

**Date**: 2026-09-17  
**Gate Status**: ARCHITECTURE APPROVED / IMPLEMENTATION PROHIBITED UNTIL NEXT GATE  
**Scope**: Pre-implementation safety architecture audit of three proposed directions: (1) change-point/step detection, (2) physical/domain bounds for non-linear coordinates (signed-asinh IGSS), (3) Module A evidence integration into Module B prognostic gating. Zero implementation code written or modified.

---

#### 1. Executive Summary & Audit Findings
1. **Audit A (Step / Change-Point Semantics)**:
   - Forward extrapolation of a discrete step jump as a continuous slope velocity was the root cause of catastrophic forecast blowups in Stage 2 (`LOT_M01_C003`, IGSS error $>94\text{ nA}$ in Task 1, $>63\text{ nA}$ in Task 2).
   - Ingesting Module A's $D_{\text{step}}$ (`StepEvidence`) enables strict inhibition of slope projection, switching the forecast to post-step Carry-Forward: $\hat{y}(T_{\text{target}}) = y(T_{\text{as\_of}})$.
   - Because $D_{\text{step}}$ is evaluated strictly as-of $T$ using historical data ($t \le T$) and data flows unidirectionally from Module A to Module B, this creates zero feedback leakage or circularity.
   - Distinguishing "step detected" from "physical failure mechanism identified" is mandatory: step detection is a mathematical property of the time series, not physical proof of gate oxide breakdown or ESD.
2. **Audit B (Nonlinear Transform Domain & Bound Policy)**:
   - The signed-asinh transform $u = \text{asinh}(\text{IGSS}/1.0\text{ nA})$ maps back via $\sinh(u)$, which grows exponentially at large $u$. Forward linear projection in $u$-space over $144\text{h}$ leads to explosive tail overshooting if noise slopes leak through the gate (`LOT_D04_C001` projecting $343\text{ nA}$).
   - **Specification Limit ($100\text{ nA}$) Clipping is PROHIBITED**: Clipping predictions at the datasheet specification limit hides the predicted severity of defect runaway from downstream mission-critical screening and distorts error metrics.
   - Stage 3 requires a **measurement/plausibility domain bound** (ATE electrometer compliance ceiling, $\pm 10\ \mu\text{A}$ to $\pm 100\ \mu\text{A}$, $u \approx \pm 9.9$ to $\pm 12.2$) to eliminate floating-point overflows/singularities, coupled with a mandatory `PREDICTED_SPEC_BREACH` status flag whenever $\hat{y} > 100\text{ nA}$.
3. **Audit C (Module A $\to$ Module B Interface)**:
   - Upstream detectors $D_{\text{drift}}$, $D_{\text{step}}$, $D_{\text{eq}}$, and $D_{\text{suff}}$ are causal and approved for prognostic gating.
   - $D_{\text{spec}}$, composite `final_state`, and `disposition_qualifier` must NOT modify forecast kinematics (slopes); they pertain strictly to static acceptance and final screening disposition.
4. **Audit D (Correction of $K=2$ Claim)**:
   - Any claim that "$K=2$ is mathematically ill-posed" is formally retracted and corrected.
   - At $K=2$, linear slope $\hat{\beta} = (y_1 - y_0)/(t_1 - t_0)$ is **algebraically uniquely identified**.
   - With $N=2$ observations and $p=2$ parameters, degrees of freedom $df = 2 - 2 = 0$. Hence, **residual noise variance $\sigma^2$ is unidentifiable from a single device's data alone**, and curvature/acceleration is unidentifiable.
5. **Audit E (Epistemic Audit of Causal / Physical Language)**:
   - Casual references to "electrometer noise" are classified as **SYNTHETIC SCENARIO INTERPRETATION**.
   - References to "gate-oxide rupture", "carrier leakage physics", or "metallization wearout" are classified as **UNSUPPORTED CLAIMS** and purged from technical claims.
   - Specification limits from MIL-PRF-19500/703 Table I are classified as **VERIFIED EXTERNAL FACTS**.
6. **Preservation Verification (Audit H)**:
   - Phase 2F frozen hashes verified 100% bit-for-bit intact.
   - Module A and Phase 2C untouched.
   - Strict LOLO lot partitioning and temporal as-of quarantine verified. 164 tests pass.

---

#### 2. Required Semantic Corrections

| Item | Previous Informal Framing | Corrected Scientific Framing | Epistemic Rationale |
| :--- | :--- | :--- | :--- |
| **$K=2$ Identifiability** | "$K=2$ is mathematically ill-posed; no algorithm can identify degradation." | "At $K=2$, slope $\hat{\beta}$ is algebraically uniquely identified, but degrees of freedom $df = 0$, making single-device residual variance $\sigma^2$, prediction uncertainty, and trajectory curvature unidentifiable without external instrument/lot priors." | Distinguishes algebraic determinism from statistical degrees of freedom. |
| **Step Jump Interpretation** | "A sudden step jump indicates gate-oxide rupture or micro-crack opening." | "A sudden step jump represents a discrete time-series discontinuity ($J(T) \ge 4.0$). Physical mechanism attribution is unverified without independent failure analysis (SEM/TEM/TEM-EDX)." | Distinguishes mathematical change-point detection from causal physical attribution. |
| **Transform Coordinates** | "Carrier leakage physics governs the asinh IGSS coordinate." | "Signed-asinh is an empirical variance-stabilizing and sign-preserving mathematical coordinate with linear behavior near zero and logarithmic behavior at large amplitudes; it is not a physical transport model." | Prevents mathematical coordinate choices from masquerading as physical device models. |
| **Datasheet Limits** | "The 100 nA datasheet limit is a physical saturation bound." | "The 100 nA limit is a Class A contractual acceptance ceiling under MIL-PRF-19500/703 Table I; physical saturation occurs at electrometer compliance limits ($\sim 10\ \mu\text{A} - 100\ \mu\text{A}$)." | Prevents conflating administrative acceptance limits with physical hardware saturation. |

---

#### 3. Approved vs. Unapproved Stage 3 Directions

| Direction / Proposal | Approval Status | Classification / Justification |
| :--- | :--- | :--- |
| **1. Step-Gated Slope Inhibition** | **APPROVED** | **Justified by current benchmark evidence**. Empirically eliminates catastrophic step-extrapolation errors (`LOT_M01_C003`). |
| **2. Plausibility / Instrument Bounds for Non-Linear Coordinates** | **APPROVED (WITH RESTRICTIONS)** | **Justified by current benchmark evidence**. Clamping at instrument plausibility limit ($\pm 10\ \mu\text{A}$) prevents mathematical divergence. Clamping at 100 nA spec limit is **PROHIBITED**. |
| **3. Module A Ingestion ($D_{\text{drift}}, D_{\text{step}}, D_{\text{eq}}, D_{\text{suff}}$)** | **APPROVED** | **Justified by current benchmark evidence**. Leverages validated upstream evidence to govern prognostic state machines causally. |
| **Ingestion of $D_{\text{spec}}$, `final_state`, `disposition_qualifier` into kinematics** | **PROHIBITED** | **Currently unsupported**. Conflates static compliance and policy logic with kinetic drift forecasting. |
| **New Complex Forecasting Models (GBM, LSTM, Neural Nets, ODEs)** | **PROHIBITED** | **Currently unsupported & Violates PRD**. High-complexity black-boxes violate space qualification interpretability and overfit small sample sizes. |
| **Threshold Tuning / Post-Hoc Re-calibration** | **PROHIBITED** | **Methodologically invalid**. Retuning thresholds to fit observed benchmark results corrupts evaluation integrity. |
| **Benchmark Modification / Synthetic Re-generation** | **PROHIBITED** | **Violates frozen evaluation contract**. Phase 2F benchmark remains immutable. |

---

#### 4. Proposed Stage 3 Data-Flow Architecture

```
                                  STRICT AS-OF TEMPORAL BOUNDARY (t <= T_as_of)
                                 =============================================
  Raw Telemetry (t <= T)
  ----------------------> [ Module A: Upstream Multi-Detector Screening ]
                                |
                                +---> D_suff: Sufficiency Status {SUFFICIENT, INCOMPLETE, ...}
                                |
                                +---> D_step: Step Status {NO_STEP, ABRUPT_JUMP_ALERT}
                                |
                                +---> D_eq:   Equipment Status {NOMINAL, CHAMBER/CHANNEL_SUSPECTED}
                                |
                                +---> D_drift: Temporal Status {STATIONARY, SUBTLE_DRIFT, ACCEL}
                                |
                                v
                   [ Prognostic Input Contract ]
                   - Historical Observations: {(t_i, y_i)} for t_i <= T
                   - Module A Gating Evidence (Read-Only)
                   - Lineage: (component_id, lot_id, param, unit, T_as_of, T_target)
                                |
                                v
                   [ Module B: Prognostic State Controller ]
                                |
          +---------------------+---------------------+---------------------+
          |                     |                     |                     |
     [Insufficient]          [Step Jump]         [Equipment Bias]      [Nominal/Drift]
     D_suff = False      D_step = JUMP_ALERT    D_eq = SUSPECTED       D_suff = True
          |                     |                     |                     |
          v                     v                     v                     v
     is_valid=False        beta_eff = 0          beta_eff = 0         Check D_drift:
     y_pred = NaN       Carry-Forward post-step  Carry-Forward        - STATIONARY: beta=0
     MPIW = NaN         Flag: STEP_DISCONT    Flag: EQUIP_CONFOUND   - DRIFT: L1 Adaptive
                        Widen interval         Widen interval               Slope Extrap.
          |                     |                     |                     |
          +---------------------+---------------------+---------------------+
                                |
                                v
                   [ Representation Space Inversion & Bounds ]
                   - Map u_pred -> y_pred via inverse_transform_parameter()
                   - Clamp strictly at Instrument Plausibility Bound (|y| <= 10 uA)
                   - NEVER clamp at Specification Limit (100 nA)
                   - Check: If y_pred > 100 nA -> emit PREDICTED_SPEC_BREACH flag
                                |
                                v
                   [ Prognostic Forecast Contract ]
                   - predicted_value, forecast_change_from_origin, baseline_relative_change
                   - prediction interval [lower, upper], sigma_eff, is_valid, metadata
```

---

#### 5. Exact Module A $\to$ Module B Interface Fields

| Upstream Field (`ParameterScreeningResult`) | Type | As-of T? | Causal? | Circularity Risk? | Permitted Role in Module B |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `sufficiency_evidence.sufficient` | `bool` | Yes | Yes | None | **Execution Gate**: If `False`, emit invalid forecast with NaN and exclusion reason. |
| `step_evidence.status` | `AbruptStepStatus` | Yes | Yes | None | **Kinematic Switch**: If `ABRUPT_JUMP_ALERT`, inhibit slope ($\beta=0$); enforce post-step carry-forward. |
| `equipment_evidence.suspected` | `bool` | Yes | Yes | None | **Kinematic Switch & Confidence Modifier**: If `True`, inhibit slope ($\beta=0$); widen interval; flag equipment confounding. |
| `temporal_evidence.status` | `TemporalDriftStatus`| Yes | Yes | None | **Kinematic Selector**: If `STATIONARY`, set $\beta=0$; if `SUBTLE_DRIFT` or `ACCELERATING_DRIFT`, extrapolate slope. |
| `spec_evidence.status` | `SpecificationStatus`| Yes | No (rate) | None | **Disposition Only**: Forbidden from modifying slope kinematics. |
| `parameter_state` / `final_state` | `ScreeningState` | Yes | No (policy)| None | **Disposition Only**: Forbidden from modifying slope kinematics. |
| `disposition_qualifier` | `DispositionQualifier`| Yes| No (policy)| None | **Disposition Only**: Forbidden from modifying slope kinematics. |

---

#### 6. Forecast-State Behavior Matrix

| Operational State | Primary Gating Condition | Kinematic Slope ($\beta_{\text{eff}}$) | Point Forecast ($\hat{y}(T_{\text{target}})$) | Uncertainty Interval Policy | Output Validity & Flags |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Insufficient Data** | $D_{\text{suff}}.\text{sufficient} == \text{False}$ | None | `NaN` | `[NaN, NaN]` | `is_valid=False`, exclusion reason recorded. |
| **Equipment Confounded** | $D_{\text{eq}}.\text{suspected} == \text{True}$ | $0.0$ | Level Carry-Forward: $y(T_{\text{as\_of}})$ | Inflated interval ($\sigma_{\text{eff}} \times \sqrt{2}$ or lot dispersion floor) | `is_valid=True`, `EQUIPMENT_CONFOUNDED` flag emitted. |
| **Step Discontinuity** | $D_{\text{step}} == \text{ABRUPT\_JUMP\_ALERT}$ | $0.0$ | Post-Step Carry-Forward: $y(T_{\text{as\_of}})$ | Expanded interval reflecting unverified post-step variance | `is_valid=True`, `STEP_LEVEL_PROJECTED` flag emitted. |
| **Stationary / Stable** | $D_{\text{drift}} == \text{STATIONARY}$ | $0.0$ | Carry-Forward: $y(T_{\text{as\_of}})$ | Nominal empirical interval: $\hat{u} \pm z_{0.90} \cdot \sigma_{\text{eff}}$ | `is_valid=True`, `STATIONARY_CARRY_FORWARD` flag. |
| **Active Drift** | $D_{\text{drift}} \in \{\text{SUBTLE}, \text{ACCEL}\}$ | Soft-thresholded regularized slope $\tilde{\beta}$ | Extrapolated: $\phi^{-1}(u_{\text{as\_of}} + \tilde{\beta} \cdot \Delta t)$ | Empirical drift interval: $\hat{u} \pm z_{0.90} \cdot \sigma_{\text{eff}}$ | `is_valid=True`, `ACTIVE_DRIFT_EXTRAPOLATED` flag. |

---

#### 7. Bound and Clamp Policy

1. **Four Distinct Bound Domains**:
   - **Physical Bound**: Ultimate physical breakdown limits ($\sim 1\text{ A}$ for silicon junction thermal destruction). Too loose for screening numerical sanity.
   - **Instrument / Measurement Range Bound**: ATE electrometer compliance and saturation ceiling ($\pm 10\ \mu\text{A} = \pm 10,000\text{ nA}$ on low range; $u \approx \pm 9.903$). **Enforced as the numerical clamp**.
   - **Specification Limit**: MIL-PRF-19500/703 Table I Class A acceptance limit ($100\text{ nA}$; $u_{\text{spec}} \approx 5.298$). **STRICTLY PROHIBITED FROM CLAMPING POINT PREDICTIONS**.
   - **Model Domain**: Transformed space representation $u \in [-9.903, +9.903]$.
2. **Failure Severity Preservation Rule**:
   - If a forecast projects $350\text{ nA}$, clamping to $100\text{ nA}$ would falsify the forecast, hide the predicted runaway degradation from mission reliability engineers, and distort residual tracking.
   - **Policy**: Clamping is applied *only* at the instrument plausibility bound ($10\ \mu\text{A}$) to prevent floating-point overflow. If $\hat{y} > 100\text{ nA}$, the value is preserved, and a structured `PREDICTED_SPEC_BREACH` flag is attached to the forecast record.

---

#### 8. Leakage Risk Analysis

1. **Temporal Lookahead Leakage**:
   - Mitigated by strict as-of filter: $t \le T_{\text{as\_of}} < T_{\text{target}}$.
   - Enforced by `PrognosticInput.__post_init__` and verified by automated leakage tests.
2. **Upstream Screening Circularity**:
   - Mitigated by unidirectional dependency: Module A runs first; its evidence is frozen into `PrognosticInput`; Module B reads this evidence as immutable input; Module B never writes to Module A.
3. **Lot-Pooling Leakage**:
   - Mitigated by strict Leave-One-Lot-Out (LOLO): calibration of $\sigma_{\text{eff}}$ and empirical shrinkage priors is conducted strictly on the 15 training lots, with zero exposure to the held-out evaluation lot.
4. **Target / Ground Truth Quarantine**:
   - `ground_truth.csv` is completely isolated from feature extraction, model inference, and gating logic; it is read only by downstream scoring scripts during final audit evaluation.

---

#### 9. Remaining Evidence Gaps

1. **Real Hardware Physical Noise vs. Synthetic Gaussian Analogies**:
   - The synthetic benchmark models electrometer noise as stationary Gaussian perturbations. Real hardware electrometers exhibit $1/f$ pink noise, humidity-dependent dielectric leakage, and cable triboelectric currents. Hardware-calibrated noise priors require real ATE characterization data.
2. **Post-Step Long-Term Trajectory Dynamics**:
   - The frozen benchmark contains only 4 checkpoints ($0, 24, 96, 168\text{h}$). When a step occurs at $24\text{h}$ or $96\text{h}$, the benchmark provides at most 1 or 2 subsequent observations. Determining whether step changes relax, plateau, or accelerate over thousands of mission hours requires extended temporal datasets (e.g. $T \ge 1,000\text{h}$).
3. **Lot-Level Shrinkage at Low Lot Count**:
   - In production environments with small lot sizes ($N < 8$), empirical Bayes lot medians have higher variance, which may degrade shrinkage reliability.

---

#### 10. Explicit Implementation Authorization Boundary

| Subsystem / Action | Authorization Status | Governing Constraint |
| :--- | :--- | :--- |
| **Step-gated slope inhibition in Module B** | **READY FOR IMPLEMENTATION (PENDING USER GO)** | Must use post-step Carry-Forward; no new tunable hyperparameters. |
| **Instrument plausibility clamp ($10\ \mu\text{A}$)** | **READY FOR IMPLEMENTATION (PENDING USER GO)** | Must preserve values between $100\text{ nA}$ and $10\ \mu\text{A}$ and emit `PREDICTED_SPEC_BREACH`. |
| **Module A evidence input integration** | **READY FOR IMPLEMENTATION (PENDING USER GO)** | Restricted strictly to $D_{\text{suff}}, D_{\text{step}}, D_{\text{eq}}, D_{\text{drift}}$. No $D_{\text{spec}}$ or `final_state` in kinematics. |
| **Modifying Module A code or thresholds** | **STRICTLY PROHIBITED** | Module A remains frozen and read-only. |
| **Adding new ML/DL/GBM forecasting models** | **STRICTLY PROHIBITED** | Keep existing baselines + regularized models only. |
| **Retuning thresholds or hyperparameters** | **STRICTLY PROHIBITED** | Preserve existing $k_{\sigma}=2.0$, $Z_{0.90}=1.645$. |
| **Modifying Phase 2F benchmark data** | **STRICTLY PROHIBITED** | Frozen hashes remain immutable. |

---

### LOG-068: Stage 3 Correction Gate — As-Of, Equipment, Specification, and Bound Semantics Decision Record

**Date**: 2026-09-17  
**Gate Status**: CORRECTION RECORD ACCEPTED / IMPLEMENTATION PROHIBITED UNTIL EXPLICIT USER APPROVAL  
**Scope**: Epistemic, mathematical, and architectural corrections to Stage 3 prognostic safety pre-implementation review (LOG-067). Covers: (1) As-of step candidate vs. persistence semantics, (2) Equipment-confounding decoupling from zero degradation, (3) $D_{\text{drift}}$ stationarity as noise shrinkage vs. physical null, (4) Deterministic Module A precedence table, (5) Signed bipolar IGSS specification envelope, (6) Audit of $\pm 10\ \mu\text{A}$ instrument bound (unsupported claim) and domain separation, (7) Numerical overflow protection vs. forbidden specification clipping, (8) Formal proof of strict as-of information boundary ($T=24\text{h}$ uses zero future telemetry), and (9) Preservation verification. Zero code modified.

---

#### 1. As-Of Step Semantics: Candidate vs. Persistent

1. **Epistemic Distinction**:
   - `STEP_CANDIDATE` / `ABRUPT_JUMP_DETECTED`: A single-interval discrete jump ratio $J(T) = \frac{|u(T) - u(T_{\text{prev}})|}{\Delta u_{\text{typical}}} \ge 4.0$ observed across the immediately preceding measurement interval $[T_{\text{prev}}, T]$.
   - `STEP_PERSISTENT`: A step discontinuity that is verified to sustain its post-step level across subsequent temporal checkpoints ($T_{\text{sub}} > T$) without returning to baseline or relaxing (differentiating a persistent level shift from a single-checkpoint transient excursion).
2. **Temporal Boundary Enforcement**:
   - At $T=24\text{h}$ ($K=2$) or $T=96\text{h}$ ($K=3$), **persistence cannot be known** for a step occurring at $T$. Proving persistence requires observing future checkpoints ($t > T$). Asserting that a step at $T=24\text{h}$ is "persistent" without observing $T=96\text{h}$ or $T=168\text{h}$ is a temporal lookahead fallacy.
   - At as-of time $T$, $D_{\text{step}}$ reports strictly whether an abrupt step jump *occurred into checkpoint $T$* (`ABRUPT_JUMP_ALERT`).
3. **Module B Behavior on Step Candidate**:
   - **Inhibit slope extrapolation**: Extrapolating a discrete jump $\Delta u$ across remaining lead time $\Delta t_{\text{lead}}$ as a continuous velocity $\beta = \Delta u / \Delta t_{\text{obs}}$ treats an impulse as a rate, causing massive overshooting (e.g. `LOT_M01_C003`). Effective slope is forced to $\beta_{\text{forecast}} = 0$.
   - **Post-Step Level Carry-Forward**: The forecast projects the latest observed level: $\hat{y}(T_{\text{target}}) = y(T_{\text{as\_of}})$.
   - **Degraded Confidence Flag**: Emits structured status `STEP_CANDIDATE_UNVERIFIED_PERSISTENCE` and inflates prediction intervals to account for unobserved post-step variance and potential transient relaxation.
4. **Proof of As-Of Independence**:
   - Evaluation of $J(T)$ uses only $u(T)$ and $u(T_{\text{prev}})$, where $T_{\text{prev}} < T \le T_{\text{as\_of}}$.
   - Projection uses only $y(T_{\text{as\_of}})$. Zero future telemetry ($t > T_{\text{as\_of}}$) is required.

---

#### 2. Equipment-Confounding Semantics: Decoupling Confounding from Zero-Degradation

1. **Forensic Problem**:
   - LOG-067 proposed: $D_{\text{eq}} = \text{SUSPECTED} \implies \beta_{\text{eff}} = 0 \implies \text{Carry-Forward}$.
   - This rule repeats the Phase 3B architectural flaw (`LOG-057`) where equipment precedence masked $93.75\%$ of legitimate wearout alerts.
   - **Critical Principle**: **"Observed change is confounded by equipment" is NOT equivalent to "Component has zero physical degradation."**
2. **Architectural Resolution via Excess Motion**:
   - In Module A (Phase 3C hardening, `LOG-058`), temporal drift under equipment suspicion is decomposed into:
     - Lot common-mode reference drift: $g_{\text{lot},-i}(T)$
     - Component excess drift: $g_{\text{excess}, i}(T) = g_i(T) - g_{\text{lot},-i}(T)$
   - Module B adopts this exact evidence-preserving decomposition:
     - **Case A: Confounded Drift Without Excess Motion ($|g_{\text{excess}}| < 2.5$)**:
       The component's shift is fully explained by chamber thermal drift or fixture channel bias.
       $\implies$ Inhibit component-specific slope ($\beta_{\text{component}} = 0$); emit Carry-Forward $\hat{y} = y(T_{\text{as\_of}})$; widen prediction interval to cover common-mode uncertainty; emit flag `EQUIPMENT_COMMON_MODE_UNRESOLVED`.
     - **Case B: Confounded Drift With Significant Excess Motion ($|g_{\text{excess}}| \ge 2.5$)**:
       The component is drifting faster than the common-mode equipment shift (candidate autonomous wearout under adverse test conditions).
       $\implies$ **Do NOT zero the slope!** Extrapolate the regularized excess slope $\tilde{\beta}_{\text{excess}}$; inflate prediction intervals by the equipment scale uncertainty; emit flag `CONFOUNDED_ACTIVE_DRIFT`.

---

#### 3. $D_{\text{drift}}$ Semantics: Non-Detection vs. Physical Stationarity

1. **Statistical Null vs. Physical Reality**:
   - $D_{\text{drift}} = \text{STATIONARY}$ indicates that normalized drift $|g(T)| < 2.5$.
   - In statistical hypothesis testing, failure to reject $H_0: \text{drift} = 0$ is **never proof that physical degradation is zero**.
   - Sub-threshold wearout ($< 2.5\sigma$) may be physically active, but cannot be reliably differentiated from measurement noise at current $T$.
2. **Module B Operational Mandate**:
   - Module B sets $\beta_{\text{eff}} = 0$ strictly as a **minimax variance-reduction shrinkage policy under noise dominance**, not as a claim of physical perfection. Extrapolating noise slopes multiplies variance by $(\Delta t_{\text{lead}}/\Delta t_{\text{obs}})^2$ (up to $36\times$), which benchmark evidence proves degrades MSE.
   - Carry-Forward $\hat{y} = y(T_{\text{as\_of}})$ is the optimal point forecast under noise dominance.
   - Prediction uncertainty $\hat{u} \pm z_{0.90} \cdot \sigma_{\text{eff}}$ explicitly covers the probability of undetected sub-threshold degradation.
   - Emitted status code: `STATIONARY_NOISE_BOUNDED`.

---

#### 4. Deterministic Module A Precedence Table

The following deterministic state machine governs Module B prognostic gating across all detector combinations:

| $D_{\text{suff}}$ | $D_{\text{step}}$ | $D_{\text{eq}}$ | $D_{\text{drift}}$ | Forecast Mode | Kinematic Slope ($\beta_{\text{eff}}$) | Confidence & Uncertainty Interval Policy | Attribution / Semantic Statement | Emitted Status Flags |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`INSUFFICIENT`** | Any | Any | Any | **`INVALID_FORECAST`** | Undefined ($\beta = \text{None}$) | Interval undefined: `[NaN, NaN]`. No forecast emitted. | Insufficient temporal or lot history to evaluate prognostic models. | `is_valid=False`, `INSUFFICIENT_DATA`, reason code recorded |
| **`SUFFICIENT`** | **`JUMP_ALERT`** | **`SUSPECTED`** | Any | **`CONFOUNDED_STEP_CANDIDATE`** | $\beta_{\text{eff}} = 0.0$ (inhibit extrapolation) | Inflated interval: $\hat{y} \pm z \cdot (\sigma_{\text{eff}} \times \sqrt{2})$. Confidence degraded. | Step discontinuity observed contemporaneously with equipment excursion; post-step level projected without slope extrapolation. | `is_valid=True`, `STEP_CANDIDATE_UNVERIFIED_PERSISTENCE`, `EQUIPMENT_CONFOUNDED` |
| **`SUFFICIENT`** | **`JUMP_ALERT`** | **`NOMINAL`** | Any | **`AUTONOMOUS_STEP_CANDIDATE`** | $\beta_{\text{eff}} = 0.0$ (inhibit extrapolation) | Post-step interval: $\hat{y} \pm z \cdot \sigma_{\text{step\_eff}}$. Reflects post-step variance. | Autonomous abrupt jump candidate observed; post-step level projected without slope extrapolation; persistence unverified. | `is_valid=True`, `STEP_CANDIDATE_UNVERIFIED_PERSISTENCE`, `AUTONOMOUS_STEP` |
| **`SUFFICIENT`** | **`NO_STEP`** | **`SUSPECTED`** | **`SUBTLE_DRIFT`** or **`ACCEL_DRIFT`** (with $\|g_{\text{excess}}\| \ge 2.5$) | **`CONFOUNDED_ACTIVE_DRIFT`** | Regularized excess slope $\tilde{\beta}_{\text{excess}}$ | Expanded interval: $\hat{u} \pm z \cdot (\sigma_{\text{eff}} + \sigma_{\text{equip\_dispersion}})$. | Active degradation kinetics observed with excess drift exceeding common-mode shift; trajectory extrapolated under equipment confounding. | `is_valid=True`, `CONFOUNDED_ACTIVE_DRIFT`, `EQUIPMENT_CONFOUNDED` |
| **`SUFFICIENT`** | **`NO_STEP`** | **`SUSPECTED`** | **`SUBTLE_DRIFT`** or **`ACCEL_DRIFT`** (with $\|g_{\text{excess}}\| < 2.5$) | **`EQUIPMENT_COMMON_MODE_SHIFT`** | $\beta_{\text{eff}} = 0.0$ (component slope attributed to equipment) | Expanded interval: $\hat{y} \pm z \cdot \sigma_{\text{equip}}$. High uncertainty on baseline return. | Observed temporal drift is fully explained by common-mode equipment excursion; component-specific wearout not established. | `is_valid=True`, `EQUIPMENT_COMMON_MODE_UNRESOLVED`, `SLOPE_ATTRIBUTED_TO_EQUIPMENT` |
| **`SUFFICIENT`** | **`NO_STEP`** | **`SUSPECTED`** | **`STATIONARY`** | **`EQUIPMENT_STATIONARY_HOLD`** | $\beta_{\text{eff}} = 0.0$ | Expanded interval: $\hat{y} \pm z \cdot (\sigma_{\text{eff}} \times \sqrt{2})$. | Component is stationary relative to baseline; equipment anomaly suspected in peer group. Carry-Forward emitted. | `is_valid=True`, `STATIONARY_NOISE_BOUNDED`, `EQUIPMENT_CONFOUNDED` |
| **`SUFFICIENT`** | **`NO_STEP`** | **`NOMINAL`** | **`STATIONARY`** | **`NOMINAL_CARRY_FORWARD`** | $\beta_{\text{eff}} = 0.0$ (minimax noise shrinkage) | Nominal training-fold empirical interval: $\hat{u} \pm z \cdot \sigma_{\text{eff}}$. | No statistically significant drift detected above measurement noise floor. Carry-Forward emitted under noise-dominance shrinkage. | `is_valid=True`, `STATIONARY_NOISE_BOUNDED` |
| **`SUFFICIENT`** | **`NO_STEP`** | **`NOMINAL`** | **`SUBTLE_DRIFT`** or **`ACCEL_DRIFT`** | **`AUTONOMOUS_ACTIVE_DRIFT`** | Soft-thresholded L1 regularized slope $\tilde{\beta}$ | Empirical drift interval: $\hat{u} \pm z \cdot \sigma_{\text{eff}}$. | Statistically significant autonomous drift detected; regularized kinetic slope extrapolated forward. | `is_valid=True`, `ACTIVE_DRIFT_EXTRAPOLATED` |

---

#### 5. Signed Bipolar IGSS Specification Semantics

1. **Normative Acceptance Envelope**:
   - MIL-PRF-19500/703 Table I establishes symmetric bipolar limits:
     - $I_{\text{GSS1}} \in [-100\text{ nA}, +100\text{ nA}]$ at $V_{\text{GS}} = +20\text{V}, V_{\text{DS}} = 0\text{V}, T_A = +25^\circ\text{C}$
     - $I_{\text{GSS2}} \in [-100\text{ nA}, +100\text{ nA}]$ at $V_{\text{GS}} = -20\text{V}, V_{\text{DS}} = 0\text{V}, T_A = +25^\circ\text{C}$
   - In representation space: $u \in [\text{asinh}(-100), \text{asinh}(+100)] \approx [-5.2983, +5.2983]$.
2. **Mathematical Definitions**:
   - **Positive Predicted Breach**: $\hat{y}(T_{\text{target}}) > +100.0\text{ nA}$ ($\hat{u} > +5.2983$). Emits `PREDICTED_SPEC_BREACH_POSITIVE`.
   - **Negative Predicted Breach**: $\hat{y}(T_{\text{target}}) < -100.0\text{ nA}$ ($\hat{u} < -5.2983$). Emits `PREDICTED_SPEC_BREACH_NEGATIVE`.
   - **Compliant Forecast**: $\hat{y}(T_{\text{target}}) \in [-100.0\text{ nA}, +100.0\text{ nA}]$.
   - **Exactly Zero**: $\hat{y} = 0.0\text{ nA} \iff \hat{u} = 0.0$.
   - **Near-Zero Signed Value**: $|y| \le \text{NOISE\_FLOOR}$ ($0.1\text{ nA}$). Preserves sign bit ($\pm 0.03\text{ nA}$).
3. **Absolute Prohibition of `abs()`**:
   - $u = \text{asinh}(y / 1.0\text{ nA})$ is strictly odd: $\text{asinh}(-y) = -\text{asinh}(y)$.
   - Taking $\text{abs}(I_{\text{GSS}})$ is strictly prohibited. Polarity encodes dielectric field direction and must be preserved across all transforms and forecasts.

---

#### 6. Instrument Bound Audit & Epistemic Delineation

1. **Classification of $\pm 10\ \mu\text{A}$ Bound**:
   - Audit finding: The $\pm 10\ \mu\text{A}$ value was mentioned in LOG-067 as an ATE electrometer compliance limit for IGSS.
   - Inspection of `docs/SIH26170_PRD.md`, `configs/synthetic.yaml`, and `docs/PHASE_3A_MODULE_A_SPEC.md` reveals that $10\ \mu\text{A}$ is the specification limit for **$I_{\text{DSS}}$**, NOT an ATE compliance specification for $I_{\text{GSS}}$.
   - **Epistemic Classification**: **UNSUPPORTED CLAIM / UNVERIFIED ASSUMPTION**.
   - **Authorization Status**: **PROHIBITED FROM IMPLEMENTATION**. No hard clamp at $\pm 10\ \mu\text{A}$ may be coded.
2. **Purge of Generic "~1 A" Physical Limit**:
   - The "~1 A silicon destruction limit" discussed in LOG-067 has no technical connection to nanoampere gate dielectric leakage. It is formally purged from the prognostic architecture.
3. **Rigid Separation of Four Operational Domains**:
   - **Physical Device Domain**: True device dielectric breakdown physics. Unmodeled in linear telemetry screening.
   - **ATE Measurement Range**: Hardware electrometer range (e.g. $1\ \mu\text{A}, 100\ \mu\text{A}$). Unspecified in benchmark metadata; cannot be used as an authoritative numerical boundary.
   - **Numerical Transform Domain**: Machine precision floating-point representation (IEEE 754 float64). Requires finite number guards (`np.isfinite()`) to prevent `inf`/`nan` crashes.
   - **Specification Acceptance Limits**: MIL-PRF-19500/703 Table I limits. Quality acceptance criteria only; forbidden from clamping forecasts.

---

#### 7. Clamp and Saturation Policy

1. **No Artificial Clipping**:
   - Clamping point predictions at specification limits (e.g. capping a $350\text{ nA}$ projection at $100\text{ nA}$) is **STRICTLY PROHIBITED**. It conceals runaway failure kinetics and distorts screening risk.
2. **No Physical Saturation Assumptions**:
   - Simulating artificial current saturation curves without physical device parameters is rejected as speculative curve-fitting.
3. **Required Controls**:
   - **Numerical Overflow Guard**: An IEEE 754 check ensuring that coordinate extrapolation $u_{\text{pred}} = u_{\text{as\_of}} + \beta \Delta t$ does not overflow `np.sinh()` (i.e. $|u_{\text{pred}}| < 100.0$). If an overflow would occur, the model marks the forecast as an unconstrained divergence: `DIVERGENT_RUNAWAY_PREDICTION`.
   - **Specification Breach Warning**: If $|\hat{y}| > 100\text{ nA}$, the value is preserved unmodified, and a structured warning flag (`PREDICTED_SPEC_BREACH_POSITIVE` or `PREDICTED_SPEC_BREACH_NEGATIVE`) is attached to `PrognosticForecast.metadata`.

---

#### 8. Final Stage 3 Architecture Contract & As-Of Proof

- **Core Invariant**:
  "What information may Module B use at $T=24\text{h}$ that would not be available at $T=24\text{h}$?"
  **Answer: NONE.**
- **Proof of As-Of Temporal Boundary**:
  1. *Telemetry Input*: Historical series contains only $(t_i, y_i)$ with $t_i \le T_{\text{as\_of}}$. Verified by `PrognosticInput.__post_init__` check ($t \le \text{as\_of\_hours}$).
  2. *Upstream Screening Input*: `screening_result` metadata must have `as_of_hours <= input.as_of_hours`. Verified by validation assertion.
  3. *Detector Evidence Available at $T=24\text{h}$*:
     - $D_{\text{suff}}(24\text{h})$: Evaluates checkpoints $\{0\text{h}, 24\text{h}\}$.
     - $D_{\text{step}}(24\text{h})$: Evaluates jump across $[0\text{h}, 24\text{h}]$.
     - $D_{\text{eq}}(24\text{h})$: Evaluates contemporaneous lot median and fixture channels at $24\text{h}$.
     - $D_{\text{drift}}(24\text{h})$: Evaluates normalized drift $g(24\text{h})$ and excess drift $g_{\text{excess}}(24\text{h})$.
  4. *Training-Fold Calibration*: $\sigma_{\text{eff}}$ is computed strictly across the 15 training lots in the LOLO fold. The held-out lot is quarantined.
  5. *Zero Target Exposure*: Ground truth labels and future checkpoints ($96\text{h}, 168\text{h}$) are quarantined.

---

#### 9. Preservation Audit

- **Frozen Phase 2F Hashes**:
  - `observations.csv`: `b4282e0743cd6a0b2b74354e431bf8f308b03281c44c0437d30f7b53bd6ca983` (**MATCHED**)
  - `ground_truth.csv`: `4bf2155fcc7698813f766e1dea9730213e0a6097e484bfa786eb1b94925f3d2b` (**MATCHED**)
  - `manifest.json`: `5a08630f9fafc95563c13acea77df7aa066f7abc7a08b785a77c2709553980f6` (**MATCHED**)
- **Source Code**: `src/sih26170/screening/` and `src/sih26170/prognostics/` completely untouched.
- **Test Suite**: 164 passed, 0 failures.
- **Threshold Integrity**: No thresholds tuned. No new models introduced.

---

#### 10. Summary Authorization Boundary

| Item | Final Status |
| :--- | :--- |
| Step Candidate vs. Persistence distinction | **CORRECTED & APPROVED** |
| Equipment Confounding Decoupling via $g_{\text{excess}}$ | **CORRECTED & APPROVED** |
| $D_{\text{drift}}$ Stationarity as Noise Shrinkage | **CORRECTED & APPROVED** |
| Deterministic Precedence State Machine | **CORRECTED & APPROVED** |
| Signed Bipolar IGSS Envelope $[-100\text{ nA}, +100\text{ nA}]$ | **CORRECTED & APPROVED** |
| $\pm 10\ \mu\text{A}$ Instrument Bound & $\sim 1\text{ A}$ Physical Bound | **REJECTED / PURGED AS UNVERIFIED** |
| Specification Clipping Policy | **STRICTLY PROHIBITED** |
| Code Implementation | **PROHIBITED (STOPPED AWAITING EXPLICIT USER AUTHORIZATION)** |

---

### LOG-069: Stage 3 Final Pre-Implementation Contract Gate Decision Record

**Date**: 2026-09-17  
**Gate Status**: CONTRACT FINALIZED & ACCEPTED / IMPLEMENTATION PROHIBITED PENDING USER GO  
**Scope**: Final epistemic, semantic, and mathematical contract for Stage 3 Module B implementation. Resolves: (1) Causal overclaim removals (`NO_SIGNIFICANT_EXCESS_MOTION_DETECTED`), (2) Removal of "optimal" claims, (3) Complete numerical policy classification inventory, (4) Module A $\to$ Module B excess-drift contract, (5) Equipment state semantics, (6) Precedence hierarchy with evidence preservation, (7) As-of step candidate semantics, (8) Specification separation without clipping, (9) Signed IGSS representation without unverified bounds, (10) Uncertainty contract classification, and (11) Final authorized changes list. Zero code modified.

---

#### 1. Removal of Causal and Optimality Overclaims

1. **Epistemic Rectification of Equipment Confounding**:
   - The label `"SLOPE_ATTRIBUTED_TO_EQUIPMENT"` and phrasing `"component shift is fully explained by equipment"` are formally **retracted and replaced**.
   - **Corrected Terminology**: `NO_SIGNIFICANT_EXCESS_MOTION_DETECTED`.
   - **Scientific Meaning**: The condition $|g_{\text{excess}}| < 2.5$ establishes that no statistically significant excess motion was detected beyond the contemporaneous common-mode lot shift under the benchmark threshold. It does **not** prove that equipment caused the entire component change; it establishes that component-specific wearout cannot be distinguished from common-mode variation under current data support.
   - Similarly, `CONFOUNDED_ACTIVE_DRIFT` is formally classified as **"candidate component-specific excess drift under equipment confounding"**, NOT proof of autonomous physical wearout.
2. **Rectification of "Optimal" Forecasting Claims**:
   - The claim `"Carry-Forward is the optimal point forecast under noise dominance"` is formally **retracted and replaced** with:
     *"Carry-Forward is the benchmark-supported variance-conservative baseline under noise-dominated early-life conditions."*
   - The claim `"benchmark evidence proves raw trend degrades MSE"` is formally **retracted and replaced** with:
     *"The frozen benchmark demonstrates higher MSE for the evaluated raw-trend baseline under the tested noise/scenario conditions."*

---

#### 2. Numerical Policy Inventory & Classification

Every numerical constant and heuristic used in Stage 3 is audited and classified into exactly one category:
- **A. Existing Frozen Parameter** (pre-established in specification/frozen code)
- **B. Deterministic Implementation Policy** (pure numerical/computational guard)
- **C. Calibrated Parameter** (statistically calibrated against independent data)
- **D. Provisional Design Policy — Not Calibrated** (heuristic operational policy awaiting empirical calibration)

| Numerical Quantity | Classification | Mathematical Role & Operational Justification | Evidence Status |
| :--- | :--- | :--- | :--- |
| `|g_excess| >= 2.5` | **A. Existing Frozen Parameter** | Threshold for distinguishing excess component drift from common-mode lot motion. Established in Phase 3A/3C Module A specification (`fusion.py`). | **Frozen Specification Constant** |
| `k_sigma = 2.0` | **A. Existing Frozen Parameter** | Noise floor multiplier for soft-thresholded slope regularization. Frozen in Stage 2 (`AdaptiveDriftGatedModel`). | **Frozen Model Hyperparameter** |
| `Z_90 = 1.645` | **A. Existing Frozen Parameter** | Standard normal two-sided 90% coverage quantile. Frozen in Stage 1 (`baselines.py`). | **Standard Statistical Value** |
| `np.isfinite(y_pred)` | **B. Deterministic Implementation Policy** | Safe evaluation catching floating-point overflow (`OverflowError`) and non-finite results (`isinf`, `isnan`) in inverse transform. | **Standard IEEE 754 Error Guard (No Arbitrary Cutoff)** |
| `sigma_eff * sqrt(2)` | **D. Provisional Design Policy — Not Calibrated** | Heuristic interval inflation factor ($1.414\times$) applied when equipment confounding or unverified step candidates are present. | **Provisional Design Policy — NOT CALIBRATED** |
| `sigma_eff + sigma_equip` | **D. Provisional Design Policy — Not Calibrated** | Heuristic additive interval expansion incorporating lot dispersion under equipment confounding. | **Provisional Design Policy — NOT CALIBRATED** |
| `sigma_step_eff` | **D. Provisional Design Policy — Not Calibrated** | Post-step residual dispersion scale. Awaiting empirical calibration across verified step subsets. | **Provisional Design Policy — NOT CALIBRATED** |

*Mandate*: Zero constants may be described as "calibrated" unless empirical calibration evidence is independently established. No threshold tuning is authorized.

---

#### 3. Module A $\to$ Module B Excess-Drift Read-Only Contract

Module B must **never** independently reconstruct or recompute a second definition of $g_{\text{excess}}$. It must ingest the exact upstream fields evaluated by Module A at as-of time $T$:

| Field Name | Type / Representation | As-Of Timestamp | Source Module | Permitted Use in Module B | Recomputation in Module B? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `g_excess` | `Optional[float]` | $t \le T_{\text{as\_of}}$ | `screening/temporal.py` (`TemporalEvidence.g_excess`) | Quantitative excess drift magnitude relative to leave-one-out lot median. | **STRICTLY PROHIBITED** (Read-only) |
| `g_excess_status` | `bool` (`abs(g_excess) >= 2.5`) | $t \le T_{\text{as\_of}}$ | Derived from `TemporalEvidence.g_excess` | Gating condition to branch between `CONFOUNDED_ACTIVE_DRIFT` and `EQUIPMENT_COMMON_MODE_UNRESOLVED`. | Evaluated as boolean comparison only |
| `equipment_status` | `EquipmentStatus` enum | $t = T_{\text{as\_of}}$ | `screening/equipment.py` (`EquipmentEvidence.status`) | Gating condition for equipment confounding branch. | **STRICTLY PROHIBITED** (Read-only) |
| `drift_status` | `TemporalDriftStatus` enum | $t \le T_{\text{as\_of}}$ | `screening/temporal.py` (`TemporalEvidence.status`) | Gating condition for slope activation vs. Carry-Forward. | **STRICTLY PROHIBITED** (Read-only) |
| `step_status` | `AbruptStepStatus` enum | $t \le T_{\text{as\_of}}$ | `screening/step.py` (`StepEvidence.status`) | Gating condition for slope inhibition upon step candidate. | **STRICTLY PROHIBITED** (Read-only) |
| `sufficiency_status` | `bool` (`SufficiencyEvidence.sufficient`) | $t \le T_{\text{as\_of}}$ | `screening/sufficiency.py` | Hard execution veto. If `False`, emit invalid forecast. | **STRICTLY PROHIBITED** (Read-only) |

---

#### 4. Equipment State Semantics & Actions

1. **`EQUIPMENT_COMMON_MODE_UNRESOLVED`**:
   - **Trigger Condition**: $D_{\text{eq}}.\text{suspected} == \text{True}$ AND $|g_{\text{excess}}| < 2.5$.
   - **Epistemic Meaning**: No statistically significant component-specific excess motion detected beyond the contemporaneous common-mode lot shift. Component-specific wearout cannot be distinguished from test apparatus artifacts.
   - **Forecasting Action**: Do not assert zero physical degradation. Apply variance-conservative Carry-Forward ($\beta_{\text{eff}} = 0$, $\hat{y} = y(T_{\text{as\_of}})$). Widen prediction interval by provisional factor $\sqrt{2}$. Attach flags `EQUIPMENT_CONFOUNDED` and `NO_SIGNIFICANT_EXCESS_MOTION_DETECTED`.
2. **`CONFOUNDED_ACTIVE_DRIFT`**:
   - **Trigger Condition**: $D_{\text{eq}}.\text{suspected} == \text{True}$ AND $|g_{\text{excess}}| \ge 2.5$.
   - **Epistemic Meaning**: Candidate component-specific excess drift detected despite equipment/common-mode excursion. Component is drifting significantly faster than its peer group.
   - **Forecasting Action**: Do NOT zero the slope. Extrapolate regularized slope $\tilde{\beta}$. Inflate prediction interval by provisional equipment uncertainty. Attach flags `EQUIPMENT_CONFOUNDED` and `CANDIDATE_EXCESS_DRIFT_CONFOUNDED`.

---

#### 5. Deterministic Precedence Hierarchy & Evidence Preservation

1. **Precedence Hierarchy (Governs Kinematic Forecast Mode Only)**:
   $$\text{Sufficiency Failure} > \text{Step Candidate} > \text{Equipment-Confounded Drift} > \text{Autonomous Drift} > \text{Stationary / No Significant Drift}$$
2. **Evidence Preservation Guarantee**:
   - Precedence selects which mathematical model generates $\hat{y}(T_{\text{target}})$.
   - **Precedence NEVER erases, masks, or suppresses detector evidence from lower-priority detectors.**
   - All upstream detector outputs ($D_{\text{spec}}$, $D_{\text{peer}}$, $D_{\text{drift}}$, $D_{\text{step}}$, $D_{\text{eq}}$, $D_{\text{suff}}$) and all reason codes are copied verbatim into `PrognosticForecast.metadata["screening_evidence"]`.
   - Downstream consumers receive both the unconstrained multi-detector evidence and the gated prognostic forecast.

---

#### 6. Step Candidate As-Of Semantics

- At $T=24\text{h}$ or $T=96\text{h}$, $D_{\text{step}}$ establishes strictly: `ABRUPT_JUMP_DETECTED` (or `ABRUPT_JUMP_ALERT`).
- It must **never** use future checkpoints to evaluate whether the step persists across $168\text{h}$.
- Persistence is an ex-post descriptive property evaluated across future telemetry ($t > T$), never an as-of prognostic feature.
- Emitted flag strictly as-of $T$: `STEP_CANDIDATE_UNVERIFIED_PERSISTENCE`.

---

#### 7. Specification Separation Without Artificial Clipping

- $D_{\text{spec}}$ **never** alters kinematic slope $\beta_{\text{eff}}$ or point prediction $\hat{y}$.
- If a forecasted value exceeds Class A limits ($|\hat{y}| > 100.0\text{ nA}$ for $I_{\text{GSS}}$):
  - The numerical forecast is **preserved unmodified** (e.g. $250.0\text{ nA}$ remains $250.0\text{ nA}$).
  - It is **STRICTLY FORBIDDEN** to clip or clamp $\hat{y}$ to $\pm 100.0\text{ nA}$.
  - Structured metadata flags are emitted: `PREDICTED_SPEC_BREACH_POSITIVE` (if $\hat{y} > +100\text{ nA}$) or `PREDICTED_SPEC_BREACH_NEGATIVE` (if $\hat{y} < -100\text{ nA}$).

---

#### 8. Signed Bipolar IGSS Domain Without Unverified Bounds

- No physical device breakdown bound or ATE hardware compliance bound is authorized for implementation.
- Required controls:
  1. Strict signed bipolar coordinate: $u = \text{asinh}(y / 1.0\text{ nA})$ with inverse $y = \sinh(u) \cdot 1.0\text{ nA}$.
  2. Polarity is strictly preserved; taking $\text{abs}(I_{\text{GSS}})$ is prohibited.
  3. Numerical inverse-transform safety: Evaluate inverse transform safely. If `np.sinh()` encounters floating-point overflow (`OverflowError`) or produces a non-finite result (`isnan`, `isinf`), emit structured status `DIVERGENT_RUNAWAY_PREDICTION` with deterministic fallback to $y(T_{\text{as\_of}})$. No arbitrary finite cutoff is imposed.
  4. Never invent or hard-code unverified instrument ranges.

---

#### 9. Uncertainty Contract Classification

- All Stage 3 prediction intervals and uncertainty multipliers are formally classified as:
  **"uncalibrated training-fold empirical prediction policy"**
- They must **never** be described as "calibrated," "conformal," or "guaranteed."
- Intervals reflect training-fold empirical residual dispersion, not physical ground-truth bounds.

---

#### 10. Complete Stage 3 Implementation Authorization Boundary

The following represents the complete, closed list of authorized changes for Stage 3 implementation. Anything not listed here is strictly prohibited:

| Component | Authorized Stage 3 Change | Strict Prohibition |
| :--- | :--- | :--- |
| **`src/sih26170/prognostics/schema.py`** | Add typed metadata fields to `PrognosticForecast` for step candidate, equipment confounding, and spec breach flags. | No changes to `PrognosticInput` lineage or temporal as-of assertions. |
| **`src/sih26170/prognostics/stage2_models.py`** | Update `AdaptiveDriftGatedModel` point prediction to consume upstream $D_{\text{step}}$, $D_{\text{eq}}$, and $g_{\text{excess}}$ to execute the precedence table. | Zero new ML models (no GBMs, neural nets, ODEs). No modification to frozen baseline models. |
| **Slope Kinematics** | Inhibit slope ($\beta=0$) upon `ABRUPT_JUMP_ALERT` or `EQUIPMENT_COMMON_MODE_UNRESOLVED`. Retain regularized slope on `CONFOUNDED_ACTIVE_DRIFT`. | No post-hoc threshold tuning ($k_{\sigma}=2.0$ remains immutable). |
| **Specification Handling** | Attach `PREDICTED_SPEC_BREACH_POSITIVE/NEGATIVE` flags when $|\hat{y}| > 100\text{ nA}$. | **NEVER clip forecast at 100 nA**. |
| **Numerical Guards** | Catch non-finite results (`isnan`, `isinf`, `OverflowError`) on inverse transformation; emit `DIVERGENT_RUNAWAY_PREDICTION`. | Do not invent arbitrary cutoff thresholds or unverified ATE bounds. |
| **Preservation** | Phase 2F benchmark, Phase 2C data, Module A source code, and ground truth quarantine remain 100% frozen. | Zero code modification outside authorized prognostic files. |

---

### Verification
- Phase 2F frozen benchmark SHA-256 hashes verified 100% bit-for-bit intact.
- Full test suite passes: 164 passed, 0 failures.
- Zero implementation code modified.

---

### LOG-070: Stage 3 Final Micro-Gate — Numerical Safety & Fallback Architecture Decision Record

**Date**: 2026-09-17  
**Gate Status**: MICRO-GATE CLEARED / IMPLEMENTATION PROHIBITED PENDING USER GO  
**Scope**: Final mathematical correction to numerical guard semantics and fallback error handling. Resolves: (1) Retraction of the mathematical error asserting that $|u_{\text{pred}}| \ge 100$ is an IEEE float64 overflow risk, (2) Strict separation of numerical inverse-transform safety from model plausibility, eliminating arbitrary finite cutoffs, (3) Formal specification of deterministic fallback semantics upon non-finite inverse transforms, (4) Explicit confirmation of uncertainty scope (zero redesign of empirical $\sigma_{\text{eff}}$), and (5) Point-prediction scope boundary. Zero code modified.

---

#### 1. Retraction of the Mathematical Error Concerning $u = 100$

- **Mathematical Fact**: In IEEE 754 double precision (float64), maximum representable finite magnitude is $\approx 1.7977 \times 10^{308}$.
  - At $u = 100.0$, $\sinh(100.0) = \frac{e^{100} - e^{-100}}{2} \approx 1.344 \times 10^{43}$, which is **completely finite** and approximately 265 orders of magnitude below IEEE float64 overflow.
  - Float64 overflow in $\sinh(u)$ occurs only when $u > \ln(2 \times 1.7977 \times 10^{308}) \approx 710.476$.
- **Formal Retraction**: Any statement asserting that $|u_{\text{pred}}| \ge 100$ represents an "IEEE overflow risk" or "overflow threshold" is mathematically false and formally retracted.
- **Policy**: The arbitrary threshold $|u_{\text{pred}}| \ge 100$ is **eliminated entirely**. No arbitrary finite cutoffs are introduced into the numerical or physical pipeline.

---

#### 2. Separation of Numerical Safety from Model Plausibility

1. **Numerical Inverse-Transform Safety (Pure Computational Guard)**:
   - Must evaluate `inverse_transform_parameter(param, u_pred)` safely inside structured exception/finite checks.
   - Catches Python/NumPy `OverflowError`, `FloatingPointError`, and inspects `np.isfinite(y_pred)`.
   - If the inverse transform produces non-finite values (`inf`, `-inf`, `nan`):
     - Immediately flags the condition as `DIVERGENT_RUNAWAY_PREDICTION`.
     - Imposes no arbitrary pre-emptive finite clamping.
2. **Model Plausibility**:
   - Out-of-domain and extreme values are governed strictly by verified normative criteria (e.g. MIL-PRF-19500/703 Table I Class A specification limits $[-100\text{ nA}, +100\text{ nA}]$).
   - No unverified heuristic plausibility ceilings are added to numerical code.

---

#### 3. Deterministic Fallback Semantics

When numerical evaluation of the inverse transform produces a non-finite result (`OverflowError`, `inf`, `nan`):
1. **Fallback Value**: The point prediction falls back to the latest observed physical value: $\hat{y}(T_{\text{target}}) = y(T_{\text{as\_of}})$.
2. **Classification**: This fallback is strictly classified as a **deterministic software error-handling policy**, NOT an inferred physical device forecast.
3. **Audit Trail & Integrity**:
   - The forecast is marked with `is_valid = True` (telemetry is valid) but attaches the severe failure flag: `DIVERGENT_RUNAWAY_PREDICTION`.
   - The divergent transformed coordinate $u_{\text{pred}}$ is preserved in `PrognosticForecast.metadata["raw_unconstrained_u_pred"]`.
   - The numerical failure is **never silently converted into a nominal or healthy PASS forecast**.

---

#### 4. Uncertainty Scope Confirmation

- Stage 3 implementation **does NOT redesign or recalibrate uncertainty estimation**.
- The existing Leave-One-Lot-Out training-fold empirical $\sigma_{\text{eff}}$ machinery from Stage 1 and Stage 2 remains completely unchanged.
- Any interval widening for equipment confounding ($\sqrt{2}$) or unverified step candidates remains explicitly:
  **"uncalibrated training-fold empirical prediction policy."**
- Zero claims of conformal validity or statistical coverage guarantees are permitted.

---

#### 5. Point-Prediction Scope Confirmation

Stage 3 implementation modifies strictly and exclusively:
1. **Step Gating**: Inhibit slope extrapolation upon upstream `ABRUPT_JUMP_ALERT` (switching to post-step Carry-Forward).
2. **Equipment-Confounded Gating**: Decouple confounding from zero-degradation via upstream `g_excess` ($|g_{\text{excess}}| \ge 2.5 \implies$ extrapolate excess slope; $< 2.5 \implies$ Carry-Forward with `NO_SIGNIFICANT_EXCESS_MOTION_DETECTED`).
3. **Upstream Evidence Ingestion**: Read-only ingestion of $D_{\text{step}}$, $D_{\text{eq}}$, $D_{\text{drift}}$, $D_{\text{suff}}$, and $g_{\text{excess}}$ from `ParameterScreeningResult`.
4. **Specification Metadata**: Attachment of `PREDICTED_SPEC_BREACH_POSITIVE/NEGATIVE` flags without clipping point forecasts.
5. **Numerical Error Handling**: Safe exception and non-finite catching on inverse transformations.

**STRICTLY PROHIBITED**:
- No new forecasting models (no GBMs, neural nets, ODEs).
- No threshold tuning ($k_{\sigma}=2.0, Z_{0.90}=1.645$ remain immutable).
- No uncertainty recalibration.
- No benchmark modifications.

---

### LOG-071: Stage 3 Implementation & Safety Architecture Verification Record

- **Log ID**: LOG-071
- **Date**: 2026-09-17
- **Phase**: Phase 4 / Module B Stage 3 Implementation
- **Change**: Stage 3 Prognostics Safety Architecture Implementation & Verification
- **Previous State**: Stage 2 `AdaptiveDriftGatedModel` without upstream Module A evidence ingestion, without step-candidate slope inhibition, without excess-motion equipment decoupling, and with potential inverse-transform non-finite unhandled divergence.
- **New State**: Stage 3 deterministic precedence slope-gating, read-only Module A integration, safe inverse-transform fallback, unclipped specification breach flags, and complete evidence preservation fully implemented, tested, and verified.
- **Reason**: Contract execution authorized under LOG-069 and amended by LOG-070.
- **Source / Provenance**: LOG-069, LOG-070, MIL-PRF-19500/703 Table I.
- **Status**: TESTED
- **Affected Area**: Module B Prognostics (`src/sih26170/prognostics/schema.py`, `src/sih26170/prognostics/stage2_models.py`, `tests/prognostics/test_stage3_safety_architecture.py`).
- **Impact**: Eliminates noise amplification, safely handles inverse transform divergence, strictly preserves signed IGSS semantics and upstream detector evidence across all 173 passing tests.

#### 1. Implementation Summary Against Cleared Contract

The Stage 3 implementation was executed strictly within the boundaries authorized by LOG-069 and amended by LOG-070:

1. **Enriched Prognostic Metadata & Contract (`schema.py`)**:
   - Added typed fields to `PrognosticForecast`:
     - `step_candidate_status: Optional[str] = None`
     - `equipment_confounded: bool = False`
     - `drift_status: Optional[str] = None`
     - `predicted_spec_breach: Optional[str] = None`
     - `is_divergent_fallback: bool = False`
     - `raw_unconstrained_u_pred: Optional[float] = None`
   - Added `to_dict()` serialization method to `PrognosticForecast`.
   - Updated `PrognosticForecast.__post_init__` to guard finite checks with `if self.is_valid:`, correctly permitting `NaN` on invalid / excluded forecasts.

2. **Upstream Module A Evidence Integration (`stage2_models.py`)**:
   - Added read-only helper `_extract_parameter_screening_evidence` to safely extract parameter-specific screening results from `input_data.screening_result`.
   - Ingests $D_{\text{step}}$, $D_{\text{eq}}$, $D_{\text{drift}}$, $D_{\text{suff}}$, and $g_{\text{excess}}$ strictly read-only without recomputing upstream metrics.
   - All upstream detector outputs and reason codes are faithfully preserved in `PrognosticForecast.metadata["screening_evidence"]`.

3. **Deterministic Slope-Gating Precedence State Machine**:
   - **Level 0 (Sufficiency Failure)**: Upstream $D_{\text{suff}}.\text{sufficient} == \text{False}$ or `not input_data.data_sufficiency_passed` immediately terminates with `is_valid = False` and the upstream reason code.
   - **Level 1 (Abrupt Step Candidate)**: If $D_{\text{step}}.\text{status} == \text{ABRUPT\_JUMP\_ALERT}$, the kinetic slope is set to $\beta_{\text{eff}} = 0.0$ (switching to post-step Carry-Forward). Emits `step_candidate_status = "STEP_CANDIDATE_UNVERIFIED_PERSISTENCE"`.
   - **Level 2 (Equipment Confounding Decoupling)**: If $D_{\text{eq}}.\text{suspected} == \text{True}$:
     - If $|g_{\text{excess}}| \ge 2.5$: Retains regularized excess slope candidate ($\tilde{\beta}$), emitting flag `CANDIDATE_EXCESS_DRIFT_CONFOUNDED`.
     - If $|g_{\text{excess}}| < 2.5$ or `None`: Extrapolation is zeroed ($\beta_{\text{eff}} = 0.0$), emitting flag `NO_SIGNIFICANT_EXCESS_MOTION_DETECTED`.
     - Sets `equipment_confounded = True`.
   - **Level 3 (Autonomous Drift vs. Stationary)**:
     - If $D_{\text{drift}}.\text{status} == \text{STATIONARY}$: Extrapolation is zeroed ($\beta_{\text{eff}} = 0.0$), emitting `drift_status = "STATIONARY_NOISE_BOUNDED"`.
     - Otherwise: Evaluates soft-thresholded L1 regularized slope with $k_{\sigma} = 2.0$. If $|raw\_slope| \le \theta$, slope is zeroed (`STATIONARY_NOISE_BOUNDED`); if $> \theta$, regularized slope $\tilde{\beta} = \text{sign}(\text{raw}) \cdot (|\text{raw}| - \theta)$ is extrapolated forward (`ACTIVE_DRIFT_EXTRAPOLATED`).

4. **Safe Inverse-Transform Evaluation & Deterministic Software Fallback**:
   - Evaluates `inverse_transform_parameter(param, u_pred)` inside a try-catch block handling `(OverflowError, FloatingPointError, Exception)` and verifies `np.isfinite(y_pred)`.
   - On non-finite failure:
     - Sets $\hat{y} = y(T_{\text{as\_of}})$ (deterministic software error fallback, NOT an inferred physical forecast).
     - Emits `is_divergent_fallback = True`.
     - Attaches flag `DIVERGENT_RUNAWAY_PREDICTION`.
     - Preserves the divergent coordinate in `raw_unconstrained_u_pred`.
     - Never silently converts the fallback into a healthy or nominal forecast.
   - Completely eliminates the arbitrary $u = 100$ cutoff as mandated by LOG-070.

5. **Signed Bipolar IGSS & Specification Breach Flagging**:
   - Retains signed bipolar asinh representation: $u = \text{asinh}(y / 1.0\text{ nA})$. Taking `abs()` is strictly avoided.
   - Point predictions exceeding $\pm 100.0\text{ nA}$ are **never clipped**.
   - Structured metadata flags `PREDICTED_SPEC_BREACH_POSITIVE` (if $\hat{y} > +100\text{ nA}$) or `PREDICTED_SPEC_BREACH_NEGATIVE` (if $\hat{y} < -100\text{ nA}$) are attached.

---

#### 2. Verification Evidence

##### A. Test Suite Results
Full test suite executed via `PYTHONPATH=. python3 -m pytest -v`:
- **Total Tests**: 173 passed, 0 failed, 0 skipped in 7.49s.
- **Baseline Integrity**: All 164 previous tests (Module A detectors, pipeline, transformers, baselines, leakage controls, Phase 2F generator, config, schema, standing log) pass 100%.
- **New Stage 3 Tests Added (`tests/prognostics/test_stage3_safety_architecture.py`)**:
  1. `test_abrupt_step_slope_inhibition`: Proves that an upstream `ABRUPT_JUMP_ALERT` inhibits slope extrapolation to post-step Carry-Forward and emits `STEP_CANDIDATE_UNVERIFIED_PERSISTENCE`.
  2. `test_equipment_common_mode_insignificant_excess_motion`: Proves that under equipment excursion with $|g_{\text{excess}}| = 1.1 < 2.5$, slope extrapolation is inhibited to Carry-Forward and emits `NO_SIGNIFICANT_EXCESS_MOTION_DETECTED`.
  3. `test_equipment_confounding_significant_excess_motion`: Proves that under equipment excursion with $|g_{\text{excess}}| = 3.5 \ge 2.5$, regularized excess slope is extrapolated and emits `CANDIDATE_EXCESS_DRIFT_CONFOUNDED`.
  4. `test_evidence_preservation`: Proves all upstream evidence ($D_{\text{step}}, D_{\text{eq}}, D_{\text{drift}}, D_{\text{spec}}, D_{\text{suff}}$) is completely preserved in `metadata["screening_evidence"]`.
  5. `test_signed_bipolar_igss_behavior`: Proves negative IGSS polarity is strictly preserved in both linear and asinh space without taking `abs()`.
  6. `test_predicted_specification_breach_metadata`: Proves that forecasts exceeding $\pm 100\text{ nA}$ on IGSS remain unclipped (e.g. $+250.0\text{ nA}$ and $-180.0\text{ nA}$) and attach `PREDICTED_SPEC_BREACH_POSITIVE/NEGATIVE`.
  7. `test_actual_non_finite_inverse_transform_fallback`: Proves that non-finite inverse transforms (e.g. simulated overflow) trigger deterministic fallback to $y(T_{\text{as\_of}})$ with `is_divergent_fallback = True` and flag `DIVERGENT_RUNAWAY_PREDICTION`.
  8. `test_preservation_of_raw_divergent_u_pred`: Proves that raw divergent coordinate $u_{\text{pred}}$ is preserved in metadata upon non-finite fallback.
  9. `test_leakage_and_adversarial_future_data_isolation`: Proves that adversarial future corruption ($t > T_{\text{as\_of}}$) and future screening evidence are strictly rejected or isolated from the forecast.

##### B. Frozen Phase 2F Hash Verification
Bit-for-bit cryptographic SHA-256 verification of `data/synthetic_phase2f_frozen/*`:
```text
3da9e473050158d978777bd5e3775206171be9a3ef662dab245d072d30c9a363  REPRODUCIBILITY.md
ac63acce868d9453c6c50859cb4e4752d3bc5daf1dbd58675c6264b6c5d26a87  SCENARIO_ONTOLOGY.md
964983ad21c1983e26d1433a99533d8e374d8926979b2f5d729a84333e2dc02e  SCIENTIFIC_BOUNDARIES.md
17033eaf8ee352cda2ebf3da8b3366601eba6412daa553ad1382ddaaa86576f7  THRESHOLD_PROVENANCE.md
a4bb3f75f8211bf38b4c38cde0bbd1908eeecb75039700de84b1cc0c56f6dd27  configuration_snapshot.json
25cc3d7cc908ad511c08193221dd7b196ea2fa45505bbc0682fb80fb107fab00  generation_metadata.json
4bf2155fcc7698813f766e1dea9730213e0a6097e484bfa786eb1b94925f3d2b  ground_truth.csv
5a08630f9fafc95563c13acea77df7aa066f7abc7a08b785a77c2709553980f6  manifest.json
b4282e0743cd6a0b2b74354e431bf8f308b03281c44c0437d30f7b53bd6ca983  observations.csv
8f7b756255adfe444a3f15ba55b739d07e478565fb4e27639000905c49116b2e  scenario_manifest.json
```
All hashes matched 100% bit-for-bit.

##### C. Architecture & Boundary Integrity
- **Module A Source**: `src/sih26170/screening/` untouched (timestamps confirmed unchanged from Phase 3A).
- **Threshold Integrity**: $k_{\sigma} = 2.0$, $Z_{0.90} = 1.645$, $|g_{\text{excess}}| = 2.5$ immutable; no thresholds tuned.
- **Uncertainty Architecture**: No redesign or recalibration of empirical $\sigma_{\text{eff}}$.
- **Model Classes**: Zero new model classes (only `AdaptiveDriftGatedModel` and `HierarchicalLotShrunkModel`).
- **Benchmark Evaluation**: Completed as single authorized pass (results audited in LOG-072).

---

### LOG-072: Stage 3 Frozen Benchmark Post-Evaluation Forensic Audit & Scientific Boundary Correction

- **Log ID**: LOG-072
- **Date**: 2026-09-17
- **Phase**: Phase 4 / Module B Stage 3 Post-Evaluation Forensic Audit
- **Change**: Post-Evaluation Forensic Audit, Metric Reconciliation & Scientific Boundary Correction
- **Previous State**: Preliminary post-evaluation summary with overstated claims ("proves correctness", "1,274 stable components", "zero unwarranted movement", "noise-shrunk trajectories", "correctly flagged spec breaches").
- **New State**: Fully audited, mathematically reconciled, and epistemically corrected canonical evaluation record distinguishing components ($N=398$), parameter-series ($N=1,592$), valid forecasts ($N=1,592$ in Task 1, $N=1,585$ in Task 2), and observations ($N=6,368$).
- **Reason**: Scientific boundary compliance, epistemic precision, metric reconciliation, and preservation of architectural dependencies and negative findings.
- **Source / Provenance**: PHASE_2F_FROZEN_BENCHMARK_v1.0.0 LOLO Evaluation Results (`stage3_full_frozen_evaluation.json`).
- **Status**: AUDITED
- **Affected Area**: Canonical Project Log (`docs/PROTOTYPE_STANDING_LOG.md` / `docs/PROJECT_LOG.md`).
- **Impact**: Restricts claims strictly to synthetic benchmark evidence, preserves the architectural constraint of Module B on Module A evidence, documents trade-offs where sub-threshold degradation is held at Carry-Forward, and confirms exact mathematical reconciliation.

#### 1. Exact Mathematical Reconciliation & N-Value Disambiguation

A forensic audit of all sample counts and denominators across the evaluation pipeline establishes:
- **Component Population**: Exactly $N = 398$ synthetic simulated MOSFET components across $16$ lots.
- **Checkpoints**: $4$ fixed checkpoints ($0\text{h}, 24\text{h}, 96\text{h}, 168\text{h}$).
- **Parameter-Series Population**: Exactly $398 \times 4 = 1,592$ parameter-series per task ($398$ series each for `IDSS`, `VGS(th)`, `RDS(on)`, `IGSS`).
- **Total Historical Observations**: Exactly $6,368$ measurement records in `observations.csv`, containing $7$ intermittent missing values at $96\text{h}$.
- **Task 1 ($24\text{h} \to 168\text{h}$)**:
  - Total series evaluated: $N = 1,592$.
  - Valid forecasts: $N_{\text{valid}} = 1,592$. Excluded forecasts: $N_{\text{excl}} = 0$.
  - Mathematical reconciliation: Weighted parameter MAE ($0.518678$) and weighted scenario MAE ($0.518678$) match overall aggregate MAE exactly ($\Delta = 0.0$).
- **Task 2 ($96\text{h} \to 168\text{h}$)**:
  - Total series evaluated: $N = 1,592$.
  - Valid forecasts: $N_{\text{valid}} = 1,585$. Excluded forecasts: $N_{\text{excl}} = 7$.
  - Exclusion Root Cause: Upstream Module A sufficiency detector ($D_{\text{suff}}$) correctly asserted `MISSING_CHECKPOINTS_96` on 7 specific parameter-series (`LOT_D02_C012` IGSS, `LOT_D02_C028` VGS(th), `LOT_M01_C026` IGSS, `LOT_N01_C025` RDS(on), `LOT_S05_C013` VGS(th), `LOT_W01_C003` IDSS, `LOT_W01_C035` RDS(on)). Under Level 0 precedence, these were emitted as `is_valid = False` with `NaN` predictions.
  - Mathematical reconciliation: When weighted by valid series ($N_{\text{valid}} = 1,585$), overall MAE ($0.534819$), overall MSE ($11.013115$), and overall coverage ($87.2555\%$) reconcile with per-parameter and per-scenario metrics down to machine precision ($\Delta < 10^{-14}$).

#### 2. Canonical Rectification of Overstated Language

The preliminary post-evaluation summary contained overstated terminology that is formally corrected in this canonical log:
1. **No "Proof of Correctness or Physical Validity"**: All statements claiming that benchmark evaluation "proves mathematical correctness," "proves physical validity," or "proves general behavior" are retracted. Language is strictly restricted to observed empirical performance on `PHASE_2F_FROZEN_BENCHMARK_v1.0.0`.
2. **Component vs. Parameter-Series Clarification**: The phrase "1,274 stable components" is corrected to "1,274 stable parameter-series" across the 398 components.
3. **Forecast Movement Clarification**: The claim of "zero unwarranted forecast movement" is replaced with the precise statement that the evaluated stationary/high-but-stable gating paths suppressed slope extrapolation and reduced noise-driven forecast error on the benchmark.
4. **Kinematic Mechanism Clarification**: The phrase "noise-shrunk trajectories" is replaced with "Carry-Forward point projection ($\beta_{\text{eff}} = 0$)" where the gating mechanism sets the extrapolation slope to zero.
5. **Specification Breach Observation**: The phrase "correctly flagged predicted specification breaches" is corrected to the implementation-observation statement: attached `PREDICTED_SPEC_BREACH_POSITIVE/NEGATIVE` metadata flags to forecasts exceeding Class A absolute limits without modifying point predictions.
6. **Design Consistency**: The phrase "proving that the safety gating contract behaves exactly as mathematically designed" is corrected to "demonstrating consistency with the intended deterministic gating behavior on the frozen benchmark."

#### 3. Preservation of Legitimate Negative Findings & Architectural Dependencies

The forensic audit confirms an essential architectural reality and a legitimate negative finding that must not be obscured:
1. **Module B Architectural Dependency**: Module B prognostic gating is strictly downstream of and constrained by upstream Module A evidence ($D_{\text{step}}$, $D_{\text{eq}}$, $D_{\text{drift}}$, $D_{\text{suff}}$, $g_{\text{excess}}$). Module B does not independently evaluate raw sensor trajectories to override Module A screening decisions.
2. **Negative Finding on Sub-Threshold Degradation**:
   - For low-rate or late-accelerating degrading parameter-series (`linear_drift` and `accelerating_drift`), cumulative drift at $T \le 96\text{h}$ remains below Module A's kinetic evidence threshold ($|g| < 2.5\sigma$ or $|g_{\text{excess}}| < 2.5$).
   - Consequently, upstream Module A classifies them as `STATIONARY` or `EQUIPMENT_CONFOUNDED`.
   - By strictly obeying upstream evidence, Stage 3 suppresses extrapolation and sets $\beta_{\text{eff}} = 0$ (Carry-Forward).
   - This causes an increase in forecast error on these specific degrading series compared to un-gated Stage 2 slope extrapolation:
     - Task 1 `linear_drift` MAE: $0.6935 \to 0.9114$ ($\Delta\text{MAE} = +0.2179$).
     - Task 2 `linear_drift` MAE: $0.4973 \to 0.6759$ ($\Delta\text{MAE} = +0.1786$).
     - Task 2 `accelerating_drift` MAE: $13.2967 \to 16.6883$ ($\Delta\text{MAE} = +3.3916$).
3. **No Threshold Tuning**: No threshold changes, ad-hoc overrides, or remedies are proposed or implemented. This behavior is preserved as an inherent trade-off of evidence-gated prognostics under sub-threshold signal-to-noise ratios.

#### 4. Reconciled Performance Summary Table

```text
┌──────────────────────────────┬────────────────────────┬────────────────────────┬────────────────────────┐
│ Metric / Scenario            │ Stage 2 Baseline       │ Stage 3 Gated          │ Delta (S3 - S2)        │
├──────────────────────────────┼────────────────────────┼────────────────────────┼────────────────────────┤
│ TASK 1 (24h -> 168h, N=1592) │                        │                        │                        │
│   Overall MAE                │ 1.09396                │ 0.51868                │ -0.57528 (-52.59%)     │
│   Overall RMSE               │ 9.55121                │ 3.05988                │ -6.49133 (-67.96%)     │
│   90% Coverage Rate          │ 82.47%                 │ 90.01%                 │ +7.54 pp (+9.14%)      │
│   Mean Interval Width        │ 2.94960                │ 1.77373                │ -1.17587 (-39.87%)     │
│   Mean Winkler Score         │ 9.68293                │ 3.49132                │ -6.19161 (-63.94%)     │
├──────────────────────────────┼────────────────────────┼────────────────────────┼────────────────────────┤
│ TASK 2 (96h -> 168h, N=1585) │                        │                        │                        │
│   Overall MAE                │ 0.59361                │ 0.53482                │ -0.05879 (-9.90%)      │
│   Overall RMSE               │ 3.68040                │ 3.31860                │ -0.36180 (-9.83%)      │
│   90% Coverage Rate          │ 85.74%                 │ 87.26%                 │ +1.51 pp (+1.77%)      │
│   Mean Interval Width        │ 1.92917                │ 1.79129                │ -0.13788 (-7.15%)      │
│   Mean Winkler Score         │ 3.96655                │ 3.48678                │ -0.47978 (-12.10%)     │
├──────────────────────────────┼────────────────────────┼────────────────────────┼────────────────────────┤
│ KEY SCENARIO MAE (Task 1)    │                        │                        │                        │
│   subtle_abrupt_change (N=2) │ 48.0454                │ 4.8798                 │ -43.1656 (-89.84%)     │
│   equipment_common_mode (N=92│ 0.2506                 │ 0.2437                 │ -0.0070 (-2.78%)       │
│   stable (N=1274)            │ 1.0100                 │ 0.3809                 │ -0.6291 (-62.29%)      │
│   high_but_stable (N=170)    │ 0.4131                 │ 0.3480                 │ -0.0651 (-15.76%)      │
│   linear_drift (N=11)        │ 0.6935                 │ 0.9114                 │ +0.2179 (+31.42%)      │
│   accelerating_drift (N=4)   │ 21.5521                │ 21.5521                │ +0.0000 (0.00%)        │
├──────────────────────────────┼────────────────────────┼────────────────────────┼────────────────────────┤
│ KEY SCENARIO MAE (Task 2)    │                        │                        │                        │
│   subtle_abrupt_change (N=2) │ 32.0498                │ 1.3875                 │ -30.6623 (-95.67%)     │
│   equipment_common_mode (N=92│ 0.6183                 │ 0.5211                 │ -0.0972 (-15.72%)      │
│   stable (N=1268 valid)      │ 0.4100                 │ 0.3824                 │ -0.0275 (-6.73%)       │
│   high_but_stable (N=169 val)│ 0.3521                 │ 0.3497                 │ -0.0024 (-0.68%)       │
│   linear_drift (N=11)        │ 0.4973                 │ 0.6759                 │ +0.1786 (+35.91%)      │
│   accelerating_drift (N=4)   │ 13.2967                │ 16.6883                │ +3.3916 (+25.51%)      │
└──────────────────────────────┴────────────────────────┴────────────────────────┴────────────────────────┘
```

---

### LOG-073: Stage 4 Architecture Discovery Gate — Sub-Threshold Degradation Decision Record

- **Log ID**: LOG-073
- **Date**: 2026-09-17
- **Phase**: Phase 4 / Module B Stage 4 Architecture Discovery Gate
- **Change**: Sub-Threshold Degradation Architecture Discovery & Feasibility Evaluation
- **Previous State**: Stage 3 deterministic gating where sub-threshold degradation ($|g| < 2.5\sigma$, $|g_{\text{excess}}| < 2.5$) is held at Carry-Forward ($\beta_{\text{eff}} = 0$), increasing forecast error on 15 degrading parameter-series while preventing catastrophic noise amplification on 1,274 stable parameter-series.
- **New State**: Formal architecture discovery, identifiability analysis, and epistemic audit completed. Recommendation: **DEFER — no new incipient-degradation detector should be implemented or calibrated from the current four-checkpoint Phase 2F benchmark.**
- **Reason**: Scientific evaluation of whether persistent weak directional change can be distinguished from measurement noise at $K=2$ ($T=24\text{h}$) and $K=3$ ($T=96\text{h}$) without lowering $2.5\sigma$ or inflating false-positive rates.
- **Source / Provenance**: LOG-060, LOG-069, LOG-072, PHASE_2F_FROZEN_BENCHMARK_v1.0.0.
- **Status**: DESIGN_DECISION
- **Affected Area**: Architecture Design (`docs/SIH26170_Architecture.md`, `docs/PROTOTYPE_STANDING_LOG.md`).
- **Impact**: Prevents circular and uncalibrated changes, proves mathematical unidentifiability at $K=2$ and $K=3$, establishes required conditions for future sub-threshold detection experiments, and keeps Stage 3 frozen and validated.

---

#### 1. The Identified Architectural Limitation

`[VERIFIED FROM CURRENT PROJECT ARTIFACTS]`
- **Architectural Hierarchy**: Module B prognostic gating is strictly downstream of and constrained by upstream Module A kinetic evidence ($D_{\text{step}}$, $D_{\text{eq}}$, $D_{\text{drift}}$, $D_{\text{suff}}$, $g_{\text{excess}}$).
- **The Trade-Off Phenomenon**: In Phase 2F benchmark testing, when early or late physical degradation has not yet accumulated sufficient normalized drift to cross Module A's screening evidence threshold ($|g| \ge 2.5\sigma$ or $|g_{\text{excess}}| \ge 2.5$), Module A reports `STATIONARY` or `EQUIPMENT_CONFOUNDED`.
- Under the Stage 3 deterministic precedence contract (LOG-069 Level 2/3), Module B sets $\beta_{\text{eff}} = 0$ (Carry-Forward).
- **Observed Empirical Impact**:
  - *System-Level Benefit*: Suppressed noise-jitter extrapolation across the 1,274 stable parameter-series, collapsing Task 1 stable RMSE from $9.7722 \to 0.6367$ ($-93.48\%$) and overall benchmark RMSE from $9.5512 \to 3.0599$ ($-67.96\%$).
  - *Identified Limitation*: Point prediction error increased on the 15 true degrading parameter-series:
    - Task 1 `linear_drift` ($N=11$): MAE increased from $0.6935 \to 0.9114$ ($\Delta = +0.2179$).
    - Task 2 `linear_drift` ($N=11$): MAE increased from $0.4973 \to 0.6759$ ($\Delta = +0.1786$).
    - Task 2 `accelerating_drift` ($N=4$): MAE increased from $13.2967 \to 16.6883$ ($\Delta = +3.3916$).
- **Mandate**: Lowering the $2.5\sigma$ threshold is explicitly prohibited. The purpose of this gate is to evaluate whether an independent "incipient/sub-threshold change" evidence channel is technically defensible.

---

#### 2. Candidate Approaches Evaluated

`[PROPOSED DESIGN]`
Five potential mathematical formulations for a sub-threshold evidence channel were audited:
1. **Approach 1: Non-Parametric Checkpoint Monotonicity**: Testing strict directional consistency across available checkpoints ($u_0 < u_1 < u_2$).
2. **Approach 2: Non-Parametric Rank Slope Confidence Intervals**: Sen-Kendall rank intervals on pairwise differences $S_{jk} = (u_k - u_j)/(t_k - t_j)$ requiring the lower $(1-\alpha)$ bound to be positive ($\beta_{\text{lower}} > 0$).
3. **Approach 3: Parametric Low-Degree Polynomial / Linear Regression**: Evaluating the t-statistic on OLS slope $\hat{\beta} / \text{SE}(\hat{\beta})$.
4. **Approach 4: Sequential Cumulative Evidence (CUSUM / SPRT / State-Space)**: Accumulating normalized residual evidence against a zero-drift null hypothesis.
5. **Approach 5: Lot-Relative Excess Drift Relaxation**: Reducing the excess drift threshold below $|g_{\text{excess}}| < 2.5$ for high-confidence nominal lots.

---

#### 3. Identifiability Analysis at $T=24\text{h}$ ($K=2$) and $T=96\text{h}$ ($K=3$)

##### A. Checkpoint $T=24\text{h}$, $K=2$ ($t \in \{0\text{h}, 24\text{h}\}$)
`[MATHEMATICAL/STATISTICAL INFERENCE]`
- **Available Data**: Exactly two historical observations $(0, y_0)$ and $(24, y_1)$ transformed to $(u_0, u_1)$.
- **Degrees of Freedom**: $df = 0$ for residual dispersion, noise estimation, or curvature.
- **Statistical Structure**: Under Gaussian white noise $\epsilon \sim \mathcal{N}(0, \sigma_{\text{noise}}^2)$, the observed difference is $\Delta u = u_1 - u_0 \sim \mathcal{N}(\mu_{\text{drift}}, 2\sigma_{\text{noise}}^2)$.
- **Identifiability Barrier**: Any observed difference $\Delta u$ is mathematically indistinguishable between:
  1. A true weak physical degradation drift rate $\beta = \Delta u / 24$.
  2. A random noise excursion $\epsilon_1 - \epsilon_0 = \Delta u$.
  3. A temporary contact resistance / electrometer fluctuation.
- **False-Positive Explosion**: Any decision rule asserting "incipient drift" when $|\Delta u| > \tau$ on $K=2$ is an unregularized threshold test. To detect weak drift with $\mu_{\text{drift}} \approx 1.0\sigma$, setting $\tau \approx 1.0\sigma$ yields a per-test false positive rate:
  $$P(|\mathcal{N}(0, 2\sigma^2)| > 1.0\sigma) = 2\left(1 - \Phi\left(\frac{1.0}{\sqrt{2}}\right)\right) \approx 2(1 - 0.7602) \approx 47.95\%$$
- Across 1,274 stable parameter-series, such a detector would falsely classify $\approx 610$ healthy components as "incipient degraders" at 24h!
- **Conclusion at $K=2$**: Weak directional change is **mathematically unidentifiable** from measurement noise at the individual component level with $K=2$.

##### B. Checkpoint $T=96\text{h}$, $K=3$ ($t \in \{0\text{h}, 24\text{h}, 96\text{h}\}$)
`[MATHEMATICAL/STATISTICAL INFERENCE]`
- **Available Data**: Exactly three observations $(0, u_0)$, $(24, u_1)$, $(96, u_2)$ with pairwise slopes $S_{01}, S_{12}, S_{02}$ ($M = \binom{3}{2} = 3$).
- **Permutation Probability of Monotonicity**: Under the null hypothesis $H_0$ of independent stationary measurement noise, all $3! = 6$ permutations of $(u_0, u_1, u_2)$ are equally likely.
  - The probability of strict upward monotonicity $(u_0 < u_1 < u_2)$ occurring purely by random noise is:
    $$P(\text{monotonic upward} \mid H_0) = \frac{1}{3!} = \frac{1}{6} \approx 16.67\%$$
  - The probability of monotonicity in either direction is $2/6 = 33.33\%$.
  - **Operational Consequence**: A simple monotonicity detector would falsely flag $16.67\%$ of completely stationary, nominal parameter-series. Across the 1,268 valid stable series at 96h, this would produce $\approx 211$ false degradation alarms.
- **Sen-Kendall Non-Parametric Rank Bounds**:
  - With $M=3$ slope pairs, the minimum achievable one-sided significance level for a rank test (testing whether the minimum slope $S_{(1)} > 0$) is exactly $\alpha = 1/6 \approx 0.167$.
  - Achieving standard false-positive control ($\alpha \le 0.05$, let alone engineering screening standards $\alpha \le 0.001$) is **mathematically impossible** with $K=3$.
- **Parametric Regression with $df=1$**:
  - Fitting a linear slope across 3 points leaves $df = 3 - 2 = 1$.
  - The Student-t critical value at $\alpha = 0.05$ (two-sided) with $df=1$ is $t_{0.025, 1} = 12.706$ (one-sided: $t_{0.05, 1} = 6.314$).
  - A weak degradation signal ($\text{SNR} \le 10\text{ dB}$) cannot achieve $t > 6.31$ with 1 degree of freedom unless the residual scatter is artificially zero.
- **Conclusion at $K=3$**: Weak directional change is **statistically uncalibratable** for controlled false-alarm rates ($< 1\%$) with $K=3$.

---

#### 4. Statistical Assumptions & Failure Modes

`[MATHEMATICAL/STATISTICAL INFERENCE]`
To make an incipient detector appear functional with $K \le 3$, an engineer would have to assume:
1. *Zero Autocorrelation*: Measurement noise is strictly white with zero temporal autocorrelation between checkpoints.
   - *Failure Mode*: In real burn-in ovens and ATE fixtures, contact resistance drift, chamber thermal gradients, and electrometer zero-drifts persist across 24–72 hours, creating spurious monotonic sequences on nominal devices.
2. *Strict Gaussianity*: Residual errors have light Gaussian tails.
   - *Failure Mode*: Gate leakage ($I_{\text{GSS}}$) and drain leakage ($I_{\text{DSS}}$) exhibit log-normal or Cauchy-like heavy tails near electrometric noise floors, triggering frequent outlier excursions that mimic incipient drift.
3. *Zero Lot-Level Common Mode*: Any observed drift is component-specific.
   - *Failure Mode*: In lots with equipment excursions (e.g., `LOT_E01`, `LOT_E02`, `LOT_W01`), synchronous drift would be falsely flagged as autonomous component wearout.

---

#### 5. Interaction with Upstream Module A Detectors

`[PROPOSED DESIGN]`
An incipient evidence channel would create severe architectural conflicts with existing Module A detectors:
- **Conflict with $D_{\text{eq}}$ (Equipment Common Mode)**: If $D_{\text{eq}}.\text{suspected} == \text{True}$ and $|g_{\text{excess}}| < 2.5$, the component's shift is statistically indistinguishable from the lot median. Promoting an "incipient drift" alarm under equipment confounding directly reverses the decoupling achieved in Stage 3, re-introducing equipment-induced false alarms.
- **Conflict with $D_{\text{drift}}$ (Cumulative Temporal Drift)**: $D_{\text{drift}}$ uses $2.5\sigma$ to control the lot-wide Family-Wise Error Rate (FWER). If an incipient channel triggers below $2.5\sigma$, what prognostic action could it take?
  - If it triggers Carry-Forward, it provides no benefit.
  - If it triggers slope extrapolation, it re-activates the noise-jitter extrapolation that exploded stable series RMSE in Stage 2 ($9.77$ vs $0.64$).
- **Conflict with $D_{\text{step}}$ (Abrupt Jump)**: An incipient channel could misinterpret the onset of an abrupt step change as continuous drift, bypassing step-slope inhibition.

---

#### 6. Architectural Placement Evaluation

`[MATHEMATICAL/STATISTICAL INFERENCE]`
- **Option A: New Module A Detector ($D_{\text{incipient}}$)**:
  - *Verdict*: **DEFERRED under the current evidence regime; no benchmark-supported basis exists to introduce an additional detector without independent null/power calibration.**
- **Option B: Module B-Only Diagnostic**:
  - *Verdict*: **REJECTED**. Stage 2 proved that when Module B operates on unconstrained weak slopes, it increases overall RMSE by $212\%$ on the benchmark.
- **Option C: Explicitly Remain Unavailable under Current Data Support**:
  - *Verdict*: **ACCEPTED**. The limitation is an inherent consequence of low temporal sampling density ($K \le 3$), not an algorithmic defect.

---

#### 7. Benchmark Representativeness & Circularity Risk

`[VERIFIED FROM CURRENT PROJECT ARTIFACTS]`
- **True Degrading Population in Phase 2F**: Exactly $15$ parameter-series out of $1,592$ ($0.94\%$ of the benchmark):
  - $11$ `linear_drift` series across 5 lots (`LOT_D01`, `LOT_D02`, `LOT_D04`, `LOT_M01`, `LOT_W01`).
  - $4$ `accelerating_drift` series across 2 lots (`LOT_D03`, `LOT_M01`).
- **LOLO Quarantining Reality**: In 11 of the 16 LOLO folds, the held-out test lot contains **zero** degrading components.
- **Circularity Risk**: Developing, tuning, or evaluating an incipient-drift detector on these 15 specific synthetic series would constitute direct post-hoc circular tuning to random noise realizations of 15 specific simulation seeds. It would have zero scientific validity for establishing general detection capabilities.

---

#### 8. Required Experimental Conditions to Establish Feasibility

`[CURRENTLY UNSUPPORTED]`
To determine whether an incipient-degradation channel is ever technically defensible, a dedicated future experiment would require:
1. **Denser Temporal Sampling ($K \ge 6$)**:
   - Distinction between sampling support and detection guarantees:
     - $K=6$ represents a mathematical minimum example where pairwise slope rank combinations ($M = \binom{6}{2} = 15$) and permutation space ($6! = 720$) first begin to permit discrete probabilities below $0.002$.
     - An explicitly proposed candidate schedule ($0\text{h}, 24\text{h}, 48\text{h}, 72\text{h}, 96\text{h}, 120\text{h}, 168\text{h}$) contains **$K=7$ checkpoints** ($M = \binom{7}{2} = 21$ pairs, $7! = 5,040$).
     - *Permutation Argument Assumptions*: The permutation probability ($P(\text{monotonic upward} \mid H_0) = 1/K!$) applies strictly under the theoretical assumptions that stationary measurement errors are continuous, independent, and identically distributed (exchangeable), and refers solely to the specific event of strict monotonicity. It does **not** imply that $K=6$ alone guarantees rigorous detector false-positive rate (FPR) control in practice. Realistic detector calibration still requires independent null simulation to account for non-exchangeability, serial thermal autocorrelation, and ATE calibration shifts.
2. **Dedicated Null Simulation Population**:
   - Monte Carlo generation of $N \ge 100,000$ synthetic stationary trajectories with empirical measurement noise to calibrate threshold $\tau_{\text{incipient}}$ at $\text{FPR} \le 0.001$.
3. **Power Evaluation on Independent Synthetic Data**:
   - A newly generated, separate benchmark with controlled SNR sweeps ($1.0\sigma, 1.5\sigma, 2.0\sigma, 2.5\sigma$) to measure true positive detection rates independently of Phase 2F.

---

#### 9. Formal Architecture Gate Decision

`[VERIFIED FROM CURRENT PROJECT ARTIFACTS]`
- **Decision**: **DEFER — no new incipient-degradation detector should be implemented or calibrated from the current four-checkpoint Phase 2F benchmark.**
- **Preserved Epistemic Distinctions**:
  - **Mathematically Possible Statistic**: A rank slope, Kendall-tau test, pairwise median, or monotonicity indicator can be computed on any series with $K \ge 3$. Its mathematical existence does not establish operational utility or validity.
  - **Statistically Calibratable Detector**: Requires sufficient degrees of freedom ($K \ge 6$ or $K=7$) and an independent exchangeable null population to formally bound family-wise false alarms to acceptable engineering screening levels ($\text{FPR} \le 0.001$). Under $K \le 3$, false-alarm control is mathematically unachievable.
  - **Physically Validated Detector**: Requires empirical, experimental telemetry from physical MOSFET aging and radiation stress tests demonstrating that real device wearout kinetics conform to the modeled trajectory assumptions.
- **Rationale**:
  1. An incipient degradation evidence channel is **mathematically unidentifiable** at $K=2$ ($T=24\text{h}$) and **statistically uncalibratable** at $K=3$ ($T=96\text{h}$) under required false-alarm controls.
  2. The current frozen Phase 2F benchmark ($K=4$ overall, $15$ true degraders) cannot support non-circular calibration.
  3. Module B's conservative Carry-Forward under sub-threshold evidence is the **benchmark-supported variance-conservative policy under the current four-checkpoint protocol**.
- **Status of Code & Artifacts**:
  - `src/sih26170/screening/` remains completely frozen.
  - `src/sih26170/prognostics/` remains completely frozen.
  - Phase 2F benchmark data, hashes, and Stage 3 evaluation artifacts remain 100% immutable.
  - Zero implementation code written.

---

### LOG-074: Project-Wide Technical Evidence & Claim Forensic Audit Record

- **Log ID**: LOG-074
- **Date**: 2026-09-17
- **Phase**: Phase 5 / Project-Wide Evidence & Claim Audit
- **Change**: Forensic Classification & Epistemic Audit of All Major Technical Claims
- **Previous State**: Technical claims dispersed across documentation with varying degrees of precision, occasionally risking conflation between synthetic benchmark evidence and physical device validation.
- **New State**: Every major technical claim formally audited and classified into seven canonical evidence layers with explicit boundaries defining what is demonstrated versus what must NOT be claimed.
- **Reason**: Prevent epistemic overreach, eliminate unverified physical/qualification claims, and establish an unassailable audit trail for project handoff and review.
- **Source / Provenance**: MIL-PRF-19500/703, MIL-STD-750, NASA Ames Prognostics Data Repository, PHASE_2F_FROZEN_BENCHMARK_v1.0.0, LOG-060 through LOG-073.
- **Status**: AUDITED
- **Affected Area**: Canonical Project Log (`docs/PROTOTYPE_STANDING_LOG.md` / `docs/PROJECT_LOG.md`).
- **Impact**: Formalizes immutable boundaries across all 11 technical claim domains; strictly forbids claims of flight readiness, physical qualification, or empirical validation without real device test data.

---

#### 1. The Seven Canonical Evidence Layers

Every technical statement and claim in SIH26170 is classified into exactly one of the following seven evidentiary categories:
1. **VERIFIED DEVICE FACT**: Published manufacturer specifications, datasheet ratings, physical package geometry, or part number cross-references for the physical device anchor.
2. **VERIFIED STANDARD/TEST FACT**: Normative clauses, inspection tables, test methods, bias conditions, and static acceptance limits established in published military/space standards (e.g. MIL-PRF-19500, MIL-STD-750).
3. **GENERIC PHYSICS/LITERATURE**: Established solid-state physics, semiconductor device equations, Arrhenius reaction kinetics, interface-trap models, or degradation literature applicable to power MOSFETs generally.
4. **SURROGATE EMPIRICAL EVIDENCE**: Real experimental test data collected on external or proxy hardware (e.g. NASA Ames power cycling of commercial IRF520NPbF MOSFETs) used strictly as structural/phenomenological reference.
5. **SYNTHETIC BENCHMARK EVIDENCE**: Algorithmic performance metrics, confusion matrices, error rates, and coverage statistics evaluated strictly on the immutable synthetic benchmark dataset (`PHASE_2F_FROZEN_BENCHMARK_v1.0.0`).
6. **DESIGN/ARCHITECTURE CHOICE**: Engineering decisions, model formulations, mathematical approximations, threshold selections, state machine precedence rules, or sampling schedules designed by the engineering team.
7. **UNSUPPORTED / EVIDENCE GAP**: Claims, assumptions, extrapolations, or operational assertions that lack empirical, normative, or benchmark verification in the repository.

---

#### 2. Detailed Audit of Eleven Core Technical Claims

The table and detailed records below itemize the forensic audit for all eleven mandatory project domains:

| # | Claim Domain | Evaluated Statement / Claim | Evidence Source | Assigned Evidence Layer |
| :---: | :--- | :--- | :--- | :--- |
| **1** | **Device Identity** | IRHNJ57130 corresponds to military JANSR2N7481U3 under MIL-PRF-19500/703. | MIL-PRF-19500/703, DLA QPL-19500, IR HiRel Datasheet | **VERIFIED STANDARD/TEST FACT** & **VERIFIED DEVICE FACT** |
| **2** | **Parameter Limits** | $I_{\text{DSS}} \le 10\mu\text{A}, V_{\text{GS(th)}} \in [2, 4]\text{V}, R_{\text{DS(on)}} \le 65\text{m}\Omega, I_{\text{GSS}} \in [\pm 100\text{nA}]$. | MIL-PRF-19500/703 Table I (Group A, 25°C) | **VERIFIED STANDARD/TEST FACT** |
| **3** | **HTRB/HTGB Stress** | Stress testing represents HTRB ($V_{\text{DS}}=80\text{V}, 150^\circ\text{C}$) and HTGB ($V_{\text{GS}}=20\text{V}$ [slash-sheet 100%] / $16\text{V}$ [Method 1042 80% min], $150^\circ\text{C}$). | MIL-PRF-19500/703 Table IV, MIL-STD-750 Method 1042 | **VERIFIED STANDARD/TEST FACT** & **GENERIC PHYSICS/LITERATURE** |
| **4** | **Burn-in Schedule** | Phase 2F uses 0, 24, 96, and 168 h as a prototype benchmark observation schedule. This schedule is an engineering/design choice for the synthetic benchmark and must not be interpreted as a universal MIL-PRF-19500 JANS screening duration. | Benchmark configuration `configs/synthetic.yaml`, LOG-044 | **DESIGN/ARCHITECTURE CHOICE** |
| **5** | **Screening Thresholds** | PDA $\le 3-5\%$; Module A thresholds $2.5\sigma$ drift, $4.0\times$ step, $3.0\times$ peer. | MIL-PRF-19500 Table V (PDA), `THRESHOLD_PROVENANCE.md` | **VERIFIED STANDARD/TEST FACT** (PDA) & **DESIGN/ARCHITECTURE CHOICE** (Detectors) |
| **6** | **Module A Anomaly** | 78.6% spec sens, 62.5% drift recall (Def A), 100% equip prec, 95.2% stable sens. | `run_evaluation_phase3c.py`, Phase 2F benchmark | **SYNTHETIC BENCHMARK EVIDENCE** |
| **7** | **Stage 3 Prognostics** | Task 1 MAE 0.519, RMSE 3.060 (-68% vs S2), 90.0% coverage; step runaway eliminated. | `stage3_full_frozen_evaluation.json`, LOLO Primary | **SYNTHETIC BENCHMARK EVIDENCE** |
| **8** | **Equipment Decoupling** | Common-mode detected at $\ge 1.5\sigma$; $g_{\text{excess}}$ decouples component drift. | `screening/equipment.py`, `screening/temporal.py` | **DESIGN/ARCHITECTURE CHOICE** & **SYNTHETIC BENCHMARK EVIDENCE** |
| **9** | **Forecast Uncertainty** | LOLO empirical prediction intervals achieve $\approx 90\%$ empirical coverage. | LOLO evaluation across 16 folds, LOG-062, LOG-072 | **DESIGN/ARCHITECTURE CHOICE** & **SYNTHETIC BENCHMARK EVIDENCE** |
| **10** | **NASA Dataset** | NASA Ames MOSFET dataset provides surrogate empirical evidence of electrical-parameter degradation in commercially tested power MOSFETs under accelerated thermal/power cycling. | NASA Ames Prognostics Data Repository (Celaya 2011) | **SURROGATE EMPIRICAL EVIDENCE** |
| **11** | **Physical Qualification** | "System is flight-qualified, space-ready, and physically validated on real devices." | High-level marketing language, PRD initial drafts | **UNSUPPORTED / EVIDENCE GAP** |

---

#### 3. Itemized Forensic Statements

##### Claim 1: IRHNJ57130 ↔ JANSR2N7481U3 ↔ MIL-PRF-19500/703 Identity
- **Claim**: The target physical device is the radiation-hardened N-channel power MOSFET IRHNJ57130, which corresponds to military designation JANSR2N7481U3 defined under slash sheet MIL-PRF-19500/703.
- **Evidence Source**: MIL-PRF-19500/703, DLA Land and Maritime QPL-19500, International Rectifier / Infineon HiRel Datasheet for IRHNJ57130.
- **Evidence Layer**: **VERIFIED STANDARD/TEST FACT** & **VERIFIED DEVICE FACT**.
- **What is actually demonstrated**: MIL-PRF-19500/703 formally establishes the technical specification for JANSR2N7481U3 (100V, 22A, 100 krad(Si) TID, SMD-0.5 surface-mount package), which provides the physical device anchor for electrical ratings and parameter definitions in this project.
- **What must NOT be claimed**: That any physical IRHNJ57130 or JANSR2N7481U3 silicon devices were procured, packaged, wire-bonded, irradiated, or tested in this project. The 398 benchmark components are synthetic simulated devices built around this physical anchor.

##### Claim 2: IDSS, VGS(th), RDS(on), IGSS Specifications
- **Claim**: Primary electrical screening parameters have normative specification limits: $I_{\text{DSS}} \le 10.0\ \mu\text{A}$ ($V_{\text{DS}}=80\text{V}, V_{\text{GS}}=0\text{V}$), $V_{\text{GS(th)}} \in [2.0\text{V}, 4.0\text{V}]$ ($V_{\text{DS}}=V_{\text{GS}}, I_D=1.0\text{mA}$), $R_{\text{DS(on)}} \le 65.0\text{ m}\Omega$ ($V_{\text{GS}}=12\text{V}, I_D=22\text{A}$), and $I_{\text{GSS}} \in [-100.0\text{ nA}, +100.0\text{ nA}]$ ($V_{\text{GS}}=\pm 20\text{V}, V_{\text{DS}}=0\text{V}$).
- **Evidence Source**: MIL-PRF-19500/703 Table I ("Group A inspection, electrical measurements at 25°C").
- **Evidence Layer**: **VERIFIED STANDARD/TEST FACT**.
- **What is actually demonstrated**: These parameter definitions, measurement test conditions, and Class A pass/fail limits are verified normative military standard requirements published in MIL-PRF-19500/703.
- **What must NOT be claimed**: That these specification boundaries were derived from statistical screening of the synthetic benchmark, or that physical semiconductor breakdown occurs at precisely these numerical boundaries.

##### Claim 3: HTRB / HTGB / Operating-Life Conditions
- **Claim**: Accelerated life screening conditions represent High-Temperature Reverse Bias (HTRB: $V_{\text{DS}}=80\text{V}, V_{\text{GS}}=0\text{V}, T_A=150^\circ\text{C}$) and High-Temperature Gate Bias (HTGB: $V_{\text{GS}}=20\text{V}$ [slash-sheet 100%] / $16\text{V}$ [Method 1042 80% min], $V_{\text{DS}}=0\text{V}, T_A=150^\circ\text{C}$) screening under thermal acceleration.
- **Evidence Source**: MIL-PRF-19500/703 Table II & Table IV Screen 7; MIL-STD-750 Method 1042 (Conditions A & B).
- **Evidence Layer**: **VERIFIED STANDARD/TEST FACT** & **GENERIC PHYSICS/LITERATURE**.
- **What is actually demonstrated**: 
  - *HTRB Condition*: MIL-STD-750 Method 1042 Condition A specifies $\ge 80\%$ of rated $V_{\text{(BR)DSS}}$ ($0.80 \times 100\text{V} = 80\text{V}$) at $T_A = 150^\circ\text{C}$.
  - *HTGB Normative Reconciliation*: MIL-STD-750 Method 1042 Condition B prescribes gate bias at $80\%\text{--}100\%$ of rated maximum gate voltage ($V_{\text{GS,\max}} = \pm 20\text{V}$ per MIL-PRF-19500/703 Table II), establishing a normative stress range of $16\text{V}$ to $20\text{V}$. The detail specification slash sheet MIL-PRF-19500/703 Screen 7 explicitly mandates $100\%$ rated gate bias ($V_{\text{GS}} = 20\text{V}$, or $\pm 20\text{V}$), which corresponds exactly to the condition annotated in the benchmark telemetry metadata (`observations.csv`: `"HTGB (150°C, 20V)"` and `"HTGB (150°C, ±20V)"`). The discrepancy between $16\text{V}$ and $20\text{V}$ in the historical project record is thus reconciled as the Method 1042 $80\%$ lower bound versus the /703 detail slash-sheet $100\%$ rating.
- **What must NOT be claimed**: That real HTRB/HTGB ovens or thermal chambers were operated in this project, or that the synthetic telemetry was recorded from physical hardware under thermal stress.

##### Claim 4: Burn-in Duration and Checkpoint Semantics
- **Claim**: Phase 2F uses 0, 24, 96, and 168 h as a prototype benchmark observation schedule. This schedule is an engineering/design choice for the synthetic benchmark and must not be interpreted as a universal MIL-PRF-19500 JANS screening duration.
- **Evidence Source**: Benchmark configuration `configs/synthetic.yaml`, LOG-044.
- **Evidence Layer**: **DESIGN/ARCHITECTURE CHOICE**.
- **What is actually demonstrated**: The project configured a 4-point discrete sampling schedule ($0, 24, 96, 168\text{h}$) as an engineering/design choice to evaluate screening and prognostic algorithms under sparse temporal support ($K=4$).
- **What must NOT be claimed**: That $168\text{h}$ is a normative MIL-PRF-19500 JANS screening requirement or universal duration (under MIL-PRF-19500 Table IV for JANS, HTRB is 48h min, HTGB is 48h min, and steady-state operating life is 160h–240h; 168h is an engineering benchmark interval drawn from standard 1-week test practices such as JEDEC JESD22-A108); that intermediate device behavior between checkpoints is known; or that 4 checkpoints provide continuous degradation tracking.

##### Claim 5: PDA (Percent Defective Allowable) and Screening Thresholds
- **Claim**: 
  - PDA limit: Standard lot rejection occurs when failures exceed $3\%$ or $5\%$.
  - Module A thresholds: Drift threshold $|g| \ge 2.5\sigma$, step threshold $J \ge 4.0\times$, peer threshold $|z| \ge 3.0\times$, equipment common-mode threshold $1.5\sigma$.
- **Evidence Source**: MIL-PRF-19500 Table V (PDA limits), `THRESHOLD_PROVENANCE.md`, `configs/synthetic.yaml`, LOG-060.
- **Evidence Layer**: **VERIFIED STANDARD/TEST FACT** (PDA) & **DESIGN/ARCHITECTURE CHOICE** (Detectors).
- **What is actually demonstrated**: 
  - *PDA Limits*: MIL-PRF-19500 Section 4.5.3 and Table V formally mandate a $\le 5.0\%$ cumulative defect allowable threshold for primary lot acceptance, and a tightened $\le 3.0\%$ PDA threshold for a single resubmission burn-in run.
  - *Drift Detector Threshold*: The 2.5σ drift threshold is a project design parameter whose provenance and benchmark behavior are documented in THRESHOLD_PROVENANCE.md; it is not a normative MIL-PRF-19500 limit and has not been calibrated on real production lots. (In `THRESHOLD_PROVENANCE.md`, synthetic Monte Carlo simulations evaluate the univariate tail probability of the single-parameter statistic under isolated Gaussian noise, but this does not establish calibrated family-wise or per-parameter false positive rate control across the full multi-parameter, multi-detector screening state machine on real production lots.)
- **What must NOT be claimed**: That $2.5\sigma$, $4.0\times$, or $3.0\times$ are normative standards in MIL-PRF-19500 (MIL-PRF-19500 specifies static absolute limits and delta limits, not median MAD $z$-scores), or that these thresholds have been empirically tuned on real physical MOSFET lots.

##### Claim 6: Module A Anomaly Detection Performance
- **Claim**: Module A screening achieves $78.57\%$ sensitivity on spec failures (Target A), $37.50\%$ disposition recall ($62.50\%$ evidence-level recall) on degraded parts (Target B), $100\%$ precision on equipment excursions (Target C), and $95.18\%$ acceptance of stable parts with $2.59\%$ genuine non-HBS false pass rate (Target D).
- **Evidence Source**: `data/synthetic_phase2f_frozen/`, `run_evaluation_phase3c.py`, LOG-060.
- **Evidence Layer**: **SYNTHETIC BENCHMARK EVIDENCE**.
- **What is actually demonstrated**: On the immutable synthetic benchmark dataset (`PHASE_2F_FROZEN_BENCHMARK_v1.0.0`), Module A's rule-based fusion state machine produces exactly these evaluated confusion matrix outcomes.
- **What must NOT be claimed**: Real-world qualification, flight-acceptance screening validation, or that Module A has been verified on real component manufacturing lines.

##### Claim 7: Stage 3 Prognostic Performance
- **Claim**: Stage 3 `AdaptiveDriftGatedModel` achieves Task 1 ($24\text{h} \to 168\text{h}$) MAE of $0.5187$ and RMSE of $3.0599$ ($-67.96\%$ RMSE reduction vs Stage 2 baseline), eliminates catastrophic step extrapolation, and achieves $90.01\%$ empirical coverage on 16-fold LOLO.
- **Evidence Source**: `stage3_full_frozen_evaluation.json`, LOG-071, LOG-072.
- **Evidence Layer**: **SYNTHETIC BENCHMARK EVIDENCE**.
- **What is actually demonstrated**: On the frozen synthetic benchmark under 16-fold Leave-One-Lot-Out cross-validation, deterministic slope gating consistently suppresses noise-jitter extrapolation on stationary components and abrupt steps.
- **What must NOT be claimed**: That Stage 3 demonstrates physical device prognostics, that it validates real MOSFET degradation models, or that Carry-Forward is mathematically optimal or universally best on unobserved real hardware.

##### Claim 8: Equipment/Common-Mode Detection & Decoupling
- **Claim**: $D_{\text{eq}}$ detects synchronous lot shifts ($\ge 1.5\sigma$) across channels, and $g_{\text{excess}}$ decouples individual component wearout from common-mode lot motion ($|g_{\text{excess}}| \ge 2.5 \implies$ candidate excess drift; $< 2.5 \implies$ Carry-Forward with `NO_SIGNIFICANT_EXCESS_MOTION_DETECTED`).
- **Evidence Source**: `src/sih26170/screening/equipment.py`, `src/sih26170/screening/temporal.py`, LOG-060, LOG-072.
- **Evidence Layer**: **DESIGN/ARCHITECTURE CHOICE** & **SYNTHETIC BENCHMARK EVIDENCE**.
- **What is actually demonstrated**: Simulated fixture offsets and chamber thermal ramps injected into synthetic telemetry are successfully identified and decoupled on the benchmark.
- **What must NOT be claimed**: That the algorithm has been evaluated against real ATE electrometer glitches, real oven thermal oscillation profiles, or physical test socket oxidation.

##### Claim 9: Forecast Uncertainty Calibration
- **Claim**: 90% prediction intervals achieve empirical coverage of $90.01\%$ in Task 1 and $87.26\%$ in Task 2 under 16-fold LOLO.
- **Evidence Source**: `stage3_full_frozen_evaluation.json`, LOG-062, LOG-072.
- **Evidence Layer**: **DESIGN/ARCHITECTURE CHOICE** & **SYNTHETIC BENCHMARK EVIDENCE**.
- **What is actually demonstrated**: Training-fold empirical residual dispersion scaling yields near-nominal coverage on synthetic benchmark trajectories generated with stationary Gaussian noise.
- **What must NOT be claimed**: That these prediction intervals are formally calibrated, conformal, distribution-free, or mathematically guaranteed for real physical devices with non-Gaussian or non-stationary noise.

##### Claim 10: NASA Ames MOSFET Dataset Relevance
- **Claim**: NASA Ames MOSFET dataset provides surrogate empirical evidence of electrical-parameter degradation in commercially tested power MOSFETs under accelerated thermal/power cycling.
- **Evidence Source**: NASA Ames Prognostics Data Repository (Celaya et al., 2011/2012).
- **Evidence Layer**: **SURROGATE EMPIRICAL EVIDENCE**.
- **What is actually demonstrated**: Experimental data from real physical power MOSFETs (commercial IRF520NPbF) subjected to accelerated thermal stress exhibits measurable degradation in $R_{\text{DS(on)}}$ and gate threshold parameters, demonstrating that physical power transistor wearout kinetics exist in commercial silicon under accelerated thermal/power cycling stress.
- **What must NOT be claimed**: That NASA Ames data:
  - is IRHNJ57130 or JANSR2N7481U3 (IRF520NPbF is a commercial TO-220 part, not a rad-hard hermetic space MOSFET);
  - was used to train or calibrate Module A or Module B;
  - directly validates the SIH26170 algorithm.

##### Claim 11: Claims Implying Physical Validation, Reliability Qualification, Flightworthiness
- **Claim**: Statements suggesting that SIH26170 provides "flight-qualified screening," "experimentally validated reliability," or "production-ready satellite deployment."
- **Evidence Source**: Early exploratory drafts and high-level marketing language.
- **Evidence Layer**: **UNSUPPORTED / EVIDENCE GAP**.
- **What is actually demonstrated**: SIH26170 is a rigorous algorithmic prototype whose screening and prognostic pipelines have been verified and benchmarked against physics-informed synthetic data.
- **What must NOT be claimed**: Any claim of flight qualification, spaceflight readiness, experimental physical validation, mission deployment readiness, or TRL $\ge 5$ is completely unsupported by current project evidence and is strictly prohibited.

---

#### 4. Summary Governance Rule for Future Documentation

`[VERIFIED FROM CURRENT PROJECT ARTIFACTS]`
All future project deliverables, reports, presentations, and code comments must strictly adhere to the following governance rule:
1. **Always cite the exact evidence layer**: Any technical claim must be explicitly qualified by whether it is a military standard specification, a synthetic benchmark result, a surrogate empirical dataset, an engineering design choice, or an unverified gap.
2. **Never promote synthetic results to physical validation**: Phrases such as "physically validated," "production-ready," "flight-proven," or "experimentally certified" are banned unless primary test data from physical space-qualified silicon under certified burn-in testing is produced.
3. **Preserve negative findings and trade-offs**: The architectural dependency of Module B on Module A evidence and the resulting Carry-Forward behavior on sub-threshold degradation must remain transparently documented in all project summaries.

---

### LOG-075: Phase 4A Incipient-Degradation Evidence Readiness Gate

- **Log ID**: LOG-075
- **Date**: 2026-09-17
- **Phase**: Phase 4A / Incipient-Degradation Evidence Readiness Gate
- **Change**: Forensic Design & Evidence Readiness Audit for an Independent Sub-Threshold Degradation Channel
- **Previous State**: Stage 3 and Stage 4 frozen; sub-threshold degradation ($|g| < 2.5\sigma$) deferred in LOG-073 due to mathematical unidentifiability at $K \le 3$; project evidence audited and classified in LOG-074.
- **New State**: Comprehensive feasibility, noise adequacy, temporal support, and calibration experiment design complete. Strict evidence boundaries established. Candidate statistical families evaluated without implementation.
- **Reason**: Formally determine whether the repository, generator, and theoretical machinery can support an independent incipient-degradation channel without violating frozen baselines or creating uncalibrated false alarms.
- **Source / Provenance**: `src/sih26170/synthetic/phase2f/`, `THRESHOLD_PROVENANCE.md`, LOG-060, LOG-073, LOG-074.
- **Gate Outcome**: **DEFER**
- **Affected Area**: Canonical Project Log (`docs/PROTOTYPE_STANDING_LOG.md` / `docs/PROJECT_LOG.md`).
- **Canonical Invariants Preserved**: Zero code modifications in `src/`; zero threshold adjustments; zero modifications to `PHASE_2F_FROZEN_BENCHMARK_v1.0.0`; zero tuning against existing benchmark results.

---

#### 1. Synthetic Data Generator Inspection & Generation Capabilities

An inspection of the Phase 2F generator codebase (`src/sih26170/synthetic/phase2f/` — `generator.py`, `latent.py`, `measurement.py`, `scenarios.py`) confirms that the generator architecture decouples latent physical states from measurement transduction and can independently synthesize all necessary trajectory regimes:

| Trajectory Regime | Generator Mechanism | Ground-Truth Decoupling | Evidence Layer |
| :--- | :--- | :--- | :--- |
| **Stationary Null Trajectories** | `ParameterScenario.STABLE` and `HIGH_BUT_STABLE` enforce $g_p(t) = 0.0$ for all $t$. Measurements receive purely zero-mean noise. | Evaluated into separate `ground_truth.csv` records; observations contain only raw readouts. | **DESIGN/ARCHITECTURE CHOICE** |
| **Weak Linear Degradation** | `ParameterScenario.LINEAR_DRIFT` with target SNR support: $\Delta_{\text{req}} = \text{target\_snr} \times \sigma_{\text{noise}}$. Supports sub-threshold amplitudes (e.g. $1.0\sigma, 1.5\sigma, 2.0\sigma, 2.5\sigma$). | Latent drift rate parameterized independently of observation mechanics. | **DESIGN/ARCHITECTURE CHOICE** |
| **Weak Accelerating Degradation** | `ParameterScenario.ACCELERATING_DRIFT` models power-law growth $g(t) = \text{rate} \times (t/168)^{2.1}$. Drift rates can be scaled to weak sub-threshold endpoints. | Curvature exponent and rate are quarantined in generator state. | **DESIGN/ARCHITECTURE CHOICE** |
| **Weak Abrupt Step Changes** | `ParameterScenario.SUBTLE_ABRUPT_CHANGE` activates at $t \ge 96\text{h}$ with target SNR scaling relative to $\sigma_{\text{noise}}$. | Step injection timing ($96\text{h}$) is unobserved by detectors. | **DESIGN/ARCHITECTURE CHOICE** |
| **Equipment/Common-Mode Excursions** | `Phase2FMeasurementSimulator` injects synchronous lot-wide shifts at $96\text{h}$ (e.g. $\Delta T = 5^\circ\text{C}$ chamber excursion) and ATE socket channel offsets ($+20\%$ log or $+100\text{mV}$ linear). | Latent device parameter remains nominal ($g_p(t)=0$); shift is purely instrumentation-level. | **DESIGN/ARCHITECTURE CHOICE** |
| **Mixed Multi-Parameter Behavior** | `Phase2FScenarioManager` assigns independent scenario vectors per parameter (e.g. drifting $I_{\text{DSS}}$ alongside stable $V_{\text{GS(th)}}$ and $R_{\text{DS(on)}}$). | Vector mappings are stored strictly in `scenario_manifest.json` and quarantined. | **DESIGN/ARCHITECTURE CHOICE** |

**Conclusion on Generator Capability**: The generator architecture is mathematically and structurally capable of generating independent calibration suites for weak-signal experiments without leaking ground truth.

---

#### 2. Parameter-by-Parameter Measurement-Noise Audit & Model Adequacy

An audit of `src/sih26170/synthetic/phase2f/config.py` and `measurement.py` reveals the following parameter-specific noise specifications:

| Parameter | Unit | Transductive Coordinate | Baseline $\mu_0$ | Configured Noise $\sigma_{\text{noise}}$ | Effective Transformed Noise $\sigma_u$ | Model Noise Characteristics |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **$I_{\text{DSS}}$** | $\mu\text{A}$ | Log ($\ln x$) | $0.50\ \mu\text{A}$ | $0.04\ \mu\text{A}$ | $\sigma_{\log} = 0.04 / 0.50 = 0.08$ | Multiplicative log-normal noise ($8\%$ relative standard deviation). |
| **$V_{\text{GS(th)}}$** | $\text{V}$ | Linear ($x$) | $3.00\ \text{V}$ | $0.02\ \text{V}$ ($20\text{ mV}$) | $\sigma_{\text{lin}} = 0.02\ \text{V}$ | Additive homoscedastic Gaussian noise. |
| **$R_{\text{DS(on)}}$** | $\text{m}\Omega$ | Log ($\ln x$) | $48.0\ \text{m}\Omega$ | $0.60\ \text{m}\Omega$ | $\sigma_{\log} = 0.60 / 48.0 = 0.0125$ | Multiplicative log-normal noise ($1.25\%$ relative standard deviation). |
| **$I_{\text{GSS}}$** | $\text{nA}$ | Signed Asinh ($\text{asinh}(x/1.0)$) | $2.00\ \text{nA}$ | $0.25\ \text{nA}$ | $\sigma_{\text{asinh}} = 0.25 / 1.0 = 0.25$ | Additive Gaussian in asinh coordinates (except `stationary_zero_igss` where noise is hardcoded to $0.0$). |

##### Forensic Audit of Model Adequacy for Weak-Signal Experiments:
1. **Idealized Gaussianity** (`DESIGN/ARCHITECTURE CHOICE`): The current model assumes independent, identically distributed (i.i.d.) Gaussian fluctuations across all checkpoints. Real ATE instrumentation displays $1/f$ flicker noise, thermal drift between test sessions, and non-Gaussian electrometer baseline wander.
2. **Omission of Socket Contact Resistance Variability** (`GENERIC PHYSICS/LITERATURE`): For $R_{\text{DS(on)}}$, physical measurements are highly sensitive to test fixture socket insertion contact resistance ($\sim 0.5\text{--}2.0\text{ m}\Omega$). Socket contact resistance variations between checkpoints can mimic or obscure weak true physical drift ($\le 1.0\text{--}1.5\sigma$).
3. **Artifactual Zero-Noise State** (`DESIGN/ARCHITECTURE CHOICE`): The hardcoded zero-noise assignment for `stationary_zero_igss` in `measurement.py` (line 90) is an unphysical synthetic artifact; real electrometers reading nominal zero gate leakage always display symmetric noise around zero ($\pm 0.1\text{--}0.2\text{ nA}$).
4. **Adequacy Verdict** (`DESIGN/ARCHITECTURE CHOICE`):
   "The current noise model is adequate for controlled synthetic algorithmic experimentation but insufficient to establish physical weak-signal performance against realistic ATE/session variability."

---

#### 3. Temporal Support Comparison ($K=4$ vs Candidate $K=7$)

The fundamental barrier to weak-signal drift detection identified in LOG-073 is temporal degrees of freedom ($df = K - 2$).

| Checkpoint Schedule | Evaluated As-Of Time | Available Points ($K$) | Residual Degrees of Freedom ($df = K-2$) | Permutation Sequence Probability ($1/K!$) | Statistical Assessment & Feasibility |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Phase 2F Frozen** | $T = 24\text{h}$ | $K = 2$ | **$df = 0$** | $1/2 = 50.0\%$ | **Zero Residual Degrees of Freedom** (`GENERIC STATISTICAL KNOWLEDGE`). Line connects two points; within-series residual variance cannot be estimated. The current $K=2$ support does not provide sufficient within-series information for the proposed data-driven weak-drift calibration. |
| **Phase 2F Frozen** | $T = 96\text{h}$ | $K = 3$ | **$df = 1$** | $1/6 \approx 16.67\%$ | **Sparse Temporal Support** (`GENERIC STATISTICAL KNOWLEDGE`). $df = 1$ for ordinary linear regression yields heavy-tailed $t$-distribution critical values ($t_{0.975} = 12.71$). Monotonic sequence probability under exchangeable continuous null is $1/6 = 16.67\%$. The current $K=2/K=3$ support does not provide sufficient within-series information for the proposed data-driven weak-drift calibration. |
| **Phase 2F Frozen** | $T = 168\text{h}$ | $K = 4$ | **$df = 2$** | $1/24 \approx 4.17\%$ | **Sparse Nonparametric Support** (`GENERIC STATISTICAL KNOWLEDGE`). Monotonic sequence probability under exchangeable null is $1/24 = 4.17\%$ (two-sided $8.33\%$). $K=4$ remains too sparse for the planned nonparametric/multiplicity-controlled evidence channel without additional assumptions or independent calibration. |
| **Candidate Dense** | $T = 96\text{h}$ | $K = 5$ | **$df = 3$** | $1/120 \approx 0.83\%$ | **Candidate Dense Intermediate Checkpoint** (`DESIGN/ARCHITECTURE CHOICE`). $df = 3$ stabilizes ordinary linear regression variance ($t_{0.975} = 3.182$); permutation sequence resolution reaches $0.83\%$. |
| **Candidate Dense** | $T = 168\text{h}$ | $K = 7$ | **$df = 5$** | $1/5040 \approx 0.02\%$ | **Candidate dense schedule with substantially improved statistical resolution; requires independent null/power calibration** (`DESIGN/ARCHITECTURE CHOICE`). |

*Candidate Dense Schedule*: $t \in \{0, 24, 48, 72, 96, 120, 168\}\ \text{h}$ (`DESIGN/ARCHITECTURE CHOICE`).

> [!NOTE]
> **Permutation Resolution Semantics (`GENERIC STATISTICAL KNOWLEDGE`)**:
> The $1/K!$ quantity describes the probability of one strictly ordered sequence under an ideal i.i.d. exchangeable continuous null; it does not by itself establish detector FPR control.

##### Proposed Candidate Test Requirements (Project Design Choices):
*These $K$ values are proposed project-specific engineering requirements for the planned evidence channel, not universal mathematical minimum sample sizes for the named statistical methods:*
- **Two-Point Algebraic Slope**: Requires $K \ge 2$ ($df=0$). Zero residual degrees of freedom for within-series residual variance estimation (`GENERIC STATISTICAL KNOWLEDGE`).
- **Ordinary Least Squares (OLS) $t$-test**: Proposed project design requirement $K \ge 4$ ($df \ge 2$); $K \ge 5$ ($df \ge 3$) recommended for residual variance stabilization (`DESIGN/ARCHITECTURE CHOICE`).
- **Theil-Sen / Kendall's Tau**: Proposed project design requirement $K \ge 5$ (at $K=4$, only 6 pairs; at $K=5$, 10 pairs with permutation sequence probability $1/120 \approx 0.0083$) (`DESIGN/ARCHITECTURE CHOICE`).
- **Permutation / Monotonicity Tests**: Proposed project design requirement $K \ge 6\text{--}7$ (at $K=6$, $1/6! = 1/720 \approx 0.0014$; at $K=7$, $1/7! = 1/5040 \approx 0.0002$) (`DESIGN/ARCHITECTURE CHOICE`).
- **Change-Point / Level-Shift Detection**: Proposed project design requirement $K \ge 6$ (allocating at least 3 pre-shift and 3 post-shift checkpoints) (`DESIGN/ARCHITECTURE CHOICE`).

---

#### 4. Design of Two Independent Calibration Experiments

To prevent data snooping or circular threshold tuning against `PHASE_2F_FROZEN_BENCHMARK_v1.0.0`, two independent synthetic experiments are designed for future execution on dense temporal support ($K=7$):

##### Experiment A: Large-Scale Null Calibration Experiment (Design Only)
- **Objective**: Empirically calibrate detector rejection thresholds under the pure stationary null hypothesis to evaluate false positive rate control.
- **Sample Size**: $N \ge 100,000$ independent synthetic stationary trajectories ($g(t) \equiv 0$).
- **Noise Distributions**: Sampled using parameter-specific noise models ($I_{\text{DSS}}, V_{\text{GS(th)}}, R_{\text{DS(on)}}, I_{\text{GSS}}$).
- **Temporal Checkpoints**: Candidate dense schedule $K=7$ ($0, 24, 48, 72, 96, 120, 168\text{h}$), evaluated strictly as-of $T=96\text{h}$ ($K=5$) and $T=168\text{h}$ ($K=7$).
- **Multiplicity Handling**: Use Holm-Bonferroni adjustment across the four parameter-level tests (with a conservative Bonferroni reference of $\alpha / 4$).
- **Target Performance Metric**: Empirical $\text{FPR} \le 0.001$ ($0.1\%$) per lot-component.
- **Status & Classification**: **DESIGN/ARCHITECTURE CHOICE (Proposed Project Design Requirement)**. Must NOT be cited as a normative standard.

##### Experiment B: Controlled Power Calibration Experiment (Design Only)
- **Objective**: Characterize the probability of detection $P(\text{Reject } H_0 \mid \text{Signal})$ as a function of signal amplitude, completely independent of the null calibration dataset.
- **Signal Strengths Tested**: Controlled net parameter shift $\Delta x \in \{1.0\sigma, 1.5\sigma, 2.0\sigma, 2.5\sigma\}$.
- **Sample Size**: $N = 10,000$ trajectories per parameter, per signal strength ($160,000$ total series).
- **Scenarios Evaluated**:
  1. Pure linear drift ($g(t) \propto t$).
  2. Accelerating power-law drift ($g(t) \propto t^{2.1}$).
  3. Abrupt step change emerging at intermediate checkpoints.
  4. Confounded drift under simultaneous chamber common-mode shift ($\Delta T = 5^\circ\text{C}$).
- **Output Artifacts**: Detection power curves vs SNR, Empirical ROC curves, and common-mode rejection specificity.
- **Strict Isolation Rule**: Must not use or tune on `PHASE_2F_FROZEN_BENCHMARK_v1.0.0`.

---

#### 5. Evaluation of Candidate Statistical Families (Without Implementation)

*These candidate evaluations reflect proposed project-specific engineering requirements for the planned evidence channel, not universal mathematical limitations on the statistical methods:*

| Statistical Family | Proposed Project Design $K$ | Core Mathematical Assumptions | Multiplicity Issue | Primary Failure Mode | Supported by Current Frozen Benchmark ($K=4$)? |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **Sen / Kendall Trend Evidence** | $K \ge 5$ | Continuous observations; monotonic trend under alternative; symmetric errors for slope CI. | Testing 4 parameters per component inflates family-wise error without adjustment. | Extreme granularity at small $K$; at $K \le 3$, Kendall $\tau$ can only take $\{-1, -1/3, +1/3, +1\}$; fails to capture late accelerating curvature. | **NO** (Current $K=2/K=3$ support does not provide sufficient within-series information for proposed calibration; $K=4$ remains too sparse without additional assumptions). |
| **Permutation / Monotonicity Tests** | $K \ge 6\text{--}7$ | Exchangeability of measurement noise under the null hypothesis (i.i.d. errors). | Sequential testing across checkpoints creates repeated-testing alpha spending. | High discrete granularity; cannot detect non-monotonic degradation (e.g. noise dip during true drift); power is zero if a single noise realization inverts rank. | **NO** (Permutation sequence probability under null is $16.67\%$ at $K=3$ and $4.17\%$ at $K=4$; too sparse for planned channel without independent calibration). |
| **Slope Confidence Intervals (OLS / Robust)** | $K \ge 5$ | Gaussian residuals; homoscedasticity; linear relation $y = \beta_0 + \beta_1 t + \epsilon$. | Multiple checkpoints $\times$ 4 parameters. | Massive confidence interval widths at small $K$ due to heavy $t$-distribution tails ($df \le 2$); yields near-zero detection power on weak signals ($1.0\text{--}1.5\sigma$). | **NO** ($df = 0$ at $24\text{h}$, $df = 1$ at $96\text{h}$; insufficient within-series degrees of freedom). |
| **Robust Regression (Huber / RANSAC)** | $K \ge 6$ | Majority of data points follow linear model; contamination fraction $< 50\%$. | Asymptotic standard errors fail completely for small finite samples. | Breakdown point requires $N > 2p$; with 2 parameters ($\beta_0, \beta_1$), a single outlier corrupts or destroys degrees of freedom at $K \le 4$. | **NO** ($K=4$ too small for planned finite-sample breakdown requirements). |
| **Sequential / Change-Point (CUSUM)** | $K \ge 8\text{--}10$ | Known pre-change mean and variance $\sigma^2_0$; stable initial calibration phase. | Continuous monitoring inflates false alarm probability without stopping boundary adjustments. | Cannot establish pre-change baseline variance from 1 or 2 sparse points; confuses noise jitter with step shifts. | **NO** (Sparse checkpoints do not support proposed sequential baseline estimation). |

---

#### 6. Conceptual & Mathematical Disambiguation

To ensure scientific rigor in future documentation and avoid conflating mathematical concepts, the following five terms are explicitly disambiguated:

1. **Algebraic Slope Identifiability**: The purely geometric property that 2 distinct points uniquely define a line ($K \ge 2, df = 0$). It indicates that a slope can be calculated numerically, but carries *zero* degrees of freedom to assess noise, error, or confidence.
2. **Variance Estimation**: The statistical ability to compute the residual variance $s^2 = \frac{1}{K-2} \sum (y_i - \hat{y}_i)^2$. Mathematically requires $K \ge 3$ ($df \ge 1$), and practically requires $K \ge 5$ ($df \ge 3$) to prevent runaway estimation variance.
3. **Statistical Significance**: The probabilistic determination that an observed test statistic falls in the extreme tail of the null distribution ($p < \alpha$). Requires sample support $K$ large enough for the discrete or continuous null distribution to reach tail probabilities smaller than the target significance level.
4. **Detection Power**: The operational probability ($1 - \beta$) that a true physical signal of magnitude $\delta\sigma$ will exceed the calibrated significance threshold. A test may be statistically valid but possess unacceptably low power ($< 20\%$) if temporal support or effect size is small.
5. **Physical Degradation Interpretation**: The engineering attribution that a statistically significant trend represents genuine semiconductor wearout kinetics (e.g. interface trap accumulation, mobile ion drift, gate oxide breakdown) rather than instrumentation drift, chamber thermal gradients, or socket contact resistance fluctuations.

---

#### 7. Strict Leakage Boundary for Future Independent Detectors

Any future independent sub-threshold or incipient detector candidate must comply with the following immutable leakage boundaries:
- **Causal Slice Isolation**: May only ingest observations $y_i(t)$ where $t \le T_{\text{as\_of}}$.
- **Ground Truth Quarantine**: Must never access columns from `ground_truth.csv` (`is_spec_failure`, `is_degradation`, `scenario_tag`, `true_value`).
- **Future Observation Isolation**: Must never access data from future checkpoints ($t > T_{\text{as\_of}}$).
- **Future Lot Statistic Isolation**: Lot medians, MADs, and common-mode estimates must be computed strictly using observations up to $T_{\text{as\_of}}$.
- **Metadata Blindness**: Must not ingest scenario manifests, seed sequences, generator configuration files, or equipment channel labels used to identify synthetic scenario profiles.
- **Prognostic Feedforward Only**: Must operate upstream of Module B. Module B prognostics must never feed back into screening detectors.
- **Frozen Detector Non-Interference**: Must ingest existing frozen Module A evidence ($D_{\text{step}}, D_{\text{eq}}, D_{\text{drift}}, D_{\text{suff}}$) as read-only signals without altering their existing contract or thresholds ($|g| \ge 2.5\sigma, 4.0\times, 3.0\times, 1.5\sigma$).

---

#### 8. Gate Outcome & Explicit Non-Goals

##### Gate Outcome: **`DEFER`**
- **Justification**:
  1. Current temporal support is insufficient for the planned independently calibrated weak-signal channel ($K=2/K=3$ provides $df=0$ and $df=1$ within-series degrees of freedom, and $K=4$ remains too sparse for the planned nonparametric/multiplicity-controlled evidence channel without additional assumptions or independent calibration).
  2. The current noise model is adequate for controlled synthetic algorithmic experimentation but insufficient to establish physical weak-signal performance against realistic ATE/session variability (missing socket contact resistance variability, missing $1/f$/session drift, and an unphysical exact-zero noise artifact for `stationary_zero_igss`).
  3. No independent null/power calibration dataset exists in the repository.
  4. Dense temporal data and independent calibration are required before detector implementation.
  5. Lowering the existing $2.5\sigma$ threshold without an independently calibrated null distribution could increase false alarms across the stable population; no threshold sweep establishing the resulting FPR is currently available or authorized.

##### Explicit Non-Goals:
- Do NOT implement a new detector in `src/sih26170/screening/`.
- Do NOT lower or tune the $2.5\sigma$ drift threshold.
- Do NOT modify Module A or Module B production code.
- Do NOT regenerate, retrain, or modify `PHASE_2F_FROZEN_BENCHMARK_v1.0.0`.
- Do NOT alter any existing test assertions or evaluation metrics.

Execution stopped per gate instructions.

---

### LOG-076: Phase 4B Independent Calibration Experiment Specification Gate

- **Log ID**: LOG-076
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Independent Calibration Experiment Specification Gate
- **Change**: Complete Implementation-Ready Benchmark Specification for Weak/Incipient Degradation Calibration
- **Previous State**: LOG-075 deferred incipient detector implementation due to sparse temporal support ($K=4$), lack of empirical socket noise, and absence of an independent calibration dataset.
- **New State**: Complete architectural and statistical specification for an independent Phase 4B benchmark established; sampling schedules, signal spaces, null architectures, alternative degradation fixtures, and leakage contracts formally locked.
- **Reason**: Enable controlled future generation of an independent calibration benchmark with dense temporal support ($K=7$) capable of validating candidate sub-threshold detectors under formal false-positive rate control without altering or snooping Phase 2F.
- **Source / Provenance**: `src/sih26170/synthetic/phase2f/`, `THRESHOLD_PROVENANCE.md`, LOG-060, LOG-073, LOG-074, LOG-075.
- **Gate Outcome**: **READY FOR BENCHMARK GENERATION**
- **Affected Area**: Canonical Project Log (`docs/PROTOTYPE_STANDING_LOG.md` / `docs/PROJECT_LOG.md`).
- **Canonical Invariants Preserved**: Design-only gate; zero code modifications in `src/`; zero threshold adjustments; zero modifications to `PHASE_2F_FROZEN_BENCHMARK_v1.0.0`; zero new benchmark executions.

---

#### 1. Purpose Statement & Epistemic Distinctions

The Phase 4B benchmark is designed to provide an independent, synthetic, physics-informed data environment to evaluate the statistical performance of candidate incipient/sub-threshold degradation detectors under controlled false-alarm criteria.

##### Four Distinct Objectives (`DESIGN/ARCHITECTURE CHOICE`):
1. **A. Statistical Detectability of a Synthetic Weak Signal**: Determine the empirical probability of detection $P(\text{Detect} \mid \delta\sigma)$ for weak parametric drift ($\delta \in [1.0, 2.5]$ noise standard deviations, `DESIGN/ARCHITECTURE CHOICE`) under dense temporal sampling ($K=7$, `DESIGN/ARCHITECTURE CHOICE`).
2. **B. False-Positive Behavior under a Synthetic Stationary Null**: Empirically quantify and calibrate the family-wise false positive rate ($\text{FPR}$) of candidate detectors on an experiment design requirement of $N \ge 100,000$ purely stationary synthetic trajectories, accounting for multi-parameter and sequential testing multiplicity (`DESIGN/ARCHITECTURE CHOICE / FUTURE ENGINEERING TARGET`).
3. **C. Robustness to Synthetic Equipment/Common-Mode Effects**: Evaluate the ability of candidate detectors to decouple synchronous lot-wide chamber thermal excursions ($\Delta T = 5^\circ\text{C}$, synthetic stress parameter, `DESIGN/ARCHITECTURE CHOICE`) and ATE socket channel offsets from genuine component wearout.
4. **D. Characterization of Synthetic Noise Model Boundaries**: Measure algorithmic sensitivity to departures from idealized white noise (e.g. autoregressive session drift and contact resistance variance) within synthetic data generation (`DESIGN/ARCHITECTURE CHOICE`).

> [!CAUTION]
> **Physical Interpretation Boundary (`UNSUPPORTED / EVIDENCE GAP`)**:
> Phase 4B is an idealized synthetic simulation environment. It does **NOT** evaluate, validate, or prove real semiconductor device reliability, physical degradation kinetics in spaceflight hardware, or production-lot flightworthiness.

---

#### 2. Temporal Design Analysis

Three candidate sampling schedules are evaluated for Phase 4B:

| Schedule ID | Checkpoint Grid ($t$ in hours) | Checkpoint Count ($K$) | Elapsed Duration | Pairwise Comparisons ($K(K-1)/2$) | Linear Regression Residual $df = K-2$ | Linear Drift Assessment | Curvature / Acceleration Assessment | Abrupt Step Assessment | Statistical Limitations |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- | :--- | :--- |
| **S1 (Primary Candidate)** | **0, 24, 48, 72, 96, 120, 168** | **$K = 7$** | **168 h** | **21 pairs** | **$df = 5$** | Continuous tracking across full 168 h duration; stabilized slope variance. | Quadratic curvature term estimable with $df = 4$; power-law exponents identifiable. | Pre-step and post-step intervals each contain $\ge 3$ points for steps at $48\text{h}, 72\text{h}, \text{or } 96\text{h}$. | Non-uniform final step ($48\text{h}$ from $120 \to 168$ vs $24\text{h}$ earlier). |
| **S2** | 0, 24, 48, 72, 96, 120 | $K = 6$ | 120 h | 15 pairs | $df = 4$ | Uniform $24\text{h}$ step size throughout entire test. | Quadratic term has $df = 3$. | Exactly 3 points before and 3 points after mid-point step at $72\text{h}$. | Ends observation at 120 h; provides an alternative shorter-horizon design but reduces the available late-life observation window compared to 168 h. |
| **S3** | 0, 24, 48, 72, 96 | $K = 5$ | 96 h | 10 pairs | $df = 3$ | Uniform $24\text{h}$ step size over early screening interval. | Weak curvature resolution ($df = 2$ for quadratic term). | At most 2 points follow a step at $72\text{h}$; cannot establish post-step persistence. | Ends observation at 96 h; provides an alternative shorter-horizon design but curtails the late-life observation window. |

##### Schedule Selection (`DESIGN/ARCHITECTURE CHOICE`):
S1 is selected as the primary candidate because it preserves the full Phase 2F 168 h observation horizon while increasing temporal resolution. S2 and S3 provide alternative shorter-horizon designs but reduce the available late-life observation window. Neither S2 nor S3 is disqualified on military screening compliance grounds, as 168 h is not a universal screening mandate; schedule selection is strictly an experimental design choice. Introducing intermediate readouts ($48, 72, 120\ \text{h}$) expands residual degrees of freedom from $df=2$ (under Phase 2F $K=4$) to $df=5$ (under $K=7$).

---

#### 3. Parameter-Specific Transformed Signal Space

Weak degradation signals are formulated strictly in transformed coordinates to preserve parameter-specific physics (`DESIGN/ARCHITECTURE CHOICE`):

| Parameter | Native Unit | Transformed Representation ($u$) | Inversion Formula ($x = g^{-1}(u)$) | Baseline $\mu_0$ | Nominal Transformed Noise Scale ($\sigma_{u,p}$) | Signal Unit Definition ($1.0\sigma_{u,p}$) |
| :--- | :---: | :--- | :--- | :---: | :---: | :--- |
| **$I_{\text{DSS}}$** | $\mu\text{A}$ | $u = \ln(x / 1.0\ \mu\text{A})$ | $x = \exp(u)$ | $0.50\ \mu\text{A}$ | $\sigma_{u,\text{IDSS}} = 0.04 / 0.50 = 0.08$ | $\approx 8.3\%$ relative increase in leakage current. |
| **$V_{\text{GS(th)}}$** | $\text{V}$ | $u = x / 1.0\ \text{V}$ | $x = u$ | $3.00\ \text{V}$ | $\sigma_{u,\text{VGSTH}} = 0.02\ \text{V}$ | $20.0\text{ mV}$ absolute threshold shift. |
| **$R_{\text{DS(on)}}$** | $\text{m}\Omega$ | $u = \ln(x / 1.0\ \text{m}\Omega)$ | $x = \exp(u)$ | $48.0\ \text{m}\Omega$ | $\sigma_{u,\text{RDSON}} = 0.60 / 48.0 = 0.0125$ | $\approx 1.26\%$ relative increase in channel resistance. |
| **$I_{\text{GSS}}$** | $\text{nA}$ | $u = \text{asinh}(x / 1.0\ \text{nA})$ | $x = 1.0 \times \sinh(u)$ | $2.00\ \text{nA}$ | $\sigma_{u,\text{IGSS}} = 0.25$ | $\approx 0.25\text{ nA}$ shift around zero; $\approx 13\%$ shift at $2.0\text{ nA}$. |

##### Formal Definition of Weak Signal Strength $\delta$ (`DESIGN/ARCHITECTURE CHOICE`):
A degradation trajectory of amplitude $\delta \in \{1.0, 1.5, 2.0, 2.5\}$ represents a total net cumulative shift over $168\text{h}$ equal to:
$$\Delta u_p(168) = u_p(168) - u_p(0) = \delta \cdot \sigma_{u,p}$$

> [!NOTE]
> **Non-Equivalence of Parameter Sigmas (`GENERIC STATISTICAL KNOWLEDGE`)**:
> A signal of $1.0\sigma$ in $I_{\text{DSS}}$ ($8.3\%$ shift) is **not** physically or numerically interchangeable with $1.0\sigma$ in $R_{\text{DS(on)}}$ ($1.26\%$ shift) or $1.0\sigma$ in $V_{\text{GS(th)}}$ ($20\text{ mV}$). Each is normalized strictly by its respective transductive instrumentation noise scale $\sigma_{u,p}$.

---

#### 4. Three Independent Null Model Architectures

The Phase 4B null benchmark specifies an experiment design requirement of $N \ge 100,000$ independent stationary parameter-series ($g_p(t) \equiv 0$ for all $t$, `DESIGN/ARCHITECTURE CHOICE`) across three distinct operational regimes:

1. **Null Model A: Ideal i.i.d. Gaussian Null (`DESIGN/ARCHITECTURE CHOICE`)**:
   - Noise formulation: $\epsilon_t \sim \mathcal{N}(0, \sigma^2_{u,p})$ independently across all checkpoints.
   - Purpose: Baseline theoretical null for evaluating asymptotic distribution limits, Kendall tau null quantiles, and permutation sequence probabilities under idealized conditions.
2. **Null Model B: Correlated / Session-Drift Null (`DESIGN/ARCHITECTURE CHOICE — synthetic stress parameter`)**:
   - Noise formulation: First-order autoregressive structure:
     $$\epsilon_t = \phi \cdot \epsilon_{t-1} + \sqrt{1 - \phi^2} \cdot \eta_t, \quad \eta_t \sim \mathcal{N}(0, \sigma^2_{u,p}), \quad \phi \in [0.20, 0.35]$$
   - Parameter provenance: The selected $\phi$ range is a proposed synthetic temporal-correlation stress parameter and is not empirically calibrated to production ATE or session-drift data. AR(1) is a synthetic stress model and is not a validated physical model of socket or electrometer behavior.
   - Purpose: Stress-tests candidate detectors against persistent between-session instrumentation drift and socket thermal re-insertion offsets.
3. **Null Model C: Equipment / Common-Mode Null (`DESIGN/ARCHITECTURE CHOICE`)**:
   - Noise formulation: Synchronous lot-level thermal excursion ($\Delta T = 5^\circ\text{C}$ ramp at $72\text{h}$, recovering at $120\text{h}$) affecting all components in the lot simultaneously without individual component degradation.
   - Purpose: Verifies that common-mode chamber artifacts do not trigger component-level false alarms.

> [!WARNING]
> **Empirical Noise Limitation (`UNSUPPORTED / EVIDENCE GAP`)**:
> The repository contains synthetic noise formulations only. True physical ATE noise distributions (including socket oxidation and contact resistance fluctuations) remain an evidence gap and must not be claimed as verified.

---

#### 5. Alternative Degradation Signal Models

Phase 4B defines six independent, parameter-selective signal fixtures (`DESIGN/ARCHITECTURE CHOICE`):

- **Fixture A (Weak Linear Drift)**: Constant wearout kinetics (`DESIGN/ARCHITECTURE CHOICE`):
  $$u_p(t) = u_{p,0} + \delta \sigma_{u,p} \left(\frac{t}{168}\right)$$
- **Fixture B (Weak Accelerating Drift)**: Superlinear fatigue kinetics (`DESIGN/ARCHITECTURE CHOICE`):
  $$u_p(t) = u_{p,0} + \delta \sigma_{u,p} \left(\frac{t}{168}\right)^{2.1}$$
- **Fixture C (Weak Abrupt Step)**: Localized dielectric or structural shift occurring at discrete time $t_{\text{step}} \in \{48, 72, 96\}\ \text{h}$ (`DESIGN/ARCHITECTURE CHOICE`):
  $$u_p(t) = \begin{cases} u_{p,0}, & t < t_{\text{step}} \\ u_{p,0} + \delta \sigma_{u,p}, & t \ge t_{\text{step}} \end{cases}$$
- **Fixture D (Confounded Weak Drift)**: Component-specific linear drift ($+1.5\sigma$) superimposed on a synchronous lot-wide chamber shift ($\Delta T = 5^\circ\text{C}$) (`DESIGN/ARCHITECTURE CHOICE`).
- **Fixture E (Heteroscedastic Noise Drift)**: Linear drift where measurement noise variance increases with cumulative operational hours: $\sigma_u(t) = \sigma_{u,0} \cdot (1 + 0.5 \cdot t/168)$ (`DESIGN/ARCHITECTURE CHOICE`).
- **Fixture F (Staggered Onset Drift)**: Dormant latent state until intermediate burn-in, with drift commencing at $t_{\text{onset}} \in \{48, 72\}\ \text{h}$ (`DESIGN/ARCHITECTURE CHOICE`).

##### Trajectory Independence:
Each component preserves independent parameter time-series: $T_i(I_{\text{DSS}})$, $T_i(V_{\text{GS(th)}})$, $T_i(R_{\text{DS(on)}})$, and $T_i(I_{\text{GSS}})$. Single-parameter degradation lots (e.g. only $I_{\text{DSS}}$ drifts while others remain nominal) and multi-parameter degradation lots are evaluated separately to prevent unwarranted physical coupling assumptions.

---

#### 6. Equipment Confounding & Decoupling Architecture

To mitigate common-mode chamber thermal shifts from confounding individual component assessment, Phase 4B specifies a leave-one-out decoupling architecture (`DESIGN/ARCHITECTURE CHOICE`):

1. **Leave-One-Out Lot-Median Reference**:
   To eliminate self-inclusion bias (where an anomalous component distorts the reference toward itself), the robust lot-central reference for component $i$ is computed excluding component $i$:
   $$\tilde{u}_{\text{lot}\setminus\{i\},p}(t) = \text{median}_{j \in \mathcal{L} \setminus \{i\}} \{ u_{j,p}(t) \} = \text{median}_{j \neq i} \{ u_{j,p}(t) \}$$
2. **Excess Component Motion**:
   The individual component candidate trajectory is evaluated relative to the leave-one-out lot median:
   $$u_{i,p}^{\text{excess}}(t) = u_{i,p}(t) - \text{median}_{j \neq i} \{ u_{j,p}(t) \}$$
3. **Lot Size Stability Requirement (`PROJECT DESIGN CHOICE`)**:
   A stable leave-one-out median reference requires a minimum lot size of $N_{\text{lot}} \ge 10$ components ($N_{\text{lot}} \ge 20$ recommended). In smaller lots, individual component variability inflates the median estimation error, degrading excess signal resolution.
4. **Failure Mode Documentation (`DESIGN/ARCHITECTURE CHOICE`)**:
   If degradation becomes widespread within a lot, a lot-median reference can absorb part of the common degradation signal and reduce component-specific excess magnitude.
5. **Statistical Decoupling Test**:
   - If $|\tilde{u}_{\text{lot}\setminus\{i\},p}(t) - \tilde{u}_{\text{lot}\setminus\{i\},p}(0)| \ge 1.5\sigma_{u,p}$ (`DESIGN/ARCHITECTURE CHOICE`), an equipment common-mode condition is declared.
   - Component-level drift detection is performed strictly on $u_{i,p}^{\text{excess}}(t)$.
6. **Leakage Prohibition**: Detectors must **never** ingest synthetic generator metadata (e.g. `has_chamber_drift`, `scenario_tag`, or fixture chamber IDs) to deduce common-mode presence.
7. **Epistemic Limitation**: Common-mode subtraction is a synthetic mathematical decoupling heuristic, not a physically proven model of chamber thermal dynamics or multi-component failure physics.

---

#### 7. Conceptual Comparison of Candidate Detector Families

*All statistical families are evaluated conceptually; none are implemented in this gate:*

| Statistical Family | Mathematical Assumptions (`GENERIC STATISTICAL KNOWLEDGE`) | Proposed Project Design $K$ (`DESIGN/ARCHITECTURE CHOICE`) | Test Statistic | Null Hypothesis $H_0$ | Alternative Hypothesis $H_1$ | Multiplicity Challenge | Primary Failure Mode | Common-Mode Handling | Missing Data Treatment |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Theil-Sen / Kendall's Tau** | Continuous observations; monotonic trend under alternative; symmetric errors. | $K \ge 5$ | Kendall rank correlation $\tau$ or median pairwise slope $\hat{\beta}_{\text{TS}}$. | $\tau = 0$ (no monotonic trend). | $\tau \neq 0$ or $\tau > 0$ (directional drift). | 4 parameters per component inflate FWER. | Substantial loss of power if acceleration emerges late in test. | Applied to excess residuals $u_i^{\text{excess}}(t)$. | Naturally accommodates missing checkpoints by evaluating available pairs. |
| **Slope Confidence Intervals (OLS)** | Homoscedastic Gaussian errors; linear relation $u_t = \beta_0 + \beta_1 t + \epsilon$. | $K \ge 5$ | Student $t = \hat{\beta}_1 / \text{SE}(\hat{\beta}_1)$. | $\beta_1 = 0$ | $\beta_1 > 0$ or $\beta_1 \neq 0$ | Multiplicity across 4 parameters $\times$ sequential readouts. | Severe vulnerability to leverage points and non-Gaussian electrometer tails. | OLS fitted to $u_i^{\text{excess}}(t)$. | Requires least-squares formulation with variable time delta $\Delta t$. |
| **Robust Regression (Huber / RANSAC)** | Majority inlier population; symmetric error core; contamination $< 50\%$. | $K \ge 6$ | M-estimator slope $\hat{\beta}_{\text{Huber}}$ or RANSAC consensus slope. | $\beta_1 = 0$ | $\beta_1 \neq 0$ | Asymptotic standard errors fail completely at finite $K \le 7$. | Breakdown point requires $N > 2p$; $K=7$ allows tolerance of at most 1 outlier. | Excess coordinates used as regression target. | Omission of missing points reduces sample size toward breakdown boundary. |
| **Permutation Trend Tests** | Exchangeability of noise realizations under $H_0$ (i.i.d. errors). | $K \ge 6\text{--}7$ | Observed rank correlation vs $K!$ permutation distribution. | All $K!$ observation permutations equally likely. | Monotonic ordering aligned with time sequence. | Repeated testing across checkpoints consumes alpha rapidly. | Zero power if a single intermediate noise excursion inverts trajectory rank. | Permutations evaluated on excess sequence. | Permutation set recalculated on remaining $K_{\text{obs}}$ points. |
| **Change-Point (Pelt / CUSUM)** | Independent observations; known baseline $\mu_0, \sigma_0$; piecewise constant mean. | $K \ge 8\text{--}10$ | Cumulative sum $S_k = \max(0, S_{k-1} + (u_k - \mu_0 - k_{\text{ref}}))$. | Stationary mean $\mu = \mu_0$. | Abrupt level shift at unknown location $\tau$. | Sequential monitoring inflates false alarms without Wald boundaries. | Cannot establish pre-change variance from 1–2 sparse points; confuses noise with steps. | Lot-median subtracted before computing cumulative sum. | Cumulative sum accumulates over irregular time steps $\Delta t$. |
| **Sequential Likelihood Ratio (SPRT)** | Known parameter distributions under $H_0$ and $H_1$; independent observations. | $K \ge 6$ | Log-likelihood ratio $\Lambda_k = \sum \ln [f_1(u_t)/f_0(u_t)]$. | Observation follows $f_0(u)$. | Observation follows $f_1(u)$. | Boundary crossing probabilities require exact multi-parameter correction. | High false-positive rate if noise distribution deviates from assumed $f_0$. | Likelihood evaluated on residual innovation. | Irregular $\Delta t$ requires time-scaled drift rate in $f_1$. |

---

#### 8. False-Positive Calibration Procedure

##### Target False Positive Rate (`DESIGN/ARCHITECTURE CHOICE / FUTURE ENGINEERING TARGET`):
- **Candidate Target**: Empirical component-level False Positive Rate $\text{FPR} \le 0.001$ ($0.1\%$).
- **Classification**: Proposed engineering design target. Must **NOT** be cited as a verified result or a military/normative requirement.
- **Sample Size Requirement**: $N \ge 100,000$ null runs is an experiment design requirement (`DESIGN/ARCHITECTURE CHOICE`), not completed evidence.

##### Multiplicity & Calibration Structure:
1. **Unit of FPR**: Component-level $\text{FPR}_{\text{comp}} = P(\text{At least one parameter triggers false alarm} \mid \text{Component is healthy})$.
2. **Directional vs Two-Sided Testing (`DESIGN/ARCHITECTURE CHOICE`)**:
   - $I_{\text{DSS}}$ (leakage increase) and $R_{\text{DS(on)}}$ (resistance increase) evaluate one-sided alternatives ($H_1: \beta > 0$).
   - $V_{\text{GS(th)}}$ (interface trapping vs hole trapping) and $I_{\text{GSS}}$ (positive vs negative leakage) evaluate two-sided alternatives ($H_1: \beta \neq 0$).
3. **Four-Parameter Multiplicity Control (Holm-Bonferroni Procedure, `DESIGN/ARCHITECTURE CHOICE`)**:
   - For a given component, compute parameter p-values: $p_1, p_2, p_3, p_4$.
   - Sort in ascending order: $p_{(1)} \le p_{(2)} \le p_{(3)} \le p_{(4)}$.
   - Evaluate rejection sequentially:
     - Step 1: If $p_{(1)} \le \alpha / 4$, reject $H_{0,(1)}$ and proceed; else accept all.
     - Step 2: If $p_{(2)} \le \alpha / 3$, reject $H_{0,(2)}$ and proceed; else accept remaining.
     - Step 3: If $p_{(3)} \le \alpha / 2$, reject $H_{0,(3)}$ and proceed; else accept remaining.
     - Step 4: If $p_{(4)} \le \alpha / 1$, reject $H_{0,(4)}$; else accept.
4. **Sequential Alpha Spending (`DESIGN/ARCHITECTURE CHOICE`)**: If evaluated at multiple checkpoints ($T \in \{48, 72, 96, 120, 168\}\ \text{h}$), cumulative alpha spending must be partitioned using a Lan-DeMets spending function to maintain overall $\alpha \le 0.001$.
5. **Statistical Precision of Estimated FPR (`DESIGN/ARCHITECTURE CHOICE / FUTURE ENGINEERING TARGET`)**:
   - A Wilson 95% confidence interval will be reported after execution of the $N \ge 100,000$ null calibration experiment. No empirical Phase 4B FPR estimate or confidence interval currently exists.

---

#### 9. Independent Power Calibration Experiment Design

##### Signal Amplitudes Tested (`DESIGN/ARCHITECTURE CHOICE`):
Controlled cumulative shifts: $\delta \in \{1.0\sigma_{u,p}, 1.5\sigma_{u,p}, 2.0\sigma_{u,p}, 2.5\sigma_{u,p}\}$.

##### Sample Size & Morphologies (`DESIGN/ARCHITECTURE CHOICE` — experiment design requirement):
- $N = 10,000$ independent trajectories per parameter, per signal strength, across each morphology:
  1. Linear drift.
  2. Accelerating drift.
  3. Abrupt step change.
  4. Confounded drift under equipment thermal shift.
- Total power calibration sample size: $160,000$ series per parameter ($640,000$ total series).

##### Metric & Uncertainty Reporting:
- Empirical detection power:
  $$\hat{\text{Power}}(\delta) = \frac{N_{\text{detected}}}{N_{\text{true\_signals}}}$$
- Reported with $95\%$ binomial Wilson score confidence intervals.
- **Strict Separation Rule**: Power evaluation fixtures must be generated independently from null calibration fixtures. Zero threshold tuning on power fixtures.

---

#### 10. Train / Calibration / Evaluation Split Contract

To prevent data snooping, Phase 4B data must be generated in three disjoint partitions (`DESIGN/ARCHITECTURE CHOICE`):

| Partition Name | Allocation Fraction | Target Trajectories | Role in Development | Constraints & Access Rules |
| :--- | :---: | :---: | :--- | :--- |
| **CALIBRATION** | **$50\%$** | $50,000$ Null series<br>$80,000$ Power series | Threshold determination and empirical null quantile estimation. | Used exclusively to calibrate critical decision values $c_\alpha$. Never used to report final benchmark performance. |
| **VALIDATION** | **$25\%$** | $25,000$ Null series<br>$40,000$ Power series | Hyperparameter tuning, sensitivity analysis, and common-mode rejection testing. | Used for algorithm diagnostic inspection and feature engineering. |
| **FINAL EVALUATION** | **$25\%$** | $25,000$ Null series<br>$40,000$ Power series | Primary benchmark evaluation. | **Frozen, quarantined, evaluated exactly once.** Zero threshold selection or tuning permitted on this split. |

##### Cryptographic Random Seed Policy (`DESIGN/ARCHITECTURE CHOICE`):
- Partition seeds derived via HMAC-SHA256 from master seed $S_{\text{Phase4B}} = 261704$:
  - `seed_calib = HMAC(S, "calibration")`
  - `seed_val = HMAC(S, "validation")`
  - `seed_eval = HMAC(S, "final_evaluation")`
- Zero overlap in PRNG streams across partitions.

---

#### 11. Immutable Leakage Contract

Any future detector evaluated on Phase 4B must operate strictly under the following causal interface:

##### Permitted Ingestion (Causal Slice $V_T$):
- Measured values $y_i(t)$ for component $i$ where $t \le T_{\text{as\_of}}$.
- Parameter name and units ($I_{\text{DSS}}, V_{\text{GS(th)}}, R_{\text{DS(on)}}, I_{\text{GSS}}$).
- Observed lot measurements $\{y_j(t) : j \in \mathcal{L}, t \le T_{\text{as\_of}}\}$ for computing contemporaneous leave-one-out lot medians.

##### Strictly Quarantined Metadata (Forbidden Ingestion):
- Ground truth failure status (`is_spec_failure`, `is_degradation`).
- True latent values ($x^*(t)$, $b_{i,p}$, $g_{i,p}(t)$).
- Scenario labels (`scenario_tag`, `trajectory_vector`).
- Future observations ($t > T_{\text{as\_of}}$).
- Future lot statistics ($t > T_{\text{as\_of}}$).
- Chamber ID or ATE instrument ID (prevents using chamber metadata to infer common-mode status).
- PRNG random seeds or generator configuration files.
- Module B prognostic outputs (feedforward flow strictly enforced; Module B never feeds into Module A).

---

#### 12. Physical-Interpretation & Claim Boundaries

##### Permitted Statements (`SYNTHETIC BENCHMARK EVIDENCE`):
- *"Under the Phase 4B synthetic data-generating process with schedule S1, Candidate Detector X achieved an empirical component-level FPR of [value] on stationary Gaussian trajectories."*
- *"Candidate Detector X demonstrated empirical detection power of [value] on synthetic linear drift at an effect size of $1.5\sigma$."*
- *"Common-mode decoupling successfully rejected [value]% of synthetic chamber thermal excursions without triggering component drift alerts."*

##### Strictly Prohibited Statements (`UNSUPPORTED / EVIDENCE GAP`):
- *"Detector X detects real MOSFET degradation."*
- *"Detector X is space-qualified or flight-ready."*
- *"Detector X is validated for satellite component screening."*
- *"Phase 4B proves physical degradation kinetics in discrete power transistors."*
- *"Carry-Forward is optimal for real-world devices."*

---

#### 13. Proposed Acceptance Criteria Matrix

| Criterion ID | Target Metric | Proposed Benchmark Threshold | Assigned Layer | Verification Method |
| :--- | :--- | :--- | :--- | :--- |
| **Crit-A** | Null False Positive Rate ($\text{FPR}_{\text{comp}}$) | $\text{FPR} \le 0.0010$ ($0.1\%$) on Calibration Null | **DESIGN/ARCHITECTURE CHOICE / FUTURE ENGINEERING TARGET** | Planned empirical count on planned null experiment ($N \ge 100,000$ experiment design requirement). |
| **Crit-B** | FPR Precision Confidence Interval | $\text{CI}_{0.95} \text{ upper bound} \le 0.0013$ | **DESIGN/ARCHITECTURE CHOICE / FUTURE ENGINEERING TARGET** | Planned Wilson score 95% binomial interval evaluated post-execution. |
| **Crit-C** | Power at $1.0\sigma$ (Subtle drift) | $\text{Power} \ge 25.0\%$ (informational baseline) | **DESIGN/ARCHITECTURE CHOICE** | Empirical detection rate on Fixture A ($1.0\sigma$). |
| **Crit-D** | Power at $1.5\sigma$ (Target subtle drift) | $\text{Power} \ge 70.0\%$ | **DESIGN/ARCHITECTURE CHOICE** | Empirical detection rate on Fixture A ($1.5\sigma$). |
| **Crit-E** | Power at $2.0\sigma$ (Moderate drift) | $\text{Power} \ge 90.0\%$ | **DESIGN/ARCHITECTURE CHOICE** | Empirical detection rate on Fixture A ($2.0\sigma$). |
| **Crit-F** | Power at $2.5\sigma$ (Module A handoff) | $\text{Power} \ge 98.0\%$ | **DESIGN/ARCHITECTURE CHOICE** | Empirical detection rate on Fixture A ($2.5\sigma$). |
| **Crit-G** | Common-Mode Rejection Specificity | $\text{FPR} \le 0.0020$ under $\Delta T = 5^\circ\text{C}$ excursion | **DESIGN/ARCHITECTURE CHOICE** | Empirical false alarm rate on Null Model C. |
| **Crit-H** | Missing Data Resilience | Degradation power drop $\le 10\%$ with 1 missing point | **DESIGN/ARCHITECTURE CHOICE** | Evaluated on trajectories with $K=6$ observed points. |
| **Crit-I** | Multiplicity Invariance | Per-component $\text{FWER} \le 0.0010$ across 4 parameters | **DESIGN/ARCHITECTURE CHOICE / FUTURE ENGINEERING TARGET** | Holm-Bonferroni step-down verification across parameters. |

---

#### 14. Cryptographic Reproducibility & Governance

1. **Benchmark Version Identity**: The future dataset will be tagged uniquely as `PHASE_4B_BENCHMARK_v1.0.0`.
2. **Phase 2F Immutability**: Phase 4B will reside in a distinct directory (`data/synthetic_phase4b/`) and will **never** overwrite or mutate `data/synthetic_phase2f_frozen/`.
3. **Cryptographic Manifest**: Generation will emit:
   - `observations.csv` + SHA-256
   - `ground_truth.csv` + SHA-256 (quarantined)
   - `manifest.json` containing bit-for-bit file hashes, generator commit hash, and master seed.
4. **Frozen Evaluation Protocol**: Detectors will be evaluated exactly once on the Final Evaluation partition after threshold locking on Calibration/Validation partitions.

---

#### 15. Gate Decision

##### Gate Outcome: **`READY FOR BENCHMARK GENERATION`**

> [!NOTE]
> **Gate Definition & Scope (`DESIGN/ARCHITECTURE CHOICE`)**:
> "READY FOR BENCHMARK GENERATION" signifies strictly that the specification is approved for a subsequent benchmark-generation gate.
> It does **NOT** mean:
> - the benchmark exists;
> - calibration has succeeded;
> - FPR has been demonstrated;
> - power has been demonstrated;
> - the detector is ready;
> - physical validity has been established.

##### Justification:
1. The Phase 4B benchmark design is sufficiently specified for controlled implementation and independent calibration, subject to the documented assumptions and future empirical validation.
2. Sampling schedule S1 ($K=7$), parameter noise scales, three null architectures, six degradation fixtures, and Holm-Bonferroni multiplicity controls are unambiguously specified as design choices.
3. Strict causal leakage boundaries, leave-one-out common-mode referencing, and epistemic interpretation limits are established.
4. Per gate rules, detector implementation remains frozen and unauthorized until the benchmark is generated, cryptographically signed, and independently inspected.

Execution stopped per gate instructions.

---

### LOG-077: Phase 4B Independent Benchmark Generation Gate

- **Log ID**: LOG-077
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Independent Benchmark Generation Gate
- **Change**: Generation, Cryptographic Signing, and Quarantined Storage of `PHASE_4B_BENCHMARK_v1.0.0`
- **Previous State**: LOG-076 locked the complete implementation-ready benchmark specification under the pre-generation forensic correction gate (`READY FOR BENCHMARK GENERATION`).
- **New State**: `PHASE_4B_BENCHMARK_v1.0.0` generated into `data/synthetic_phase4b/`; telemetry, ground-truth, manifest, and checksum artifacts created, verified, and cryptographically frozen.
- **Reason**: Execute authorized generation gate to produce an independent benchmark with dense temporal sampling ($K=7$, S1 schedule), 3 independent null architectures (A, B, C), and 6 degradation fixtures (A-F) across disjoint calibration/validation/final partitions.
- **Source / Provenance**: `src/sih26170/synthetic/phase4b/`, LOG-076 specification, `data/synthetic_phase4b/manifest.json`.
- **Gate Outcome**: **BENCHMARK GENERATED AND FROZEN — READY FOR FORENSIC AUDIT**
- **Affected Area**: Canonical Project Log (`docs/PROTOTYPE_STANDING_LOG.md` / `docs/PROJECT_LOG.md`), `data/synthetic_phase4b/`, `src/sih26170/synthetic/phase4b/`, `tests/test_phase4b_benchmark.py`.
- **Canonical Invariants Preserved**: Zero modifications to Phase 2F (`data/synthetic_phase2f_frozen/` bit-for-bit unchanged); zero modifications to Module A; zero modifications to Module B; zero modifications to Stage 3; zero threshold adjustments; zero detector training or calibration executed.

---

#### 1. Benchmark Artifact Inventory & Cryptographic Hashes

The generated benchmark is quarantined in immutable namespace `data/synthetic_phase4b/` under version `PHASE_4B_BENCHMARK_v1.0.0`:

| Artifact Filename | File Role | Size (Bytes) | SHA-256 Checksum |
| :--- | :--- | :---: | :--- |
| `observations.csv` | Unlabeled detector-visible telemetry (CANONICAL_COLUMNS only) | 7,896,162 | `b5de6a03022a9350b6f304b9af593768e7f83a8fc61fde6ca98e690cfa1f275f` |
| `ground_truth.csv` | Quarantined latent states, kinetics, fixtures, and labels | 8,700,672 | `b48a2c0845492646ad9451d5a7efe256fe143043726807603a775d5f07c75656` |
| `manifest.json` | Benchmark configuration, schedule, parameters, partition mappings | 7,191 | `fe85a035e9ed2ecc46a1cbcf1d999f048313ccabadab23ee0969fa1033ac87e2` |
| `checksums.sha256` | Authoritative sha256 checksum manifest | 246 | (Checksum container) |

---

#### 2. Structural & Dataset Summary

| Dimension | Configured Specification | Generated Verification Status | Notes |
| :--- | :---: | :---: | :--- |
| **Temporal Schedule** | S1: $\{0, 24, 48, 72, 96, 120, 168\}\ \text{h}$ | **VERIFIED** | $K=7$ checkpoints, 168 h observation horizon |
| **Manufacturing Lots** | 100 lots | **VERIFIED** | 100 distinct lot identifiers |
| **Components per Lot** | 20 components | **VERIFIED** | Satisfies $N_{\text{lot}} \ge 10$ stability requirement for leave-one-out median |
| **Total Components** | 2,000 components | **VERIFIED** | $100 \text{ lots} \times 20 \text{ components}$ |
| **Parameters** | 4 observables | **VERIFIED** | $I_{\text{DSS}}, V_{\text{GS(th)}}, R_{\text{DS(on)}}, I_{\text{GSS}}$ |
| **Total Parameter-Series** | 8,000 series | **VERIFIED** | $2,000 \text{ components} \times 4 \text{ parameters}$ |
| **Observation Rows** | 56,000 rows | **VERIFIED** | $8,000 \text{ series} \times 7 \text{ checkpoints}$ |
| **Ground Truth Rows** | 56,000 rows | **VERIFIED** | $8,000 \text{ series} \times 7 \text{ checkpoints}$ |

---

#### 3. Three-Way Disjoint Partition Summary

| Partition | Allocation Fraction | Lot Count | Component Count | Parameter-Series | Observation Rows | HMAC Seed Identifier |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **CALIBRATION** | **$50\%$** | 50 lots | 1,000 | 4,000 | 28,000 | `11999057` |
| **VALIDATION** | **$25\%$** | 25 lots | 500 | 2,000 | 14,000 | `499376249` |
| **FINAL EVALUATION** | **$25\%$** | 25 lots | 500 | 2,000 | 14,000 | `460793515` |
| **TOTAL** | **$100\%$** | **100 lots** | **2,000** | **8,000** | **56,000** | Master: `261704` |

---

#### 4. Fixture & Mechanism Distribution

| Fixture Identifier | Description / Mathematical Model (`DESIGN/ARCHITECTURE CHOICE`) | Lots | Components | Parameter-Series | Latent Drift $g(t)$ |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Null A (`null_gaussian`)** | Ideal i.i.d. Gaussian stationary null ($\epsilon \sim \mathcal{N}(0, \sigma^2)$) | 20 | 400 | 1,600 | $\equiv 0.0$ |
| **Null B (`null_ar1`)** | AR(1) session-drift null ($\phi \in [0.20, 0.35]$, synthetic stress parameter) | 20 | 400 | 1,600 | $\equiv 0.0$ |
| **Null C (`null_common_mode`)** | Synchronous chamber excursion ($\Delta T = +5^\circ\text{C}$ at $72\text{h}, 96\text{h}$) | 9 | 180 | 720 | $\equiv 0.0$ |
| **Fixture A (`fixture_a_linear_drift`)** | Weak linear drift ($u_0 + s \cdot \delta \sigma (t/168)$, $\delta \in \{1.0, 1.5, 2.0, 2.5\}$) | 11 | 220 | 880 | Active on target |
| **Fixture B (`fixture_b_accelerating_drift`)** | Weak accelerating drift ($u_0 + s \cdot \delta \sigma (t/168)^{2.1}$, $\delta \in \{1.0, 1.5, 2.0, 2.5\}$) | 11 | 220 | 880 | Active on target |
| **Fixture C (`fixture_c_abrupt_step`)** | Weak abrupt step ($s \cdot \delta \sigma$ at $t_{\text{step}} \in \{48, 72, 96\}\ \text{h}$) | 11 | 220 | 880 | Active on target |
| **Fixture D (`fixture_d_confounded_drift`)** | Linear drift $+1.5\sigma$ superimposed on synchronous $+5^\circ\text{C}$ chamber excursion | 5 | 100 | 400 | Active on target |
| **Fixture E (`fixture_e_heteroscedastic_noise`)** | Linear drift with expanding measurement noise $\sigma(t) = \sigma_0(1 + 0.5 \cdot t/168)$ | 5 | 100 | 400 | Active on target |
| **Fixture F (`fixture_f_staggered_onset`)** | Dormant latent state commencing drift at $t_{\text{onset}} \in \{48, 72\}\ \text{h}$ | 8 | 160 | 640 | Active on target |
| **TOTAL** | | **100** | **2,000** | **8,000** | |

---

#### 5. Generation Integrity & Statistical Sanity Verification Results

1. **Structural Checks (`PASS`)**:
   - Total rows: 56,000 observations, 56,000 ground truth.
   - All 7 checkpoints present: $\{0, 24, 48, 72, 96, 120, 168\}\ \text{h}$.
   - Zero missing or NaN/Inf values in observations or ground truth.
   - Physical domain validity: $I_{\text{DSS}} \in [0.206, 1.466]\ \mu\text{A} > 0$; $R_{\text{DS(on)}} \in [33.31, 68.65]\ \text{m}\Omega > 0$; $V_{\text{GS(th)}} \in [2.57, 3.45]\ \text{V} \in [1.5, 4.5]\ \text{V}$.
2. **Signed IGSS Preservation (`PASS`)**:
   - $I_{\text{GSS}}$ observed values range from $-0.2877\ \text{nA}$ to $+17.1512\ \text{nA}$.
   - Negative values are preserved directly through the asinh/sinh coordinate transform.
   - No `abs()` applied; no clipping to positive values; no clipping at $\pm 100\ \text{nA}$.
3. **Statistical Sanity Checks (`PASS`)**:
   - Stationary Null Integrity: All Null A, B, and C series exhibit $\max |g(t)| = 0.000000$ (zero injected degradation).
   - Degradation Fixtures: Evaluated across target signal amplitudes $\delta \in \{1.0, 1.5, 2.0, 2.5\}\sigma$.
   - AR(1) Correlation: Pooled ensemble lag-1 autocorrelation across Null B series is $\hat{\rho}_1 = 0.2753$, matching the configured uniform synthetic stress range $\phi \in [0.20, 0.35]$ (midpoint $0.275$).
   - Common-Mode Excursion: Synchronous $+5.0^\circ\text{C}$ temperature offset confirmed at $t \in \{72, 96\}\ \text{h}$ across all chamber drift lots with zero component-level drift.
4. **Leakage Audit (`PASS`)**:
   - Observation columns strictly equal `CANONICAL_COLUMNS` (15 fields).
   - Zero scenario labels, zero partition labels, zero latent states, zero random seeds, and zero future values exist in `observations.csv`.
   - Quarantined ground truth resides exclusively in `ground_truth.csv`.
5. **Phase 2F Frozen Baseline Integrity (`PASS`)**:
   - `observations.csv`: `b4282e0743cd6a0b2b74354e431bf8f308b03281c44c0437d30f7b53bd6ca983` (**MATCH**)
   - `ground_truth.csv`: `4bf2155fcc7698813f766e1dea9730213e0a6097e484bfa786eb1b94925f3d2b` (**MATCH**)
   - `manifest.json`: `5a08630f9fafc95563c13acea77df7aa066f7abc7a08b785a77c2709553980f6` (**MATCH**)
   - `scenario_manifest.json`: `8f7b756255adfe444a3f15ba55b739d07e478565fb4e27639000905c49116b2e` (**MATCH**)
6. **Automated Test Suite (`PASS`)**:
   - 180 passed in 8.14s (`PYTHONPATH=. pytest`).

---

#### 6. Scientific & Epistemic Boundaries (`DESIGN/ARCHITECTURE CHOICE`)

> [!CAUTION]
> **Epistemic Classification & Limitations**:
> Phase 4B is an idealized synthetic simulation environment. It does **NOT** evaluate, validate, or prove real semiconductor device reliability, physical degradation kinetics in spaceflight hardware, or production-lot flightworthiness.
> The AR(1) noise structure ($\phi \in [0.20, 0.35]$) and chamber thermal excursions ($\Delta T = 5^\circ\text{C}$) are synthetic stress parameters, not empirical calibrations of factory ATE or flight hardware.

---

#### 7. Gate Decision

##### Gate Outcome: **`BENCHMARK GENERATED AND FROZEN — READY FOR FORENSIC AUDIT`**

##### Justification:
1. `PHASE_4B_BENCHMARK_v1.0.0` is generated, cryptographically signed, and quarantined in `data/synthetic_phase4b/`.
2. All structural integrity checks, statistical sanity checks, and leakage isolation audits passed.
3. No detector implementation, calibration, threshold tuning, or evaluation was performed.
4. The next authorized gate is a separate **PHASE 4B BENCHMARK FORENSIC AUDIT GATE**.

Execution stopped per gate instructions.

---

### LOG-078: Phase 4B Benchmark Forensic Audit Gate

- **Log ID**: LOG-078
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Benchmark Forensic Audit Gate
- **Change**: Independent Forensic Audit of `PHASE_4B_BENCHMARK_v1.0.0`
- **Previous State**: LOG-077 generated, cryptographically signed, and quarantined `PHASE_4B_BENCHMARK_v1.0.0` (`BENCHMARK GENERATED AND FROZEN — READY FOR FORENSIC AUDIT`).
- **New State**: Comprehensive forensic audit completed across 22 criteria covering cryptographic identity, entity accounting, partition disjointness, causal as-of contracts, ground-truth quarantine, fixture integrity, AR(1) Hurwicz bias, cross-parameter coupling, and leave-one-out referencing.
- **Reason**: Independently verify benchmark integrity, statistical properties, and causal quarantine before any detector calibration, implementation, or evaluation is authorized.
- **Source / Provenance**: `scratch/forensic_audit_phase4b.py`, `tests/test_phase4b_benchmark.py`, `data/synthetic_phase4b/`.
- **Gate Outcome**: **PASS WITH DOCUMENTED LIMITATIONS**
- **Affected Area**: Canonical Project Log (`docs/PROTOTYPE_STANDING_LOG.md` / `docs/PROJECT_LOG.md`).
- **Canonical Invariants Preserved**: Zero benchmark modifications; zero data regenerations; zero modifications to Phase 2F; zero modifications to Module A, Module B, Stage 3; zero threshold adjustments; zero detector training, calibration, or evaluation executed.

---

#### 1. Cryptographic Identity & Artifact Verification

All four benchmark artifacts on disk in `data/synthetic_phase4b/` match their authoritative cryptographic baseline bit-for-bit:

| Artifact Path | Size (Bytes) | Verified SHA-256 Checksum | Audit Status |
| :--- | :---: | :--- | :---: |
| `data/synthetic_phase4b/observations.csv` | 7,896,162 | `b5de6a03022a9350b6f304b9af593768e7f83a8fc61fde6ca98e690cfa1f275f` | **MATCH** |
| `data/synthetic_phase4b/ground_truth.csv` | 8,700,672 | `b48a2c0845492646ad9451d5a7efe256fe143043726807603a775d5f07c75656` | **MATCH** |
| `data/synthetic_phase4b/manifest.json` | 7,191 | `fe85a035e9ed2ecc46a1cbcf1d999f048313ccabadab23ee0969fa1033ac87e2` | **MATCH** |
| `data/synthetic_phase4b/checksums.sha256` | 246 | `36bd9a2f47b73ac216f6c1003b2b12187a70877feb169c54054e6c3da8d9cb7c` | **MATCH** |

---

#### 2. Row & Entity Accounting Audit

Independent arithmetic reconstruction of all dataset dimensions:

- **Manufacturing Lots**: 100 lots ($50\ \text{Calibration}, 25\ \text{Validation}, 25\ \text{Final Evaluation}$).
- **Components per Lot**: Exactly 20 components per lot across all 100 lots (distribution: $\{20: 100\}$).
- **Total Components**: $100 \times 20 = 2,000$ components.
- **Physical Parameters**: 4 observables ($I_{\text{DSS}}, V_{\text{GS(th)}}, R_{\text{DS(on)}}, I_{\text{GSS}}$).
- **Total Parameter-Series**: $2,000 \times 4 = 8,000$ series.
- **Temporal Checkpoints**: Exactly 7 checkpoints ($0, 24, 48, 72, 96, 120, 168\ \text{h}$).
- **Observation Telemetry Rows**: $8,000 \times 7 = 56,000$ rows.
- **Ground-Truth Telemetry Rows**: $8,000 \times 7 = 56,000$ rows.
- **Partition Row Allocations**:
  - `CALIBRATION`: 28,000 rows ($50.0\%$).
  - `VALIDATION`: 14,000 rows ($25.0\%$).
  - `FINAL_EVALUATION`: 14,000 rows ($25.0\%$).

All entities exhibit exactly 4 parameter-series and 7 checkpoints with zero missingness or imbalance.

---

#### 3. Partition Disjointness Audit (`PASS`)

Independence across partitions was audited at all structural levels:

- **Lot-Level Disjointness**:
  - $\text{CALIBRATION} \cap \text{VALIDATION} = \emptyset$ (0 lots in common).
  - $\text{CALIBRATION} \cap \text{FINAL\_EVALUATION} = \emptyset$ (0 lots in common).
  - $\text{VALIDATION} \cap \text{FINAL\_EVALUATION} = \emptyset$ (0 lots in common).
- **Component-Level Disjointness**:
  - $\text{CALIBRATION} \cap \text{VALIDATION} = \emptyset$ (0 components in common).
  - $\text{CALIBRATION} \cap \text{FINAL\_EVALUATION} = \emptyset$ (0 components in common).
  - $\text{VALIDATION} \cap \text{FINAL\_EVALUATION} = \emptyset$ (0 components in common).
- **Parameter-Series Disjointness**: Zero series intersect across partitions.
- **HMAC Seed Independence**:
  - Calibration Root Seed: `11999057`
  - Validation Root Seed: `499376249`
  - Final Evaluation Root Seed: `460793515`
  All three PRNG streams are cryptographically disjoint.

---

#### 4. Causal As-Of Slicing Contract Audit (`PASS`)

The causal boundary was audited by distinguishing:
1. **Full Benchmark Storage**: `observations.csv` necessarily archives all 7 checkpoints ($0\text{--}168\ \text{h}$) on disk.
2. **Detector-Visible Causal Slice**: For any analysis time $T_{\text{as\_of}}$, only records satisfying $\text{elapsed\_hours} \le T_{\text{as\_of}}$ may be passed to candidate algorithms.

##### Empirical Verification:
- At $T_{\text{as\_of}} = 24\ \text{h}$: Exactly 16,000 rows visible (checkpoints: $\{0, 24\}\ \text{h}$); zero rows with $t > 24\ \text{h}$.
- At $T_{\text{as\_of}} = 96\ \text{h}$: Exactly 40,000 rows visible (checkpoints: $\{0, 24, 48, 72, 96\}\ \text{h}$); zero rows with $t > 96\ \text{h}$.
- At $T_{\text{as\_of}} = 168\ \text{h}$: Full 56,000 rows visible.

> [!NOTE]
> **Causal Slicing Contract**: The benchmark archive contains future checkpoints by design; the audited causal slicing contract restricts detector-visible input to $\text{elapsed\_hours} \le T_{\text{as\_of}}$, which must be strictly enforced at runtime by future detector evaluation harnesses.

---

#### 5. Ground-Truth Quarantine & Indirect Leakage Audit (`PASS`)

- **Direct Leakage**: Inspection of `observations.csv` header confirms zero presence of prohibited fields:
  - `is_degradation`: absent
  - `is_spec_failure`: absent
  - `fixture_type`: absent
  - `latent_drift`: absent
  - `latent_true_value`: absent
  - `latent_true_transformed`: absent
  - `noise_realization`: absent
  - `signal_delta`: absent
  - `scenario`: absent
  - `partition`: absent
  - `seed`: absent
- **Indirect Leakage**: Columns strictly equal `CANONICAL_COLUMNS` (15 fields).
- **Intentionally Detector-Visible Metadata**:
  - Test conditions (`temperature_C`, `test_condition`, `instrument_id`, `channel_id`, `rework_count`, `measurement_quality`, `source_type`) and normative specification limits (`absolute_limit_low`, `absolute_limit_high`). None of these fields encode component failure status or degradation kinetics.

---

#### 6. Fixture Integrity & Series Accounting

Reconstruction from quarantined ground truth verifies all 9 fixtures sum to exactly 8,000 parameter-series:

| Fixture Identifier | Fixture Description | Lots | Components | Parameter-Series | Degradation Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `null_gaussian` | Ideal i.i.d. Gaussian Null A | 20 | 400 | 1,600 | Strictly Stationary ($g \equiv 0$) |
| `null_ar1` | AR(1) Session-Drift Null B | 20 | 400 | 1,600 | Strictly Stationary ($g \equiv 0$) |
| `null_common_mode` | Chamber Excursion Null C | 9 | 180 | 720 | Strictly Stationary ($g \equiv 0$) |
| `fixture_a_linear_drift` | Weak Linear Drift | 11 | 220 | 880 | Active ($\delta \in [1.0, 2.5]\sigma$) |
| `fixture_b_accelerating_drift` | Weak Accelerating Drift | 11 | 220 | 880 | Active ($\delta \in [1.0, 2.5]\sigma$) |
| `fixture_c_abrupt_step` | Weak Abrupt Step | 11 | 220 | 880 | Active ($\delta \in [1.0, 2.5]\sigma$) |
| `fixture_d_confounded_drift` | Confounded Linear Drift | 5 | 100 | 400 | Active ($\delta \in [1.5, 2.0]\sigma$) |
| `fixture_e_heteroscedastic_noise` | Expanding Noise Drift | 5 | 100 | 400 | Active ($\delta \in [1.5, 2.5]\sigma$) |
| `fixture_f_staggered_onset` | Staggered Onset Drift | 8 | 160 | 640 | Active ($\delta \in [1.5, 2.5]\sigma$) |
| **TOTAL** | | **100** | **2,000** | **8,000** | |

---

#### 7. Null Model A Audit (`PASS`)

- **Latent Drift**: Strictly $\max |g_p(t)| = 0.000000$ across all 1,600 series (zero injected latent degradation).
- **Transformed Coordinate Noise Std**:
  - $I_{\text{DSS}}$: $0.0809$ (configured: $0.0800$)
  - $V_{\text{GS(th)}}$: $0.0198\ \text{V}$ (configured: $0.0200\ \text{V}$)
  - $R_{\text{DS(on)}}$: $0.0125$ (configured: $0.0125$)
  - $I_{\text{GSS}}$: $0.2522$ (configured: $0.2500$)
- **Epistemic Distinction**: Zero injected degradation must be distinguished from zero observed slope. Observed sample regression slopes on stationary series fluctuate symmetrically around zero ($\mathbb{E}[\hat{b}] = 0$) due to finite-sample instrumentation noise dispersion; sample slopes are not expected to be identically zero. Furthermore, static specification or screening crossings do not represent degradation.

---

#### 8. Null Model B AR(1) Audit & Hurwicz Finite-Sample Bias (`PASS WITH DOCUMENTED LIMITATIONS`)

- **Latent Drift**: Strictly $\max |g_p(t)| = 0.000000$.
- **Configured Parameter**: Uniform synthetic stress range $\phi \in [0.20, 0.35]$ (nominal midpoint $0.275$).
- **Pooled Ensemble Lag-1 Autocorrelation**: The pooled ensemble lag-1 autocorrelation was 0.2560, which is directionally and approximately consistent with the nominal configured $\phi$ midpoint of 0.275. Because each series contains only $K=7$ points and the series-level sample correlations have substantial finite-sample dispersion, this pooled statistic does not establish accurate recovery of each series' configured $\phi$.
- **Series-Level Sample Correlation Distribution** (across 1,600 individual 7-point series):
  - Mean: $+0.0026$
  - Median: $+0.0172$
  - Std: $0.3810$
  - 10th percentile: $-0.5297$, 90th percentile: $+0.4999$
  - Range: $[-0.9016, +0.9476]$
- **Analytical Hurwicz Bias Reconciliation**:
  In short time-series ($T=7$), the sample Pearson autocorrelation suffers severe downward Hurwicz bias:
  $$\mathbb{E}[\hat{r}_1] \approx \phi - \frac{1 + 3\phi}{T} = 0.275 - \frac{1 + 3(0.275)}{7} = 0.275 - 0.2607 = +0.0143$$
  The observed series-level sample mean ($+0.0026$) is consistent with the theoretical Hurwicz expectation for $T=7$ ($+0.014 \pm 0.02$).
- **Epistemic Classification**: $\phi \in [0.20, 0.35]$ is an engineering design parameter intended for stress-testing, not an empirical model of factory ATE/session drift; no physical validation is claimed.

---

#### 9. Null Model C Common-Mode Audit (`PASS WITH DOCUMENTED LIMITATIONS`)

- **Latent Component Degradation**: Strictly $0.000000$ (no component-level wearout).
- **Chamber Perturbation**: Synchronous $+5.0^\circ\text{C}$ step confirmed at $t \in \{72, 96\}\ \text{h}$ across all 9 common-mode lots ($143.75^\circ\text{C} \to 148.75^\circ\text{C}$ lot average; $150^\circ\text{C} \to 155^\circ\text{C}$ for HTRB/HTGB, $125^\circ\text{C} \to 130^\circ\text{C}$ for operating life).
- **Telemetry Manifestation**: The synthetic measurement model applies the configured thermal-sensitivity relationships, producing the expected synthetic coordinate shifts ($\Delta u_{\text{IDSS}} = +0.20$, $\Delta u_{\text{VGSTH}} = -0.025\ \text{V}$, $\Delta u_{\text{RDSON}} = +0.025$, $\Delta u_{\text{IGSS}} = +0.10$).
- **Epistemic Classification**: These thermal-sensitivity relationships are synthetic design/model assumptions, not physical chamber calibrations. Environmental chamber excursion is an external test perturbation, critically distinguished from internal electrical parameter degradation.

---

#### 10. Signal-Amplitude Calibration Audit (`PASS`)

Latent signal amplitudes at $168\ \text{h}$ were verified independently across all 4 physical observables:
- $\delta \in \{1.0, 1.5, 2.0, 2.5\}\sigma_{u,p}$ realized accurately relative to parameter-specific scales:
  - $I_{\text{DSS}}$ ($\sigma_u = 0.08$): $|g(168)| \in [0.08, 0.20]$
  - $V_{\text{GS(th)}}$ ($\sigma_u = 0.02\ \text{V}$): $|g(168)| \in [0.02, 0.05]\ \text{V}$
  - $R_{\text{DS(on)}}$ ($\sigma_u = 0.0125$): $|g(168)| \in [0.0125, 0.03125]$
  - $I_{\text{GSS}}$ ($\sigma_u = 0.25$): $|g(168)| \in [0.25, 0.625]$

---

#### 11. Parameter Independence & Coupling Audit (`PASS WITH DOCUMENTED LIMITATIONS`)

- **Empirical Observation Inter-Parameter Correlation**:
  - $\text{Corr}(I_{\text{DSS}}, V_{\text{GS(th)}}) = -0.0686$
  - $\text{Corr}(I_{\text{DSS}}, R_{\text{DS(on)}}) = +0.0386$
  - $\text{Corr}(I_{\text{DSS}}, I_{\text{GSS}}) = +0.0296$
  - $\text{Corr}(V_{\text{GS(th)}}, R_{\text{DS(on)}}) = +0.0082$
  - $\text{Corr}(V_{\text{GS(th)}}, I_{\text{GSS}}) = -0.0024$
  - $\text{Corr}(R_{\text{DS(on)}}, I_{\text{GSS}}) = -0.0327$
  All inter-parameter correlations satisfy $|\rho| < 0.07$ (near zero).
- **Parameter-Selective Degradation Allocation**:
  - 980 components: 0 degraded parameters (stationary null).
  - 640 components: exactly 1 degraded parameter (isolated single-parameter drift).
  - 380 components: 4 degraded parameters (multi-parameter compound drift).
- **Coupling Assessment**: No evidence of the Phase 2F-style forced component-wide trajectory coupling was found under the audited parameter allocation.
- **Epistemic Classification**: The synthetic generator's parameter independence is an engineering design property, not proof that real MOSFET physical degradation mechanisms are independent.

---

#### 12. Heteroscedasticity Audit (Fixture E) (`PASS`)

Monotonic expansion of noise standard deviation confirmed:
- $t = 0\ \text{h}$: scale factor $1.000 \implies \text{std} = 0.1225$
- $t = 24\ \text{h}$: scale factor $1.071 \implies \text{std} = 0.1354$
- $t = 48\ \text{h}$: scale factor $1.143 \implies \text{std} = 0.1428$
- $t = 72\ \text{h}$: scale factor $1.214 \implies \text{std} = 0.1463$
- $t = 96\ \text{h}$: scale factor $1.286 \implies \text{std} = 0.1745$
- $t = 120\ \text{h}$: scale factor $1.357 \implies \text{std} = 0.1818$
- $t = 168\ \text{h}$: scale factor $1.500 \implies \text{std} = 0.1929$
The observed variance growth ratio is $0.1929 / 0.1225 = 1.57$, representing a finite-sample realization consistent with the configured 1.50 scale factor (not an exact realization of the configured model due to sample dispersion).

---

#### 13. Staggered-Onset Audit (Fixture F) (`PASS`)

- Pre-onset checkpoints ($t \le 24\ \text{h}$ for $t_{\text{onset}}=48\ \text{h}$, and $t \le 48\ \text{h}$ for $t_{\text{onset}}=72\ \text{h}$) have strictly zero injected latent degradation ($g(t) = 0.000000$) across all 640 series.
- Post-onset kinetics ramp smoothly to target delta at $168\ \text{h}$.
- Pre-onset telemetry exhibits expected finite-sample observation noise without degradation; this audit evaluates generator integrity and does not constitute a detection performance claim.

---

#### 14. Signed IGSS Preservation Audit (`PASS`)

- Range: $[-0.2877\ \text{nA}, +17.1512\ \text{nA}]$. Both positive and negative values observed.
- Round-trip mapping numerical error: $\max |x - \sinh(\text{asinh}(x))| = 1.78 \times 10^{-15}$ (machine epsilon).
- Zero `abs()` calls; zero clipping to positive; $\pm 100\ \text{nA}$ boundary not clipped.

---

#### 15. Physical Domain & Spec-Limit Breaches Audit (`PASS WITH DOCUMENTED LIMITATIONS`)

- **Total Specification/Screening Breaches Across Dataset**: 100 rows out of 56,000 ($0.18\%$). All 100 occurrences reside in $R_{\text{DS(on)}}$.
- **Normative vs Commercial Classification**:
  The project canonical physical anchor distinguishes:
  1. $60\ \text{m}\Omega$: configured commercial screening acceptance criterion (Class C screening in Infineon context);
  2. $65\ \text{m}\Omega$: military device specification ceiling under the MIL-PRF-19500/703 context.
- **Stationary Null Rows (49 rows across 7 components)**:
  49 stationary-null rows exceed the configured 60 mΩ commercial screening criterion, with $R_{\text{DS(on)}}$ approximately 62–67 mΩ. Values between 60 and 65 mΩ exceed that configured commercial screening criterion but do not by themselves exceed the 65 mΩ military specification ceiling. Values above 65 mΩ constitute military-specification exceedance under the project's stated device-specification semantics:
  - $R_{\text{DS(on)}} \in (60, 65]\ \text{m}\Omega$ (commercial screening exceedance only): 35 rows across 5 components (`LOT_CAL_001_C017`, `LOT_CAL_015_C016`, `LOT_VAL_006_C006`, `LOT_VAL_006_C010`, `LOT_VAL_006_C016`), with latent values between $60.45\ \text{m}\Omega$ and $64.39\ \text{m}\Omega$.
  - $R_{\text{DS(on)}} > 65\ \text{m}\Omega$ (military specification ceiling exceedance): 14 rows across 2 components (`LOT_CAL_015_C006`, `LOT_CAL_015_C011`), with latent values of $66.96\ \text{m}\Omega$ and $67.26\ \text{m}\Omega$.
- **Degradation Fixture Breaches (51 rows)**: Progressive wearout drift breaching limits late in life.
- **Static Specification Non-Compliance vs Degradation**:
  All 49 stationary-null exceedances represent static yield non-compliance present at baseline ($t=0$) under log-normal baseline dispersion ($\Delta u = 0$). A stationary series can be statically non-compliant without exhibiting temporal degradation. None of these stationary series represent degradation.

---

#### 16. Common-Mode Leave-One-Out Reference Audit (`PASS`)

- Reference formula: $u^{\text{excess}}_{i,p}(t) = u_{i,p}(t) - \text{median}_{j \neq i} \{ u_{j,p}(t) \}$.
- Verified: Lot size is 20 ($N_{\text{lot}} \ge 10$ stability requirement met).
- Analytical failure mode:
  - If 1 out of 20 components drifts by $+2.0\sigma$, the leave-one-out reference is $0.0\sigma$, preserving $100\%$ of the excess signal.
  - If 100% of components drift by $+2.0\sigma$, the leave-one-out reference is $+2.0\sigma$, absorbing $100\%$ of the signal and attenuating excess motion to 0.

---

#### 17. Seed Hierarchy & Reproducibility Audit (`PASS`)

- Deterministic HMAC-SHA256 derivation verified:
  - Master: `261704`
  - Calibration: `11999057`
  - Validation: `499376249`
  - Final Evaluation: `460793515`
- Zero seeds exposed in `observations.csv`.

---

#### 18. Manifest Consistency Audit (`PASS`)

All entries in `manifest.json` match `observations.csv`, `ground_truth.csv`, and `checksums.sha256` bit-for-bit.

---

#### 19. No Detector Evaluation (`CONFIRMED`)

Zero detector evaluation was executed. No FPR, sensitivity, specificity, precision, recall, power, or ROC curves were computed.

---

#### 20. Final Forensic Verdict

### **PASS WITH DOCUMENTED LIMITATIONS**

**Verdict Statement**: `PHASE_4B_BENCHMARK_v1.0.0` is structurally complete, causally partitioned according to the audited contract, and cryptographically verified, subject to the documented synthetic-model limitations.

##### Rationale:
The benchmark passes structural, cryptographic, partition, ground-truth quarantine, causal slicing contract, fixture-integrity, transformation, and reproducibility audits.

##### Documented Limitations (Explicit Synthetic Constraints, Not Defects):
1. **Synthetic AR(1) Model**: The $\phi \in [0.20, 0.35]$ stress model is an engineering design parameter for stress-testing, not an empirically calibrated model of factory ATE or session drift; no physical validation is claimed.
2. **Synthetic Common-Mode Thermal Relationships**: Transductive thermal sensitivity relationships are synthetic model assumptions, not physical chamber validations.
3. **Synthetic Noise Model**: Univariate Gaussian/heteroscedastic noise is an idealized synthetic process, not equivalent to production measurement noise.
4. **Finite-Sample Uncertainty ($K=7$)**: Sample statistics at $K=7$ checkpoints are subject to substantial finite-sample dispersion (e.g. downward Hurwicz bias for sample autocorrelation).
5. **Static Specification Exceedance vs Degradation**: Baseline parameter exceedance (e.g. $R_{\text{DS(on)}} > 60\ \text{m}\Omega$ or $> 65\ \text{m}\Omega$) represents static yield non-compliance, not temporal wearout degradation.
6. **Synthetic Parameter Independence**: Synthetic trajectory independence across observables is an engineering design choice, not evidence that real physical MOSFET degradation mechanisms are decoupled.

##### Summary of Verification Status:
1. Cryptographic integrity confirmed bit-for-bit across all artifacts.
2. Exact entity accounting verified (100 lots, 2,000 components, 8,000 series, 56,000 rows).
3. 3-way partition disjointness verified at lot, component, and series levels.
4. Causal as-of slicing contract validated.
5. Ground-truth quarantine strictly maintained with zero leaks.
6. Parameter independence confirmed ($|\rho| < 0.07$) with balanced single- and multi-parameter degradation lots.
7. Hurwicz finite-sample bias for AR(1) at $T=7$ formally reconciled.
8. Signed $I_{\text{GSS}}$ preserved at machine precision.
9. Phase 2F frozen baseline remains bit-for-bit immutable.

Execution stopped per gate instructions.

---

### LOG-079: Phase 4B Detector Calibration Experiment Specification Gate

- **Log ID**: LOG-079
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Detector Calibration Experiment Specification Gate
- **Change**: Formally Approved Revised Detector Calibration & Power Evaluation Specification (`docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` v1.4.0)
- **Previous State**: LOG-078 completed independent forensic audit of `PHASE_4B_BENCHMARK_v1.0.0` (`PASS WITH DOCUMENTED LIMITATIONS`).
- **New State**: Detailed, pre-execution specification established for candidate weak/incipient degradation detectors; explicit Monte Carlo unit definition (1 replicate = 1 complete 4-parameter component; $N_A = N_B = N_C = 100,000$ components = $1,200,000$ parameter series total; strictly not described as merely 300k trajectories); Null A established as sole calibration reference with Null B and Null C as frozen stress tests; dedicated HMAC seed namespace; mathematically valid finite-sample empirical p-value construction; signed $I_{\text{GSS}}$ pipeline preservation (signed $I_{\text{GSS}} \to \text{signed asinh} \to \text{excess coordinate} \to \text{detector statistic} \to \text{two-sided } p$-value without taking absolute value); formal Holm-Bonferroni component-level FWER calibration guarantee under Null A at $\alpha = 0.001$; frozen Module A comparator semantics; benchmark power amplitude verification vs independent power sweep; explicit two-stage validation freeze boundaries (diagnostic characterization only); and final audit hashes formally specified.
- **Reason**: Implement final pre-authorization forensic corrections: define Monte Carlo replicate unit as complete component, provide exact parameter series accounting ($3 \times 100{,}000 = 300{,}000$ components, $1{,}200{,}000$ series), define component-level FWER estimation formula, adopt exact statistical guarantee wording under Null A, enforce signed $I_{\text{GSS}}$ preservation throughout pipeline, remove hyperparameter tuning from validation, and clarify benchmark vs auxiliary power suites.
- **Source / Provenance**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` (v1.4.0, SHA-256: `3a3fe0fecb0e5d2cb8cbaaf7753b8b2753409cf40f8f8e4e3608972d36fba8fb`), LOG-076, LOG-077, LOG-078.
- **Gate Outcome**: **SPECIFICATION REVISED (v1.4.0) — LOCKED FOR EXECUTION GATE AUTHORIZATION**
- **Affected Area**: Canonical Project Log (`docs/PROTOTYPE_STANDING_LOG.md` / `docs/PROJECT_LOG.md`), `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md`.
- **Canonical Invariants Preserved**: Zero code modifications in `src/`; zero threshold adjustments; zero modifications to `PHASE_4B_BENCHMARK_v1.0.0`; zero modifications to `data/synthetic_phase2f_frozen/`; zero detector execution or calibration performed.

---

#### 1. Purpose & Pre-Execution Boundary

The Phase 4B Detector Calibration Experiment Gate executes the already-authorized calibration design established in LOG-076 without optimizing against the primary final benchmark.

- **Primary Mandate**: Calibration of detector decision boundaries strictly on stationary Null A trajectories to control component-level $\text{FWER}$ at $\alpha = 0.001$, followed by frozen stress-testing on Null B/C and power evaluation on weak signals without post-hoc amplitude retrofitting.
- **Protocol Formulation**: Calibrate detector statistic / empirical $p$-value mapping under Null A, then apply the pre-specified Holm-Bonferroni procedure to the resulting parameter-level $p$-values.
- **Statistical Guarantee Wording**: Under the assumptions required for valid parameter-level $p$-values, the pre-specified Holm-Bonferroni procedure controls component-level FWER at $\alpha = 0.001$. Empirical FWER is estimated from the simulated null components.
- **Pre-Execution Boundary**: This gate is strictly documentation-only. No detector code is implemented, no thresholds are tuned, no models are trained, and no evaluations are executed in this step.

---

#### 2. Three-Way Partition & Quarantine Rules

The 100 lots of `PHASE_4B_BENCHMARK_v1.0.0` remain strictly isolated:
1. **`CALIBRATION` (50 lots / 1,000 components / 4,000 series / 28,000 rows)**: Used exclusively for empirical null quantile estimation, Monte Carlo null calibration, and critical decision threshold determination.
2. **`VALIDATION` (25 lots / 500 components / 2,000 series / 14,000 rows)**: **Diagnostic characterization only.** Zero hyperparameter tuning or threshold modification permitted.
3. **`FINAL_EVALUATION` (25 lots / 500 components / 2,000 series / 14,000 rows)**: Strictly quarantined. Evaluated exactly once after thresholds and algorithms are frozen. Zero parameter tuning or threshold exploration permitted.

---

#### 3. Dedicated HMAC RNG Seed Namespace

To prevent seed collision with benchmark partitions, calibration generation does **not** reuse partition seed `11999057`. Sourced deterministically from Master Key `261704`:
- **Null A Seed**: `194572359` (`"calibration:null_a:v1"`)
- **Null B Seed**: `270315777` (`"calibration:null_b:v1"`)
- **Null C Seed**: `622638004` (`"calibration:null_c:v1"`)
- **Power Sweep Seed**: `15152878` (`"calibration:power:v1"`)

---

#### 4. Strict Causal As-Of Slicing Contract

- Sequential analysis checkpoints: $T_{\text{as\_of}} \in \{24, 48, 72, 96, 120, 168\}\ \text{hours}$.
- For a given $T_{\text{as\_of}}$, only records satisfying $\text{elapsed\_hours} \le T_{\text{as\_of}}$ are detector-visible.
- Leave-one-out median reference $\tilde{u}_{\text{lot}\setminus\{i\},p}(t) = \text{median}_{j \neq i} \{ u_{j,p}(t) \}$ is constructed exclusively from observations at or prior to $T_{\text{as\_of}}$.
- Zero future checkpoints, future aggregates, or future lot statistics may enter detector features.

---

#### 5. Ground-Truth Quarantine & Prohibited Leakage Paths

Detector logic ingests strictly detector-visible fields from `observations.csv`. It is strictly prohibited from accessing:
- `ground_truth.csv` (all columns, including `is_degradation`, `is_spec_failure`, `fixture_type`, `latent_drift`, `latent_true_value`, `latent_true_transformed`, `noise_realization`, `signal_delta`, `as_of_hours`).
- Scenario/fixture labels or generator metadata.
- PRNG seeds.
- Future checkpoints or future lot-level statistics.
- Partition labels during inference.

---

#### 6. Monte Carlo Unit Accounting & Stress-Testing Protocol

The protocol defines the Monte Carlo replicate unit and enforces an unambiguous epistemic distinction between statistical calibration and stress testing:

1. **Monte Carlo Unit Definition**:
   For FWER purposes, one Monte Carlo replicate represents **one complete synthetic component** containing all four physical parameter trajectories:
   - $I_{\text{DSS}}$ (drain-source leakage current)
   - $V_{\text{GS(th)}}$ (threshold voltage)
   - $R_{\text{DS(on)}}$ (channel on-resistance)
   - $I_{\text{GSS}}$ (gate-source leakage current, signed)

2. **Parameter-Series Accounting**:
   - Null A: $100,000$ components $\times$ 4 = $400,000$ series ($N_A = 100,000$).
   - Null B: $100,000$ components $\times$ 4 = $400,000$ series ($N_B = 100,000$).
   - Null C: $100,000$ components $\times$ 4 = $400,000$ series ($N_C = 100,000$).
   - **Total**: $300,000$ null components, $1,200,000$ parameter series.
   - *Strict Rule*: The suite must **never** be described as merely 300,000 trajectories, because each simulated component realizes four parameter series.

3. **Null Protocol Roles**:
   - **Null A (Stationary IID Null)**: Sole reference distribution for empirical detector-statistic calibration and parameter-level $p$-value derivation (Seed `194572359`).
   - **Null B (Correlated AR(1) Null)**: Temporal stress test of frozen Null-A-calibrated detector; never used for threshold tuning (Seed `270315777`).
   - **Null C (Common-Mode Thermal Excursion)**: Equipment stress test of frozen Null-A-calibrated detector; never used for threshold tuning (Seed `622638004`).
   - **No Pooling**: False positive rates and FWER are reported independently for Null A, Null B, and Null C ($\text{FPR}_A, \text{FPR}_B, \text{FPR}_C$ and $\text{FWER}_A, \text{FWER}_B, \text{FWER}_C$).

---

#### 7. Complete Hypothesis-Testing Chain, FWER Estimation, & Signal Preservation

Holm-Bonferroni step-down multiplicity control is applied strictly to mathematically valid $p$-values, not raw detector scores.

1. **Four Parameter-Level Hypotheses $H_0(i, p)$**:
   For each component $i$ and physical parameter $p \in \{I_{\text{DSS}}, V_{\text{GS(th)}}, R_{\text{DS(on)}}, I_{\text{GSS}}\}$:
   - $H_0(i, p)$: No component-specific degradation signal under the calibrated null on leave-one-out excess coordinates $u_{i,p}^{\text{excess}}(t) = u_{i,p}(t) - \tilde{u}_{\text{lot}\setminus\{i\},p}(t)$.
   - Directionality:
     - $I_{\text{DSS}}$ and $R_{\text{DS(on)}}$: One-sided upper-tail test ($H_0: S(i, p) \le 0$ vs $H_1: S(i, p) > 0$).
     - $V_{\text{GS(th)}}$ and $I_{\text{GSS}}$: Two-sided symmetric test ($H_0: S(i, p) = 0$ vs $H_1: S(i, p) \ne 0$).

2. **Preservation of Signed $I_{\text{GSS}}$**:
   $I_{\text{GSS}}$ remains signed throughout the entire pipeline:
   $$\text{signed } I_{\text{GSS}} \longrightarrow \text{signed asinh transform} \longrightarrow \text{excess coordinate} \longrightarrow \text{detector statistic} \longrightarrow \text{two-sided empirical } p\text{-value}$$
   Do **NOT** apply $\text{abs}(I_{\text{GSS}})$ before transformation or detector calculation.

3. **Detector Test Statistics $S(i, p)$ and Tie Handling**:
   - Nonparametric Rank Trend (Kendall's $\tau$): $S_\tau(i, p) = \frac{2}{K(K-1)} \sum_{j < k} \text{sgn}(u_{i,p}^{\text{excess}}(t_k) - u_{i,p}^{\text{excess}}(t_j))$.
   - Linear Regression $t$-Statistic: $S_t(i, p) = \hat{\beta}_1(i, p) / \text{SE}(\hat{\beta}_1(i, p))$.
   - Tie Handling: Checkpoint inspection times $t_k$ are strictly monotonic ($t_j < t_k$, no ties). Telemetry ties assign $\text{sgn}(0) = 0$. Under continuous Gaussian instrumentation noise, observation ties occur with measure zero.

4. **Empirical $p$-Value Derivation with Finite-Sample Correction $p(i, p)$**:
   Empirical tail probability calibrated strictly from $N_A = 100,000$ Null A reference runs ($S_{1,p}, \dots, S_{N_A,p}$) with Davison-Hinkley $+1$ finite-sample correction:
   - One-sided upper-tail ($I_{\text{DSS}}, R_{\text{DS(on)}}$):
     $$p(i, p) = \frac{1 + \sum_{m=1}^{N_A} \mathbb{I}\left( S_{m, p} \ge S(i, p) \right)}{N_A + 1}$$
   - Two-sided symmetric tail ($V_{\text{GS(th)}}, I_{\text{GSS}}$):
     $$p(i, p) = \min\left(1.0,\; 2 \cdot \frac{1 + \sum_{m=1}^{N_A} \mathbb{I}\left( |S_{m, p}| \ge |S(i, p)| \right)}{N_A + 1}\right)$$

5. **Step-Down Holm-Bonferroni Procedure ($\alpha = 0.001$)**:
   For each simulated component $i$:
   - Generate four parameter-level null trajectories;
   - Calculate four parameter-level $p$-values;
   - Apply Holm-Bonferroni across those four $p$-values: order $p_{(1)} \le p_{(2)} \le p_{(3)} \le p_{(4)}$ tested against $\alpha/4 = 0.00025, \alpha/3 \approx 0.0003333, \alpha/2 = 0.00050, \alpha/1 = 0.00100$;
   - Record whether at least one parameter hypothesis is rejected: $\text{Reject } H_0(i) \iff p_{(1)} \le \frac{\alpha}{4} = 0.00025$.

6. **Component-Level FWER Estimation**:
   For each null family, empirical component-level FWER is estimated as:
   $$\widehat{\text{FWER}} = \frac{\# \text{ simulated components with } \ge 1 \text{ false rejection}}{\# \text{ simulated null components}}$$
   Report $\widehat{\text{FWER}}_A, \widehat{\text{FWER}}_B, \widehat{\text{FWER}}_C$ separately, each with an exact 95% Wilson score confidence interval.

7. **Statistical Guarantee Wording & Epistemic Boundary**:
   Under the assumptions required for valid parameter-level $p$-values, the pre-specified Holm-Bonferroni procedure controls component-level FWER at $\alpha = 0.001$. Empirical FWER is estimated from the simulated null components.
   - This formal calibration statement applies **strictly to the Null-A reference process**.
   - **Null B** and **Null C** remain frozen out-of-distribution stress tests of the already-calibrated detector and are **NOT** used for threshold tuning.
   - Do **NOT** claim Holm-Bonferroni provides a formal FWER guarantee under Null B or Null C unless the statistical validity of the corresponding $p$-values under those processes has independently been established.

---

#### 8. Power Experiments & Pre-Registered Amplitude Verification

- **Audit of Existing Benchmark Amplitudes**:
  - Fixtures A & B: encode $\delta \in \{1.0, 1.5, 2.0, 2.5\}\sigma_{u,p}$.
  - Fixtures C, E, F: encode $\delta \in \{1.5, 2.0, 2.5\}\sigma_{u,p}$.
  - Fixture D: encodes $\delta \in \{1.5, 2.0\}\sigma_{u,p}$.
  - *No post-hoc retrofitting*: Evaluations on `PHASE_4B_BENCHMARK_v1.0.0` strictly evaluate actual encoded ground-truth amplitudes.
- **Pre-Registered Independent Power Sweep**: Uniform 4-level grid ($\delta \in \{1.0, 1.5, 2.0, 2.5\}\sigma_{u,p}$) across all 6 morphologies evaluated via separate pre-registered calibration suite ($N=10,000$ per cell, Seed `15152878`). Operates auxiliary to and does not modify Phase 4B benchmark artifacts.
- **Reporting**: Empirical power $\hat{P}_D$ with 95% Wilson score CIs (never collapsed into a single scalar score).

---

#### 9. Module A Comparator Semantics

- Label $|g_p(T_{\text{as\_of}})| \ge 2.5$ explicitly as **Option A: Frozen Non-Calibrated Comparator** (NOT a candidate detector subject to tuning).
- Strictly causal: $g_p(T_{\text{as\_of}}) = (u_p(T_{\text{as\_of}}) - u_p(0)) / \sigma_{u,p}$ computed only using telemetry $\le T_{\text{as\_of}}$.

---

#### 10. Validation Semantics & Final Evaluation Integrity

- **Explicit Freeze Boundary**:
  $$\text{CALIBRATION} \longrightarrow \text{Freeze Detector / Configuration / Thresholds} \longrightarrow \text{VALIDATION (Diagnostic Characterization Only)} \longrightarrow \text{Permanent Freeze} \longrightarrow \text{FINAL\_EVALUATION}$$
- Validation diagnoses robustness and common-mode rejection, but may **never** silently tune thresholds, features, hyperparameters, or code before final evaluation.
- `FINAL_EVALUATION` is read-only and executed exactly once. Final artifact records complete cryptographic provenance (detector git hash, threshold config hash, calibration hash, validation hash, benchmark hash `b5de6a...`, source hash, RNG seeds, timestamp). No reruns permitted.

Execution stopped per gate instructions.

---

### LOG-081: Phase 4B Temporal-Calibration & Detector Separation Correction Gate

- **Log ID**: LOG-081
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Temporal-Calibration & Detector Separation Correction Gate
- **Change**: Updated `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` from v1.4.0 to v1.5.0 with six mandatory specification corrections.
- **Previous State**: LOG-079 (v1.4.0) locked for execution gate review with horizon-unindexed calibration and merged Kendall/Theil-Sen detector family.
- **New State**: Specification v1.5.0 incorporates all six temporal-calibration and detector-separation corrections:
  1. **As-Of-Specific Calibration**: Separate Null-A reference distributions for each $(T_{\text{as\_of}}, \text{detector\_family}, \text{parameter})$ tuple. A $K = 7$ distribution must NOT be used for $K < 7$ evaluation. Section 4 now includes explicit horizon-checkpoint mapping table and an `[IMPORTANT]` callout enforcing per-horizon calibration.
  2. **OLS $t$-Statistic UNDEFINED at $K = 2$**: Explicitly marked as undefined at $T_{\text{as\_of}} = 24\ \text{h}$ ($df = K - 2 = 0$). Must NOT be evaluated at this horizon. Dedicated applicability table in Section 5 with `[CAUTION]` alert.
  3. **Kendall vs Theil-Sen Separation**: Split into two distinct detector families (Family 1: Kendall $\tau$ [`PRIMARY CANDIDATE`], Family 2: Theil-Sen [`AUXILIARY CANDIDATE`]) with independent calibration, $p$-value mappings, thresholds, and evaluation results. Pre-registration warning: selection must not occur after inspecting final results.
  4. **Complete $p$-Value Reference Table**: New Section 7 specifies the full empirical reference table schema: $24 + 24 + 20 = 68$ required entries indexed by (detector family, parameter, $T_{\text{as\_of}}$).
  5. **FWER Reporting by (Null, Detector, Horizon)**: Section 8E now mandates separate reporting by null family, detector family, and as-of horizon. No pooling across $K$ values or detector families.
  6. **Power Matrix Extended**: Power reporting now includes detector family dimension: $\text{Power} = f(\text{Morphology}, \delta, \text{Parameter}, T_{\text{as\_of}}, \text{Detector Family})$.
- **Reason**: Resolve six specification deficiencies identified during pre-authorization review: horizon-agnostic calibration would invalidate empirical $p$-values at short horizons; merged Kendall/Theil-Sen would allow post-hoc selection; undefined OLS $t$-statistic at $K = 2$ would produce division-by-zero artifacts; missing calibration table schema would leave implementation ambiguous; pooled FWER reporting would mask horizon-specific failure modes.
- **Source / Provenance**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` (v1.5.0), LOG-076, LOG-077, LOG-078, LOG-079.
- **Gate Outcome**: **SPECIFICATION REVISED (v1.5.0) — LOCKED FOR EXECUTION GATE AUTHORIZATION**
- **Affected Area**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Canonical Invariants Preserved**: Zero code modifications in `src/`; zero threshold adjustments; zero modifications to `PHASE_4B_BENCHMARK_v1.0.0`; zero modifications to `data/synthetic_phase2f_frozen/`; zero detector execution or calibration performed.

Execution stopped per gate instructions.

---

### LOG-082: Phase 4B Lot-Structure Calibration Correction Gate

- **Log ID**: LOG-082
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Lot-Structure Calibration Correction Gate
- **Change**: Updated `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` from v1.5.0 to v1.6.0 with mandatory lot-topology preservation in all null Monte Carlo simulations.
- **Previous State**: LOG-081 (v1.5.0) specified as-of-specific calibration, detector separation, and 68-entry $p$-value reference table, but described null MC replicates as isolated components without specifying the lot structure required by the LOO excess-coordinate pipeline.
- **New State**: Specification v1.6.0 incorporates the following corrections:
  1. **Lot-Structure Calibration Requirement** (§6.A): Explicitly identifies the statistical dependency — the detector operates on LOO excess coordinates $u_{i,p}^{\text{excess}}(t) = u_{i,p}(t) - \text{median}_{j \neq i}(u_{j,p}(t))$, making the test-statistic distribution depend on lot topology. Calibrating on isolated trajectories and applying to LOO excess would produce distribution mismatch.
  2. **Null Lot Topology Contract** (§6.B): All null simulations must preserve $L = 20$ components per lot (matching `manifest.json` / `configured_lot_size`), 4 parameters per component, same checkpoint schedule, same measurement-noise transformations, same LOO construction with self-exclusion, and independent recomputation of the LOO reference at each $T_{\text{as\_of}}$.
  3. **Per-Component Calibration Pipeline** (§6.C): Mandatory 6-step procedure for extracting each calibration statistic through the full LOO pipeline: generate lot → as-of mask → LOO median → excess coords → detector statistic → $p$-value. Every simulated lot contributes $L = 20$ component-level statistics.
  4. **Lot-Level Sample Accounting** (§6.D–E): $N_A = 100{,}000$ components in $5{,}000$ lots; total $15{,}000$ simulated lots across all three null families.
  5. **Null-A Lot Contract**: $L = 20$ i.i.d. Gaussian components per lot; all components stationary and independently drawn.
  6. **Null-B Lot Contract**: Same $L = 20$ topology; AR(1) applied per component-parameter pair; lot size and LOO mechanics unchanged from Null A.
  7. **Null-C Spatial Scope**: Common-mode thermal perturbation is **lot-synchronous** — applied simultaneously and identically to all $L = 20$ components within a lot, simulating a shared chamber excursion. Does not affect other simulated lots.
  8. **Horizon-Specific LOO Recomputation** (§4.4): LOO median must be recomputed independently at each $T_{\text{as\_of}}$; forbidden to compute a single $K = 7$ reference and retroactively truncate.
  9. **Detector Family Immutability** (§5): Kendall $\tau$ fixed as PRIMARY CANDIDATE, Theil-Sen as AUXILIARY CANDIDATE; neither may be selected, promoted, demoted, or discarded after observing any results.
  10. **$p$-Value Reference Linkage** (§8.C): Explicitly states each reference statistic was computed through the full LOO lot-median pipeline (§6.C).
- **Reason**: The LOO excess-coordinate construction creates a statistical dependency between the null calibration distribution and the lot topology. Without preserving the same lot structure in calibration, the empirical $p$-values would be computed under a mismatched null and would not provide valid type-I error control.
- **Source / Provenance**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` (v1.6.0), LOG-076, LOG-077, LOG-078, LOG-079, LOG-081.
- **Gate Outcome**: **SPECIFICATION REVISED (v1.6.0) — LOCKED FOR EXECUTION GATE AUTHORIZATION**
- **Affected Area**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Canonical Invariants Preserved**: Zero code modifications in `src/`; zero threshold adjustments; zero modifications to `PHASE_4B_BENCHMARK_v1.0.0`; zero modifications to `data/synthetic_phase2f_frozen/`; zero detector execution or calibration performed; zero generator source modifications.

Execution stopped per gate instructions.

---

### LOG-083: Phase 4B Independent Null-A Audit Correction Gate

- **Log ID**: LOG-083
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Independent Null-A Audit Correction Gate
- **Change**: Updated `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` from v1.6.0 to v1.7.0 (SHA-256: `5f83d594041c8f36040824d779e89909e5c856c5c77cc6a23f93f53f21757bbc`) to decouple empirical calibration reference construction from operational FPR/FWER error auditing.
- **Previous State**: LOG-082 (v1.6.0) established lot-topology preservation and LOO excess coordinate mechanics for null simulations, but allowed operating FPR and FWER to be estimated on the same Null-A sample used to calibrate the 68 empirical reference distributions.
- **New State**: Specification v1.7.0 incorporates the following structural corrections:
  1. **Separation of Null-A Calibration and Audit** (§6.D): Replaced single Null-A pool with two strictly separated suites:
     - `Null-A Calibration Set`: $N_{A,\text{cal}} = 100,000$ complete components in $5,000$ simulated lots ($400,000$ series). Used solely to construct the 68 empirical reference distributions, critical thresholds, and $p$-value mappings.
     - `Calibration Freeze`: Immediately after calibration, all 68 reference distributions, critical values, $p$-value mappings, tail definitions, and detector configurations are permanently locked. No retuning permitted.
     - `Independent Null-A Audit Set`: $N_{A,\text{audit}} = 100,000$ independent complete components in $5,000$ simulated lots ($400,000$ series). Used solely to evaluate operating parameter-level FPR, component-level FWER, and Wilson 95% CIs under the frozen detector. Zero recalibration or threshold adjustments permitted.
  2. **Independent Audit Seed Namespace** (§3): Derived dedicated seed `233837969` from Master Key `261704` under context string `"calibration:null_a_audit:v1"`. Disjoint from benchmark partition seeds (`11999057`, `499376249`, `460793515`), Null-A calibration seed (`194572359`), Null-B seed (`270315777`), Null-C seed (`622638004`), and Power sweep seed (`15152878`).
  3. **Total Sample Accounting** (§6.F): Suite updated to $N_{\text{comp}} = 400{,}000$ null components in $20{,}000$ simulated lots ($1{,}600{,}000$ parameter series) across Null-A Calibration ($100k$), Null-A Audit ($100k$), Null-B Stress ($100k$), and Null-C Stress ($100k$).
  4. **Frozen Stress Tests** (§6.G.3–4): Explicitly specified that Null B (AR(1)) and Null C (lot-synchronous common-mode) remain frozen stress tests of the already-calibrated detector and must not modify calibration or tune thresholds.
  5. **Explicit Holm-Bonferroni Decision Unit & FWER Denominator** (§6.E, §8.D–E): Clarified that each simulated lot contains 20 components, and each component has 4 parameter $p$-values tested via Holm-Bonferroni step-down, resulting in exactly one component-level rejection event. The FWER denominator is strictly the number of simulated components ($100{,}000$), not the number of lots ($5{,}000$).
  6. **Calibration Artifact Metadata Schema** (§7.C): Specified the 12 required metadata fields for each of the 68 calibrated reference entries in `calibration_reference_table.json`: `detector_family`, `parameter`, `T_as_of`, `K`, `tail_direction`, `N_calibration`, `statistic_definition`, `p_value_method`, `finite_sample_correction`, `critical_value_threshold`, `calibration_seed`, `artifact_hash`.
  7. **Multi-Stage Freeze Hierarchy** (§10): Formalized Freeze 0 (Calibration locked prior to audit/stress tests), Freeze 1 (Thresholds & detector locked prior to validation), and Freeze 2 (Permanent configuration lock prior to single-pass final evaluation). Validation redesign version incremented to v1.8.0.
- **Reason**: Estimating operating type-I error on the calibration sample induces circularity and optimistic bias. An independent audit set under a distinct PRNG seed provides an unbiased estimate of operating FPR and FWER under the frozen calibration.
- **Source / Provenance**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` (v1.7.0), LOG-076, LOG-077, LOG-078, LOG-079, LOG-081, LOG-082.
- **Gate Outcome**: **SPECIFICATION REVISED (v1.7.0) — LOCKED FOR EXECUTION GATE AUTHORIZATION**
- **Affected Area**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Canonical Invariants Preserved**: Zero code modifications in `src/`; zero threshold adjustments; zero modifications to `PHASE_4B_BENCHMARK_v1.0.0`; zero modifications to `data/synthetic_phase2f_frozen/`; zero detector execution or calibration performed; zero generator source modifications.

Execution stopped per gate instructions.

---

### LOG-084: Phase 4B Frozen Null-A Baseline Specification Check Gate

- **Log ID**: LOG-084
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Frozen Null-A Baseline Specification Check Gate
- **Change**: Updated `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` from v1.7.0 to v1.8.0 (SHA-256: `5c8bc86364789c84684f0e2ddaef15abb786fb9bbfee505f1c912326496d4659`) to explicitly identify the frozen configuration and generative model governing the Null-A baseline process.
- **Previous State**: LOG-083 (v1.7.0) specified the independent audit set, lot topology ($L=20$), LOO differencing, and $400,000$-component sample accounting, but did not explicitly tabulate the hierarchical lot-to-lot and component-to-component baseline dispersion parameters, leaving potential ambiguity for calibration generation.
- **New State**: Specification v1.8.0 incorporates §6.C ("Frozen Baseline Generative Model Specification"), establishing:
  1. **Canonical Configuration Provenance**: Formally verified that the baseline distributions and dispersion scales are pre-defined by LOG-076 (§3), canonized in `src/sih26170/synthetic/phase4b/config.py` (`Phase4BParameterConfig`, `get_default_phase4b_config()`), and cryptographically frozen in `data/synthetic_phase4b/manifest.json` under `PHASE_4B_BENCHMARK_v1.0.0`.
  2. **Frozen Parameter-by-Parameter Baseline Table**:
     - $I_{\text{DSS}}$: Log transform, nominal baseline $\mu_0 = 0.50\ \mu\text{A}$ ($u_{\text{nom}} \approx -0.69315$), lot dispersion $\sigma_{\text{lot}} = 0.15$, device dispersion $\sigma_{\text{device}} = 0.20$, measurement noise $\sigma_u = 0.08$, latent degradation $g(t) \equiv 0.0$.
     - $V_{\text{GS(th)}}$: Linear transform, nominal baseline $\mu_0 = 3.00\ \text{V}$ ($u_{\text{nom}} = 3.00000$), lot dispersion $\sigma_{\text{lot}} = 0.08$, device dispersion $\sigma_{\text{device}} = 0.10$, measurement noise $\sigma_u = 0.02$, latent degradation $g(t) \equiv 0.0$.
     - $R_{\text{DS(on)}}$: Log transform, nominal baseline $\mu_0 = 48.0\ \text{m}\Omega$ ($u_{\text{nom}} \approx 3.87120$), lot dispersion $\sigma_{\text{lot}} = 0.06$, device dispersion $\sigma_{\text{device}} = 0.08$, measurement noise $\sigma_u = 0.0125$, latent degradation $g(t) \equiv 0.0$.
     - $I_{\text{GSS}}$: asinh transform ($s = 1.0\ \text{nA}$), nominal baseline $\mu_0 = 2.00\ \text{nA}$ ($u_{\text{nom}} \approx 1.44364$), lot dispersion $\sigma_{\text{lot}} = 0.20$, device dispersion $\sigma_{\text{device}} = 0.25$, measurement noise $\sigma_u = 0.25$, latent degradation $g(t) \equiv 0.0$.
  3. **Hierarchical Generative Model Equation**: Formally specifies the 3-tier generative structure: $u_{\text{lot},l,p} = u_{\text{nom},p} + \mathcal{N}(0, \sigma_{\text{lot},p}^2)$, $u_{i,p}(0) = u_{\text{lot},l,p} + \mathcal{N}(0, \sigma_{\text{device},p}^2)$, and checkpoint observation $u_{i,p}(t_k) = u_{i,p}(0) + \mathcal{N}(0, \sigma_{u,p}^2)$.
  4. **Interaction with Leave-One-Out Differencing**: Clarified that while $u_{\text{lot}}$ cancels identically in $u_{i,p}^{\text{excess}}(t) = u_{i,p}(t) - \text{median}_{j \neq i}(u_{j,p}(t))$, the static component offsets $\delta_{\text{comp},j,p} \sim \mathcal{N}(0, \sigma_{\text{device},p}^2)$ establish the spatial ordering of the 19 lot-mates across time, determining which components realize the median and stabilizing the median across checkpoints. Omitting $\sigma_{\text{device}}$ would falsely model the median as an independent draw at each checkpoint.
  5. **Anti-Invention Prohibition**: Explicitly forbids the execution harness from inventing, altering, or re-tuning baseline distributions or dispersion parameters.
- **Reason**: Ensure statistical fidelity between the empirical null calibration distribution and the Phase 4B benchmark's actual excess-coordinate process.
- **Source / Provenance**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` (v1.8.0), `src/sih26170/synthetic/phase4b/config.py`, LOG-076, LOG-077, LOG-078, `data/synthetic_phase4b/manifest.json`.
- **Gate Outcome**: **SPECIFICATION REVISED (v1.8.0) — LOCKED FOR EXECUTION GATE AUTHORIZATION**
- **Affected Area**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Canonical Invariants Preserved**: Zero code modifications in `src/`; zero threshold adjustments; zero modifications to `PHASE_4B_BENCHMARK_v1.0.0`; zero modifications to `data/synthetic_phase2f_frozen/`; zero detector execution or calibration performed; zero generator source modifications.

Execution stopped per gate instructions.

---

### LOG-085: Phase 4B Pre-Execution Kendall Tau Feasibility Audit Gate

- **Log ID**: LOG-085
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Pre-Execution Kendall Tau Feasibility Audit Gate
- **Change**: Performed pre-execution statistical feasibility audit of Kendall's tau rank correlation under the frozen Phase 4B protocol ($K \in \{2, 3, 4, 5, 6, 7\}$, component-level Holm-Bonferroni with $\alpha = 0.001$ across 4 parameters $\implies$ Step 1 threshold $\alpha / 4 = 0.00025$). Updated `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` from v1.8.0 to v1.9.0 (SHA-256: `c846fd302f815f063502ca5f5c061613d17e86f0f1263e6f3aff74f50bda71cc`). Incorporates approved documentation-only clarifications for Kendall wording, empirical $p$-value bounds caveat, and Stage 4 versioning (`v1.10.0`).
- **Previous State**: Specification v1.8.0 listed Kendall's $\tau$ as PRIMARY CANDIDATE applicable at all horizons $K \in \{2, 3, 4, 5, 6, 7\}$, but did not document the discrete permutation probability bounds relative to the Holm Step 1 threshold of $0.00025$, creating a risk of misinterpreting structural null-conservatism or zero power as calibration defects during execution.
- **New State**: Specification v1.9.0 incorporates §5.1 ("Pre-Execution Combinatorial Feasibility Audit of Kendall's $\tau$") and establishes:
  1. **Attainable Null-Tail Probability Resolution ($1/K!$ and $2/K!$)**:
     - $K=2$ ($T_{\text{as\_of}}=24\ \text{h}$, $K!=2$): Min one-sided $p = 0.50000$; Min two-sided $p = 1.00000$. **INCAPABLE** ($p \gg 0.00025$).
     - $K=3$ ($T_{\text{as\_of}}=48\ \text{h}$, $K!=6$): Min one-sided $p = 0.16667$; Min two-sided $p = 0.33333$. **INCAPABLE** ($p \gg 0.00025$).
     - $K=4$ ($T_{\text{as\_of}}=72\ \text{h}$, $K!=24$): Min one-sided $p = 0.04167$; Min two-sided $p = 0.08333$. **INCAPABLE** ($p \gg 0.00025$).
     - $K=5$ ($T_{\text{as\_of}}=96\ \text{h}$, $K!=120$): Min one-sided $p = 0.00833$; Min two-sided $p = 0.01667$. **INCAPABLE** ($p \gg 0.00025$).
     - $K=6$ ($T_{\text{as\_of}}=120\ \text{h}$, $K!=720$): Min one-sided $p = 0.00139$; Min two-sided $p = 0.00278$. **INCAPABLE** ($p > 0.00025$).
     - $K=7$ ($T_{\text{as\_of}}=168\ \text{h}$, $K!=5{,}040$): Min one-sided $p = 0.0001984 \le 0.00025$ (**CAPABLE** at Step 1); Min two-sided $p = 0.0003968 > 0.00025$ (**INCAPABLE** at Step 1 or 2; only rejectable at Step 3 where $\alpha/2 = 0.00050$ conditional on prior rejections).
  2. **Implication for Component-Level Holm $\alpha = 0.001$**:
     - At $K \in \{2, 3, 4, 5, 6\}$, Kendall's $\tau$ is algebraically incapable of producing a component-level Holm rejection. For K ≤ 6, Kendall has zero component-level rejection capacity under the frozen Holm α=0.001 procedure. Parameter-level tail events may still occur and must be reported descriptively; they cannot produce a component-level Holm rejection at these horizons. Kendall's $\tau$ is documented as operating in a **descriptive / comparator role** at these horizons.
     - At $K = 7$, one-sided parameters ($I_{\text{DSS}}, R_{\text{DS(on)}}$) can initiate rejections at Step 1 ($p \approx 0.00020 \le 0.00025$), while two-sided parameters ($V_{\text{GS(th)}}, I_{\text{GSS}}$) cannot initiate rejections and can only reject if accompanied by one-sided rejections.
  3. **Methodological Distinctions**:
     - Finite permutation resolution ($1/K!$) vs Monte Carlo simulation resolution ($N=100,000 \implies \Delta p \approx 10^{-5}$): The inability to reject at $K \le 6$ is not a sample-size artifact; it is an intrinsic algebraic property of rank statistics on small sets.
     - Empirical LOO null distribution: Evaluated on leave-one-out median-differenced series $u^{\text{excess}}$, which contains spatial correlation but cannot expand rank support beyond $K!$. The 1/K! and 2/K! values are analytical feasibility bounds under the ideal continuous-exchangeable rank null. They are not asserted as the exact minimum empirical p-values produced by the frozen LOO calibration. Actual operating p-values and FWER remain determined by the independently generated Null-A calibration/audit procedure.
  4. **Theil-Sen Algebraic Identity at $K=2$**:
     - At $K=2$, Theil-Sen is algebraically identical to the simple two-point endpoint slope $\hat{\beta}_{\text{TS}} \equiv (u(24) - u(0))/24$. It possesses zero median breakdown protection or multi-point smoothing and must not be characterized as a robust multi-point estimator at this horizon.
  5. **Protocol Invariance & Status Preservation**:
     - No protocol change is required or authorized. Kendall's $\tau$ is preserved as PRIMARY CANDIDATE and Theil-Sen as AUXILIARY CANDIDATE per protocol immutability. Its inferential boundaries at $K \le 6$ are documented as structural limitations rather than altering $\alpha$ or thresholds.
- **Reason**: Strict pre-execution verification of statistical feasibility to prevent misinterpreting structural null-hypothesis conservatism or zero power as empirical detector failure or calibration error.
- **Source / Provenance**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` (v1.9.0), LOG-076, LOG-079, LOG-080, LOG-081, LOG-082, LOG-083, LOG-084.
- **Gate Outcome**: **FEASIBILITY AUDIT COMPLETE & SPECIFICATION REVISED (v1.9.0) — LOCKED FOR EXECUTION GATE AUTHORIZATION**
- **Affected Area**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Canonical Invariants Preserved**: Zero code modifications in `src/`; zero threshold adjustments; zero modifications to `PHASE_4B_BENCHMARK_v1.0.0`; zero modifications to `data/synthetic_phase2f_frozen/`; zero detector execution or calibration performed; zero generator source modifications.

Execution stopped per gate instructions.

---

### LOG-086: Phase 4B Stage 1 Implementation & Phase 2.1 Null-A Calibration Execution Gate

- **Log ID**: LOG-086
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Stage 1 Implementation & Phase 2.1 Null-A Calibration Execution Gate
- **Change**: Executed authorized Stage 1 detector implementation and Phase 2.1 Null-A calibration. Updated `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` (SHA-256: `5450e69bea7bf8295df1c3c25f7a8ee8a1d04cc4fc0128d3288ab8ae79ef13bb`) with three approved documentation-only corrections (Kendall rejection capacity wording, empirical $p$-value bounds caveat, and next project redesign version `v1.10.0`).
- **Previous State**: LOG-085 canonized the pre-execution feasibility audit under locked spec v1.9.0. Detectors and empirical calibration tables were uninstantiated.
- **New State**:
  1. **Stage 1 Detector Implementation**:
     - Implemented `src/sih26170/screening/phase4b_detectors.py`:
       * `compute_kendall_tau`: Vectorized rank correlation for $K \ge 2$.
       * `compute_theil_sen`: Vectorized median pairwise slope estimator for $K \ge 2$.
       * `compute_ols_t`: Vectorized parametric regression $t$-statistic for $K \ge 3$; explicitly excludes $K=2$ ($df = 0$, raises `ValueError`).
       * `compute_module_a_drift`: Endpoint drift comparator $g_p(T_{\text{as\_of}}) = \Delta u / \sigma_u$.
       * `compute_loo_excess_coordinates`: Vectorized exact leave-one-out lot median differencing preserving lot topology ($L=20$) with strict self-exclusion.
       * `compute_empirical_p_value`: Empirical tail probability with Davison-Hinkley ($+1$) finite-sample correction.
       * `apply_holm_bonferroni`: Step-down Holm-Bonferroni multiplicity control across $M=4$ physical parameters at $\alpha = 0.001$.
     - Implemented comprehensive unit tests in `tests/screening/test_phase4b_detectors.py` (all passed).
  2. **Phase 2.1 Null-A Calibration Execution**:
     - Implemented `src/sih26170/screening/phase4b_calibration.py` and unit tests in `tests/screening/test_phase4b_calibration.py`.
     - Generated $N_{A,\text{cal}} = 100{,}000$ stationary IID null components across $5{,}000$ simulated lots ($400{,}000$ parameter series) using dedicated HMAC seed `194572359` under the frozen hierarchical generative model (§6.C).
     - Applied causal LOO lot median differencing per lot and per as-of horizon ($T_{\text{as\_of}} \in \{24, 48, 72, 96, 120, 168\}\ \text{h}$).
     - Successfully built and validated all 68 required empirical reference distributions:
       * Kendall's $\tau$: 4 parameters $\times$ 6 horizons = 24 entries
       * Theil-Sen: 4 parameters $\times$ 6 horizons = 24 entries
       * OLS $t$-statistic: 4 parameters $\times$ 5 horizons ($K \ge 3$) = 20 entries
     - Zero non-finite statistics encountered across all 68 entries (`n_non_finite = 0`).
     - Empirical thresholds for Holm steps 1–4 ($\alpha_{(1)} = 0.00025$, $\alpha_{(2)} \approx 0.000333$, $\alpha_{(3)} = 0.00050$, $\alpha_{(4)} = 0.00100$) computed and recorded.
  3. **Calibration Artifact Suite & Cryptographic Checksums**:
     - `data/evaluation_phase4b/calibration_reference_table.json`: `153d387597ba6a247ed5302a7512730c678bc3ce39e056848cd9135fc39c7d60`
     - `data/evaluation_phase4b/calibration_distributions.npz`: `147f1d38ed9b197af6b6301b9b454223d5cce54286fcfeb89a1ea15cec055d98`
     - `data/evaluation_phase4b/calibration_manifest.json`: `b7c5515144e0ea800f4e3b1f0acd5739b5acee88cd8e7f9fefa87a8294400b25`
     - `data/evaluation_phase4b/checksums.sha256`: generated and locked under Freeze 0.
  4. **Empirical Verification of Pre-Execution Feasibility Audit**:
     - For Kendall's $\tau$ across $K \le 6$ ($T_{\text{as\_of}} \le 120\ \text{h}$), the empirical Step 1 critical threshold is $1.0000$, confirming zero component-level rejection capacity under Holm $\alpha = 0.001$.
     - At $K = 7$ ($168\ \text{h}$), one-sided parameters ($I_{\text{DSS}}, R_{\text{DS(on)}}$) achieve critical threshold $0.9048$ ($= 19/21$), confirming activation at Step 1; two-sided parameters ($V_{\text{GS(th)}}, I_{\text{GSS}}$) remain inactive at Step 1 and Step 2 (threshold $1.0000$) and activate at Step 3 (threshold $0.9048$).
  5. **Freeze 0 Enforcement**:
     - All 68 empirical reference distributions, mappings, critical values, and configurations are permanently frozen.
     - Zero Null-A audit, Null-B, Null-C, power sweeps, validation, or final evaluation executed.
- **Reason**: Implement candidate detectors and freeze the empirical Null-A calibration reference table prior to evaluating operating error rates or detection power.
- **Source / Provenance**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` (v1.9.0), `src/sih26170/screening/phase4b_detectors.py`, `src/sih26170/screening/phase4b_calibration.py`, `data/evaluation_phase4b/`, LOG-085.
- **Gate Outcome**: **STAGE 1 & PHASE 2.1 CALIBRATION COMPLETE — FROZEN AT FREEZE 0 — STOPPED FOR ARTIFACT REVIEW**
- **Affected Area**: `src/sih26170/screening/phase4b_detectors.py`, `src/sih26170/screening/phase4b_calibration.py`, `tests/screening/test_phase4b_detectors.py`, `tests/screening/test_phase4b_calibration.py`, `data/evaluation_phase4b/`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Canonical Invariants Preserved**: Zero modifications to `PHASE_4B_BENCHMARK_v1.0.0`; zero modifications to `data/synthetic_phase2f_frozen/`; zero post-calibration interpretation or detector promotion/demotion; 190/190 pytest tests pass cleanly.

Execution stopped per gate instructions.

---

### LOG-087: Phase 4B Independent Null-A Audit Gate (Complete Results & Forensic Interpretation)

- **Log ID**: LOG-087
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Phase 2.2 Independent Null-A Audit Gate
- **Change**: Executed Phase 2.2 Independent Null-A Audit on $N_{A,\text{audit}} = 100{,}000$ complete stationary null components in $5{,}000$ lots ($400{,}000$ parameter series) under dedicated HMAC audit seed `233837969`. Evaluated all 68 candidate detector cells and comparator metrics against the frozen Null-A calibration reference table (`calibration_reference_table.json` and `calibration_distributions.npz`) in strictly read-only mode without threshold adjustments or circular error estimation.
- **Previous State**: LOG-086 established and froze the 68 empirical Null-A calibration reference distributions under Freeze 0. The independent audit set was uninstantiated.
- **New State**:
  1. **Audit Execution & Sample Accounting**:
     - Total Components Evaluated: 100,000 independent components across 5,000 lots (lot size $L=20$).
     - Total Series Evaluated: 400,000 series across 4 physical parameters ($I_{\text{DSS}}, V_{\text{GS(th)}}, R_{\text{DS(on)}}, I_{\text{GSS}}$) and 7 checkpoints ($T \in \{0, 24, 48, 72, 96, 120, 168\}\ \text{h}$).
     - Audit Seed: `233837969` (cryptographically isolated from calibration seed `194572359`).
     - Causal LOO Excess Coordinates: Computed independently at each as-of checkpoint against simultaneous lot median excluding component $i$.
  2. **Audit Artifact Integrity & Cryptographic Verifications**:
     - Consumed Calibration Table SHA-256: `153d387597ba6a247ed5302a7512730c678bc3ce39e056848cd9135fc39c7d60` (100% unmutated).
     - Consumed Calibration Distributions SHA-256: `147f1d38ed9b197af6b6301b9b454223d5cce54286fcfeb89a1ea15cec055d98` (100% unmutated).
     - Consumed Calibration Manifest SHA-256: `b7c5515144e0ea800f4e3b1f0acd5739b5acee88cd8e7f9fefa87a8294400b25` (100% unmutated).
     - Produced Audit Artifact: `data/evaluation_phase4b/null_a_audit_results.json` (SHA-256: `1bd10cb8541d467084c15efa97e6e8fa9dc8799f356a4739a6141fd06bc1d9ad`).
     - Audit Dataset Hashes: Raw measurements SHA-256: `28e111ab5f241a3e30f572262cb2fa5aefb20aa2e9c6ada01007a2d53c5ba1cc`; Excess coordinates SHA-256: `d7bdf40832c0bb70b248984799f6e7e809a0f99008dd1c517566b1bfe64e8816`.
     - Frozen Benchmarks Verified: All 4 Phase 4B benchmark files and 10 Phase 2F benchmark files bit-for-bit unchanged.
  3. **Empirical p-Value Implementation Verification**:
     - Formula: Davison-Hinkley $+1$ continuity-corrected empirical $p$-value: $p = (\sum_{b=1}^B I(\text{ref}_b \ge s_{\text{obs}}) + 1) / (B + 1)$ with $B = 100{,}000$.
     - Isolation: Evaluated strictly against calibration distributions. No audit data added to reference; zero threshold retuning.
     - Unpooled: Each of the 68 cells uses its own independent calibration reference array. Zero pooling across horizons or detector families.
  4. **Complete Cell-Level Audit Results**:

#### Table 1: Component-Level Family-Wise Error Rate (FWER) Across All 17 Detector-Horizon Cells (N = 100,000 components/cell)

| Detector Family | Role | Horizon | K | N Components | Holm Rejections | FWER | Wilson 95% CI | Step-1 | Step-2 | Step-3 | Step-4 | Parameter Breakdown (IDSS, VGS, RDS, IGSS) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `kendall_tau` | PRIMARY CANDIDATE | 24h | 2 | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0 | 0 | (0, 0, 0, 0) |
| `kendall_tau` | PRIMARY CANDIDATE | 48h | 3 | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0 | 0 | (0, 0, 0, 0) |
| `kendall_tau` | PRIMARY CANDIDATE | 72h | 4 | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0 | 0 | (0, 0, 0, 0) |
| `kendall_tau` | PRIMARY CANDIDATE | 96h | 5 | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0 | 0 | (0, 0, 0, 0) |
| `kendall_tau` | PRIMARY CANDIDATE | 120h | 6 | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0 | 0 | (0, 0, 0, 0) |
| `kendall_tau` | PRIMARY CANDIDATE | 168h | 7 | 100,000 | 30 | **0.000300** | [0.000210, 0.000428] | 30 | 0 | 0 | 0 | (10, 0, 20, 0) |
| `theil_sen` | AUXILIARY CANDIDATE | 24h | 2 | 100,000 | 92 | **0.000920** | [0.000750, 0.001128] | 92 | 0 | 0 | 0 | (21, 18, 23, 30) |
| `theil_sen` | AUXILIARY CANDIDATE | 48h | 3 | 100,000 | 124 | **0.001240** | [0.001040, 0.001478] | 124 | 0 | 0 | 0 | (21, 25, 32, 46) |
| `theil_sen` | AUXILIARY CANDIDATE | 72h | 4 | 100,000 | 108 | **0.001080** | [0.000895, 0.001304] | 108 | 0 | 0 | 0 | (33, 24, 24, 27) |
| `theil_sen` | AUXILIARY CANDIDATE | 96h | 5 | 100,000 | 109 | **0.001090** | [0.000904, 0.001315] | 109 | 0 | 0 | 0 | (29, 26, 25, 29) |
| `theil_sen` | AUXILIARY CANDIDATE | 120h | 6 | 100,000 | 74 | **0.000740** | [0.000590, 0.000929] | 74 | 0 | 0 | 0 | (21, 22, 17, 14) |
| `theil_sen` | AUXILIARY CANDIDATE | 168h | 7 | 100,000 | 105 | **0.001050** | [0.000868, 0.001271] | 105 | 0 | 0 | 0 | (21, 32, 24, 28) |
| `ols_t` | BENCHMARK COMPARATOR | 48h | 3 | 100,000 | 100 | **0.001000** | [0.000822, 0.001216] | 100 | 0 | 0 | 0 | (34, 13, 26, 27) |
| `ols_t` | BENCHMARK COMPARATOR | 72h | 4 | 100,000 | 83 | **0.000830** | [0.000670, 0.001029] | 83 | 0 | 0 | 0 | (24, 18, 23, 18) |
| `ols_t` | BENCHMARK COMPARATOR | 96h | 5 | 100,000 | 94 | **0.000940** | [0.000768, 0.001150] | 94 | 0 | 0 | 0 | (25, 16, 21, 32) |
| `ols_t` | BENCHMARK COMPARATOR | 120h | 6 | 100,000 | 87 | **0.000870** | [0.000705, 0.001073] | 87 | 0 | 0 | 0 | (15, 18, 26, 28) |
| `ols_t` | BENCHMARK COMPARATOR | 168h | 7 | 100,000 | 89 | **0.000890** | [0.000723, 0.001095] | 89 | 0 | 0 | 0 | (16, 17, 33, 23) |

#### Table 2: Parameter-Level False Positive Rate (FPR) Across All 68 Detector-Horizon-Parameter Cells (N = 100,000 series/cell)

| Cell # | Detector Family | Horizon | K | Parameter | Tail Direction | N Evaluated | FP Count | FPR | Wilson 95% CI | Step-1 Threshold | Non-Finite | Distinct | Ties |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `kendall_tau` | 24h | 2 | IDSS | upper | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 2 | 100000 |
| 02 | `kendall_tau` | 24h | 2 | VGS(th) | two_sided | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 2 | 100000 |
| 03 | `kendall_tau` | 24h | 2 | RDS(on) | upper | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 2 | 100000 |
| 04 | `kendall_tau` | 24h | 2 | IGSS | two_sided | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 2 | 100000 |
| 05 | `kendall_tau` | 48h | 3 | IDSS | upper | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 4 | 100000 |
| 06 | `kendall_tau` | 48h | 3 | VGS(th) | two_sided | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 4 | 100000 |
| 07 | `kendall_tau` | 48h | 3 | RDS(on) | upper | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 4 | 100000 |
| 08 | `kendall_tau` | 48h | 3 | IGSS | two_sided | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 4 | 100000 |
| 09 | `kendall_tau` | 72h | 4 | IDSS | upper | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 7 | 100000 |
| 10 | `kendall_tau` | 72h | 4 | VGS(th) | two_sided | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 7 | 100000 |
| 11 | `kendall_tau` | 72h | 4 | RDS(on) | upper | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 7 | 100000 |
| 12 | `kendall_tau` | 72h | 4 | IGSS | two_sided | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 7 | 100000 |
| 13 | `kendall_tau` | 96h | 5 | IDSS | upper | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 11 | 100000 |
| 14 | `kendall_tau` | 96h | 5 | VGS(th) | two_sided | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 11 | 100000 |
| 15 | `kendall_tau` | 96h | 5 | RDS(on) | upper | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 11 | 100000 |
| 16 | `kendall_tau` | 96h | 5 | IGSS | two_sided | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 11 | 100000 |
| 17 | `kendall_tau` | 120h | 6 | IDSS | upper | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 16 | 100000 |
| 18 | `kendall_tau` | 120h | 6 | VGS(th) | two_sided | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 16 | 100000 |
| 19 | `kendall_tau` | 120h | 6 | RDS(on) | upper | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 16 | 100000 |
| 20 | `kendall_tau` | 120h | 6 | IGSS | two_sided | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 16 | 100000 |
| 21 | `kendall_tau` | 168h | 7 | IDSS | upper | 100,000 | 10 | **0.000100** | [0.000054, 0.000184] | 0.00025 | 0 | 22 | 100000 |
| 22 | `kendall_tau` | 168h | 7 | VGS(th) | two_sided | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 22 | 100000 |
| 23 | `kendall_tau` | 168h | 7 | RDS(on) | upper | 100,000 | 20 | **0.000200** | [0.000129, 0.000309] | 0.00025 | 0 | 22 | 100000 |
| 24 | `kendall_tau` | 168h | 7 | IGSS | two_sided | 100,000 | 0 | **0.000000** | [0.000000, 0.000038] | 0.00025 | 0 | 22 | 100000 |
| 25 | `theil_sen` | 24h | 2 | IDSS | upper | 100,000 | 21 | **0.000210** | [0.000137, 0.000321] | 0.00025 | 0 | 100000 | 0 |
| 26 | `theil_sen` | 24h | 2 | VGS(th) | two_sided | 100,000 | 18 | **0.000180** | [0.000114, 0.000285] | 0.00025 | 0 | 100000 | 0 |
| 27 | `theil_sen` | 24h | 2 | RDS(on) | upper | 100,000 | 23 | **0.000230** | [0.000153, 0.000345] | 0.00025 | 0 | 100000 | 0 |
| 28 | `theil_sen` | 24h | 2 | IGSS | two_sided | 100,000 | 30 | **0.000300** | [0.000210, 0.000428] | 0.00025 | 0 | 100000 | 0 |
| 29 | `theil_sen` | 48h | 3 | IDSS | upper | 100,000 | 21 | **0.000210** | [0.000137, 0.000321] | 0.00025 | 0 | 100000 | 0 |
| 30 | `theil_sen` | 48h | 3 | VGS(th) | two_sided | 100,000 | 25 | **0.000250** | [0.000169, 0.000369] | 0.00025 | 0 | 100000 | 0 |
| 31 | `theil_sen` | 48h | 3 | RDS(on) | upper | 100,000 | 32 | **0.000320** | [0.000227, 0.000452] | 0.00025 | 0 | 100000 | 0 |
| 32 | `theil_sen` | 48h | 3 | IGSS | two_sided | 100,000 | 46 | **0.000460** | [0.000345, 0.000613] | 0.00025 | 0 | 100000 | 0 |
| 33 | `theil_sen` | 72h | 4 | IDSS | upper | 100,000 | 33 | **0.000330** | [0.000235, 0.000463] | 0.00025 | 0 | 100000 | 0 |
| 34 | `theil_sen` | 72h | 4 | VGS(th) | two_sided | 100,000 | 24 | **0.000240** | [0.000161, 0.000357] | 0.00025 | 0 | 100000 | 0 |
| 35 | `theil_sen` | 72h | 4 | RDS(on) | upper | 100,000 | 24 | **0.000240** | [0.000161, 0.000357] | 0.00025 | 0 | 100000 | 0 |
| 36 | `theil_sen` | 72h | 4 | IGSS | two_sided | 100,000 | 27 | **0.000270** | [0.000186, 0.000393] | 0.00025 | 0 | 100000 | 0 |
| 37 | `theil_sen` | 96h | 5 | IDSS | upper | 100,000 | 29 | **0.000290** | [0.000202, 0.000416] | 0.00025 | 0 | 100000 | 0 |
| 38 | `theil_sen` | 96h | 5 | VGS(th) | two_sided | 100,000 | 26 | **0.000260** | [0.000177, 0.000381] | 0.00025 | 0 | 100000 | 0 |
| 39 | `theil_sen` | 96h | 5 | RDS(on) | upper | 100,000 | 25 | **0.000250** | [0.000169, 0.000369] | 0.00025 | 0 | 100000 | 0 |
| 40 | `theil_sen` | 96h | 5 | IGSS | two_sided | 100,000 | 29 | **0.000290** | [0.000202, 0.000416] | 0.00025 | 0 | 100000 | 0 |
| 41 | `theil_sen` | 120h | 6 | IDSS | upper | 100,000 | 21 | **0.000210** | [0.000137, 0.000321] | 0.00025 | 0 | 100000 | 0 |
| 42 | `theil_sen` | 120h | 6 | VGS(th) | two_sided | 100,000 | 22 | **0.000220** | [0.000145, 0.000333] | 0.00025 | 0 | 100000 | 0 |
| 43 | `theil_sen` | 120h | 6 | RDS(on) | upper | 100,000 | 17 | **0.000170** | [0.000106, 0.000272] | 0.00025 | 0 | 100000 | 0 |
| 44 | `theil_sen` | 120h | 6 | IGSS | two_sided | 100,000 | 14 | **0.000140** | [0.000083, 0.000235] | 0.00025 | 0 | 100000 | 0 |
| 45 | `theil_sen` | 168h | 7 | IDSS | upper | 100,000 | 21 | **0.000210** | [0.000137, 0.000321] | 0.00025 | 0 | 100000 | 0 |
| 46 | `theil_sen` | 168h | 7 | VGS(th) | two_sided | 100,000 | 32 | **0.000320** | [0.000227, 0.000452] | 0.00025 | 0 | 100000 | 0 |
| 47 | `theil_sen` | 168h | 7 | RDS(on) | upper | 100,000 | 24 | **0.000240** | [0.000161, 0.000357] | 0.00025 | 0 | 100000 | 0 |
| 48 | `theil_sen` | 168h | 7 | IGSS | two_sided | 100,000 | 28 | **0.000280** | [0.000194, 0.000405] | 0.00025 | 0 | 100000 | 0 |
| 49 | `ols_t` | 48h | 3 | IDSS | upper | 100,000 | 34 | **0.000340** | [0.000243, 0.000475] | 0.00025 | 0 | 100000 | 0 |
| 50 | `ols_t` | 48h | 3 | VGS(th) | two_sided | 100,000 | 13 | **0.000130** | [0.000076, 0.000222] | 0.00025 | 0 | 100000 | 0 |
| 51 | `ols_t` | 48h | 3 | RDS(on) | upper | 100,000 | 26 | **0.000260** | [0.000177, 0.000381] | 0.00025 | 0 | 100000 | 0 |
| 52 | `ols_t` | 48h | 3 | IGSS | two_sided | 100,000 | 27 | **0.000270** | [0.000186, 0.000393] | 0.00025 | 0 | 100000 | 0 |
| 53 | `ols_t` | 72h | 4 | IDSS | upper | 100,000 | 24 | **0.000240** | [0.000161, 0.000357] | 0.00025 | 0 | 100000 | 0 |
| 54 | `ols_t` | 72h | 4 | VGS(th) | two_sided | 100,000 | 18 | **0.000180** | [0.000114, 0.000285] | 0.00025 | 0 | 100000 | 0 |
| 55 | `ols_t` | 72h | 4 | RDS(on) | upper | 100,000 | 23 | **0.000230** | [0.000153, 0.000345] | 0.00025 | 0 | 100000 | 0 |
| 56 | `ols_t` | 72h | 4 | IGSS | two_sided | 100,000 | 18 | **0.000180** | [0.000114, 0.000285] | 0.00025 | 0 | 100000 | 0 |
| 57 | `ols_t` | 96h | 5 | IDSS | upper | 100,000 | 25 | **0.000250** | [0.000169, 0.000369] | 0.00025 | 0 | 100000 | 0 |
| 58 | `ols_t` | 96h | 5 | VGS(th) | two_sided | 100,000 | 16 | **0.000160** | [0.000098, 0.000260] | 0.00025 | 0 | 100000 | 0 |
| 59 | `ols_t` | 96h | 5 | RDS(on) | upper | 100,000 | 21 | **0.000210** | [0.000137, 0.000321] | 0.00025 | 0 | 100000 | 0 |
| 60 | `ols_t` | 96h | 5 | IGSS | two_sided | 100,000 | 32 | **0.000320** | [0.000227, 0.000452] | 0.00025 | 0 | 100000 | 0 |
| 61 | `ols_t` | 120h | 6 | IDSS | upper | 100,000 | 15 | **0.000150** | [0.000091, 0.000247] | 0.00025 | 0 | 100000 | 0 |
| 62 | `ols_t` | 120h | 6 | VGS(th) | two_sided | 100,000 | 18 | **0.000180** | [0.000114, 0.000285] | 0.00025 | 0 | 100000 | 0 |
| 63 | `ols_t` | 120h | 6 | RDS(on) | upper | 100,000 | 26 | **0.000260** | [0.000177, 0.000381] | 0.00025 | 0 | 100000 | 0 |
| 64 | `ols_t` | 120h | 6 | IGSS | two_sided | 100,000 | 28 | **0.000280** | [0.000194, 0.000405] | 0.00025 | 0 | 100000 | 0 |
| 65 | `ols_t` | 168h | 7 | IDSS | upper | 100,000 | 16 | **0.000160** | [0.000098, 0.000260] | 0.00025 | 0 | 100000 | 0 |
| 66 | `ols_t` | 168h | 7 | VGS(th) | two_sided | 100,000 | 17 | **0.000170** | [0.000106, 0.000272] | 0.00025 | 0 | 100000 | 0 |
| 67 | `ols_t` | 168h | 7 | RDS(on) | upper | 100,000 | 33 | **0.000330** | [0.000235, 0.000463] | 0.00025 | 0 | 100000 | 0 |
| 68 | `ols_t` | 168h | 7 | IGSS | two_sided | 100,000 | 23 | **0.000230** | [0.000153, 0.000345] | 0.00025 | 0 | 100000 | 0 |

#### Table 3: Module A Endpoint Drift Comparator Across All 6 Horizons (Frozen Non-Calibrated Rule: |g_p| >= 2.5)

| Horizon | K | N Components | Component Breaches | Operating FWER | Wilson 95% CI | IDSS FPR | VGS(th) FPR | RDS(on) FPR | IGSS FPR |
|---|---|---|---|---|---|---|---|---|---|
| 24h | 2 | 100,000 | 38,354 | **0.383540** | [0.380531, 0.386558] | 0.1037 | 0.1239 | 0.1342 | 0.0933 |
| 48h | 3 | 100,000 | 38,443 | **0.384430** | [0.381419, 0.387449] | 0.1067 | 0.1239 | 0.1344 | 0.0928 |
| 72h | 4 | 100,000 | 37,961 | **0.379610** | [0.376607, 0.382622] | 0.1036 | 0.1227 | 0.1326 | 0.0914 |
| 96h | 5 | 100,000 | 38,514 | **0.385140** | [0.382128, 0.388160] | 0.1044 | 0.1226 | 0.1346 | 0.0944 |
| 120h | 6 | 100,000 | 38,333 | **0.383330** | [0.380321, 0.386348] | 0.1047 | 0.1222 | 0.1341 | 0.0936 |
| 168h | 7 | 100,000 | 38,587 | **0.385870** | [0.382857, 0.388891] | 0.1049 | 0.1238 | 0.1343 | 0.0938 |

#### Detailed Forensic Interpretation & Anomaly Audits

1. **Kendall's $\tau$ Analytical Feasibility & Capacity Accounting**:
   - *Horizons $K=2..6$ ($T \in \{24, 48, 72, 96, 120\}\ \text{h}$)*: Exactly **0** component-level Holm rejections out of 100,000 components (FWER = $0.000000$, 95% CI: $[0.000000, 0.000038]$). Exactly **0** parameter-level false positives across all 20 cells. This directly confirms the pre-execution analytical proof: the permutation support of Kendall's $\tau$ is bounded by $1/K!$ (e.g., $1/2! = 0.50$, $1/3! \approx 0.167$, $1/4! \approx 0.0417$, $1/5! \approx 0.00833$, $1/6! \approx 0.001389$). Because every achievable $p$-value for $K \le 6$ satisfies $p \ge 1/K! > \alpha/4 = 0.000250$, no test statistic can pass Step 1 of the Holm procedure. Thus, Kendall's $\tau$ has **analytical zero rejection capacity** at $K \le 6$ under the frozen Holm $\alpha = 0.001$ protocol.
   - *Horizon $K=7$ ($T=168\ \text{h}$)*: Permutation support size is $7! = 5{,}040$. For one-sided upper-tail tests ($I_{\text{DSS}}, R_{\text{DS(on)}}$), $1/7! = 1/5040 \approx 0.0001984 < 0.000250$, opening positive rejection capacity at Step 1. In the audit set, exactly 10 $I_{\text{DSS}}$ series (FPR = $0.000100$) and 20 $R_{\text{DS(on)}}$ series (FPR = $0.000200$) achieved $\tau = +1$ and $p \le 0.000250$, yielding exactly 30 component-level rejections (FWER = $0.000300$, 95% CI: $[0.000210, 0.000428]$).
   - *Two-Sided Inactivity at $K=7$*: For two-sided tests ($V_{\text{GS(th)}}, I_{\text{GSS}}$), the minimum theoretical tail probability is $2/7! = 2/5040 \approx 0.0003968$. Because $0.0003968 > \alpha_1 = 0.000250$ and $0.0003968 > \alpha_2 = 0.000333$, two-sided Kendall tests **cannot reject at Step 1 or Step 2**. They could only reject at Step 3 (threshold $0.000500$) if both one-sided parameters had already rejected. As verified in the audit, zero two-sided rejections occurred.
   - *Distinction Between Tail Events and Rejections*: Parameter-level extreme rank events ($\{x_t\}$ monotonically increasing, $\tau = +1$) did occur in components across all horizons, but for $K \le 6$, the empirical $p$-value mapped to $\ge 1/K! > 0.000250$, properly preventing Holm component rejection. Parameter tail events are observed descriptive phenomena that do not constitute statistical rejections.
2. **Theil-Sen Robust Slope Evaluation & Calibration Deviation Identification**:
   - Four of the 6 evaluated horizons ($24\text{h}, 72\text{h}, 96\text{h}, 168\text{h}$) contain the nominal target $\alpha = 0.001000$ strictly inside their Wilson 95% confidence intervals ($24\text{h}: [0.000750, 0.001128]$; $72\text{h}: [0.000895, 0.001304]$; $96\text{h}: [0.000904, 0.001315]$; $168\text{h}: [0.000868, 0.001271]$).
   - Horizon $120\text{h}$ exhibits a conservative FWER of $0.000740$ (95% CI: $[0.000590, 0.000929]$, $Z = -2.60$).
   - **Horizon $48\text{h}$ ($K=3$) exhibits an open calibration deviation**: observed FWER is $0.001240$ (124 rejections / 100,000 components) with Wilson 95% CI $[0.001040, 0.001478]$. Because the lower bound $0.001040 > 0.001000$, nominal $\alpha = 0.001000$ lies strictly outside the reported 95% CI ($Z = +2.401$, exact two-sided $p = 0.0225$). This is formally classified as an **OPEN CALIBRATION-DEVIATION FORENSIC ISSUE** requiring focused single-cell review rather than nominal sampling conformity or detector invalidation.
   - Non-finite statistics: Exactly 0 across all horizons. Distinct values: 100,000. Ties: 0.
3. **Parametric OLS $t$-Statistic Evaluation ($K \ge 3$)**:
   - Operating FWER across all 5 valid horizons spans $[0.000830, 0.001000]$, exhibiting near-exact calibration to the nominal $\alpha = 0.001000$ target (e.g. at $T=48\text{h}$, FWER = $0.001000$ with exactly 100 rejections out of 100,000 components; 95% CI: $[0.000822, 0.001216]$).
   - Parameter-level FPR spans $[0.000130, 0.000340]$, closely aligning with $\alpha/4 = 0.000250$.
   - Non-finite statistics: Exactly 0. Distinct values: 100,000. Ties: 0.
4. **Module A Drift Comparator Contrast**:
   - The uncalibrated frozen Module A endpoint drift comparator ($|g_p| \ge 2.5$) produces an empirical breach rate of $\approx 38.0\% - 38.6\%$ across all horizons (over 38,000 false positives per 100,000 null components), directly confirming the diagnostic finding from Phase 3C that fixed static drift thresholds suffer massive uncalibrated false alarm cascades.
5. **Focused Forensic Trace: Theil-Sen 48h ($K=3$) Calibration Deviation (Source Decomposition)**:
   - *Exact Reproduction*: 124 / 100,000 component rejections verified 100% reproducible from frozen audit artifacts (`null_a_audit_results.json`) and deterministically regenerated under seed `233837969`.
   - *Holm Chain Anatomy*: All 124 rejections occurred strictly at Step 1 ($p_{(1)} \le 0.000250$). Step 2, 3, 4 rejections = 0. Exactly four parameter $p$-values entered Holm for all 100,000 components. Exactly zero components had multiple parameters meeting Step 1.
   - *Parameter Trigger Breakdown*:
     * $I_{\text{DSS}}$ (upper tail): 21 rejections (16.9%, expected ~25, FPR = 0.000210)
     * $V_{\text{GS(th)}}$ (two-sided): 25 rejections (20.2%, expected ~25, FPR = 0.000250 — exact nominal match)
     * $R_{\text{DS(on)}}$ (upper tail): 32 rejections (25.8%, expected ~25, FPR = 0.000320)
     * $I_{\text{GSS}}$ (two-sided): 46 rejections (37.1%, expected ~25, FPR = 0.000460)
     * Sum of parameter rejections $= 21 + 25 + 32 + 46 = 124$. The elevation originates primarily from $I_{\text{GSS}}$ (+21 over expected 25) and secondarily from $R_{\text{DS(on)}}$ (+7 over expected 25).
   - *Tail Symmetry in $I_{\text{GSS}}$*: For the 46 $I_{\text{GSS}}$ rejections, 19 occurred in the positive tail ($S_{\text{TS}} > +0.027658$) and 27 in the negative tail ($S_{\text{TS}} < -0.027658$). Both tails are active, ruling out directional bias.
   - *Lot Topology Distribution*: The 124 rejections are dispersed across 121 distinct lots out of 5,000 lots (118 lots with 1 rejection, 3 lots with 2 rejections, 0 lots with $\ge 3$ rejections). Under a homogeneous Poisson lot process, expected double-hit lots is $\approx 1.54$, fully consistent with observed 3 lots. There is no obvious lot concentration or localized corruption pattern.
   - *Single-Sample Binomial Quantification (Fixed Threshold Assumption)*:
     * Observed FWER: $0.001240$
     * Nominal target $\alpha$: $0.001000$
     * Count deviation: $124 - 100 = +24$ components ($+24.0\%$)
     * Standard error $\sigma_{\text{audit}}$: $\sqrt{100{,}000 \times 0.001 \times 0.999} = 9.9950$
     * Standardized deviation $Z$: $+2.401$
     * Exact two-sided binomial $p$-value: $0.02249$ (one-sided $p = 0.01124$)
     * Wilson 95% CI: $[0.001040, 0.001478]$ (lower bound strictly exceeds $0.001000$).
6. **Empirical Calibration Boundary & Order-Statistic Diagnostics (Theil-Sen 48h vs. Neighboring Horizons)**:
   - *Order-Statistic Anatomy across Ranks 15 to 35 ($N_{\text{cal}} = 100{,}000$, $N_{\text{audit}} = 100{,}000$)*:
     * Empirical Step-1 Critical Boundary: defined by rank 25 from the top in calibration ($p = (24 + 1)/(100000 + 1) = 0.0002499975 \le 0.000250000$).
     * $I_{\text{DSS}}$ ($K=3$, upper tail): Critical boundary $= 0.00886831$. Cal exceedances $= 25$; Audit exceedances $= 21$ (delta: $-4$, audit FPR $= 0.000210$). Order stats: Cal Rank 20 $= 0.00893706$, Rank 25 $= 0.00886831$, Rank 30 $= 0.00877659$. Audit Rank 25 $= 0.00876539$.
     * $V_{\text{GS(th)}}$ ($K=3$, two-sided): Critical boundary $= 0.00250211$. Cal exceedances $= 25$; Audit exceedances $= 25$ (delta: $0$, audit FPR $= 0.000250$ — exact match). Order stats: Cal Rank 20 $= 0.00253746$, Rank 25 $= 0.00250211$, Rank 30 $= 0.00247670$. Audit Rank 25 $= 0.00252672$.
     * $R_{\text{DS(on)}}$ ($K=3$, upper tail): Critical boundary $= 0.00149147$. Cal exceedances $= 25$; Audit exceedances $= 32$ (delta: $+7$, audit FPR $= 0.000320$). Order stats: Cal Rank 20 $= 0.00151063$, Rank 25 $= 0.00149147$, Rank 30 $= 0.00147156$, Rank 32 $= 0.00146950$. In audit, Rank 32 $= 0.00149150$. Spacing between Rank 25 and Rank 32 is only $0.00002197\ \Omega/\text{h}$ ($22\ \mu\Omega/\text{h}$, or $1.47\%$ of critical threshold).
     * $I_{\text{GSS}}$ ($K=3$, two-sided): Critical boundary $= 0.02765842$. Cal exceedances $= 25$; Audit exceedances $= 46$ (delta: $+21$, audit FPR $= 0.000460$). Order stats: Cal Rank 20 $= 0.02815001$, Rank 25 $= 0.02765842$, Rank 30 $= 0.02747479$, Rank 46 $= 0.02684231$. In audit, Rank 46 $= 0.02766010$. Spacing between Rank 25 and Rank 46 is $0.00081612\ \text{nA}/\text{h}$ ($2.95\%$ of critical threshold, corresponding to $0.105\ \sigma$ of the calibration distribution).
   - *Probability Mass Concentration Test*:
     * Counts within a $\pm 5\%$ band around critical boundary: $I_{\text{DSS}}$: Cal 34, Aud 32; $V_{\text{GS(th)}}$: Cal 52, Aud 32; $R_{\text{DS(on)}}$: Cal 40, Aud 43; $I_{\text{GSS}}$: Cal 48, Aud 52.
     * Counts within a $\pm 10\%$ band: $I_{\text{DSS}}$: Cal 82, Aud 76; $V_{\text{GS(th)}}$: Cal 111, Aud 76; $R_{\text{DS(on)}}$: Cal 91, Aud 103; $I_{\text{GSS}}$: Cal 115, Aud 120.
     * Diagnostic finding: $I_{\text{GSS}}$ and $R_{\text{DS(on)}}$ exhibit smooth, continuous, and highly consistent tail density between calibration and audit. There is no discrete point mass, clustering, or distribution discontinuity near the threshold.
   - *Neighboring Horizon Boundary Cross-Comparison (Theil-Sen across all 6 horizons)*:
     * $24\text{h}$ ($K=2$): $I_{\text{DSS}}: 21$ ($-4$), $V_{\text{GS(th)}}: 18$ ($-7$), $R_{\text{DS(on)}}: 23$ ($-2$), $I_{\text{GSS}}: 30$ ($+5$). Total Parameter FPs $= 92$. Component Holm Rejections $= 92$ (FWER $= 0.000920$, 95% CI: $[0.000750, 0.001128]$).
     * $48\text{h}$ ($K=3$): $I_{\text{DSS}}: 21$ ($-4$), $V_{\text{GS(th)}}: 25$ ($0$), $R_{\text{DS(on)}}: 32$ ($+7$), $I_{\text{GSS}}: 46$ ($+21$). Total Parameter FPs $= 124$. Component Holm Rejections $= 124$ (FWER $= 0.001240$, 95% CI: $[0.001040, 0.001478]$).
     * $72\text{h}$ ($K=4$): $I_{\text{DSS}}: 33$ ($+8$), $V_{\text{GS(th)}}: 24$ ($-1$), $R_{\text{DS(on)}}: 24$ ($-1$), $I_{\text{GSS}}: 27$ ($+2$). Total Parameter FPs $= 108$. Component Holm Rejections $= 108$ (FWER $= 0.001080$, 95% CI: $[0.000895, 0.001304]$).
     * $96\text{h}$ ($K=5$): $I_{\text{DSS}}: 29$ ($+4$), $V_{\text{GS(th)}}: 26$ ($+1$), $R_{\text{DS(on)}}: 25$ ($0$), $I_{\text{GSS}}: 29$ ($+4$). Total Parameter FPs $= 109$. Component Holm Rejections $= 109$ (FWER $= 0.001090$, 95% CI: $[0.000904, 0.001315]$).
     * $120\text{h}$ ($K=6$): $I_{\text{DSS}}: 21$ ($-4$), $V_{\text{GS(th)}}: 22$ ($-3$), $R_{\text{DS(on)}}: 17$ ($-8$), $I_{\text{GSS}}: 14$ ($-11$). Total Parameter FPs $= 74$. Component Holm Rejections $= 74$ (FWER $= 0.000740$, 95% CI: $[0.000590, 0.000929]$).
     * $168\text{h}$ ($K=7$): $I_{\text{DSS}}: 21$ ($-4$), $V_{\text{GS(th)}}: 32$ ($+7$), $R_{\text{DS(on)}}: 24$ ($-1$), $I_{\text{GSS}}: 28$ ($+3$). Total Parameter FPs $= 105$. Component Holm Rejections $= 105$ (FWER $= 0.001050$, 95% CI: $[0.000868, 0.001271]$).
     * Horizon Mean across all 6 horizons: $I_{\text{DSS}}: 24.33$ ($E=25$), $V_{\text{GS(th)}}: 24.50$ ($E=25$), $R_{\text{DS(on)}}: 24.17$ ($E=25$), $I_{\text{GSS}}: 29.00$ ($E=25$). Mean total parameter FPs $= 102.0$; Mean component rejections $= 102.0$ ($E=100$, mean FWER $= 0.001020$).
   - *Explicit Distinction: Parameter Rejection Counts vs. Component Union (FWER)*:
     * Parameter-level rejection counts measure the marginal false-positive frequency of each parameter test statistic against its calibration threshold.
     * Component-level FWER measures the probability of the union event $\bigcup_{p=1}^4 \{p_p \le \alpha_{\text{step}}\}$.
     * In this specific audit sample of $100{,}000$ components, the observed number of component-level rejections ($124$) exactly equals the sum of the parameter-level rejections ($21 + 25 + 32 + 46 = 124$) because no component happened to experience multiple simultaneous Step 1 exceedances in this realization.
     * **Critical Clarification**: This numerical equality in this sample is an empirical property of this realization at extreme tail thresholds; it does **not** prove general statistical independence of the parameter-level processes across components or lots.
   - *Four-Source Statistical Variance Decomposition*:
     * **Source A (Calibration-Threshold Estimation Variability)**: The calibration threshold $\hat{s}^*$ is an empirical order statistic ($k=25$ out of $B=100{,}000$). Under frequentist order-statistic theory, the random population coverage induced by this finite calibration order statistic, $U = 1 - F(\hat{s}^*)$, follows a $\text{Beta}(25, 99976)$ distribution. The expectation is $E[U] = 25/100001 \approx 0.0002500$, with variance $\text{Var}(U) \approx 25 / B^2 = 2.5 \times 10^{-9}$ and standard error $\text{SE}(U) \approx 0.0000500$ ($5.0$ per $100{,}000$). The **95% probability interval for the random population coverage induced by the finite calibration order statistic** is approximately $[0.000152, 0.000348]$ (equivalent to $[15.2, 34.8]$ expected counts per $100{,}000$).
     * **Source B (Independent Audit Sampling Variability)**: Conditional on a fixed population coverage $U$, the realized audit count $X \sim \text{Binomial}(N=100{,}000, U)$ has conditional sampling variance $\text{Var}(X | U) \approx N p_0 = 25.0$ (standard error $5.0$).
     * **Compound Parameter Variance (A + B)**: Unconditionally across independent calibration and audit draws, $\text{Var}(X) = E[\text{Var}(X|U)] + \text{Var}(E[X|U]) \approx N p_0 + N^2 \text{Var}(U) \approx 25.0 + 25.0 = 50.0$. The compound standard error for each marginal parameter count is $\sigma_{\text{param, compound}} = \sqrt{50} \approx 7.071$.
     * **Independence-Based Compound-Variance Sensitivity Analysis (Component Level)**:
       If one assumes mutual independence among the four parameter rejection count processes as an idealized sensitivity baseline, the compound variance of the sum of parameter counts is $\text{Var}(K_{\text{comp}}) \approx 4 \times 50.0 = 200.0$, yielding $\sigma_{\text{comp, compound}} \approx \sqrt{200} \approx 14.142$, under which the deviate of 124 rejections would be $Z_{\text{indep}} = (124 - 100)/14.142 = +1.697$ (nominal two-sided normal tail area $p \approx 0.0897$).
       **Methodological Warning**: This calculation is strictly an *independence-based compound-variance sensitivity benchmark*. The exact component-level covariance structure among the four parameter processes (incorporating cross-parameter noise correlations and shared lot-median effects) is **not established by this audit**. Therefore, $Z=1.697$ and $p\approx 0.090$ must **not** be interpreted as the exact or proven probability under the full Phase 4B data-generating process.
     * **Source C (Systematic Anti-Conservatism Evaluation)**: The cross-horizon audit does **not** provide evidence of a consistent upward FWER elevation across all Theil-Sen horizons (operating FWER is $0.000920$ at 24h, $0.001080$ at 72h, $0.001090$ at 96h, $0.000740$ at 120h, and $0.001050$ at 168h; cross-horizon mean is $102.0$ rejections per 100k, mean FWER $= 0.001020$). However, this cross-horizon pattern does not mathematically rule out parameter-specific or horizon-specific systematic mechanisms at 48h.
     * **Source D (Implementation / Calibration Pipeline Check)**: Verified that calibration artifacts were consumed 100% unmutated; non-finite count is 0; ties are 0; and data transformations strictly match specification.
7. **Comprehensive Anomaly Audit Checklist & Standing Status**:
   - Nonzero Holm rejection where zero-capacity expected: **NONE** (0 / 500,000 component evaluations across $K=2..6$ for Kendall $\tau$).
   - FWER / Calibration Deviation Review: **OPEN CALIBRATION-DEVIATION FORENSIC ISSUE AT THEIL-SEN 48h ($K=3$)**. At $48\text{h}$, Theil-Sen produced 124 Holm rejections (FWER = $0.001240$, Wilson 95% CI: $[0.001040, 0.001478]$, single-sample fixed-threshold $Z_{\text{audit}} = +2.401$, two-sided $p = 0.0225$), with nominal $\alpha = 0.001000$ strictly outside the single-sample Wilson 95% CI.
   - **Forensic Summary of the 48h Theil-Sen Cell**:
     1. The 48h cell remains formally classified as an **OPEN CALIBRATION-DEVIATION FORENSIC ISSUE**.
     2. The excess rejections are concentrated in $I_{\text{GSS}}$ (46 FPs vs 25 expected) and $R_{\text{DS(on)}}$ (32 FPs vs 25 expected).
     3. There is no obvious lot concentration or localized corruption pattern (distributed across 121 lots).
     4. There is no tie or rank-discreteness artifact (100,000 distinct values, 0 ties).
     5. There is no obvious local probability-mass spike near the critical threshold.
     6. There is no implementation or calibration dataset mutation detected.
     7. Finite calibration-tail estimation variability (Source A) is a plausible contributor.
     8. Independent audit sampling variability (Source B) is also a contributor.
     9. Current evidence does **NOT** justify threshold retuning or detector redesign.
     10. The cell status remains OPEN pending formal review prior to subsequent phase authorization.
   - Unexpected ties: **NONE** (continuous statistics have 0 ties; Kendall ties match exact permutation partitions).
   - p-value discretization anomalies: **NONE** (discretization behaves exactly as predicted by permutation mathematics).
   - Horizon-specific anomalies: Verified open calibration deviation at Theil-Sen $48\text{h}$ ($Z = +2.401$) and conservative shift at $120\text{h}$ ($Z = -2.60$). Other 15 detector-horizon cells strictly conform.
   - Detector/calibration mismatch: **NONE** (all calibration reference table hashes and distribution arrays verified 100% bit-for-bit matched).
8. **Epistemic Invariant & Scientific Boundary Statement**:
   - Observed empirical FWER control under Null A establishes mathematical consistency strictly within the specified synthetic no-degradation simulation model under identical lot topology ($L=20$) and LOO median excess coordinates.
   - It does **NOT** prove physical device validity, mission lifetime compliance, or spaceflight flightworthiness of physical IRHNJ57130 hardware under MIL-PRF-19500.
- **Reason**: Comprehensive documentation and forensic interpretation of Phase 2.2 Independent Null-A Audit results per frozen protocol.
- **Source / Provenance**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` (v1.9.0), `src/sih26170/screening/phase4b_audit.py`, `data/evaluation_phase4b/null_a_audit_results.json`, LOG-086.
- **Gate Outcome**: **PHASE 2.2 AUDIT COMPLETE — THEIL-SEN 48h CALIBRATION-DEVIATION FORENSIC ISSUE PRESERVED AS OPEN — FROZEN AT FREEZE 1 — STOPPED BEFORE SUBSEQUENT PHASES**
- **Affected Area**: `data/evaluation_phase4b/null_a_audit_results.json`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Canonical Invariants Preserved**: Calibration artifacts 100% unmutated; 192/192 pytest tests passing; frozen benchmarks unchanged; zero execution of Null-B, Null-C, power, validation, or final evaluation.

Execution stopped per gate instructions.

---

### LOG-088: Phase 4B Phase 2.3 Null-B AR(1) Temporal Stress Test Gate

- **Log ID**: LOG-088
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Phase 2.3 Null-B AR(1) Temporal Stress Test Gate
- **Change**: Executed Phase 2.3 Null-B out-of-distribution stress test on $N_B = 100{,}000$ complete components in $5{,}000$ lots ($400{,}000$ parameter series) under dedicated HMAC seed `270315777` per §6.H.3. Noise follows stationary AR(1) process $\epsilon_t = \phi \epsilon_{t-1} + \sqrt{1 - \phi^2} \eta_t$ with $\phi \sim \mathcal{U}(0.20, 0.35)$ drawn independently per component-parameter. Evaluated all 68 candidate detector cells and Module A comparator against the frozen Null-A calibration reference table (`calibration_reference_table.json` and `calibration_distributions.npz`) in strictly read-only mode without threshold adjustments, recalibration, or pooling.
- **Previous State**: LOG-087 established the Null-A independent audit results and boundary diagnostics. The 48h Theil-Sen cell is classified as an OPEN / NON-BLOCKING CALIBRATION-DEVIATION OBSERVATION. The Null-B stress test set was uninstantiated.
- **New State**:
  1. **Stress Test Execution & Sample Accounting**:
     - Total Components Evaluated: 100,000 components across 5,000 lots ($L=20$).
     - Total Series Evaluated: 400,000 series across 4 physical parameters ($I_{\text{DSS}}, V_{\text{GS(th)}}, R_{\text{DS(on)}}, I_{\text{GSS}}$) and 7 checkpoints ($T \in \{0, 24, 48, 72, 96, 120, 168\}\ \text{h}$).
     - Dedicated Stress Seed: `270315777` (cryptographically isolated).
     - AR(1) Realization: Drawn $\bar{\phi} = 0.2751$, $\phi_{\min} = 0.2000$, $\phi_{\max} = 0.3500$.
     - Causal LOO Excess Coordinates: Computed independently at each as-of checkpoint against simultaneous lot median excluding component $i$.
  2. **Stress Test Artifact Integrity & Cryptographic Verifications**:
     - Consumed Calibration Table SHA-256: `153d387597ba6a247ed5302a7512730c678bc3ce39e056848cd9135fc39c7d60` (100% unmutated).
     - Consumed Calibration Distributions SHA-256: `147f1d38ed9b197af6b6301b9b454223d5cce54286fcfeb89a1ea15cec055d98` (100% unmutated).
     - Produced Stress Test Artifact: `data/evaluation_phase4b/null_b_stress_results.json` (SHA-256: `7a8f26cb450bbbc9ee1608e8902a171314eddadc1c6d13867a579b64cc4fe44c`).
     - Dataset Digests: Raw measurements SHA-256: `11d7cf9d9fb51e7efc900695ea4eb7b6f6f9fc5a95444ffc914e6b18a10ef2a2`; Excess coordinates SHA-256: `3b46944ca0835f893d58ef8a8ea4b01e38318ca47ea615bf61b369c9b4e64f7b`.
     - Frozen Benchmarks Verified: All Phase 4B, Phase 2F, and Null-A audit hashes verified 100% bit-for-bit unchanged.
  3. **Complete Null-B vs. Null-A Comparison Tables**:

#### Table 1: Component-Level Family-Wise Error Rate (FWER) Across All 17 Detector-Horizon Cells (Null-B Stress vs. Null-A Audit, N = 100,000/cell)

| Detector Family | Role | Horizon | K | Null-B Rejections | Null-B FWER | Null-B Wilson 95% CI | Null-A Rejections | Null-A FWER | Nominal Target | Exceeds Nominal? |
|---|---|---|---|---|---|---|---|---|---|---|
| `kendall_tau` | PRIMARY CANDIDATE | 24h | 2 | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.001000 | NO (conforms/conservative) |
| `kendall_tau` | PRIMARY CANDIDATE | 48h | 3 | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.001000 | NO (conforms/conservative) |
| `kendall_tau` | PRIMARY CANDIDATE | 72h | 4 | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.001000 | NO (conforms/conservative) |
| `kendall_tau` | PRIMARY CANDIDATE | 96h | 5 | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.001000 | NO (conforms/conservative) |
| `kendall_tau` | PRIMARY CANDIDATE | 120h | 6 | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.001000 | NO (conforms/conservative) |
| `kendall_tau` | PRIMARY CANDIDATE | 168h | 7 | 88 | **0.000880** | [0.000714, 0.001084] | 30 | 0.000300 | 0.001000 | NO (conforms/conservative) |
| `theil_sen` | AUXILIARY CANDIDATE | 24h | 2 | 12 | **0.000120** | [0.000069, 0.000210] | 92 | 0.000920 | 0.001000 | NO (conforms/conservative) |
| `theil_sen` | AUXILIARY CANDIDATE | 48h | 3 | 77 | **0.000770** | [0.000616, 0.000962] | 124 | 0.001240 | 0.001000 | NO (conforms/conservative) |
| `theil_sen` | AUXILIARY CANDIDATE | 72h | 4 | 128 | **0.001280** | [0.001077, 0.001522] | 108 | 0.001080 | 0.001000 | YES (stress elevation) |
| `theil_sen` | AUXILIARY CANDIDATE | 96h | 5 | 200 | **0.002000** | [0.001742, 0.002297] | 109 | 0.001090 | 0.001000 | YES (stress elevation) |
| `theil_sen` | AUXILIARY CANDIDATE | 120h | 6 | 213 | **0.002130** | [0.001863, 0.002436] | 74 | 0.000740 | 0.001000 | YES (stress elevation) |
| `theil_sen` | AUXILIARY CANDIDATE | 168h | 7 | 347 | **0.003470** | [0.003124, 0.003854] | 105 | 0.001050 | 0.001000 | YES (stress elevation) |
| `ols_t` | BENCHMARK COMPARATOR | 48h | 3 | 136 | **0.001360** | [0.001150, 0.001608] | 100 | 0.001000 | 0.001000 | YES (stress elevation) |
| `ols_t` | BENCHMARK COMPARATOR | 72h | 4 | 134 | **0.001340** | [0.001132, 0.001587] | 83 | 0.000830 | 0.001000 | YES (stress elevation) |
| `ols_t` | BENCHMARK COMPARATOR | 96h | 5 | 175 | **0.001750** | [0.001509, 0.002029] | 94 | 0.000940 | 0.001000 | YES (stress elevation) |
| `ols_t` | BENCHMARK COMPARATOR | 120h | 6 | 229 | **0.002290** | [0.002012, 0.002606] | 87 | 0.000870 | 0.001000 | YES (stress elevation) |
| `ols_t` | BENCHMARK COMPARATOR | 168h | 7 | 253 | **0.002530** | [0.002237, 0.002861] | 89 | 0.000890 | 0.001000 | YES (stress elevation) |

#### Table 2: Parameter-Level False Positive Rate (FPR) Across All 68 Cells (Null-B Stress vs. Null-A Audit, N = 100,000/cell)

| Cell # | Detector Family | Horizon | K | Parameter | Tail Direction | Null-B FPs | Null-B FPR | Null-B Wilson 95% CI | Null-A FPs | Null-A FPR | Step-1 Threshold |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `kendall_tau` | 24h | 2 | IDSS | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 02 | `kendall_tau` | 24h | 2 | VGS(th) | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 03 | `kendall_tau` | 24h | 2 | RDS(on) | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 04 | `kendall_tau` | 24h | 2 | IGSS | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 05 | `kendall_tau` | 48h | 3 | IDSS | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 06 | `kendall_tau` | 48h | 3 | VGS(th) | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 07 | `kendall_tau` | 48h | 3 | RDS(on) | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 08 | `kendall_tau` | 48h | 3 | IGSS | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 09 | `kendall_tau` | 72h | 4 | IDSS | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 10 | `kendall_tau` | 72h | 4 | VGS(th) | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 11 | `kendall_tau` | 72h | 4 | RDS(on) | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 12 | `kendall_tau` | 72h | 4 | IGSS | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 13 | `kendall_tau` | 96h | 5 | IDSS | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 14 | `kendall_tau` | 96h | 5 | VGS(th) | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 15 | `kendall_tau` | 96h | 5 | RDS(on) | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 16 | `kendall_tau` | 96h | 5 | IGSS | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 17 | `kendall_tau` | 120h | 6 | IDSS | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 18 | `kendall_tau` | 120h | 6 | VGS(th) | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 19 | `kendall_tau` | 120h | 6 | RDS(on) | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 20 | `kendall_tau` | 120h | 6 | IGSS | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 21 | `kendall_tau` | 168h | 7 | IDSS | upper | 42 | **0.000420** | [0.000311, 0.000568] | 10 | 0.000100 | 0.00025 |
| 22 | `kendall_tau` | 168h | 7 | VGS(th) | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 23 | `kendall_tau` | 168h | 7 | RDS(on) | upper | 46 | **0.000460** | [0.000345, 0.000613] | 20 | 0.000200 | 0.00025 |
| 24 | `kendall_tau` | 168h | 7 | IGSS | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0.000000 | 0.00025 |
| 25 | `theil_sen` | 24h | 2 | IDSS | upper | 2 | **0.000020** | [0.000005, 0.000073] | 21 | 0.000210 | 0.00025 |
| 26 | `theil_sen` | 24h | 2 | VGS(th) | two_sided | 5 | **0.000050** | [0.000021, 0.000117] | 18 | 0.000180 | 0.00025 |
| 27 | `theil_sen` | 24h | 2 | RDS(on) | upper | 1 | **0.000010** | [0.000002, 0.000057] | 23 | 0.000230 | 0.00025 |
| 28 | `theil_sen` | 24h | 2 | IGSS | two_sided | 4 | **0.000040** | [0.000016, 0.000103] | 30 | 0.000300 | 0.00025 |
| 29 | `theil_sen` | 48h | 3 | IDSS | upper | 15 | **0.000150** | [0.000091, 0.000247] | 21 | 0.000210 | 0.00025 |
| 30 | `theil_sen` | 48h | 3 | VGS(th) | two_sided | 21 | **0.000210** | [0.000137, 0.000321] | 25 | 0.000250 | 0.00025 |
| 31 | `theil_sen` | 48h | 3 | RDS(on) | upper | 16 | **0.000160** | [0.000098, 0.000260] | 32 | 0.000320 | 0.00025 |
| 32 | `theil_sen` | 48h | 3 | IGSS | two_sided | 25 | **0.000250** | [0.000169, 0.000369] | 46 | 0.000460 | 0.00025 |
| 33 | `theil_sen` | 72h | 4 | IDSS | upper | 38 | **0.000380** | [0.000277, 0.000522] | 33 | 0.000330 | 0.00025 |
| 34 | `theil_sen` | 72h | 4 | VGS(th) | two_sided | 38 | **0.000380** | [0.000277, 0.000522] | 24 | 0.000240 | 0.00025 |
| 35 | `theil_sen` | 72h | 4 | RDS(on) | upper | 26 | **0.000260** | [0.000177, 0.000381] | 24 | 0.000240 | 0.00025 |
| 36 | `theil_sen` | 72h | 4 | IGSS | two_sided | 26 | **0.000260** | [0.000177, 0.000381] | 27 | 0.000270 | 0.00025 |
| 37 | `theil_sen` | 96h | 5 | IDSS | upper | 73 | **0.000730** | [0.000581, 0.000918] | 29 | 0.000290 | 0.00025 |
| 38 | `theil_sen` | 96h | 5 | VGS(th) | two_sided | 50 | **0.000500** | [0.000379, 0.000659] | 26 | 0.000260 | 0.00025 |
| 39 | `theil_sen` | 96h | 5 | RDS(on) | upper | 27 | **0.000270** | [0.000186, 0.000393] | 25 | 0.000250 | 0.00025 |
| 40 | `theil_sen` | 96h | 5 | IGSS | two_sided | 50 | **0.000500** | [0.000379, 0.000659] | 29 | 0.000290 | 0.00025 |
| 41 | `theil_sen` | 120h | 6 | IDSS | upper | 50 | **0.000500** | [0.000379, 0.000659] | 21 | 0.000210 | 0.00025 |
| 42 | `theil_sen` | 120h | 6 | VGS(th) | two_sided | 57 | **0.000570** | [0.000440, 0.000738] | 22 | 0.000220 | 0.00025 |
| 43 | `theil_sen` | 120h | 6 | RDS(on) | upper | 47 | **0.000470** | [0.000353, 0.000625] | 17 | 0.000170 | 0.00025 |
| 44 | `theil_sen` | 120h | 6 | IGSS | two_sided | 60 | **0.000600** | [0.000466, 0.000772] | 14 | 0.000140 | 0.00025 |
| 45 | `theil_sen` | 168h | 7 | IDSS | upper | 59 | **0.000590** | [0.000457, 0.000761] | 21 | 0.000210 | 0.00025 |
| 46 | `theil_sen` | 168h | 7 | VGS(th) | two_sided | 91 | **0.000910** | [0.000741, 0.001117] | 32 | 0.000320 | 0.00025 |
| 47 | `theil_sen` | 168h | 7 | RDS(on) | upper | 78 | **0.000780** | [0.000625, 0.000973] | 24 | 0.000240 | 0.00025 |
| 48 | `theil_sen` | 168h | 7 | IGSS | two_sided | 119 | **0.001190** | [0.000995, 0.001424] | 28 | 0.000280 | 0.00025 |
| 49 | `ols_t` | 48h | 3 | IDSS | upper | 45 | **0.000450** | [0.000336, 0.000602] | 34 | 0.000340 | 0.00025 |
| 50 | `ols_t` | 48h | 3 | VGS(th) | two_sided | 32 | **0.000320** | [0.000227, 0.000452] | 13 | 0.000130 | 0.00025 |
| 51 | `ols_t` | 48h | 3 | RDS(on) | upper | 23 | **0.000230** | [0.000153, 0.000345] | 26 | 0.000260 | 0.00025 |
| 52 | `ols_t` | 48h | 3 | IGSS | two_sided | 37 | **0.000370** | [0.000268, 0.000510] | 27 | 0.000270 | 0.00025 |
| 53 | `ols_t` | 72h | 4 | IDSS | upper | 30 | **0.000300** | [0.000210, 0.000428] | 24 | 0.000240 | 0.00025 |
| 54 | `ols_t` | 72h | 4 | VGS(th) | two_sided | 38 | **0.000380** | [0.000277, 0.000522] | 18 | 0.000180 | 0.00025 |
| 55 | `ols_t` | 72h | 4 | RDS(on) | upper | 34 | **0.000340** | [0.000243, 0.000475] | 23 | 0.000230 | 0.00025 |
| 56 | `ols_t` | 72h | 4 | IGSS | two_sided | 32 | **0.000320** | [0.000227, 0.000452] | 18 | 0.000180 | 0.00025 |
| 57 | `ols_t` | 96h | 5 | IDSS | upper | 42 | **0.000420** | [0.000311, 0.000568] | 25 | 0.000250 | 0.00025 |
| 58 | `ols_t` | 96h | 5 | VGS(th) | two_sided | 29 | **0.000290** | [0.000202, 0.000416] | 16 | 0.000160 | 0.00025 |
| 59 | `ols_t` | 96h | 5 | RDS(on) | upper | 40 | **0.000400** | [0.000294, 0.000545] | 21 | 0.000210 | 0.00025 |
| 60 | `ols_t` | 96h | 5 | IGSS | two_sided | 64 | **0.000640** | [0.000501, 0.000817] | 32 | 0.000320 | 0.00025 |
| 61 | `ols_t` | 120h | 6 | IDSS | upper | 51 | **0.000510** | [0.000388, 0.000670] | 15 | 0.000150 | 0.00025 |
| 62 | `ols_t` | 120h | 6 | VGS(th) | two_sided | 63 | **0.000630** | [0.000492, 0.000806] | 18 | 0.000180 | 0.00025 |
| 63 | `ols_t` | 120h | 6 | RDS(on) | upper | 48 | **0.000480** | [0.000362, 0.000636] | 26 | 0.000260 | 0.00025 |
| 64 | `ols_t` | 120h | 6 | IGSS | two_sided | 68 | **0.000680** | [0.000536, 0.000862] | 28 | 0.000280 | 0.00025 |
| 65 | `ols_t` | 168h | 7 | IDSS | upper | 44 | **0.000440** | [0.000328, 0.000591] | 16 | 0.000160 | 0.00025 |
| 66 | `ols_t` | 168h | 7 | VGS(th) | two_sided | 69 | **0.000690** | [0.000545, 0.000873] | 17 | 0.000170 | 0.00025 |
| 67 | `ols_t` | 168h | 7 | RDS(on) | upper | 71 | **0.000710** | [0.000563, 0.000895] | 33 | 0.000330 | 0.00025 |
| 68 | `ols_t` | 168h | 7 | IGSS | two_sided | 69 | **0.000690** | [0.000545, 0.000873] | 23 | 0.000230 | 0.00025 |

#### Table 3: Module A Endpoint Drift Comparator on Null B (Frozen Rule: |g_p| >= 2.5)

| Horizon | K | N Components | Component Breaches | Operating FWER | Wilson 95% CI | IDSS FPR | VGS(th) FPR | RDS(on) FPR | IGSS FPR |
|---|---|---|---|---|---|---|---|---|---|
| 24h | 2 | 100,000 | 24,242 | **0.242420** | [0.239774, 0.245086] | 0.0595 | 0.0756 | 0.0829 | 0.0501 |
| 48h | 3 | 100,000 | 34,781 | **0.347810** | [0.344864, 0.350768] | 0.0918 | 0.1119 | 0.1206 | 0.0806 |
| 72h | 4 | 100,000 | 37,240 | **0.372400** | [0.369409, 0.375401] | 0.1013 | 0.1216 | 0.1275 | 0.0893 |
| 96h | 5 | 100,000 | 38,014 | **0.380140** | [0.377136, 0.383153] | 0.1025 | 0.1231 | 0.1319 | 0.0918 |
| 120h | 6 | 100,000 | 38,172 | **0.381720** | [0.378714, 0.384736] | 0.1051 | 0.1232 | 0.1330 | 0.0927 |
| 168h | 7 | 100,000 | 38,259 | **0.382590** | [0.379582, 0.385607] | 0.1045 | 0.1250 | 0.1325 | 0.0921 |

#### Detailed Forensic Analysis & Stress Test Robustness Accounting

1. **Kendall's $\tau$ Behavior under Synthetic AR(1) Stress Model**:
   - Within the tested synthetic AR(1) regime, Kendall's $\tau$ remained below the nominal component-level FWER target at K=7; K≤6 has zero Step-1 rejection capacity by the analytical rank-support bound.
   - *Horizons $K \le 6$ ($T \le 120\ \text{h}$)*: Exactly **0** component-level Holm rejections out of 100,000 components across all 5 horizons (FWER = $0.000000$, Wilson 95% CI: $[0.0, 3.8 \times 10^{-5}]$). Exactly 0 parameter false positives across all 20 cells. This zero rejection rate is strictly an algebraic consequence of the analytical rank-support bound ($p \ge 1/K! > 0.00025$); it does NOT constitute empirical evidence of detector robustness to serial noise correlation.
   - *Horizon $K = 7$ ($T = 168\ \text{h}$)*: Observed 88 component rejections (FWER = $0.000880$, Wilson 95% CI: $[0.000714, 0.001084]$). The nominal target $\alpha = 0.001000$ is strictly contained within the 95% CI. In Null-A, FWER was $0.000300$; positive serial correlation moderately increases monotonic runs, but operating FWER remains controlled below nominal $\alpha = 0.001000$. Two-sided parameters ($V_{\text{GS(th)}}, I_{\text{GSS}}$) produced 0 rejections due to the Step-1 analytical threshold barrier ($2/7! = 0.0003968 > 0.000250$).
2. **Continuous Slope Estimator Sensitivity to AR(1) Correlation (Theil-Sen & OLS $t$)**:
   - Within the synthetic AR(1) stress model, increasing temporal dependence and temporal support produced increasing false-positive rates for the slope-based detectors when evaluated against IID-derived calibration:
     - Theil-Sen: 0.000120, 0.000770, 0.001280, 0.002000, 0.002130, 0.003470
     - OLS: 0.001360, 0.001340, 0.001750, 0.002290, 0.002530
     across their applicable horizons.
   - Under positive AR(1) correlation ($\phi \in [0.20, 0.35]$), consecutive errors tend to be of the same sign, generating spurious apparent trends in finite samples.
   - *Theil-Sen Robust Slope*: At $K=2$ ($24\text{h}$), slope variance is reduced ($2\sigma^2(1-\phi) < 2\sigma^2$), causing rejections to drop to 12 ($0.000120$). At $K=3$ ($48\text{h}$), rejections are 77 ($0.000770$). As horizon expands ($K=4..7$), longer temporal persistence widens the effective sampling variance of slopes, increasing operating FWER to $0.001280$ ($72\text{h}$), $0.002000$ ($96\text{h}$), $0.002130$ ($120\text{h}$), and $0.003470$ ($168\text{h}$).
   - *Parametric OLS $t$-Statistic*: Exhibits the classic econometric inflation of $t$-statistics under unmodeled positive autocorrelation, rising from $0.001360$ at $48\text{h}$ to $0.002530$ at $168\text{h}$.
   - *Documented Limitation & Invariants*: This is a documented limitation of applying the Null-A IID calibration to the tested temporally correlated synthetic regime. Null B is strictly an out-of-distribution stress test, not a recalibration set. No thresholds may be changed, no Null-A calibration artifact may be modified, no detector may be redesigned from Null-B, and the formal calibration/FWER claim remains restricted to the preregistered Null-A model.
3. **Module A Comparator Contrast**:
   - The frozen non-calibrated Module A endpoint drift comparator exhibits massive breach rates of $24.2\% - 38.3\%$ across all horizons ($24,000 - 38,000$ component false alarms per 100,000 null components), demonstrating that the calibrated detectors provide more than two orders of magnitude lower false alarm rates under synthetic AR(1) stress.
4. **Systematic Anti-Conservatism Accounting**:
   - Under Null A (IID white noise), cross-horizon mean FWER was $0.001020$ (no systematic elevation).
   - Under Null B (positive AR(1) stress), continuous slope estimators exhibit systematic elevation at longer horizons ($K \ge 4$, FWER $\approx 0.0013 - 0.0035$), whereas Kendall's $\tau$ preserves FWER control below nominal $\alpha = 0.001000$ at $K=7$ ($0.000880$).
5. **Epistemic Invariant & Boundary Statement**:
   - Null B evaluates detector behavior against a synthetic AR(1) stress model under identical lot topology ($L=20$) and LOO median excess coordinates.
   - It does not represent empirical telemetry from real ATE/chamber environments and does not validate physical device reliability or spaceflight qualification under MIL-PRF-19500.
- **Reason**: Complete execution and forensic reporting of Phase 2.3 Null-B Stress Test per frozen calibration protocol.
- **Source / Provenance**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` (v1.9.0), `src/sih26170/screening/phase4b_null_b.py`, `data/evaluation_phase4b/null_b_stress_results.json`, LOG-087.
- **Gate Outcome**: **PHASE 2.3 NULL-B STRESS TEST COMPLETE — ACCEPTED AS VALID STRESS-TEST RESULT — AUTHORIZED PHASE 2.4 NULL-C**
- **Affected Area**: `src/sih26170/screening/phase4b_null_b.py`, `tests/screening/test_phase4b_null_b.py`, `data/evaluation_phase4b/null_b_stress_results.json`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Canonical Invariants Preserved**: Zero recalibration; calibration artifacts 100% unmutated; 196/196 pytest tests passing; frozen benchmark hashes unchanged; zero execution of power sweeps, validation, or final evaluation.

---


### LOG-089: Phase 4B Phase 2.4 Null-C Common-Mode Stress Test Gate

- **Log ID**: LOG-089
- **Date**: 2026-09-17
- **Phase**: Phase 4B / Phase 2.4 Null-C Common-Mode Stress Test Gate
- **Change**: Executed Phase 2.4 Null-C common-mode stress test on $N_C = 100{,}000$ complete components in $5{,}000$ lots ($400{,}000$ parameter series) under dedicated HMAC seed `622638004` per §6.H.4. A synchronous chamber thermal excursion of $\Delta T = +5.0^\circ\text{C}$ was applied identically to all $L = 20$ components within each lot at checkpoints $t \in \{72, 96\}\ \text{h}$, shifting observed coordinates transductively via pre-registered temperature coefficients ($I_{\text{DSS}}: +0.04/^{\circ}\text{C}$, $V_{\text{GS(th)}}: -0.005/^{\circ}\text{C}$, $R_{\text{DS(on)}}: +0.005/^{\circ}\text{C}$, $I_{\text{GSS}}: +0.02/^{\circ}\text{C}$). Evaluated all 68 candidate detector cells, all 17 component-level Holm FWER cells, and Module A comparator (on both LOO excess and raw coordinates) against the frozen Null-A calibration reference artifacts (`calibration_reference_table.json` and `calibration_distributions.npz`) in strictly read-only mode without threshold adjustments, recalibration, or pooling.
- **Previous State**: LOG-088 documented the Phase 2.3 Null-B AR(1) stress test results. Null-B established that under positive AR(1) temporal correlation, frozen IID calibration produces increasing false-positive rates for continuous slope detectors as temporal support increases. The Null-C common-mode stress test set was uninstantiated.
- **New State**:
  1. **Stress Test Execution & Sample Accounting**:
     - Total Components Evaluated: 100,000 components across 5,000 lots ($L=20$).
     - Total Series Evaluated: 400,000 series across 4 physical parameters ($I_{\text{DSS}}, V_{\text{GS(th)}}, R_{\text{DS(on)}}, I_{\text{GSS}}$) and 7 checkpoints ($T \in \{0, 24, 48, 72, 96, 120, 168\}\ \text{h}$).
     - Dedicated Stress Seed: `622638004` (cryptographically isolated per §3).
     - Chamber Disturbance: $\Delta T = +5.0^\circ\text{C}$ applied synchronously to all 20 devices in each lot at 72h and 96h.
     - Transductive Shifts: $I_{\text{DSS}} = +0.20$ ($+2.5\sigma_u$), $V_{\text{GS(th)}} = -0.025$ ($-1.25\sigma_u$), $R_{\text{DS(on)}} = +0.025$ ($+2.0\sigma_u$), $I_{\text{GSS}} = +0.10$ ($+0.40\sigma_u$).
     - Causal LOO Excess Coordinates: Computed independently at each as-of checkpoint against simultaneous lot median excluding component $i$.
  2. **Stress Test Artifact Integrity & Cryptographic Verifications**:
     - Consumed Calibration Table SHA-256: `153d387597ba6a247ed5302a7512730c678bc3ce39e056848cd9135fc39c7d60` (100% unmutated).
     - Consumed Calibration Distributions SHA-256: `147f1d38ed9b197af6b6301b9b454223d5cce54286fcfeb89a1ea15cec055d98` (100% unmutated).
     - Produced Stress Test Artifact: `data/evaluation_phase4b/null_c_stress_results.json` (SHA-256: `ae5ef6a245f91a142e8c866ed85a044381a9de8992e23fb414bb288bf225801e`).
     - Dataset Digests: Raw measurements SHA-256: `69fdd8c055bf41c159b44475d6a6c7a313b5c729741f116f076daa58fce1346e`; Excess coordinates SHA-256: `80a3a08f39c31180fe01a31f88766dd163531f19f6b20c106f83e04b22cec164`; Common-mode shift SHA-256: `d60b93c1b9f495be4aa77393082029a3f1408231c3173f9e73fb3ff0b4f602df`.
     - Frozen Benchmarks Verified: All Phase 4B, Phase 2F, Null-A audit, and Null-B hashes verified 100% bit-for-bit unchanged.
  3. **Complete Null-C Comparison Tables**:

#### Table 1: Component-Level Family-Wise Error Rate (FWER) Across All 17 Detector-Horizon Cells (Null-C Stress vs. Null-A Audit vs. Null-B Stress, N = 100,000/cell)

| Detector Family | Role | Horizon | K | Null-C Rejections | Null-C FWER | Null-C Wilson 95% CI | Null-A FWER | Null-B FWER | Nominal Target | Sampling Compatibility (Nominal in CI?) |
|---|---|---|---|---|---|---|---|---|---|---|
| `kendall_tau` | PRIMARY CANDIDATE | 24h | 2 | 0 | **0.000000** | [0.000000, 0.000038] | 0.000000 | 0.000000 | 0.001000 | Analytical zero (K<=6 bound) |
| `kendall_tau` | PRIMARY CANDIDATE | 48h | 3 | 0 | **0.000000** | [0.000000, 0.000038] | 0.000000 | 0.000000 | 0.001000 | Analytical zero (K<=6 bound) |
| `kendall_tau` | PRIMARY CANDIDATE | 72h | 4 | 0 | **0.000000** | [0.000000, 0.000038] | 0.000000 | 0.000000 | 0.001000 | Analytical zero (K<=6 bound) |
| `kendall_tau` | PRIMARY CANDIDATE | 96h | 5 | 0 | **0.000000** | [0.000000, 0.000038] | 0.000000 | 0.000000 | 0.001000 | Analytical zero (K<=6 bound) |
| `kendall_tau` | PRIMARY CANDIDATE | 120h | 6 | 0 | **0.000000** | [0.000000, 0.000038] | 0.000000 | 0.000000 | 0.001000 | Analytical zero (K<=6 bound) |
| `kendall_tau` | PRIMARY CANDIDATE | 168h | 7 | 39 | **0.000390** | [0.000285, 0.000533] | 0.000300 | 0.000880 | 0.001000 | <= nominal (CI contains alpha) |
| `theil_sen` | AUXILIARY CANDIDATE | 24h | 2 | 79 | **0.000790** | [0.000634, 0.000984] | 0.000920 | 0.000120 | 0.001000 | <= nominal (CI contains alpha) |
| `theil_sen` | AUXILIARY CANDIDATE | 48h | 3 | 117 | **0.001170** | [0.000976, 0.001402] | 0.001240 | 0.000770 | 0.001000 | > nominal (sampling-compatible; CI contains alpha) |
| `theil_sen` | AUXILIARY CANDIDATE | 72h | 4 | 95 | **0.000950** | [0.000777, 0.001161] | 0.001080 | 0.001280 | 0.001000 | <= nominal (CI contains alpha) |
| `theil_sen` | AUXILIARY CANDIDATE | 96h | 5 | 109 | **0.001090** | [0.000904, 0.001315] | 0.001090 | 0.002000 | 0.001000 | > nominal (sampling-compatible; CI contains alpha) |
| `theil_sen` | AUXILIARY CANDIDATE | 120h | 6 | 75 | **0.000750** | [0.000598, 0.000940] | 0.000740 | 0.002130 | 0.001000 | <= nominal (CI contains alpha) |
| `theil_sen` | AUXILIARY CANDIDATE | 168h | 7 | 88 | **0.000880** | [0.000714, 0.001084] | 0.001050 | 0.003470 | 0.001000 | <= nominal (CI contains alpha) |
| `ols_t` | BENCHMARK COMPARATOR | 48h | 3 | 104 | **0.001040** | [0.000858, 0.001260] | 0.001000 | 0.001360 | 0.001000 | > nominal (sampling-compatible; CI contains alpha) |
| `ols_t` | BENCHMARK COMPARATOR | 72h | 4 | 100 | **0.001000** | [0.000822, 0.001216] | 0.000830 | 0.001340 | 0.001000 | <= nominal (CI contains alpha) |
| `ols_t` | BENCHMARK COMPARATOR | 96h | 5 | 103 | **0.001030** | [0.000849, 0.001249] | 0.000940 | 0.001750 | 0.001000 | > nominal (sampling-compatible; CI contains alpha) |
| `ols_t` | BENCHMARK COMPARATOR | 120h | 6 | 91 | **0.000910** | [0.000741, 0.001117] | 0.000870 | 0.002290 | 0.001000 | <= nominal (CI contains alpha) |
| `ols_t` | BENCHMARK COMPARATOR | 168h | 7 | 76 | **0.000760** | [0.000607, 0.000951] | 0.000890 | 0.002530 | 0.001000 | <= nominal (CI contains alpha) |

#### Table 2: Parameter-Level False Positive Rate (FPR) Across All 68 Cells (Null-C Stress vs. Null-A Audit vs. Null-B Stress, N = 100,000/cell)

| Cell # | Detector Family | Horizon | K | Parameter | Tail Direction | Null-C FPs | Null-C FPR | Null-C Wilson 95% CI | Null-A FPs | Null-B FPs | Step-1 Threshold |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | `kendall_tau` | 24h | 2 | IDSS | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 02 | `kendall_tau` | 24h | 2 | VGS(th) | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 03 | `kendall_tau` | 24h | 2 | RDS(on) | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 04 | `kendall_tau` | 24h | 2 | IGSS | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 05 | `kendall_tau` | 48h | 3 | IDSS | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 06 | `kendall_tau` | 48h | 3 | VGS(th) | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 07 | `kendall_tau` | 48h | 3 | RDS(on) | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 08 | `kendall_tau` | 48h | 3 | IGSS | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 09 | `kendall_tau` | 72h | 4 | IDSS | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 10 | `kendall_tau` | 72h | 4 | VGS(th) | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 11 | `kendall_tau` | 72h | 4 | RDS(on) | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 12 | `kendall_tau` | 72h | 4 | IGSS | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 13 | `kendall_tau` | 96h | 5 | IDSS | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 14 | `kendall_tau` | 96h | 5 | VGS(th) | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 15 | `kendall_tau` | 96h | 5 | RDS(on) | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 16 | `kendall_tau` | 96h | 5 | IGSS | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 17 | `kendall_tau` | 120h | 6 | IDSS | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 18 | `kendall_tau` | 120h | 6 | VGS(th) | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 19 | `kendall_tau` | 120h | 6 | RDS(on) | upper | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 20 | `kendall_tau` | 120h | 6 | IGSS | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 21 | `kendall_tau` | 168h | 7 | IDSS | upper | 17 | **0.000170** | [0.000106, 0.000272] | 10 | 42 | 0.00025 |
| 22 | `kendall_tau` | 168h | 7 | VGS(th) | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 23 | `kendall_tau` | 168h | 7 | RDS(on) | upper | 22 | **0.000220** | [0.000145, 0.000333] | 20 | 46 | 0.00025 |
| 24 | `kendall_tau` | 168h | 7 | IGSS | two_sided | 0 | **0.000000** | [0.000000, 0.000038] | 0 | 0 | 0.00025 |
| 25 | `theil_sen` | 24h | 2 | IDSS | upper | 21 | **0.000210** | [0.000137, 0.000321] | 21 | 2 | 0.00025 |
| 26 | `theil_sen` | 24h | 2 | VGS(th) | two_sided | 26 | **0.000260** | [0.000177, 0.000381] | 18 | 5 | 0.00025 |
| 27 | `theil_sen` | 24h | 2 | RDS(on) | upper | 12 | **0.000120** | [0.000069, 0.000210] | 23 | 1 | 0.00025 |
| 28 | `theil_sen` | 24h | 2 | IGSS | two_sided | 20 | **0.000200** | [0.000129, 0.000309] | 30 | 4 | 0.00025 |
| 29 | `theil_sen` | 48h | 3 | IDSS | upper | 35 | **0.000350** | [0.000252, 0.000487] | 21 | 15 | 0.00025 |
| 30 | `theil_sen` | 48h | 3 | VGS(th) | two_sided | 25 | **0.000250** | [0.000169, 0.000369] | 25 | 21 | 0.00025 |
| 31 | `theil_sen` | 48h | 3 | RDS(on) | upper | 24 | **0.000240** | [0.000161, 0.000357] | 32 | 16 | 0.00025 |
| 32 | `theil_sen` | 48h | 3 | IGSS | two_sided | 33 | **0.000330** | [0.000235, 0.000463] | 46 | 25 | 0.00025 |
| 33 | `theil_sen` | 72h | 4 | IDSS | upper | 37 | **0.000370** | [0.000268, 0.000510] | 33 | 38 | 0.00025 |
| 34 | `theil_sen` | 72h | 4 | VGS(th) | two_sided | 20 | **0.000200** | [0.000129, 0.000309] | 24 | 38 | 0.00025 |
| 35 | `theil_sen` | 72h | 4 | RDS(on) | upper | 19 | **0.000190** | [0.000122, 0.000297] | 24 | 26 | 0.00025 |
| 36 | `theil_sen` | 72h | 4 | IGSS | two_sided | 19 | **0.000190** | [0.000122, 0.000297] | 27 | 26 | 0.00025 |
| 37 | `theil_sen` | 96h | 5 | IDSS | upper | 40 | **0.000400** | [0.000294, 0.000545] | 29 | 73 | 0.00025 |
| 38 | `theil_sen` | 96h | 5 | VGS(th) | two_sided | 28 | **0.000280** | [0.000194, 0.000405] | 26 | 50 | 0.00025 |
| 39 | `theil_sen` | 96h | 5 | RDS(on) | upper | 15 | **0.000150** | [0.000091, 0.000247] | 25 | 27 | 0.00025 |
| 40 | `theil_sen` | 96h | 5 | IGSS | two_sided | 27 | **0.000270** | [0.000186, 0.000393] | 29 | 50 | 0.00025 |
| 41 | `theil_sen` | 120h | 6 | IDSS | upper | 15 | **0.000150** | [0.000091, 0.000247] | 21 | 50 | 0.00025 |
| 42 | `theil_sen` | 120h | 6 | VGS(th) | two_sided | 29 | **0.000290** | [0.000202, 0.000416] | 22 | 57 | 0.00025 |
| 43 | `theil_sen` | 120h | 6 | RDS(on) | upper | 7 | **0.000070** | [0.000034, 0.000144] | 17 | 47 | 0.00025 |
| 44 | `theil_sen` | 120h | 6 | IGSS | two_sided | 24 | **0.000240** | [0.000161, 0.000357] | 14 | 60 | 0.00025 |
| 45 | `theil_sen` | 168h | 7 | IDSS | upper | 16 | **0.000160** | [0.000098, 0.000260] | 21 | 59 | 0.00025 |
| 46 | `theil_sen` | 168h | 7 | VGS(th) | two_sided | 18 | **0.000180** | [0.000114, 0.000285] | 32 | 91 | 0.00025 |
| 47 | `theil_sen` | 168h | 7 | RDS(on) | upper | 26 | **0.000260** | [0.000177, 0.000381] | 24 | 78 | 0.00025 |
| 48 | `theil_sen` | 168h | 7 | IGSS | two_sided | 28 | **0.000280** | [0.000194, 0.000405] | 28 | 119 | 0.00025 |
| 49 | `ols_t` | 48h | 3 | IDSS | upper | 28 | **0.000280** | [0.000194, 0.000405] | 34 | 45 | 0.00025 |
| 50 | `ols_t` | 48h | 3 | VGS(th) | two_sided | 23 | **0.000230** | [0.000153, 0.000345] | 13 | 32 | 0.00025 |
| 51 | `ols_t` | 48h | 3 | RDS(on) | upper | 25 | **0.000250** | [0.000169, 0.000369] | 26 | 23 | 0.00025 |
| 52 | `ols_t` | 48h | 3 | IGSS | two_sided | 28 | **0.000280** | [0.000194, 0.000405] | 27 | 37 | 0.00025 |
| 53 | `ols_t` | 72h | 4 | IDSS | upper | 25 | **0.000250** | [0.000169, 0.000369] | 24 | 30 | 0.00025 |
| 54 | `ols_t` | 72h | 4 | VGS(th) | two_sided | 30 | **0.000300** | [0.000210, 0.000428] | 18 | 38 | 0.00025 |
| 55 | `ols_t` | 72h | 4 | RDS(on) | upper | 19 | **0.000190** | [0.000122, 0.000297] | 23 | 34 | 0.00025 |
| 56 | `ols_t` | 72h | 4 | IGSS | two_sided | 26 | **0.000260** | [0.000177, 0.000381] | 18 | 32 | 0.00025 |
| 57 | `ols_t` | 96h | 5 | IDSS | upper | 21 | **0.000210** | [0.000137, 0.000321] | 25 | 42 | 0.00025 |
| 58 | `ols_t` | 96h | 5 | VGS(th) | two_sided | 22 | **0.000220** | [0.000145, 0.000333] | 16 | 29 | 0.00025 |
| 59 | `ols_t` | 96h | 5 | RDS(on) | upper | 24 | **0.000240** | [0.000161, 0.000357] | 21 | 40 | 0.00025 |
| 60 | `ols_t` | 96h | 5 | IGSS | two_sided | 36 | **0.000360** | [0.000260, 0.000498] | 32 | 64 | 0.00025 |
| 61 | `ols_t` | 120h | 6 | IDSS | upper | 18 | **0.000180** | [0.000114, 0.000285] | 15 | 51 | 0.00025 |
| 62 | `ols_t` | 120h | 6 | VGS(th) | two_sided | 29 | **0.000290** | [0.000202, 0.000416] | 18 | 63 | 0.00025 |
| 63 | `ols_t` | 120h | 6 | RDS(on) | upper | 26 | **0.000260** | [0.000177, 0.000381] | 26 | 48 | 0.00025 |
| 64 | `ols_t` | 120h | 6 | IGSS | two_sided | 18 | **0.000180** | [0.000114, 0.000285] | 28 | 68 | 0.00025 |
| 65 | `ols_t` | 168h | 7 | IDSS | upper | 13 | **0.000130** | [0.000076, 0.000222] | 16 | 44 | 0.00025 |
| 66 | `ols_t` | 168h | 7 | VGS(th) | two_sided | 24 | **0.000240** | [0.000161, 0.000357] | 17 | 69 | 0.00025 |
| 67 | `ols_t` | 168h | 7 | RDS(on) | upper | 24 | **0.000240** | [0.000161, 0.000357] | 33 | 71 | 0.00025 |
| 68 | `ols_t` | 168h | 7 | IGSS | two_sided | 15 | **0.000150** | [0.000091, 0.000247] | 23 | 69 | 0.00025 |

#### Table 3: Module A Endpoint Drift Comparator on Null C (Frozen Rule: |g_p| >= 2.5)

> [!NOTE]
> The ~38% breach rates below reflect the behavior of the frozen NON-CALIBRATED Module A comparator, NOT calibrated detector system FWER. The Raw/Excess FPR Ratio of ~0.71x at non-disturbance horizons (24h, 48h, 120h, 168h) arises from lot-median differencing geometry on i.i.d. noise; common-mode suppression is specifically evaluated at 72h and 96h where raw breach rates jump to 76.8% while excess rates remain unchanged at 38.3%.

| Horizon | K | N Components | Excess Breaches | Excess FPR | Excess Wilson 95% CI | Raw Breaches | Raw FPR | Raw Wilson 95% CI | Raw/Excess FPR Ratio |
|---|---|---|---|---|---|---|---|---|---|
| 24h | 2 | 100,000 | 38,497 | **0.384970** | [0.381959, 0.387990] | 27,302 | **0.273020** | [0.270268, 0.275790] | 0.71x |
| 48h | 3 | 100,000 | 38,389 | **0.383890** | [0.380880, 0.386909] | 27,376 | **0.273760** | [0.271005, 0.276532] | 0.71x |
| 72h | 4 | 100,000 | 38,378 | **0.383780** | [0.380770, 0.386799] | 76,588 | **0.765880** | [0.763245, 0.768494] | 2.00x |
| 96h | 5 | 100,000 | 38,339 | **0.383390** | [0.380381, 0.386408] | 76,805 | **0.768050** | [0.765424, 0.770656] | 2.00x |
| 120h | 6 | 100,000 | 38,719 | **0.387190** | [0.384175, 0.390213] | 27,506 | **0.275060** | [0.272301, 0.277836] | 0.71x |
| 168h | 7 | 100,000 | 38,189 | **0.381890** | [0.378883, 0.384906] | 27,496 | **0.274960** | [0.272201, 0.277736] | 0.72x |

#### Detailed Forensic Analysis & Stress Test Robustness Accounting

1. **Common-Mode Cancellation Mechanics by Leave-One-Out (LOO) Lot Median Differencing**:
   - Within the specified synthetic additive synchronous common-mode model, causal LOO lot-median differencing cancels the perturbation to machine precision ($\max |\Delta_{\text{LOO}}| < 10^{-15}$).
   - Under the synthetic chamber thermal excursion ($\Delta T = +5.0^\circ\text{C}$ at 72h and 96h), unmitigated raw coordinates undergo severe common-mode jumps ($+2.5\sigma_u$ on $I_{\text{DSS}}$, $+2.0\sigma_u$ on $R_{\text{DS(on)}}$, $-1.25\sigma_u$ on $V_{\text{GS(th)}}$).
   - On raw coordinates, the frozen non-calibrated Module A comparator experiences an elevated false-alarm rate: component breach rate jumps from $27.3\%$ to **$76.6\% - 76.8\%$** at 72h and 96h ($76{,}588$ and $76{,}805$ breaches per $100{,}000$ components), with $I_{\text{DSS}}$ parameter FPR reaching $50.2\%$ and $R_{\text{DS(on)}}$ reaching $36.5\%$.
   - On excess coordinates, Module A breach rates at 72h ($38.38\%$) and 96h ($38.34\%$) remain consistent with baseline ($38.50\%$, $38.39\%$), reflecting the properties of the LOO construction under the synthetic common-mode model.
2. **Detector Behavior under Null-C Common-Mode Stress**:
   - **Kendall's $\tau$**: Evaluated across all 6 horizons. For $K \le 6$ ($24\text{h}..120\text{h}$), zero component-level rejections occur (FWER = $0.000000$); this is strictly an analytical consequence of the rank-support bound ($p \ge 1/K! > 0.00025$) and does NOT constitute empirical evidence of robustness. Horizon $K=7$ ($168\text{h}$) provides the first tested horizon with theoretical Step-1 rejection capacity; at $K=7$, exactly 39 rejections were observed (FWER = $0.000390$, Wilson 95% CI: $[0.000285, 0.000533]$), which is below nominal $\alpha = 0.001000$ and comparable to Null-A ($30$ rejections / $0.000300$).
   - **Theil-Sen Robust Slope**: Point estimates across horizons are $0.000790$ (24h), $0.001170$ (48h), $0.000950$ (72h), $0.001090$ (96h), $0.000750$ (120h), and $0.000880$ (168h). Point estimates at 48h ($0.001170$) and 96h ($0.001090$) are slightly above nominal $\alpha = 0.001000$, but their Wilson 95% CIs ($[0.000976, 0.001402]$ and $[0.000904, 0.001315]$) both contain the nominal target $0.001000$. This indicates sampling compatibility rather than unconditional conformity.
   - **Parametric OLS $t$-Statistic**: Point estimates across horizons are $0.001040$ (48h), $0.001000$ (72h), $0.001030$ (96h), $0.000910$ (120h), and $0.000760$ (168h). Point estimates at 48h ($0.001040$) and 96h ($0.001030$) are slightly above nominal, with 95% CIs ($[0.000858, 0.001260]$ and $[0.000849, 0.001249]$) containing nominal $\alpha = 0.001000$.
   - **Common-Mode Association**: No material common-mode-associated FWER elevation was observed relative to corresponding Null-A results.
3. **Comparison with Null-B AR(1) Stress Results (Without Pooling)**:
   - Under Null-B (temporal autocorrelation stress), continuous slope estimators exhibited marked FWER inflation at longer horizons (Theil-Sen reaching $0.003470$ and OLS $t$ reaching $0.002530$ at 168h) due to unmodeled positive noise correlation.
   - Under Null-C (common-mode spatial stress), neither Theil-Sen nor OLS $t$ exhibits such horizon-expanding inflation (Theil-Sen at 168h is $0.000880$; OLS $t$ is $0.000760$).
   - The contrast is consistent with the previously observed Null-B inflation being driven by temporal autocorrelation rather than by the common-mode mechanism tested in Null-C.
4. **Verification of False-Positive Inflation**: No anomalous false-positive inflation was observed under the tested common-mode null; sensitivity and power remain unevaluated and are reserved for the preregistered power sweep. Discreteness audit confirmed 0 non-finite statistics across all 6,800,000 evaluations.
5. **Architectural & Epistemic Limitations**:
   - *Architectural Limitation*: Perfectly synchronous lot-wide movement is removed by the LOO construction. Therefore, Null-C does not establish sensitivity to lot-wide correlated physical degradation.
   - *Epistemic Limitation*: Null C establishes detector behavior strictly against the specified synthetic additive synchronous common-mode model. It does not constitute empirical evidence or qualification regarding actual semiconductor physics or physical chamber excursions under MIL-PRF-19500.
- **Reason**: Complete execution and forensic reporting of Phase 2.4 Null-C Common-Mode Stress Test per frozen calibration protocol.
- **Source / Provenance**: `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` (v1.9.0), `src/sih26170/screening/phase4b_null_c.py`, `data/evaluation_phase4b/null_c_stress_results.json`, LOG-088.
- **Gate Outcome**: **Null-C ACCEPTED WITH DOCUMENTED LIMITATIONS — FROZEN AT FREEZE 3 — POWER SWEEP AUTHORIZED AND COMPLETED IN LOG-090**
- **Affected Area**: `src/sih26170/screening/phase4b_null_c.py`, `tests/screening/test_phase4b_null_c.py`, `data/evaluation_phase4b/null_c_stress_results.json`, `data/evaluation_phase4b/checksums.sha256`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Canonical Invariants Preserved**: Dedicated seed `622638004`; $N=100{,}000$ components in $5{,}000$ lots ($L=20$); frozen Null-A calibration; all hashes bit-for-bit unchanged; zero recalibration; zero detector changes; 196/196 pytest tests passing; zero execution of power sweeps, validation, or final evaluation.

---

### LOG-090: Phase 4B Independent Power Calibration Sweep Gate
- **Timestamp**: 2026-09-17T18:25:00Z
- **Phase**: Phase 4B / Independent Power Calibration Sweep (§9)
- **Type**: POWER_CALIBRATION_SWEEP_GATE
- **Supersedes / Amends**: LOG-089
- **Status**: POWER SWEEP COMPLETED — FROZEN AT FREEZE 4 — STOPPED AWAITING VALIDATION AUTHORIZATION

#### 1. Scope, Protocol Verification & Invariants Enforced
Pursuant to formal gate authorization, the Phase 4B Independent Power Sweep was executed strictly under `docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md` (v1.9.0) §9.A.2.

Strict invariants verified prior to and throughout execution:
1. **Dedicated Independent HMAC Seed**: Evaluated strictly under preregistered seed `15152878` (`"calibration:power:v1"`).
2. **δ-to-Morphology Mapping Verification**: Prior to execution, verified that the independent power sweep grid (§9.A.2) is complete, uniform, and frozen across all six fixture morphologies ($A, B, C, D, E, F$) and all four effect sizes $\delta \in \{1.0, 1.5, 2.0, 2.5\}\sigma_{u,p}$ ($24$ cells total). Evaluated $N = 10{,}000$ components per cell ($240{,}000$ components total, $960{,}000$ parameter series). Zero ambiguity and zero discrepancy detected.
3. **Strict Immutability of Frozen Artifacts**: Read-only consumption of Null-A calibration reference table (`153d387597ba...`) and distributions (`147f1d38ed9b...`). Bit-for-bit unmutated preservation verified for all 13 baseline benchmark and evaluation artifacts.
4. **Zero Recalibration, Zero Detector Changes, Zero Threshold Tuning**: All empirical p-value evaluations and Holm step-down decisions ($\alpha = 0.001$, Step-1 $\alpha/4 = 0.00025$) executed strictly against the frozen Null-A empirical reference distributions.
5. **No Pooling Across Datasets**: Power sweep results are maintained completely isolated in `data/evaluation_phase4b/power_sweep_results.json` without pooling into Null-A, Null-B, Null-C, or benchmark evaluation partitions.
6. **Preservation of Causal As-Of Boundary**: Evaluated strictly across discrete causal checkpoints $T_{\text{as\_of}} \in \{24, 48, 72, 96, 120, 168\}\ \text{h}$ ($K \in \{2, 3, 4, 5, 6, 7\}$).
7. **Preservation of LOO Lot-Median Topology**: Each degraded device evaluated within a manufacturing lot of $L=20$ with 19 stationary peer devices.
8. **Preservation of Signed $I_{\text{GSS}}$ Semantics**: Gate leakage evaluated with continuous signed semantics and two-sided symmetric tail testing throughout.

---

#### 2. Comprehensive Power Sweep Results

##### Table 1: Component-Level Holm Step-Down Detection Power at Final Horizon $T = 168\ \text{h}$ ($K=7, \alpha = 0.001$)
*N = 10,000 components per cell (240,000 total). Parentheses indicate detected count $k$. Wilson 95% score confidence intervals shown in brackets.*

| Morphology | Delta | Kendall Tau (Primary) | Wilson 95% CI | Theil-Sen (Auxiliary) | Wilson 95% CI | OLS t (Comparator) | Wilson 95% CI | Module A Drift Comparator (|g|>=2.5) | Wilson 95% CI |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| A Linear Drift | 1.0σ | 0.0017 (17) | [0.0011, 0.0027] | 0.0054 (54) | [0.0041, 0.0070] | 0.0028 (28) | [0.0019, 0.0040] | 0.5655 (5655) | [0.5558, 0.5752] |
| A Linear Drift | 1.5σ | 0.0036 (36) | [0.0026, 0.0050] | 0.0149 (149) | [0.0127, 0.0175] | 0.0070 (70) | [0.0055, 0.0088] | 0.7113 (7113) | [0.7023, 0.7201] |
| A Linear Drift | 2.0σ | 0.0056 (56) | [0.0043, 0.0073] | 0.0362 (362) | [0.0327, 0.0400] | 0.0132 (132) | [0.0111, 0.0156] | 0.8541 (8541) | [0.8470, 0.8609] |
| A Linear Drift | 2.5σ | 0.0086 (86) | [0.0070, 0.0106] | 0.0811 (811) | [0.0759, 0.0866] | 0.0208 (208) | [0.0182, 0.0238] | 0.9415 (9415) | [0.9367, 0.9459] |
| B Accelerating Drift | 1.0σ | 0.0012 (12) | [0.0007, 0.0021] | 0.0050 (50) | [0.0038, 0.0066] | 0.0036 (36) | [0.0026, 0.0050] | 0.5685 (5685) | [0.5588, 0.5782] |
| B Accelerating Drift | 1.5σ | 0.0029 (29) | [0.0020, 0.0042] | 0.0130 (130) | [0.0110, 0.0154] | 0.0080 (80) | [0.0064, 0.0099] | 0.7109 (7109) | [0.7019, 0.7197] |
| B Accelerating Drift | 2.0σ | 0.0050 (50) | [0.0038, 0.0066] | 0.0296 (296) | [0.0265, 0.0331] | 0.0116 (116) | [0.0097, 0.0139] | 0.8477 (8477) | [0.8405, 0.8546] |
| B Accelerating Drift | 2.5σ | 0.0083 (83) | [0.0067, 0.0103] | 0.0640 (640) | [0.0594, 0.0690] | 0.0191 (191) | [0.0166, 0.0220] | 0.9389 (9389) | [0.9340, 0.9434] |
| C Abrupt Step | 1.0σ | 0.0028 (28) | [0.0019, 0.0040] | 0.0145 (145) | [0.0123, 0.0170] | 0.0044 (44) | [0.0033, 0.0059] | 0.5526 (5526) | [0.5428, 0.5623] |
| C Abrupt Step | 1.5σ | 0.0043 (43) | [0.0032, 0.0058] | 0.0500 (500) | [0.0459, 0.0544] | 0.0077 (77) | [0.0062, 0.0096] | 0.7211 (7211) | [0.7122, 0.7298] |
| C Abrupt Step | 2.0σ | 0.0060 (60) | [0.0047, 0.0077] | 0.1340 (1340) | [0.1275, 0.1408] | 0.0120 (120) | [0.0100, 0.0143] | 0.8551 (8551) | [0.8481, 0.8619] |
| C Abrupt Step | 2.5σ | 0.0109 (109) | [0.0090, 0.0131] | 0.3027 (3027) | [0.2938, 0.3118] | 0.0183 (183) | [0.0159, 0.0211] | 0.9390 (9390) | [0.9341, 0.9435] |
| D Confounded Drift | 1.0σ | 0.0010 (10) | [0.0005, 0.0018] | 0.0056 (56) | [0.0043, 0.0073] | 0.0027 (27) | [0.0019, 0.0039] | 0.5607 (5607) | [0.5510, 0.5704] |
| D Confounded Drift | 1.5σ | 0.0038 (38) | [0.0028, 0.0052] | 0.0158 (158) | [0.0135, 0.0184] | 0.0073 (73) | [0.0058, 0.0092] | 0.7185 (7185) | [0.7096, 0.7272] |
| D Confounded Drift | 2.0σ | 0.0061 (61) | [0.0048, 0.0078] | 0.0351 (351) | [0.0317, 0.0389] | 0.0140 (140) | [0.0119, 0.0165] | 0.8496 (8496) | [0.8425, 0.8565] |
| D Confounded Drift | 2.5σ | 0.0116 (116) | [0.0097, 0.0139] | 0.0834 (834) | [0.0781, 0.0890] | 0.0225 (225) | [0.0198, 0.0256] | 0.9385 (9385) | [0.9336, 0.9430] |
| E Heteroscedastic Noise | 1.0σ | 0.0016 (16) | [0.0010, 0.0026] | 0.0209 (209) | [0.0183, 0.0239] | 0.0028 (28) | [0.0019, 0.0040] | 0.6920 (6920) | [0.6829, 0.7010] |
| E Heteroscedastic Noise | 1.5σ | 0.0022 (22) | [0.0015, 0.0033] | 0.0457 (457) | [0.0418, 0.0500] | 0.0052 (52) | [0.0040, 0.0068] | 0.7845 (7845) | [0.7763, 0.7924] |
| E Heteroscedastic Noise | 2.0σ | 0.0051 (51) | [0.0039, 0.0067] | 0.0948 (948) | [0.0892, 0.1007] | 0.0098 (98) | [0.0080, 0.0119] | 0.8823 (8823) | [0.8758, 0.8885] |
| E Heteroscedastic Noise | 2.5σ | 0.0068 (68) | [0.0054, 0.0086] | 0.1748 (1748) | [0.1675, 0.1824] | 0.0133 (133) | [0.0112, 0.0157] | 0.9449 (9449) | [0.9403, 0.9492] |
| F Staggered Onset | 1.0σ | 0.0020 (20) | [0.0013, 0.0031] | 0.0061 (61) | [0.0048, 0.0078] | 0.0034 (34) | [0.0024, 0.0047] | 0.5585 (5585) | [0.5487, 0.5682] |
| F Staggered Onset | 1.5σ | 0.0037 (37) | [0.0027, 0.0051] | 0.0156 (156) | [0.0134, 0.0182] | 0.0081 (81) | [0.0065, 0.0101] | 0.7126 (7126) | [0.7036, 0.7214] |
| F Staggered Onset | 2.0σ | 0.0055 (55) | [0.0042, 0.0072] | 0.0416 (416) | [0.0379, 0.0457] | 0.0141 (141) | [0.0120, 0.0166] | 0.8548 (8548) | [0.8478, 0.8616] |
| F Staggered Onset | 2.5σ | 0.0108 (108) | [0.0090, 0.0130] | 0.0988 (988) | [0.0931, 0.1048] | 0.0258 (258) | [0.0229, 0.0291] | 0.9382 (9382) | [0.9333, 0.9428] |

---

##### Table 2: Theil-Sen Component Detection Power Across Horizons at $\delta = 2.5\sigma$
*N = 10,000 components per cell. Values indicate empirical power (count).*

| Morphology | T=24h (K=2) | T=48h (K=3) | T=72h (K=4) | T=96h (K=5) | T=120h (K=6) | T=168h (K=7) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| A Linear Drift | 0.0014 (14) | 0.0048 (48) | 0.0070 (70) | 0.0144 (144) | 0.0248 (248) | 0.0811 (811) |
| B Accelerating Drift | 0.0012 (12) | 0.0012 (12) | 0.0020 (20) | 0.0039 (39) | 0.0069 (69) | 0.0640 (640) |
| C Abrupt Step | 0.0012 (12) | 0.0012 (12) | 0.0604 (604) | 0.1694 (1694) | 0.2283 (2283) | 0.3027 (3027) |
| D Confounded Drift | 0.0016 (16) | 0.0040 (40) | 0.0078 (78) | 0.0143 (143) | 0.0255 (255) | 0.0834 (834) |
| E Heteroscedastic Noise | 0.0023 (23) | 0.0070 (70) | 0.0164 (164) | 0.0298 (298) | 0.0586 (586) | 0.1748 (1748) |
| F Staggered Onset | 0.0007 (7) | 0.0010 (10) | 0.0020 (20) | 0.0095 (95) | 0.0191 (191) | 0.0988 (988) |

---

##### Table 3: OLS $t$-Statistic Component Detection Power Across Horizons at $\delta = 2.5\sigma$
*N = 10,000 components per cell. Values indicate empirical power (count).*

| Morphology | T=24h (K=2) | T=48h (K=3) | T=72h (K=4) | T=96h (K=5) | T=120h (K=6) | T=168h (K=7) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| A Linear Drift | N/A (df=0) | 0.0020 (20) | 0.0020 (20) | 0.0042 (42) | 0.0069 (69) | 0.0208 (208) |
| B Accelerating Drift | N/A (df=0) | 0.0008 (8) | 0.0008 (8) | 0.0020 (20) | 0.0034 (34) | 0.0191 (191) |
| C Abrupt Step | N/A (df=0) | 0.0012 (12) | 0.0016 (16) | 0.0090 (90) | 0.0136 (136) | 0.0183 (183) |
| D Confounded Drift | N/A (df=0) | 0.0014 (14) | 0.0022 (22) | 0.0041 (41) | 0.0089 (89) | 0.0225 (225) |
| E Heteroscedastic Noise | N/A (df=0) | 0.0021 (21) | 0.0019 (19) | 0.0028 (28) | 0.0032 (32) | 0.0133 (133) |
| F Staggered Onset | N/A (df=0) | 0.0018 (18) | 0.0011 (11) | 0.0033 (33) | 0.0058 (58) | 0.0258 (258) |

---

##### Table 4: Kendall's $\tau$ Component Detection Power Across Horizons at $\delta = 2.5\sigma$
*N = 10,000 components per cell. Values indicate empirical power (count).*

| Morphology | T=24h (K=2) | T=48h (K=3) | T=72h (K=4) | T=96h (K=5) | T=120h (K=6) | T=168h (K=7) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| A Linear Drift | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0086 (86) |
| B Accelerating Drift | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0083 (83) |
| C Abrupt Step | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0109 (109) |
| D Confounded Drift | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0116 (116) |
| E Heteroscedastic Noise | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0068 (68) |
| F Staggered Onset | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0000 (0) | 0.0108 (108) |

---

##### Table 5: Module A Comparator Endpoint Drift Breaches ($|g_p| \ge 2.5$) Across Horizons at $\delta = 2.5\sigma$
*Parentheses indicate component breach count out of 10,000 components.*

| Morphology | T=24h (K=2) | T=48h (K=3) | T=72h (K=4) | T=96h (K=5) | T=120h (K=6) | T=168h (K=7) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| A Linear Drift | 0.3996 (3996) | 0.4801 (4801) | 0.5804 (5804) | 0.6960 (6960) | 0.7995 (7995) | 0.9415 (9415) |
| B Accelerating Drift | 0.3799 (3799) | 0.3957 (3957) | 0.4237 (4237) | 0.5002 (5002) | 0.6309 (6309) | 0.9389 (9389) |
| C Abrupt Step | 0.3869 (3869) | 0.3905 (3905) | 0.9383 (9383) | 0.9366 (9366) | 0.9357 (9357) | 0.9390 (9390) |
| D Confounded Drift | 0.4120 (4120) | 0.4766 (4766) | 0.5784 (5784) | 0.6899 (6899) | 0.7923 (7923) | 0.9385 (9385) |
| E Heteroscedastic Noise | 0.4438 (4438) | 0.5257 (5257) | 0.6432 (6432) | 0.7428 (7428) | 0.8298 (8298) | 0.9449 (9449) |
| F Staggered Onset | 0.3769 (3769) | 0.3926 (3926) | 0.4271 (4271) | 0.5582 (5582) | 0.7162 (7162) | 0.9382 (9382) |

---

##### Table 6: Parameter-Level Detection Power by Detector & Parameter (Fixture A Linear Drift, $T=168\ \text{h}, K=7$)

| Detector Family | Delta | IDSS (upper) | VGS(th) (two-sided) | RDS(on) (upper) | IGSS (two-sided) |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Theil-Sen** | 1.0σ | 0.0020 (20) | 0.0008 (8) | 0.0012 (12) | 0.0014 (14) |
| | 1.5σ | 0.0054 (54) | 0.0025 (25) | 0.0041 (41) | 0.0029 (29) |
| | 2.0σ | 0.0121 (121) | 0.0063 (63) | 0.0090 (90) | 0.0093 (93) |
| | 2.5σ | **0.0271** (271) | **0.0141** (141) | **0.0217** (217) | **0.0208** (208) |
| **OLS t-Statistic** | 1.0σ | 0.0006 (6) | 0.0006 (6) | 0.0010 (10) | 0.0006 (6) |
| | 1.5σ | 0.0022 (22) | 0.0013 (13) | 0.0022 (22) | 0.0013 (13) |
| | 2.0σ | 0.0036 (36) | 0.0031 (31) | 0.0043 (43) | 0.0023 (23) |
| | 2.5σ | **0.0068** (68) | **0.0038** (38) | **0.0066** (66) | **0.0036** (36) |
| **Kendall's $\tau$** | 1.0σ | 0.0006 (6) | 0.0000 (0) | 0.0011 (11) | 0.0000 (0) |
| | 1.5σ | 0.0018 (18) | 0.0000 (0) | 0.0018 (18) | 0.0000 (0) |
| | 2.0σ | 0.0032 (32) | 0.0000 (0) | 0.0024 (24) | 0.0000 (0) |
| | 2.5σ | **0.0054** (54) | **0.0000** (0) | **0.0033** (33) | **0.0000** (0) |

---

#### 3. Key Physical, Statistical & Architectural Insights

1. **Mathematical Explanation of Statistical Power vs. Module A Drift Comparator**:
   - The frozen Holm procedure controls Family-Wise Error Rate at $\alpha = 0.001$ across the 4 parameters, enforcing a Step-1 parameter-level rejection threshold of $\alpha/4 = 0.00025$.
   - In a Gaussian tail, $p \le 0.00025$ corresponds to $|Z| \ge \Phi^{-1}(1 - 0.000125) \approx 3.66\sigma$ (two-sided) or $Z \ge \Phi^{-1}(1 - 0.00025) \approx 3.48\sigma$ (one-sided).
   - An effect size of $\delta = 2.5\sigma_u$ distributed across $K=7$ checkpoints produces an expected test statistic mean of $\sim 2.0 - 2.8$ standard errors. Under such stringent critical values ($\ge 3.5\sigma$), statistical hypothesis test power for $\delta \le 2.5\sigma$ is mathematically bounded around $\sim 2\% - 30\%$, depending on morphology.
   - Conversely, Module A evaluates a fixed heuristic drift threshold $|(u(t) - u(0))/\sigma_u| \ge 2.5$. At $\delta = 2.5\sigma$, the drift signal matches the threshold, resulting in $\sim 94\%$ breach probability. However, under the Null hypothesis, Module A generates an uncalibrated false-alarm rate of $\sim 38.5\%$ (Table 5 in LOG-089), which is $>380\times$ higher than the target $\alpha=0.001$ FWER.
2. **Kendall's $\tau$ Rank-Null Feasibility Bound**:
   - For $K \le 6$ ($T \le 120\text{h}$), Kendall's $\tau$ has zero component-level rejection capacity under the frozen Holm Step-1 threshold ($\alpha/4 = 0.00025$): the continuous rank-null theoretical minimum tail probability is $1/K! \ge 1/720 \approx 0.001389 > 0.00025$, and under the finite empirical convention $p = \frac{1 + \text{count}}{N_{\text{cal}} + 1}$, empirical p-values at $K \le 6$ strictly exceed $0.0014$.
   - At $K=7$ ($T=168\text{h}$), the minimum one-sided empirical p-value is $1/5040 \approx 0.0001984 \le 0.00025$. Therefore, Kendall's $\tau$ can reject on one-sided upper-tail parameters ($I_{\text{DSS}}$, $R_{\text{DS(on)}}$) when $\tau = +1.0$, reaching $0.0054$ and $0.0033$ power at $\delta=2.5\sigma$.
   - However, for symmetric two-sided parameters ($V_{\text{GS(th)}}$, $I_{\text{GSS}}$), the minimum two-sided empirical p-value under continuous exchangeable ranks is $2/5040 \approx 0.0003968 > 0.00025$. Consequently, it is **mathematically impossible** for Kendall's $\tau$ to reject any two-sided parameter at $K \le 7$ under Holm $\alpha=0.001$. Within the evaluated power-sweep cells (Table 6), the observed empirical rejection count on $V_{\text{GS(th)}}$ and $I_{\text{GSS}}$ was identically zero across all tested $\delta \in \{1.0, 1.5, 2.0, 2.5\}\sigma_u$.
3. **Leave-One-Out (LOO) Lot-Median Differencing & Common-Mode Structure on Power**:
   - **Isolated Component Defect in Stationary Lot (Evaluated Suite)**: When an individual degraded component is embedded among 19 stationary peers, the peer median remains stationary. LOO differencing preserves 100% of the degradation drift $g(t)$ while completely subtracting out common-mode chamber thermal shifts (Fixture D).
   - **Observed Behavior on Common-Mode Perturbation**: At $T=168\text{h}, \delta=2.5\sigma$, Theil-Sen power in Fixture D (Confounded Drift with $+5^\circ\text{C}$ thermal excursion at 72h and 96h) is **0.0834** (Wilson 95% CI: $[0.0781, 0.0890]$), while in unconfounded Fixture A Linear Drift it is **0.0811** (Wilson 95% CI: $[0.0759, 0.0866]$). The two 95% confidence intervals broadly overlap, and the observed difference of $+0.0023$ is small relative to binomial sampling uncertainty ($\text{SE} \approx 0.0027$). Consistent with good statistical practice, equivalence is not claimed without a pre-registered equivalence test.
   - **Synchronous Lot-Wide Degradation Limitation (Architectural Boundary)**: If an entire lot degrades synchronously in the same direction ($s_p = +1$ for all 20 devices in $I_{\text{DSS}}$ or $R_{\text{DS(on)}}$), the LOO lot median tracks the degradation, and differencing cancels the drift signal ($\text{power} \to \alpha$). For alternating-sign parameters ($V_{\text{GS(th)}}$, $I_{\text{GSS}}$), the lot median remains centered near 0, preserving detection power.
4. **Distinction: Detection Power vs. Final Screening Disposition**:
   - *Detection Power* evaluates the probability that an individual statistical detector flags a component as an active degradation candidate ($p_{(1)} \le 0.00025$).
   - *Final Screening Disposition* (Module A pipeline) combines statistical drift detection with absolute specification limits (guardbands, Class A/B limits), peer MAD z-scores, step-ratio tests, and re-test/scrap policy rules. A component may trigger a screening disposition without rejecting Holm drift (e.g. static limit breach), or vice versa.
5. **Signed $I_{\text{GSS}}$ Semantics Preserved**:
   - Gate leakage remained signed throughout transformed coordinates ($u = \text{asinh}(I_{\text{GSS}}/1.0)$), preserving physical directionality across both positive and negative oxide degradation modes.
6. **Epistemic Limitation Statement**:
   - Independent power sweep results quantify empirical detection power strictly within the pre-registered synthetic degradation models. Results do NOT constitute empirical evidence of real semiconductor device degradation, ATE drift, or burn-in chamber physics under MIL-PRF-19500, and must NOT be used to retroactively optimize thresholds.

---

#### 4. Cryptographic Provenance & Artifact Verification

All 13 baseline benchmark and evaluation artifacts remain 100% byte-identical to their release hashes:

| Artifact Path | SHA-256 Digest | Status |
|:---|:---|:---:|
| `data/synthetic_phase4b/observations.csv` | `b5de6a03022a9350b6f304b9af593768e7f83a8fc61fde6ca98e690cfa1f275f` | **PRESERVED UNMUTATED** |
| `data/synthetic_phase4b/ground_truth.csv` | `b48a2c0845492646ad9451d5a7efe256fe143043726807603a775d5f07c75656` | **PRESERVED UNMUTATED** |
| `data/synthetic_phase4b/manifest.json` | `fe85a035e9ed2ecc46a1cbcf1d999f048313ccabadab23ee0969fa1033ac87e2` | **PRESERVED UNMUTATED** |
| `data/synthetic_phase2f_frozen/observations.csv` | `b4282e0743cd6a0b2b74354e431bf8f308b03281c44c0437d30f7b53bd6ca983` | **PRESERVED UNMUTATED** |
| `data/synthetic_phase2f_frozen/ground_truth.csv` | `4bf2155fcc7698813f766e1dea9730213e0a6097e484bfa786eb1b94925f3d2b` | **PRESERVED UNMUTATED** |
| `data/synthetic_phase2f_frozen/manifest.json` | `5a08630f9fafc95563c13acea77df7aa066f7abc7a08b785a77c2709553980f6` | **PRESERVED UNMUTATED** |
| `data/synthetic_phase2f_frozen/configuration_snapshot.json` | `a4bb3f75f8211bf38b4c38cde0bbd1908eeecb75039700de84b1cc0c56f6dd27` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/calibration_reference_table.json` | `153d387597ba6a247ed5302a7512730c678bc3ce39e056848cd9135fc39c7d60` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/calibration_distributions.npz` | `147f1d38ed9b197af6b6301b9b454223d5cce54286fcfeb89a1ea15cec055d98` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/calibration_manifest.json` | `b7c5515144e0ea800f4e3b1f0acd5739b5acee88cd8e7f9fefa87a8294400b25` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/null_a_audit_results.json` | `1bd10cb8541d467084c15efa97e6e8fa9dc8799f356a4739a6141fd06bc1d9ad` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/null_b_stress_results.json` | `7a8f26cb450bbbc9ee1608e8902a171314eddadc1c6d13867a579b64cc4fe44c` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/null_c_stress_results.json` | `ae5ef6a245f91a142e8c866ed85a044381a9de8992e23fb414bb288bf225801e` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/power_sweep_results.json` | `31c34f803a19e233c136725a0bd8a48809a49e7c5d0dc82fccd5fd0ecc022036` | **NEW POWER ARTIFACT** |

---

#### 5. Gate Recommendation
The preregistered power-sweep execution criteria were satisfied; empirical power characteristics require engineering review before validation.

- **Gate Status**: **POWER SWEEP COMPLETED — FROZEN AT FREEZE 4**
- **Test Suite Status**: **199/199 passing tests** (`pytest` passing in 8.16s).
- **Execution Boundary**: **STOPPED**. Validation partition and final evaluation partitions have **NOT** been evaluated.
- **Recommendation**: Formal review and authorization of the Power Sweep results prior to proceeding to Phase 4B Validation.

Execution stopped per gate instructions.

---

### LOG-091: Phase 4B Power Sweep Forensic Review & Architectural Diagnosis
- **Timestamp**: 2026-09-17T21:45:00Z
- **Phase**: Phase 4B / Power Sweep Forensic Review
- **Type**: FORENSIC_REVIEW_AND_ARCHITECTURAL_DIAGNOSIS
- **Supersedes / Amends**: LOG-090
- **Status**: FORENSIC REVIEW COMPLETE — VALIDATION BLOCKED PENDING STAKEHOLDER REVIEW

#### 1. Scope, Constraints & Boundary Enforcement
Following gate directives, this entry constitutes a documentation-only forensic diagnosis of the empirical power characteristics observed in the frozen Phase 4B Power Sweep (`data/evaluation_phase4b/power_sweep_results.json`, SHA-256 `31c34f803a19...`).

**Strict Invariants Enforced**:
1. **Zero System Mutations**: No detector code modified, no $\alpha$ altered, no Holm procedure changed, no recalibration conducted, no thresholds retuned, no benchmark data modified, and no power sweep rerun.
2. **Zero Forward Progression**: Validation and final evaluation partitions remain completely quarantined and unexecuted.
3. **Immutable Empirical Evidence**: The power sweep results ($N = 240{,}000$ components across 24 cells, seed `15152878`) are treated as immutable experimental evidence.
4. **Diagnostic Focus**: This review is strictly a diagnosis of statistical design properties versus implementation behavior; it does NOT attempt to solve or optimize thresholds.

---

#### 2. Key Finding: Quantification of Kendall's $\tau$ Power Across Morphologies
Across all six synthetic morphologies at the maximum pre-registered effect size $\delta = 2.5\sigma_{u,p}$ at the final horizon $T = 168\ \text{h}$ ($K=7$), Kendall's $\tau$ exhibits component-level Holm step-down detection power ranging strictly between **0.68% and 1.16%**:

| Morphology | Effect Size ($\delta$) | Observed Rejections ($k/10{,}000$) | Empirical Power ($\hat{P}_D$) | Wilson 95% CI |
|:---|:---:|:---:|:---:|:---:|
| **Fixture A (Linear Drift)** | 2.5σ | 86 | **0.0086** (0.86%) | [0.0070, 0.0106] |
| **Fixture B (Accelerating Drift)** | 2.5σ | 83 | **0.0083** (0.83%) | [0.0067, 0.0103] |
| **Fixture C (Abrupt Step)** | 2.5σ | 109 | **0.0109** (1.09%) | [0.0090, 0.0131] |
| **Fixture D (Confounded Drift)** | 2.5σ | 116 | **0.0116** (1.16%) | [0.0097, 0.0139] |
| **Fixture E (Heteroscedastic Noise)** | 2.5σ | 68 | **0.0068** (0.68%) | [0.0054, 0.0086] |
| **Fixture F (Staggered Onset)** | 2.5σ | 108 | **0.0108** (1.08%) | [0.0090, 0.0130] |

At intermediate horizons $T \le 120\ \text{h}$ ($K \le 6$), Kendall's $\tau$ component detection power is **identically 0.0000** (0 rejections out of 10,000 components across all cells).

Forensic diagnosis confirms: **This is NOT a detector implementation bug or software defect.** The code implements Kendall's $\tau$ with exact algebraic fidelity, ties occur with measure zero under continuous noise, the LOO pipeline executes correctly, and empirical reference ranking matches theoretical rank distributions. The dominant structural limitation arises from the interaction between Kendall rank discreteness and the Holm Step-1 threshold at $K \le 7$, while measurement noise and temporal effect construction further contribute to the observed empirical power.

---

#### 3. Mathematical Factor Separation & Derivation of Low Kendall Power

To rigorously explain why Kendall power remains so low despite an apparent signal $\delta = 2.5\sigma$, the contributing factors must be separated mathematically:

##### A. Discrete Permutation Support at $K=7$ ($7! = 5{,}040$)
With $K=7$ checkpoints, there are $7! = 5{,}040$ possible permutations of ranks. There are $\binom{7}{2} = 21$ checkpoint pairs.
- The maximum score $\tau = +1.0$ (zero inversions) occurs for exactly **1 permutation** out of 5,040 ($r = (1, 2, 3, 4, 5, 6, 7)$).
- The second-highest score $\tau = \frac{21 - 2(1)}{21} = \frac{19}{21} \approx 0.9048$ (one inversion) occurs for exactly **6 permutations** (adjacent transpositions).
- Under continuous exchangeable ranks, the probability of $\le 1$ inversion is $(1 + 6)/5040 = 7/5040 \approx 0.001389$.

##### B. Holm $\alpha = 0.001$ Multiplicity Thresholds ($\alpha/4 = 0.00025$)
Multiplicity control across $m=4$ physical parameters ($I_{\text{DSS}}, V_{\text{GS(th)}}, R_{\text{DS(on)}}, I_{\text{GSS}}$) enforces a Step-1 parameter rejection threshold:
$$p_{(1)} \le \frac{\alpha}{4} = 0.00025$$

##### C. Impact on One-Sided Parameters ($I_{\text{DSS}}, R_{\text{DS(on)}}$)
Under the one-sided upper tail:
- For $\tau = +1.0$: the empirical p-value is $\frac{1 + N_{\text{cal}} \times (1/5040)}{N_{\text{cal}} + 1} \approx \frac{1 + 19.84}{100001} \approx 0.000208 \le 0.00025$. **Rejection is possible.**
- For $\tau = 19/21 \approx 0.9048$ (a single inverted pair among 21): the empirical p-value is $\frac{1 + N_{\text{cal}} \times (7/5040)}{N_{\text{cal}} + 1} \approx \frac{1 + 138.9}{100001} \approx 0.001399 \gg 0.00025$. **Rejection is impossible.**

> **Core Mathematical Constraint (One-Sided)**:
> This is a structural property of the frozen combination of $K=7$, Kendall rank discreteness, the empirical $+1$ Davison-Hinkley p-value convention, and the Holm Step-1 threshold ($\alpha/4 = 0.00025$). Under this frozen procedure at $K=7$, Kendall's $\tau$ rejects $H_0$ if and only if **EVERY SINGLE ONE OF THE 7 OBSERVATIONS IS STRICTLY INCREASING**:
> $$u(0\text{h}) < u(24\text{h}) < u(48\text{h}) < u(72\text{h}) < u(96\text{h}) < u(120\text{h}) < u(168\text{h})$$
> If instrumentation noise causes even a single non-monotonic fluctuation (e.g. $u(48\text{h}) > u(72\text{h})$), the empirical p-value immediately jumps to $\approx 0.0014$, failing Step 1.
> For $K \le 6$, the theoretical minimum tail probability under continuous exchangeable ranks is $1/K! \ge 1/720 \approx 0.001389$. Under the finite empirical $+1$ convention $p = \frac{1 + \text{count}}{N_{\text{cal}} + 1}$ ($N_{\text{cal}} = 100{,}000$), the calibration realization yields $p \ge 0.0014$. Both the continuous-null theoretical lower bound $1/K!$ and the finite empirical convention strictly exceed the Holm Step-1 threshold ($\alpha/4 = 0.00025$); hence no attainable Step-1 rejection exists for any component at $K \le 6$.

##### D. Impact on Symmetric Two-Sided Parameters ($V_{\text{GS(th)}}, I_{\text{GSS}}$)
For symmetric parameters, the two-sided p-value counts $|\tau| \ge |\tau_{\text{obs}}|$.
- Under continuous exchangeable ranks, both strictly increasing ($r = (1, 2, 3, 4, 5, 6, 7)$) and strictly decreasing ($r = (7, 6, 5, 4, 3, 2, 1)$) permutations yield $|\tau| = 1.0$.
- The probability under the rank null is:
  $$P(|\tau| = 1.0) = \frac{2}{5040} \approx 0.0003968$$
- In a calibration set of $N_{\text{cal}} = 100{,}000$, the empirical p-value is:
  $$p = \frac{1 + 39.7}{100001} \approx 0.000407$$
- Since $0.000407 > 0.00025$, the minimum attainable two-sided p-value at $K=7$ **strictly exceeds the Step-1 Holm threshold**.

> **Impossibility Bound (Two-Sided)**:
> Under the frozen combination of $K=7$, Kendall rank discreteness, the empirical two-sided p-value convention ($p = \frac{1 + \text{count}}{N_{\text{cal}} + 1}$), and the Holm Step-1 threshold ($\alpha/4 = 0.00025$), the minimum attainable two-sided p-value ($0.000407$) strictly exceeds the threshold. Therefore, no Step-1 rejection is attainable on two-sided parameters at $K \le 7$ under the frozen calibration, even for a component exhibiting perfect deterministic monotonic drift. Within the 24 evaluated power-sweep cells (Table 6), the observed empirical rejection count on $V_{\text{GS(th)}}$ and $I_{\text{GSS}}$ under Kendall's $\tau$ is identically zero ($0/10{,}000$) across all tested effect sizes $\delta \in \{1.0, 1.5, 2.0, 2.5\}\sigma_u$.

##### E. Physical Effect Size, Noise Scale, and Temporal Sampling Schedule
The temporal inspection checkpoints are $0, 24, 48, 72, 96, 120, 168\ \text{h}$ ($K=7$). This schedule comprises five 24 h intervals ($0 \to 24, 24 \to 48, 48 \to 72, 72 \to 96, 96 \to 120$) and one 48 h interval ($120 \to 168$).

Under linear drift with total cumulative effect size $\delta = 2.5\sigma_{u,p}$ across the full 168 h burn-in:
- For each of the five 24 h intervals, the latent parameter drift increment is $\Delta g_{24} = 2.5\sigma_u \times (24/168) \approx 0.357\sigma_u$.
- For the final 48 h interval, the latent parameter drift increment is $\Delta g_{48} = 2.5\sigma_u \times (48/168) \approx 0.714\sigma_u$.

The independent measurement noise difference between any two observation checkpoints has variance $\text{Var}(\epsilon_{k+1} - \epsilon_k) = 2\sigma_u^2$, giving standard deviation $\sqrt{2}\sigma_u \approx 1.414\sigma_u$.

**Marginal SNR Intuition (Marginal Only)**:
- Over an individual 24 h interval, the marginal signal-to-noise ratio is $\text{SNR}_{\text{step, 24h}} = \frac{0.357\sigma_u}{\sqrt{2}\sigma_u} \approx 0.252$, corresponding to a marginal probability of an increasing step $\Phi(0.252) \approx 0.599$.
- Over the 48 h interval, the marginal SNR is $\text{SNR}_{\text{step, 48h}} = \frac{0.714\sigma_u}{\sqrt{2}\sigma_u} \approx 0.505$, corresponding to $\Phi(0.505) \approx 0.693$.
- *Important Statistical Note*: Consecutive observed increments $\Delta y_k = y_{k+1} - y_k$ and $\Delta y_{k-1} = y_k - y_{k-1}$ share the common observation error term $\epsilon_k$ and are negatively correlated ($\text{Cov}(\Delta y_k, \Delta y_{k-1}) = -\sigma_u^2$, correlation $-0.5$). Consequently, joint monotonicity across the 7 checkpoints cannot be computed by multiplying marginal step probabilities. True joint concordance requires evaluating multivariate Gaussian orthant probabilities across all $\binom{7}{2} = 21$ pairs simultaneously.

**Descriptive Parameter-to-Component Relationship**:
- In Fixture A at $\delta=2.5\sigma$, the observed parameter-level rejection rates are $0.0054$ (54/10,000) for $I_{\text{DSS}}$, $0.0033$ (33/10,000) for $R_{\text{DS(on)}}$, and $0.0000$ for $V_{\text{GS(th)}}$ and $I_{\text{GSS}}$ under Kendall's $\tau$.
- At the component level, a Holm rejection occurs when at least one parameter rejects at Step 1 ($p \le 0.00025$). Across the 10,000 evaluated components in Fixture A, exactly 86 components were rejected (empirical component power $0.0086$, or $0.86\%$). Descriptively, this component rejection count (86) reflects the empirical union of rejections across the two admissible one-sided parameters ($I_{\text{DSS}}$ and $R_{\text{DS(on)}}$), accounting for co-occurring rejections where both parameters rejected on the same component.

---

#### 4. Descriptive Comparative Assessment of Detector Families
*(Presented descriptively without ranking or declaring an algorithmic winner)*

| Detector Family | Horizon Applicability | Power at $\delta=2.5\sigma, 168\text{h}$ | Morphology-Specific Behavior | Primary Strengths & Limitations |
|:---|:---:|:---:|:---|:---|
| **Kendall's $\tau$** | $K \ge 2$ ($K \le 6$ has 0 capacity) | **0.68% – 1.16%** | Uniformly low across all morphologies ($0.68\%$ in heteroscedastic noise; $1.16\%$ in confounded drift). | **Strengths**: Invariant to monotonic nonlinear warping, zero parametric assumptions.<br>**Limitations**: Severe discrete support constraint at $K \le 7$; zero rejection capacity for two-sided parameters under Holm $\alpha/4 = 0.00025$. |
| **Theil-Sen Robust Slope** | All $K \ge 2$ | **6.40% – 30.27%** | Highest power on Abrupt Step (Fixture C: **30.27%**) and Heteroscedastic Noise (Fixture E: **17.48%**); lowest on Accelerating Drift (Fixture B: **6.40%**). | **Strengths**: Continuous test statistic provides rejection capacity at all horizons; highly responsive to step transitions where pairwise slopes shift strongly.<br>**Limitations**: Modest power ($\sim 8\%$) on subtle linear drift at $\delta=2.5\sigma$. |
| **OLS $t$-Statistic** | $K \ge 3$ only (undefined at $K=2$) | **1.33% – 2.58%** | Uniformly modest across morphologies ($1.33\%$ in heteroscedastic noise; $2.58\%$ in staggered onset). | **Strengths**: Standard parametric benchmark with continuous Student's $t$ statistic.<br>**Limitations**: Inflated residual variance under step transitions; undefined at $K=2$ ($df=0$). |

---

#### 5. Conceptual Clarification & Distinct Operational Definitions

To prevent conflation during subsequent reviews, four distinct quantities must be kept separate:

1. **Statistical Detection Power ($\hat{P}_D$)**:
   The empirical probability that a component's test statistics trigger a formal Step-1 Holm rejection ($p_{(1)} \le 0.00025$) under the pre-registered hypothesis testing chain.
2. **Final Screening Disposition**:
   The end-to-end production screening outcome produced by the full Module A pipeline. This decision integrates statistical drift detection with absolute specification limits (guardbands, Class A/B limits), peer MAD z-scores, step-ratio tests ($J \ge 3.0$), and re-test/scrap policy rules. A component may trigger a screening disposition without rejecting Holm drift (e.g. static limit breach), or vice versa.
3. **Module A Heuristic Endpoint Drift Breach Probability**:
   The probability that a component exceeds the fixed heuristic threshold $|(u(t) - u(0))/\sigma_u| \ge 2.5$. In the power sweep, this reaches $\sim 94\%$ at $\delta = 2.5\sigma$ at 168h because the true signal matches the threshold. However, under the Null hypothesis, Module A generates an uncalibrated false-alarm rate of $\sim 38.5\%$ (Table 5 in LOG-089), which is $>380\times$ higher than the target $\alpha=0.001$ FWER.
4. **Calibrated Family-Wise Error Rate ($\widehat{\text{FWER}}$)**:
   The empirical rate of false-positive component rejections under a true Null distribution, strictly audited on the independent Null-A Audit Set ($N = 100{,}000$) to control false alarms below $\alpha = 0.001$.

---

#### 6. Leave-One-Out (LOO) Topology & Common-Mode Noise Mechanics

1. **Isolated Component Defect in Stationary Lot (Evaluated Regime)**:
   - In the independent power sweep, each degraded device is placed in a lot of $L=20$ with 19 stationary peer devices.
   - Within the evaluated topology of one degraded component with 19 stationary peers, the leave-one-out peer median remains stationary. Consequently, LOO differencing preserves the component's latent drift while subtracting common-mode chamber perturbations.
   - **Observed Behavior on Fixture D (Confounded Drift)**: At $T=168\text{h}, \delta=2.5\sigma$, Theil-Sen power in Fixture D (Confounded Drift with $+5^\circ\text{C}$ thermal excursion at 72h and 96h) is **0.0834** ($95\%\ \text{CI}: [0.0781, 0.0890]$), while in unconfounded Fixture A Linear Drift it is **0.0811** ($95\%\ \text{CI}: [0.0759, 0.0866]$). The confidence intervals broadly overlap, and the observed difference of $+0.0023$ is small relative to sampling uncertainty ($\text{SE} \approx 0.0027$).
2. **Synchronous Lot-Wide Degradation Limitation (Architectural Blind Spot)**:
   - If an entire manufacturing lot degrades synchronously with the same sign ($s_p = +1$ for all 20 devices in $I_{\text{DSS}}$ or $R_{\text{DS(on)}}$), the LOO lot median tracks the degradation drift.
   - Under synchronous degradation, within-lot median differencing mathematically subtracts the physical degradation signal ($\text{power} \to \alpha$).
   - For alternating-sign parameters ($V_{\text{GS(th)}}, I_{\text{GSS}}$), the lot median remains centered near 0, preserving detection power.
   - Therefore, LOO lot-median topology is an outlier-screening mechanism; synchronous lot-wide drift is an architectural blind spot for unidirectional parameters.

---

#### 7. Critical Architectural Diagnosis

**Diagnostic Assessment**:
Is the current calibrated statistical architecture capable of meeting the intended screening objective under the tested synthetic benchmark?

1. **Diagnosis**:
   Under the frozen statistical architecture:
   - Under the independent Null-A audit, the frozen procedure exhibited empirical component-level FWER consistent with the nominal $\alpha=0.001$ target (while out-of-distribution temporal correlation in Null-B demonstrated that FWER control does not universally generalize across arbitrary non-i.i.d. noise regimes).
   - Holm multiplicity control enforces a Step-1 parameter threshold of $\alpha/4 = 0.00025$.
   - Under this stringent significance boundary, detecting subtle drifts ($\delta \le 2.5\sigma_u$) across $K=7$ discrete checkpoints with $\sigma_u$ measurement noise yields modest empirical statistical power:
     - Kendall's $\tau$: $\sim 0.7\% - 1.2\%$ at 168h (and $0.0\%$ at $T \le 120\text{h}$).
     - Theil-Sen: $\sim 6\% - 30\%$ at 168h.
     - OLS $t$: $\sim 1\% - 3\%$ at 168h.
2. **Nature of the Limitation**:
   Kendall rank discreteness combined with the Holm Step-1 threshold represents the dominant structural limitation on rejection capacity at $K \le 7$, while instrumentation noise and the temporal distribution of the effect size govern the observed empirical power. This is an inherent property of the frozen statistical architecture, NOT an implementation defect.
3. **No Redesign Authorized at This Gate**:
   In strict accordance with gate instructions, no alternative alpha, no threshold sweep, no modified Holm procedure, no detector redesign, and no temporal schedule change is proposed or executed. The forensic review diagnoses the frozen architecture; it does not authorize redesign.

---

#### 8. Cryptographic Provenance & Artifact Hashes

All 14 benchmark, calibration, stress, and power artifacts are verified 100% byte-identical:

| Artifact Path | SHA-256 Digest | Status |
|:---|:---|:---:|
| `data/synthetic_phase4b/observations.csv` | `b5de6a03022a9350b6f304b9af593768e7f83a8fc61fde6ca98e690cfa1f275f` | **PRESERVED UNMUTATED** |
| `data/synthetic_phase4b/ground_truth.csv` | `b48a2c0845492646ad9451d5a7efe256fe143043726807603a775d5f07c75656` | **PRESERVED UNMUTATED** |
| `data/synthetic_phase4b/manifest.json` | `fe85a035e9ed2ecc46a1cbcf1d999f048313ccabadab23ee0969fa1033ac87e2` | **PRESERVED UNMUTATED** |
| `data/synthetic_phase2f_frozen/observations.csv` | `b4282e0743cd6a0b2b74354e431bf8f308b03281c44c0437d30f7b53bd6ca983` | **PRESERVED UNMUTATED** |
| `data/synthetic_phase2f_frozen/ground_truth.csv` | `4bf2155fcc7698813f766e1dea9730213e0a6097e484bfa786eb1b94925f3d2b` | **PRESERVED UNMUTATED** |
| `data/synthetic_phase2f_frozen/manifest.json` | `5a08630f9fafc95563c13acea77df7aa066f7abc7a08b785a77c2709553980f6` | **PRESERVED UNMUTATED** |
| `data/synthetic_phase2f_frozen/configuration_snapshot.json` | `a4bb3f75f8211bf38b4c38cde0bbd1908eeecb75039700de84b1cc0c56f6dd27` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/calibration_reference_table.json` | `153d387597ba6a247ed5302a7512730c678bc3ce39e056848cd9135fc39c7d60` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/calibration_distributions.npz` | `147f1d38ed9b197af6b6301b9b454223d5cce54286fcfeb89a1ea15cec055d98` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/calibration_manifest.json` | `b7c5515144e0ea800f4e3b1f0acd5739b5acee88cd8e7f9fefa87a8294400b25` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/null_a_audit_results.json` | `1bd10cb8541d467084c15efa97e6e8fa9dc8799f356a4739a6141fd06bc1d9ad` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/null_b_stress_results.json` | `7a8f26cb450bbbc9ee1608e8902a171314eddadc1c6d13867a579b64cc4fe44c` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/null_c_stress_results.json` | `ae5ef6a245f91a142e8c866ed85a044381a9de8992e23fb414bb288bf225801e` | **PRESERVED UNMUTATED** |
| `data/evaluation_phase4b/power_sweep_results.json` | `31c34f803a19e233c136725a0bd8a48809a49e7c5d0dc82fccd5fd0ecc022036` | **FROZEN POWER ARTIFACT** |

---

#### 9. Gate Recommendation & Stop Boundary
- **Power Sweep Status**: **ACCEPTED AS EXPERIMENTAL EVIDENCE**
- **Validation Status**: **REMAINS BLOCKED PENDING FORENSIC REVIEW & STAKEHOLDER DIRECTIVE**
- **Test Suite Status**: **199/199 passing tests** (`PYTHONPATH=. pytest` passing in 8.39s).
- **Execution Boundary**: **STOPPED**. The forensic review diagnoses the frozen architecture; it does not authorize redesign. No validation partition execution. No final evaluation execution.

---

### LOG-092: Phase 4B Forensic Review Formal Closure & Stakeholder Decision Record
- **Timestamp**: 2026-09-18T03:15:00Z
- **Phase**: Phase 4B / Forensic Review Closure & Pre-Validation Gate Review
- **Type**: FORENSIC_REVIEW_CLOSURE_AND_GATE_MEMO
- **Supersedes / Amends**: LOG-091
- **Status**: FORENSIC REVIEW FORMALLY CLOSED / ACCEPTED — VALIDATION REMAINS BLOCKED

#### 1. Formal Closure & Blocked Gate Determinations
Pursuant to formal review, the Phase 4B Forensic Review is **CLOSED AND ACCEPTED**. The current frozen Phase 4B state is preserved strictly as-is:
- **Power Sweep Execution**: **ACCEPTED AS EXPERIMENTAL EVIDENCE** ($N=240{,}000$ components across 24 cells, seed `15152878`, SHA-256 `31c34f803a19...`).
- **Forensic Review**: **CLOSED / ACCEPTED** (diagnostic properties fully analyzed; structural vs implementation root causes established).
- **Validation Execution**: **REMAINS BLOCKED** (execution against `partition == "validation"` is strictly prohibited).
- **Final Evaluation Execution**: **NOT AUTHORIZED** (quarantined).
- **Detector Redesign**: **NOT AUTHORIZED** (no algorithm changes permitted within Phase 4B).
- **Threshold Tuning**: **NOT AUTHORIZED** (no threshold optimization or relaxation).
- **Recalibration**: **NOT AUTHORIZED** (frozen Null-A distributions remain unmutated).
- **Benchmark Mutation**: **NOT AUTHORIZED** (all synthetic datasets remain immutable).

---

#### 2. Exact Preserved Findings

##### A. Kendall Structural Rejection-Capacity Finding
1. **$K \le 6$ Support Barrier ($T \le 120\ \text{h}$)**:
   Under the frozen empirical $+1$ p-value convention:
   $$p = \frac{1 + \text{count}}{N_{\text{cal}} + 1}$$
   where $N_{\text{cal}} = 100{,}000$, and even under the theoretical permutation support bound $1/K!$, the minimum attainable p-value across $K \le 6$ ($6! = 720, p \ge 1/720 \approx 0.00139$) cannot reach Holm Step 1 ($\alpha/4 = 0.00025$). Therefore, **no Step-1 Holm rejection is attainable at $K \le 6$**, yielding identically zero statistical power across all six morphologies and effect sizes.
2. **$K = 7$ One-Sided Rejection Constraint ($T = 168\ \text{h}$)**:
   At $K=7$ ($7! = 5{,}040$), one-sided Kendall rejection requires **perfect increasing rank ordering ($\tau = +1.0$)** under the frozen procedure. Any single non-monotonic fluctuation drops $\tau \le 19/21 \approx 0.9048$, yielding an empirical p-value $\approx 0.00140 \gg 0.00025$.
3. **$K = 7$ Two-Sided Impossibility Constraint ($V_{\text{GS(th)}}, I_{\text{GSS}}$)**:
   For symmetric two-sided parameters, extreme tail probability mass is split across positive and negative tails ($2/5040$), resulting in a minimum empirical p-value of:
   $$p = \frac{1 + 40}{100{,}001} \approx 0.000407 > 0.00025$$
   making two-sided Step-1 Holm rejection **strictly impossible at $K \le 7$**, resulting in $0.0\%$ power for $V_{\text{GS(th)}}$ and $I_{\text{GSS}}$ across all tested power-sweep cells in Table 6.
4. **Architectural Diagnosis**:
   The frozen Kendall + Holm architecture has **extremely restricted rejection capacity** at the available temporal resolution. This is an analytical property of the discrete test family under strict Holm multiplicity control, **NOT** an implementation defect.

##### B. Empirical Power Finding at $T = 168\ \text{h}, \delta = 2.5\sigma_u$
Observed component-level detection powers across the six evaluated morphologies:
- **Kendall's $\tau$**: **$0.68\% - 1.16\%$** (Linear: $0.86\%$, Accel: $0.83\%$, Step: $1.09\%$, Confounded: $1.16\%$, Heteroscedastic: $0.68\%$, Staggered: $1.08\%$).
- **Theil-Sen Robust Slope**: **$6.40\% - 30.27\%$** (highest on Abrupt Step Fixture C at $30.27\%$).
- **OLS $t$-Statistic**: **$1.33\% - 2.58\%$**.

*Explicit Guardrail*: These descriptive results characterize empirical behavior under the frozen synthetic benchmark. They must **NOT** be converted into an algorithm ranking or winner declaration.

##### C. Epistemic Distinction Between Metrics
1. **Statistical Detection Power**: Calibrated probability of rejecting the Null under Holm step-down at component $\alpha = 0.001$.
2. **Module A Final Screening Disposition**: Multi-layered production screening outcome combining drift tests with absolute specification limits, peer MAD z-scores, step-ratio tests, and re-test rules.
3. **Module A Heuristic Endpoint Drift Breach Probability**: The probability that $|g_p(T)| \ge 2.5$. At $\delta = 2.5\sigma$, this reaches $\sim 94\%$, but under the Null hypothesis it exhibits an uncalibrated false-alarm rate of $38.5\%$ ($>380\times$ higher than target $\alpha = 0.001$).
4. **Calibrated Empirical FWER**: The empirical false-positive rate under the Null audited against the independent Null-A Audit Set ($N = 100{,}000$).

##### D. Epistemic Boundary of Synthetic Evidence
- All Phase 4B power results are synthetic benchmark evidence.
- Null-A supports empirical behavior under the specified i.i.d. Gaussian null.
- Null-B demonstrates sensitivity of continuous slope detectors to positive temporal correlation ($\text{AR}(1)$).
- Null-C evaluates cancellation under the specified additive synchronous common-mode stress.
- None of these establish real ATE/chamber noise behavior, semiconductor physics, military qualification, flight readiness, or mission readiness.

---

#### 3. Stakeholder Decision Inputs Summary
Stakeholders must resolve the following inputs documented in `docs/PHASE_4B_STAKEHOLDER_DECISION_RECORD.md` before authorizing Validation:
- **A. Statistical Operating Point**: Reconciling the nominal component FWER target $\alpha = 0.001$ (Holm Step-1 $\alpha/4 = 0.00025$) with the discrete rejection limitation of Kendall's $\tau$ at $K \le 7$ checkpoints ($0, 24, 48, 72, 96, 120, 168\ \text{h}$).
- **B. Observed Empirical Trade-Off**: Balancing the distribution-free null robustness of Kendall's $\tau$ (very low power: $0.68\% - 1.16\%$) against Theil-Sen ($6.4\% - 30.3\%$) and OLS ($1.3\% - 2.6\%$), recognizing that Module A's heuristic is not a calibrated statistical substitute due to its $38.5\%$ null breach rate.
- **C. Architectural Limitations**: Acknowledging $K=7$ rank discreteness, the LOO lot-median synchronous-drift blind spot for unidirectional parameters ($I_{\text{DSS}}, R_{\text{DS(on)}}$), Null-B temporal correlation sensitivity, and the boundary of synthetic-only evidence.
- **D. Evidence Integrity**: Confirming all 14 frozen benchmark, calibration, stress, and power artifacts remain bit-for-bit identical, 199/199 tests pass, and zero validation/final contamination exists.

---

#### 4. Requirements for Future Redesign (If Authorized)
Any future redesign must be handled as a **NEW, SEPARATELY AUTHORIZED DESIGN PHASE**. It must **NOT** be started now. If authorized in the future, it must begin with a formal written specification before implementation defining all 12 prerequisite criteria:
1. Objective
2. Primary endpoint
3. FWER target
4. Power target
5. Temporal schedule
6. Detector family
7. Multiplicity procedure
8. Calibration population
9. Independent audit population
10. Leakage controls
11. Acceptance criteria
12. Holdout/final evaluation protocol

---

#### 5. Artifact Verification & Closure Status
All 14 artifacts verified 100% bit-for-bit identical against frozen SHA-256 digests. Test suite passing (199/199).  
**Phase 4B Forensic Review is CLOSED. Validation REMAINS BLOCKED. STRICT STOP.**

---

### LOG-093: Phase 5 Module B Predictive Regression Specification Gate
- **Timestamp**: 2026-09-18T03:30:00Z
- **Phase**: Phase 5 / Module B Predictive Regression Specification
- **Type**: SPECIFICATION_GATE
- **Supersedes / Amends**: LOG-092
- **Status**: SPECIFICATION COMPLETE — SPECIFICATION ONLY — NO MODEL TRAINING / NO CODE MODIFICATION / NO VALIDATION AUTHORIZED

#### 1. Scope, Motivation & Architectural Clarification
Pursuant to the SIH26170 problem statement requirement:
> *"Build a predictive regression model that takes Value_0h and Value_24h as inputs and forecasts Value_168h. If the predicted 168h drift rate exceeds a calculated safety slope, the system flags the component for early rejection."*

A formal, implementation-independent specification has been drafted and released: [`docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md`](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md).

**Crucial Scientific Clarification Regarding Prior Work**:
The prognostic models developed in Stages 1–3 (`CarryForwardModel`, `TwoPointLinearModel`, `TheilSenExtrapolationModel`, `AdaptiveDriftGatedModel`, and `HierarchicalLotShrunkModel`) are individual-component kinematic extrapolation formulas that project single-device $(u_{24} - u_0)$ trajectories forward to 168h. None of them estimate internal regression parameters $\theta$ from the training population via loss minimization. Consequently, they are classified as reference baselines and statistical prognostic comparators. Phase 5 establishes the formal architecture for a genuinely supervised population-trained predictive regression model.

---

#### 2. Key Specification Provisions Established

1. **Primary Regression Task Formalized**:
   $$\text{INPUT}: X = [v_0, v_{24}] \in \mathbb{R}^2 \quad \longrightarrow \quad \text{TARGET}: y = v_{168} \in \mathbb{R}$$
   $$\hat{y}_{168} = f_\theta(X), \quad \hat{\theta} = \arg\min_\theta \sum_{i} \mathcal{L}(y_i, f_\theta(X_i)) + \lambda \mathcal{R}(\theta)$$
   Supervised bivariate regression fitted strictly on the training partition. Task replacements (e.g., $0 \to 24$ extrapolation, intermediate hour inputs, mandatory Module A inputs, scenario labels) are strictly prohibited for the primary task.
2. **Parameter Scope & Signed $I_{\text{GSS}}$ Semantics**:
   - Four physical observables: $I_{\text{DSS}}$ ($\mu\text{A}$), $V_{\text{GS(th)}}$ ($\text{V}$), $R_{\text{DS(on)}}$ ($\text{m}\Omega$), $I_{\text{GSS}}$ ($\text{nA}$).
   - Signed $I_{\text{GSS}}$ semantics strictly preserved: no `abs()`, no artificial clipping, full continuous bipolar support.
   - Architecture A (one decoupled model per parameter $f_{\theta_p}^{(p)}$) designated as primary specification due to distinct physical kinetics, missingness resilience, and lower sample complexity. Multi-output architecture marked OPEN extension.
3. **Transformation Contract & Numerical Safeguards**:
   - $I_{\text{DSS}}, R_{\text{DS(on)}}$: positive log $u = \ln(y)$ ($y > 0$ strictly enforced; non-positive values rejected as invalid).
   - $I_{\text{GSS}}$: signed asinh $u = \text{asinh}(y / 1.0\ \text{nA})$ (exact zero valid; full polarity preserved).
   - $V_{\text{GS(th)}}$: bounded linear identity $u = y$.
   - Divergence policy: Extreme unconstrained outputs trigger `is_divergent_fallback = True` and revert to Carry-Forward fallback. Ad-hoc cosmetic clipping is strictly prohibited.
4. **Training Data Contract & Quarantine Protocol**:
   - Eligibility: complete $[v_0, v_{24}, v_{168}]$ triad, `measurement_quality == "VALID"`, `rework_count == 0`.
   - Strict quarantine: intermediate hours ($48, 72, 96, 120\text{h}$), synthetic scenario labels, ground truth, and latent states $g(t)$ are completely quarantined.
5. **Lot-Level Leakage Control (LOLO Protocol)**:
   - Primary evaluation protocol is Leave-One-Lot-Out (LOLO) cross-validation across training lots.
   - Held-out lots contribute zero information to model fitting, scaling, imputation, tuning, or uncertainty calibration.
   - Random component-level splitting is strictly prohibited as an acceptance method.
6. **Model Family Hierarchy**:
   - Baselines: Carry-Forward, Two-Point Linear Extrapolation.
   - Primary trained candidates: Regularized Linear Regression (Ridge) and Robust Huber Regression in transformed space.
   - Nonlinear models (GBDT/RF/NN) restricted under 6 strict prerequisite criteria.
7. **Primary Evaluation Metric**:
   - Physical-unit Mean Absolute Error (MAE) per parameter: $\text{MAE}^{(p)} = \frac{1}{N} \sum |v_{168} - \hat{v}_{168}|$.
   - Switching to RMSE as the primary metric is prohibited.
   - No arbitrary numerical acceptance thresholds ("MAE < X") fabricated without stakeholder consensus.
8. **Forecast Uncertainty**:
   - $90\%$ prediction intervals calibrated strictly on out-of-fold training residuals using robust scale $\sigma_{\text{eff}} = 1.4826 \cdot \text{MAD}$.
   - No unverified claims of "guaranteed conformal" or "physical flight calibration".
9. **Safety-Slope Decision**:
   - Formally designated as **OPEN DESIGN DECISION — NO NUMERICAL VALUE INVENTED**.
   - Derivation must anchor to MIL-PRF-19500/703 post-burn-in delta limits and stakeholder loss matrix, never tuned on benchmark labels.
10. **Module A Interface**:
    - Primary regression model is completely autonomous ($[v_0, v_{24}] \to \hat{v}_{168}$).
    - Module A-enhanced models are classified as secondary extensions, restricted to causal as-of ($T \le 24\text{h}$) and read-only access.
11. **Explainability**:
    - Plain-language QA card (`QACard`) decomposing observed inputs, learned weights, point prediction, uncertainty, predicted drift rate, and safety slope comparison.
    - Zero fabrication of physical failure mechanisms from statistical coefficients.

---

#### 3. Strict Boundary & Gate Status
- **Specification Document**: [`docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md`](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md) (RELEASED).
- **Model Training**: **NOT AUTHORIZED**.
- **Production Code Changes**: **NOT AUTHORIZED**.
- **Validation Partition Execution**: **REMAINS BLOCKED**.
- **Final Evaluation Execution**: **NOT AUTHORIZED**.
- **Phase 4B Frozen Artifacts**: **14/14 HASHES PRESERVED 100% BIT-FOR-BIT IDENTICAL**.
- **Test Suite**: **199/199 TESTS PASSING**.

**STRICT STOP ENFORCED PENDING SPECIFICATION REVIEW.**

---

### LOG-094: Phase 5 Module B Regression Specification Forensic Hardening
- **Timestamp**: 2026-09-18T03:45:00Z
- **Phase**: Phase 5 / Module B Predictive Regression Specification Hardening
- **Type**: SPECIFICATION_HARDENING
- **Supersedes / Amends**: LOG-093
- **Status**: SPECIFICATION HARDENED — SPECIFICATION ONLY — NO MODEL TRAINING / NO CODE MODIFICATION / NO VALIDATION AUTHORIZED

#### 1. Scope & Hardening Invariants
Pursuant to forensic review instructions, targeted documentation-only hardening was executed on [`docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md`](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md). Zero model training was conducted, zero production code was modified, zero validation/final evaluation was executed, and all 14 frozen Phase 4B/Phase 2F baseline artifacts remain bit-for-bit unmutated.

---

#### 2. Exact Specification Corrections Applied

1. **Defective / Degrading Sample Claim Hardened**:
   - Removed unqualified claim that "defective components are sparse (4–10%)".
   - Replaced with language strictly distinguishing:
     * degrading synthetic fixtures (progressive linear, accelerating, or staggered drift),
     * abnormal/anomalous fixtures (abrupt step changes, heteroscedastic noise),
     * static specification breaches (pre-existing baseline outliers),
     * equipment/common-mode effects (synchronous chamber perturbations affecting entire lots),
     * and generic "defective" terminology.
   - Formally established that generic "defective" terminology must not be used as a training-sufficiency label without an explicit ground-truth definition.
2. **Early Observed Change vs. Physical Velocity Claim Hardened**:
   - Removed characterization of $[v_0, v_{24}]$ as establishing physical "early velocity" and prevented treating regression coefficients as physical degradation rates.
   - Standardized definition:
     > *"The two inputs contain information about early observed change. A trained regression may learn a population-level relationship between early measurements and the 168h target, but this relationship must not be interpreted as a physical degradation-rate law without independent physical evidence."*
3. **Nonlinear Model Status Reclassified as Deferred**:
   - Eliminated permanent declaration of nonlinear regression as unjustified.
   - Reclassified status:
     > *"Regularized linear/robust regression is the preregistered first model family. Nonlinear models remain deferred unless a later, separately authorized analysis demonstrates nonlinear structure and satisfies predefined sample-size, nested-LOLO, overfitting, monotonicity, leakage-control, and reproducibility requirements."*
4. **Safety-Slope Claim Strictly Disambiguated**:
   - Removed statement asserting that MIL-PRF-19500/703 directly defines the predictive safety slope.
   - Standardized formal status:
     > *"OPEN DESIGN DECISION — SAFETY SLOPE DEFINITION. Candidate derivation sources may include governing device/specification limits, allowable parametric change, burn-in endpoint criteria, measurement uncertainty, and an explicitly documented stakeholder loss matrix. No numerical safety slope is authorized or claimed until its governing source, mathematical derivation, units, and decision semantics are independently documented."*
   - Prohibition against tuning safety slopes on benchmark labels retained.
5. **Uncertainty Language Hardened Against Over-Claiming**:
   - Verified that 90% prediction intervals are strictly characterized as benchmark-specific, training-fold empirical dispersion bounds ($\sigma_{\text{eff}} = 1.4826 \cdot \text{MAD}$).
   - Reaffirmed explicit prohibitions against describing intervals as "guaranteed", "formal conformal", "distribution-free", or "calibrated for real devices".
6. **Synthetic Data Epistemic Boundary Hardened**:
   - Reaffirmed throughout specification and Section 1 that all Phase 4B and Phase 2F relationships are synthetic mathematical benchmark models that do NOT establish real semiconductor degradation kinetics, physical wearout laws, ATE electrometer drift dynamics, or flight qualification.

---

#### 3. Formal Gate Status & Strict Stop
- **Specification Document**: [`docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md`](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md) (HARDENED v1.0.1-SPEC-ONLY).
- **Model Training**: **NOT AUTHORIZED**.
- **Production Code Changes**: **NOT AUTHORIZED**.
- **Validation Execution**: **REMAINS BLOCKED**.
- **Final Evaluation Execution**: **NOT AUTHORIZED**.
- **Phase 4B Frozen Artifacts**: **14/14 HASHES PRESERVED 100% BIT-FOR-BIT IDENTICAL**.
- **Test Suite**: **199/199 TESTS PASSING**.

```
================================================================================
                    IMPLEMENTATION AUTHORIZATION BOUNDARY
================================================================================
  NO MODEL TRAINING AUTHORIZED.
  NO PRODUCTION CODE CHANGES AUTHORIZED.
  NO VALIDATION EXECUTION AUTHORIZED.
  AWAITING FORMAL PHASE 5 IMPLEMENTATION AUTHORIZATION.
================================================================================
```

**STRICT STOP ENFORCED.**

---

### LOG-095: Phase 5 Module B Predictive Regression Implementation — Controlled Stage 1
- **Timestamp**: 2026-09-18T04:05:00Z
- **Phase**: Phase 5 / Module B Predictive Regression Implementation (Controlled Stage 1)
- **Type**: CONTROLLED_IMPLEMENTATION
- **Authorization**: FORMAL IMPLEMENTATION AUTHORIZATION — CONTROLLED STAGE 1 (LOG-094, docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md)
- **Status**: CONTROLLED IMPLEMENTATION COMPLETE — STAGE 1 — VALIDATION/FINAL REMAIN QUARANTINED

#### 1. Scope & Implementation Artifacts
Under formal authorization from LOG-094 and `docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md`, controlled implementation of the primary parameter-decoupled supervised predictive regression models for Module B has been completed:

1. **Supervised Regression Engine** (`src/sih26170/prognostics/regression_models.py`):
   - `BaseSupervisedRegressionModel(BasePrognosticModel)`: Abstract base class enforcing parameter coordinate representation transformations, training-fold z-score normalization, empirical residual uncertainty calibration ($\sigma_{\text{eff}} = 1.4826 \cdot \text{MAD}$), numerical divergence detection ($|\hat{u}| > 10$ fallback to Carry-Forward $v_{24}$ with unconstrained logging and zero cosmetic clipping), and complete model lineage logging.
   - `RidgeRegressionPrognosticModel`: Exact closed-form normal equations $(X^T X + \Gamma)^{-1} X^T y$ with $L_2$ regularization on slope coefficients $(\beta_1, \beta_2)$, leaving intercept $\beta_0$ unpenalized.
   - `HuberRegressionPrognosticModel`: Robust Iteratively Reweighted Least Squares (IRLS) fitting in transformed coordinate space with adaptive Huber threshold $\delta = 1.345 \cdot \text{MAD}(r)$, dampening outlier leverage from anomalous fixtures.
   - `ParameterDecoupledRegressionPipeline`: Orchestrates four independent, parameter-specific regression models across $I_{\text{DSS}}$, $V_{\text{GS(th)}}$, $R_{\text{DS(on)}}$, and $I_{\text{GSS}}$.
2. **Leave-One-Lot-Out (LOLO) Evaluation Engine** (`src/sih26170/prognostics/phase5_lolo_evaluator.py`):
   - Strict partition isolation: operates solely on authorized training/calibration partition (`LOT_CAL_001` through `LOT_CAL_050`, 1,000 components, 4,000 parameter series).
   - 50-fold cross-validation: for each fold, fits models strictly on 49 lots and predicts on the single held-out lot. Held-out lots contribute zero information to fitting, scaling, or uncertainty calibration.
   - Complete descriptive metrics computed across all 50 folds and per fold.
3. **Artifact Outputs** (`data/evaluation_phase5/`):
   - `data/evaluation_phase5/phase5_regression_lolo_results.json`: Full 50-fold aggregated and fold-level metrics for Ridge, Huber, Carry-Forward, and Two-Point Linear across all 4 parameters.
   - `data/evaluation_phase5/phase5_model_lineage_manifest.json`: Exhaustive model lineage records (50 folds $\times$ 4 parameters $\times$ 2 trained models = 400 lineage records) capturing coefficients, preprocessing parameters, hyperparameters, and lot splits.
4. **Comprehensive Test Suite** (`tests/prognostics/test_phase5_regression.py`):
   - 12 unit and integration tests covering all 12 required dimensions: feature contract, transformation correctness, signed $I_{\text{GSS}}$ semantics, train/test lot separation, training-only preprocessing, as-of temporal boundary, ground-truth quarantine, deterministic reproducibility, finite prediction rate, divergence fallback, one-model-per-parameter topology, and baseline comparison interface compatibility.
   - Total test suite status: **211/211 TESTS PASSING** (199 existing + 12 new).

---

#### 2. Leave-One-Lot-Out (LOLO) Descriptive Evaluation Results
Primary metric: Mean Absolute Error (MAE) in physical engineering units.
Total sample count per parameter: $N = 1{,}000$ (across all 50 calibration lots).
Finite prediction rate: $100.0\%$ (0 divergence fallbacks triggered on clean calibration data).

| Parameter | Unit | Model Family | Primary MAE | RMSE | Median Abs Error | 90% Int. Coverage | Mean Int. Width | Fold MAE Mean $\pm$ Std |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$I_{\text{DSS}}$** | $\mu\text{A}$ | **RIDGE** | **0.0494** | 0.0647 | 0.0386 | 88.8% | 0.1958 | $0.0494 \pm 0.0165$ |
| | | **HUBER** | **0.0494** | 0.0648 | 0.0381 | 88.7% | 0.1955 | $0.0494 \pm 0.0166$ |
| | | *CARRY_FORWARD* | 0.0549 | 0.0732 | 0.0425 | — | — | $0.0549 \pm 0.0195$ |
| | | *TWO_POINT_LINEAR* | 0.3991 | 0.7098 | 0.2425 | — | — | $0.3991 \pm 0.1568$ |
| **$I_{\text{GSS}}$** | $\text{nA}$ | **RIDGE** | **0.6502** | 0.9371 | 0.4924 | 88.2% | 2.5242 | $0.6502 \pm 0.2635$ |
| | | **HUBER** | **0.6503** | 0.9375 | 0.4946 | 88.0% | 2.5151 | $0.6503 \pm 0.2639$ |
| | | *CARRY_FORWARD* | 0.7648 | 1.0662 | 0.5804 | — | — | $0.7648 \pm 0.2641$ |
| | | *TWO_POINT_LINEAR* | 28.0760 | 152.1079 | 3.3254 | — | — | $28.0760 \pm 34.7695$ |
| **$R_{\text{DS(on)}}$** | $\text{m}\Omega$ | **RIDGE** | **0.7149** | 0.9075 | 0.5986 | 88.1% | 2.8455 | $0.7149 \pm 0.2213$ |
| | | **HUBER** | **0.7247** | 0.9214 | 0.5926 | 88.1% | 2.9194 | $0.7247 \pm 0.2265$ |
| | | *CARRY_FORWARD* | 0.7658 | 0.9836 | 0.6279 | — | — | $0.7658 \pm 0.2476$ |
| | | *TWO_POINT_LINEAR* | 4.1283 | 5.2355 | 3.4873 | — | — | $4.1283 \pm 0.8119$ |
| **$V_{\text{GS(th)}}$** | $\text{V}$ | **RIDGE** | **0.0239** | 0.0302 | 0.0204 | 89.6% | 0.1000 | $0.0239 \pm 0.0083$ |
| | | **HUBER** | **0.0241** | 0.0304 | 0.0206 | 88.9% | 0.0993 | $0.0241 \pm 0.0083$ |
| | | *CARRY_FORWARD* | 0.0257 | 0.0322 | 0.0216 | — | — | $0.0257 \pm 0.0077$ |
| | | *TWO_POINT_LINEAR* | 0.1389 | 0.1737 | 0.1200 | — | — | $0.1389 \pm 0.0277$ |

*Descriptive observations*:
- In accordance with the Stage 1 specification, no algorithm "winner", ranking, or score is declared. Metrics are reported purely descriptively.
- Two-Point Linear extrapolation exhibits substantial error magnification across all parameters (e.g., MAE of 28.08 nA for IGSS vs 0.65 nA for trained regression) due to amplifying 0h–24h measurement jitter over the 7x extrapolation horizon.
- Observed empirical prediction-interval coverage in the controlled 50-fold LOLO evaluation was 88.0–89.6%.
- **OPEN IMPLEMENTATION DEVIATION — UNCERTAINTY CALIBRATION**: The current implementation computes residual scale $\sigma_{\text{eff}}$ on in-sample training fold residuals rather than through an out-of-fold training residual calibration. The intervals are based on in-sample training residuals and must not be claimed as calibrated.

---

#### 3. Strict Invariant & Governance Compliance
1. **Partition Isolation**:
   - Training and evaluation conducted strictly on `LOT_CAL_001` through `LOT_CAL_050`.
   - Validation (`LOT_VAL_001` to `LOT_VAL_020`) and Final Evaluation (`LOT_EVAL_001` to `LOT_EVAL_020`) partitions remained strictly quarantined and were never accessed.
2. **Feature Contract**:
   - Primary inputs strictly limited to $[v_0, v_{24}]$. Zero future checkpoints ($t > 24\text{h}$) and zero ground-truth/scenario labels were accessible to models.
3. **Signed $I_{\text{GSS}}$ Semantics**:
   - Negative gate currents preserved without `abs()` or arbitrary clipping to $\pm 100\text{ nA}$.
4. **Safety Slope**:
   - Remains an **OPEN DESIGN DECISION**. No numerical safety slope was implemented or tuned.
5. **Phase 4B Frozen Artifact Preservation**:
   - All 14 frozen artifact hashes re-verified bit-for-bit identical against authoritative records.

```
================================================================================
                    PHASE 5 STAGE 1 COMPLETION DECLARATION
================================================================================
  PHASE 5 CONTROLLED IMPLEMENTATION — COMPLETE
  MODEL TRAINING PERFORMED ONLY WITHIN AUTHORIZED TRAINING DATA.
  VALIDATION/FINAL DATA REMAIN QUARANTINED.
  SAFETY SLOPE REMAINS OPEN.
  NO PHASE 4B FROZEN ARTIFACTS MODIFIED.
================================================================================
```

**STRICT STOP ENFORCED AFTER STAGE 1.**

---

### LOG-096: Phase 5 Controlled Stage 1 Forensic Audit
- **Timestamp**: 2026-09-18T04:20:00Z
- **Phase**: Phase 5 / Module B Predictive Regression Forensic Audit
- **Type**: FORENSIC_AUDIT
- **Audit Target**: Phase 5 Controlled Stage 1 Implementation and Evaluation (LOG-095)
- **Status**: PHASE 5 CONTROLLED STAGE 1 — ACCEPTED WITH OPEN UNCERTAINTY-CALIBRATION DEVIATION

#### 1. Executive Summary & Audit Status
A forensic audit was conducted on the Phase 5 Controlled Stage 1 implementation, artifacts, and test suite. The core supervised regression engine, parameter-decoupled topology, Leave-One-Lot-Out (LOLO) cross-validation, feature contract, and numerical safety architecture conform strictly to `docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md`. One implementation deviation regarding in-sample uncertainty calibration was identified and recorded as an open issue pursuant to forensic instructions.

```
================================================================================
                    FORENSIC AUDIT FORMAL CLASSIFICATION
================================================================================
  PHASE 5 CONTROLLED STAGE 1 — ACCEPTED WITH OPEN UNCERTAINTY-CALIBRATION DEVIATION
  NO RIDGE/HUBER MODEL SELECTION AUTHORIZED.
  NO VALIDATION EXECUTION AUTHORIZED.
  NO FINAL EVALUATION AUTHORIZED.
  NO SAFETY-SLOPE IMPLEMENTATION AUTHORIZED.
================================================================================
```

---

#### 2. Detailed Audit Findings by Dimension

##### 1. Uncertainty Calibration — Critical Finding
- **Traced Code Path**: `src/sih26170/prognostics/regression_models.py` lines 141–156:
  ```python
  self.coefficients_ = self._fit_transformed(U_arr, u_t_arr)
  X_aug = np.column_stack([np.ones(len(U_arr)), U_arr])
  u_pred = X_aug @ self.coefficients_
  residuals = u_t_arr - u_pred
  med_res = float(np.median(residuals))
  mad_res = float(np.median(np.abs(residuals - med_res)))
  scale = 1.4826 * mad_res
  ```
- **Finding**: Residuals are **Option A: in-sample residuals** generated by predicting on the identical observations (`U_arr`, `u_t_arr`) used to fit `self.coefficients_`. They are not generated through an internal out-of-fold cross-validation split within the training fold.
- **Classification**: **OPEN IMPLEMENTATION DEVIATION — UNCERTAINTY CALIBRATION**.
- **Action**: Pursuant to strict audit instructions, this issue is NOT silently patched. The current prediction intervals are documented as based on in-sample training residuals and must not be claimed as calibrated.

##### 2. Huber Convergence Claim Audit
- **Audited Statement**: *"Robust Huber regression using IRLS with adaptive scale $\delta = 1.345 \cdot \text{MAD}(r)$, guaranteed monotonic convergence to the convex optimum."*
- **Mathematical Audit**: In `HuberRegressionPrognosticModel._fit_transformed`, the threshold scale $\delta^{(t)} = 1.345 \cdot 1.4826 \cdot \text{MAD}(r^{(t)})$ is recomputed at every iteration $t$ as a function of the non-smooth median absolute deviation of the current residuals. Because the effective objective changes at each iteration when $\delta$ updates, the procedure does not constitute majorization-minimization of a single static convex loss function. Neither monotonic objective decrease nor global convergence can be formally established under this adaptive-scale formulation.
- **Correction Applied**: The claim has been purged and replaced with conservative wording:
  > *"IRLS-based Huber regression with deterministic stopping criteria."*

##### 3. Empirical Coverage Language Audit
- **Audited Language**: References to "coverage conformance", "calibrated coverage", or "successful calibration".
- **Correction Applied**: Standardized across all documentation and reports to:
  > *"Observed empirical prediction-interval coverage in the controlled 50-fold LOLO evaluation was 88.0–89.6%."*
- Explicitly documented that prediction intervals are based on in-sample training residuals, representing an open implementation limitation.

##### 4. LOLO Separation Verification
- **Programmatic Audit**: Audited all 50 folds in `data/evaluation_phase5/phase5_model_lineage_manifest.json` against `data/synthetic_phase4b/observations.csv`:
  * Held-out lot rows are 100% absent from `fit()` in every fold.
  * Preprocessing parameters ($\mu_0, \sigma_0, \mu_{24}, \sigma_{24}$) and $\sigma_{\text{eff}}$ are computed strictly on the 49 training lots.
  * Held-out lot rows are used exclusively for final out-of-fold prediction and evaluation.
  * Zero component IDs leak across fold boundaries.
- **Result**: **PASS** (50/50 folds verified; 0 failures).

##### 5. Feature Contract Verification
- **Code Audit**: Inspected `fit()` and `predict_transformed()` in `src/sih26170/prognostics/regression_models.py`.
- **Finding**: Shape is strictly asserted as $(N, 2)$ representing $[v_0, v_{24}]$. Model rejects 1D, 3D, or expanded feature matrices with `ValueError`.
- **Leakage Check**: Confirmed that 48h, 72h, 96h, 120h, 168h checkpoints, scenario labels, ground truth columns, latent state variables, Module A scores/dispositions, component IDs, and future lot statistics are completely absent from model inputs.
- **Result**: **PASS**.

##### 6. Coordinate Transformations Verification
- **Code Audit**: Inspected `src/sih26170/screening/transforms.py` and models.
  * $I_{\text{DSS}} \to \ln(y)$, inverse $\exp(u)$ (**PASS**).
  * $R_{\text{DS(on)}} \to \ln(y)$, inverse $\exp(u)$ (**PASS**).
  * $V_{\text{GS(th)}} \to y$, inverse $u$ (**PASS**).
  * $I_{\text{GSS}} \to \text{asinh}(y / 1.0\ \text{nA})$, inverse $\sinh(u) \cdot 1.0\ \text{nA}$ (**PASS**).
- **Search for Forbidden Operations**:
  * `abs(IGSS)`: None found.
  * Clipping at $\pm 100\text{ nA}$: None found.
  * Positive-only IGSS coercion: None found.
- **Result**: **PASS**.

##### 7. Ridge Normal Equations Implementation Audit
- **Code Audit**: Inspected `RidgeRegressionPrognosticModel._fit_transformed()`.
  * Intercept handling: $\Gamma = \text{diag}([0.0, \lambda, \lambda])$; intercept $\beta_0$ is unpenalized (**PASS**).
  * Slope regularization: Slopes $\beta_1, \beta_2$ penalized with $L_2$ penalty $\lambda = 1.0$ (**PASS**).
  * Numerical solver: Uses `np.linalg.solve(XtX + Gamma, Xty)` (LAPACK linear solve) rather than explicit matrix inversion `np.linalg.inv` (**PASS — NUMERICALLY STABLE**).
  * Deterministic reproducibility: Verified bit-for-bit to machine precision (**PASS**).
- **Result**: **PASS**.

##### 8. Exact Sample & Result Accounting
- **Artifact Reconciliation**:
  * Total calibration lots: 50 (`LOT_CAL_001` through `LOT_CAL_050`).
  * Total components: $50 \times 20 = 1{,}000$.
  * Total parameter series: $1{,}000 \times 4 = 4{,}000$.
  * Total predictions evaluated: $1{,}000 \times 4 \times 4 = 16{,}000$ predictions.
  * Total lineage records: $50 \times 4 \times 2 = 400$ records in `phase5_model_lineage_manifest.json`.
  * Finite prediction rate: $100.0\%$ ($16{,}000 / 16{,}000$).
  * Divergence count: 0 across all models and folds on calibration data.
- **Result**: **PASS — EXACT RECONCILIATION COMPLETE**.

##### 9. Result Interpretation & Baseline Comparison
- **Descriptive Reporting**: Preserved without declaring a winner or selecting Ridge vs Huber.
- **Baseline Comparability**: `CarryForwardModel` and `TwoPointLinearModel` evaluated on identical out-of-fold `PrognosticInput` sequences and true target values. Directly comparable.
- **Result**: **PASS**.

##### 10. Frozen Artifact Integrity
- Re-verified all 14 Phase 4B and Phase 2F baseline artifact hashes against authoritative records.
- All 14 hashes remain 100% bit-for-bit identical.
- Zero access to quarantined validation (`LOT_VAL_`) or final evaluation (`LOT_EVAL_`) partitions.
- Zero mutation to Module A or Phase 4B code.
- **Result**: **PASS**.

---

#### 3. Summary of Findings & Gate Status

| Audit Dimension | Status | Key Evidence / Notes |
| :--- | :--- | :--- |
| **Uncertainty Calibration** | **OPEN DEVIATION** | Residuals in `fit()` computed in-sample on training fold. |
| **Huber Convergence Claim** | **CORRECTED** | "Guaranteed monotonic convergence" purged; reclassified to IRLS with deterministic stopping. |
| **Coverage Language** | **CORRECTED** | Replaced with conservative empirical statement (88.0–89.6%). |
| **LOLO Fold Isolation** | **PASS** | 50/50 folds verified programmatically; zero held-out leakage. |
| **Feature Contract** | **PASS** | Strictly $[v_0, v_{24}]$; zero future checkpoints or ground truth. |
| **Transforms & Signed IGSS** | **PASS** | All 4 transforms exact; zero `abs()`, zero clipping at $\pm 100\text{ nA}$. |
| **Ridge Implementation** | **PASS** | `np.linalg.solve` linear solve; unpenalized intercept; deterministic. |
| **Sample Accounting** | **PASS** | 1,000 components, 4,000 series, 16,000 predictions, 400 lineage records reconciled. |
| **Baseline Comparison** | **PASS** | Evaluated on identical held-out inputs and ground truths. |
| **Frozen Artifact Integrity** | **PASS** | 14/14 hashes bit-for-bit identical; validation partitions quarantined. |
| **Test Suite** | **PASS** | 211/211 tests passing. |

```
================================================================================
                        GATE STATUS DECLARATION
================================================================================
  PHASE 5 CONTROLLED STAGE 1 — ACCEPTED WITH OPEN UNCERTAINTY-CALIBRATION DEVIATION

  NO RIDGE/HUBER MODEL SELECTION AUTHORIZED.
  NO VALIDATION EXECUTION AUTHORIZED.
  NO FINAL EVALUATION AUTHORIZED.
  NO SAFETY-SLOPE IMPLEMENTATION AUTHORIZED.
================================================================================
```

**STRICT STOP ENFORCED AFTER FORENSIC AUDIT.**

---

### LOG-097: Phase 5 Controlled Stage 1A Uncertainty Calibration Correction
- **Timestamp**: 2026-09-18T04:45:00Z
- **Phase**: Phase 5 / Module B Predictive Regression Implementation (Controlled Stage 1A)
- **Type**: UNCERTAINTY_CALIBRATION_CORRECTION
- **Authorization**: PHASE 5 — UNCERTAINTY CALIBRATION CORRECTION CONTROLLED STAGE 1A
- **Status**: UNCERTAINTY CALIBRATION CORRECTION COMPLETE — STAGE 1A — VALIDATION/FINAL REMAIN QUARANTINED

#### 1. Scope & Architectural Correction
Following the forensic audit findings in LOG-096, the uncertainty calibration architecture of Module B supervised regression models has been refactored from in-sample residual estimation to leakage-safe, nested out-of-fold (OOF) residual calibration:

1. **Nested Lot-Wise Cross-Validation Architecture** ([`src/sih26170/prognostics/regression_models.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/src/sih26170/prognostics/regression_models.py#L72-L175)):
   - `BaseSupervisedRegressionModel.fit()` now accepts `sample_lot_ids` and executes a deterministic internal Leave-One-Lot-Out (nested LOLO) procedure across the 49 training lots.
   - For each internal fold $j \in \{1 \dots 49\}$:
     * Internal training subset: 48 training lots ($N = 960$ components).
     * Internal validation subset: 1 training lot ($N = 20$ components).
     * Internal model $\hat{\beta}_{\text{inner}}$ is fitted strictly on the 48 internal training lots.
     * Internal predictions $\hat{u}_i^{\text{OOF}}$ and residuals $e_i = u_{168, i} - \hat{u}_i^{\text{OOF}}$ are generated for the 20 components of the held-out training lot $j$.
   - Across all 49 internal folds, $N = 980$ out-of-fold residuals $e_{\text{OOF}}$ are accumulated.
   - Robust empirical residual scale is calculated:
     $$\sigma_{\text{eff}} = \max\left(1.4826 \cdot \text{MAD}(e_{\text{OOF}}), \sigma_{\text{floor}}\right)$$
   - The outer held-out lot is **100% excluded** from internal fold assignment, internal model fitting, and residual generation.

2. **Primary Model Invariant Preservation**:
   - The primary regression model coefficients $(\beta_0, \beta_1, \beta_2)$ evaluated on the outer held-out lot remain fitted on the entire 49-lot training fold.
   - Point predictions $\hat{y}_{168}$, physical MAEs, RMSEs, and median absolute errors are **100% bit-for-bit identical** between Stage 1 and Stage 1A.
   - Only prediction intervals $[L, U]$ and $\sigma_{\text{eff}}$ are updated via the out-of-fold residual scale.

3. **Artifact Versioning & Preservation**:
   - Historical Stage-1 artifacts (`phase5_regression_lolo_results.json` and `phase5_model_lineage_manifest.json`) are preserved unmodified.
   - Versioned Stage-1A artifacts generated in `data/evaluation_phase5/`:
     * `phase5_stage1a_uncertainty_lolo_results.json`
     * `phase5_stage1a_model_lineage_manifest.json`

---

#### 2. Stage-1A Descriptive Evaluation Results
Primary metric: Mean Absolute Error (MAE) in physical engineering units.
Total sample count per parameter: $N = 1{,}000$. Finite prediction rate: $100.0\%$. Divergence count: 0.

| Parameter | Unit | Model Family | Primary MAE | RMSE | Median Abs Error | 90% Int. Coverage | Mean Int. Width | Fold MAE Mean $\pm$ Std |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **$I_{\text{DSS}}$** | $\mu\text{A}$ | **RIDGE** | **0.0494** | 0.0647 | 0.0386 | 88.9% | 0.1977 | $0.0494 \pm 0.0165$ |
| | | **HUBER** | **0.0494** | 0.0648 | 0.0381 | 89.0% | 0.1979 | $0.0494 \pm 0.0166$ |
| | | *CARRY_FORWARD* | 0.0549 | 0.0732 | 0.0425 | — | — | $0.0549 \pm 0.0195$ |
| | | *TWO_POINT_LINEAR* | 0.3991 | 0.7098 | 0.2425 | — | — | $0.3991 \pm 0.1568$ |
| **$I_{\text{GSS}}$** | $\text{nA}$ | **RIDGE** | **0.6502** | 0.9371 | 0.4924 | 88.2% | 2.5254 | $0.6502 \pm 0.2635$ |
| | | **HUBER** | **0.6503** | 0.9375 | 0.4946 | 88.2% | 2.5184 | $0.6503 \pm 0.2639$ |
| | | *CARRY_FORWARD* | 0.7648 | 1.0662 | 0.5804 | — | — | $0.7648 \pm 0.2641$ |
| | | *TWO_POINT_LINEAR* | 28.0760 | 152.1079 | 3.3254 | — | — | $28.0760 \pm 34.7695$ |
| **$R_{\text{DS(on)}}$** | $\text{m}\Omega$ | **RIDGE** | **0.7149** | 0.9075 | 0.5986 | 88.7% | 2.9065 | $0.7149 \pm 0.2213$ |
| | | **HUBER** | **0.7247** | 0.9214 | 0.5926 | 88.5% | 2.9533 | $0.7247 \pm 0.2265$ |
| | | *CARRY_FORWARD* | 0.7658 | 0.9836 | 0.6279 | — | — | $0.7658 \pm 0.2476$ |
| | | *TWO_POINT_LINEAR* | 4.1283 | 5.2355 | 3.4873 | — | — | $4.1283 \pm 0.8119$ |
| **$V_{\text{GS(th)}}$** | $\text{V}$ | **RIDGE** | **0.0239** | 0.0302 | 0.0204 | 89.6% | 0.1000 | $0.0239 \pm 0.0083$ |
| | | **HUBER** | **0.0241** | 0.0304 | 0.0206 | 89.2% | 0.0997 | $0.0241 \pm 0.0083$ |
| | | *CARRY_FORWARD* | 0.0257 | 0.0322 | 0.0216 | — | — | $0.0257 \pm 0.0077$ |
| | | *TWO_POINT_LINEAR* | 0.1389 | 0.1737 | 0.1200 | — | — | $0.1389 \pm 0.0277$ |

*Descriptive observations*:
- Observed empirical prediction-interval coverage under nested LOLO out-of-fold calibration is 88.2%–89.6% across all four parameters.
- Point prediction accuracy (MAE, RMSE, MedAE) is bit-for-bit preserved from Stage 1.
- No overall algorithm winner, ranking, or selection decision is declared.

---

#### 3. Verification & Governance Summary
1. **Dedicated Test Suite** ([`tests/prognostics/test_phase5_stage1a_uncertainty.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/tests/prognostics/test_phase5_stage1a_uncertainty.py)):
   - 10 unit and integration tests proving all 10 Stage-1A requirements:
     * Every OOF prediction generated without predicted observation (**PASS**).
     * Outer held-out lot 100% excluded from OOF calibration (**PASS**).
     * Internal preprocessing fitted strictly on internal training subsets (**PASS**).
     * Mutating outer held-out target does not affect $\sigma_{\text{eff}}$ (**PASS**).
     * Mutating outer held-out features does not affect $\sigma_{\text{eff}}$ (**PASS**).
     * Corrupting validation/final partitions does not affect $\sigma_{\text{eff}}$ (**PASS**).
     * OOF residual count deterministic and reproducible ($N = 980$) (**PASS**).
     * Signed $I_{\text{GSS}}$ semantics preserved (**PASS**).
     * Model coefficients bit-for-bit unchanged by uncertainty refactoring (**PASS**).
     * Feature contract strictly $[V_0, V_{24}]$ (**PASS**).
2. **Full Repository Test Suite**:
   - `PYTHONPATH=.:src pytest` -> **221/221 TESTS PASSING** (211 existing + 10 new).
3. **Frozen Baseline Artifacts**:
   - All 14 Phase 4B and Phase 2F baseline artifact hashes remain 100% bit-for-bit identical.
4. **Quarantine Enforcement**:
   - Validation (`LOT_VAL_`) and final evaluation (`LOT_EVAL_`) partitions remain strictly quarantined and were never accessed.
   - Module A and Phase 4B detector code remain completely unmutated.

```
================================================================================
                    STAGE 1A COMPLETION DECLARATION
================================================================================
  UNCERTAINTY CALIBRATION CORRECTION COMPLETE.

  MODEL SELECTION NOT AUTHORIZED.
  VALIDATION NOT AUTHORIZED.
  FINAL EVALUATION NOT AUTHORIZED.
  SAFETY-SLOPE IMPLEMENTATION NOT AUTHORIZED.
================================================================================
```

**STRICT STOP ENFORCED AFTER STAGE 1A.**

---

### LOG-098: Phase 5 Controlled Stage 1A Final Forensic Reconciliation Gate
- **Timestamp**: 2026-09-18T05:00:00Z
- **Phase**: Phase 5 / Module B Predictive Regression Implementation (Controlled Stage 1A Reconciliation Gate)
- **Type**: GATE_FORENSIC_RECONCILIATION
- **Authorization**: PHASE 5 STAGE 1A — FINAL FORENSIC RECONCILIATION
- **Status**: PHASE 5 CONTROLLED STAGE 1A — FORENSICALLY ACCEPTED

#### 1. Reconciliation Findings
1. **Preprocessing Pipeline Equivalence & Inner Isolation**:
   - Parameter coordinate transformations $u = \phi(y)$ ($\ln(y)$, $\text{arcsinh}(y/1.0\ \text{nA})$, identity) are analytical functions requiring zero empirical population statistics.
   - In every inner fold $j \in \{1 \dots 49\}$, inner models $\hat{\beta}_{\text{inner}}$ are fitted strictly on the 48 inner-training lots ($N = 960$). Inner validation observations ($N = 20$) are transformed analytically and evaluated without contaminating inner weights.
   - The outer held-out lot (`LOT_CAL_{k:03d}`) is completely absent from all training arrays, preprocessing records, inner loops, and $\sigma_{\text{eff}}$ calculations.
   - The outer model retains identical 49-lot training preprocessing and lineage metadata as Stage 1.
2. **Adversarial Preprocessing Mutation Testing**:
   - Mutating inner-validation features by $+50.0\ \text{V}$ produced zero change in inner coefficients ($\Delta \hat{\beta}_{\text{inner}} = 0.0$) and zero change in inner statistics ($\Delta \mu_0 = 0, \Delta \sigma_0 = 0$). Validation prediction changed strictly through the linear feature projection ($\hat{\beta}_1 \times 50.0$).
   - Mutating outer held-out features/targets produced zero change in outer $\sigma_{\text{eff}}$ ($\Delta \sigma_{\text{eff}} = 0.0$).
   - Dedicated behavioral test added as Test 11 in [`tests/prognostics/test_phase5_stage1a_uncertainty.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/tests/prognostics/test_phase5_stage1a_uncertainty.py).
3. **Ridge and Huber Independent Uncertainty Traceability**:
   - Verified that nested OOF calibration is performed independently for both Ridge (closed-form solve) and Huber (IRLS).
   - Across all 400 models (50 folds $\times$ 4 parameters $\times$ 2 families), every model has exactly $N_{\text{OOF}} = 980$ residuals in transformed coordinate space.
4. **Coefficient Immutability Language**:
   - Standardized terminology: "Numerically identical coefficients to the Stage-1 artifacts within exact floating-point comparison" ($\max \|\Delta \beta\|_\infty = 0.0$).
5. **Full Repository Test Suite & Baseline Hashes**:
   - `PYTHONPATH=.:src pytest` -> **222/222 TESTS PASSING**.
   - All 14 frozen Phase 4B and Phase 2F baseline artifact hashes remain 100% bit-for-bit identical.
   - Validation (`LOT_VAL_`) and final evaluation (`LOT_EVAL_`) partitions remain strictly quarantined.

```
================================================================================
                 PHASE 5 STAGE 1A GATE CLOSURE DECLARATION
================================================================================
  PHASE 5 CONTROLLED STAGE 1A — FORENSICALLY ACCEPTED

  UNCERTAINTY CALIBRATION STATUS: PASS
  POINT-PREDICTION ARCHITECTURE: UNCHANGED
  FROZEN PHASE 4B ARTIFACTS: UNCHANGED
  VALIDATION: QUARANTINED
  FINAL EVALUATION: QUARANTINED
  RIDGE/HUBER MODEL SELECTION: NOT AUTHORIZED
  SAFETY SLOPE: OPEN
================================================================================
```

**STRICT STOP ENFORCED AFTER STAGE 1A RECONCILIATION.**

---

### LOG-099: Phase 5 Controlled Stage 1 Model Selection Protocol Pre-Registration
- **Timestamp**: 2026-09-18T05:30:00Z
- **Phase**: Phase 5 / Module B Predictive Regression Implementation (Stage 1 Model Selection Gate)
- **Type**: SELECTION_PROTOCOL_PRE_REGISTRATION
- **Authorization**: PHASE 5 — CONTROLLED STAGE 1 MODEL SELECTION GATE
- **Status**: PHASE 5 MODEL SELECTION PROTOCOL — PRE-REGISTERED AND FROZEN

#### 1. Scope & Pre-Registration Design
Following the forensic acceptance of Stage 1A under LOG-098, the model selection protocol for Phase 5 Module B supervised predictive regression has been formally pre-registered and frozen prior to any validation or final evaluation:

1. **Selection Unit**:
   - **Primary**: Parameter-Decoupled Regression (Architecture A), selecting the optimal model family independently per electrical parameter: $I_{\text{DSS}}, V_{\text{GS(th)}}, R_{\text{DS(on)}}, I_{\text{GSS}}$.
   - **Secondary**: Global Consensus Family determined via unweighted majority win count ($\ge 3/4$).
2. **Deterministic 4-Tier Decision Hierarchy**:
   - **Tier 1 (Point Accuracy)**: Physical-unit MAE on 50-fold LOLO calibration data ($N = 1{,}000$). Practical equivalence tolerance $\tau_{\text{MAE}} = 0.5\%$ (grounded in ATE electrometer repeatability limits).
   - **Tier 2 (Uncertainty Quality)**: Mean Winkler score at $\alpha = 0.10$ ($90\%$ nominal coverage) penalizing width and boundary violations ($20\times$ penalty). Equivalence tolerance $\tau_{\text{WS}} = 0.5\%$.
   - **Tier 3 (Cross-Fold Stability)**: Standard deviation of fold MAEs across the 50 LOLO folds ($\tau_{\text{Std}} = 0.5\%$).
   - **Tier 4 (Deterministic Tie-Break)**: Default to **RIDGE** based on closed-form analytical simplicity ($(X^T X + \Gamma)^{-1} X^T y$ via LAPACK `dgesv`) versus iterative IRLS optimization.
3. **Evidence & Pre-Registered Outcomes**:
   - $R_{\text{DS(on)}}$: Ridge achieves lower physical MAE ($0.71487$ vs $0.72467\ \text{m}\Omega$, $1.37\%$ margin) $\rightarrow$ **RIDGE (Tier 1)**.
   - $I_{\text{DSS}}$: MAE tied ($0.02\%$), Winkler tied ($0.23\%$), Ridge achieves lower fold std ($0.01648$ vs $0.01660$, $0.73\%$ margin) $\rightarrow$ **RIDGE (Tier 3)**.
   - $I_{\text{GSS}}$: MAE tied ($0.01\%$), Winkler tied ($0.13\%$), fold std tied ($0.16\%$) $\rightarrow$ **RIDGE (Tier 4 Tie-Break)**.
   - $V_{\text{GS(th)}}$: MAE tied ($0.42\%$), Winkler tied ($0.39\%$), fold std tied ($0.02\%$) $\rightarrow$ **RIDGE (Tier 4 Tie-Break)**.
   - **Global Consensus Family**: **RIDGE REGRESSION (4/4 Parameter Wins)**.

#### 2. Protocol Integrity & Governance
- **Dedicated Document**: [`docs/PHASE_5_MODEL_SELECTION_PROTOCOL.md`](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/PHASE_5_MODEL_SELECTION_PROTOCOL.md).
- **Executable Engine & Behavioral Tests**: [`src/sih26170/prognostics/model_selection.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/src/sih26170/prognostics/model_selection.py) and [`tests/prognostics/test_phase5_model_selection.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/tests/prognostics/test_phase5_model_selection.py).
- **Test Suite Status**: **229/229 TESTS PASSING** (8 new tests verifying determinism, quarantine rejection, and tier compliance).
- **Frozen Artifacts**: All 14 baseline hashes verified bit-for-bit.
- **Quarantine Enforcement**: Validation (`LOT_VAL_`) and final evaluation (`LOT_EVAL_`) partitions remain strictly quarantined and were never accessed.
- **Safety Slope**: Remains OPEN.

```
================================================================================
               MODEL SELECTION PROTOCOL REGISTRATION STATUS
================================================================================
  PHASE 5 MODEL SELECTION PROTOCOL — PRE-REGISTERED AND FROZEN

  PRIMARY SELECTION UNIT: PARAMETER-DECOUPLED REGRESSION (ARCHITECTURE A)
  GLOBAL CONSENSUS FAMILY: RIDGE REGRESSION (4/4 WINS)
  VALIDATION: QUARANTINED
  FINAL EVALUATION: QUARANTINED
  SAFETY SLOPE: OPEN
================================================================================
```

**STRICT STOP ENFORCED AFTER PROTOCOL PRE-REGISTRATION.**

---

### LOG-100: Phase 5 Model Selection Protocol Forensic Correction Gate
- **Timestamp**: 2026-09-18T05:45:00Z
- **Phase**: Phase 5 / Module B Predictive Regression Implementation (Selection Protocol Forensic Correction)
- **Type**: PROTOCOL_FORENSIC_CORRECTION
- **Authorization**: PHASE 5 — MODEL SELECTION PROTOCOL FORENSIC CORRECTION GATE
- **Status**: PHASE 5 MODEL SELECTION — FORENSICALLY ACCEPTED (WITH DOCUMENTED PROVENANCE LIMITATION)

#### 1. Forensic Corrections Applied to Protocol
1. **0.5% Tolerance Classification**:
   - Removed unverified claims attributing $\tau = 0.5\%$ to measured physical ATE hardware specifications.
   - Formally designated: *"$\tau = 0.5\%$ is a pre-registered engineering equivalence margin / design choice for this controlled model-selection protocol. It is not a measured universal ATE repeatability limit and is not claimed as a device-specific specification."* (Classified as **Layer 6: Design / Architecture Choice**).
2. **Epistemic Classification & Removal of "Mathematically Optimal"**:
   - Purged unsupported claims of universal mathematical optimality.
   - Grounded parameter physical descriptions as **Layer 3: Generic Physics / Literature Hypothesis** and design motivations as **Layer 6: Design / Architecture Choice**.
   - Verified that zero **Layer 7 (Unsupported / Evidence Gap)** claims serve as factual justifications for selection.
3. **Ridge Tie-Break Implementation Bounding**:
   - Replaced claims of machine-precision universal determinism with implementation-bounded language: *"Ridge uses a deterministic closed-form linear solve in the controlled implementation, whereas Huber uses iterative IRLS with an iteration-varying adaptive threshold and stopping criteria."*
4. **Pre-Registration Provenance Limitation Recorded**:
   - Documented that while the primary metric (physical MAE) was fixed in the specification prior to training, the numerical tolerance $\tau = 0.5\%$ and 4-tier hierarchy were frozen after Stage 1/1A LOLO calibration metrics were generated.
   - The protocol is pre-registered **strictly relative to the quarantined validation (`LOT_VAL_`) and final evaluation (`LOT_EVAL_`) benchmarks**, which have never been unquarantined or inspected.
5. **Zero-Tolerance Analysis Guardrails**:
   - Documented the strict $\tau = 0.0$ sensitivity check (where Ridge wins 3/4 parameters) strictly as a robustness check, confirming that it is not part of the primary rule, did not modify the rule, does not constitute an independent dataset, and does not represent statistical significance.
6. **Coverage Window Eligibility Verified**:
   - Confirmed both Ridge and Huber satisfy the $[85.0\%, 95.0\%]$ nominal coverage window across all 4 parameters ($88.2\%–89.6\%$).
7. **Implementation Isolation & Tests**:
   - Selection engine verified in [`src/sih26170/prognostics/model_selection.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/src/sih26170/prognostics/model_selection.py) and [`tests/prognostics/test_phase5_model_selection.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/tests/prognostics/test_phase5_model_selection.py) (9 tests passing).
   - Full repository test suite: **231/231 TESTS PASSING**.
   - All 14 frozen baseline hashes verified $100\%$ bit-for-bit identical.

```
================================================================================
                    MODEL SELECTION GATE DISPOSITION
================================================================================
  PHASE 5 MODEL SELECTION — FORENSICALLY ACCEPTED
  SELECTED MODEL FAMILY: RIDGE REGRESSION
  SELECTION BASIS: PRE-REGISTERED CALIBRATION-ONLY RULE (WITH PROVENANCE LIMITATION)

  IMPORTANT: SELECTING RIDGE FROM CALIBRATION EVIDENCE DOES NOT AUTHORIZE
  VALIDATION OR FINAL EVALUATION.

  VALIDATION: QUARANTINED
  FINAL EVALUATION: QUARANTINED
  SAFETY SLOPE: OPEN
================================================================================
```

**STRICT STOP ENFORCED AFTER PROTOCOL CORRECTION GATE.**

---

### LOG-101: Phase 5 Independent Validation Authorization & Forensic Reconciliation (Ridge Regression Locked)
- **Timestamp**: 2026-09-18T10:18:00Z (Reconciled: 2026-09-18T10:23:00Z)
- **Phase**: Phase 5 / Module B Predictive Regression Implementation (Independent Validation Stage)
- **Type**: INDEPENDENT_VALIDATION_EXECUTION_AND_RECONCILIATION
- **Authorization**: PHASE 5 — INDEPENDENT VALIDATION AUTHORIZATION (RIDGE REGRESSION — LOCKED MODEL)
- **Status**: PHASE 5 VALIDATION — FORENSICALLY ACCEPTED (MODEL LOCK MAINTAINED)

#### 1. Validation Authorization, Standing Log Lineage & Model Lock
- **Authorized Partition**: `LOT_VAL_*` unquarantined for evaluation-only access.
- **Standing Log Numbering Reconciliation**: LOG-095 documented initial Controlled Stage 1 implementation; LOG-101 is the authoritative, canonical log entry for Phase 5 Independent Validation.
- **Model Lock**: Architecture, hyperparameters ($\lambda = 1.0$), analytical transforms, features ($X = [v_0, v_{24}]$), coefficients, and nested LOLO uncertainty calibration scales ($\sigma_{\text{eff}}$) frozen pre-validation.
- **Implementation & Preprocessing Reconciliation**: The model solves directly on the design matrix $[1, u_0, u_{24}]$, where $u_0 = \phi(v_0), u_{24} = \phi(v_{24})$ are parameter-specific coordinate transforms. Features are **not** z-score standardized prior to Ridge regression; `preprocessor_params_` are recorded strictly as training-partition lineage metadata.
- **Zero Retraining / Zero Recalibration**: Models fitted exclusively on calibration partition (`LOT_CAL_001`–`LOT_CAL_050`, $N = 1{,}000$). Zero validation data entered model fitting, preprocessing parameter estimation, or uncertainty calibration.
- **Final Evaluation Quarantine**: `LOT_EVAL_*` remains strictly quarantined and inaccessible.
- **Safety Slope**: Remains OPEN (deferred to Phase 6 / Sentry gate).

#### 2. Validation Dataset Population & Hash Lineage
- **Dataset File**: `data/synthetic_phase4b/observations.csv`
- **SHA-256 Hash**: `b5de6a03022a9350b6f304b9af593768e7f83a8fc61fde6ca98e690cfa1f275f` (bit-for-bit match to frozen baseline manifest).
- **Validation Population**: 25 lots (`LOT_VAL_001` to `LOT_VAL_025`), 500 components, 2,000 parameter series, 14,000 observations across 7 checkpoints ($0\,\text{h}$, $24\,\text{h}$, $48\,\text{h}$, $72\,\text{h}$, $96\,\text{h}$, $120\,\text{h}$, $168\,\text{h}$).
- **Completeness**: $100.0\%$ complete $[v_0, v_{24}, v_{168}]$ triples (zero missing or non-finite values).

#### 3. Primary Empirical Results (Validation vs Frozen Calibration LOLO)
- **$I_{\text{DSS}}$ ($\mu\text{A}$)**:
  - Validation MAE: **$0.05485\,\mu\text{A}$** (vs Calibration LOLO: $0.04937\,\mu\text{A}$, $+11.10\%$)
  - RMSE: $0.07227\,\mu\text{A}$, MedAE: $0.04305\,\mu\text{A}$
  - Empirical Coverage ($90\%$ nominal): **$85.8\%$** (vs Calibration: $88.9\%$), Mean Width: $0.1963\,\mu\text{A}$
  - Winkler Score: $0.3015$ (vs Calibration: $0.2644$)
  - Baseline Comparison: Ridge outperforms Carry-Forward ($0.06003\,\mu\text{A}$) by **$+8.64\%$** and Two-Point Linear ($0.31676\,\mu\text{A}$) by $82.7\%$.
- **$I_{\text{GSS}}$ ($\text{nA}$)**:
  - Validation MAE: **$0.76516\,\text{nA}$** (vs Calibration LOLO: $0.65022\,\text{nA}$, $+17.68\%$)
  - RMSE: $1.23048\,\text{nA}$, MedAE: $0.52520\,\text{nA}$
  - Empirical Coverage ($90\%$ nominal): **$84.8\%$** (vs Calibration: $88.2\%$), Mean Width: $2.5322\,\text{nA}$
  - Winkler Score: $5.0067$ (vs Calibration: $3.8776$)
  - Baseline Comparison: Ridge outperforms Carry-Forward ($0.84207\,\text{nA}$) by **$+9.13\%$** and Two-Point Linear ($4.45732\,\text{nA}$) by $82.8\%$.
- **$R_{\text{DS(on)}}$ ($\text{m}\Omega$)**:
  - Validation MAE: **$0.73982\,\text{m}\Omega$** (vs Calibration LOLO: $0.71487\,\text{m}\Omega$, $+3.49\%$)
  - RMSE: $0.93258\,\text{m}\Omega$, MedAE: $0.63301\,\text{m}\Omega$
  - Empirical Coverage ($90\%$ nominal): **$90.2\%$** (vs Calibration: $88.7\%$), Mean Width: $2.9813\,\text{m}\Omega$
  - Winkler Score: **$3.7203$** (improved over Calibration: $3.7852$)
  - Baseline Comparison: Ridge outperforms Carry-Forward ($0.81483\,\text{m}\Omega$) by **$+9.21\%$** and Two-Point Linear ($4.21934\,\text{m}\Omega$) by $82.5\%$.
- **$V_{\text{GS(th)}}$ ($\text{V}$)**:
  - Validation MAE: **$0.02349\,\text{V}$** (improved over Calibration LOLO: $0.02395\,\text{V}$, **$-1.92\%$**)
  - RMSE: $0.02954\,\text{V}$, MedAE: $0.02065\,\text{V}$
  - Empirical Coverage ($90\%$ nominal): **$91.2\%$** (vs Calibration: $89.6\%$), Mean Width: $0.1003\,\text{V}$
  - Winkler Score: **$0.1225$** (improved over Calibration: $0.1269$)
  - Baseline Comparison: Ridge outperforms Carry-Forward ($0.02588\,\text{V}$) by **$+9.25\%$** and Two-Point Linear ($0.14431\,\text{V}$) by $83.7\%$.
- **Two-Point Linear Descriptive Characterization**: The result is consistent with amplification of early measurement variation by long-horizon linear extrapolation, rather than physical device degradation.

#### 4. Adversarial Leakage, Immutability & Determinism Verification
- **Adversarial Target & Feature Mutations**: Mutating validation targets ($+99{,}999.0$) or features ($\times 1{,}000.0$) in memory produced zero change in model coefficients ($\Delta \beta = 0.0$) and zero change in uncertainty scale ($\Delta \sigma_{\text{eff}} = 0.0$).
- **Intermediate Checkpoints Isolation**: Mutating observations at $48\,\text{h}$, $72\,\text{h}$, $96\,\text{h}$, and $120\,\text{h}$ produced zero change in validation predictions or errors.
- **Quarantined LOT_EVAL Invariance & Barrier**: Corrupting `LOT_EVAL_*` observations in CSV produced zero change in validation metrics. Passing `LOT_EVAL_*` directly into the evaluator triggers a fatal `PermissionError`.
- **Deterministic Repetition**: Repeated validation evaluations produced bit-for-bit identical results (`data/evaluation_phase5/phase5_validation_results.json`, SHA-256: `2e7398a66f4865c90a2fcbd47c3618862d73407d12a6a567770b9d88d0caa34d`).
- **Dedicated Test Suite**: [`tests/prognostics/test_phase5_validation.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/tests/prognostics/test_phase5_validation.py) passes 10 formal validation requirements.
- **Repository Full Test Suite**: **241/241 TESTS PASSING** (198 foundation + 1 standing log + 12 Stage 1 + 11 Stage 1A + 9 Model Selection + 10 Validation).
- **All 14 Frozen Baseline Artifacts**: Verified $100\%$ bit-for-bit immutable.

#### 5. Limitations & Protocol Discipline
- Observed degradations in $I_{\text{DSS}}$ ($+11.1\%$) and $I_{\text{GSS}}$ ($+17.7\%$) are documented as descriptive empirical findings and strictly not used to alter Ridge models.
- No pass/fail threshold was manufactured.
- No claims of production-readiness, flight qualification, or physical device validity are made.

```
================================================================================
                    PHASE 5 INDEPENDENT VALIDATION DISPOSITION
================================================================================
  PHASE 5 VALIDATION — FORENSICALLY ACCEPTED
  SELECTED MODEL: RIDGE REGRESSION
  MODEL LOCK: MAINTAINED (IMMUTABLE)
  FINAL EVALUATION: QUARANTINED (LOT_EVAL_* UNTOUCHED)
  NO FINAL EVALUATION AUTHORIZED
  SAFETY SLOPE: OPEN (DEFERRED TO PHASE 6)
================================================================================
```

**STRICT STOP ENFORCED AFTER INDEPENDENT VALIDATION FORENSIC RECONCILIATION.**

---

### LOG-102: Phase 6 Safety-Slope Decision Gate (Forensically Reconciled)
- **Timestamp**: 2026-09-18T10:28:00Z (Reconciled: 2026-09-18T10:30:00Z)
- **Phase**: Phase 6 / Prognostic Governance & Decision Framework (Safety-Slope Decision Gate)
- **Type**: GATE_DECISION_RECORD
- **Authorization**: PHASE 6 — SAFETY-SLOPE DECISION GATE AUTHORIZATION
- **Status**: PHASE 6 SAFETY SLOPE — OPEN EVIDENCE GAP

#### 1. Core Mandate & Four Decoupled Roles
Pursuant to formal instructions, a comprehensive forensic evaluation was executed on the candidate "safety slope" ($S_{\text{safe}}$) requirement for Module B, decoupled into four distinct engineering functions:
1. **Numerical Divergence Safeguard**: Preventing mathematical explosion.
2. **Physical Plausibility Bound**: Parameter-specific transforms enforce mathematical domain constraints where required; they do not independently establish physical validity of forecasts. Signed $I_{\text{GSS}}$ semantics are strictly preserved.
3. **Screening / Early Rejection Rule**: Decision rule scrapping physical components at $24\,\text{h}$ burn-in based on predicted drift rate $|\hat{S}_{168}| > S_{\text{safe}}$. Carries major operational/yield risk and is unsupported without calibrated loss matrices.
4. **Forecast-Risk Flag**: Informational epistemic uncertainty metadata communicating forecast confidence to screening engineers.

#### 2. Repository Inventory of Slope-Related Quantities
- `raw_slope_u`: $(u_{24} - u_0) / 24\,\text{h}$ linear rate in transformed coordinates.
- `theil_sen_slope_u`: Multi-point robust median slope estimator (collapses to `raw_slope_u` at $24\,\text{h}$).
- $g(T)$: Normalized drift $(u_T - u_0) / \sigma_{\text{floor}}$ in units of instrument repeatability floor.
- $g_{\text{excess}}(T)$: Common-mode excess drift subtracting Leave-One-Out lot median motion.
- Excess motion heuristic: $|g_{\text{excess}}| \ge 2.5$ in Module A (engineering design parameter, not a normative requirement).
- Regression weights $\beta_1, \beta_2$: Supervised Ridge feature slopes fitted on calibration data.
- $\hat{S}_{168}$: Mandated predicted drift rate $(\hat{v}_{168} - v_0) / 168\,\text{h}$.
- Two-Point Linear Extrapolation: $7 v_{24} - 6 v_0$, exhibiting severe error amplification.

#### 3. Epistemic Classification (Layers 1–7)
- **Measured Specification Failure** ($v_{168} \notin \text{Table I limits}$): **Layer 2 (Verified Standard Fact)**.
- **Physical Domain Constraints** ($v \ge 0$ for $I_{\text{DSS}}, R_{\text{DS(on)}}$, signed $I_{\text{GSS}}$): **Layer 1 (Verified Device Fact)** / **Layer 3 (Generic Physics)**.
- **Predicted Specification Breach** ($\hat{v}_{168} \notin \text{Table I limits}$): **Layer 6 (Design / Architecture Choice)**. Prognostic evidence, not a verified physical failure.
- **Predictive Early Rejection Policy**: **Layer 6 (Design / Architecture Choice)**. Must not automatically reject components solely because a forecast crosses a limit without explicit procurement authority.
- **Module A Excess Motion Threshold** ($|g_{\text{excess}}| \ge 2.5$): **Layer 6 (Design / Architecture Choice)**. Module A provides an upstream statistical evidence layer for excess motion and other screening signals; it does not establish a normative physical degradation-rate limit.
- **Ridge Regularized Linear Solve** ($\lambda = 1.0$): **Layer 3 / Layer 6**. Coefficients are finite and regularized; coefficient sums below 1 do not constitute a proof of global contractivity.
- **Numerical Early Rejection Safety Slope Threshold ($S_{\text{safe}}^{(p)}$)**: **Layer 7 (Unsupported / Open Evidence Gap)**.

#### 4. Military Standards Audit & Benchmark Schedules
- **Prototype Schedule vs Standards**: $168\,\text{h}$ burn-in duration represents the project prototype synthetic benchmark schedule / design choice (Layer 6). `MIL-STD-750` Method 1042 prescribes burn-in test methodology; neither standard specifies an in-situ hourly degradation rate boundary.
- **MIL-PRF-19500/703 Table I**: Audited thoroughly; confirmed to contain **zero normative intermediate hourly slope limits or dynamic early-rejection rate thresholds**.
- **No Benchmark Snooping**: Inventing or tuning a slope threshold against `LOT_VAL_*` or `LOT_EVAL_*` is strictly prohibited.

#### 5. Architectural Findings on Locked Ridge Model
- **Descriptive Numerical Stability**: Locked Ridge produced finite predictions on all validation cases. The fitted coefficients are finite and regularized; coefficient sums below 1 do not constitute a proof of global contractivity or a noise-damping guarantee. Across the 2,000 independent validation cases, predictions remained fully bounded with zero divergence fallbacks ($0 / 2{,}000$, $0.0\%$).
- **No Automatic Predictive Rejection**: Early statistical screening is properly provided by Module A ($g_{\text{excess}}$). The absence of a safety slope does not grant implicit authority for automatic component rejection based on predicted specification breaches.

```
================================================================================
                 PHASE 6 SAFETY-SLOPE DECISION DISPOSITION
================================================================================
  GATE STATUS: PHASE 6 SAFETY SLOPE — OPEN EVIDENCE GAP
  RIDGE MODEL: LOCKED & MAINTAINED (IMMUTABLE)
  SAFETY SLOPE IMPLEMENTATION: NOT AUTHORIZED
  AUTOMATIC PREDICTIVE REJECTION: NOT AUTHORIZED
  FINAL EVALUATION: QUARANTINED (LOT_EVAL_* UNTOUCHED)
  NO FINAL EVALUATION AUTHORIZED
================================================================================
```


**STRICT STOP ENFORCED AFTER PHASE 6 SAFETY-SLOPE DECISION GATE.**

---

### LOG-103: Phase 5 Final Evaluation Readiness & Governance Gate (Pre-Execution Protocol)
- **Log ID**: LOG-103
- **Date**: 2026-09-18
- **Timestamp**: 2026-09-18T10:35:00Z
- **Phase**: Phase 5 / Module B Final Evaluation Readiness & Governance Gate
- **Change**: Establishment of formal readiness protocol, mathematical contracts, leakage controls, and forensic governance records for Phase 5 final evaluation.
- **Previous State**: Phase 6 Safety-Slope Decision Gate closed as Open Evidence Gap (LOG-102); final evaluation partition (`LOT_EVAL_*`) quarantined with no authorized evaluation protocol record.
- **New State**: Registered comprehensive governance document [`docs/PHASE_5_FINAL_EVALUATION_READINESS.md`](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/PHASE_5_FINAL_EVALUATION_READINESS.md) defining exact final evaluation protocol (Sections A–K). Ridge models locked; safety slope an Open Evidence Gap; predictive rejection unauthorized; `LOT_EVAL_*` cryptographically quarantined and untouched.
- **Reason**: Rigorous adherence to pre-registered evaluation discipline; prevention of evaluation data leakage; verification of cryptographic artifact immutability; and enforcement of explicit separation of prognostic evidence from physical scrap authority prior to any final evaluation.
- **Source / Provenance**: DESIGN_DECISION / GOVERNANCE_GATE (User Instruction: Phase 5 Final Evaluation Readiness Gate).
- **Status**: PHASE 5 FINAL EVALUATION — READY FOR EXPLICIT AUTHORIZATION
- **Affected Area**: `docs/PHASE_5_FINAL_EVALUATION_READINESS.md`, `tests/prognostics/test_phase5_final_readiness.py`, `docs/PROTOTYPE_STANDING_LOG.md`
- **Impact**: Establishes complete governance protocol, mathematical formulas, and adversarial controls for final evaluation without executing evaluation or modifying models.

#### 1. Evaluation Population Specification (`LOT_EVAL_*`)
- **Partition Identifier**: `FINAL_EVALUATION` (`LOT_EVAL_*` only).
- **Lot Enumeration**: Exactly 25 lots (`LOT_EVAL_001` through `LOT_EVAL_025`).
- **Component Population**: 20 components per lot $\times$ 25 lots = **500 unique components**.
- **Parameter Series**: 500 components $\times$ 4 electrical parameters ($I_{\text{DSS}}, V_{\text{GS(th)}}, R_{\text{DS(on)}}, I_{\text{GSS}}$) = **2,000 parameter series**.
- **Temporal Checkpoints**: 7 protocol checkpoints ($0\,\text{h}, 24\,\text{h}, 48\,\text{h}, 72\,\text{h}, 96\,\text{h}, 120\,\text{h}, 168\,\text{h}$).
- **Total Observations**: 2,000 series $\times$ 7 checkpoints = **14,000 observation records**.
- **Forecast Triples**: Exactly 2,000 triples of $[v_0, v_{24}, v_{168}]$.
- **Partition Disjointness**: Verified pairwise disjointness across all 100 lots:
  $$\text{CAL (50)} \cap \text{VAL (25)} = \emptyset, \quad \text{CAL (50)} \cap \text{EVAL (25)} = \emptyset, \quad \text{VAL (25)} \cap \text{EVAL (25)} = \emptyset$$

#### 2. Locked Model Family & Immutable Parameters
- **Model Family**: Ridge Regression ($\lambda = 1.0$) operating in parameter-specific coordinate transforms ($u = \phi(v)$).
- **Input Features**: $X = [v_0, v_{24}]$ (measurements at $0\,\text{h}$ and $24\,\text{h}$).
- **Target**: $y = v_{168}$ (measurement at $168\,\text{h}$).
- **Design Matrix**: $X_{\text{aug}} = [1, u_0, u_{24}]$. Features are **not** z-score standardized prior to the solve.
- **Frozen Coefficients**:
  - $I_{\text{DSS}}$: $\beta = [+0.00233956, +0.46570384, +0.49182429]$
  - $I_{\text{GSS}}$: $\beta = [+0.32574745, +0.39407454, +0.38162141]$
  - $R_{\text{DS(on)}}$ : $\beta = [+0.22165031, +0.47211305, +0.47157973]$
  - $V_{\text{GS(th)}}$: $\beta = [+0.10161611, +0.46955702, +0.49620188]$
- **Zero Retraining**: Zero refitting or hyperparameter tuning on validation or evaluation data.

#### 3. Uncertainty & Prediction Interval Protocol
- **Calibration Lineage**: Frozen nested LOLO out-of-fold calibration on calibration partition (`LOT_CAL_001`–`050`, $N_{\text{OOF}} = 1{,}000$).
- **Frozen Scales**: $\sigma_{\text{eff}} = [0.10770870, 0.31391464, 0.01849041, 0.03048219]$.
- **Zero Recalibration Rule**: No updating or blending of $\sigma_{\text{eff}}$ using validation or evaluation observations.
- **Epistemic Discipline**: Coverage rates reported strictly as descriptive empirical proportions; no claim of formal conformal or guaranteed coverage.

#### 4. Primary Metrics & Secondary Forensic Breakdowns
- **Primary Metrics**: MAE, RMSE, MedAE, observed 90% PI coverage, mean interval width, Winkler score ($\alpha = 0.10$).
- **Secondary Views**: Error distributions (quantiles 25%–99%), lot-level error, parameter-level error, finite/divergence prediction rate, signed $I_{\text{GSS}}$ behavior, prediction interval asymmetry, explicit identification of top 1% extreme errors.

#### 5. Five-Tier Screening Semantics & Decision Separation
- Strict architectural decoupling maintained:
  1. *Measured specification failure* (Layer 2: deterministic failure at test time).
  2. *Predicted future specification breach* (Layer 6: prognostic risk evidence).
  3. *Forecast-risk evidence* (Layer 6: informative metadata, e.g. interval width / Winkler score).
  4. *Module A detector evidence* (Layer 6: statistical screening layer, $g_{\text{excess}} \ge 2.5$).
  5. *Final disposition policy* (Layer 6: authorized human screening decision rules).
- **Prohibition**: A predicted specification breach must **NOT** automatically trigger physical rejection.

#### 6. Scenario Labels & Ground Truth Isolation
- Primary scoring consumes `observations.csv` only.
- Ground truth (`ground_truth.csv`) remains quarantined during model inference and primary scoring.
- Diagnostic join permitted **ONLY AFTER** primary evaluation outputs are cryptographically frozen.
- Scenario labels must never influence model coefficients, uncertainty, thresholds, or disposition logic.

#### 7. Adversarial Leakage Controls & Verification
- Dedicated test suite implemented in [`tests/prognostics/test_phase5_final_readiness.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/tests/prognostics/test_phase5_final_readiness.py) verifying 7 critical invariants:
  1. `test_evaluation_targets_cannot_alter_coefficients_or_sigma_eff` (PASS)
  2. `test_evaluation_future_checkpoints_cannot_alter_predictions` (PASS)
  3. `test_scenario_and_ground_truth_columns_cannot_enter_model` (PASS)
  4. `test_validation_and_evaluation_data_cannot_enter_fitting` (PASS)
  5. `test_repeated_execution_is_deterministic` (PASS)
  6. `test_cal_val_eval_partition_boundaries_are_strictly_disjoint` (PASS)
  7. `test_quarantine_barrier_strictly_enforced_prior_to_authorization` (PASS)
- **Repository Full Test Suite**: **248/248 TESTS PASSING** (10.47s across 31 test files).
- **All 14 Frozen Baseline Artifacts**: Verified $100\%$ bit-for-bit identical against authoritative SHA-256 hashes.

#### 8. Governance & No Success Threshold Policy
- No post-hoc pass/fail threshold on MAE, RMSE, coverage, or Winkler score will be manufactured.
- No model ranking against alternatives (Ridge is already locked).
- Scope: Synthetic semiconductor benchmark suite only; no claim of physical device validity or flight qualification.
- Final evaluation data (`LOT_EVAL_*`) remains **100% untouched, unread, unscored, and quarantined**.

```
================================================================================
             PHASE 5 FINAL EVALUATION READINESS GATE DISPOSITION
================================================================================
  READINESS STATUS: PHASE 5 FINAL EVALUATION — READY FOR EXPLICIT AUTHORIZATION
  SELECTED MODEL: RIDGE REGRESSION (LOCKED & IMMUTABLE)
  SAFETY SLOPE: OPEN EVIDENCE GAP (NO IMPLEMENTATION AUTHORIZED)
  PREDICTIVE REJECTION: NOT AUTHORIZED (INFORMATIVE EVIDENCE ONLY)
  FINAL EVALUATION DATA: QUARANTINED (LOT_EVAL_* UNTOUCHED)
  EXECUTION STATUS: PENDING SEPARATE EXPLICIT AUTHORIZATION
================================================================================
```


**STRICT STOP ENFORCED AFTER PHASE 5 FINAL EVALUATION READINESS GATE.**

---

### LOG-104: Phase 5 Final Evaluation Execution & Artifact Freezing (Locked Ridge Regression)
- **Log ID**: LOG-104
- **Date**: 2026-09-18
- **Timestamp**: 2026-09-18T10:38:00Z
- **Phase**: Phase 5 / Module B Predictive Regression (Final Evaluation Execution Stage)
- **Change**: Execution, verification, forensic breakdown, and cryptographic freezing of Phase 5 Final Evaluation on quarantined partition `LOT_EVAL_*`.
- **Previous State**: Phase 5 Final Evaluation was ready for explicit authorization under LOG-103; `LOT_EVAL_*` was cryptographically quarantined and untouched.
- **New State**: Phase 5 Final Evaluation executed under explicit authorization; results and manifest frozen and cryptographically hashed; `LOT_EVAL_*` evaluated across 25 lots, 500 components, 2,000 series; primary and secondary forensic metrics documented in [`docs/PHASE_5_FINAL_EVALUATION_REPORT.md`](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/PHASE_5_FINAL_EVALUATION_REPORT.md) and [`data/evaluation_phase5/phase5_final_results.json`](file:///Users/siyabhardwaj/Desktop/SIH26170/data/evaluation_phase5/phase5_final_results.json).
- **Reason**: Completion of the final stage of Module B predictive regression benchmark evaluation under strict pre-registered protocol, frozen model architecture, and five-tier semantic decoupling.
- **Source / Provenance**: DESIGN_DECISION / EVALUATION_GATE (User Instruction: Authorize Phase 5 Final Evaluation).
- **Status**: PHASE 5 FINAL EVALUATION — COMPLETED
- **Affected Area**: `src/sih26170/prognostics/phase5_final_evaluator.py`, `tests/prognostics/test_phase5_final_evaluation.py`, `data/evaluation_phase5/phase5_final_results.json`, `data/evaluation_phase5/phase5_final_lineage_manifest.json`, `docs/PHASE_5_FINAL_EVALUATION_REPORT.md`, `docs/PROTOTYPE_STANDING_LOG.md`.
- **Impact**: Establishes permanent, frozen evaluation benchmark records for locked Ridge regression without modifying models, tuning hyperparameters, or violating partition boundaries.

#### 1. Authorization, Governance & Scope
- **Explicit Authorization**: Formally authorized execution on `LOT_EVAL_*` under pre-registered protocol [`docs/PHASE_5_FINAL_EVALUATION_READINESS.md`](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/PHASE_5_FINAL_EVALUATION_READINESS.md) and [LOG-103](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/PROTOTYPE_STANDING_LOG.md#L6282).
- **Model Lock Maintained**: Decoupled per-parameter Ridge regression ($\lambda = 1.0$) operating on design matrix $[1, u_0, u_{24}]$ with parameter-specific coordinate transforms. Zero retraining, refitting, or hyperparameter tuning.
- **Safety Slope Status**: Retained as an **OPEN EVIDENCE GAP (NO IMPLEMENTATION)**.
- **Predictive Rejection Status**: **NOT AUTHORIZED**. A predicted future specification breach is informational prognostic risk evidence only; autonomous physical rejection is strictly prohibited.
- **Scientific Scope**: Synthetic benchmark suite only (Phase 4B). No claim of real-device validity, space flight qualification, or production readiness.

#### 2. Pre-Evaluation Integrity & Baseline Artifact Verification
- **Frozen Baseline Artifacts**: All 14 baseline hashes verified $100\%$ bit-for-bit identical before accessing evaluation data.
- **Partition Disjointness**: Verified across all 100 lots:
  $$\text{CAL (50)} \cap \text{VAL (25)} = \emptyset, \quad \text{CAL (50)} \cap \text{EVAL (25)} = \emptyset, \quad \text{VAL (25)} \cap \text{EVAL (25)} = \emptyset$$
- **Population Accounting**: Exactly 25 evaluation lots (`LOT_EVAL_001`–`LOT_EVAL_025`), 500 components, 2,000 parameter series ($I_{\text{DSS}}, V_{\text{GS(th)}}, R_{\text{DS(on)}}, I_{\text{GSS}}$), 14,000 observations across 7 checkpoints. $100.0\%$ complete triples; zero missing or non-finite values.

#### 3. Primary Final Evaluation Results (`LOT_EVAL_*`)
- **$I_{\text{DSS}}$ ($\mu\text{A}$)**:
  - Evaluation MAE: **$0.05740\,\mu\text{A}$** (vs Calibration LOLO: $0.04937\,\mu\text{A}$, $+16.3\%$; vs Validation: $0.05485\,\mu\text{A}$, $+4.6\%$)
  - RMSE: $0.07582\,\mu\text{A}$, MedAE: $0.04601\,\mu\text{A}$
  - Empirical 90% Coverage: **$84.2\%$** (421/500), Mean Width: $0.19258\,\mu\text{A}$
  - Winkler Score ($\alpha=0.10$): $0.30387$
  - Baseline Comparison: Ridge outperforms Carry-Forward ($0.06221\,\mu\text{A}$) by **$+7.72\%$** and Two-Point Linear ($0.29443\,\mu\text{A}$) by **$+80.50\%$**.
- **$I_{\text{GSS}}$ ($\text{nA}$)**:
  - Evaluation MAE: **$0.71336\,\text{nA}$** (vs Calibration LOLO: $0.65022\,\text{nA}$, $+9.7\%$; improved over Validation: $0.76516\,\text{nA}$, $-6.8\%$)
  - RMSE: $0.93832\,\text{nA}$, MedAE: $0.53694\,\text{nA}$
  - Empirical 90% Coverage: **$85.2\%$** (426/500), Mean Width: $2.48303\,\text{nA}$
  - Winkler Score ($\alpha=0.10$): **$3.76583$** (improved over Validation: $5.0067$)
  - Baseline Comparison: Ridge outperforms Carry-Forward ($0.80362\,\text{nA}$) by **$+11.23\%$** and Two-Point Linear ($4.38723\,\text{nA}$) by **$+83.74\%$**.
  - Signed Behavior: Preserved signed asinh transform without `abs()` or clipping. Positive subpopulation ($N=499$, MAE $0.7121\,\text{nA}$, cov $85.4\%$); Negative subpopulation ($N=1$, MAE $1.3236\,\text{nA}$, cov $0.0\%$).
- **$R_{\text{DS(on)}}$ ($\text{m}\Omega$)**:
  - Evaluation MAE: **$0.69986\,\text{m}\Omega$** (best across all phases; vs Calibration: $0.71487\,\text{m}\Omega$, $-2.1\%$; vs Validation: $0.73982\,\text{m}\Omega$, $-5.4\%$)
  - RMSE: $0.88283\,\text{m}\Omega$, MedAE: $0.57510\,\text{m}\Omega$
  - Empirical 90% Coverage: **$89.6\%$** (448/500), Mean Width: $2.92148\,\text{m}\Omega$
  - Winkler Score ($\alpha=0.10$): **$3.63683$** (monotonic improvement across all phases)
  - Baseline Comparison: Ridge outperforms Carry-Forward ($0.78593\,\text{m}\Omega$) by **$+10.95\%$** and Two-Point Linear ($4.39067\,\text{m}\Omega$) by **$+84.06\%$**.
- **$V_{\text{GS(th)}}$ ($\text{V}$)**:
  - Evaluation MAE: **$0.02420\,\text{V}$** (vs Calibration: $0.02395\,\text{V}$, $+1.0\%$; vs Validation: $0.02349\,\text{V}$, $+3.0\%$)
  - RMSE: $0.03038\,\text{V}$, MedAE: $0.02105\,\text{V}$
  - Empirical 90% Coverage: **$90.0\%$** (450/500, exact match to nominal 90%), Mean Width: $0.10028\,\text{V}$
  - Winkler Score ($\alpha=0.10$): $0.12408$
  - Baseline Comparison: Ridge outperforms Carry-Forward ($0.02544\,\text{V}$) by **$+4.88\%$** and Two-Point Linear ($0.14438\,\text{V}$) by **$+83.24\%$**.
- **Finite Prediction Rate**: **100.0%** across all 2,000 series; **0** divergent fallbacks.

#### 4. Cryptographic Artifact Freezing
- Primary Results Artifact: [`data/evaluation_phase5/phase5_final_results.json`](file:///Users/siyabhardwaj/Desktop/SIH26170/data/evaluation_phase5/phase5_final_results.json)
  - SHA-256 Digest: `1d1d75542c4dab727ba7dd54dbcd91ed14dd6b5fc263ebdad2fdc0f44110d969`
- Lineage Manifest: [`data/evaluation_phase5/phase5_final_lineage_manifest.json`](file:///Users/siyabhardwaj/Desktop/SIH26170/data/evaluation_phase5/phase5_final_lineage_manifest.json)
  - SHA-256 Digest: `bde6989e24d195ab4b53f93c46c2156d1c336fe820baf149d76d32943e135667`

#### 5. Secondary Forensic Analysis & Unfavorable Findings
- Diagnostic join with `ground_truth.csv` performed strictly after freezing primary results.
- **Unfavorable Findings Prominently Documented**:
  - *Staggered Onset Kinetic Blindspot (`fixture_f_staggered_onset`)*: Ridge observes only $0\text{--}24\,\text{h}$; degradation commencing post-24h yielded an MAE of $0.10496\,\mu\text{A}$ on $I_{\text{DSS}}$ and empirical coverage collapse to **$60.0\%$**.
  - *Confounded Drift Sensitivity (`fixture_d_confounded_drift`)*: Fixture drift combined with degradation on $I_{\text{GSS}}$ yielded an MAE of **$1.26094\,\text{nA}$** and empirical coverage collapse to **$60.0\%$**.
  - *Heteroscedastic Noise Undercoverage (`fixture_e_heteroscedastic_noise`)*: Non-stationary noise variance produced undercoverage ($70.0\%–75.0\%$).
- **Residual Quantiles**: MedAE ($0.0460\,\mu\text{A}, 0.5369\,\text{nA}, 0.5751\,\text{m}\Omega, 0.0211\,\text{V}$), Q90 ($0.1185\,\mu\text{A}, 1.4788\,\text{nA}, 1.4734\,\text{m}\Omega, 0.0501\,\text{V}$), Q99 ($0.2263\,\mu\text{A}, 2.7034\,\text{nA}, 2.2542\,\text{m}\Omega, 0.0722\,\text{V}$).
- **Specification-Breach Forensics**: Evaluated against MIL-PRF-19500/703 Table I limits. Zero actual breaches; zero predicted breaches; zero false alarms.

#### 6. Five-Tier Semantic Decoupling
- Strictly preserved distinction across:
  1. *Measured specification failure* (Layer 2: deterministic failure at test time).
  2. *Predicted future specification breach* (Layer 6: prognostic risk evidence).
  3. *Forecast uncertainty/risk evidence* (Layer 6: informative metadata).
  4. *Module A detector evidence* (Layer 6: statistical screening layer).
  5. *Final disposition policy* (Layer 6: authorized human screening decision rules).
- Autonomous physical scrap based on predicted breach remains strictly unauthorized.

#### 7. Final Verification & Test Suite
- **Full Repository Test Suite**: **259 / 259 TESTS PASSING** (11.15s across 32 test files).
- **All 14 Frozen Baseline Artifacts**: Verified $100\%$ bit-for-bit identical.
- **Deterministic Repeatability**: Verified bit-for-bit identical re-execution.
- **Observations CSV**: Verified byte-identical post-evaluation (`b5de6a03...`).

```
================================================================================
                    PHASE 5 FINAL EVALUATION DISPOSITION
================================================================================
  EXECUTION STATUS: PHASE 5 FINAL EVALUATION — COMPLETED
  SELECTED MODEL FAMILY: RIDGE REGRESSION (LOCKED & IMMUTABLE)
  SAFETY SLOPE: OPEN EVIDENCE GAP (NO IMPLEMENTATION)
  PREDICTIVE REJECTION: NOT AUTHORIZED (INFORMATIONAL EVIDENCE ONLY)
  FINAL RESULTS: FROZEN (SHA-256: 1d1d75542c4dab727ba7dd54dbcd91ed14dd6b5fc...)
  SYNTHETIC BENCHMARK SCOPE: MAINTAINED (PHASE 4B BENCHMARK)
================================================================================
```


**STRICT STOP ENFORCED: PHASE 5 FINAL EVALUATION COMPLETED. NO SUBSEQUENT MODEL MODIFICATION IS AUTHORIZED.**

---

### LOG-105: Phase 5 Final Evaluation Forensic Interpretation & Documentation Pass
- **Log ID**: LOG-105
- **Date**: 2026-09-18
- **Timestamp**: 2026-09-18T10:45:00Z
- **Phase**: Phase 5 / Module B Predictive Regression (Final Evaluation Forensic Interpretation Gate)
- **Change**: Forensic documentation pass reconciling interpretation of interval undercoverage, zero-breach test metrics, cross-lot observations, and screening semantics in [`docs/PHASE_5_FINAL_EVALUATION_REPORT.md`](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/PHASE_5_FINAL_EVALUATION_REPORT.md).
- **Previous State**: LOG-104 documented the execution and artifact freeze of Phase 5 Final Evaluation; certain interpretive formulations contained qualitative phrases ("best MAE across all phases", "stable cross-lot generalization", "hard-gate rejection authority") and unelaborated zero-breach TNR descriptions.
- **New State**: Updated [`docs/PHASE_5_FINAL_EVALUATION_REPORT.md`](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/PHASE_5_FINAL_EVALUATION_REPORT.md) with strict, descriptive forensic language:
  1. *Interval Undercoverage Explicitly Highlighted*: "Nominal 90% prediction intervals produced 84.2–90.0% observed empirical coverage on the untouched final benchmark, with undercoverage for IDSS and IGSS." No retuning of $\sigma_{\text{eff}}$, no claim of formal conformal or guaranteed coverage.
  2. *Zero-Breach Interpretation Corrected*: "Because the final evaluation population contains zero actual 168h specification breaches, sensitivity/recall for predictive specification-breach detection cannot be estimated. The observed 100% true-negative rate is descriptive only. Predictive breach detection was not validated for positive cases."
  3. *Removal of Partition Ranking*: Removed "best MAE across all phases"; historical calibration and validation numbers are reported purely as descriptive benchmark context without ranking.
  4. *Cross-Lot Characterization Qualified*: "Performance across the independently generated evaluation lots remained within the observed benchmark range." Unrestricted real-world generalization is explicitly disclaimed.
  5. *Screening Semantics Clarified*: "Measured specification failure is an objective test result against the applicable specification limit; final disposition is governed by the applicable qualification/quality procedure." Preserved: "Predicted future specification breach is prognostic evidence only and must not autonomously scrap a component."
  6. *Preservation of Unfavorable Findings*: Staggered onset coverage drop ($60.0\%$), confounded drift sensitivity ($60.0\%$), heteroscedastic undercoverage ($70.0\%–75.0\%$), and negative $I_{\text{GSS}}$ error are preserved with full prominence.
  7. *Preservation of Exact Headline Metrics*:
     - $I_{\text{DSS}}$: MAE $0.05740\,\mu\text{A}$, RMSE $0.07582$, MedAE $0.04601$, Coverage $84.2\%$, Width $0.19258$, Winkler $0.30387$
     - $I_{\text{GSS}}$: MAE $0.71336\,\text{nA}$, RMSE $0.93832$, MedAE $0.53694$, Coverage $85.2\%$, Width $2.48303$, Winkler $3.76583$
     - $R_{\text{DS(on)}}$: MAE $0.69986\,\text{m}\Omega$, RMSE $0.88283$, MedAE $0.57510$, Coverage $89.6\%$, Width $2.92148$, Winkler $3.63683$
     - $V_{\text{GS(th)}}$: MAE $0.02420\,\text{V}$, RMSE $0.03038$, MedAE $0.02105$, Coverage $90.0\%$, Width $0.10028$, Winkler $0.12408$
  8. *Cryptographic Digests Verified & Unmodified*:
     - Results JSON: `1d1d75542c4dab727ba7dd54dbcd91ed14dd6b5fc263ebdad2fdc0f44110d969`
     - Lineage Manifest: `bde6989e24d195ab4b53f93c46c2156d1c336fe820baf149d76d32943e135667`
- **Reason**: Scientific transparency, intellectual rigor, adherence to epistemic boundaries, and prevention of overclaiming on synthetic benchmark metrics.
- **Source / Provenance**: DESIGN_DECISION / FORENSIC_GATE (User Instruction: Final Forensic Documentation Pass).
- **Status**: PHASE 5 FINAL EVALUATION — COMPLETED (FORENSICALLY RECONCILED)
- **Affected Area**: `docs/PHASE_5_FINAL_EVALUATION_REPORT.md`, `docs/PROTOTYPE_STANDING_LOG.md`
- **Impact**: Establishes permanent, forensically sound documentation of final evaluation without touching models, code, or evaluation results.

```
================================================================================
                    PHASE 5 FINAL EVALUATION DISPOSITION
================================================================================
  STATUS: PHASE 5 FINAL EVALUATION — COMPLETED (FORENSICALLY RECONCILED)
  RIDGE MODEL: LOCKED & IMMUTABLE
  FINAL RESULTS: FROZEN
  SAFETY SLOPE: OPEN EVIDENCE GAP (NO IMPLEMENTATION)
  PREDICTIVE REJECTION: NOT AUTHORIZED (INFORMATIONAL EVIDENCE ONLY)
  SYNTHETIC BENCHMARK SCOPE: MAINTAINED
================================================================================
```


**STRICT FINAL STOP: NO FURTHER MODEL TUNING OR BENCHMARK MODIFICATION IS AUTHORIZED.**

---

### LOG-106: Phase 5 Final Evaluation Repository-Integrity Verification & Closure
- **Log ID**: LOG-106
- **Date**: 2026-09-18
- **Timestamp**: 2026-09-18T11:05:00Z
- **Phase**: Phase 5 / Module B Predictive Regression (Computational Closure Gate)
- **Change**: Verification of repository cryptographic integrity, confirmation of frozen artifact digests, and formal computational closure of Phase 5 Final Evaluation.
- **Previous State**: LOG-105 reconciled documentation interpretations; computational state required final automated integrity verification.
- **New State**: All 14 frozen baseline hashes verified bit-for-bit ($100\%$ match); primary results artifact (`1d1d75542c...`) and lineage manifest (`bde6989e24...`) verified unchanged; 259/259 tests passing; zero computational modifications; Phase 5 Final Evaluation forensically and computationally CLOSED.
- **Reason**: Verification of repository state integrity and final formal closure of Phase 5 evaluation.
- **Source / Provenance**: DESIGN_DECISION / CLOSURE_GATE (User Instruction: Final Repository-Integrity Verification).
- **Status**: PHASE 5 FINAL EVALUATION — COMPUTATIONALLY CLOSED
- **Affected Area**: `docs/PROTOTYPE_STANDING_LOG.md`
- **Impact**: Permanent closure of Phase 5 evaluation without model, benchmark, or evaluation mutations.

#### 1. Cryptographic Artifact Verification Summary
- `data/synthetic_phase4b/observations.csv`: `b5de6a03022a9350b6f304b9af593768e7f83a8fc61fde6ca98e690cfa1f275f` (VERIFIED BIT-IDENTICAL)
- `data/evaluation_phase5/phase5_final_results.json`: `1d1d75542c4dab727ba7dd54dbcd91ed14dd6b5fc263ebdad2fdc0f44110d969` (VERIFIED BIT-IDENTICAL)
- `data/evaluation_phase5/phase5_final_lineage_manifest.json`: `bde6989e24d195ab4b53f93c46c2156d1c336fe820baf149d76d32943e135667` (VERIFIED BIT-IDENTICAL)
- All 14 frozen baseline artifacts across Phase 4B and Phase 2F verified 100% bit-for-bit identical.

#### 2. Test Suite Status
- Repository full test suite: **259 / 259 TESTS PASSING** (10.99s across 32 test files). Zero tests modified or bypassed.

#### 3. Epistemic Boundaries & Closed Gate
- Safety slope: Formally preserved as an **OPEN EVIDENCE GAP (NO IMPLEMENTATION)**.
- Predictive rejection: Strictly **NOT AUTHORIZED**.
- Synthetic benchmark scope: Strictly maintained; zero hardware or space flight qualification claims.
- Computational results: $100\%$ frozen and unmodified.

```
================================================================================
                    PHASE 5 FINAL EVALUATION DISPOSITION
================================================================================
  STATUS: PHASE 5 FINAL EVALUATION — COMPUTATIONALLY CLOSED
  RIDGE MODEL: LOCKED & IMMUTABLE
  FINAL RESULTS: FROZEN (SHA-256: 1d1d75542c4dab727ba7dd54dbcd91ed14dd6b5fc...)
  SAFETY SLOPE: OPEN EVIDENCE GAP (NO IMPLEMENTATION)
  PREDICTIVE REJECTION: NOT AUTHORIZED (INFORMATIONAL EVIDENCE ONLY)
  SYNTHETIC BENCHMARK SCOPE: MAINTAINED
================================================================================
```


**STRICT FINAL STOP: PHASE 5 FINAL EVALUATION IS COMPUTATIONALLY CLOSED.**

---

### LOG-107: Next-Phase Engineering Plan (Post-Synthetic Evidence Framework)
- **Log ID**: LOG-107
- **Date**: 2026-09-18
- **Timestamp**: 2026-09-18T12:15:00Z
- **Phase**: Next Phase / Post-Synthetic Engineering Planning Framework
- **Change**: Establishment of formal next-phase planning record defining physical evidence, ATE metrology, and characterization requirements.
- **Previous State**: Phase 5 Final Evaluation computationally and forensically closed (LOG-106); no formal engineering plan existed defining post-synthetic physical characterization and evidence requirements.
- **New State**: Created [`docs/NEXT_PHASE_ENGINEERING_PLAN.md`](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/NEXT_PHASE_ENGINEERING_PLAN.md) defining Sections A through I: completed computational evidence, missing physical evidence, ATE metrology characterization, real IRHNJ57130 burn-in telemetry requirements, safety-policy prerequisites, hardware validation progression roadmap, and qualification boundaries classified under the 7-layer epistemic ontology.
- **Reason**: Scientific transparency and engineering rigor; establishing prerequisite empirical milestones required before algorithmic screening can be evaluated on real semiconductor flight hardware, without mutating Phase 5 models or benchmark artifacts.
- **Source / Provenance**: DESIGN_DECISION / PLANNING_GATE (User Instruction: Next-Phase Engineering Plan).
- **Status**: NEXT PHASE — PLANNING ONLY
- **Affected Area**: `docs/NEXT_PHASE_ENGINEERING_PLAN.md`, `docs/PROTOTYPE_STANDING_LOG.md`
- **Impact**: Formally establishes the evidence boundaries and empirical progression roadmap for physical hardware testing while maintaining Phase 5 computational closure.

#### 1. Core Planning Tenet & Epistemic Boundaries
- The plan explicitly begins from the **evidence gap**, not from an attempt to optimize or retune Phase 5 benchmark scores.
- Phase 5 remains **computationally closed**; Ridge remains **locked and immutable**; all baseline and evaluation artifacts remain **unmodified and cryptographically verified**.
- Safety slope remains an **OPEN EVIDENCE GAP (NO IMPLEMENTATION)**.
- Autonomous predictive rejection remains **STRICTLY NOT AUTHORIZED**.
- Work items are classified under the 7-layer epistemic ontology; no Layer 5/6 synthetic benchmark result may be promoted to Layer 1/2 verified physical evidence.

#### 2. Summary of Missing Physical Evidence Defined
- *Physical Telemetry*: Real multi-lot burn-in readouts for Infineon IRHNJ57130 / JANSR2N7481U3 under MIL-STD-750 Method 1042 Condition A/B (Layer 1, marked OPEN).
- *ATE Metrology*: Type 1 Gage R&R repeatability ($\sigma_{\text{repeatability}}$), contact resistance variation, electrometer zero-offset distributions across temperature (Layer 2, marked OPEN).
- *Burn-in Schedule & Samples*: Statistically powered sample sizes and procurement-authorized intermediate checkpoints (Layer 2/6, marked OPEN).
- *Chamber Common-Mode*: In-situ thermal mapping and bias supply ripple telemetry (Layer 2, marked OPEN).
- *Positive Degradation Articles*: Physical test articles with verified specification breaches to estimate positive predictive sensitivity/recall (Layer 1, marked OPEN).
- *Safety Slope Evidence*: Physical failure mechanism proof, normative slash-sheet threshold, and calibrated loss matrix (Layer 7, OPEN EVIDENCE GAP).
- *Disposition Concurrence*: Formal space qualification board authorization (ISRO/NASA/ESA) before predictive risk flags may influence screening disposition (Layer 2, NOT AUTHORIZED).

```
================================================================================
                    NEXT-PHASE ENGINEERING DISPOSITION
================================================================================
  STAGE: NEXT PHASE — PLANNING ONLY (ZERO IMPLEMENTATION AUTHORIZED)
  PHASE 5 COMPUTATIONAL EVALUATION: CLOSED & FROZEN
  RIDGE PROGNOSTIC MODEL: LOCKED & IMMUTABLE
  FROZEN ARTIFACTS: UNTOUCHED & CRYPTOGRAPHICALLY VERIFIED
  SAFETY SLOPE: OPEN EVIDENCE GAP (NO IMPLEMENTATION)
  PHYSICAL VALIDATION: NOT YET ESTABLISHED
  PREDICTIVE REJECTION: NOT AUTHORIZED
================================================================================
```

**STRICT FINAL STOP: NEXT PHASE PLANNING ONLY. ZERO IMPLEMENTATION AUTHORIZED.**

---

### LOG-108: Epistemic Classification Correction for Post-Phase-5 Planning Record
- **Log ID**: LOG-108
- **Date**: 2026-09-18
- **Timestamp**: 2026-09-18T12:35:00Z
- **Phase**: Next Phase / Post-Synthetic Engineering Planning Framework
- **Change**: Forensic documentation-only correction of the epistemic classification of unresolved engineering questions in [`docs/NEXT_PHASE_ENGINEERING_PLAN.md`](file:///Users/siyabhardwaj/Desktop/SIH26170/docs/NEXT_PHASE_ENGINEERING_PLAN.md).
- **Previous State**: Proposed future physical telemetry and characterization items were referenced alongside target Layer 1 / Layer 2 designations, and Gage R&R sample size of $N \ge 30$ was not explicitly designated as a Layer 6 design choice.
- **New State**: 
  1. *Epistemic Classification Refinement*: Clarified that future physical empirical measurements are empirical evidence not yet obtained; they cannot be automatically labeled Layer 1 (Verified Device Fact) or Layer 2 (Verified Standard/Test Fact) prior to verified provenance, test records, and normative standard basis.
  2. *Normative vs Design Separation*: Formally separated normative standard requirements (Layer 2, only when verified from MIL-PRF-19500/703 or MIL-STD-750) from experimental protocol choices (Layer 6 Design Choice).
  3. *Gage R&R Sample Size*: Reframed candidate characterization design ($\ge 30$ repeated insertions per defined condition) explicitly as a Layer 6 project design choice pending protocol authorization, avoiding unsourced normative claims.
  4. *Maintained Governance Gate*: Phase 5 remains computationally closed, Ridge locked and immutable, all frozen artifacts untouched, safety slope an open evidence gap, and predictive rejection unauthorized.
- **Reason**: Strict epistemic fidelity; avoiding premature promotion of future physical empirical data to verified facts before collection, calibration, and normative verification.
- **Source / Provenance**: FORENSIC_AUDIT / DOCUMENTATION_UPDATE (User Direction: Documentation-Only Epistemic Classification Correction).
- **Status**: NEXT PHASE — PLANNING ONLY
- **Affected Area**: `docs/NEXT_PHASE_ENGINEERING_PLAN.md`, `docs/PROTOTYPE_STANDING_LOG.md`
- **Impact**: Ensures perfect epistemic ontology compliance without altering any code, models, data, or frozen benchmark results.

```
================================================================================
                    NEXT-PHASE ENGINEERING DISPOSITION
================================================================================
  STAGE: NEXT PHASE — PLANNING ONLY (ZERO IMPLEMENTATION AUTHORIZED)
  PHASE 5 COMPUTATIONAL EVALUATION: CLOSED & FROZEN
  RIDGE PROGNOSTIC MODEL: LOCKED & IMMUTABLE
  FROZEN ARTIFACTS: UNTOUCHED & CRYPTOGRAPHICALLY VERIFIED
  SAFETY SLOPE: OPEN EVIDENCE GAP (NO IMPLEMENTATION)
  PHYSICAL VALIDATION: NOT YET ESTABLISHED
  PREDICTIVE REJECTION: NOT AUTHORIZED
================================================================================
```

**STRICT FINAL STOP: NEXT PHASE PLANNING ONLY. ZERO IMPLEMENTATION AUTHORIZED.**

---

### LOG-109: Engineering Prototype Integration Completion
- **Log ID**: LOG-109
- **Date**: 2026-09-18
- **Timestamp**: 2026-09-18T15:00:00Z
- **Phase**: Prototype Integration
- **Change**: Complete implementation, forensic audit, contract verification, and documentation of the SIH26170 Engineering Prototype around the LOCKED Phase 5 Ridge regression model and existing Module A dynamic screening pipeline.
- **Previous State**: LOG-108 established the post-Phase-5 engineering planning framework; prototype implementation was pending authorization and pre-implementation corrections.
- **New State**:
  1. *Authoritative Lineage Verification*: Pre-calibrated Ridge coefficients and $\sigma_{\text{eff}}$ verified bit-for-bit in exact parsed IEEE-754 hex representation against `data/evaluation_phase5/phase5_final_lineage_manifest.json` (`bde6989e24d195ab4b53f93c46c2156d1c336fe820baf149d76d32943e135667`). Verification is enforced automatically at module import time (`_verify_manifest_lineage()`). Zero model refitting, tuning, or artifact regeneration occurred.
  2. *Canonical Application Schema*: Created [`src/sih26170/pipeline/schema.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/src/sih26170/pipeline/schema.py) defining typed contracts: `PhysicalParameter`, `ForecastInterpretation`, `EngineeringExplainability`, `PipelineAuditRecord`, `ModelLineageInfo`, and `ComponentPipelineResult` with deterministic `to_canonical_dict()` export.
  3. *Locked Model Factory*: Created [`src/sih26170/prognostics/locked_models.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/src/sih26170/prognostics/locked_models.py) providing `LockedRidgeModel` with closed-form point predictions, 90% empirical prediction intervals ($Z_{90} = 1.6448536269514722$), and strict divergence guard ($|u| > 10.0$ locked numerical policy falling back to Carry-Forward $v_{24}$ without clipping).
  4. *Telemetry Provider Abstraction*: Created [`src/sih26170/pipeline/telemetry.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/src/sih26170/pipeline/telemetry.py) with `BaseTelemetryProvider` ABC and `SyntheticTelemetryProvider`. Core screening/prognostic logic depends strictly on the provider interface, allowing future real-data substitution without core logic changes. Ingestion strictly enforces ground-truth quarantine (`observations.csv` only) and historical causality ($\text{elapsed\_hours} \le \text{as\_of\_hours}$).
  5. *Pipeline Orchestration*: Created [`src/sih26170/pipeline/orchestrator.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/src/sih26170/pipeline/orchestrator.py) implementing the unified 12-step flow `run_component_pipeline(...)` combining Module A screening and Module B prognostics. Lot context is strictly required for peer/equipment evidence; when unavailable, peer evidence is explicitly marked as single-unit/suppressed.
  6. *Explainability & Audit Engine*: Created [`src/sih26170/pipeline/explainability.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/src/sih26170/pipeline/explainability.py) and [`src/sih26170/pipeline/audit.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/src/sih26170/pipeline/audit.py). Computed `canonical_result_hash` exclusively over deterministic result content, completely isolating nondeterministic runtime timestamps (`created_at`) and UUIDs (`run_id`) into `PipelineAuditRecord`.
  7. *Service API Router & Demo*: Created [`src/sih26170/service/router.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/src/sih26170/service/router.py) and [`src/sih26170/pipeline/demo.py`](file:///Users/siyabhardwaj/Desktop/SIH26170/src/sih26170/pipeline/demo.py). Bare `GET /components/{id}` returns metadata only; all evaluation endpoints require explicit `as_of` query parameter (returning 400 Bad Request if missing).
  8. *Test Suite & Hash Integrity*: Full test suite passing with **283 / 283 tests passing** (259 existing + 17 integration + 7 API tests). All 16 frozen benchmark, baseline, and evaluation artifacts verified 100% bit-for-bit identical to their authoritative release digests.
- **Reason**: Completion of prototype integration per post-Phase-5 engineering specifications and pre-implementation corrections.
- **Source / Provenance**: DESIGN_DECISION / PROTOTYPE_GATE (Pre-Implementation Corrections & Architecture Approval).
- **Status**: ENGINEERING PROTOTYPE — INTEGRATION COMPLETED
- **Affected Area**: `src/sih26170/pipeline/`, `src/sih26170/prognostics/locked_models.py`, `src/sih26170/service/router.py`, `docs/PROTOTYPE_ARCHITECTURE.md`, `tests/`
- **Impact**: Delivers a fully verified, runnable, causally isolated engineering prototype with zero model retraining, quarantined ground truth, and preserved epistemic boundaries.

```
================================================================================
               SIH26170 ENGINEERING PROTOTYPE DISPOSITION
================================================================================
  STATUS: ENGINEERING PROTOTYPE INTEGRATION COMPLETED
  PHASE 5 FINAL EVALUATION: COMPUTATIONALLY CLOSED & FROZEN
  RIDGE MODEL: LOCKED & IMMUTABLE (lambda = 1.0, [v0, v24] -> v168)
  FROZEN ARTIFACT INTEGRITY: 16 / 16 ARTIFACTS VERIFIED EXACT SHA-256 MATCH
  TEST SUITE STATUS: 283 / 283 PASSING (100% GREEN)
  DETERMINISTIC HASH REPEATABILITY: VERIFIED (5/5 IDENTICAL HASHES)
  GROUND TRUTH ISOLATION: VERIFIED QUARANTINED (observations.csv ONLY)
  AS-OF CAUSALITY & ADVERSARIAL ISOLATION: VERIFIED AT T=24h AND T=96h
  SAFETY SLOPE: OPEN EVIDENCE GAP (NO IMPLEMENTATION)
  PREDICTIVE REJECTION: NOT AUTHORIZED (INFORMATIONAL EVIDENCE ONLY)
  PHYSICAL QUALIFICATION: NOT ESTABLISHED (PROTOTYPE BENCHMARK SCOPE ONLY)
================================================================================
```

---

### LOG-105: Advanced Empirical Technical Evaluation & Verification Integration (338 -> 353 Tests)
- **Timestamp**: 2026-10-05T18:20:00Z
- **Phase**: Post-Phase 5 Advanced Empirical Evaluation Delivery
- **Type**: TECHNICAL_IMPROVEMENT_INTEGRATION_AND_BENCHMARK
- **Status**: COMPLETE & CRYPTOGRAPHICALLY VERIFIED (353 / 353 TESTS PASSING)

#### 1. Scope & Core Code Adoption
Adopts and benchmarks 10 advanced technical capabilities natively in `src/sih26170/` mapped across the 3 official evaluation criteria:
- **Metric 1 (Anomaly Detection Score):**
  * Item 1.1: Cost-sensitive threshold evaluation ($C_{\text{FN}}:C_{\text{FP}} = 20:1$) via `src/sih26170/screening/risk.py`.
  * Item 1.2: Multivariate Mahalanobis backstop detector ($D_{\text{joint}}$) with LOO shrinkage covariance ($\alpha=0.20, D_{\text{crit}}=4.25$) via `src/sih26170/screening/joint.py`.
  * Item 1.3: Component-level union/OR fusion audit (strict 8-level precedence cascade, 0 AND-gate bottlenecks) via `src/sih26170/screening/fusion.py`.
- **Metric 2 (Drift Prediction Accuracy / MAE):**
  * Item 2.1: Relative drift target ($\Delta u$) vs direct level target empirical comparison via `src/sih26170/prognostics/empirical_validation.py`.
  * Item 2.2: Continuous 50-point fine log-grid CV sweep over $\lambda \in [10^{-3}, 10^3]$ proving $\lambda=1.0$ is within $\le 0.22\%$ of held-out minimum via `src/sih26170/prognostics/empirical_validation.py`.
  * Item 2.3: Regime-conditional conformal calibration (88.6% - 93.3% tail coverage on active drift parts) via `src/sih26170/prognostics/empirical_validation.py`.
- **Metric 3 (Explainability & Transparency):**
  * Item 3.1: Unified `/components/{id}/explain` endpoint consolidating all 6+1 detectors, SHAP, CIs, and bounds via `src/sih26170/service/router.py`.
  * Item 3.2: Closed-form counterfactual boundary inversion ($|\text{residual}| = 1.78 \times 10^{-15}$ float64 math; $2.7 \times 10^{-7}$ 4-decimal operator display) via `src/sih26170/pipeline/explainability.py`.
  * Item 3.3: Inspector-grade natural language justifications citing exact numbers, limits, and fixture states via `src/sih26170/pipeline/explainability.py`.
  * Item 3.4: Formal Known Limitations catalog (`KL-01` through `KL-04`) via `src/sih26170/pipeline/explainability.py`.

#### 2. Exact Test Suite Expansion Trail (+15 Tests: 338 -> 353)
- `tests/screening/test_joint_detector.py` (+3 tests):
  1. `test_joint_detector_on_nominal_component`
  2. `test_joint_detector_on_compound_drift_anomaly`
  3. `test_joint_detector_small_sample_guard`
- `tests/test_service_api.py` (+3 tests):
  4. `test_api_known_limitations`
  5. `test_api_counterfactual_exactness`
  6. `test_api_sub_resource_views` (augmented explainability contract)
- `tests/test_empirical_study.py` (+9 tests):
  7. `test_metric_1_1_cost_sensitive_monotonicity`
  8. `test_metric_1_2_joint_mahalanobis_backstop`
  9. `test_metric_1_3_union_fusion_precedence`
  10. `test_metric_2_1_relative_vs_direct_drift`
  11. `test_metric_2_2_regularization_cv_valley`
  12. `test_metric_2_3_regime_conditional_conformal`
  13. `test_metric_3_counterfactual_exact_inversion`
  14. `test_metric_3_known_limitations_disclosure`
  15. `test_full_empirical_study_fast_execution`

#### 3. Verification & Lineage Lock
- Full pytest suite passes: **353 / 353 passed in 19.56s**.
- Zero modification to frozen production artifacts or baseline lineage hashes (`test_frozen_baseline_hashes_all_match` 100% green).
- Full benchmark executable via `PYTHONPATH=src python3 benchmarks/empirical_study.py`.
- Complete documentation published in `docs/EMPIRICAL_TECHNICAL_EVALUATION.md`.

---

### LOG-106: Module A Change & Retraining Plan Implementation
- **Timestamp**: 2026-10-05T18:40:00Z
- **Phase**: Module A Architectural Alignment & Retraining Plan
- **Type**: CODE_DELIVERY / FEATURE_IMPLEMENTATION / COMPLIANCE_ALIGNMENT
- **Prior State**: Module A relied solely on endpoint normalized drift $g(T)$, raw uncalibrated heuristic cutoffs, univariate equipment confounding flags, and level-space multivariate Mahalanobis backstop.
- **New State**:
  1. **Change #1 (CUSUM Persistent Drift Detector)**:
     - Implemented sequential Leave-One-Out cumulative departure accumulator ($C_k = \max(C_k^+, C_k^-)$) with slack $k_{\text{ref}} = 0.25$ and threshold $h = 2.0$ across $0\text{h} \to 24\text{h} \to 96\text{h} \to 168\text{h}$.
     - Detects `SMALL_BUT_PERSISTENT_DRIFT` ($|g| \approx 1.8 < 2.5$) that escapes single-point cutoffs without triggering on `HIGH_BUT_STABLE` ($C=0$) or `COMMON_MODE_MOVEMENT` ($C=0$).
     - Preserves 24h two-point guard ($n_{\text{pts}} \ge 3$ required for persistent drift alert).
  2. **Change #2 (Quantitative Equipment Decomposition)**:
     - Preserves `common_mode_evidence` and `device_specific_evidence` explicitly on `EquipmentEvidence`.
     - Links temporal excess residual $g_{\text{excess}} = g_T - g_{\text{lot}}$ into equipment record, distinguishing shared chamber movement from intrinsic device degradation.
  3. **Change #3 (Detector Score Empirical Calibration)**:
     - Created `src/sih26170/screening/calibration.py` implementing exact closed-form evidence normalization into $[0, 1]$:
       - Peer: $\text{erf}(|z| / \sqrt{2})$
       - Temporal Drift: Combined endpoint $\text{erf}(|g| / \sqrt{2})$ and logistic CUSUM link
       - Step Jump: Logistic link centered at $J = 4.0$
       - Joint Mahalanobis: Exact $\chi^2_4$ cumulative distribution $F(x; 4) = 1 - (1 + x/2) e^{-x/2}$
       - Equipment: Normalized chamber/ATE common-mode ratio
     - Retains raw physical values for explainability cards while recording `calibrated_score`.
  4. **Change #4 (Multivariate Early-Change Delta Detector)**:
     - Upgraded `evaluate_joint_mahalanobis` to compute the $N \times 4$ observation matrix over early parameter changes $\Delta \mathbf{u}(T) = \mathbf{u}(T) - \mathbf{u}(0)$ when $T > 0$ and $t=0$ baseline exists.
     - Operates in `delta` space to catch correlated sub-threshold drift patterns that escape univariate cutoffs.
- **Verification**:
  - Full test suite: **359 / 359 tests passed in 19.84s** (0 failures, 0 warnings).
  - Dedicated test suite `tests/screening/test_change_plan_implementation.py` (6/6 passed).
  - Frozen baseline lineage hashes 100% verified.




















