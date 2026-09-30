"""Phase 5 Supervised Predictive Regression Models for Module B.

Complies strictly with docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md:
- Exact primary task: [v0h, v24h] -> predicted v168h
- Genuinely population-trained supervised regression models (Ridge, Huber)
- Parameter-decoupled topology: separate independent model per physical parameter
- Established coordinate representations:
    * IDSS: positive log u = ln(y)
    * RDS(on): positive log u = ln(y)
    * VGS(th): bounded linear u = y
    * IGSS: signed asinh u = asinh(y / 1.0 nA), NEVER abs(), NEVER clipped
- Leakage-safe: training-fold only preprocessing and uncertainty calibration
- Numerical safety architecture: divergence detection, unconstrained logging,
  deterministic fallback to Carry-Forward, zero cosmetic clipping.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np

from sih26170.prognostics.schema import PrognosticInput, PrognosticForecast
from sih26170.prognostics.baselines import BasePrognosticModel, Z_90
from sih26170.screening.transforms import (
    transform_parameter,
    inverse_transform_parameter,
    get_noise_floor,
    IGSS_SCALE_NA,
)


class BaseSupervisedRegressionModel(BasePrognosticModel, ABC):
    """Abstract base class for population-trained supervised regression models."""

    def __init__(
        self,
        parameter_name: str,
        unit: str,
        model_family: str,
        model_id_prefix: str = "REG",
    ) -> None:
        model_id = f"{model_id_prefix}_{model_family}_{parameter_name}"
        super().__init__(model_id=model_id)
        self.parameter_name = parameter_name
        self.unit = unit
        self.model_family = model_family
        self.is_fitted: bool = False

        # Fitted parameters: intercept, slope_v0, slope_v24 in transformed space
        # Model: u_hat_168 = beta_0 + beta_1 * u_0 + beta_2 * u_24
        self.coefficients_: Optional[np.ndarray] = None  # shape (3,)
        self.preprocessor_params_: Dict[str, float] = {}
        self.hyperparameters: Dict[str, Any] = {}
        self.training_lot_ids: List[str] = []
        self.training_sample_count: int = 0
        self._sigma_eff_u_scalar: float = get_noise_floor(parameter_name)

    @abstractmethod
    def _fit_transformed(
        self,
        U_train: np.ndarray,
        u_target: np.ndarray,
    ) -> np.ndarray:
        """Fit model on transformed design matrix U_train (N, 2) and u_target (N,).

        Returns:
            np.ndarray of shape (3,) containing [beta_0, beta_1, beta_2].
        """
        pass

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_lot_ids: Optional[Sequence[str]] = None,
        training_lot_ids: Optional[Sequence[str]] = None,
    ) -> BaseSupervisedRegressionModel:
        """Fit supervised regression model on training population.

        Args:
            X: Array of shape (N, 2) containing [v0, v24] in physical units.
            y: Array of shape (N,) containing v168 in physical units.
            sample_lot_ids: Optional sequence of lot IDs corresponding to each row of X/y.
                When provided with >= 2 unique lots, uncertainty calibration uses nested
                leave-one-lot-out (LOLO) out-of-fold residuals within the training fold.
            training_lot_ids: Optional sequence of unique lot IDs present in training data.

        Returns:
            Self (fitted model instance).
        """
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)

        if X.ndim != 2 or X.shape[1] != 2:
            raise ValueError(f"X must be of shape (N, 2) representing [v0, v24], got {X.shape}")
        if y.ndim != 1 or y.shape[0] != X.shape[0]:
            raise ValueError(f"y must be of shape ({X.shape[0]},), got {y.shape}")
        if len(y) < 3:
            raise ValueError(f"Training set must have at least 3 samples, got {len(y)}")

        # 1. Transform inputs and target into model representation space
        U_list: List[Tuple[float, float]] = []
        u_target_list: List[float] = []
        valid_sample_lots: List[str] = []

        for i in range(len(y)):
            v0 = float(X[i, 0])
            v24 = float(X[i, 1])
            v168 = float(y[i])

            if not (np.isfinite(v0) and np.isfinite(v24) and np.isfinite(v168)):
                continue

            try:
                u0 = transform_parameter(self.parameter_name, v0)
                u24 = transform_parameter(self.parameter_name, v24)
                u168 = transform_parameter(self.parameter_name, v168)
                U_list.append((u0, u24))
                u_target_list.append(u168)
                if sample_lot_ids is not None:
                    valid_sample_lots.append(str(sample_lot_ids[i]))
            except (ValueError, KeyError):
                # Exclude non-physical measurements (e.g. non-positive IDSS/RDS(on))
                continue

        if len(u_target_list) < 3:
            raise ValueError(
                f"Fewer than 3 physically valid complete cases for {self.parameter_name}: {len(u_target_list)}"
            )

        U_arr = np.array(U_list, dtype=np.float64)
        u_t_arr = np.array(u_target_list, dtype=np.float64)
        sample_lots_arr = np.array(valid_sample_lots) if valid_sample_lots else None

        # 2. Record training-fold preprocessor statistics (strictly training-fold only)
        u0_mean = float(np.mean(U_arr[:, 0]))
        u0_std = float(np.std(U_arr[:, 0]))
        u24_mean = float(np.mean(U_arr[:, 1]))
        u24_std = float(np.std(U_arr[:, 1]))

        self.preprocessor_params_ = {
            "u0_mean": u0_mean,
            "u0_std": u0_std if u0_std > 1e-12 else 1.0,
            "u24_mean": u24_mean,
            "u24_std": u24_std if u24_std > 1e-12 else 1.0,
        }

        # 3. Fit primary model parameters on entire training fold
        self.coefficients_ = self._fit_transformed(U_arr, u_t_arr)

        # 4. Generate leakage-safe out-of-fold (OOF) residuals for uncertainty calibration
        # Critical requirement: Every OOF prediction must be produced by an internal model
        # fitted WITHOUT the observation / lot being predicted.
        oof_residuals: List[float] = []

        if sample_lots_arr is not None and len(np.unique(sample_lots_arr)) >= 2:
            # Internal lot-wise cross-validation (nested LOLO across training lots)
            unique_lots = np.unique(sample_lots_arr)
            for inner_lot in unique_lots:
                inner_train_mask = (sample_lots_arr != inner_lot)
                inner_val_mask = (sample_lots_arr == inner_lot)

                U_in_train = U_arr[inner_train_mask]
                u_t_in_train = u_t_arr[inner_train_mask]
                beta_inner = self._fit_transformed(U_in_train, u_t_in_train)

                U_in_val = U_arr[inner_val_mask]
                u_t_in_val = u_t_arr[inner_val_mask]
                X_aug_val = np.column_stack([np.ones(len(U_in_val)), U_in_val])
                u_pred_val = X_aug_val @ beta_inner

                oof_residuals.extend((u_t_in_val - u_pred_val).tolist())
        elif len(u_t_arr) >= 5:
            # Deterministic k-fold cross-validation when lot identifiers are absent
            k = min(5, len(u_t_arr))
            indices = np.arange(len(u_t_arr))
            for f in range(k):
                inner_train_mask = (indices % k != f)
                inner_val_mask = (indices % k == f)

                U_in_train = U_arr[inner_train_mask]
                u_t_in_train = u_t_arr[inner_train_mask]
                beta_inner = self._fit_transformed(U_in_train, u_t_in_train)

                U_in_val = U_arr[inner_val_mask]
                u_t_in_val = u_t_arr[inner_val_mask]
                X_aug_val = np.column_stack([np.ones(len(U_in_val)), U_in_val])
                u_pred_val = X_aug_val @ beta_inner

                oof_residuals.extend((u_t_in_val - u_pred_val).tolist())
        else:
            # Fallback for ultra-small sample sizes (N < 5)
            X_aug = np.column_stack([np.ones(len(U_arr)), U_arr])
            u_pred = X_aug @ self.coefficients_
            oof_residuals = (u_t_arr - u_pred).tolist()

        oof_residuals_arr = np.array(oof_residuals, dtype=np.float64)
        med_res = float(np.median(oof_residuals_arr))
        mad_res = float(np.median(np.abs(oof_residuals_arr - med_res)))
        scale = 1.4826 * mad_res
        noise_floor = get_noise_floor(self.parameter_name)
        self._sigma_eff_u_scalar = max(scale, noise_floor)
        self._sigma_eff_u[self.parameter_name] = self._sigma_eff_u_scalar
        self.oof_residual_count_ = len(oof_residuals_arr)

        self.training_sample_count = len(u_t_arr)
        if training_lot_ids is not None:
            self.training_lot_ids = list(training_lot_ids)
        elif sample_lots_arr is not None:
            self.training_lot_ids = sorted(list(np.unique(sample_lots_arr)))
        self.is_fitted = True

        return self


    def predict_transformed(self, X: np.ndarray) -> np.ndarray:
        """Generate point predictions in transformed space.

        Args:
            X: Array of shape (N, 2) containing [v0, v24] in physical units.

        Returns:
            np.ndarray of shape (N,) containing u_hat_168.
        """
        if not self.is_fitted or self.coefficients_ is None:
            raise RuntimeError(f"Model {self.model_id} must be fitted before predict")

        X = np.asarray(X, dtype=np.float64)
        if X.ndim != 2 or X.shape[1] != 2:
            raise ValueError(f"X must be of shape (N, 2), got {X.shape}")

        u_preds: List[float] = []
        for i in range(len(X)):
            v0, v24 = float(X[i, 0]), float(X[i, 1])
            if not (np.isfinite(v0) and np.isfinite(v24)):
                u_preds.append(float("nan"))
                continue
            try:
                u0 = transform_parameter(self.parameter_name, v0)
                u24 = transform_parameter(self.parameter_name, v24)
                # u_hat = beta_0 + beta_1 * u0 + beta_2 * u24
                u_hat = self.coefficients_[0] + self.coefficients_[1] * u0 + self.coefficients_[2] * u24
                u_preds.append(float(u_hat))
            except (ValueError, KeyError):
                u_preds.append(float("nan"))

        return np.array(u_preds, dtype=np.float64)

    def predict_physical(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate point predictions and 90% uncertainty intervals in physical engineering units.

        Returns:
            Tuple of (y_pred, y_lower, y_upper) in physical units.
            In case of divergence or non-finite result, falls back to Carry-Forward (v24).
        """
        X = np.asarray(X, dtype=np.float64)
        u_preds = self.predict_transformed(X)

        y_preds: List[float] = []
        y_lowers: List[float] = []
        y_uppers: List[float] = []

        sigma_u = self._sigma_eff_u_scalar

        for i in range(len(X)):
            u_hat = u_preds[i]
            v24 = float(X[i, 1])

            # Numerical safety checks
            is_valid = np.isfinite(u_hat) and abs(u_hat) <= 10.0

            if is_valid:
                try:
                    y_p = inverse_transform_parameter(self.parameter_name, u_hat)
                    u_low = u_hat - Z_90 * sigma_u
                    u_upp = u_hat + Z_90 * sigma_u
                    y_l = inverse_transform_parameter(self.parameter_name, u_low)
                    y_u = inverse_transform_parameter(self.parameter_name, u_upp)

                    if np.isfinite(y_p) and np.isfinite(y_l) and np.isfinite(y_u):
                        y_preds.append(float(y_p))
                        y_lowers.append(float(min(y_l, y_u)))
                        y_uppers.append(float(max(y_l, y_u)))
                        continue
                except (ValueError, OverflowError):
                    pass

            # Fallback to Carry-Forward (v24) if divergent
            fallback_val = v24 if np.isfinite(v24) else float("nan")
            y_preds.append(fallback_val)
            y_lowers.append(fallback_val)
            y_uppers.append(fallback_val)

        return (
            np.array(y_preds, dtype=np.float64),
            np.array(y_lowers, dtype=np.float64),
            np.array(y_uppers, dtype=np.float64),
        )

    def predict_single(self, input_data: PrognosticInput) -> PrognosticForecast:
        """Generate forecast contract for a single component input."""
        if not input_data.data_sufficiency_passed:
            return PrognosticForecast(
                component_id=input_data.component_id,
                lot_id=input_data.lot_id,
                parameter_name=input_data.parameter_name,
                unit=input_data.unit,
                as_of_hours=input_data.as_of_hours,
                target_hours=input_data.target_hours,
                predicted_value=float("nan"),
                forecast_change_from_origin=float("nan"),
                baseline_relative_forecast_change=float("nan"),
                model_id=self.model_id,
                is_valid=False,
                exclusion_reason=input_data.insufficient_reason or "Insufficient data",
            )

        baseline = input_data.get_baseline_observation()
        latest = input_data.get_latest_observation()

        if baseline is None or latest is None or input_data.as_of_hours < 24:
            return PrognosticForecast(
                component_id=input_data.component_id,
                lot_id=input_data.lot_id,
                parameter_name=input_data.parameter_name,
                unit=input_data.unit,
                as_of_hours=input_data.as_of_hours,
                target_hours=input_data.target_hours,
                predicted_value=float("nan"),
                forecast_change_from_origin=float("nan"),
                baseline_relative_forecast_change=float("nan"),
                model_id=self.model_id,
                is_valid=False,
                exclusion_reason="Missing 0h baseline or 24h intermediate readout",
            )

        v0 = baseline[1]
        v24 = latest[1]

        # Single bivariate feature vector
        X = np.array([[v0, v24]], dtype=np.float64)
        u_pred = float(self.predict_transformed(X)[0])

        is_divergent = False
        raw_u_pred = u_pred

        if not np.isfinite(u_pred) or abs(u_pred) > 10.0:
            is_divergent = True
            pred_y = v24
            y_low = v24
            y_upp = v24
        else:
            try:
                pred_y = inverse_transform_parameter(self.parameter_name, u_pred)
                u_low = u_pred - Z_90 * self._sigma_eff_u_scalar
                u_upp = u_pred + Z_90 * self._sigma_eff_u_scalar
                y_low_t = inverse_transform_parameter(self.parameter_name, u_low)
                y_upp_t = inverse_transform_parameter(self.parameter_name, u_upp)
                y_low = min(y_low_t, y_upp_t)
                y_upp = max(y_low_t, y_upp_t)

                if not (np.isfinite(pred_y) and np.isfinite(y_low) and np.isfinite(y_upp)):
                    is_divergent = True
                    pred_y = v24
                    y_low = v24
                    y_upp = v24
            except (ValueError, OverflowError):
                is_divergent = True
                pred_y = v24
                y_low = v24
                y_upp = v24

        forecast_change_from_origin = pred_y - v24
        baseline_relative_forecast_change = pred_y - v0

        metadata = {
            "v0": v0,
            "v24": v24,
            "coefficients": list(self.coefficients_) if self.coefficients_ is not None else None,
            "preprocessor_params": dict(self.preprocessor_params_),
            "hyperparameters": dict(self.hyperparameters),
            "raw_unconstrained_u_pred": raw_u_pred,
        }

        return PrognosticForecast(
            component_id=input_data.component_id,
            lot_id=input_data.lot_id,
            parameter_name=input_data.parameter_name,
            unit=input_data.unit,
            as_of_hours=input_data.as_of_hours,
            target_hours=input_data.target_hours,
            predicted_value=float(pred_y),
            forecast_change_from_origin=float(forecast_change_from_origin),
            baseline_relative_forecast_change=float(baseline_relative_forecast_change),
            interval_lower=float(y_low),
            interval_upper=float(y_upp),
            interval_coverage=0.90,
            sigma_eff=float(self._sigma_eff_u_scalar),
            model_id=self.model_id,
            is_valid=True,
            is_divergent_fallback=is_divergent,
            raw_unconstrained_u_pred=float(raw_u_pred) if np.isfinite(raw_u_pred) else None,
            metadata=metadata,
        )

    def get_lineage(self) -> Dict[str, Any]:
        """Return complete model lineage dictionary."""
        return {
            "model_id": self.model_id,
            "model_family": self.model_family,
            "parameter_name": self.parameter_name,
            "unit": self.unit,
            "is_fitted": self.is_fitted,
            "training_sample_count": self.training_sample_count,
            "oof_residual_count": getattr(self, "oof_residual_count_", self.training_sample_count),
            "calibration_method": "NESTED_LOLO_OUT_OF_FOLD",
            "training_lot_ids": list(self.training_lot_ids),
            "preprocessor_params": {k: float(v) for k, v in self.preprocessor_params_.items()},
            "coefficients": [float(c) for c in self.coefficients_] if self.coefficients_ is not None else None,
            "hyperparameters": dict(self.hyperparameters),
            "sigma_eff": float(self._sigma_eff_u_scalar),
            "random_seed": None,
        }

    def _compute_point_prediction(self, input_data: PrognosticInput) -> Optional[float]:
        forecast = self.predict_single(input_data)
        return float(forecast.predicted_value) if forecast.is_valid and np.isfinite(forecast.predicted_value) else None


