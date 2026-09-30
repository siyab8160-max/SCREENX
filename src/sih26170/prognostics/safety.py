"""Module B — Safety-Slope / Early-Rejection Decision Layer for SIH26170.

Implements the official Problem Statement requirement:
    "If the predicted 168h drift rate exceeds a calculated safety slope,
     the system flags the component for early rejection."

Decision Rule & Mathematical Formulation:
    predicted_drift_rate = (predicted_value_168h - value_24h) / 144  [units/hour]
    safety_slope         = (safety_threshold   - value_24h) / 144  [units/hour]

ALGEBRAIC EQUIVALENCE NOTE:
    Because both predicted drift rate and safety slope share the identical 144-hour denominator:
        predicted_drift_rate > safety_slope
        <=> (predicted_value_168h - value_24h) / 144 > (safety_threshold - value_24h) / 144
        <=> predicted_value_168h > safety_threshold (for upper-limit parameters)
    The comparison is algebraically equivalent to checking whether predicted Value_168h
    crosses the configured safety threshold. This is a deterministic engineering decision
    rule based on the shared 144h horizon. It is NOT an independently learned slope model.

Dispositions:
    - EARLY_REJECT: Predicted drift rate exceeds safety slope (or crosses safety threshold)
    - CONTINUE: Predicted drift rate remains within safety slope boundaries
    - INSUFFICIENT_DATA: Missing intermediate observations; cannot extrapolate safely
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import yaml

from sih26170.prognostics.schema import PrognosticForecast


# ============================================================
# Leakage Guard — Block future/ground-truth columns
# ============================================================

FORBIDDEN_SAFETY_COLUMNS = frozenset([
    "value_96h", "value_168h", "actual_value", "ground_truth",
    "scenario_label", "event_hour", "future_equipment_state",
    "drift_multiplier", "acceleration_exponent", "abrupt_event_hour",
    "equipment_shift_mult", "abrupt_magnitude_mult",
])


def assert_no_safety_leakage(column_names: Sequence[str]) -> None:
    """Structurally assert that no forbidden future/ground-truth columns are present."""
    for col in column_names:
        col_lower = col.strip().lower()
        if col_lower.startswith("predicted_") or col_lower.startswith("forecast_"):
            continue
        for forbidden in FORBIDDEN_SAFETY_COLUMNS:
            if forbidden in col_lower:
                raise ValueError(
                    f"Safety decision leakage violation! Column '{col}' matches "
                    f"forbidden pattern '{forbidden}'. The safety layer must not "
                    f"consume future or ground-truth information."
                )


# ============================================================
# Enumerations
# ============================================================

class SafetyDecision(str, Enum):
    """Safety-layer decision disposition."""
    CONTINUE = "CONTINUE"
    EARLY_REJECT = "EARLY_REJECT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class IntervalSafetyStatus(str, Enum):
    """Prediction interval position relative to safety boundary."""
    WITHIN_BOUNDARY = "WITHIN_BOUNDARY"
    BOUNDARY_CROSSED = "BOUNDARY_CROSSED"
    BEYOND_BOUNDARY = "BEYOND_BOUNDARY"
    NO_INTERVAL = "NO_INTERVAL"


class SafetyDirection(str, Enum):
    """Safety threshold directionality."""
    UPPER = "upper"
    LOWER = "lower"
    TWO_SIDED = "two_sided"


# ============================================================
# Data Contracts
# ============================================================

@dataclass(frozen=True)
class ParameterSafetyThreshold:
    """Safety threshold configuration for a single electrical parameter."""
    parameter_name: str
    safety_threshold_high: Optional[float]
    safety_threshold_low: Optional[float]
    direction: SafetyDirection
    unit: str
    source: str

    def __post_init__(self) -> None:
        if self.direction == SafetyDirection.UPPER and self.safety_threshold_high is None:
            raise ValueError(f"Upper-direction parameter '{self.parameter_name}' requires safety_threshold_high")
        if self.direction == SafetyDirection.LOWER and self.safety_threshold_low is None:
            raise ValueError(f"Lower-direction parameter '{self.parameter_name}' requires safety_threshold_low")
        if self.direction == SafetyDirection.TWO_SIDED:
            if self.safety_threshold_high is None or self.safety_threshold_low is None:
                raise ValueError(
                    f"Two-sided parameter '{self.parameter_name}' requires both "
                    f"safety_threshold_high and safety_threshold_low"
                )
            if self.safety_threshold_low >= self.safety_threshold_high:
                raise ValueError(
                    f"Two-sided parameter '{self.parameter_name}': safety_threshold_low "
                    f"({self.safety_threshold_low}) must be < safety_threshold_high ({self.safety_threshold_high})"
                )


@dataclass(frozen=True)
class SafetyDecisionResult:
    """Structured output of the safety-slope / early-rejection decision layer.

    Every decision includes human-readable arithmetic explanation.
    """
    component_id: str
    parameter_name: str
    unit: str
    value_24h: float
    predicted_value_168h: float
    predicted_total_drift: float
    predicted_drift_rate: float
    safety_threshold: float
    safety_slope: float
    direction: str
    evaluated_direction: str
    margin_to_safety_threshold: float
    decision: SafetyDecision
    interval_status: IntervalSafetyStatus
    reason: str
    model_id: str = ""
    upstream_disposition: str = "PREDICTED"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value
        d["interval_status"] = self.interval_status.value
        return d


@dataclass
class SafetyConfig:
    """Safety-slope configuration loaded from YAML."""
    thresholds: Dict[str, ParameterSafetyThreshold]
    formula_source: str
    formula_notice: str
    as_of_hours: int
    target_horizon_hours: int
    horizon_delta_hours: int
    boundary_comparison: str

    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> SafetyConfig:
        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        thresholds: Dict[str, ParameterSafetyThreshold] = {}
        for p_name, p_cfg in raw.get("safety_thresholds", {}).items():
            thresholds[p_name] = ParameterSafetyThreshold(
                parameter_name=p_name,
                safety_threshold_high=p_cfg.get("safety_threshold_high"),
                safety_threshold_low=p_cfg.get("safety_threshold_low"),
                direction=SafetyDirection(p_cfg["direction"]),
                unit=p_cfg.get("unit", ""),
                source=p_cfg.get("source", "unspecified"),
            )

        return cls(
            thresholds=thresholds,
            formula_source=raw.get("formula_source", "configurable_engineering_decision_rule"),
            formula_notice=raw.get("formula_notice", ""),
            as_of_hours=int(raw.get("as_of_hours", 24)),
            target_horizon_hours=int(raw.get("target_horizon_hours", 168)),
            horizon_delta_hours=int(raw.get("forecast_horizon_delta_hours", 144)),
            boundary_comparison=raw.get("boundary_comparison", "strict_inequality"),
        )

    @classmethod
    def default(cls) -> SafetyConfig:
        thresholds = {
            "IDSS": ParameterSafetyThreshold(
                parameter_name="IDSS",
                safety_threshold_high=10.0,
                safety_threshold_low=None,
                direction=SafetyDirection.UPPER,
                unit="uA",
                source="MIL-PRF-19500/703 Table I spec_limit_high",
            ),
            "VGS(th)": ParameterSafetyThreshold(
                parameter_name="VGS(th)",
                safety_threshold_high=4.0,
                safety_threshold_low=2.0,
                direction=SafetyDirection.TWO_SIDED,
                unit="V",
                source="MIL-PRF-19500/703 Table I spec_limit_high and spec_limit_low",
            ),
            "RDS(on)": ParameterSafetyThreshold(
                parameter_name="RDS(on)",
                safety_threshold_high=60.0,
                safety_threshold_low=None,
                direction=SafetyDirection.UPPER,
                unit="mOhm",
                source="Configured engineering screening threshold (spec ceiling is 65.0 mOhm per MIL-PRF-19500/703)",
            ),
            "IGSS": ParameterSafetyThreshold(
                parameter_name="IGSS",
                safety_threshold_high=100.0,
                safety_threshold_low=-100.0,
                direction=SafetyDirection.TWO_SIDED,
                unit="nA",
                source="MIL-PRF-19500/703 Table I spec_limit_high and spec_limit_low",
            ),
        }
        return cls(
            thresholds=thresholds,
            formula_source="configurable_engineering_decision_rule",
            formula_notice=(
                "The public SIH26170 problem statement requires comparison against a "
                "calculated safety slope. Because both drift rate and safety slope share "
                "the 144h denominator, the comparison is algebraically equivalent to checking "
                "whether predicted Value_168h crosses the safety threshold."
            ),
            as_of_hours=24,
            target_horizon_hours=168,
            horizon_delta_hours=144,
            boundary_comparison="strict_inequality",
        )


# ============================================================
# Safety-Slope Evaluator
# ============================================================

class SafetySlopeEvaluator:
    """Stateless safety-slope / early-rejection decision engine."""

    def __init__(self, config: Optional[SafetyConfig] = None) -> None:
        if config is None:
            config = SafetyConfig.default()
        self.config = config

    def evaluate_single(
        self,
        component_id: str,
        parameter_name: str,
        value_24h: float,
        predicted_value_168h: float,
        model_id: str = "unknown",
        upstream_disposition: str = "PREDICTED",
        lower_bound: Optional[float] = None,
        upper_bound: Optional[float] = None,
    ) -> SafetyDecisionResult:
        threshold = self.config.thresholds.get(parameter_name)
        if threshold is None:
            raise ValueError(
                f"No safety threshold configured for parameter '{parameter_name}'. "
                f"Available: {list(self.config.thresholds.keys())}"
            )

        unit = threshold.unit
        delta_h = float(self.config.horizon_delta_hours)

        if upstream_disposition == "INSUFFICIENT_DATA" or not math.isfinite(value_24h) or not math.isfinite(predicted_value_168h):
            return SafetyDecisionResult(
                component_id=component_id,
                parameter_name=parameter_name,
                unit=unit,
                value_24h=value_24h if math.isfinite(value_24h) else float("nan"),
                predicted_value_168h=predicted_value_168h if math.isfinite(predicted_value_168h) else float("nan"),
                predicted_total_drift=float("nan"),
                predicted_drift_rate=float("nan"),
                safety_threshold=float("nan"),
                safety_slope=float("nan"),
                direction=threshold.direction.value,
                evaluated_direction="none",
                margin_to_safety_threshold=float("nan"),
                decision=SafetyDecision.INSUFFICIENT_DATA,
                interval_status=IntervalSafetyStatus.NO_INTERVAL,
                reason=f"{parameter_name}: insufficient history for 24h baseline or non-finite values. No early rejection evaluated.",
                model_id=model_id,
                upstream_disposition=upstream_disposition,
            )

        predicted_total_drift = predicted_value_168h - value_24h
        predicted_drift_rate = predicted_total_drift / delta_h

        decision, evaluated_direction, safety_threshold_val, safety_slope_val, margin = (
            self._evaluate_direction(
                threshold, value_24h, predicted_value_168h,
                predicted_total_drift, predicted_drift_rate, delta_h
            )
        )

        interval_status = self._evaluate_interval_status(
            threshold, evaluated_direction, safety_threshold_val,
            lower_bound, upper_bound
        )

        reason = self._generate_explanation(
            parameter_name, unit, value_24h, predicted_value_168h,
            predicted_total_drift, predicted_drift_rate,
            safety_threshold_val, safety_slope_val, margin,
            evaluated_direction, decision, interval_status,
            upstream_disposition,
        )

        return SafetyDecisionResult(
            component_id=component_id,
            parameter_name=parameter_name,
            unit=unit,
            value_24h=value_24h,
            predicted_value_168h=predicted_value_168h,
            predicted_total_drift=predicted_total_drift,
            predicted_drift_rate=predicted_drift_rate,
            safety_threshold=safety_threshold_val,
            safety_slope=safety_slope_val,
            direction=threshold.direction.value,
            evaluated_direction=evaluated_direction,
            margin_to_safety_threshold=margin,
            decision=decision,
            interval_status=interval_status,
            reason=reason,
            model_id=model_id,
            upstream_disposition=upstream_disposition,
        )

    def _evaluate_direction(
        self,
        threshold: ParameterSafetyThreshold,
        value_24h: float,
        predicted_168h: float,
        total_drift: float,
        drift_rate: float,
        delta_h: float,
    ) -> Tuple[SafetyDecision, str, float, float, float]:
        if threshold.direction == SafetyDirection.UPPER:
            st = threshold.safety_threshold_high  # type: ignore[assignment]
            ss = (st - value_24h) / delta_h
            margin = st - predicted_168h
            decision = SafetyDecision.EARLY_REJECT if predicted_168h > st else SafetyDecision.CONTINUE
            return decision, "upper", st, ss, margin

        elif threshold.direction == SafetyDirection.LOWER:
            st = threshold.safety_threshold_low  # type: ignore[assignment]
            ss = (st - value_24h) / delta_h
            margin = predicted_168h - st
            decision = SafetyDecision.EARLY_REJECT if predicted_168h < st else SafetyDecision.CONTINUE
            return decision, "lower", st, ss, margin

        else:  # TWO_SIDED
            st_high = threshold.safety_threshold_high  # type: ignore[assignment]
            st_low = threshold.safety_threshold_low  # type: ignore[assignment]

            if total_drift > 0:
                ss = (st_high - value_24h) / delta_h
                margin = st_high - predicted_168h
                decision = SafetyDecision.EARLY_REJECT if predicted_168h > st_high else SafetyDecision.CONTINUE
                return decision, "upper", st_high, ss, margin
            elif total_drift < 0:
                ss = (st_low - value_24h) / delta_h
                margin = predicted_168h - st_low
                decision = SafetyDecision.EARLY_REJECT if predicted_168h < st_low else SafetyDecision.CONTINUE
                return decision, "lower", st_low, ss, margin
            else:
                margin = min(st_high - predicted_168h, predicted_168h - st_low)
                return SafetyDecision.CONTINUE, "none", st_high, 0.0, margin

    def _evaluate_interval_status(
        self,
        threshold: ParameterSafetyThreshold,
        evaluated_direction: str,
        safety_threshold: float,
        lower_bound: Optional[float],
        upper_bound: Optional[float],
    ) -> IntervalSafetyStatus:
        if lower_bound is None or upper_bound is None:
            return IntervalSafetyStatus.NO_INTERVAL

        if evaluated_direction == "upper":
            if upper_bound <= safety_threshold:
                return IntervalSafetyStatus.WITHIN_BOUNDARY
            elif lower_bound > safety_threshold:
                return IntervalSafetyStatus.BEYOND_BOUNDARY
            else:
                return IntervalSafetyStatus.BOUNDARY_CROSSED
        elif evaluated_direction == "lower":
            if lower_bound >= safety_threshold:
                return IntervalSafetyStatus.WITHIN_BOUNDARY
            elif upper_bound < safety_threshold:
                return IntervalSafetyStatus.BEYOND_BOUNDARY
            else:
                return IntervalSafetyStatus.BOUNDARY_CROSSED
        else:
            st_high = threshold.safety_threshold_high
            st_low = threshold.safety_threshold_low
            if st_high is not None and st_low is not None:
                if lower_bound >= st_low and upper_bound <= st_high:
                    return IntervalSafetyStatus.WITHIN_BOUNDARY
                elif lower_bound < st_low or upper_bound > st_high:
                    return IntervalSafetyStatus.BOUNDARY_CROSSED
            return IntervalSafetyStatus.WITHIN_BOUNDARY

    def _generate_explanation(
        self,
        parameter_name: str,
        unit: str,
        value_24h: float,
        predicted_168h: float,
        total_drift: float,
        drift_rate: float,
        safety_threshold: float,
        safety_slope: float,
        margin: float,
        evaluated_direction: str,
        decision: SafetyDecision,
        interval_status: IntervalSafetyStatus,
        upstream_disposition: str,
    ) -> str:
        lines = []
        lines.append(
            f"{parameter_name} predicted to reach {predicted_168h:.4f} {unit} at 168h "
            f"(observed {value_24h:.4f} {unit} at 24h)."
        )
        lines.append(
            f"Predicted drift rate = {drift_rate:+.6f} {unit}/h over 144h horizon."
        )
        dir_label = f" ({evaluated_direction})" if evaluated_direction != "none" else ""
        lines.append(
            f"Calculated safety slope{dir_label} = {safety_slope:+.6f} {unit}/h "
            f"(threshold: {safety_threshold:.4f} {unit})."
        )

        if decision == SafetyDecision.EARLY_REJECT:
            if evaluated_direction == "upper":
                lines.append(f"CRITICAL: Predicted drift rate exceeds safety slope (+{drift_rate - safety_slope:.6f} {unit}/h excess). Flagged for EARLY_REJECT.")
            elif evaluated_direction == "lower":
                lines.append(f"CRITICAL: Predicted downward drift rate breaches lower safety slope ({drift_rate - safety_slope:.6f} {unit}/h shortfall). Flagged for EARLY_REJECT.")
        else:
            lines.append(f"NOMINAL: Predicted drift rate remains within safety slope (margin: {margin:.4f} {unit}). Component disposition: CONTINUE.")

        if interval_status != IntervalSafetyStatus.NO_INTERVAL:
            lines.append(f"90% Prediction Interval status: {interval_status.value}.")

        return " ".join(lines)


def evaluate_component_safety(
    forecasts: Dict[str, PrognosticForecast],
    observations_24h: Dict[str, float],
    safety_config: Optional[SafetyConfig] = None,
) -> Dict[str, SafetyDecisionResult]:
    """Evaluate safety slopes across all parameters of a component."""
    evaluator = SafetySlopeEvaluator(config=safety_config)
    results: Dict[str, SafetyDecisionResult] = {}

    for param, forecast in forecasts.items():
        v24 = observations_24h.get(param, float("nan"))
        upstream_disp = "INSUFFICIENT_DATA" if not forecast.is_valid else "PREDICTED"
        res = evaluator.evaluate_single(
            component_id=forecast.component_id,
            parameter_name=param,
            value_24h=v24,
            predicted_value_168h=forecast.predicted_value,
            model_id=forecast.model_id,
            upstream_disposition=upstream_disp,
            lower_bound=forecast.interval_lower,
            upper_bound=forecast.interval_upper,
        )
        results[param] = res

    return results
