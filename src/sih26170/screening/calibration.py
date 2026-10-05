"""Empirical evidence calibration and score normalization for Module A detectors.

Compliant with Module A Change Plan §6 & Phase 4B specifications:
- Converts heterogeneous raw detector scores (MAD z-score, slope/drift ratio,
  step ratio J(T), Mahalanobis distance D_joint) into comparable [0, 1] empirical
  evidence scales.
- Preserves raw physical units on evidence records for inspector explainability,
  while providing normalized scores for statistical fusion.
- Uses exact closed-form reference CDFs (e.g. chi-square k=4 for joint Mahalanobis,
  error function for Gaussian z-scores, logistic link for step jump ratios).
- Zero external C-dependencies (pure Python standard library + math).
"""

from __future__ import annotations

import math
from typing import Optional


def calibrate_peer_score(z_score: Optional[float]) -> Optional[float]:
    """Convert robust LOO peer z-score to two-sided empirical percentile evidence in [0, 1].

    Under the nominal baseline reference, E_peer = erf(|z| / sqrt(2)).
    |z| = 0.0 -> E = 0.0000
    |z| = 2.0 -> E = 0.9545
    |z| = 3.0 -> E = 0.9973 (Mild Outlier cutoff)
    |z| = 5.0 -> E = 0.9999994 (Extreme Outlier cutoff)
    """
    if z_score is None or not math.isfinite(z_score):
        return None
    abs_z = abs(float(z_score))
    # Closed-form error function from math
    p = math.erf(abs_z / math.sqrt(2.0))
    return float(round(max(0.0, min(1.0, p)), 4))


def calibrate_temporal_drift_score(
    normalized_drift: Optional[float],
    cusum_statistic: Optional[float] = None,
) -> Optional[float]:
    """Convert normalized drift g(T) and CUSUM persistence into [0, 1] evidence scale.

    Combines:
    1. Endpoint normalized drift: erf(|g| / sqrt(2))
    2. CUSUM cumulative score: logistic sigmoid centered at h_cusum = 3.5
    """
    scores = []
    if normalized_drift is not None and math.isfinite(normalized_drift):
        e_drift = math.erf(abs(float(normalized_drift)) / math.sqrt(2.0))
        scores.append(e_drift)

    if cusum_statistic is not None and math.isfinite(cusum_statistic):
        c = float(cusum_statistic)
        if c <= 0.0:
            scores.append(0.0)
        else:
            e_cusum = 1.0 / (1.0 + math.exp(-1.5 * (c - 3.5)))
            scores.append(e_cusum)

    if not scores:
        return None

    return float(round(max(0.0, min(1.0, max(scores))), 4))


def calibrate_step_score(step_ratio: Optional[float]) -> Optional[float]:
    """Convert abrupt step jump ratio J(T) into [0, 1] evidence scale.

    Uses logistic link centered at J_threshold = 4.0 with slope 1.5:
    J = 0.0 -> E = 0.0000
    J = 2.0 -> E = 0.0474
    J = 4.0 -> E = 0.5000 (Alarm threshold)
    J = 6.0 -> E = 0.9526
    """
    if step_ratio is None or not math.isfinite(step_ratio):
        return None
    j = float(step_ratio)
    if j <= 0.0:
        return 0.0
    val = 1.0 / (1.0 + math.exp(-1.5 * (j - 4.0)))
    return float(round(max(0.0, min(1.0, val)), 4))



def calibrate_joint_score(mahalanobis_distance: Optional[float]) -> Optional[float]:
    """Convert joint 4-D Mahalanobis distance into exact chi-square (df=4) CDF probability.

    For D_joint across 4 parameters: D^2 ~ chi^2_4.
    Closed-form CDF: F(x; 4) = 1 - (1 + x/2) * exp(-x/2), where x = D^2.
    D = 0.00 -> F = 0.0000
    D = 2.00 -> F = 0.5940
    D = 3.00 -> F = 0.9161
    D = 4.25 -> F = 0.9988 (Critical backstop cutoff)
    """
    if mahalanobis_distance is None or not math.isfinite(mahalanobis_distance):
        return None
    d = max(0.0, float(mahalanobis_distance))
    x = d * d
    # Exact chi^2 with k=4 CDF
    cdf = 1.0 - (1.0 + 0.5 * x) * math.exp(-0.5 * x)
    return float(round(max(0.0, min(1.0, cdf)), 4))


def calibrate_equipment_score(
    lot_median_shift: Optional[float],
    channel_offset: Optional[float],
    noise_floor: float,
) -> float:
    """Compute normalized common-mode excursion evidence in [0, 1]."""
    c_evidence = 0.0
    if lot_median_shift is not None and math.isfinite(lot_median_shift):
        ratio = abs(float(lot_median_shift)) / max(noise_floor, 1e-9)
        c_chamber = 1.0 / (1.0 + math.exp(-1.2 * (ratio - 3.0)))
        c_evidence = max(c_evidence, c_chamber)

    if channel_offset is not None and math.isfinite(channel_offset):
        ratio_chan = abs(float(channel_offset)) / max(noise_floor, 1e-9)
        c_ate = 1.0 / (1.0 + math.exp(-1.2 * (ratio_chan - 3.0)))
        c_evidence = max(c_evidence, c_ate)

    return float(round(max(0.0, min(1.0, c_evidence)), 4))
