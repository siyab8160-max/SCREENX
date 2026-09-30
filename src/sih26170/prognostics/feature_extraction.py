"""Strictly as-of feature extraction for Module B Stage 2 prognostics.

Defines the exact Stage 2 feature contract:
- Provenance: strictly observations with elapsed_hours <= as_of_hours
- Isolation: no future telemetry, no future lot statistics, no ground truth
- Audit trail: cryptographic hash for each feature vector
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd

from sih26170.prognostics.schema import PrognosticInput
from sih26170.prognostics.validation import assert_no_ground_truth_leakage
from sih26170.screening.transforms import transform_parameter


@dataclass(frozen=True)
class PrognosticFeatures:
    """Feature contract for Stage 2 prognostic models."""
    component_id: str
    lot_id: str
    parameter_name: str
    unit: str
    as_of_hours: int
    target_hours: int
    # Component-level temporal features (transformed coordinate space)
    u_as_of: float
    u_0h: float
    delta_u: float
    raw_slope_u: float
    theil_sen_slope_u: Optional[float]
    # Contemporaneous lot-level context (strictly at as_of_hours)
    lot_median_slope_u: float
    lot_mad_slope_u: float
    # Upstream Module A screening evidence (strictly as of <= as_of_hours)
    module_a_drift_alert: bool
    module_a_step_alert: bool
    module_a_state: str
    # Audit metadata
    feature_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "lot_id": self.lot_id,
            "parameter_name": self.parameter_name,
            "unit": self.unit,
            "as_of_hours": self.as_of_hours,
            "target_hours": self.target_hours,
            "u_as_of": self.u_as_of,
            "u_0h": self.u_0h,
            "delta_u": self.delta_u,
            "raw_slope_u": self.raw_slope_u,
            "theil_sen_slope_u": self.theil_sen_slope_u,
            "lot_median_slope_u": self.lot_median_slope_u,
            "lot_mad_slope_u": self.lot_mad_slope_u,
            "module_a_drift_alert": self.module_a_drift_alert,
            "module_a_step_alert": self.module_a_step_alert,
            "module_a_state": self.module_a_state,
            "feature_hash": self.feature_hash,
        }


def extract_features_for_input(
    prog_input: PrognosticInput,
    contemporaneous_lot_inputs: Optional[Sequence[PrognosticInput]] = None,
) -> PrognosticFeatures:
    """Extract strictly as-of feature vector for a given PrognosticInput.

    Args:
        prog_input: Target component prognostic input
        contemporaneous_lot_inputs: Optional sequence of PrognosticInputs for peers in the same lot at as_of_hours

    Returns:
        PrognosticFeatures instance with full provenance and no future leakage.
    """
    obs_map = {t: v for t, v in prog_input.historical_observations}
    param = prog_input.parameter_name
    as_of = prog_input.as_of_hours

    latest = prog_input.get_latest_observation()
    baseline = prog_input.get_baseline_observation()

    if latest is None or baseline is None:
        raise ValueError(f"Cannot extract features for {prog_input.component_id}: missing baseline or latest observation")

    y_as_of = float(latest[1])
    y_0 = float(baseline[1])

    u_as_of = transform_parameter(param, y_as_of)
    u_0h = transform_parameter(param, y_0)
    delta_u = u_as_of - u_0h
    raw_slope_u = delta_u / float(as_of) if as_of > 0 else 0.0

    # Theil-Sen slope (only when K >= 3 checkpoints exist, e.g. at 96h)
    theil_sen_slope_u: Optional[float] = None
    checkpoints = sorted([t for t in obs_map.keys() if t <= as_of])
    if len(checkpoints) >= 3:
        transformed_pts = [(t, transform_parameter(param, obs_map[t])) for t in checkpoints]
        slopes = []
        for i in range(len(transformed_pts)):
            for j in range(i + 1, len(transformed_pts)):
                dt = transformed_pts[j][0] - transformed_pts[i][0]
                if dt > 0:
                    slopes.append((transformed_pts[j][1] - transformed_pts[i][1]) / dt)
        if slopes:
            theil_sen_slope_u = float(np.median(slopes))

    # Contemporaneous lot statistics strictly at as_of_hours
    lot_median_slope_u = raw_slope_u
    lot_mad_slope_u = 0.0
    if contemporaneous_lot_inputs:
        peer_slopes = []
        for peer in contemporaneous_lot_inputs:
            if peer.parameter_name == param and peer.as_of_hours == as_of and peer.data_sufficiency_passed:
                p_latest = peer.get_latest_observation()
                p_base = peer.get_baseline_observation()
                if p_latest and p_base:
                    try:
                        p_u_as_of = transform_parameter(param, float(p_latest[1]))
                        p_u_0 = transform_parameter(param, float(p_base[1]))
                        if as_of > 0:
                            peer_slopes.append((p_u_as_of - p_u_0) / float(as_of))
                    except Exception:
                        continue
        if len(peer_slopes) >= 3:
            arr = np.array(peer_slopes)
            med = float(np.median(arr))
            mad = float(np.median(np.abs(arr - med)))
            lot_median_slope_u = med
            lot_mad_slope_u = 1.4826 * mad

    # Upstream Module A screening evidence (guaranteed <= as_of_hours)
    module_a_drift_alert = False
    module_a_step_alert = False
    module_a_state = "UNKNOWN"

    sr = prog_input.screening_result
    if sr is not None:
        sr_as_of = getattr(sr, "as_of_hours", None)
        if sr_as_of is not None and sr_as_of > as_of:
            raise ValueError(f"Leakage detected: Module A screening result is as-of {sr_as_of}h, exceeding {as_of}h")
        module_a_state = str(getattr(sr, "final_state", "UNKNOWN"))
        param_results = getattr(sr, "parameter_results", {})
        if param in param_results:
            p_res = param_results[param]
            drift_ev = getattr(p_res, "drift_evidence", None)
            if drift_ev is not None:
                module_a_drift_alert = bool(getattr(drift_ev, "status", None) == "DRIFT_ALERT" or getattr(drift_ev, "acceleration_evidence", False))
            step_ev = getattr(p_res, "step_evidence", None)
            if step_ev is not None:
                module_a_step_alert = bool(getattr(step_ev, "status", None) == "STEP_ALERT")

    # Hash for auditability
    raw_hash_input = (
        f"{prog_input.component_id}:{param}:{as_of}:{u_as_of:.6f}:{u_0h:.6f}:"
        f"{raw_slope_u:.6e}:{lot_median_slope_u:.6e}:{lot_mad_slope_u:.6e}"
    )
    import hashlib
    feature_hash = hashlib.sha256(raw_hash_input.encode("utf-8")).hexdigest()

    return PrognosticFeatures(
        component_id=prog_input.component_id,
        lot_id=prog_input.lot_id,
        parameter_name=param,
        unit=prog_input.unit,
        as_of_hours=as_of,
        target_hours=prog_input.target_hours,
        u_as_of=u_as_of,
        u_0h=u_0h,
        delta_u=delta_u,
        raw_slope_u=raw_slope_u,
        theil_sen_slope_u=theil_sen_slope_u,
        lot_median_slope_u=lot_median_slope_u,
        lot_mad_slope_u=lot_mad_slope_u,
        module_a_drift_alert=module_a_drift_alert,
        module_a_step_alert=module_a_step_alert,
        module_a_state=module_a_state,
        feature_hash=feature_hash,
    )
