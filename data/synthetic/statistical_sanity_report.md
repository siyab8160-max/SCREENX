# Synthetic Dataset Statistical Sanity Report

## Population & Record Counts
- **Lots**: 14
- **Components**: 395
- **Parameters**: 3
- **Checkpoints**: 4
- **Observation Records**: 4,609
- **Ground Truth Records**: 4,740

## Trajectory Class Distribution
- `stable`: 335 (84.8%)
- `linear_drift`: 18 (4.6%)
- `high_but_stable`: 16 (4.1%)
- `abrupt_failure`: 11 (2.8%)
- `accelerating_drift`: 9 (2.3%)
- `lot_outlier`: 6 (1.5%)

## Measurement & Artifact Semantics
- **Missing Observations**: 131 (2.76%)
- **Negative Observations (Preserved)**: 4
- **Zero Observations**: 0
- **Non-Finite Readings**: 0
- **Equipment Shift Readings**: 188

## Ground Truth Abnormality vs. Absolute Limits
- **Ground-Truth Abnormal Components**: 60
  - Abnormal by 24h: 29
  - Abnormal by 96h: 60
  - Abnormal by 168h: 60
- **Absolute Operational Limit Crossings**: 62

> [!NOTE]
> These are dataset QA summary statistics, NOT machine learning detector performance metrics.