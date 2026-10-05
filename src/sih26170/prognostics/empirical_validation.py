"""Empirical validation, target formulation comparison, and conformal calibration.

Consolidates rigorous statistical validation protocols for Module B prognostics:
1. Relative drift target (delta_u) vs direct level modeling comparison.
2. Regularization parameter (lambda) stability validation via lot-grouped nested CV.
3. Regime-conditional conformal prediction calibration for valid coverage under non-stationary drift.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from sih26170.screening.transforms import inverse_transform_parameter, transform_parameter

PRIMARY_PARAMETERS = ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]
DEFAULT_LAMBDAS: List[float] = [float(x) for x in np.logspace(-3, 3, 50)]


def evaluate_relative_vs_direct_drift(
    obs_df: pd.DataFrame,
    cal_lot_ids: List[str],
    eval_lot_ids: List[str],
    lam: float = 1.0,
) -> Dict[str, Any]:
    """Compares relative drift target (delta_u) vs direct level modeling.

    Formulations:
        Direct:   u_hat_168 = beta_0 + beta_1 * u_0 + beta_2 * u_24
        Relative: delta_u = u_168 - u_24; u_hat_168 = u_24 + delta_u_hat
    """
    cal_df = obs_df[obs_df["lot_id"].isin(set(cal_lot_ids))]
    eval_df = obs_df[obs_df["lot_id"].isin(set(eval_lot_ids))]

    parameter_results: Dict[str, Any] = {}

    for param in PRIMARY_PARAMETERS:
        p_cal = cal_df[cal_df["parameter_name"] == param].pivot(
            index="component_id", columns="elapsed_hours", values="value"
        ).dropna()
        p_eval = eval_df[eval_df["parameter_name"] == param].pivot(
            index="component_id", columns="elapsed_hours", values="value"
        ).dropna()

        # Transform inputs and targets
        u0_cal = np.array([transform_parameter(param, v) for v in p_cal[0]])
        u24_cal = np.array([transform_parameter(param, v) for v in p_cal[24]])
        u168_cal = np.array([transform_parameter(param, v) for v in p_cal[168]])

        u0_eval = np.array([transform_parameter(param, v) for v in p_eval[0]])
        u24_eval = np.array([transform_parameter(param, v) for v in p_eval[24]])
        u168_eval = np.array([transform_parameter(param, v) for v in p_eval[168]])
        y168_eval_true = p_eval[168].values

        X_cal = np.column_stack([np.ones_like(u0_cal), u0_cal, u24_cal])
        X_eval = np.column_stack([np.ones_like(u0_eval), u0_eval, u24_eval])

        # Model 1: Direct terminal prediction
        beta_dir = np.linalg.solve(X_cal.T @ X_cal + lam * np.eye(3), X_cal.T @ u168_cal)
        u_pred_dir = X_eval @ beta_dir
        y_pred_dir = np.array([inverse_transform_parameter(param, u) for u in u_pred_dir])

        mae_dir = float(np.mean(np.abs(y_pred_dir - y168_eval_true)))
        rmse_dir = float(np.sqrt(np.mean((y_pred_dir - y168_eval_true) ** 2)))
        medae_dir = float(np.median(np.abs(y_pred_dir - y168_eval_true)))

        # Model 2: Relative drift prediction (delta_u = u168 - u24)
        delta_u_cal = u168_cal - u24_cal
        beta_delta = np.linalg.solve(X_cal.T @ X_cal + lam * np.eye(3), X_cal.T @ delta_u_cal)
        delta_u_pred = X_eval @ beta_delta
        u_pred_delta = u24_eval + delta_u_pred
        y_pred_delta = np.array([inverse_transform_parameter(param, u) for u in u_pred_delta])

        mae_delta = float(np.mean(np.abs(y_pred_delta - y168_eval_true)))
        rmse_delta = float(np.sqrt(np.mean((y_pred_delta - y168_eval_true) ** 2)))
        medae_delta = float(np.median(np.abs(y_pred_delta - y168_eval_true)))

        rel_diff_pct = float((mae_delta - mae_dir) / max(1e-9, mae_dir) * 100.0)

        # Physical category rationale
        is_leakage = param in ("IDSS", "IGSS")
        parameter_results[param] = {
            "parameter": param,
            "unit": "uA" if param == "IDSS" else ("V" if param == "VGS(th)" else ("mOhm" if param == "RDS(on)" else "nA")),
            "domain_category": "surface_leakage" if is_leakage else "bulk_conduction",
            "direct_mae": mae_dir,
            "direct_rmse": rmse_dir,
            "direct_medae": medae_dir,
            "relative_mae": mae_delta,
            "relative_rmse": rmse_delta,
            "relative_medae": medae_delta,
            "mae_delta_pct": rel_diff_pct,
            "optimal_target": "relative_delta" if rel_diff_pct <= 0 else "direct_level",
            "physics_rationale": (
                "Wide dynamic-range leakage: delta isolates oxide/p-n degradation from lot baseline offset"
                if is_leakage
                else "Tight-tolerance bulk parameter: direct 2-point estimator regularizes measurement noise"
            ),
        }

    return {
        "metric_id": "2.1",
        "description": "Relative drift target (delta_u) vs direct level modeling comparison",
        "calibration_lots_count": len(cal_lot_ids),
        "evaluation_lots_count": len(eval_lot_ids),
        "parameter_results": parameter_results,
    }


def evaluate_nested_cv_lambda_sweep(
    obs_df: pd.DataFrame,
    cal_lot_ids: List[str],
    lambdas: Optional[List[float]] = None,
    n_folds: int = 5,
) -> Dict[str, Any]:
    """Re-validates regularization strength lambda via lot-grouped nested CV.

    Confirms lambda = 1.0 is in the optimal valley of the regularization curve.
    """
    if lambdas is None:
        lambdas = DEFAULT_LAMBDAS

    cal_df = obs_df[obs_df["lot_id"].isin(set(cal_lot_ids))].copy()
    unique_lots = sorted(cal_df["lot_id"].unique())
    actual_folds = max(2, min(n_folds, len(unique_lots))) if len(unique_lots) >= 2 else 1
    lot_folds = {lot: i % actual_folds for i, lot in enumerate(unique_lots)}
    cal_df["fold"] = cal_df["lot_id"].map(lot_folds)

    sweep_results: Dict[str, Any] = {}

    for param in PRIMARY_PARAMETERS:
        p_df = cal_df[cal_df["parameter_name"] == param]
        piv = p_df.pivot(index=["component_id", "lot_id", "fold"], columns="elapsed_hours", values="value").reset_index().dropna()

        u0 = np.array([transform_parameter(param, v) for v in piv[0]])
        u24 = np.array([transform_parameter(param, v) for v in piv[24]])
        u168 = np.array([transform_parameter(param, v) for v in piv[168]])
        y168_true = piv[168].values
        folds = np.asarray(piv["fold"].values)

        cv_curve: List[Dict[str, float]] = []
        for lam in lambdas:
            fold_maes = []
            for f in range(actual_folds):
                train_mask = (folds != f)
                val_mask = (folds == f)
                n_train = int(np.sum(train_mask))
                n_val = int(np.sum(val_mask))
                if n_val == 0 or n_train == 0:
                    continue

                X_tr = np.column_stack([np.ones(n_train), u0[train_mask], u24[train_mask]])
                X_va = np.column_stack([np.ones(n_val), u0[val_mask], u24[val_mask]])

                beta = np.linalg.solve(X_tr.T @ X_tr + lam * np.eye(3), X_tr.T @ u168[train_mask])
                u_pred = X_va @ beta
                y_pred = np.array([inverse_transform_parameter(param, u) for u in u_pred])
                fold_maes.append(float(np.mean(np.abs(y_pred - y168_true[val_mask]))))

            mean_cv_mae = float(np.mean(fold_maes)) if fold_maes else 0.0
            cv_curve.append({"lambda": float(lam), "cv_mae": mean_cv_mae})

        maes = [pt["cv_mae"] for pt in cv_curve]
        best_idx = int(np.argmin(maes))
        best_lambda = float(cv_curve[best_idx]["lambda"])
        best_mae = float(maes[best_idx])

        # Explicitly evaluate locked production baseline lambda = 1.0
        fold_maes_1 = []
        for f in range(actual_folds):
            train_mask = (folds != f)
            val_mask = (folds == f)
            n_train = int(np.sum(train_mask))
            n_val = int(np.sum(val_mask))
            if n_val == 0 or n_train == 0:
                continue
            X_tr = np.column_stack([np.ones(n_train), u0[train_mask], u24[train_mask]])
            X_va = np.column_stack([np.ones(n_val), u0[val_mask], u24[val_mask]])
            beta = np.linalg.solve(X_tr.T @ X_tr + 1.0 * np.eye(3), X_tr.T @ u168[train_mask])
            u_pred = X_va @ beta
            y_pred = np.array([inverse_transform_parameter(param, u) for u in u_pred])
            fold_maes_1.append(float(np.mean(np.abs(y_pred - y168_true[val_mask]))))
        mae_at_1 = float(np.mean(fold_maes_1)) if fold_maes_1 else best_mae
        delta_pct_from_opt = float((mae_at_1 - best_mae) / max(1e-9, best_mae) * 100.0)

        sweep_results[param] = {
            "parameter": param,
            "optimal_lambda": best_lambda,
            "optimal_cv_mae": best_mae,
            "locked_lambda": 1.0,
            "locked_lambda_cv_mae": mae_at_1,
            "gap_to_optimum_pct": delta_pct_from_opt,
            "within_half_percent_valley": delta_pct_from_opt <= 0.50,
            "cv_curve": cv_curve,
        }

    return {
        "metric_id": "2.2",
        "description": "Regularization strength lambda sweep via lot-grouped nested CV",
        "folds": n_folds,
        "lots_evaluated": len(unique_lots),
        "parameter_sweeps": sweep_results,
    }


def evaluate_regime_conditional_conformal(
    obs_df: pd.DataFrame,
    cal_lot_ids: List[str],
    eval_lot_ids: List[str],
    target_coverage: float = 0.90,
) -> Dict[str, Any]:
    """Evaluates regime-conditional conformal calibration.

    Stratifies calibration residuals by early drift (|u_24 - u_0|), improving
    coverage on high-drift components without widening nominal intervals unnecessarily.
    """
    cal_df = obs_df[obs_df["lot_id"].isin(set(cal_lot_ids))]
    eval_df = obs_df[obs_df["lot_id"].isin(set(eval_lot_ids))]

    results: Dict[str, Any] = {}

    for param in PRIMARY_PARAMETERS:
        p_cal = cal_df[cal_df["parameter_name"] == param].pivot(
            index="component_id", columns="elapsed_hours", values="value"
        ).dropna()
        p_eval = eval_df[eval_df["parameter_name"] == param].pivot(
            index="component_id", columns="elapsed_hours", values="value"
        ).dropna()

        u0_cal = np.array([transform_parameter(param, v) for v in p_cal[0]])
        u24_cal = np.array([transform_parameter(param, v) for v in p_cal[24]])
        u168_cal = np.array([transform_parameter(param, v) for v in p_cal[168]])

        u0_eval = np.array([transform_parameter(param, v) for v in p_eval[0]])
        u24_eval = np.array([transform_parameter(param, v) for v in p_eval[24]])
        u168_eval = np.array([transform_parameter(param, v) for v in p_eval[168]])

        X_cal = np.column_stack([np.ones_like(u0_cal), u0_cal, u24_cal])
        X_eval = np.column_stack([np.ones_like(u0_eval), u0_eval, u24_eval])

        beta = np.linalg.solve(X_cal.T @ X_cal + 1.0 * np.eye(3), X_cal.T @ u168_cal)
        res_cal = np.abs(u168_cal - X_cal @ beta)

        # Global conformal nonconformity score quantile
        q_global = float(np.quantile(res_cal, target_coverage))

        # Regime-stratified nonconformity score quantiles
        d24_cal = np.abs(u24_cal - u0_cal)
        d24_eval = np.abs(u24_eval - u0_eval)
        tau = float(np.median(d24_cal))

        nom_mask_cal = d24_cal <= tau
        drift_mask_cal = d24_cal > tau

        q_nom = float(np.quantile(res_cal[nom_mask_cal], target_coverage))
        q_drift = float(np.quantile(res_cal[drift_mask_cal], target_coverage))

        # Evaluation coverage
        u_pred_eval = X_eval @ beta
        res_eval = np.abs(u168_eval - u_pred_eval)

        drift_mask_eval = d24_eval > tau

        # Uniform global coverage
        cov_global_overall = float(np.mean(res_eval <= q_global)) if len(res_eval) > 0 else 1.0
        cov_global_drift = float(np.mean(res_eval[drift_mask_eval] <= q_global)) if np.sum(drift_mask_eval) > 0 else 1.0

        # Regime-conditional coverage
        q_conditional_eval = np.where(d24_eval <= tau, q_nom, q_drift)
        cov_cond_overall = float(np.mean(res_eval <= q_conditional_eval)) if len(res_eval) > 0 else 1.0
        cov_cond_drift = float(np.mean(res_eval[drift_mask_eval] <= q_drift)) if np.sum(drift_mask_eval) > 0 else 1.0

        results[param] = {
            "parameter": param,
            "target_coverage": target_coverage,
            "drift_split_threshold_tau": tau,
            "q_global": q_global,
            "q_regime_nominal": q_nom,
            "q_regime_drift": q_drift,
            "uniform_coverage_overall": cov_global_overall,
            "uniform_coverage_high_drift": cov_global_drift,
            "regime_conditional_coverage_overall": cov_cond_overall,
            "regime_conditional_coverage_high_drift": cov_cond_drift,
            "high_drift_coverage_gain_pct": float((cov_cond_drift - cov_global_drift) * 100.0),
        }

    return {
        "metric_id": "2.3",
        "description": "Regime-conditional conformal calibration analysis",
        "parameter_results": results,
    }
