# SIH26170 — PHASE 2F BENCHMARK SCIENTIFIC BOUNDARIES
## Release Identifier: `PHASE_2F_FROZEN_BENCHMARK_v1.0.0`

### 1. Mandatory Epistemic Demarcation
The Phase 2F Frozen Benchmark is governed by strict scientific and evidentiary boundaries:

#### VERIFIED FACTS:
- Infineon IRHNJ57130 / JANSR2N7481U3 MIL-PRF-19500/703 Table I specification ratings and test conditions.
- MIL-PRF-19500 general specification screening and burn-in PDA rules ($\le 5\%$ initial, $\le 3\%$ resubmission).
- Bit-for-bit mathematical reproducibility of all generated benchmark files under HMAC-SHA256 hierarchical seed derivation.
- Absolute quarantine of evaluation ground-truth labels from telemetry observations (`observations.csv`).
- Real as-of historical slice immutability across checkpoints $0\text{h}, 24\text{h}, 96\text{h}, 168\text{h}$.

#### SYNTHETIC BENCHMARK DESIGN:
- All scenario assignments (`linear_drift`, `accelerating_drift`, `subtle_abrupt_change`, `mixed_compound`, `equipment_common_mode`).
- The subtle anomaly SNR difficulty envelope ($[1.5, 2.5]$).
- The baseline missingness rate ($0.1099\%$, modeling 7 ATE contact aborts).
- The small-lot DPAT suppression heuristic ($N < 8$).
- The chamber temperature excursion ($+5^\circ\text{C}$ at $96\text{h}$) and ATE fixture channel offsets.

#### EMPIRICAL SURROGATE EVIDENCE:
- NASA Ames IRF520NPBF power-cycling data provides structural temporal evidence for nonlinear resistance degradation curves $z(t) = R(t)/R(0)$ under thermal overstress. It is strictly quarantined from space flight qualification or radiation hardness claims for the IRHNJ57130.

#### NOT ESTABLISHED:
- This benchmark does **NOT** predict real IRHNJ57130 mission failure rates.
- It does **NOT** represent flight telemetry from ISRO missions.
- It does **NOT** establish that real spaceflight degradation mechanisms are statistically orthogonal.
- It does **NOT** prove that the proposed screening architecture will achieve target detection accuracy on real production lines prior to Module A execution.
- It does **NOT** claim validity for other component families (bipolar transistors, diodes, ICs).
