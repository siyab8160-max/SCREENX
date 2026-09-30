"""Phase 5 Leave-One-Lot-Out (LOLO) Cross-Validation Evaluator for Module B.

Implements the formal evaluation contract authorized in docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md:
- Strictly partitioned: ONLY training/calibration lots (LOT_CAL_001 to LOT_CAL_050) are accessed.
- Phase 4B validation (LOT_VAL_*) and final (LOT_EVAL_*) partitions remain strictly quarantined.
- No ground truth or future information leakage.
- Exact primary task: [Value_0h, Value_24h] -> predicted Value_168h.
- Parameter-decoupled topology: IDSS, VGS(th), RDS(on), IGSS evaluated independently.
- Primary candidate families: Ridge regression, Huber regression.
- Frozen baselines: Carry-Forward, Two-Point Linear.
- Primary reporting metric: MAE in physical engineering units.
- Full descriptive metrics: MAE, RMSE, median absolute error, sample count, finite prediction rate.
- Complete model lineage recorded across all folds and parameters.
- No overall winner, ranking, or score declared.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd

from sih26170.prognostics.schema import PrognosticInput, PrognosticForecast
from sih26170.prognostics.baselines import (
    CarryForwardModel,
    TwoPointLinearModel,
)
from sih26170.prognostics.regression_models import (
    RidgeRegressionPrognosticModel,
    HuberRegressionPrognosticModel,
    BaseSupervisedRegressionModel,
)
from sih26170.prognostics.validation import (
    build_prognostic_input,
    assert_no_ground_truth_leakage,
)

PARAMETERS = ("IDSS", "VGS(th)", "RDS(on)", "IGSS")
UNITS = {
    "IDSS": "uA",
    "VGS(th)": "V",
    "RDS(on)": "mOhm",
    "IGSS": "nA",
}


def compute_metrics_for_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    unit: str,
    intervals: Optional[Tuple[np.ndarray, np.ndarray]] = None,
) -> Dict[str, Any]:
    """Compute comprehensive descriptive metrics for a set of predictions.

    Args:
        y_true: Array of ground-truth terminal values in physical engineering units.
        y_pred: Array of predicted terminal values in physical engineering units.
        unit: Physical engineering unit string.
        intervals: Optional tuple of (lower_bounds, upper_bounds) in physical engineering units.

    Returns:
        Dictionary of descriptive metrics.
    """
    total_count = len(y_true)
    finite_mask = np.isfinite(y_true) & np.isfinite(y_pred)
    finite_count = int(np.sum(finite_mask))
    finite_rate = float(finite_count / total_count) if total_count > 0 else 0.0

    if finite_count == 0:
        return {
            "total_count": total_count,
            "finite_count": 0,
            "finite_prediction_rate": 0.0,
            "mae": None,
            "rmse": None,
            "median_abs_error": None,
            "unit": unit,
        }

    valid_true = y_true[finite_mask]
    valid_pred = y_pred[finite_mask]
    abs_errors = np.abs(valid_true - valid_pred)
    sq_errors = (valid_true - valid_pred) ** 2

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(sq_errors)))
    med_ae = float(np.median(abs_errors))

    metrics: Dict[str, Any] = {
        "total_count": total_count,
        "finite_count": finite_count,
        "finite_prediction_rate": finite_rate,
        "mae": mae,
        "rmse": rmse,
        "median_abs_error": med_ae,
        "unit": unit,
    }

    if intervals is not None:
        low_arr, upp_arr = intervals
        valid_low = low_arr[finite_mask]
        valid_upp = upp_arr[finite_mask]
        coverage_hits = (valid_low <= valid_true) & (valid_true <= valid_upp)
        widths = valid_upp - valid_low
        metrics["coverage_rate_90"] = float(np.mean(coverage_hits))
        metrics["mean_interval_width"] = float(np.mean(widths))

    return metrics


def run_phase5_lolo_evaluation(
    telemetry_path: str = "data/synthetic_phase4b/observations.csv",
    output_dir: str = "data/evaluation_phase5",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Execute complete 50-fold Leave-One-Lot-Out Cross-Validation.

    Args:
        telemetry_path: Path to observations CSV.
        output_dir: Directory to save evaluation and manifest artifacts.

    Returns:
        Tuple of (results_dict, lineage_manifest_dict).
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. Load telemetry and assert partition governance
    df_raw = pd.read_csv(telemetry_path)
    assert_no_ground_truth_leakage(df_raw)

    # Strict partition filter: calibration lots only
    cal_lots = sorted([l for l in df_raw["lot_id"].unique() if l.startswith("LOT_CAL_")])
    if not cal_lots:
        raise ValueError(f"No LOT_CAL_ lots found in telemetry at {telemetry_path}")
    if len(cal_lots) != 50:
        raise ValueError(f"Expected exactly 50 LOT_CAL_ lots, found {len(cal_lots)}")

    # Isolate training dataframe strictly to LOT_CAL_ lots
    df_cal = df_raw[df_raw["lot_id"].isin(cal_lots)].copy()

    # Verify no validation or final evaluation lots are present in df_cal
    quarantined_lots = [l for l in df_cal["lot_id"].unique() if l.startswith("LOT_VAL_") or l.startswith("LOT_EVAL_")]
    if quarantined_lots:
        raise RuntimeError(f"FATAL LEAKAGE: Quarantined lots detected in calibration partition: {quarantined_lots}")

    print(f"Loaded {len(df_cal)} rows across {len(cal_lots)} calibration lots.")

    # 2. Extract [v0, v24, v168] triads for each component and parameter
    # Structure: dict[parameter, pd.DataFrame] indexed by (lot_id, component_id)
    param_data: Dict[str, pd.DataFrame] = {}
    for param in PARAMETERS:
        pdf = df_cal[df_cal["parameter_name"] == param]
        piv = pdf.pivot(index=["lot_id", "component_id"], columns="elapsed_hours", values="value")
        if 0 not in piv.columns or 24 not in piv.columns or 168 not in piv.columns:
            raise ValueError(f"Telemetry missing required checkpoints (0, 24, 168h) for {param}")
        triads = piv[[0, 24, 168]].dropna().reset_index()
        param_data[param] = triads

    model_families = ["RIDGE", "HUBER", "CARRY_FORWARD", "TWO_POINT_LINEAR"]

    # Storage for out-of-fold predictions:
    # dict[model_family, dict[parameter, list of (lot_id, comp_id, y_true, y_pred, y_low, y_upp, is_div)]]
    fold_predictions: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
        mf: {p: [] for p in PARAMETERS} for mf in model_families
    }

    # Storage for model lineage records:
    # list of lineage records
    lineage_records: List[Dict[str, Any]] = []

    # Fold-level MAEs for statistical stability reporting
    fold_maes: Dict[str, Dict[str, List[float]]] = {
        mf: {p: [] for p in PARAMETERS} for mf in model_families
    }

    # 3. 50-Fold LOLO Loop
    print(f"Starting 50-fold Leave-One-Lot-Out Cross-Validation across {len(cal_lots)} lots...")

    for fold_idx, held_out_lot in enumerate(cal_lots, start=1):
        train_lots = [l for l in cal_lots if l != held_out_lot]

        for param in PARAMETERS:
            unit = UNITS[param]
            triads = param_data[param]

            train_triads = triads[triads["lot_id"].isin(train_lots)]
            test_triads = triads[triads["lot_id"] == held_out_lot]

            X_train = train_triads[[0, 24]].values
            y_train = train_triads[168].values
            sample_lots_train = train_triads["lot_id"].values

            X_test = test_triads[[0, 24]].values
            y_test = test_triads[168].values
            test_comps = test_triads["component_id"].values

            # Build PrognosticInput list for the test lot components
            test_inputs = [
                PrognosticInput(
                    component_id=cid,
                    lot_id=held_out_lot,
                    parameter_name=param,
                    unit=unit,
                    as_of_hours=24,
                    target_hours=168,
                    historical_observations=[(0, float(v0)), (24, float(v24))],
                    data_sufficiency_passed=True,
                )
                for cid, (v0, v24) in zip(test_comps, X_test)
            ]

            # A. Fit and predict RIDGE
            ridge_model = RidgeRegressionPrognosticModel(
                parameter_name=param,
                unit=unit,
                l2_reg=1.0,
            )
            ridge_model.fit(X_train, y_train, sample_lot_ids=sample_lots_train, training_lot_ids=train_lots)
            lineage_ridge = ridge_model.get_lineage()
            lineage_ridge["fold_index"] = fold_idx
            lineage_ridge["held_out_lot_id"] = held_out_lot
            lineage_records.append(lineage_ridge)

            ridge_preds = [ridge_model.predict_single(inp) for inp in test_inputs]
            ridge_fold_abs_errs = []
            for inp, pred, y_tr in zip(test_inputs, ridge_preds, y_test):
                fold_predictions["RIDGE"][param].append({
                    "lot_id": held_out_lot,
                    "component_id": inp.component_id,
                    "y_true": float(y_tr),
                    "y_pred": float(pred.predicted_value),
                    "y_low": float(pred.interval_lower) if pred.interval_lower is not None else None,
                    "y_upp": float(pred.interval_upper) if pred.interval_upper is not None else None,
                    "is_divergent": pred.is_divergent_fallback,
                })
                if np.isfinite(pred.predicted_value):
                    ridge_fold_abs_errs.append(abs(float(y_tr) - float(pred.predicted_value)))
            if ridge_fold_abs_errs:
                fold_maes["RIDGE"][param].append(float(np.mean(ridge_fold_abs_errs)))

            # B. Fit and predict HUBER
            huber_model = HuberRegressionPrognosticModel(
                parameter_name=param,
                unit=unit,
                delta_scale=1.345,
                max_iter=50,
            )
            huber_model.fit(X_train, y_train, sample_lot_ids=sample_lots_train, training_lot_ids=train_lots)
            lineage_huber = huber_model.get_lineage()
            lineage_huber["fold_index"] = fold_idx
            lineage_huber["held_out_lot_id"] = held_out_lot
            lineage_records.append(lineage_huber)

            huber_preds = [huber_model.predict_single(inp) for inp in test_inputs]
            huber_fold_abs_errs = []
            for inp, pred, y_tr in zip(test_inputs, huber_preds, y_test):
                fold_predictions["HUBER"][param].append({
                    "lot_id": held_out_lot,
                    "component_id": inp.component_id,
                    "y_true": float(y_tr),
                    "y_pred": float(pred.predicted_value),
                    "y_low": float(pred.interval_lower) if pred.interval_lower is not None else None,
                    "y_upp": float(pred.interval_upper) if pred.interval_upper is not None else None,
                    "is_divergent": pred.is_divergent_fallback,
                })
                if np.isfinite(pred.predicted_value):
                    huber_fold_abs_errs.append(abs(float(y_tr) - float(pred.predicted_value)))
            if huber_fold_abs_errs:
                fold_maes["HUBER"][param].append(float(np.mean(huber_fold_abs_errs)))

            # C. Baseline: Carry Forward
            cf_model = CarryForwardModel()
            cf_preds = [cf_model.predict_single(inp) for inp in test_inputs]
            cf_fold_abs_errs = []
            for inp, pred, y_tr in zip(test_inputs, cf_preds, y_test):
                fold_predictions["CARRY_FORWARD"][param].append({
                    "lot_id": held_out_lot,
                    "component_id": inp.component_id,
                    "y_true": float(y_tr),
                    "y_pred": float(pred.predicted_value),
                    "y_low": float(pred.interval_lower) if pred.interval_lower is not None else None,
                    "y_upp": float(pred.interval_upper) if pred.interval_upper is not None else None,
                    "is_divergent": False,
                })
                if np.isfinite(pred.predicted_value):
                    cf_fold_abs_errs.append(abs(float(y_tr) - float(pred.predicted_value)))
            if cf_fold_abs_errs:
                fold_maes["CARRY_FORWARD"][param].append(float(np.mean(cf_fold_abs_errs)))

            # D. Baseline: Two-Point Linear
            tpl_model = TwoPointLinearModel()
            tpl_preds = [tpl_model.predict_single(inp) for inp in test_inputs]
            tpl_fold_abs_errs = []
            for inp, pred, y_tr in zip(test_inputs, tpl_preds, y_test):
                fold_predictions["TWO_POINT_LINEAR"][param].append({
                    "lot_id": held_out_lot,
                    "component_id": inp.component_id,
                    "y_true": float(y_tr),
                    "y_pred": float(pred.predicted_value),
                    "y_low": float(pred.interval_lower) if pred.interval_lower is not None else None,
                    "y_upp": float(pred.interval_upper) if pred.interval_upper is not None else None,
                    "is_divergent": False,
                })
                if np.isfinite(pred.predicted_value):
                    tpl_fold_abs_errs.append(abs(float(y_tr) - float(pred.predicted_value)))
            if tpl_fold_abs_errs:
                fold_maes["TWO_POINT_LINEAR"][param].append(float(np.mean(tpl_fold_abs_errs)))

        if fold_idx % 10 == 0 or fold_idx == 50:
            print(f"Completed fold {fold_idx}/50 ({held_out_lot})...")

    # 4. Compute aggregate evaluation metrics across all 50 folds
    results: Dict[str, Any] = {
        "metadata": {
            "evaluation_protocol": "Leave-One-Lot-Out (LOLO) Cross-Validation",
            "number_of_folds": len(cal_lots),
            "lots_evaluated": cal_lots,
            "partition": "LOT_CAL_001 through LOT_CAL_050",
            "validation_and_final_status": "QUARANTINED",
            "primary_task": "Value_0h, Value_24h -> predicted Value_168h",
            "primary_metric": "Mean Absolute Error (MAE) in physical engineering units",
            "models_evaluated": model_families,
            "parameters_evaluated": list(PARAMETERS),
        },
        "parameter_metrics": {},
    }

    for param in PARAMETERS:
        unit = UNITS[param]
        results["parameter_metrics"][param] = {
            "unit": unit,
            "models": {},
        }

        for mf in model_families:
            preds_list = fold_predictions[mf][param]
            y_tr_arr = np.array([p["y_true"] for p in preds_list], dtype=np.float64)
            y_pr_arr = np.array([p["y_pred"] for p in preds_list], dtype=np.float64)
            div_count = sum(1 for p in preds_list if p.get("is_divergent", False))

            intervals = None
            if preds_list and preds_list[0]["y_low"] is not None:
                low_arr = np.array([p["y_low"] for p in preds_list], dtype=np.float64)
                upp_arr = np.array([p["y_upp"] for p in preds_list], dtype=np.float64)
                intervals = (low_arr, upp_arr)

            summary = compute_metrics_for_predictions(
                y_true=y_tr_arr,
                y_pred=y_pr_arr,
                unit=unit,
                intervals=intervals,
            )
            summary["divergence_count"] = div_count

            # Add fold-level MAE statistics
            f_maes = fold_maes[mf][param]
            if f_maes:
                summary["fold_mae_mean"] = float(np.mean(f_maes))
                summary["fold_mae_std"] = float(np.std(f_maes))
                summary["fold_mae_min"] = float(np.min(f_maes))
                summary["fold_mae_max"] = float(np.max(f_maes))

            results["parameter_metrics"][param]["models"][mf] = summary

    # 5. Build Model Lineage Manifest
    results_json_str = json.dumps(results, indent=2, sort_keys=True)
    results_hash = hashlib.sha256(results_json_str.encode("utf-8")).hexdigest()

    manifest: Dict[str, Any] = {
        "manifest_version": "1.1.0",
        "phase": "PHASE_5_MODULE_B_PREDICTIVE_REGRESSION_STAGE_1A",
        "uncertainty_calibration": "NESTED_LOLO_OUT_OF_FOLD",
        "evaluation_type": "LEAVE_ONE_LOT_OUT_50_FOLDS",
        "dataset": {
            "telemetry_source": telemetry_path,
            "authorized_partition": "LOT_CAL_001 to LOT_CAL_050",
            "total_calibration_lots": len(cal_lots),
            "total_calibration_components": len(cal_lots) * 20,
            "quarantined_partitions": ["LOT_VAL_001 to LOT_VAL_020", "LOT_EVAL_001 to LOT_EVAL_020"],
        },
        "results_hash": results_hash,
        "total_lineage_records": len(lineage_records),
        "model_lineage_records": lineage_records,
    }

    # 6. Save versioned Stage-1A artifacts (preserving historical Stage-1 artifacts)
    results_file = output_path / "phase5_stage1a_uncertainty_lolo_results.json"
    manifest_file = output_path / "phase5_stage1a_model_lineage_manifest.json"

    with open(results_file, "w", encoding="utf-8") as f:
        f.write(results_json_str)

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    print(f"\nSaved Stage-1A LOLO evaluation results to: {results_file}")
    print(f"Saved Stage-1A model lineage manifest to: {manifest_file}")

    return results, manifest


if __name__ == "__main__":
    run_phase5_lolo_evaluation()
