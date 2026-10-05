"""Detector C: Robust Temporal Drift Detector (D_drift).

Compliant with docs/PHASE_3A_MODULE_A_SPEC.md Sections 4.3 & 7 & Phase 3C Pre-Implementation Amendments:
- As-of restricted historical trajectory evaluation (V_T)
- Theil-Sen robust slope estimation over available checkpoints
- Second-order finite difference proxy for acceleration (strictly screened, not prognostic)
- Normalized drift g(T) = Delta u(T) / sigma_0
- Leave-One-Out (LOO) lot common-mode reference: g_lot,-i(T) and g_excess(T) = g_i(T) - g_lot,-i(T)
- Component i is strictly excluded from its own reference and from baseline scale calculation
- Preserves temporal kinetics (drift, slope, acceleration) even under equipment confounding
  without erasing or overwriting evidence
- g_excess serves as a confounding comparator across common valid checkpoints
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np

from sih26170.screening.calibration import calibrate_temporal_drift_score
from sih26170.screening.schema import (
    TemporalDriftStatus,
    TemporalEvidence,
)
from sih26170.screening.transforms import (
    get_noise_floor,
    transform_parameter,
)

# Thresholds for temporal drift (Layer F Benchmark/Design Parameters, Class D heuristics)
SUBTLE_DRIFT_G_THRESHOLD: float = 2.5
ACCELERATING_DRIFT_G_THRESHOLD: float = 3.0
PERSISTENT_DRIFT_CUSUM_THRESHOLD: float = 2.0
CUSUM_SLACK_K: float = 0.25



def evaluate_temporal_drift(
    parameter: str,
    history: List[Tuple[int, float]],
    as_of_hours: int,
    baseline_lot_scale: Optional[float] = None,
    confounded_by_equipment: bool = False,
    lot_peer_history: Optional[Dict[str, List[Tuple[int, float]]]] = None,
    target_component_id: Optional[str] = None,
) -> TemporalEvidence:
    """Evaluate temporal drift on historical checkpoints up to as_of_hours.

    Args:
        parameter: Parameter name ('IDSS', 'VGS(th)', 'RDS(on)', 'IGSS')
        history: List of (elapsed_hours, raw_value) tuples for target component
        as_of_hours: Current checkpoint boundary T
        baseline_lot_scale: Robust scale sigma_0 from t=0h lot baseline
        confounded_by_equipment: True if common-mode/chamber excursion affected this checkpoint
        lot_peer_history: Optional dict of component_id -> history for all lot components
        target_component_id: Optional target component ID for strict leave-one-out exclusion

    Returns:
        TemporalEvidence containing slope, normalized drift, g_lot, g_excess, CUSUM, and status.
    """
    # 1. Enforce strict as-of restriction: keep only t <= as_of_hours
    as_of_history = sorted(
        [(int(t), float(v)) for t, v in history if t <= as_of_hours],
        key=lambda x: x[0],
    )

    checkpoints_used = [t for t, _ in as_of_history]
    k = len(as_of_history)
    time_range = (checkpoints_used[0], checkpoints_used[-1]) if k > 0 else (0, 0)

    # 2. Check single-point or empty history (e.g. t = 0h)
    if k < 2:
        return TemporalEvidence(
            parameter=parameter,
            observations_used=k,
            checkpoints_used=checkpoints_used,
            time_range=time_range,
            slope_per_hour=0.0,
            normalized_drift=0.0,
            acceleration_evidence=None,
            status=TemporalDriftStatus.STATIONARY,
            confounded_by_equipment=confounded_by_equipment,
            reason_code="BASELINE_INITIAL_OBSERVATION" if k == 1 else "NO_OBSERVATIONS_AVAILABLE",
            g_lot=0.0,
            g_excess=0.0,
            lot_reference_note=None,
            cusum_statistic=0.0,
            persistent_drift=False,
            calibrated_score=0.0,
        )

    # 3. Transform measurements to parameter representation space
    transformed_points: List[Tuple[int, float]] = []
    for t, raw_val in as_of_history:
        try:
            u = transform_parameter(parameter, raw_val)
            transformed_points.append((t, u))
        except ValueError:
            continue

    if len(transformed_points) < 2:
        return TemporalEvidence(
            parameter=parameter,
            observations_used=k,
            checkpoints_used=checkpoints_used,
            time_range=time_range,
            slope_per_hour=None,
            normalized_drift=None,
            acceleration_evidence=None,
            status=TemporalDriftStatus.INSUFFICIENT_HISTORY,
            confounded_by_equipment=confounded_by_equipment,
            reason_code="INSUFFICIENT_TRANSFORMABLE_POINTS",
            g_lot=None,
            g_excess=None,
            lot_reference_note=None,
            cusum_statistic=None,
            persistent_drift=False,
            calibrated_score=None,
        )

    floor = get_noise_floor(parameter)

    # 4. Leave-One-Out (LOO) Lot Reference & Baseline Scale Computation
    # Component i must NEVER enter its own reference
    g_lot: Optional[float] = None
    g_excess: Optional[float] = None
    lot_reference_note: Optional[str] = None
    loo_sigma_0 = baseline_lot_scale if (baseline_lot_scale is not None and baseline_lot_scale > 0) else floor

    cusum_val = 0.0
    cusum_pos = 0.0
    cusum_neg = 0.0

    if lot_peer_history is not None:
        # Filter peers excluding target component
        peer_shifts: List[float] = []
        peer_t0_vals: List[float] = []
        peer_shifts_by_t: Dict[int, List[float]] = {}

        for peer_id, peer_hist in lot_peer_history.items():
            if target_component_id is not None and peer_id == target_component_id:
                continue  # Strict LOO: target component excluded

            # Keep only t <= as_of_hours
            p_as_of = {int(t): float(v) for t, v in peer_hist if t <= as_of_hours}
            if 0 in p_as_of:
                try:
                    u_0_p = transform_parameter(parameter, p_as_of[0])
                    peer_t0_vals.append(u_0_p)
                    for t_step, v_step in p_as_of.items():
                        if t_step > 0:
                            u_step_p = transform_parameter(parameter, v_step)
                            peer_shifts_by_t.setdefault(t_step, []).append(u_step_p - u_0_p)
                except ValueError:
                    pass

            if 0 in p_as_of and as_of_hours in p_as_of:
                try:
                    u_0_p = transform_parameter(parameter, p_as_of[0])
                    u_T_p = transform_parameter(parameter, p_as_of[as_of_hours])
                    peer_shifts.append(u_T_p - u_0_p)
                except ValueError:
                    pass

        # LOO baseline scale from peer t=0 values
        if len(peer_t0_vals) >= 7:
            p_t0_arr = np.array(peer_t0_vals, dtype=np.float64)
            med_0 = float(np.median(p_t0_arr))
            mad_0 = float(np.median(np.abs(p_t0_arr - med_0)))
            loo_sigma_0 = max(1.4826 * mad_0, floor)

        # LOO median lot shift across common valid pairs (t=0 and t=T)
        if len(peer_shifts) >= 4:
            median_lot_shift = float(np.median(peer_shifts))
            g_lot = median_lot_shift / max(loo_sigma_0, floor)
        else:
            lot_reference_note = "LOT_REFERENCE_UNAVAILABLE_SMALL_LOT"

        # Sequential CUSUM accumulation across checkpoints
        u_0_target = transformed_points[0][1]
        for t_k, u_k in transformed_points[1:]:
            delta_k = u_k - u_0_target
            peer_t_shifts = peer_shifts_by_t.get(t_k, [])
            if len(peer_t_shifts) >= 4:
                med_lot_k = float(np.median(peer_t_shifts))
                excess_k = (delta_k - med_lot_k) / max(loo_sigma_0, floor)
            else:
                excess_k = delta_k / max(loo_sigma_0, floor)

            cusum_pos = max(0.0, cusum_pos + (excess_k - CUSUM_SLACK_K))
            cusum_neg = max(0.0, cusum_neg + (-excess_k - CUSUM_SLACK_K))
            cusum_val = max(cusum_pos, cusum_neg)
    else:
        # Lot peer history not provided: accumulate individual departures
        u_0_target = transformed_points[0][1]
        for t_k, u_k in transformed_points[1:]:
            delta_k = u_k - u_0_target
            excess_k = delta_k / max(loo_sigma_0, floor)
            cusum_pos = max(0.0, cusum_pos + (excess_k - CUSUM_SLACK_K))
            cusum_neg = max(0.0, cusum_neg + (-excess_k - CUSUM_SLACK_K))
            cusum_val = max(cusum_pos, cusum_neg)

    # 5. Normalized drift g(T) = (u(T) - u(0)) / sigma_0
    u_0 = transformed_points[0][1]
    u_T = transformed_points[-1][1]
    delta_u = u_T - u_0
    g_T = delta_u / max(loo_sigma_0, floor)

    # 6. Excess drift relative to LOO lot reference
    if g_lot is not None:
        g_excess = g_T - g_lot
    else:
        g_excess = g_T  # Fallback to individual drift if lot reference unavailable

    # 7. Robust slope estimation (Theil-Sen for k >= 3, pairwise difference for k == 2)
    n_pts = len(transformed_points)
    if n_pts == 2:
        dt = transformed_points[1][0] - transformed_points[0][0]
        slope = (transformed_points[1][1] - transformed_points[0][1]) / dt if dt > 0 else 0.0
    else:
        pairwise_slopes: List[float] = []
        for i in range(n_pts):
            for j in range(i + 1, n_pts):
                dt = transformed_points[j][0] - transformed_points[i][0]
                if dt > 0:
                    pairwise_slopes.append((transformed_points[j][1] - transformed_points[i][1]) / dt)
        slope = float(np.median(pairwise_slopes)) if pairwise_slopes else 0.0

    # 8. Acceleration proxy kappa(T) for k >= 3 (second difference across last 3 checkpoints)
    kappa: Optional[float] = None
    if n_pts >= 3:
        dt_recent = transformed_points[-1][0] - transformed_points[-2][0]
        dt_prior = transformed_points[-2][0] - transformed_points[-3][0]
        if dt_recent > 0 and dt_prior > 0:
            s_recent = (transformed_points[-1][1] - transformed_points[-2][1]) / dt_recent
            s_prior = (transformed_points[-2][1] - transformed_points[-3][1]) / dt_prior
            kappa = float(s_recent - s_prior)

    # 9. Classify kinetic status autonomously (preserving wearout signals)
    persistent_drift_flag = False
    # At 24h (n_pts == 2), 2-point CUSUM is not treated as new information per §4
    if n_pts >= 3 and cusum_val >= PERSISTENT_DRIFT_CUSUM_THRESHOLD:
        persistent_drift_flag = True

    if abs(g_T) >= ACCELERATING_DRIFT_G_THRESHOLD and kappa is not None and (kappa > 1e-5 and slope > 0):
        status = TemporalDriftStatus.ACCELERATING_DRIFT
        reason_code = "ACCELERATING_TEMPORAL_DRIFT"
    elif abs(g_T) >= SUBTLE_DRIFT_G_THRESHOLD:
        status = TemporalDriftStatus.SUBTLE_DRIFT
        reason_code = "SUBTLE_TEMPORAL_DRIFT"
    elif persistent_drift_flag:
        status = TemporalDriftStatus.PERSISTENT_DRIFT
        reason_code = "PERSISTENT_TEMPORAL_DRIFT"
    elif confounded_by_equipment:
        # Stationary relative to baseline, but equipment disturbance is present
        status = TemporalDriftStatus.TEMPORALLY_CONFOUNDED_BY_EQUIPMENT
        reason_code = "TEMPORALLY_CONFOUNDED_BY_EQUIPMENT"
    else:
        status = TemporalDriftStatus.STATIONARY
        reason_code = "TEMPORALLY_STATIONARY"

    cal_score = calibrate_temporal_drift_score(g_T, cusum_val)

    return TemporalEvidence(
        parameter=parameter,
        observations_used=n_pts,
        checkpoints_used=checkpoints_used,
        time_range=time_range,
        slope_per_hour=float(slope),
        normalized_drift=float(g_T),
        acceleration_evidence=kappa,
        status=status,
        confounded_by_equipment=confounded_by_equipment,
        reason_code=reason_code,
        g_lot=float(g_lot) if g_lot is not None else None,
        g_excess=float(g_excess) if g_excess is not None else None,
        lot_reference_note=lot_reference_note,
        cusum_statistic=float(round(cusum_val, 4)),
        persistent_drift=persistent_drift_flag,
        calibrated_score=cal_score,
    )

