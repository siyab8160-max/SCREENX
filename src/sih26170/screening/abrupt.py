"""Detector D: Abrupt Change Detector (D_step).

Compliant with docs/PHASE_3A_MODULE_A_SPEC.md Sections 4.4 & 7:
- Single-interval step jump evaluation across adjacent checkpoints: J(T) >= 4.0
- Uses strictly adjacent historical observations available at T
- Zero/near-zero denominators explicitly bounded by parameter noise floor
- Future intervals strictly prohibited from influencing earlier decisions
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from sih26170.screening.schema import (
    AbruptStepStatus,
    StepEvidence,
)
from sih26170.screening.transforms import (
    get_noise_floor,
    transform_parameter,
)

# Normalized step jump ratio threshold (Class D heuristic)
ABRUPT_JUMP_RATIO_THRESHOLD: float = 4.0


def evaluate_abrupt_step(
    parameter: str,
    history: List[Tuple[int, float]],
    as_of_hours: int,
    lot_scale_prev: Optional[float] = None,
) -> StepEvidence:
    """Evaluate abrupt step jump across the most recent checkpoint interval.

    Args:
        parameter: Parameter name ('IDSS', 'VGS(th)', 'RDS(on)', 'IGSS')
        history: List of (elapsed_hours, raw_value) tuples
        as_of_hours: Current checkpoint boundary T
        lot_scale_prev: Robust lot dispersion scale at previous checkpoint T_prev

    Returns:
        StepEvidence containing step magnitude, step ratio J(T), and status.
    """
    # 1. Enforce strict as-of restriction: keep only t <= as_of_hours
    as_of_history = sorted(
        [(int(t), float(v)) for t, v in history if t <= as_of_hours],
        key=lambda x: x[0],
    )

    k = len(as_of_history)
    if k < 2:
        curr_t = as_of_history[0][0] if k == 1 else as_of_hours
        return StepEvidence(
            parameter=parameter,
            previous_checkpoint=None,
            current_checkpoint=curr_t,
            step_magnitude=0.0,
            step_ratio=0.0,
            status=AbruptStepStatus.NO_STEP,
            reason_code="NO_PRIOR_CHECKPOINT",
        )

    floor = get_noise_floor(parameter)
    denom = max(lot_scale_prev, floor) if (lot_scale_prev is not None and lot_scale_prev > 0) else floor

    # 2. Evaluate all adjacent intervals in history up to as_of_hours
    # Preserves evidence of transient excursions and abrupt events across all intervals
    max_j_ratio = 0.0
    max_delta = 0.0
    max_t_prev = as_of_history[-2][0]
    max_t_curr = as_of_history[-1][0]
    valid_interval_found = False

    for i in range(1, k):
        t_p, val_p = as_of_history[i - 1]
        t_c, val_c = as_of_history[i]
        try:
            u_p = transform_parameter(parameter, val_p)
            u_c = transform_parameter(parameter, val_c)
        except ValueError:
            continue

        valid_interval_found = True
        delta = abs(u_c - u_p)
        j = delta / denom
        if j > max_j_ratio or not (max_j_ratio > 0):
            max_j_ratio = j
            max_delta = delta
            max_t_prev = t_p
            max_t_curr = t_c

    if not valid_interval_found:
        t_prev, _ = as_of_history[-2]
        t_curr, _ = as_of_history[-1]
        return StepEvidence(
            parameter=parameter,
            previous_checkpoint=t_prev,
            current_checkpoint=t_curr,
            step_magnitude=None,
            step_ratio=None,
            status=AbruptStepStatus.INSUFFICIENT_HISTORY,
            reason_code="INVALID_TRANSFORM_AT_INTERVAL",
        )

    # 3. Classify status based on max step ratio across history
    if max_j_ratio >= ABRUPT_JUMP_RATIO_THRESHOLD:
        status = AbruptStepStatus.ABRUPT_JUMP_ALERT
        reason_code = "ABRUPT_STEP_CHANGE"
    else:
        status = AbruptStepStatus.NO_STEP
        reason_code = "NOMINAL_STEP_INTERVAL"

    return StepEvidence(
        parameter=parameter,
        previous_checkpoint=max_t_prev,
        current_checkpoint=max_t_curr,
        step_magnitude=float(max_delta),
        step_ratio=float(max_j_ratio),
        status=status,
        reason_code=reason_code,
    )

