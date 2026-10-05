"""Leave-One-Out (LOO) Lot-Context Feature Extraction and Prognostic Models.

Implements STEP 3 requirements for SIH 2026 Problem Statement SIH26170:
- Strictly as-of observations with elapsed_hours <= 24h
- Strict Leave-One-Out (LOO) exclusion: component i is NEVER included in its own lot statistics
- Exact linear contribution decomposition (SHAP / additivity down to machine precision)
- Zero lookahead, zero future equipment state, zero ground-truth access
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd

from sih26170.screening.transforms import (
    get_noise_floor,
    inverse_transform_parameter,
    transform_parameter,
)

# Canonical parameter-specific coordinate representations:
# IDSS: positive log u = ln(y)
# RDS(on): positive log u = ln(y)
# VGS(th): linear representation u = y
# IGSS: signed asinh u = asinh(y / 1.0 nA)

FEATURE_VARIANTS: Dict[str, List[str]] = {
    "Variant A (u0, u24)": ["u0", "u24"],
    "Variant B (+lot_med_0h)": ["u0", "u24", "loo_lot_median_0h"],
    "Variant C (+lot_med_0h, 24h)": ["u0", "u24", "loo_lot_median_0h", "loo_lot_median_24h"],
    "Variant D (+lot_drift)": ["u0", "u24", "lot_drift"],
    "Variant E (+excess_drift)": ["u0", "u24", "excess_drift"],
    "Variant F (+lot_drift, +excess_drift)": ["u0", "u24", "lot_drift", "excess_drift"],
    "Variant G (+context, +scale)": ["u0", "u24", "lot_drift", "excess_drift", "loo_lot_scale_0h"],
}


@dataclass(frozen=True)
class LooLotContextFeatures:
    """Feature contract for Leave-One-Out lot-context prognostics."""
    component_id: str
    lot_id: str
    parameter_name: str
    v0: float
    v24: float
    u0: float
    u24: float
    component_drift: float
    loo_lot_median_0h: float
    loo_lot_median_24h: float
    lot_drift: float
    excess_drift: float
    loo_lot_scale_0h: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "lot_id": self.lot_id,
            "parameter_name": self.parameter_name,
            "v0": self.v0,
            "v24": self.v24,
            "u0": self.u0,
            "u24": self.u24,
            "component_drift": self.component_drift,
            "loo_lot_median_0h": self.loo_lot_median_0h,
            "loo_lot_median_24h": self.loo_lot_median_24h,
            "lot_drift": self.lot_drift,
            "excess_drift": self.excess_drift,
            "loo_lot_scale_0h": self.loo_lot_scale_0h,
        }


def extract_loo_lot_context_features(obs_df: pd.DataFrame) -> pd.DataFrame:
    """Extract strictly as-of <= 24h features with strict Leave-One-Out lot context.

    Enforces Phase 3 requirement:
    Target component i MUST be strictly excluded from its own lot statistics:
        lot_statistics = statistics(all components in L except i)

    Args:
        obs_df: DataFrame containing burn-in observations.

    Returns:
        DataFrame with LOO lot context features for all eligible components.
    """
    obs_24 = obs_df[obs_df["elapsed_hours"] <= 24].copy()

    # Extract 0h and 24h readings
    p0 = (
        obs_24[obs_24["elapsed_hours"] == 0]
        .groupby(["component_id", "lot_id", "parameter_name"])["value"]
        .last()
        .reset_index()
        .rename(columns={"value": "v0"})
    )
    p24 = (
        obs_24[obs_24["elapsed_hours"] == 24]
        .groupby(["component_id", "lot_id", "parameter_name"])["value"]
        .last()
        .reset_index()
        .rename(columns={"value": "v24"})
    )

    merged = pd.merge(p0, p24, on=["component_id", "lot_id", "parameter_name"], how="inner")

    records = []
    for _, row in merged.iterrows():
        param = str(row["parameter_name"])
        v0 = float(row["v0"])
        v24 = float(row["v24"])
        try:
            u0 = transform_parameter(param, v0)
            u24 = transform_parameter(param, v24)
            records.append({
                "component_id": str(row["component_id"]),
                "lot_id": str(row["lot_id"]),
                "parameter_name": param,
                "v0": v0,
                "v24": v24,
                "u0": u0,
                "u24": u24,
            })
        except Exception:
            continue

    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame()

    loo_records = []
    grouped = df.groupby(["lot_id", "parameter_name"])

    for (lot_id, param), group in grouped:
        comp_ids = group["component_id"].values
        v0_arr = group["v0"].values
        v24_arr = group["v24"].values
        u0_arr = group["u0"].values
        u24_arr = group["u24"].values
        n_comps = len(comp_ids)
        floor = get_noise_floor(param)

        for idx in range(n_comps):
            cid = comp_ids[idx]
            v0_i = v0_arr[idx]
            v24_i = v24_arr[idx]
            u0_i = u0_arr[idx]
            u24_i = u24_arr[idx]

            # LOO peers: strictly exclude idx
            peer_mask = np.ones(n_comps, dtype=bool)
            peer_mask[idx] = False

            if np.sum(peer_mask) >= 1:
                peer_u0 = u0_arr[peer_mask]
                peer_u24 = u24_arr[peer_mask]

                loo_med_0h = float(np.median(peer_u0))
                loo_med_24h = float(np.median(peer_u24))
                lot_drift = loo_med_24h - loo_med_0h
                comp_drift = u24_i - u0_i
                excess_drift = comp_drift - lot_drift
                peer_mad_0h = float(np.median(np.abs(peer_u0 - loo_med_0h)))
                loo_scale_0h = float(max(1.4826 * peer_mad_0h, floor))
            else:
                # Ultra-small lot fallback
                loo_med_0h = u0_i
                loo_med_24h = u24_i
                lot_drift = 0.0
                comp_drift = u24_i - u0_i
                excess_drift = comp_drift
                loo_scale_0h = floor

            loo_records.append(
                LooLotContextFeatures(
                    component_id=cid,
                    lot_id=str(lot_id),
                    parameter_name=str(param),
                    v0=v0_i,
                    v24=v24_i,
                    u0=u0_i,
                    u24=u24_i,
                    component_drift=comp_drift,
                    loo_lot_median_0h=loo_med_0h,
                    loo_lot_median_24h=loo_med_24h,
                    lot_drift=lot_drift,
                    excess_drift=excess_drift,
                    loo_lot_scale_0h=loo_scale_0h,
                ).to_dict()
            )

    return pd.DataFrame(loo_records)


class LotContextRidgeModel:
    """Ridge Regression model with arbitrary feature vector and exact linear explainability."""

    def __init__(
        self,
        parameter_name: str,
        feature_columns: Sequence[str],
        l2_reg: float = 1.0,
    ) -> None:
        self.parameter_name = parameter_name
        self.feature_columns = list(feature_columns)
        self.l2_reg = float(l2_reg)
        self.coefficients_: Optional[np.ndarray] = None  # [intercept, beta_1, ..., beta_D]
        self.is_fitted: bool = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> LotContextRidgeModel:
        """Solve Ridge normal equations: (X_aug^T X_aug + Gamma)^(-1) X_aug^T y."""
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        N, D = X.shape

        X_aug = np.column_stack([np.ones(N), X])
        Gamma = np.diag([0.0] + [self.l2_reg] * D)

        XtX = X_aug.T @ X_aug
        Xty = X_aug.T @ y
        self.coefficients_ = np.linalg.solve(XtX + Gamma, Xty)
        self.is_fitted = True
        return self

    def predict_transformed(self, X: np.ndarray) -> np.ndarray:
        """Predict in transformed representation space."""
        if not self.is_fitted or self.coefficients_ is None:
            raise RuntimeError("Model must be fitted before predict_transformed.")
        X = np.asarray(X, dtype=np.float64)
        X_aug = np.column_stack([np.ones(len(X)), X])
        return X_aug @ self.coefficients_

    def predict(
        self,
        X: np.ndarray,
        v24_values: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Predict terminal physical values with numerical divergence protection.

        Returns:
            Tuple of (pred_physical, pred_transformed, is_divergent_mask)
        """
        raw_u = self.predict_transformed(X)
        N = len(raw_u)
        pred_phys = []
        is_divergent = []

        for i in range(N):
            u_val = raw_u[i]
            v24 = v24_values[i]
            if not np.isfinite(u_val) or abs(u_val) > 10.0:
                pred_phys.append(float(v24))
                is_divergent.append(True)
            else:
                try:
                    phys = inverse_transform_parameter(self.parameter_name, u_val)
                    if not np.isfinite(phys):
                        pred_phys.append(float(v24))
                        is_divergent.append(True)
                    else:
                        pred_phys.append(float(phys))
                        is_divergent.append(False)
                except Exception:
                    pred_phys.append(float(v24))
                    is_divergent.append(True)

        return (
            np.array(pred_phys, dtype=np.float64),
            raw_u,
            np.array(is_divergent, dtype=bool),
        )

    def explain(self, x: np.ndarray) -> Dict[str, Any]:
        """Compute exact linear contribution decomposition (SHAP additivity).

        Guaranteed: sum(feature_contributions) + intercept == transformed_prediction
        within IEEE-754 precision.

        Returns:
            Dictionary with feature contributions, intercept, and grouped contributions.
        """
        if not self.is_fitted or self.coefficients_ is None:
            raise RuntimeError("Model must be fitted before explain.")
        x = np.asarray(x, dtype=np.float64)
        intercept = float(self.coefficients_[0])
        slopes = self.coefficients_[1:]

        contributions: Dict[str, float] = {}
        for col, slope, val in zip(self.feature_columns, slopes, x):
            contributions[col] = float(slope * val)

        transformed_pred = intercept + float(np.dot(slopes, x))

        # Grouped contributions
        baseline_contrib = contributions.get("u0", 0.0)
        curr_24h_contrib = contributions.get("u24", 0.0)
        lot_context_contrib = (
            contributions.get("loo_lot_median_0h", 0.0)
            + contributions.get("loo_lot_median_24h", 0.0)
            + contributions.get("lot_drift", 0.0)
            + contributions.get("loo_lot_scale_0h", 0.0)
        )
        excess_drift_contrib = contributions.get("excess_drift", 0.0)

        return {
            "intercept": intercept,
            "feature_contributions": contributions,
            "sum_contributions": float(sum(contributions.values()) + intercept),
            "transformed_prediction": transformed_pred,
            "additivity_delta": float(abs(sum(contributions.values()) + intercept - transformed_pred)),
            "baseline_contribution": baseline_contrib,
            "current_24h_contribution": curr_24h_contrib,
            "lot_context_contribution": lot_context_contrib,
            "excess_drift_contribution": excess_drift_contrib,
        }