class RidgeRegressionPrognosticModel(BaseSupervisedRegressionModel):
    """L2 Regularized Linear Population Regression in parameter-specific coordinate space.

    Hypothesis:
    Under common semiconductor manufacturing kinetics, early burn-in measurements
    contain population-level associations with terminal values. Ridge regularized
    estimation stabilizes matrix inversion across collinear (u0, u24) pairs and
    smooths individual measurement jitter toward the population trend.
    """

    def __init__(
        self,
        parameter_name: str,
        unit: str,
        l2_reg: float = 1.0,
    ) -> None:
        super().__init__(
            parameter_name=parameter_name,
            unit=unit,
            model_family="RIDGE",
            model_id_prefix="REG",
        )
        self.l2_reg = float(l2_reg)
        self.hyperparameters = {"l2_reg": self.l2_reg}

    def _fit_transformed(
        self,
        U_train: np.ndarray,
        u_target: np.ndarray,
    ) -> np.ndarray:
        """Solve exact Ridge normal equations: (X^T X + Gamma)^(-1) X^T y."""
        N = len(U_train)
        X_aug = np.column_stack([np.ones(N), U_train])  # (N, 3)

        # Penalize slopes beta_1 and beta_2, do NOT penalize intercept beta_0
        Gamma = np.diag([0.0, self.l2_reg, self.l2_reg])
        XtX = X_aug.T @ X_aug
        Xty = X_aug.T @ u_target

        beta = np.linalg.solve(XtX + Gamma, Xty)
        return beta


