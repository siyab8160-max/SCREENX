# SIH26170 — PHASE 2F BENCHMARK SCENARIO ONTOLOGY
## Release Identifier: `PHASE_2F_FROZEN_BENCHMARK_v1.0.0`

### 1. Hierarchical Ontology Model (Option A Confirmed)
The Phase 2F benchmark formally defines `mixed_compound` as a **component-level composite scenario**. It models a multi-parameter failure mode where an individual physical semiconductor component experiences simultaneous distinct degradation kinetics across different electrical observables.

At the parameter level, an individual observable ($I_{\text{DSS}}$, $V_{\text{GS(th)}}$, $R_{\text{DS(on)}}$, $I_{\text{GSS}}$) cannot experience a "mixed compound scenario"; its kinetic trajectory is either linear drift, accelerating wearout, step change, or stationary. Therefore, child parameter trajectories retain their own specific parameter-level scenario identities.

### 2. Multi-Level Scenario Population Breakdown

```text
┌─────────────────────────┬──────────────────┬──────────────────┬──────────────────┬──────────────────────┐
│ Scenario Class          │ Component-Level  │ Parameter-Level  │ Observation-Level│ Ontology & Scope     │
│                         │ (N = 398)        │ (N = 1,592)      │ (N = 6,368)      │                      │
├─────────────────────────┼──────────────────┼──────────────────┼──────────────────┼──────────────────────┤
│ stable                  │ 166 (41.71%)     │ 1,274 (80.03%)   │ 5,096 (80.03%)   │ Component / Parameter│
│ high_but_stable         │ 169 (42.46%)     │ 170 (10.68%)     │ 680 (10.68%)     │ Component / Parameter│
│ equipment_common_mode   │ 32 (8.04%)       │ 92 (5.78%)       │ 368 (5.78%)      │ Component / Parameter│
│ insufficient_data       │ 8 (2.01%)        │ 32 (2.01%)       │ 128 (2.01%)      │ Component / Lot      │
│ linear_drift            │ 10 (2.51%)       │ 11 (0.69%)       │ 44 (0.69%)       │ Parameter Trajectory │
│ static_limit_breach     │ 6 (1.51%)        │ 6 (0.38%)        │ 24 (0.38%)       │ Parameter Trajectory │
│ accelerating_drift      │ 3 (0.75%)        │ 4 (0.25%)        │ 16 (0.25%)       │ Parameter Trajectory │
│ mixed_compound          │ 2 (0.50%)        │ *Decomposed (0)* │ *Decomposed (0)* │ Component Composite  │
│ subtle_abrupt_change    │ 1 (0.25%)        │ 2 (0.13%)        │ 8 (0.13%)        │ Parameter Trajectory │
│ lot_outlier             │ 1 (0.25%)        │ 1 (0.06%)        │ 4 (0.06%)        │ Component / Parameter│
├─────────────────────────┼──────────────────┼──────────────────┼──────────────────┼──────────────────────┤
│ Total Sum               │ 398 (100.0%)     │ 1,592 (100.0%)   │ 6,368 (100.0%)   │ All Rows Accounted   │
└─────────────────────────┴──────────────────┴──────────────────┴──────────────────┴──────────────────────┘
```

### 3. Decomposition of Mixed Compound Components
- **`LOT_M01_C001`**:
  - Component Scenario: `mixed_compound`
  - $I_{\text{DSS}}$ Trajectory: `linear_drift`
  - $V_{\text{GS(th)}}$ Trajectory: `subtle_abrupt_change`
  - $R_{\text{DS(on)}}$ Trajectory: `stable`
  - $I_{\text{GSS}}$ Trajectory: `stable`
- **`LOT_M01_C002`**:
  - Component Scenario: `mixed_compound`
  - $R_{\text{DS(on)}}$ Trajectory: `accelerating_drift`
  - $I_{\text{DSS}}$ Trajectory: `high_but_stable`
  - $V_{\text{GS(th)}}$ Trajectory: `stable`
  - $I_{\text{GSS}}$ Trajectory: `stable`
