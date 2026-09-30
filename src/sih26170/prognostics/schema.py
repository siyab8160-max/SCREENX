"""Data contracts and schemas for Module B Prognostics.

Defines:
- PrognosticInput: Minimal strictly-as-of input contract
- PrognosticForecast: Fully scoped prognostic forecast contract with dual drift quantities
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence, Tuple
import hashlib
import numpy as np


@dataclass(frozen=True)
class PrognosticInput:
    """Minimal strictly-as-of input contract for Module B prognostics.

    Guarantees:
    - Complete lineage: component_id, lot_id, parameter_name, unit.
    - Strict temporal causality: elapsed_hours <= as_of_hours < target_hours.
    - Quarantine: No ground truth labels, scenario tags, or future telemetry.
    """
    component_id: str
    lot_id: str
    parameter_name: str
    unit: str
    as_of_hours: int
    target_hours: int
    # Chronologically ordered sequence of (elapsed_hours, physical_value)
    historical_observations: Tuple[Tuple[int, float], ...]
    screening_result: Optional[Any] = None
    data_sufficiency_passed: bool = True
    insufficient_reason: Optional[str] = None
    audit_hash: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("component_id cannot be empty")
        if not self.lot_id:
            raise ValueError("lot_id cannot be empty")
        if not self.parameter_name:
            raise ValueError("parameter_name cannot be empty")
        if not self.unit:
            raise ValueError("unit cannot be empty")
        if self.as_of_hours >= self.target_hours:
            raise ValueError(
                f"as_of_hours ({self.as_of_hours}) must be strictly less than target_hours ({self.target_hours})"
            )

        # Enforce chronological ordering and strict as-of boundary on observations
        prev_t = -1
        for obs in self.historical_observations:
            t, v = obs[0], obs[1]
            if t < 0:
                raise ValueError(f"Observation elapsed_hours ({t}) cannot be negative")
            if t > self.as_of_hours:
                raise ValueError(
                    f"Temporal leakage: observation at {t}h exceeds as_of_hours ({self.as_of_hours}h)"
                )
            if t < prev_t:
                raise ValueError(
                    f"Observations must be chronologically ordered: got {t}h after {prev_t}h"
                )
            if not np.isfinite(v):
                raise ValueError(f"Observation at {t}h has non-finite value: {v}")
            prev_t = t

        # Verify screening result as-of boundary if provided
        if self.screening_result is not None:
            res_as_of = getattr(self.screening_result, "as_of_hours", None)
            if res_as_of is not None and res_as_of > self.as_of_hours:
                raise ValueError(
                    f"Temporal leakage: screening_result as_of_hours ({res_as_of}) exceeds input as_of_hours ({self.as_of_hours})"
                )

    def get_latest_observation(self) -> Optional[Tuple[int, float]]:
        """Return the observation at or immediately prior to as_of_hours."""
        if not self.historical_observations:
            return None
        return self.historical_observations[-1]

    def get_baseline_observation(self) -> Optional[Tuple[int, float]]:
        """Return the baseline observation at 0h."""
        for t, v in self.historical_observations:
            if t == 0:
                return (t, v)
        return None

    def compute_sha256(self) -> str:
        """Compute cryptographic hash of the input lineage and observations."""
        payload = f"{self.component_id}:{self.lot_id}:{self.parameter_name}:{self.unit}:{self.as_of_hours}:{self.target_hours}"
        obs_str = ";".join(f"{t}:{v:.6g}" for t, v in self.historical_observations)
        raw = f"{payload}|{obs_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PrognosticForecast:
    """Fully scoped prognostic forecast contract produced by Module B.

    Enforces:
    - Strict parameter/unit/component/lot/as-of/target lineage.
    - Explicit dual drift quantities (neither hard-coded nor silently prioritized):
      A. forecast_change_from_origin: predicted_value(target) - observed_value(as_of)
      B. baseline_relative_forecast_change: predicted_value(target) - observed_value(0h)
    - Uncertainty bounds: interval_lower <= interval_upper.
    - Data sufficiency & validity tracking.
    """
    component_id: str
    lot_id: str
    parameter_name: str
    unit: str
    as_of_hours: int
    target_hours: int
    predicted_value: float
    forecast_change_from_origin: float
    baseline_relative_forecast_change: float
    interval_lower: Optional[float] = None
    interval_upper: Optional[float] = None
    interval_coverage: float = 0.90
    sigma_eff: Optional[float] = None
    model_id: str = ""
    is_valid: bool = True
    exclusion_reason: Optional[str] = None
    # Stage 3 enriched prognostics metadata fields
    step_candidate_status: Optional[str] = None
    equipment_confounded: bool = False
    drift_status: Optional[str] = None
    predicted_spec_breach: Optional[str] = None
    is_divergent_fallback: bool = False
    raw_unconstrained_u_pred: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.component_id:
            raise ValueError("component_id cannot be empty")
        if not self.lot_id:
            raise ValueError("lot_id cannot be empty")
        if not self.parameter_name:
            raise ValueError("parameter_name cannot be empty")
        if not self.unit:
            raise ValueError("unit cannot be empty")
        if self.as_of_hours >= self.target_hours:
            raise ValueError(
                f"as_of_hours ({self.as_of_hours}) must be strictly less than target_hours ({self.target_hours})"
            )

        if self.is_valid:
            if not np.isfinite(self.predicted_value):
                raise ValueError(f"predicted_value must be finite, got {self.predicted_value}")
            if not np.isfinite(self.forecast_change_from_origin):
                raise ValueError(
                    f"forecast_change_from_origin must be finite, got {self.forecast_change_from_origin}"
                )
            if not np.isfinite(self.baseline_relative_forecast_change):
                raise ValueError(
                    f"baseline_relative_forecast_change must be finite, got {self.baseline_relative_forecast_change}"
                )

        # Uncertainty contract validation
        if self.interval_lower is not None and self.interval_upper is not None:
            if not np.isfinite(self.interval_lower) or not np.isfinite(self.interval_upper):
                raise ValueError(
                    f"Interval bounds must be finite: lower={self.interval_lower}, upper={self.interval_upper}"
                )
            if self.interval_lower > self.interval_upper:
                raise ValueError(
                    f"Prediction interval lower bound ({self.interval_lower}) exceeds upper bound ({self.interval_upper})"
                )
        elif self.interval_lower is not None or self.interval_upper is not None:
            raise ValueError("Both interval_lower and interval_upper must be provided, or both None")

    @property
    def interval_width(self) -> Optional[float]:
        """Return width of prediction interval if defined."""
        if self.interval_lower is not None and self.interval_upper is not None:
            return float(self.interval_upper - self.interval_lower)
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize forecast contract to dictionary."""
        return {
            "component_id": self.component_id,
            "lot_id": self.lot_id,
            "parameter_name": self.parameter_name,
            "unit": self.unit,
            "as_of_hours": self.as_of_hours,
            "target_hours": self.target_hours,
            "predicted_value": self.predicted_value,
            "forecast_change_from_origin": self.forecast_change_from_origin,
            "baseline_relative_forecast_change": self.baseline_relative_forecast_change,
            "interval_lower": self.interval_lower,
            "interval_upper": self.interval_upper,
            "interval_coverage": self.interval_coverage,
            "sigma_eff": self.sigma_eff,
            "model_id": self.model_id,
            "is_valid": self.is_valid,
            "exclusion_reason": self.exclusion_reason,
            "step_candidate_status": self.step_candidate_status,
            "equipment_confounded": self.equipment_confounded,
            "drift_status": self.drift_status,
            "predicted_spec_breach": self.predicted_spec_breach,
            "is_divergent_fallback": self.is_divergent_fallback,
            "raw_unconstrained_u_pred": self.raw_unconstrained_u_pred,
            "metadata": dict(self.metadata),
        }
