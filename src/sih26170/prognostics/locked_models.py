"""Pre-calibrated, locked Phase 5 Ridge regression models for Module B.

Complies strictly with post-Phase-5 engineering integration specifications:
- Exact IEEE-754 lineage provenance verified against phase5_final_lineage_manifest.json.
- Zero retraining, refitting, optimization, or artifact regeneration permitted.
- Parameter coordinate representations:
    * IDSS: positive log-domain u = ln(y)
    * RDS(on): positive log-domain u = ln(y)
    * VGS(th): linear representation u = y
    * IGSS: signed asinh u = asinh(y / 1.0 nA), NEVER abs(), NEVER clipped
- Divergence guard: |u| > 10.0 is a LOCKED PHASE-5 NUMERICAL POLICY.
    * On divergence/non-finite: preserves raw unconstrained transformed prediction,
      sets is_divergent_fallback=True, falls back deterministically to Carry-Forward (v24).
      Does NOT clip the prediction.
- 90% prediction intervals constructed using frozen sigma_eff and Z_90 = 1.6448536269514722.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from sih26170.prognostics.schema import PrognosticForecast, PrognosticInput
from sih26170.screening.transforms import (
    get_noise_floor,
    inverse_transform_parameter,
    transform_parameter,
)

Z_90: float = 1.6448536269514722
DIVERGENCE_THRESHOLD_U: float = 10.0  # LOCKED PHASE-5 NUMERICAL POLICY

# Exact parsed IEEE-754 hex float representations from phase5_final_lineage_manifest.json
LOCKED_COEFFICIENTS_HEX: Dict[str, List[str]] = {
    "IDSS": [
        "0x1.32a6a466c178dp-9",
        "0x1.dce1775cfbae1p-2",
        "0x1.f7a0c97093a41p-2",
    ],
    "VGS(th)": [
        "0x1.a038382826d76p-4",
        "0x1.e0d38e0e4fa4fp-2",
        "0x1.fc1c58453983dp-2",
    ],
    "RDS(on)": [
        "0x1.c5f098eb8f3dbp-3",
        "0x1.e3719a785e27ep-2",
        "0x1.e2e5cba69ffbdp-2",
    ],
    "IGSS": [
        "0x1.4d90bd29279aep-2",
        "0x1.938846f479f57p-2",
        "0x1.86c7c338aea03p-2",
    ],
}

FROZEN_SIGMA_EFF_HEX: Dict[str, str] = {
    "IDSS": "0x1.b92cc184ed97fp-4",
    "VGS(th)": "0x1.f36b94aeadf72p-6",
    "RDS(on)": "0x1.2ef26452b8545p-6",
    "IGSS": "0x1.4172d6c90fda4p-2",
}

CANONICAL_UNITS: Dict[str, str] = {
    "IDSS": "uA",
    "VGS(th)": "V",
    "RDS(on)": "mOhm",
    "IGSS": "nA",
}

POPULATION_BASELINE_U: Dict[str, float] = {
    "IDSS": -2.302585092994046,       # ln(0.1 uA)
    "VGS(th)": 3.0,                   # 3.0 V
    "RDS(on)": 3.8066624897703196,     # ln(45.0 mOhm)
    "IGSS": 0.0,                      # asinh(0.0)
}


def _verify_manifest_lineage(manifest_path: Optional[Path] = None) -> None:
    """Verify that hardcoded IEEE-754 representations match the manifest bit-for-bit."""
    if manifest_path is None:
        manifest_path = Path(__file__).resolve().parents[3] / "data/evaluation_phase5/phase5_final_lineage_manifest.json"

    if not manifest_path.exists():
        # If running in environment without repo root structure, skip file-level check
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for rec in manifest.get("records", []):
        param = rec["parameter_name"]
        if param not in LOCKED_COEFFICIENTS_HEX:
            continue

        manifest_coeffs = [float(c) for c in rec["coefficients"]]
        expected_coeffs = [float.fromhex(h) for h in LOCKED_COEFFICIENTS_HEX[param]]
        for i, (mc, ec) in enumerate(zip(manifest_coeffs, expected_coeffs)):
            if mc.hex() != ec.hex():
                raise RuntimeError(
                    f"LINEAGE INTEGRITY VIOLATION for {param} coeff[{i}]: "
                    f"manifest={mc.hex()} != expected={ec.hex()}"
                )

        manifest_sigma = float(rec["sigma_eff"])
        expected_sigma = float.fromhex(FROZEN_SIGMA_EFF_HEX[param])
        if manifest_sigma.hex() != expected_sigma.hex():
            raise RuntimeError(
                f"LINEAGE INTEGRITY VIOLATION for {param} sigma_eff: "
                f"manifest={manifest_sigma.hex()} != expected={expected_sigma.hex()}"
            )


# Execute strict lineage verification at import time
_verify_manifest_lineage()


class LockedRidgeModel:
    """Pre-calibrated, immutable Ridge model for a single physical parameter."""

    def __init__(self, parameter_name: str) -> None:
        if parameter_name not in LOCKED_COEFFICIENTS_HEX:
            raise KeyError(
                f"Unknown parameter '{parameter_name}'. Expected one of {list(LOCKED_COEFFICIENTS_HEX.keys())}"
            )
        self.parameter_name = parameter_name
        self.unit = CANONICAL_UNITS[parameter_name]
        self.coefficients = [float.fromhex(h) for h in LOCKED_COEFFICIENTS_HEX[parameter_name]]
        self.sigma_eff = float.fromhex(FROZEN_SIGMA_EFF_HEX[parameter_name])
        self.model_id = f"REG_RIDGE_{parameter_name}"
        self.model_family = "RIDGE"
        self.l2_reg = 1.0

    def predict_transformed(self, v0: float, v24: float) -> Tuple[float, float, bool]:
        """Compute prediction in transformed coordinate space.

        Returns:
            Tuple of (effective_u, raw_u, is_divergent)
        """
        u0 = transform_parameter(self.parameter_name, v0)
        u24 = transform_parameter(self.parameter_name, v24)

        raw_u = self.coefficients[0] + self.coefficients[1] * u0 + self.coefficients[2] * u24

        # Divergence guard: |u| > 10.0 is a LOCKED PHASE-5 NUMERICAL POLICY
        if not np.isfinite(raw_u) or abs(raw_u) > DIVERGENCE_THRESHOLD_U:
            return u24, raw_u, True

        return raw_u, raw_u, False

    def predict_physical(
        self, v0: float, v24: float
    ) -> Tuple[float, float, float, bool, Optional[float]]:
        """Compute point forecast and 90% prediction interval in physical engineering units.

        Returns:
            Tuple of (predicted_value, interval_lower, interval_upper, is_divergent, raw_unconstrained_u)
        """
        try:
            eff_u, raw_u, is_divergent = self.predict_transformed(v0, v24)
        except (ValueError, OverflowError):
            # Transformation domain violation (e.g. non-positive IDSS/RDS)
            fallback_val = float(v24)
            return fallback_val, fallback_val, fallback_val, True, None

        if is_divergent:
            # Deterministic fallback to Carry-Forward (v24) under Phase-5 policy
            fallback_val = float(v24)
            return fallback_val, fallback_val, fallback_val, True, raw_u

        try:
            pred_y = inverse_transform_parameter(self.parameter_name, eff_u)
            u_low = eff_u - Z_90 * self.sigma_eff
            u_upp = eff_u + Z_90 * self.sigma_eff
            y_l_raw = inverse_transform_parameter(self.parameter_name, u_low)
            y_u_raw = inverse_transform_parameter(self.parameter_name, u_upp)

            y_low = min(y_l_raw, y_u_raw)
            y_upp = max(y_l_raw, y_u_raw)

            if not (np.isfinite(pred_y) and np.isfinite(y_low) and np.isfinite(y_upp)):
                fallback_val = float(v24)
                return fallback_val, fallback_val, fallback_val, True, raw_u

            return float(pred_y), float(y_low), float(y_upp), False, raw_u
        except (ValueError, OverflowError):
            fallback_val = float(v24)
            return fallback_val, fallback_val, fallback_val, True, raw_u

    def forecast_single(
        self,
        v0: float,
        v24: float,
        component_id: str,
        lot_id: str,
        as_of_hours: int = 24,
        target_hours: int = 168,
        screening_result: Optional[Any] = None,
    ) -> PrognosticForecast:
        """Generate a complete PrognosticForecast contract for a single parameter."""
        pred_y, y_low, y_upp, is_div, raw_u = self.predict_physical(v0, v24)

        forecast_change_from_origin = pred_y - v24
        baseline_relative_forecast_change = pred_y - v0

        # Extract Module A evidence if available
        drift_status = None
        eq_confounded = False
        step_cand = None
        if screening_result is not None:
            p_res = getattr(screening_result, "parameter_results", {}).get(self.parameter_name)
            if p_res is not None:
                drift_status = getattr(p_res.temporal_evidence.status, "value", None)
                eq_confounded = bool(getattr(p_res.temporal_evidence, "confounded_by_equipment", False))
                step_cand = getattr(p_res.step_evidence.status, "value", None)

        metadata = {
            "v0": float(v0),
            "v24": float(v24),
            "coefficients": list(self.coefficients),
            "l2_reg": self.l2_reg,
            "divergence_threshold_u": DIVERGENCE_THRESHOLD_U,
            "divergence_policy": "LOCKED_PHASE_5_NUMERICAL_POLICY",
        }

        # Compute exact closed-form Ridge SHAP attributions
        shap_res = self.compute_shap_attributions(v0, v24)
        metadata["shap"] = shap_res
        metadata["shap_attributions"] = shap_res["shap_values"]
        metadata["primary_driver"] = shap_res["primary_driver"]
        metadata["shap_explanation"] = shap_res["explanation"]

        return PrognosticForecast(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=self.parameter_name,
            unit=self.unit,
            as_of_hours=as_of_hours,
            target_hours=target_hours,
            predicted_value=float(pred_y),
            forecast_change_from_origin=float(forecast_change_from_origin),
            baseline_relative_forecast_change=float(baseline_relative_forecast_change),
            interval_lower=float(y_low),
            interval_upper=float(y_upp),
            interval_coverage=0.90,
            sigma_eff=float(self.sigma_eff),
            model_id=self.model_id,
            is_valid=True,
            step_candidate_status=step_cand,
            equipment_confounded=eq_confounded,
            drift_status=drift_status,
            is_divergent_fallback=is_div,
            raw_unconstrained_u_pred=float(raw_u) if raw_u is not None else None,
            shap_attributions=shap_res["shap_values"],
            primary_driver=shap_res["primary_driver"],
            metadata=metadata,
        )

    def compute_shap_attributions(self, v0: float, v24: float) -> Dict[str, Any]:
        """Compute exact linear Shapley attributions for Ridge forecast.

        For a linear model y_hat = beta_0 + beta_1 * u0 + beta_2 * u24,
        Shapley values with respect to background reference u_bar are exact:
            phi_u0 = beta_1 * (u0 - u_bar)
            phi_u24 = beta_2 * (u24 - u_bar)
            phi_0 = beta_0 + (beta_1 + beta_2) * u_bar

        Decomposing into physical engineering features:
            Initial Baseline Level (u0) and Burn-In Drift (u24 - u0):
            phi_drift_slope = beta_2 * (u24 - u0)
            phi_baseline_offset = (beta_1 + beta_2) * (u0 - u_bar)

        Guarantees exact efficiency / additivity:
            phi_0 + phi_baseline_offset + phi_drift_slope == u_hat
        """
        try:
            u0 = transform_parameter(self.parameter_name, v0)
            u24 = transform_parameter(self.parameter_name, v24)
        except (ValueError, OverflowError):
            return {
                "base_value_u": 0.0,
                "shap_values": {"slope_0_24": 0.0, "baseline_0h": 0.0, "u0": 0.0, "u24": 0.0},
                "feature_values": {"slope_0_24": 0.0, "delta_0_24": 0.0, "u0": 0.0, "u24": 0.0},
                "primary_driver": "baseline_0h",
                "explanation": "Transformation domain violation; SHAP attributions undefined.",
            }

        b0, b1, b2 = self.coefficients
        u_bar = POPULATION_BASELINE_U.get(self.parameter_name, 0.0)

        # Base value E[u] under population null
        phi_0 = b0 + (b1 + b2) * u_bar

        # Physical feature decomposition
        delta_u = u24 - u0
        phi_drift_slope = b2 * delta_u
        phi_baseline_offset = (b1 + b2) * (u0 - u_bar)

        # Raw feature attributions
        phi_u0 = b1 * (u0 - u_bar)
        phi_u24 = b2 * (u24 - u_bar)

        abs_drift = abs(phi_drift_slope)
        abs_base = abs(phi_baseline_offset)
        total_mag = abs_drift + abs_base + 1e-9

        if abs_drift >= abs_base:
            primary_driver = "slope_0_24"
            pct = (abs_drift / total_mag) * 100.0
            sign_str = "+" if phi_drift_slope >= 0 else ""
            explanation = (
                f"slope_0_24 was the primary driver "
                f"({sign_str}{phi_drift_slope:.4f} transformed attribution, {pct:.1f}% of total predicted shift)"
            )
        else:
            primary_driver = "baseline_0h"
            pct = (abs_base / total_mag) * 100.0
            sign_str = "+" if phi_baseline_offset >= 0 else ""
            explanation = (
                f"baseline_0h was the primary driver "
                f"({sign_str}{phi_baseline_offset:.4f} transformed attribution, {pct:.1f}% of total predicted shift)"
            )

        return {
            "base_value_u": float(phi_0),
            "shap_values": {
                "slope_0_24": float(phi_drift_slope),
                "baseline_0h": float(phi_baseline_offset),
                "u0": float(phi_u0),
                "u24": float(phi_u24),
            },
            "feature_values": {
                "slope_0_24": float(delta_u / 24.0),
                "delta_0_24": float(delta_u),
                "u0": float(u0),
                "u24": float(u24),
            },
            "primary_driver": primary_driver,
            "explanation": explanation,
        }


_MODEL_CACHE: Dict[str, LockedRidgeModel] = {}


def get_locked_ridge_model(parameter_name: str) -> LockedRidgeModel:
    """Retrieve pre-calibrated, locked Ridge model instance for parameter."""
    if parameter_name not in _MODEL_CACHE:
        _MODEL_CACHE[parameter_name] = LockedRidgeModel(parameter_name)
    return _MODEL_CACHE[parameter_name]
