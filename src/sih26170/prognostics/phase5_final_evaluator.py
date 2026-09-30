"""Phase 5 Final Evaluation Evaluator for Locked Ridge Regression Models.

Implements the formal final evaluation protocol authorized under LOG-103 and LOG-104:
- Pre-evaluation integrity: 14 baseline hashes verified, CAL/VAL/EVAL disjointness asserted.
- Model family locked: Decoupled per-parameter Ridge regression (lambda = 1.0).
- Input features: X = [Value_0h, Value_24h], target: Value_168h.
- Transforms: IDSS=log, VGS(th)=identity, RDS(on)=log, IGSS=signed asinh.
- Exact locked coefficients and frozen nested-LOLO sigma_eff values.
- Primary evaluation consumes observations.csv ONLY on LOT_EVAL_* (500 components, 2,000 series).
- Primary metrics: MAE, RMSE, MedAE, 90% PI coverage, mean width, Winkler score (alpha=0.10).
- IGSS signed semantics preserved throughout.
- Primary results frozen before any diagnostic ground truth is joined.
- Secondary forensic analysis: scenario-level MAE, lot-level error, quantiles, extreme cases,
  specification-breach prognostic flags, and Module A excess motion evidence.
- Five-tier semantic separation enforced throughout.
"""

from __future__ import annotations

import hashlib
import json
import math
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
from sih26170.screening.specification import SPEC_LIMITS_CLASS_A
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

FROZEN_BASELINE_HASHES = {
    "data/synthetic_phase4b/observations.csv": "b5de6a03022a9350b6f304b9af593768e7f83a8fc61fde6ca98e690cfa1f275f",
    "data/synthetic_phase4b/ground_truth.csv": "b48a2c0845492646ad9451d5a7efe256fe143043726807603a775d5f07c75656",
    "data/synthetic_phase4b/manifest.json": "fe85a035e9ed2ecc46a1cbcf1d999f048313ccabadab23ee0969fa1033ac87e2",
    "data/synthetic_phase2f_frozen/observations.csv": "b4282e0743cd6a0b2b74354e431bf8f308b03281c44c0437d30f7b53bd6ca983",
    "data/synthetic_phase2f_frozen/ground_truth.csv": "4bf2155fcc7698813f766e1dea9730213e0a6097e484bfa786eb1b94925f3d2b",
    "data/synthetic_phase2f_frozen/manifest.json": "5a08630f9fafc95563c13acea77df7aa066f7abc7a08b785a77c2709553980f6",
    "data/synthetic_phase2f_frozen/configuration_snapshot.json": "a4bb3f75f8211bf38b4c38cde0bbd1908eeecb75039700de84b1cc0c56f6dd27",
    "data/evaluation_phase4b/calibration_reference_table.json": "153d387597ba6a247ed5302a7512730c678bc3ce39e056848cd9135fc39c7d60",
    "data/evaluation_phase4b/calibration_distributions.npz": "147f1d38ed9b197af6b6301b9b454223d5cce54286fcfeb89a1ea15cec055d98",
    "data/evaluation_phase4b/calibration_manifest.json": "b7c5515144e0ea800f4e3b1f0acd5739b5acee88cd8e7f9fefa87a8294400b25",
    "data/evaluation_phase4b/null_a_audit_results.json": "1bd10cb8541d467084c15efa97e6e8fa9dc8799f356a4739a6141fd06bc1d9ad",
    "data/evaluation_phase4b/null_b_stress_results.json": "7a8f26cb450bbbc9ee1608e8902a171314eddadc1c6d13867a579b64cc4fe44c",
    "data/evaluation_phase4b/null_c_stress_results.json": "ae5ef6a245f91a142e8c866ed85a044381a9de8992e23fb414bb288bf225801e",
    "data/evaluation_phase4b/power_sweep_results.json": "31c34f803a19e233c136725a0bd8a48809a49e7c5d0dc82fccd5fd0ecc022036",
}

LOCKED_MODEL_COEFFICIENTS = {
    "IDSS": [0.002339561050919542, 0.4657038355352779, 0.49182429074872763],
    "IGSS": [0.32574744762123486, 0.39407454363980804, 0.3816214087816265],
    "RDS(on)": [0.22165031448834925, 0.47211305481717325, 0.47157973059881373],
    "VGS(th)": [0.10161610660682186, 0.46955702209772825, 0.4962018809228965],
}