RESIDUAL_VARIANTS: Dict[str, Tuple[List[str], str]] = {
    "Variant A (Current Ridge [u0, u24])": (["u0", "u24"], "u_168"),
    "Variant B (Residual [u0, u24])": (["u0", "u24"], "delta_u"),
    "Variant C (Residual [u0, u24, lot_drift])": (["u0", "u24", "lot_drift"], "delta_u"),
    "Variant D (Residual [u0, u24, excess_drift])": (["u0", "u24", "excess_drift"], "delta_u"),
    "Variant E (Residual [u0, u24, lot_drift, excess_drift])": (["u0", "u24", "lot_drift", "excess_drift"], "delta_u"),
    "Variant F (Residual [u24, early_drift, lot_drift, excess_drift])": (["u24", "component_drift", "lot_drift", "excess_drift"], "delta_u"),
}


class ResidualRidgeModel:
    """Predicts delta_u = u_168 - u_24 and reconstructs u_168_hat = u_24 + delta_u_hat.

    Implements Step 4 requirements for SIH 2026 Problem Statement SIH26170:
    - Target: delta_u = u_168 - u_24
    - Reconstructed forecast: u_168_hat = u_24 + delta_u_hat
    - Exact linear explainability:
        u_24 + intercept + sum(feature_contributions) == u_168_hat
    """

    def __init__(
        self,
        parameter_name: str,
        feature_columns: Sequence[str],
        l2_reg: float = 1.0,
    ) -> None:
        self.parameter_name = parameter_name
        self.feature_columns = list(feature_columns)
        self.l2_reg = float(l2_reg)
        self.coefficients_: Optional[np.ndarray] = None  # [intercept, beta_1, ..., beta_D]
        self.is_fitted: bool = False

    def fit(self, X: np.ndarray, y_delta: np.ndarray) -> ResidualRidgeModel:
        """Solve Ridge normal equations for target delta_u."""
        X = np.asarray(X, dtype=np.float64)
        y_delta = np.asarray(y_delta, dtype=np.float64)
        N, D = X.shape

        X_aug = np.column_stack([np.ones(N), X])
        Gamma = np.diag([0.0] + [self.l2_reg] * D)

        XtX = X_aug.T @ X_aug
        Xty = X_aug.T @ y_delta
        self.coefficients_ = np.linalg.solve(XtX + Gamma, Xty)
        self.is_fitted = True
        return self

    def predict_delta(self, X: np.ndarray) -> np.ndarray:
        """Predict forward delta in transformed representation space."""
        if not self.is_fitted or self.coefficients_ is None:
            raise RuntimeError("Model must be fitted before predict_delta.")
        X = np.asarray(X, dtype=np.float64)
        X_aug = np.column_stack([np.ones(len(X)), X])
        return X_aug @ self.coefficients_

    def predict(
        self,
        X: np.ndarray,
        u24_values: np.ndarray,
        v24_values: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Predict terminal physical values via residual reconstruction.

        Reconstruction: u_168_hat = u_24 + delta_u_hat
        Divergence guard: if |u_168_hat| > 10.0 or non-finite, fall back to v24.

        Returns:
            Tuple of (pred_physical, pred_u168, pred_delta, is_divergent_mask)
        """
        pred_delta = self.predict_delta(X)
        u24_arr = np.asarray(u24_values, dtype=np.float64)
        v24_arr = np.asarray(v24_values, dtype=np.float64)
        pred_u168 = u24_arr + pred_delta
        N = len(pred_u168)

        pred_phys = []
        is_divergent = []

        for i in range(N):
            u_val = pred_u168[i]
            v24 = v24_arr[i]
            if not np.isfinite(u_val) or abs(u_val) > 10.0:
                pred_phys.append(float(v24))
                is_divergent.append(True)
            else:
                try:
                    phys = inverse_transform_parameter(self.parameter_name, u_val)
                    if not np.isfinite(phys):
                        pred_phys.append(float(v24))
                        is_divergent.append(True)
                    else:
                        pred_phys.append(float(phys))
                        is_divergent.append(False)
                except Exception:
                    pred_phys.append(float(v24))
                    is_divergent.append(True)

        return (
            np.array(pred_phys, dtype=np.float64),
            pred_u168,
            pred_delta,
            np.array(is_divergent, dtype=bool),
        )

    def explain(self, x: np.ndarray, u24: float) -> Dict[str, Any]:
        """Compute exact linear contribution decomposition for residual model.

        Guaranteed:
            delta_hat == intercept + sum(feature_contributions)
            u_168_hat == u_24 + delta_hat
        within IEEE-754 precision.

        Returns:
            Dictionary with feature contributions, intercept, u24 baseline, and reconstructed prediction.
        """
        if not self.is_fitted or self.coefficients_ is None:
            raise RuntimeError("Model must be fitted before explain.")
        x = np.asarray(x, dtype=np.float64)
        u24_val = float(u24)
        intercept = float(self.coefficients_[0])
        slopes = self.coefficients_[1:]

        contributions: Dict[str, float] = {}
        for col, slope, val in zip(self.feature_columns, slopes, x):
            contributions[col] = float(slope * val)

        pred_delta = intercept + float(np.dot(slopes, x))
        reconstructed_u168 = u24_val + pred_delta

        sum_contribs = float(intercept + sum(contributions.values()))
        delta_additivity_error = float(abs(sum_contribs - pred_delta))
        reconstructed_additivity_error = float(abs(u24_val + sum_contribs - reconstructed_u168))

        return {
            "u24_baseline": u24_val,
            "intercept": intercept,
            "feature_contributions": contributions,
            "predicted_forward_delta": pred_delta,
            "reconstructed_u168": reconstructed_u168,
            "delta_additivity_error": delta_additivity_error,
            "reconstructed_additivity_error": reconstructed_additivity_error,
            "lot_drift_contribution": contributions.get("lot_drift", 0.0),
            "excess_drift_contribution": contributions.get("excess_drift", 0.0),
            "component_drift_contribution": contributions.get("component_drift", 0.0),
        }


def compute_training_excess_drift_scales(train_feat_df: pd.DataFrame) -> Dict[str, float]:
    """Compute training-only robust scales for excess_drift per parameter:
    scale = max(1.4826 * MAD_train(excess_drift), noise_floor)
    """
    scales: Dict[str, float] = {}
    for param in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]:
        sub = train_feat_df[train_feat_df["parameter_name"] == param]
        if sub.empty:
            scales[param] = get_noise_floor(param)
            continue
        ed = sub["excess_drift"].values
        med = float(np.median(ed))
        mad = float(np.median(np.abs(ed - med)))
        nf = get_noise_floor(param)
        scales[param] = float(max(1.4826 * mad, nf))
    return scales


class ResidualHistGBMModel:
    """Predicts delta_u = u_168 - u_24 using HistGradientBoostingRegressor and reconstructs u_168_hat = u_24 + delta_u_hat."""

    def __init__(
        self,
        parameter_name: str,
        feature_columns: Sequence[str],
        max_depth: int = 3,
        max_iter: int = 50,
        learning_rate: float = 0.05,
        min_samples_leaf: int = 10,
        l2_regularization: float = 1.0,
        random_state: int = 20260918,
    ) -> None:
        self.parameter_name = parameter_name
        self.feature_columns = list(feature_columns)
        self.hyperparameters = {
            "max_depth": max_depth,
            "max_iter": max_iter,
            "learning_rate": learning_rate,
            "min_samples_leaf": min_samples_leaf,
            "l2_regularization": l2_regularization,
            "random_state": random_state,
        }
        try:
            from sklearn.ensemble import HistGradientBoostingRegressor
            self.model = HistGradientBoostingRegressor(**self.hyperparameters)
        except ImportError:
            self.model = None
        self.is_fitted: bool = False

    def fit(self, X: np.ndarray, y_delta: np.ndarray) -> ResidualHistGBMModel:
        if self.model is None:
            raise RuntimeError("scikit-learn is required for ResidualHistGBMModel.")
        X = np.asarray(X, dtype=np.float64)
        y_delta = np.asarray(y_delta, dtype=np.float64)
        self.model.fit(X, y_delta)
        self.is_fitted = True
        return self

    def predict_delta(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model must be fitted before predict_delta.")
        X = np.asarray(X, dtype=np.float64)
        return self.model.predict(X)

    def predict(
        self,
        X: np.ndarray,
        u24_values: np.ndarray,
        v24_values: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        pred_delta = self.predict_delta(X)
        u24_arr = np.asarray(u24_values, dtype=np.float64)
        v24_arr = np.asarray(v24_values, dtype=np.float64)
        pred_u168 = u24_arr + pred_delta
        N = len(pred_u168)
        pred_phys = []
        is_divergent = []
        for i in range(N):
            u_val = pred_u168[i]
            v24 = v24_arr[i]
            if not np.isfinite(u_val) or abs(u_val) > 10.0:
                pred_phys.append(float(v24))
                is_divergent.append(True)
            else:
                try:
                    phys = inverse_transform_parameter(self.parameter_name, u_val)
                    if not np.isfinite(phys):
                        pred_phys.append(float(v24))
                        is_divergent.append(True)
                    else:
                        pred_phys.append(float(phys))
                        is_divergent.append(False)
                except Exception:
                    pred_phys.append(float(v24))
                    is_divergent.append(True)
        return (
            np.array(pred_phys, dtype=np.float64),
            pred_u168,
            pred_delta,
            np.array(is_divergent, dtype=bool),
        )


class ZeroAnchoredHybridPrognosticModel:
    """Two-regime zero-anchored hybrid prognostic model.

    Implements Step 5 requirements for SIH 2026 Problem Statement SIH26170:
    Regime Decision:
        IF abs(excess_drift) <= threshold:
            regime = "ZERO_ANCHORED"
            reason = "Excess drift within training-derived noise band"
            delta_hat = 0
            u168_hat = u24
            y168_hat = v24
        ELSE:
            regime = "DRIFT_MODEL"
            reason = "Excess drift above training-derived noise band"
            delta_hat = base_model.predict_delta(X)
            u168_hat = u24 + delta_hat
            y168_hat = phi^-1(u168_hat)
    """

    def __init__(
        self,
        parameter_name: str,
        base_model: Any,
        threshold: float,
        feature_columns: Sequence[str],
    ) -> None:
        self.parameter_name = parameter_name
        self.base_model = base_model
        self.threshold = float(threshold)
        self.feature_columns = list(feature_columns)

    def predict_single(
        self,
        features_dict: Dict[str, float],
    ) -> Dict[str, Any]:
        u24 = float(features_dict["u24"])
        v24 = float(features_dict["v24"])
        excess_drift = float(features_dict["excess_drift"])

        if abs(excess_drift) <= self.threshold:
            regime = "ZERO_ANCHORED"
            reason = "Excess drift within training-derived noise band"
            delta_hat = 0.0
            u168_hat = u24
            pred_phys = v24
            is_divergent = False
            contributions = {"zero_anchor": 0.0}
            explanation = {
                "regime": regime,
                "reason": reason,
                "excess_drift": excess_drift,
                "threshold": self.threshold,
                "u24_baseline": u24,
                "predicted_forward_delta": 0.0,
                "reconstructed_u168": u24,
                "contributions": contributions,
            }
        else:
            regime = "DRIFT_MODEL"
            reason = "Excess drift above training-derived noise band"
            X = np.array([[features_dict[col] for col in self.feature_columns]], dtype=np.float64)
            p_phys, p_u168, p_delta, p_div = self.base_model.predict(X, np.array([u24]), np.array([v24]))
            delta_hat = float(p_delta[0])
            u168_hat = float(p_u168[0])
            pred_phys = float(p_phys[0])
            is_divergent = bool(p_div[0])
            
            contributions = {}
            if hasattr(self.base_model, "explain"):
                exp_base = self.base_model.explain(X[0], u24)
                contributions = dict(exp_base.get("feature_contributions", {}))
                contributions["intercept"] = exp_base.get("intercept", 0.0)
            else:
                # Tree-based model explanation
                contributions = {col: float(X[0, i]) for i, col in enumerate(self.feature_columns)}

            explanation = {
                "regime": regime,
                "reason": reason,
                "excess_drift": excess_drift,
                "threshold": self.threshold,
                "u24_baseline": u24,
                "predicted_forward_delta": delta_hat,
                "reconstructed_u168": u168_hat,
                "contributions": contributions,
            }

        return {
            "parameter_name": self.parameter_name,
            "regime": regime,
            "reason": reason,
            "u24": u24,
            "v24": v24,
            "excess_drift": excess_drift,
            "threshold": self.threshold,
            "predicted_physical": pred_phys,
            "predicted_u168": u168_hat,
            "predicted_delta": delta_hat,
            "is_divergent": is_divergent,
            "contributions": contributions,
            "explanation": explanation,
        }

    def predict_batch(
        self,
        feat_df: pd.DataFrame,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[str], List[str]]:
        """Predict batch of features."""
        preds_phys = []
        preds_u168 = []
        preds_delta = []
        regimes = []
        reasons = []

        for _, row in feat_df.iterrows():
            f_dict = {col: float(row[col]) for col in self.feature_columns}
            f_dict["u24"] = float(row["u24"])
            f_dict["v24"] = float(row["v24"])
            f_dict["excess_drift"] = float(row["excess_drift"])

            res = self.predict_single(f_dict)
            preds_phys.append(res["predicted_physical"])
            preds_u168.append(res["predicted_u168"])
            preds_delta.append(res["predicted_delta"])
            regimes.append(res["regime"])
            reasons.append(res["reason"])

        return (
            np.array(preds_phys, dtype=np.float64),
            np.array(preds_u168, dtype=np.float64),
            np.array(preds_delta, dtype=np.float64),
            regimes,
            reasons,
        )
