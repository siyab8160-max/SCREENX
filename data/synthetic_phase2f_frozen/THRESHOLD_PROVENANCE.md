# SIH26170 — PHASE 2F BENCHMARK THRESHOLD PROVENANCE
## Release Identifier: `PHASE_2F_FROZEN_BENCHMARK_v1.0.0`

### 1. Classification Framework
Every threshold utilized in the Phase 2F frozen benchmark is classified into one of five rigorous epistemic and legal categories to ensure complete transparency:
- **Class A**: Verified Device Specification
- **Class B**: Verified Military Standard / Test Method Requirement
- **Class C**: Configured Screening Acceptance Criterion
- **Class D**: Engineering Heuristic
- **Class E**: Synthetic Benchmark Design Parameter

### 2. Complete Provenance Matrix

```text
┌────────────────────────────┬─────────────────────────────┬─────────────┬──────────────────────────────────────────────────────────┐
│ Parameter / Threshold      │ Value / Envelope            │ Semantic    │ Legal / Epistemic Provenance                             │
│                            │                             │ Class       │                                                          │
├────────────────────────────┼─────────────────────────────┼─────────────┼──────────────────────────────────────────────────────────┤
│ IDSS Table I Limit         │ <= 10.0 uA                  │ Class A     │ Verified Device Spec (MIL-PRF-19500/703 Table I, 80V)    │
│ VGS(th) Table I Limits     │ [2.0 V, 4.0 V]              │ Class A     │ Verified Device Spec (MIL-PRF-19500/703 Table I, 1 mA)   │
│ IGSS Table I Limits        │ [-100.0 nA, +100.0 nA]      │ Class A     │ Verified Device Spec (MIL-PRF-19500/703 Table I, +/-20V) │
│ RDS(on) Table I Limit      │ <= 65.0 mOhm                │ Class A     │ Verified Device Spec (MIL-PRF-19500/703 Table I, 22A)    │
│ RDS(on) Screening Margin   │ <= 60.0 mOhm                │ Class C     │ Configured Screening Acceptance Criterion (PD-97217)     │
│ Burn-in Initial PDA        │ <= 5.0% cumulative fails    │ Class B     │ Verified Standard Requirement (MIL-PRF-19500 Sec 4.5.3)  │
│ Burn-in Resubmission PDA   │ <= 3.0% cumulative fails    │ Class B     │ Verified Standard Requirement (MIL-PRF-19500 Sec 4.5.3)  │
│ Subtle Anomaly SNR Window  │ SNR in [1.5, 2.5]           │ Class E     │ Synthetic Benchmark Design Parameter (Difficulty Tuning) │
│ Small-Lot Policy Cutoff    │ N < 8 components            │ Class D     │ Engineering Heuristic (DPAT Sample Variance Guard)       │
│ Benchmark Missingness Rate │ 0.1099% (7 omissions)       │ Class E     │ Synthetic Benchmark Design Parameter (ATE Dropout Model) │
└────────────────────────────┴─────────────────────────────┴─────────────┴──────────────────────────────────────────────────────────┘
```

### 3. Critical Safeguards
1. **$R_{\text{DS(on)}}$ Disambiguation**:
   - $65.0\,\text{m}\Omega$ is the Table I military specification ceiling for `JANSR2N7481U3`.
   - $60.0\,\text{m}\Omega$ is the manufacturer room-temperature pre-rad ceiling (Datasheet PD-97217 Table 3) configured as a tightened screening margin. It is not represented as a universal military limit.
2. **Subtle Failure Difficulty**: SNR $[1.5, 2.5]$ is a benchmark difficulty calibrator to challenge screening detectors, not an empirical device failure boundary.
3. **Small-Lot Policy**: $N < 8$ is an algorithmic heuristic to suppress DPAT false alarms on small samples; it is not a statistical theorem.