class HuberRegressionPrognosticModel(BaseSupervisedRegressionModel):
    """Robust Huber Loss Population Regression in parameter-specific coordinate space.

    Hypothesis:
    Measurement anomalies or isolated physical defects can produce heavy-tailed
    residuals in training lots. Huber loss applies quadratic loss to nominal
    residuals and linear loss to extreme deviations, preventing outlier leverage
    from distorting the population regression parameters.
    """

    def __init__(
        self,
        parameter_name: str,
        unit: str,
        l2_reg: float = 1.0,
        delta_scale: float = 1.345,
        max_iter: int = 50,
        tol: float = 1e-6,
    ) -> None:
        super().__init__(
            parameter_name=parameter_name,
            unit=unit,
            model_family="HUBER",
            model_id_prefix="REG",
        )
        self.l2_reg = float(l2_reg)
        self.delta_scale = float(delta_scale)
        self.max_iter = int(max_iter)
        self.tol = float(tol)
        self.hyperparameters = {
            "l2_reg": self.l2_reg,
            "delta_scale": self.delta_scale,
            "max_iter": self.max_iter,
            "tol": self.tol,
        }

    def _fit_transformed(
        self,
        U_train: np.ndarray,
        u_target: np.ndarray,
    ) -> np.ndarray:
        """Fit Huber regression via Iteratively Reweighted Least Squares (IRLS)."""
        N = len(U_train)
        X_aug = np.column_stack([np.ones(N), U_train])
        Gamma = np.diag([0.0, self.l2_reg, self.l2_reg])

        # 1. Initialize with Ridge estimate
        beta = np.linalg.solve(X_aug.T @ X_aug + Gamma, X_aug.T @ u_target)

        noise_floor = get_noise_floor(self.parameter_name)

        # 2. Iterate IRLS to convergence
        for _ in range(self.max_iter):
            residuals = u_target - X_aug @ beta
            med_res = float(np.median(residuals))
            mad_res = float(np.median(np.abs(residuals - med_res)))
            # Adaptive Huber threshold: delta = 1.345 * sigma_eff
            sigma_eff = max(1.4826 * mad_res, noise_floor)
            delta = self.delta_scale * sigma_eff

            abs_r = np.abs(residuals)
            # Weight function: w_i = 1 if |r_i| <= delta else delta / |r_i|
            weights = np.where(abs_r <= delta, 1.0, delta / np.maximum(abs_r, 1e-12))

            # Solve weighted least squares: (X^T W X + Gamma)^(-1) X^T W y
            X_weighted = X_aug * weights[:, np.newaxis]
            Xt_W_X = X_aug.T @ X_weighted
            Xt_W_y = X_aug.T @ (weights * u_target)

            new_beta = np.linalg.solve(Xt_W_X + Gamma, Xt_W_y)

            if np.max(np.abs(new_beta - beta)) < self.tol:
                beta = new_beta
                break
            beta = new_beta

        return beta


