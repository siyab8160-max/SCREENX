"""Stage 2 Prognostic Models for Module B.

Implements two physically and statistically justified models:
1. AdaptiveDriftGatedModel: Soft-thresholded L1-regularized slope extrapolation.
   Eliminates measurement-noise amplification on nominal parts while preserving
   extrapolation on true degraders.
2. HierarchicalLotShrunkModel: Empirical Bayes lot-shrinkage extrapolation.
   Uses contemporaneous lot median and dispersion to adaptively shrink noisy slopes.

Complies strictly with:
- Zero neural networks, deep learning, or high-complexity black-boxes.
- Strict as-of temporal causality.
- Training-fold only uncertainty calibration.
- Complete lineage and dual drift quantities.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence
import numpy as np

from sih26170.prognostics.schema import PrognosticInput, PrognosticForecast
from sih26170.prognostics.baselines import BasePrognosticModel, Z_90
from sih26170.prognostics.feature_extraction import extract_features_for_input, PrognosticFeatures
from sih26170.screening.transforms import (
    transform_parameter,
    inverse_transform_parameter,
    get_noise_floor,
)


def _extract_parameter_screening_evidence(screening_result: Any, param: str) -> Optional[Any]:
    """Safely extract parameter-specific screening result from upstream evidence."""
    if screening_result is None:
        return None
    if getattr(screening_result, "parameter", None) == param:
        return screening_result
    param_results = getattr(screening_result, "parameter_results", None)
    if isinstance(param_results, dict) and param in param_results:
        return param_results[param]
    return None


class AdaptiveDriftGatedModel(BasePrognosticModel):
    """Adaptive Drift-Gated (Soft-Thresholded) Extrapolation Model.

    Hypothesis: Degradation is sparse. Measured slopes within the measurement
    noise floor represent pure observation jitter and must be shrunk to zero
    (recovering Carry-Forward). Only statistically significant slopes are extrapolated.
    """

    def __init__(self, k_sigma: float = 2.0) -> None:
        super().__init__(model_id="STAGE2_ADAPTIVE_DRIFT_GATED")
        self.k_sigma = k_sigma

    def _compute_point_prediction(self, input_data: PrognosticInput) -> Optional[float]:
        forecast = self.predict_single(input_data)
        return float(forecast.predicted_value) if forecast.is_valid and np.isfinite(forecast.predicted_value) else None

    def predict_single(self, input_data: PrognosticInput) -> PrognosticForecast:
        # Check sufficiency: both input flag and upstream sufficiency detector
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

        param = input_data.parameter_name
        p_res = _extract_parameter_screening_evidence(input_data.screening_result, param)

        if p_res is not None:
            suff_ev = getattr(p_res, "sufficiency_evidence", None)
            if suff_ev is not None and not getattr(suff_ev, "sufficient", True):
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
                    exclusion_reason=getattr(suff_ev, "reason_code", "Upstream sufficiency failure"),
                )

        latest = input_data.get_latest_observation()
        baseline = input_data.get_baseline_observation()

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
                exclusion_reason="Missing required baseline or latest observation",
            )

        y_as_of = float(latest[1])
        y_0 = float(baseline[1])
        as_of = input_data.as_of_hours
        dt_lead = float(input_data.target_hours - as_of)
        dt_obs = max(float(as_of), 1.0)
        noise_floor = get_noise_floor(param)
        theta_slope = self.k_sigma * (np.sqrt(2.0) * noise_floor / dt_obs)

        try:
            feats = extract_features_for_input(input_data)
            u_as_of = feats.u_as_of
            raw_slope = feats.theil_sen_slope_u if feats.theil_sen_slope_u is not None else feats.raw_slope_u
        except Exception:
            u_as_of = transform_parameter(param, y_as_of)
            u_0 = transform_parameter(param, y_0)
            raw_slope = (u_as_of - u_0) / dt_obs

        # Extract upstream detector evidence if provided
        step_status = None
        eq_suspected = False
        temp_status = None
        g_excess = None
        screening_evidence: Dict[str, Any] = {}

        if p_res is not None:
            step_ev = getattr(p_res, "step_evidence", None)
            if step_ev is not None:
                step_status = getattr(step_ev.status, "value", str(step_ev.status))
                screening_evidence["step_status"] = step_status
                screening_evidence["step_magnitude"] = getattr(step_ev, "step_magnitude", None)
                screening_evidence["step_ratio"] = getattr(step_ev, "step_ratio", None)

            eq_ev = getattr(p_res, "equipment_evidence", None)
            if eq_ev is not None:
                eq_suspected = bool(getattr(eq_ev, "suspected", False))
                screening_evidence["equipment_status"] = getattr(eq_ev.status, "value", str(eq_ev.status))
                screening_evidence["equipment_suspected"] = eq_suspected

            temp_ev = getattr(p_res, "temporal_evidence", None)
            if temp_ev is not None:
                temp_status = getattr(temp_ev.status, "value", str(temp_ev.status))
                g_excess = getattr(temp_ev, "g_excess", None)
                screening_evidence["temporal_status"] = temp_status
                screening_evidence["g_excess"] = g_excess
                screening_evidence["slope_per_hour"] = getattr(temp_ev, "slope_per_hour", None)
                screening_evidence["normalized_drift"] = getattr(temp_ev, "normalized_drift", None)

            spec_ev = getattr(p_res, "spec_evidence", None)
            if spec_ev is not None:
                screening_evidence["spec_status"] = getattr(spec_ev.status, "value", str(spec_ev.status))

            suff_ev = getattr(p_res, "sufficiency_evidence", None)
            if suff_ev is not None:
                screening_evidence["sufficiency_status"] = getattr(suff_ev.status, "value", str(suff_ev.status))

        flags: List[str] = []
        step_candidate_status: Optional[str] = None
        equipment_confounded: bool = eq_suspected
        drift_status_flag: Optional[str] = None

        # Precedence Level 1: Abrupt Step Candidate
        if step_status == "ABRUPT_JUMP_ALERT":
            shrunk_slope = 0.0
            u_pred = u_as_of
            step_candidate_status = "STEP_CANDIDATE_UNVERIFIED_PERSISTENCE"
            flags.append("STEP_CANDIDATE_UNVERIFIED_PERSISTENCE")
            if eq_suspected:
                flags.append("EQUIPMENT_CONFOUNDED")

        # Precedence Level 2: Equipment Confounded
        elif eq_suspected:
            flags.append("EQUIPMENT_CONFOUNDED")
            # Check excess motion: |g_excess| >= 2.5
            has_excess_motion = (g_excess is not None and abs(g_excess) >= 2.5)
            if has_excess_motion:
                flags.append("CANDIDATE_EXCESS_DRIFT_CONFOUNDED")
                # Retain regularized excess slope candidate
                abs_slope = abs(raw_slope)
                if abs_slope <= theta_slope:
                    shrunk_slope = 0.0
                else:
                    shrunk_slope = np.sign(raw_slope) * (abs_slope - theta_slope)
                u_pred = u_as_of + shrunk_slope * dt_lead
            else:
                flags.append("NO_SIGNIFICANT_EXCESS_MOTION_DETECTED")
                shrunk_slope = 0.0
                u_pred = u_as_of

        # Precedence Level 3: Autonomous Drift or Stationary
        else:
            is_explicitly_stationary = (temp_status == "STATIONARY")
            if is_explicitly_stationary:
                shrunk_slope = 0.0
                drift_status_flag = "STATIONARY_NOISE_BOUNDED"
                flags.append("STATIONARY_NOISE_BOUNDED")
                u_pred = u_as_of
            else:
                abs_slope = abs(raw_slope)
                if abs_slope <= theta_slope:
                    shrunk_slope = 0.0
                    drift_status_flag = "STATIONARY_NOISE_BOUNDED"
                    flags.append("STATIONARY_NOISE_BOUNDED")
                else:
                    shrunk_slope = np.sign(raw_slope) * (abs_slope - theta_slope)
                    drift_status_flag = "ACTIVE_DRIFT_EXTRAPOLATED"
                    flags.append("ACTIVE_DRIFT_EXTRAPOLATED")
                u_pred = u_as_of + shrunk_slope * dt_lead

        # Record raw unconstrained coordinate forecast
        raw_unconstrained_u_pred = float(u_pred)

        # Safe inverse transform evaluation (catching overflow and non-finite)
        is_divergent_fallback = False
        try:
            y_pred = float(inverse_transform_parameter(param, u_pred))
            if not np.isfinite(y_pred):
                raise FloatingPointError(f"Non-finite inverse transform for {param}: {y_pred}")
        except (OverflowError, FloatingPointError, Exception):
            # Deterministic software error-handling policy
            y_pred = y_as_of
            is_divergent_fallback = True
            flags.append("DIVERGENT_RUNAWAY_PREDICTION")

        # Predicted Specification Breach Evaluation (Do NOT clip prediction!)
        predicted_spec_breach: Optional[str] = None
        if param == "IGSS":
            if y_pred > 100.0:
                predicted_spec_breach = "PREDICTED_SPEC_BREACH_POSITIVE"
                flags.append("PREDICTED_SPEC_BREACH_POSITIVE")
            elif y_pred < -100.0:
                predicted_spec_breach = "PREDICTED_SPEC_BREACH_NEGATIVE"
                flags.append("PREDICTED_SPEC_BREACH_NEGATIVE")
        elif param == "IDSS":
            if y_pred > 10.0:
                predicted_spec_breach = "PREDICTED_SPEC_BREACH_POSITIVE"
                flags.append("PREDICTED_SPEC_BREACH_POSITIVE")
        elif param == "RDS(on)":
            if y_pred > 65.0:
                predicted_spec_breach = "PREDICTED_SPEC_BREACH_POSITIVE"
                flags.append("PREDICTED_SPEC_BREACH_POSITIVE")
        elif param == "VGS(th)":
            if y_pred < 2.0:
                predicted_spec_breach = "PREDICTED_SPEC_BREACH_NEGATIVE"
                flags.append("PREDICTED_SPEC_BREACH_NEGATIVE")
            elif y_pred > 4.0:
                predicted_spec_breach = "PREDICTED_SPEC_BREACH_POSITIVE"
                flags.append("PREDICTED_SPEC_BREACH_POSITIVE")

        # Drift quantities
        forecast_change_from_origin = y_pred - y_as_of
        baseline_relative_forecast_change = y_pred - y_0

        # Uncertainty intervals (preserving empirical sigma_eff)
        sigma_eff_u = self._sigma_eff_u.get(param)
        interval_lower: Optional[float] = None
        interval_upper: Optional[float] = None

        if sigma_eff_u is not None:
            try:
                u_pred_center = transform_parameter(param, y_pred)
                multiplier = np.sqrt(2.0) if equipment_confounded else 1.0
                u_low = u_pred_center - Z_90 * (sigma_eff_u * multiplier)
                u_high = u_pred_center + Z_90 * (sigma_eff_u * multiplier)
                interval_lower = inverse_transform_parameter(param, u_low)
                interval_upper = inverse_transform_parameter(param, u_high)
            except Exception:
                interval_lower = None
                interval_upper = None

        metadata: Dict[str, Any] = {
            "k_sigma": self.k_sigma,
            "shrunk_slope": shrunk_slope,
            "raw_slope": raw_slope,
            "theta_slope": theta_slope,
            "flags": flags,
            "step_candidate_status": step_candidate_status,
            "equipment_confounded": equipment_confounded,
            "drift_status": drift_status_flag,
            "predicted_spec_breach": predicted_spec_breach,
            "is_divergent_fallback": is_divergent_fallback,
            "raw_unconstrained_u_pred": raw_unconstrained_u_pred,
            "audit_hash": input_data.audit_hash,
        }
        if screening_evidence:
            metadata["screening_evidence"] = screening_evidence

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
            step_candidate_status=step_candidate_status,
            equipment_confounded=equipment_confounded,
            drift_status=drift_status_flag,
            predicted_spec_breach=predicted_spec_breach,
            is_divergent_fallback=is_divergent_fallback,
            raw_unconstrained_u_pred=raw_unconstrained_u_pred,
            metadata=metadata,
        )


class HierarchicalLotShrunkModel(BasePrognosticModel):
    """Hierarchical Empirical Bayes Lot-Shrunk Extrapolation Model.

    Hypothesis: Devices from the same wafer/diffusion lot share physical baseline
    drift behavior. Individual slopes are shrunk toward the contemporaneous lot
    median, preventing isolated measurement noise from dominating predictions.
    """

    def __init__(self) -> None:
        super().__init__(model_id="STAGE2_HIERARCHICAL_LOT_SHRUNK")
        self._lot_inputs_cache: Dict[str, List[PrognosticInput]] = {}

    def set_contemporaneous_lot_inputs(self, lot_inputs: Sequence[PrognosticInput]) -> None:
        """Register contemporaneous lot inputs strictly at as_of_hours."""
        self._lot_inputs_cache.clear()
        for inp in lot_inputs:
            lid = inp.lot_id
            if lid not in self._lot_inputs_cache:
                self._lot_inputs_cache[lid] = []
            self._lot_inputs_cache[lid].append(inp)

    def _compute_point_prediction(self, input_data: PrognosticInput) -> Optional[float]:
        lot_peers = self._lot_inputs_cache.get(input_data.lot_id, [input_data])
        try:
            feats = extract_features_for_input(input_data, contemporaneous_lot_inputs=lot_peers)
        except Exception:
            latest = input_data.get_latest_observation()
            return float(latest[1]) if latest else None

        param = input_data.parameter_name
        as_of = input_data.as_of_hours
        dt_lead = float(input_data.target_hours - as_of)
        noise_floor = get_noise_floor(param)

        raw_slope = feats.theil_sen_slope_u if feats.theil_sen_slope_u is not None else feats.raw_slope_u
        mu_lot = feats.lot_median_slope_u
        tau_lot = feats.lot_mad_slope_u

        # Measurement noise variance for the slope
        dt_obs = max(float(as_of), 1.0)
        var_noise = (2.0 * (noise_floor ** 2)) / (dt_obs ** 2)

        # Empirical Bayes shrinkage factor
        signal_var = tau_lot ** 2 + (raw_slope - mu_lot) ** 2
        denom = signal_var + var_noise
        lambda_shrink = signal_var / denom if denom > 0 else 0.0

        # Shrunk slope
        shrunk_slope = mu_lot + lambda_shrink * (raw_slope - mu_lot)

        # If contemporaneous lot median itself is indistinguishable from zero noise, clamp
        if abs(mu_lot) < (noise_floor / dt_obs) and abs(raw_slope - mu_lot) < (noise_floor / dt_obs):
            shrunk_slope = 0.0

        u_pred = feats.u_as_of + shrunk_slope * dt_lead
        try:
            return float(inverse_transform_parameter(param, u_pred))
        except Exception:
            return float(input_data.get_latest_observation()[1])

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
                exclusion_reason="Missing required baseline or latest observation",
            )

        y_as_of = float(latest[1])
        y_0 = float(baseline[1])
        param = input_data.parameter_name

        y_pred = self._compute_point_prediction(input_data)
        if y_pred is None or not np.isfinite(y_pred):
            y_pred = y_as_of

        forecast_change_from_origin = y_pred - y_as_of
        baseline_relative_forecast_change = y_pred - y_0

        sigma_eff_u = self._sigma_eff_u.get(param)
        interval_lower: Optional[float] = None
        interval_upper: Optional[float] = None

        if sigma_eff_u is not None:
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
            is_valid=True,
            metadata={"audit_hash": input_data.audit_hash},
        )
