"""Joint-parameter multivariate anomaly backstop detector (D_joint).

Detector J: Comprehensive multivariate anomaly backstop detector (D_joint):
- Computes Mahalanobis distance across all four electrical parameters jointly
  (IDSS, VGS(th), RDS(on), IGSS in their respective transform spaces).
- Uses Leave-One-Out (LOO) robust shrinkage covariance to prevent outlier self-contamination.
- Serves as an independent multivariate backstop for anomalies where correlated
  sub-threshold movement across multiple parameters escapes univariate detector cutoffs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from sih26170.screening.schema import JointEvidence, JointStatus
from sih26170.screening.transforms import get_noise_floor, transform_parameter

DEFAULT_JOINT_MAHALANOBIS_THRESHOLD: float = 4.25
SHRINKAGE_ALPHA: float = 0.20
MINIMUM_LOT_SIZE_FOR_JOINT: int = 6


def evaluate_joint_mahalanobis(
    component_id: str,
    lot_id: str,
    checkpoint: int,
    lot_observations_as_of: pd.DataFrame,
    primary_parameters: Optional[List[str]] = None,
    threshold: float = DEFAULT_JOINT_MAHALANOBIS_THRESHOLD,
    shrinkage_alpha: float = SHRINKAGE_ALPHA,
) -> JointEvidence:
    """Evaluate joint Mahalanobis distance across all parameters for a single component.

    Args:
        component_id: Target component identifier
        lot_id: Lot identifier
        checkpoint: Current elapsed hours checkpoint T
        lot_observations_as_of: Filtered lot telemetry up to checkpoint T
        primary_parameters: List of 4 parameters to evaluate jointly (default: IDSS, VGS(th), RDS(on), IGSS)
        threshold: Critical distance cutoff (default: 4.25 ~ chi^2_4 0.999 quantile)
        shrinkage_alpha: Intensity of shrinkage toward identity correlation (default: 0.20)

    Returns:
        JointEvidence containing exact Mahalanobis distance, status, and feature contributions.
    """
    if primary_parameters is None:
        primary_parameters = ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]

    curr_df = lot_observations_as_of[lot_observations_as_of["elapsed_hours"] == checkpoint]
    cids = sorted(curr_df["component_id"].unique())
    n_lot = len(cids)

    # Small lot guard
    if n_lot < MINIMUM_LOT_SIZE_FOR_JOINT or component_id not in cids:
        return JointEvidence(
            component_id=component_id,
            checkpoint=checkpoint,
            mahalanobis_distance=None,
            critical_threshold=threshold,
            status=JointStatus.INSUFFICIENT_PEERS,
            suspected=False,
            reason_code="PEER_COUNT_INSUFFICIENT_FOR_JOINT_COVARIANCE",
            feature_contributions={},
        )

    # Build N x 4 transformed matrix (evaluating early changes Delta u when t=0 baseline is present)
    p_count = len(primary_parameters)
    X = np.zeros((n_lot, p_count), dtype=float)

    has_t0 = (checkpoint > 0) and (0 in lot_observations_as_of["elapsed_hours"].values)
    input_space = "delta" if has_t0 else "level"
    t0_df = lot_observations_as_of[lot_observations_as_of["elapsed_hours"] == 0] if has_t0 else None

    for j, p in enumerate(primary_parameters):
        p_df = curr_df[curr_df["parameter_name"] == p]
        v_map = dict(zip(p_df["component_id"], p_df["value"]))
        v0_map = (
            dict(zip(t0_df[t0_df["parameter_name"] == p]["component_id"], t0_df[t0_df["parameter_name"] == p]["value"]))
            if t0_df is not None else {}
        )
        for i, cid in enumerate(cids):
            val = v_map.get(cid, float("nan"))
            try:
                u_curr = transform_parameter(p, val)
                if has_t0 and cid in v0_map:
                    u_0 = transform_parameter(p, v0_map[cid])
                    X[i, j] = u_curr - u_0
                else:
                    X[i, j] = u_curr
            except (ValueError, OverflowError):
                X[i, j] = float("nan")

    # If any column has non-finite values for the target component, return insufficient
    target_idx = cids.index(component_id)
    if not np.all(np.isfinite(X[target_idx, :])):
        return JointEvidence(
            component_id=component_id,
            checkpoint=checkpoint,
            mahalanobis_distance=None,
            critical_threshold=threshold,
            status=JointStatus.INSUFFICIENT_PEERS,
            suspected=False,
            reason_code="NON_FINITE_TRANSFORM_FOR_TARGET_COMPONENT",
            feature_contributions={},
            input_space=input_space,
        )

    # Leave-One-Out (LOO) cohort: exclude target component from reference baseline
    other_indices = [k for k in range(n_lot) if k != target_idx]
    X_other = X[other_indices, :]

    # Robust LOO center and scales
    med_other = np.nanmedian(X_other, axis=0)
    mad_other = 1.4826 * np.nanmedian(np.abs(X_other - med_other), axis=0)
    noise_floors = np.array([get_noise_floor(p) for p in primary_parameters])
    scales_other = np.maximum(mad_other, noise_floors)

    # Standardize other observations
    Z_other = (X_other - med_other) / scales_other

    # Filter out any non-finite peer rows
    valid_peer_mask = np.all(np.isfinite(Z_other), axis=1)
    Z_valid = Z_other[valid_peer_mask, :]
    n_valid = len(Z_valid)

    if n_valid < 4:
        return JointEvidence(
            component_id=component_id,
            checkpoint=checkpoint,
            mahalanobis_distance=None,
            critical_threshold=threshold,
            status=JointStatus.INSUFFICIENT_PEERS,
            suspected=False,
            reason_code="INSUFFICIENT_VALID_PEERS_FOR_COVARIANCE",
            feature_contributions={},
            input_space=input_space,
        )

    # Shrinkage correlation matrix R_shrunk = (1 - alpha) * R + alpha * I
    R_sample = (Z_valid.T @ Z_valid) / max(1, n_valid - 1)
    R_shrunk = (1.0 - shrinkage_alpha) * R_sample + shrinkage_alpha * np.eye(p_count)

    try:
        R_inv = np.linalg.inv(R_shrunk)
    except np.linalg.LinAlgError:
        R_inv = np.eye(p_count)

    # Compute target component standardized z-vector
    z_target = (X[target_idx, :] - med_other) / scales_other

    # Exact Mahalanobis distance D = sqrt(z^T * R_inv * z)
    d_sq = float(z_target @ R_inv @ z_target)
    d_mahal = float(np.sqrt(max(0.0, d_sq)))

    # Feature-by-feature partial contribution: z_j * (R_inv * z)_j
    quad_vec = z_target * (R_inv @ z_target)
    feature_contributions = {
        primary_parameters[j]: float(round(quad_vec[j], 4)) for j in range(p_count)
    }

    suspected = d_mahal >= threshold
    status = JointStatus.JOINT_ANOMALY_ALERT if suspected else JointStatus.NOMINAL_JOINT
    reason_code = (
        f"JOINT_MAHALANOBIS_EXCESS_{d_mahal:.2f}_SIGMA"
        if suspected
        else "NOMINAL_JOINT_COVARIANCE"
    )

    from sih26170.screening.calibration import calibrate_joint_score
    cal_score = calibrate_joint_score(d_mahal)

    return JointEvidence(
        component_id=component_id,
        checkpoint=checkpoint,
        mahalanobis_distance=float(round(d_mahal, 4)),
        critical_threshold=float(threshold),
        status=status,
        suspected=suspected,
        reason_code=reason_code,
        feature_contributions=feature_contributions,
        calibrated_score=cal_score,
        input_space=input_space,
    )


def evaluate_multivariate_joint_backstop(
    obs_df: pd.DataFrame,
    gt_df: pd.DataFrame,
    lot_ids: List[str],
    checkpoint: int = 24,
) -> Dict[str, Any]:
    """Evaluates the statistical discrimination of the multivariate D_joint detector."""
    comp_gt = gt_df.groupby("component_id")[["is_degradation", "is_spec_failure"]].any()
    comp_gt["is_defective"] = comp_gt["is_degradation"] | comp_gt["is_spec_failure"]

    rows = []
    for lot_id in lot_ids:
        lot_obs = obs_df[(obs_df["lot_id"] == lot_id) & (obs_df["elapsed_hours"] <= checkpoint)]
        cids = lot_obs[lot_obs["elapsed_hours"] == checkpoint]["component_id"].unique().tolist()
        for cid in cids:
            ev = evaluate_joint_mahalanobis(cid, lot_id, checkpoint, lot_obs)
            d_val = ev.mahalanobis_distance
            is_def = bool(comp_gt.loc[cid, "is_defective"]) if cid in comp_gt.index else False
            rows.append({
                "component_id": cid,
                "lot_id": lot_id,
                "d_joint": d_val,
                "is_defective": is_def,
                "flagged": ev.suspected,
            })

    res_df = pd.DataFrame(rows)
    valid_d = res_df.dropna(subset=["d_joint"])

    valid_nom = valid_d[~valid_d["is_defective"]]
    mean_d_nom = float(valid_nom["d_joint"].mean()) if len(valid_nom) > 0 else 0.0
    p95_d_nom = float(valid_nom["d_joint"].quantile(0.95)) if len(valid_nom) > 0 else 0.0

    valid_def = valid_d[valid_d["is_defective"]]
    mean_d_def = float(valid_def["d_joint"].mean()) if len(valid_def) > 0 else 0.0
    p05_d_def = float(valid_def["d_joint"].quantile(0.05)) if len(valid_def) > 0 else 0.0

    tp = int(len(valid_def[valid_def["flagged"]]))
    fp = int(len(valid_nom[valid_nom["flagged"]]))
    fn = int(len(valid_def[~valid_def["flagged"]]))
    tn = int(len(valid_nom[~valid_nom["flagged"]]))

    return {
        "metric_id": "1.2",
        "description": "Multivariate Joint Mahalanobis Backstop (D_joint)",
        "threshold": DEFAULT_JOINT_MAHALANOBIS_THRESHOLD,
        "components_evaluated": int(len(valid_d)),
        "mean_mahalanobis_nominal": float(round(mean_d_nom, 3)),
        "p95_mahalanobis_nominal": float(round(p95_d_nom, 3)),
        "mean_mahalanobis_defective": float(round(mean_d_def, 3)),
        "p05_mahalanobis_defective": float(round(p05_d_def, 3)),
        "separation_ratio": float(round(mean_d_def / max(1e-9, mean_d_nom), 2)),
        "contingency": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