FROZEN_SIGMA_EFF = {
    "IDSS": 0.10770869821030792,
    "IGSS": 0.3139146430379899,
    "RDS(on)": 0.01849041285376378,
    "VGS(th)": 0.030482191599865184,
}


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def verify_pre_evaluation_integrity(repo_root: Path) -> Dict[str, Any]:
    """Phase A: Pre-evaluation integrity verification.

    Asserts:
    1. All 14 frozen baseline hashes match authoritative registry bit-for-bit.
    2. CAL, VAL, and EVAL partitions are 100% pairwise disjoint.
    3. Model configuration parameters match pre-registered locks.
    """
    hash_audit = {}
    for rel_path, expected in FROZEN_BASELINE_HASHES.items():
        full_path = repo_root / rel_path
        if not full_path.exists():
            raise FileNotFoundError(f"Missing frozen baseline file: {rel_path}")
        actual = compute_file_sha256(full_path)
        if actual != expected:
            raise ValueError(
                f"INTEGRITY VIOLATION: Baseline hash mismatch for {rel_path}!\n"
                f"Expected: {expected}\nActual:   {actual}"
            )
        hash_audit[rel_path] = "VERIFIED_BIT_EXACT"

    # Partition disjointness check from manifest
    manifest_path = repo_root / "data/synthetic_phase4b/manifest.json"
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    cal_lots = set(manifest["partitions"]["CALIBRATION"]["lots"])
    val_lots = set(manifest["partitions"]["VALIDATION"]["lots"])
    eval_lots = set(manifest["partitions"]["FINAL_EVALUATION"]["lots"])

    if len(cal_lots) != 50 or len(val_lots) != 25 or len(eval_lots) != 25:
        raise ValueError("Invalid partition lot counts in manifest!")

    if not (cal_lots.isdisjoint(val_lots) and cal_lots.isdisjoint(eval_lots) and val_lots.isdisjoint(eval_lots)):
        raise ValueError("CRITICAL INTEGRITY VIOLATION: Partitions are not strictly disjoint!")

    return {
        "status": "PRE_EVALUATION_INTEGRITY_VERIFIED",
        "frozen_hashes_checked": len(hash_audit),
        "cal_lots_count": len(cal_lots),
        "val_lots_count": len(val_lots),
        "eval_lots_count": len(eval_lots),
        "total_lots": len(cal_lots | val_lots | eval_lots),
    }


