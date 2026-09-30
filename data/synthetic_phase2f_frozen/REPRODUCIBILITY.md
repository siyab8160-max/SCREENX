# SIH26170 — PHASE 2F BENCHMARK REPRODUCIBILITY GUIDE
## Release Identifier: `PHASE_2F_FROZEN_BENCHMARK_v1.0.0`

### 1. Deterministic Cryptographic Reproducibility
All telemetry and ground-truth values in this release are derived using a deterministic seed hierarchy anchored at master seed `26170`:
- Root Seed: `26170`
- Derivation Function: `HMAC-SHA256(key=parent_seed, msg=path_elements)`
- Path Hierarchy:
  - Lot Seed: `derive_seed_hmac(master_seed, "lot", lot_id)`
  - Component Seed: `derive_seed_hmac(lot_seed, "component", comp_id)`
  - Parameter Seed: `derive_seed_hmac(comp_seed, "parameter", param_name)`
  - Readout Noise Seed: `derive_seed_hmac(comp_seed, "readout", param_name, checkpoint)`

This design guarantees that any compliant implementation running on any operating system generates bit-for-bit identical outputs without depending on global random number generator state.

### 2. Frozen Release Verification Hashes
To verify the integrity of the frozen files:

```bash
shasum -a 256 data/synthetic_phase2f_frozen/observations.csv
# Must match: b4282e0743cd6a0b2b74354e431bf8f308b03281c44c0437d30f7b53bd6ca983

shasum -a 256 data/synthetic_phase2f_frozen/ground_truth.csv
# Must match: 4bf2155fcc7698813f766e1dea9730213e0a6097e484bfa786eb1b94925f3d2b
```
