"""Phase 5 Independent Validation Evaluator for Locked Ridge Regression Models.

Implements the formal evaluation contract authorized in docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md:
- Strictly partitioned: Fits models on Calibration Partition (LOT_CAL_001 to LOT_CAL_050).
- Evaluates on Validation Partition (LOT_VAL_001 to LOT_VAL_025).
- Final Evaluation Partition (LOT_EVAL_*) remains strictly quarantined and inaccessible.
- Primary task: [Value_0h, Value_24h] -> predicted Value_168h.
- Parameter-decoupled Ridge models: IDSS, VGS(th), RDS(on), IGSS.
- Computes primary and secondary metrics: Physical MAE, RMSE, MedAE, empirical coverage, interval width, Winkler score.
- Generates reproducible, auditable evaluation artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from sih26170.prognostics.regression_models import (
    RidgeRegressionPrognosticModel,
    Z_90,
    get_noise_floor,
)
from sih26170.screening.transforms import (
    transform_parameter,
    inverse_transform_parameter,
    NOISE_FLOORS,
)


PARAMETERS = ("IDSS", "VGS(th)", "RDS(on)", "IGSS")
UNITS = {
    "IDSS": "uA",
    "VGS(th)": "V",
    "RDS(on)": "mOhm",
    "IGSS": "nA",
}


def assert_quarantine_integrity(evaluated_df: pd.DataFrame) -> None:
    """Verify that no final-evaluation lots (LOT_EVAL_*) are present in evaluated or training data."""
    lots = evaluated_df["lot_id"].unique()
    eval_lots = [l for l in lots if str(l).startswith("LOT_EVAL_")]
    if eval_lots:
        raise PermissionError(
            f"CRITICAL DATA GOVERNANCE BREACH: Final evaluation lots {eval_lots[:3]} detected in evaluator!"
        )


def compute_winkler_score_90(y_true: np.ndarray, y_lower: np.ndarray, y_upper: np.ndarray) -> float:
    """Compute Winkler score for a 90% prediction interval (alpha = 0.10)."""
    y = np.asarray(y_true, dtype=np.float64)
    l = np.asarray(y_lower, dtype=np.float64)
    u = np.asarray(y_upper, dtype=np.float64)

    width = u - l
    below = np.maximum(0.0, l - y)
    above = np.maximum(0.0, y - u)

    score = width + 20.0 * below + 20.0 * above
    return float(np.mean(score))


def run_phase5_validation(
    observations_csv_path: Path,
    output_results_path: Optional[Path] = None,
    output_manifest_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute independent validation of locked Ridge models on LOT_VAL_*.

    Args:
        observations_csv_path: Path to observations.csv containing synthetic data.
        output_results_path: Optional path to save JSON results.
        output_manifest_path: Optional path to save model lineage manifest.

    Returns:
        Dictionary containing comprehensive validation results.
    """
    df = pd.read_csv(observations_csv_path)

    # 1. Strictly isolate calibration (training) and validation (evaluation) partitions
    cal_mask = df["lot_id"].str.startswith("LOT_CAL_")
    val_mask = df["lot_id"].str.startswith("LOT_VAL_")

    cal_df = df[cal_mask].copy()
    val_df = df[val_mask].copy()

    # Enforce strict quarantine: neither training nor validation can contain LOT_EVAL_
    assert_quarantine_integrity(cal_df)
    assert_quarantine_integrity(val_df)

    cal_lots = sorted(cal_df["lot_id"].unique())
    val_lots = sorted(val_df["lot_id"].unique())

    if len(cal_lots) != 50:
        raise ValueError(f"Expected 50 calibration lots, got {len(cal_lots)}")
    if len(val_lots) != 25:
        raise ValueError(f"Expected 25 validation lots, got {len(val_lots)}")

    # Pivot into component-level sequences
    piv_cal = cal_df.pivot(
        index=["lot_id", "component_id", "parameter_name"],
        columns="elapsed_hours",
        values="value",
    ).reset_index()

    piv_val = val_df.pivot(
        index=["lot_id", "component_id", "parameter_name"],
        columns="elapsed_hours",
        values="value",
    ).reset_index()

    results: Dict[str, Any] = {
        "metadata": {
            "evaluation_stage": "PHASE_5_INDEPENDENT_VALIDATION",
            "selected_model": "RIDGE_REGRESSION",
            "model_lock": "LOCKED_PRE_VALIDATION",
            "governing_protocol": "docs/PHASE_5_MODEL_SELECTION_PROTOCOL.md",
            "training_partition": "LOT_CAL_001_TO_LOT_CAL_050",
            "validation_partition": "LOT_VAL_001_TO_LOT_VAL_025",
            "n_calibration_lots": len(cal_lots),
            "n_calibration_components": len(piv_cal) // 4,
            "n_validation_lots": len(val_lots),
            "n_validation_components": len(piv_val) // 4,
            "observations_hash": hashlib.sha256(open(observations_csv_path, "rb").read()).hexdigest(),
        },
        "parameter_metrics": {},
    }

    manifest_records: List[Dict[str, Any]] = []

    for param in PARAMETERS:
        unit = UNITS[param]
        sub_cal = piv_cal[piv_cal["parameter_name"] == param].copy()
        sub_val = piv_val[piv_val["parameter_name"] == param].copy()

        X_cal = sub_cal[[0, 24]].values
        y_cal = sub_cal[168].values
        lots_cal = sub_cal["lot_id"].values

        X_val = sub_val[[0, 24]].values
        y_val = sub_val[168].values
        lots_val = sub_val["lot_id"].values
        comps_val = sub_val["component_id"].values

        # 2. Fit locked Ridge model strictly on 50 calibration lots with nested LOLO uncertainty
        model = RidgeRegressionPrognosticModel(parameter_name=param, unit=unit, l2_reg=1.0)
        model.fit(X_cal, y_cal, sample_lot_ids=lots_cal)

        # 3. Generate predictions and intervals on validation partition
        y_pred, y_lower, y_upper = model.predict_physical(X_val)

        # Primary metrics
        abs_err = np.abs(y_val - y_pred)
        sq_err = (y_val - y_pred) ** 2

        mae = float(np.mean(abs_err))
        rmse = float(np.sqrt(np.mean(sq_err)))
        med_ae = float(np.median(abs_err))

        in_interval = (y_val >= y_lower) & (y_val <= y_upper)
        coverage_90 = float(np.mean(in_interval))
        mean_width = float(np.mean(y_upper - y_lower))
        winkler = compute_winkler_score_90(y_val, y_lower, y_upper)

        # Baselines on validation partition
        cf_pred = X_val[:, 1]  # Value_24h
        cf_mae = float(np.mean(np.abs(y_val - cf_pred)))

        tpl_pred = 7.0 * X_val[:, 1] - 6.0 * X_val[:, 0]
        tpl_mae = float(np.mean(np.abs(y_val - tpl_pred)))

        # Per-lot validation breakdown
        per_lot_breakdown: Dict[str, Dict[str, float]] = {}
        lot_maes: List[float] = []

        for lot in val_lots:
            l_mask = (lots_val == lot)
            l_abs_err = abs_err[l_mask]
            l_mae = float(np.mean(l_abs_err))
            l_cov = float(np.mean(in_interval[l_mask]))
            l_width = float(np.mean(y_upper[l_mask] - y_lower[l_mask]))
            lot_maes.append(l_mae)
            per_lot_breakdown[lot] = {
                "mae": l_mae,
                "coverage_90": l_cov,
                "mean_width": l_width,
                "n_samples": int(np.sum(l_mask)),
            }

        # Parameter summary dictionary
        results["parameter_metrics"][param] = {
            "parameter_name": param,
            "unit": unit,
            "n_samples": len(y_val),
            "primary_metrics": {
                "mae": mae,
                "rmse": rmse,
                "median_abs_error": med_ae,
                "coverage_rate_90": coverage_90,
                "mean_interval_width": mean_width,
                "winkler_score": winkler,
            },
            "baselines": {
                "carry_forward_mae": cf_mae,
                "two_point_linear_mae": tpl_mae,
                "ridge_improvement_vs_carry_forward_pct": float((cf_mae - mae) / cf_mae * 100),
            },
            "lot_distribution": {
                "lot_mae_mean": float(np.mean(lot_maes)),
                "lot_mae_std": float(np.std(lot_maes)),
                "lot_mae_min": float(np.min(lot_maes)),
                "lot_mae_max": float(np.max(lot_maes)),
            },
            "per_lot_breakdown": per_lot_breakdown,
            "uncertainty_provenance": {
                "sigma_eff": float(model._sigma_eff_u_scalar),
                "noise_floor": float(get_noise_floor(param)),
                "calibration_oof_count": model.oof_residual_count_,
                "interval_quantile_z90": Z_90,
            },
            "model_lineage": {
                "coefficients": [float(c) for c in model.coefficients_],
                "preprocessor_params": {k: float(v) for k, v in model.preprocessor_params_.items()},
                "hyperparameters": dict(model.hyperparameters),
            },
        }

        manifest_records.append({
            "parameter_name": param,
            "unit": unit,
            "model_id": model.model_id,
            "model_family": model.model_family,
            "coefficients": [float(c) for c in model.coefficients_],
            "sigma_eff": float(model._sigma_eff_u_scalar),
            "preprocessor_params": {k: float(v) for k, v in model.preprocessor_params_.items()},
            "hyperparameters": dict(model.hyperparameters),
            "validation_sample_count": len(y_val),
            "validation_mae": mae,
            "validation_coverage_90": coverage_90,
        })

    # Save results if requested
    if output_results_path is not None:
        output_results_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_results_path, "w") as f:
            json.dump(results, f, indent=2, sort_keys=True)

    if output_manifest_path is not None:
        output_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_manifest_path, "w") as f:
            json.dump({
                "stage": "PHASE_5_VALIDATION",
                "records": manifest_records,
            }, f, indent=2, sort_keys=True)

    return results


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent.parent
    obs_file = root / "data/synthetic_phase4b/observations.csv"
    res_out = root / "data/evaluation_phase5/phase5_validation_results.json"
    man_out = root / "data/evaluation_phase5/phase5_validation_lineage_manifest.json"

    print("Running Phase 5 Independent Validation...")
    res = run_phase5_validation(obs_file, res_out, man_out)
    print("Validation completed successfully.")