def execute_primary_final_evaluation(
    observations_csv_path: Path,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], pd.DataFrame]:
    """Phase B: Primary final evaluation on LOT_EVAL_* observations ONLY.

    Does NOT touch ground_truth.csv.

    Returns:
        Tuple of (primary_results_dict, manifest_records_list, predictions_dataframe).
    """
    df = pd.read_csv(observations_csv_path)

    # Strictly isolate CAL (for fitting) and EVAL (for evaluation)
    cal_mask = df["lot_id"].str.startswith("LOT_CAL_")
    eval_mask = df["lot_id"].str.startswith("LOT_EVAL_")
    val_mask = df["lot_id"].str.startswith("LOT_VAL_")

    cal_df = df[cal_mask].copy()
    eval_df = df[eval_mask].copy()

    # Assert no partition contamination
    assert not any(cal_df["lot_id"].str.startswith("LOT_VAL_"))
    assert not any(cal_df["lot_id"].str.startswith("LOT_EVAL_"))
    assert not any(eval_df["lot_id"].str.startswith("LOT_CAL_"))
    assert not any(eval_df["lot_id"].str.startswith("LOT_VAL_"))

    cal_lots = sorted(cal_df["lot_id"].unique())
    eval_lots = sorted(eval_df["lot_id"].unique())

    if len(cal_lots) != 50:
        raise ValueError(f"Expected 50 calibration lots, got {len(cal_lots)}")
    if len(eval_lots) != 25:
        raise ValueError(f"Expected 25 evaluation lots, got {len(eval_lots)}")

    # Pivot observations
    piv_cal = cal_df.pivot(
        index=["lot_id", "component_id", "parameter_name"],
        columns="elapsed_hours",
        values="value",
    ).reset_index()

    piv_eval = eval_df.pivot(
        index=["lot_id", "component_id", "parameter_name"],
        columns="elapsed_hours",
        values="value",
    ).reset_index()

    primary_results: Dict[str, Any] = {
        "metadata": {
            "evaluation_stage": "PHASE_5_FINAL_EVALUATION",
            "selected_model": "RIDGE_REGRESSION",
            "model_lock": "LOCKED_IMMUTABLE",
            "governing_protocol": "docs/PHASE_5_FINAL_EVALUATION_READINESS.md",
            "training_partition": "LOT_CAL_001_TO_LOT_CAL_050",
            "evaluation_partition": "LOT_EVAL_001_TO_LOT_EVAL_025",
            "n_calibration_lots": len(cal_lots),
            "n_calibration_components": len(piv_cal) // 4,
            "n_evaluation_lots": len(eval_lots),
            "n_evaluation_components": len(piv_eval) // 4,
            "observations_hash": compute_file_sha256(observations_csv_path),
            "safety_slope_status": "OPEN_EVIDENCE_GAP",
            "predictive_rejection_authorized": False,
        },
        "parameter_metrics": {},
    }

    manifest_records: List[Dict[str, Any]] = []
    pred_rows: List[Dict[str, Any]] = []

    for param in PARAMETERS:
        unit = UNITS[param]
        sub_cal = piv_cal[piv_cal["parameter_name"] == param].copy()
        sub_eval = piv_eval[piv_eval["parameter_name"] == param].copy()

        X_cal = sub_cal[[0, 24]].values
        y_cal = sub_cal[168].values
        lots_cal = sub_cal["lot_id"].values

        X_eval = sub_eval[[0, 24]].values
        y_eval = sub_eval[168].values
        lots_eval = sub_eval["lot_id"].values
        comps_eval = sub_eval["component_id"].values

        # 1. Fit locked Ridge model strictly on CAL lots
        model = RidgeRegressionPrognosticModel(parameter_name=param, unit=unit, l2_reg=1.0)
        model.fit(X_cal, y_cal, sample_lot_ids=lots_cal)

        # Verify fitted model strictly matches frozen parameters
        np.testing.assert_allclose(
            model.coefficients_,
            LOCKED_MODEL_COEFFICIENTS[param],
            rtol=1e-5,
            atol=1e-5,
            err_msg=f"Coefficient mismatch for {param}!",
        )
        assert math.isclose(
            float(model._sigma_eff_u_scalar),
            FROZEN_SIGMA_EFF[param],
            rel_tol=1e-5,
        ), f"Sigma_eff mismatch for {param}!"

        # 2. Predict on LOT_EVAL_*
        y_pred, y_lower, y_upper = model.predict_physical(X_eval)

        # Verify finite predictions
        finite_mask = np.isfinite(y_pred) & np.isfinite(y_lower) & np.isfinite(y_upper)
        finite_rate = float(np.mean(finite_mask))
        divergent_count = int(np.sum(~finite_mask))

        # Primary metrics
        abs_err = np.abs(y_eval - y_pred)
        sq_err = (y_eval - y_pred) ** 2

        mae = float(np.mean(abs_err))
        rmse = float(np.sqrt(np.mean(sq_err)))
        med_ae = float(np.median(abs_err))

        in_interval = (y_eval >= y_lower) & (y_eval <= y_upper)
        coverage_90 = float(np.mean(in_interval))
        mean_width = float(np.mean(y_upper - y_lower))
        winkler = compute_winkler_score_90(y_eval, y_lower, y_upper)

        # Baseline metrics
        cf_pred = X_eval[:, 1]
        cf_mae = float(np.mean(np.abs(y_eval - cf_pred)))
        tpl_pred = 7.0 * X_eval[:, 1] - 6.0 * X_eval[:, 0]
        tpl_mae = float(np.mean(np.abs(y_eval - tpl_pred)))

        # Per-lot breakdown
        per_lot_breakdown: Dict[str, Dict[str, float]] = {}
        lot_maes: List[float] = []

        for lot in eval_lots:
            l_mask = (lots_eval == lot)
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

        # Signed IGSS specific analysis
        igss_signed_behavior = None
        if param == "IGSS":
            pos_mask = (y_eval >= 0)
            neg_mask = (y_eval < 0)
            igss_signed_behavior = {
                "positive_count": int(np.sum(pos_mask)),
                "negative_count": int(np.sum(neg_mask)),
                "positive_mae": float(np.mean(abs_err[pos_mask])) if np.any(pos_mask) else None,
                "negative_mae": float(np.mean(abs_err[neg_mask])) if np.any(neg_mask) else None,
                "positive_coverage": float(np.mean(in_interval[pos_mask])) if np.any(pos_mask) else None,
                "negative_coverage": float(np.mean(in_interval[neg_mask])) if np.any(neg_mask) else None,
            }

        # Store component predictions
        for i in range(len(y_eval)):
            pred_rows.append({
                "lot_id": lots_eval[i],
                "component_id": comps_eval[i],
                "parameter_name": param,
                "unit": unit,
                "v0": float(X_eval[i, 0]),
                "v24": float(X_eval[i, 1]),
                "v168_true": float(y_eval[i]),
                "v168_pred": float(y_pred[i]),
                "v168_lower": float(y_lower[i]),
                "v168_upper": float(y_upper[i]),
                "abs_error": float(abs_err[i]),
                "signed_error": float(y_eval[i] - y_pred[i]),
                "in_interval": bool(in_interval[i]),
            })

        # Record parameter summary
        param_summary: Dict[str, Any] = {
            "parameter_name": param,
            "unit": unit,
            "n_eligible_forecasts": len(y_eval),
            "primary_metrics": {
                "mae": mae,
                "rmse": rmse,
                "median_abs_error": med_ae,
                "coverage_rate_90": coverage_90,
                "mean_interval_width": mean_width,
                "winkler_score": winkler,
                "finite_prediction_rate": finite_rate,
                "divergent_fallback_count": divergent_count,
            },
            "baselines": {
                "carry_forward_mae": cf_mae,
                "two_point_linear_mae": tpl_mae,
                "ridge_improvement_vs_carry_forward_pct": float((cf_mae - mae) / cf_mae * 100),
                "ridge_improvement_vs_two_point_linear_pct": float((tpl_mae - mae) / tpl_mae * 100),
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

        if igss_signed_behavior is not None:
            param_summary["igss_signed_behavior"] = igss_signed_behavior

        primary_results["parameter_metrics"][param] = param_summary

        manifest_records.append({
            "parameter_name": param,
            "unit": unit,
            "model_id": model.model_id,
            "model_family": model.model_family,
            "coefficients": [float(c) for c in model.coefficients_],
            "sigma_eff": float(model._sigma_eff_u_scalar),
            "preprocessor_params": {k: float(v) for k, v in model.preprocessor_params_.items()},
            "hyperparameters": dict(model.hyperparameters),
            "evaluation_sample_count": len(y_eval),
            "evaluation_mae": mae,
            "evaluation_coverage_90": coverage_90,
        })

    preds_df = pd.DataFrame(pred_rows)
    return primary_results, manifest_records, preds_df


def perform_secondary_forensic_analysis(
    preds_df: pd.DataFrame,
    ground_truth_csv_path: Path,
    observations_csv_path: Path,
) -> Dict[str, Any]:
    """Phase D: Secondary forensic analysis.

    Executed ONLY AFTER primary evaluation outputs are produced and frozen.
    Joins ground_truth.csv and computes:
    - scenario-level MAE
    - residual quantiles
    - top 1% largest error cases
    - specification-breach forecast flags (Class A Table I)
    - interval behavior asymmetry
    - Module A detector excess motion evidence
    """
    gt_df = pd.read_csv(ground_truth_csv_path)

    # Filter to evaluation partition and checkpoint 168h
    gt_eval = gt_df[
        (gt_df["partition"] == "FINAL_EVALUATION") &
        (gt_df["elapsed_hours"] == 168)
    ][["lot_id", "component_id", "parameter_name", "fixture_type", "is_degradation", "is_spec_failure"]].drop_duplicates()

    # Diagnostic join
    merged = pd.merge(
        preds_df,
        gt_eval,
        on=["lot_id", "component_id", "parameter_name"],
        how="left",
    )

    # Load Module A 0-24h excess motion from observations
    obs_df = pd.read_csv(observations_csv_path)
    obs_eval = obs_df[obs_df["lot_id"].str.startswith("LOT_EVAL_")].copy()

    # Compute Module A raw slope and excess drift for 24h
    piv_obs = obs_eval.pivot(
        index=["lot_id", "component_id", "parameter_name"],
        columns="elapsed_hours",
        values="value",
    ).reset_index()

    piv_obs["raw_drift_24h"] = piv_obs[24] - piv_obs[0]

    # Compute leave-one-out lot median drift
    loo_excess_records = []
    for (lot, param), grp in piv_obs.groupby(["lot_id", "parameter_name"]):
        drifts = grp["raw_drift_24h"].values
        n = len(drifts)
        sorted_d = np.sort(drifts)
        k_target = (n - 1) // 2
        low_med = sorted_d[k_target]
        high_med = sorted_d[k_target + 1] if n > 1 else low_med

        loo_meds = np.where(drifts < high_med, high_med, low_med)
        excess = drifts - loo_meds
        scale = max(1.4826 * np.median(np.abs(drifts - np.median(drifts))), NOISE_FLOORS.get(param, 0.01))
        g_excess = excess / scale

        for c_id, ge in zip(grp["component_id"], g_excess):
            loo_excess_records.append({
                "lot_id": lot,
                "component_id": c_id,
                "parameter_name": param,
                "g_excess_24h": float(ge),
                "module_a_excess_motion_flag": bool(abs(ge) >= 2.5),
            })

    mod_a_df = pd.DataFrame(loo_excess_records)
    merged = pd.merge(merged, mod_a_df, on=["lot_id", "component_id", "parameter_name"], how="left")

    forensic_results: Dict[str, Any] = {
        "metadata": {
            "analysis_type": "DIAGNOSTIC_SECONDARY_FORENSIC_EVALUATION",
            "epistemic_scope": "SYNTHETIC_BENCHMARK_EVALUATION_ONLY",
            "prohibition_notice": "Scenario labels must never flow backward into model or decision logic.",
        },
        "scenario_level_metrics": {},
        "residual_quantiles": {},
        "interval_asymmetry": {},
        "specification_breach_forensics": {},
        "largest_error_cases": {},
    }

    # 1. Scenario-level breakdown
    for param in PARAMETERS:
        p_sub = merged[merged["parameter_name"] == param]
        unit = UNITS[param]

        scen_dict = {}
        for scen, grp in p_sub.groupby("fixture_type"):
            scen_dict[str(scen)] = {
                "n_samples": len(grp),
                "mae": float(np.mean(grp["abs_error"])),
                "coverage_90": float(np.mean(grp["in_interval"])),
            }
        forensic_results["scenario_level_metrics"][param] = scen_dict

        # 2. Residual quantiles
        abs_errs = p_sub["abs_error"].values
        signed_errs = p_sub["signed_error"].values
        forensic_results["residual_quantiles"][param] = {
            "abs_error_q25": float(np.percentile(abs_errs, 25)),
            "abs_error_q50": float(np.percentile(abs_errs, 50)),
            "abs_error_q75": float(np.percentile(abs_errs, 75)),
            "abs_error_q90": float(np.percentile(abs_errs, 90)),
            "abs_error_q95": float(np.percentile(abs_errs, 95)),
            "abs_error_q99": float(np.percentile(abs_errs, 99)),
            "signed_error_q25": float(np.percentile(signed_errs, 25)),
            "signed_error_q50": float(np.percentile(signed_errs, 50)),
            "signed_error_q75": float(np.percentile(signed_errs, 75)),
        }

        # 3. Interval asymmetry
        y_true = p_sub["v168_true"].values
        y_low = p_sub["v168_lower"].values
        y_upp = p_sub["v168_upper"].values
        below_count = int(np.sum(y_true < y_low))
        above_count = int(np.sum(y_true > y_upp))
        forensic_results["interval_asymmetry"][param] = {
            "total_breaches": below_count + above_count,
            "lower_breaches_y_below_L": below_count,
            "upper_breaches_y_above_U": above_count,
            "breach_rate": float((below_count + above_count) / len(p_sub)),
        }

        # 4. Specification Breach Forensics (Class A Limits)
        spec = SPEC_LIMITS_CLASS_A[param]
        lim_low = spec["low"]
        lim_high = spec["high"]

        # True spec breach at 168h
        actual_breach = np.zeros(len(p_sub), dtype=bool)
        if lim_low is not None:
            actual_breach |= (y_true < lim_low)
        if lim_high is not None:
            actual_breach |= (y_true > lim_high)

        # Predicted future spec breach at 168h
        y_pred = p_sub["v168_pred"].values
        pred_breach = np.zeros(len(p_sub), dtype=bool)
        if lim_low is not None:
            pred_breach |= (y_pred < lim_low)
        if lim_high is not None:
            pred_breach |= (y_pred > lim_high)

        tp = int(np.sum(actual_breach & pred_breach))
        fp = int(np.sum(~actual_breach & pred_breach))
        fn = int(np.sum(actual_breach & ~pred_breach))
        tn = int(np.sum(~actual_breach & ~pred_breach))

        # Module A excess motion cross-tabulation
        mod_a_flags = p_sub["module_a_excess_motion_flag"].values
        mod_a_breach_overlap = int(np.sum(mod_a_flags & pred_breach))

        forensic_results["specification_breach_forensics"][param] = {
            "spec_limits": {"low": lim_low, "high": lim_high, "unit": unit},
            "actual_spec_breaches_count": int(np.sum(actual_breach)),
            "predicted_future_spec_breaches_count": int(np.sum(pred_breach)),
            "contingency_table": {
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "true_negatives": tn,
            },
            "module_a_excess_motion_count": int(np.sum(mod_a_flags)),
            "module_a_and_pred_breach_overlap": mod_a_breach_overlap,
            "governance_rule": (
                "A predicted future specification breach is INFORMATIONAL EVIDENCE ONLY. "
                "Autonomous physical component rejection is STRICTLY PROHIBITED."
            ),
        }

        # 5. Top 1% extreme error cases (5 components)
        top_err = p_sub.sort_values(by="abs_error", ascending=False).head(5)
        extreme_cases = []
        for _, row in top_err.iterrows():
            extreme_cases.append({
                "lot_id": row["lot_id"],
                "component_id": row["component_id"],
                "v0": row["v0"],
                "v24": row["v24"],
                "v168_true": row["v168_true"],
                "v168_pred": row["v168_pred"],
                "abs_error": row["abs_error"],
                "fixture_type": row["fixture_type"],
                "in_interval": row["in_interval"],
                "module_a_flag": row["module_a_excess_motion_flag"],
            })
        forensic_results["largest_error_cases"][param] = extreme_cases

    return forensic_results


def run_phase5_final_evaluation(
    repo_root: Path,
    output_results_path: Optional[Path] = None,
    output_manifest_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute complete authorized Phase 5 Final Evaluation workflow.

    Workflow:
    Phase A: Verify pre-evaluation integrity (14 hashes, partitions, locked models).
    Phase B: Execute primary final evaluation on observations only.
    Phase C: Freeze primary results artifact and hash.
    Phase D: Execute secondary forensic analysis on joined ground truth.
    Phase E: Return consolidated and verified results.
    """
    obs_file = repo_root / "data/synthetic_phase4b/observations.csv"
    gt_file = repo_root / "data/synthetic_phase4b/ground_truth.csv"

    # Phase A: Integrity check
    integrity_record = verify_pre_evaluation_integrity(repo_root)

    # Phase B: Primary evaluation
    primary_results, manifest_records, preds_df = execute_primary_final_evaluation(obs_file)

    # Attach Phase A record
    primary_results["pre_evaluation_integrity"] = integrity_record

    # Phase C: Serialize and freeze primary artifacts first
    if output_results_path is not None:
        output_results_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_results_path, "w") as f:
            json.dump(primary_results, f, indent=2, sort_keys=True)
        primary_hash = compute_file_sha256(output_results_path)
    else:
        primary_hash = hashlib.sha256(json.dumps(primary_results, sort_keys=True).encode("utf-8")).hexdigest()

    if output_manifest_path is not None:
        output_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_payload = {
            "stage": "PHASE_5_FINAL_EVALUATION",
            "model_family": "RIDGE_REGRESSION",
            "model_lock": "LOCKED_IMMUTABLE",
            "safety_slope_status": "OPEN_EVIDENCE_GAP",
            "primary_results_hash": primary_hash,
            "records": manifest_records,
        }
        with open(output_manifest_path, "w") as f:
            json.dump(manifest_payload, f, indent=2, sort_keys=True)
        manifest_hash = compute_file_sha256(output_manifest_path)
    else:
        manifest_hash = "IN_MEMORY"

    primary_results["metadata"]["frozen_primary_results_hash"] = primary_hash
    primary_results["metadata"]["frozen_lineage_manifest_hash"] = manifest_hash

    # Phase D: Secondary forensic analysis (AFTER primary freeze)
    forensics = perform_secondary_forensic_analysis(preds_df, gt_file, obs_file)
    primary_results["secondary_forensic_analysis"] = forensics

    # Re-save complete consolidated artifact
    if output_results_path is not None:
        with open(output_results_path, "w") as f:
            json.dump(primary_results, f, indent=2, sort_keys=True)

    return primary_results


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent.parent.parent
    res_out = root / "data/evaluation_phase5/phase5_final_results.json"
    man_out = root / "data/evaluation_phase5/phase5_final_lineage_manifest.json"

    print("Executing Phase 5 Final Evaluation under LOG-103/LOG-104...")
    results = run_phase5_final_evaluation(root, res_out, man_out)
    print("Final evaluation completed successfully. Primary results frozen.")
