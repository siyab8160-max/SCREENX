"""Detector F: Data Sufficiency and Telemetry Integrity Detector (D_suff).

Compliant with docs/PHASE_3A_MODULE_A_SPEC.md Sections 4.6 & 8:
- Checkpoint history completeness validation: {0, 24, 96, 168}h schedule
- Explicit detection of missing checkpoints and corrupted sensor reads
- Enforces small-lot policy heuristic (N < 8)
- Emits INSUFFICIENT_DATA without silent value imputation
"""

from __future__ import annotations

from typing import List, Set
from sih26170.screening.schema import (
    SufficiencyEvidence,
    SufficiencyStatus,
)

# Standard burn-in inspection schedule
SCHEDULE_CHECKPOINTS: List[int] = [0, 24, 96, 168]
MIN_LOT_SIZE: int = 8


def evaluate_data_sufficiency(
    component_id: str,
    checkpoint: int,
    available_checkpoints: List[int],
    measurement_qualities: List[str],
    lot_size: int,
) -> SufficiencyEvidence:
    """Evaluate telemetry completeness and lot size sufficiency up to checkpoint T.

    Args:
        component_id: Component identifier
        checkpoint: Current as-of boundary T
        available_checkpoints: Checkpoints present for this component
        measurement_qualities: Quality strings for present checkpoints
        lot_size: Number of unique components in the lot

    Returns:
        SufficiencyEvidence with sufficiency flag and reason code.
    """
    # 1. Determine expected checkpoints up to T
    expected = [t for t in SCHEDULE_CHECKPOINTS if t <= checkpoint]
    available_set = set(available_checkpoints)
    missing = [t for t in expected if t not in available_set]

    # 2. Check measurement quality validity
    corrupted_count = sum(1 for q in measurement_qualities if q != "VALID")

    # 3. Check small lot policy
    is_small = lot_size < MIN_LOT_SIZE

    # 4. Classify status
    if missing:
        status = SufficiencyStatus.INCOMPLETE_HISTORY
        sufficient = False
        missing_str = "_".join(str(t) for t in sorted(missing))
        reason_code = f"MISSING_CHECKPOINTS_{missing_str}"
    elif corrupted_count > 0:
        status = SufficiencyStatus.CORRUPTED_MEASUREMENT
        sufficient = False
        reason_code = "CORRUPTED_MEASUREMENT_QUALITY"
    elif is_small:
        status = SufficiencyStatus.SMALL_LOT_RESTRICTION
        sufficient = True  # Measurements valid for single-part eval, but peer DPAT restricted
        reason_code = "SMALL_LOT_PEER_RESTRICTION"
    else:
        status = SufficiencyStatus.SUFFICIENT
        sufficient = True
        reason_code = "DATA_SUFFICIENT_AND_VALID"

    return SufficiencyEvidence(
        component_id=component_id,
        checkpoint=checkpoint,
        expected_checkpoints=expected,
        available_checkpoints=sorted(available_checkpoints),
        lot_size=lot_size,
        is_small_lot=is_small,
        status=status,
        sufficient=sufficient,
        reason_code=reason_code,
    )
