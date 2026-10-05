"""Detector B: Leave-One-Out Robust Lot/Peer Relative Deviation Detector (D_peer).

Compliant with docs/PHASE_3A_MODULE_A_SPEC.md Sections 4.2 & 6:
- Leave-one-out peer statistics strictly excluding target component i
- Robust median and MAD with 50% breakdown point
- N < 8 small-lot policy: formally suppresses peer detection and records PEER_SUPPRESSED_SMALL_LOT
- Evaluated strictly in parameter-specific representation space u = phi(y)
- Epistemic terminology: PER-LOT BASELINE REFERENCE (no unsupported conformal claims)
"""

from __future__ import annotations

from typing import Dict, List, Optional
import numpy as np

from sih26170.screening.schema import (
    PeerDeviationStatus,
    PeerEvidence,
)
from sih26170.screening.transforms import (
    get_noise_floor,
    inverse_transform_parameter,
    transform_parameter,
)

# Minimum lot size threshold for robust peer statistics (Class D heuristic)
MIN_LOT_SIZE_FOR_PEERS: int = 8

# Robust z-score thresholds (Class D heuristics)
MILD_OUTLIER_Z_THRESHOLD: float = 3.0
EXTREME_OUTLIER_Z_THRESHOLD: float = 5.0


def evaluate_peer_deviation(
    component_id: str,
    lot_id: str,
    parameter: str,
    observed_value: float,
    lot_observations: Dict[str, float],
    custom_noise_floor: Optional[float] = None,
) -> PeerEvidence:
    """Evaluate leave-one-out peer relative deviation at current checkpoint.

    Args:
        component_id: Unique target component identifier
        lot_id: Lot identifier
        parameter: Observable name ('IDSS', 'VGS(th)', 'RDS(on)', 'IGSS')
        observed_value: Raw physical measurement for target component
        lot_observations: Map of {comp_id: raw_value} for all components in lot at checkpoint T
        custom_noise_floor: Optional custom floor override

    Returns:
        PeerEvidence with leave-one-out robust statistics.
    """
    u_target = transform_parameter(parameter, observed_value)

    # Leave-One-Out: strictly exclude the target device from its peer reference population
    peer_raw_values: List[float] = [
        val for cid, val in lot_observations.items() if cid != component_id
    ]
    total_lot_size = 1 + len(peer_raw_values)

    # 1. Enforce small-lot policy (N < 8): suppress peer-relative scoring
    if total_lot_size < MIN_LOT_SIZE_FOR_PEERS:
        return PeerEvidence(
            parameter=parameter,
            observed_value=float(observed_value),
            transformed_value=u_target,
            peer_median=None,
            peer_mad=None,
            peer_scale=None,
            z_score=None,
            status=PeerDeviationStatus.PEER_SUPPRESSED_SMALL_LOT,
            peer_count=len(peer_raw_values),
            reason_code="PEER_SUPPRESSED_SMALL_LOT",
            reference_slice="PER-LOT BASELINE REFERENCE",
        )

    # 2. Transform all valid peer measurements to representation space
    u_peers: List[float] = []
    for v in peer_raw_values:
        try:
            u_peers.append(transform_parameter(parameter, v))
        except ValueError:
            continue  # Skip un-transformable peer readings

    if len(u_peers) < (MIN_LOT_SIZE_FOR_PEERS - 1):
        return PeerEvidence(
            parameter=parameter,
            observed_value=float(observed_value),
            transformed_value=u_target,
            peer_median=None,
            peer_mad=None,
            peer_scale=None,
            z_score=None,
            status=PeerDeviationStatus.INSUFFICIENT_PEERS,
            peer_count=len(u_peers),
            reason_code="INSUFFICIENT_VALID_PEERS",
            reference_slice="PER-LOT BASELINE REFERENCE",
        )

    u_peers_arr = np.array(u_peers, dtype=np.float64)

    # 3. Compute robust location (median) and scale (MAD)
    med_u = float(np.median(u_peers_arr))
    mad_u = float(np.median(np.abs(u_peers_arr - med_u)))

    floor = custom_noise_floor if custom_noise_floor is not None else get_noise_floor(parameter)
    scale_u = max(1.4826 * mad_u, floor)

    # 4. Compute robust normalized deviation (z-score)
    z = (u_target - med_u) / scale_u

    # Back-transform median to physical units for explainability
    try:
        phys_median = inverse_transform_parameter(parameter, med_u)
    except Exception:
        phys_median = med_u

    # 5. Classify peer status
    abs_z = abs(z)
    if abs_z >= EXTREME_OUTLIER_Z_THRESHOLD:
        status = PeerDeviationStatus.PEER_EXTREME_OUTLIER
        reason_code = "EXTREME_PEER_OUTLIER"
    elif abs_z >= MILD_OUTLIER_Z_THRESHOLD:
        status = PeerDeviationStatus.PEER_MILD_OUTLIER
        reason_code = "MILD_PEER_OUTLIER"
    else:
        status = PeerDeviationStatus.PEER_NORMAL
        reason_code = "PEER_NORMAL"

    from sih26170.screening.calibration import calibrate_peer_score
    cal_score = calibrate_peer_score(z)

    return PeerEvidence(
        parameter=parameter,
        observed_value=float(observed_value),
        transformed_value=u_target,
        peer_median=phys_median,
        peer_mad=mad_u,
        peer_scale=scale_u,
        z_score=float(z),
        status=status,
        peer_count=len(u_peers),
        reason_code=reason_code,
        reference_slice="PER-LOT BASELINE REFERENCE",
        calibrated_score=cal_score,
    )