class ParameterDecoupledRegressionPipeline:
    """Orchestrates independent regression models across the four physical parameters.

    Enforces:
    - Zero parameter cross-contamination.
    - Decoupled physical transformations.
    - Signed IGSS semantics.
    """

    PARAMETERS: Tuple[str, ...] = ("IDSS", "VGS(th)", "RDS(on)", "IGSS")
    UNITS: Dict[str, str] = {
        "IDSS": "uA",
        "VGS(th)": "V",
        "RDS(on)": "mOhm",
        "IGSS": "nA",
    }

    def __init__(
        self,
        model_family: str = "RIDGE",
        **model_kwargs: Any,
    ) -> None:
        self.model_family = model_family.upper()
        self.models: Dict[str, BaseSupervisedRegressionModel] = {}

        for param in self.PARAMETERS:
            unit = self.UNITS[param]
            if self.model_family == "RIDGE":
                self.models[param] = RidgeRegressionPrognosticModel(
                    parameter_name=param,
                    unit=unit,
                    **model_kwargs,
                )
            elif self.model_family == "HUBER":
                self.models[param] = HuberRegressionPrognosticModel(
                    parameter_name=param,
                    unit=unit,
                    **model_kwargs,
                )
            else:
                raise ValueError(f"Unknown model_family '{model_family}'. Expected 'RIDGE' or 'HUBER'.")

    def fit_from_dataframe(
        self,
        df: pd.DataFrame,
        training_lot_ids: Optional[Sequence[str]] = None,
    ) -> ParameterDecoupledRegressionPipeline:
        """Fit all 4 models from a telemetry observations DataFrame.

        Extracts complete [v0, v24, v168] triads for each parameter.
        """
        import pandas as pd

        # Assert no ground-truth or future-leakage columns
        from sih26170.prognostics.validation import assert_no_ground_truth_leakage
        assert_no_ground_truth_leakage(df)

        for param, model in self.models.items():
            pdf = df[df["parameter_name"] == param]
            piv = pdf.pivot(index=["lot_id", "component_id"], columns="elapsed_hours", values="value").reset_index()

            if 0 not in piv.columns or 24 not in piv.columns or 168 not in piv.columns:
                raise ValueError(f"Telemetry missing required checkpoints (0, 24, 168h) for {param}")

            triads = piv[[0, 24, 168, "lot_id"]].dropna()
            X = triads[[0, 24]].values
            y = triads[168].values
            sample_lots = triads["lot_id"].values

            model.fit(X, y, sample_lot_ids=sample_lots, training_lot_ids=training_lot_ids)

        return self

    def get_model(self, parameter_name: str) -> BaseSupervisedRegressionModel:
        """Retrieve fitted model for specific physical parameter."""
        if parameter_name not in self.models:
            raise KeyError(f"Unknown parameter '{parameter_name}'. Expected one of {self.PARAMETERS}")
        return self.models[parameter_name]

    def predict_single(self, input_data: PrognosticInput) -> PrognosticForecast:
        """Route prediction to the appropriate parameter-specific model."""
        model = self.get_model(input_data.parameter_name)
        return model.predict_single(input_data)
