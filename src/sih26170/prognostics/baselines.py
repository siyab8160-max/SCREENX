"""Baseline prognostic models for Module B Stage 1.

Implements ONLY:
1. CarryForwardModel (Persistence Baseline)
2. TwoPointLinearModel (for Task 1: 24h -> 168h)
3. TheilSenExtrapolationModel (for Task 2: 96h -> 168h)

Complies with:
- Strict as-of invariance.
- Uncertainty estimation calibrated ONLY on training fold residuals.
- Dual drift quantities exposed on every forecast:
  A. forecast_change_from_origin = predicted_value - observed_value(as_of)
  B. baseline_relative_forecast_change = predicted_value - observed_value(0h)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Sequence, Tuple
import numpy as np

from sih26170.prognostics.schema import PrognosticInput, PrognosticForecast
from sih26170.screening.transforms import (
    transform_parameter,
    inverse_transform_parameter,
    get_noise_floor,
)

# Standard normal critical value for two-sided 90% confidence interval (alpha = 0.10)
Z_90: float = 1.6448536269514722
Z_95: float = 1.959963984540054


class BasePrognosticModel(ABC):
    """Abstract base class for prognostic models."""

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        # Per-parameter calibrated residual scale in transformed space: sigma_eff_u[param]
        self._sigma_eff_u: Dict[str, float] = {}

    @abstractmethod
    def predict_single(self, input_data: PrognosticInput) -> PrognosticForecast:
        """Generate forecast for a single component parameter."""
        pass

    def fit(
        self,
        train_inputs: Sequence[PrognosticInput],
        train_ground_truth: Sequence[float],
        coverage: float = 0.90,
    ) -> None:
        """Calibrate candidate residual scale sigma_eff on training fold data ONLY.

        Args:
            train_inputs: Sequence of PrognosticInput from training lots
            train_ground_truth: True physical values at target_hours from training lots
            coverage: Nominal interval coverage (default: 0.90)
        """
        if len(train_inputs) != len(train_ground_truth):
            raise ValueError("train_inputs and train_ground_truth must have identical lengths")

        # Collect residuals in transformed space partitioned by parameter
        param_residuals: Dict[str, List[float]] = {}
        for inp, true_y in zip(train_inputs, train_ground_truth):
            if not inp.data_sufficiency_passed or not np.isfinite(true_y):
                continue
            pred = self._compute_point_prediction(inp)
            if pred is None or not np.isfinite(pred):
                continue

            param = inp.parameter_name
            try:
                u_true = transform_parameter(param, true_y)
                u_pred = transform_parameter(param, pred)
                res_u = u_true - u_pred
                if np.isfinite(res_u):
                    if param not in param_residuals:
                        param_residuals[param] = []
                    param_residuals[param].append(res_u)
            except (ValueError, KeyError):
                continue

        # Compute robust scale: sigma_eff_u = 1.4826 * MAD(residuals)
        self._sigma_eff_u.clear()
        for param, res_list in param_residuals.items():
            if len(res_list) >= 3:
                arr = np.array(res_list)
                med = float(np.median(arr))
                mad = float(np.median(np.abs(arr - med)))
                scale = 1.4826 * mad
                # Bound below by parameter noise floor
                floor = get_noise_floor(param)
                self._sigma_eff_u[param] = max(scale, floor)
            else:
                self._sigma_eff_u[param] = get_noise_floor(param)

    def _compute_point_prediction(self, input_data: PrognosticInput) -> Optional[float]:
        """Compute uncalibrated point prediction."""
        pass


class CarryForwardModel(BasePrognosticModel):
    """Carry-Forward (Persistence) Baseline Model.

    Forecasts that the parameter value at target_hours equals its latest as-of observation.
    """

    def __init__(self) -> None:
        super().__init__(model_id="BASELINE_CARRY_FORWARD")

    def _compute_point_prediction(self, input_data: PrognosticInput) -> Optional[float]:
        latest = input_data.get_latest_observation()
        if latest is None:
            return None
        return float(latest[1])

    def predict_single(self, input_data: PrognosticInput) -> PrognosticForecast:
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

        latest = input_data.get_latest_observation()
        baseline = input_data.get_baseline_observation()

        if latest is None:
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
                exclusion_reason="No historical observations available",
            )

        y_as_of = float(latest[1])
        y_0 = float(baseline[1]) if baseline is not None else y_as_of

        # Carry forward point prediction
        y_pred = y_as_of

        # Dual drift calculations
        forecast_change_from_origin = y_pred - y_as_of  # Strictly 0.0 for carry-forward
        baseline_relative_forecast_change = y_pred - y_0

        # Uncertainty calculation if calibrated
        param = input_data.parameter_name
        sigma_eff_u = self._sigma_eff_u.get(param)
        interval_lower: Optional[float] = None
        interval_upper: Optional[float] = None

        if sigma_eff_u is not None:
            try:
                u_pred = transform_parameter(param, y_pred)
                u_low = u_pred - Z_90 * sigma_eff_u
                u_high = u_pred + Z_90 * sigma_eff_u
                interval_lower = inverse_transform_parameter(param, u_low)
                interval_upper = inverse_transform_parameter(param, u_high)
            except Exception:
                interval_lower = None
                interval_upper = None

        return PrognosticForecast(
            component_id=input_data.component_id,
            lot_id=input_data.lot_id,
            parameter_name=input_data.parameter_name,
            unit=input_data.unit,
            as_of_hours=input_data.as_of_hours,
            target_hours=input_data.target_hours,
            predicted_value=y_pred,
            forecast_change_from_origin=forecast_change_from_origin,
            baseline_relative_forecast_change=baseline_relative_forecast_change,
            interval_lower=interval_lower,
            interval_upper=interval_upper,
            interval_coverage=0.90,
            sigma_eff=sigma_eff_u,
            model_id=self.model_id,
            is_valid=True,
            metadata={"audit_hash": input_data.audit_hash},
        )


class TwoPointLinearModel(BasePrognosticModel):
    """Two-Point Linear Extrapolation Baseline (Task 1: 24h -> 168h).

    Computes linear slope in parameter-transformed space across (0h, 24h),
    extrapolates to target_hours (168h), and inverts back to physical units.
    """

    def __init__(self) -> None:
        super().__init__(model_id="BASELINE_TWO_POINT_LINEAR")

    def _compute_point_prediction(self, input_data: PrognosticInput) -> Optional[float]:
        # Extract 0h and 24h points
        obs_map = {t: v for t, v in input_data.historical_observations}
        if 0 not in obs_map or 24 not in obs_map:
            latest = input_data.get_latest_observation()
            return float(latest[1]) if latest else None

        param = input_data.parameter_name
        try:
            u_0 = transform_parameter(param, obs_map[0])
            u_24 = transform_parameter(param, obs_map[24])
            slope = (u_24 - u_0) / 24.0
            u_pred = u_0 + slope * float(input_data.target_hours)
            return float(inverse_transform_parameter(param, u_pred))
        except Exception:
            return float(obs_map[24])

    def predict_single(self, input_data: PrognosticInput) -> PrognosticForecast:
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

        obs_map = {t: v for t, v in input_data.historical_observations}
        baseline = input_data.get_baseline_observation()
        latest = input_data.get_latest_observation()

        if latest is None or baseline is None:
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
                exclusion_reason="Missing required baseline observation",
            )

        y_as_of = float(latest[1])
        y_0 = float(baseline[1])
        param = input_data.parameter_name

        if 0 not in obs_map or 24 not in obs_map:
            # Fallback to carry-forward with logged exclusion flag
            y_pred = y_as_of
            is_valid = False
            exclusion_reason = "Missing 0h or 24h observation for two-point extrapolation"
        else:
            try:
                u_0 = transform_parameter(param, obs_map[0])
                u_24 = transform_parameter(param, obs_map[24])
                slope = (u_24 - u_0) / 24.0
                u_pred = u_0 + slope * float(input_data.target_hours)
                y_pred = float(inverse_transform_parameter(param, u_pred))
                is_valid = True
                exclusion_reason = None
            except Exception as ex:
                y_pred = y_as_of
                is_valid = False
                exclusion_reason = f"Numerical error in two-point extrapolation: {str(ex)}"

        forecast_change_from_origin = y_pred - y_as_of
        baseline_relative_forecast_change = y_pred - y_0

        sigma_eff_u = self._sigma_eff_u.get(param)
        interval_lower: Optional[float] = None
        interval_upper: Optional[float] = None

        if sigma_eff_u is not None and is_valid:
            try:
                u_pred_center = transform_parameter(param, y_pred)
                u_low = u_pred_center - Z_90 * sigma_eff_u
                u_high = u_pred_center + Z_90 * sigma_eff_u
                interval_lower = inverse_transform_parameter(param, u_low)
                interval_upper = inverse_transform_parameter(param, u_high)
            except Exception:
                interval_lower = None
                interval_upper = None

        return PrognosticForecast(
            component_id=input_data.component_id,
            lot_id=input_data.lot_id,
            parameter_name=input_data.parameter_name,
            unit=input_data.unit,
            as_of_hours=input_data.as_of_hours,
            target_hours=input_data.target_hours,
            predicted_value=y_pred,
            forecast_change_from_origin=forecast_change_from_origin,
            baseline_relative_forecast_change=baseline_relative_forecast_change,
            interval_lower=interval_lower,
            interval_upper=interval_upper,
            interval_coverage=0.90,
            sigma_eff=sigma_eff_u,
            model_id=self.model_id,
            is_valid=is_valid,
            exclusion_reason=exclusion_reason,
            metadata={"audit_hash": input_data.audit_hash},
        )


class TheilSenExtrapolationModel(BasePrognosticModel):
    """Robust Theil-Sen Extrapolation Baseline (Task 2: 96h -> 168h).

    Computes median pairwise slope in parameter-transformed space across {0h, 24h, 96h},
    extrapolates from 96h to target_hours (168h), and inverts back to physical units.
    """

    def __init__(self) -> None:
        super().__init__(model_id="BASELINE_THEIL_SEN")

    def _compute_point_prediction(self, input_data: PrognosticInput) -> Optional[float]:
        obs_map = {t: v for t, v in input_data.historical_observations}
        checkpoints = sorted([t for t in obs_map.keys() if t <= input_data.as_of_hours])
        if len(checkpoints) < 2:
            latest = input_data.get_latest_observation()
            return float(latest[1]) if latest else None

        param = input_data.parameter_name
        try:
            transformed_pts = [(t, transform_parameter(param, obs_map[t])) for t in checkpoints]
            slopes = []
            for i in range(len(transformed_pts)):
                for j in range(i + 1, len(transformed_pts)):
                    dt = transformed_pts[j][0] - transformed_pts[i][0]
                    if dt > 0:
                        slopes.append((transformed_pts[j][1] - transformed_pts[i][1]) / dt)
            if not slopes:
                return float(obs_map[checkpoints[-1]])

            med_slope = float(np.median(slopes))
            latest_t, latest_u = transformed_pts[-1]
            u_pred = latest_u + med_slope * float(input_data.target_hours - latest_t)
            return float(inverse_transform_parameter(param, u_pred))
        except Exception:
            latest = input_data.get_latest_observation()
            return float(latest[1]) if latest else None

    def predict_single(self, input_data: PrognosticInput) -> PrognosticForecast:
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

        obs_map = {t: v for t, v in input_data.historical_observations}
        baseline = input_data.get_baseline_observation()
        latest = input_data.get_latest_observation()

        if latest is None or baseline is None:
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
                exclusion_reason="Missing required observation",
            )

        y_as_of = float(latest[1])
        y_0 = float(baseline[1])
        param = input_data.parameter_name

        checkpoints = sorted([t for t in obs_map.keys() if t <= input_data.as_of_hours])
        if len(checkpoints) < 2:
            y_pred = y_as_of
            is_valid = False
            exclusion_reason = "Fewer than 2 historical points available for slope estimation"
        else:
            try:
                transformed_pts = [(t, transform_parameter(param, obs_map[t])) for t in checkpoints]
                slopes = []
                for i in range(len(transformed_pts)):
                    for j in range(i + 1, len(transformed_pts)):
                        dt = transformed_pts[j][0] - transformed_pts[i][0]
                        if dt > 0:
                            slopes.append((transformed_pts[j][1] - transformed_pts[i][1]) / dt)

                med_slope = float(np.median(slopes))
                latest_t, latest_u = transformed_pts[-1]
                u_pred = latest_u + med_slope * float(input_data.target_hours - latest_t)
                y_pred = float(inverse_transform_parameter(param, u_pred))
                is_valid = True
                exclusion_reason = None
            except Exception as ex:
                y_pred = y_as_of
                is_valid = False
                exclusion_reason = f"Numerical error in Theil-Sen extrapolation: {str(ex)}"

        forecast_change_from_origin = y_pred - y_as_of
        baseline_relative_forecast_change = y_pred - y_0

        sigma_eff_u = self._sigma_eff_u.get(param)
        interval_lower: Optional[float] = None
        interval_upper: Optional[float] = None

        if sigma_eff_u is not None and is_valid:
            try:
                u_pred_center = transform_parameter(param, y_pred)
                u_low = u_pred_center - Z_90 * sigma_eff_u
                u_high = u_pred_center + Z_90 * sigma_eff_u
                interval_lower = inverse_transform_parameter(param, u_low)
                interval_upper = inverse_transform_parameter(param, u_high)
            except Exception:
                interval_lower = None
                interval_upper = None

        return PrognosticForecast(
            component_id=input_data.component_id,
            lot_id=input_data.lot_id,
            parameter_name=input_data.parameter_name,
            unit=input_data.unit,
            as_of_hours=input_data.as_of_hours,
            target_hours=input_data.target_hours,
            predicted_value=y_pred,
            forecast_change_from_origin=forecast_change_from_origin,
            baseline_relative_forecast_change=baseline_relative_forecast_change,
            interval_lower=interval_lower,
            interval_upper=interval_upper,
            interval_coverage=0.90,
            sigma_eff=sigma_eff_u,
            model_id=self.model_id,
            is_valid=is_valid,
            exclusion_reason=exclusion_reason,
            metadata={"audit_hash": input_data.audit_hash},
        )
