"""Canonical long-format data schema and Screening Run models for SIH26170.

Architecture Document Section 2 and PRD Section 4/5 compliant:
- Telemetry measurements are strictly formatted in long format.
- Ground truth trajectory labels exist only for evaluation and are isolated from model features.
- ScreeningRun structures establish the engineer-centric screening workflow.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


CANONICAL_COLUMNS = [
    "component_id",
    "lot_id",
    "parameter_name",
    "elapsed_hours",
    "value",
    "unit",
    "temperature_C",
    "test_condition",
    "instrument_id",
    "channel_id",
    "measurement_quality",
    "rework_count",
    "absolute_limit_low",
    "absolute_limit_high",
    "source_type",
]

GROUND_TRUTH_COLUMNS = [
    "trajectory_class",
    "first_abnormal_hour",
    "abnormal_by_24h",
    "abnormal_by_96h",
    "abnormal_by_168h",
]

ALL_COLUMNS = CANONICAL_COLUMNS + GROUND_TRUTH_COLUMNS

VALID_MEASUREMENT_QUALITIES = {"VALID", "DEGRADED", "SUSPECT", "MISSING"}
VALID_SOURCE_TYPES = {"synthetic", "real", "assumption"}
VALID_TRAJECTORY_CLASSES = {
    "stable",
    "high_but_stable",
    "lot_outlier",
    "linear_drift",
    "accelerating_drift",
    "abrupt_failure",
}


class ValueStatus(str, Enum):
    """Explicit numerical status of an observed measurement (Issue A).

    Guarantees raw data immutability while distinguishing states that cannot
    be mathematically processed identically:
    - POSITIVE: measurement > 0.0 (eligible for direct log transformation).
    - ZERO: measurement == 0.0 (physically zero; undefined in log space).
    - NEGATIVE: measurement < 0.0 (negative sensor offset/noise; ineligible for direct log transform).
    - MISSING: value is None or NaN.
    - NON_FINITE: value is +Inf or -Inf.
    """
    POSITIVE = "POSITIVE"
    ZERO = "ZERO"
    NEGATIVE = "NEGATIVE"
    MISSING = "MISSING"
    NON_FINITE = "NON_FINITE"


class AbsoluteStatus(str, Enum):
    """Deterministic hard gate absolute limit status channel (never overridden)."""
    PASS = "PASS"
    BREACH = "BREACH"
    NOT_EVALUATED = "NOT_EVALUATED"


class PeerStatus(str, Enum):
    """Peer-level offset status channel (b_i). Can be INSUFFICIENT_DATA."""
    NORMAL = "NORMAL"
    SUSPECT = "SUSPECT"
    OUTLIER = "OUTLIER"
    MAJOR_OUTLIER = "MAJOR_OUTLIER"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class TrendStatus(str, Enum):
    """Time-varying drift status channel (g_i(t)). Can be INSUFFICIENT_DATA."""
    STABLE = "STABLE"
    DRIFTING = "DRIFTING"
    ACCELERATING = "ACCELERATING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class DecisionState(str, Enum):
    """Final fused screening decision states (PRD FR3.1 & Architecture Section 5)."""
    PASS = "PASS"
    PASS_MONITOR = "PASS_MONITOR"
    REVIEW = "REVIEW"
    HOLD_FOR_RETEST = "HOLD_FOR_RETEST"
    REJECT = "REJECT"
    EQUIPMENT_HOLD = "EQUIPMENT_HOLD"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    OUT_OF_DISTRIBUTION = "OUT_OF_DISTRIBUTION"


def classify_measurement_value(val: Any) -> ValueStatus:
    """Classify the numerical state of a raw measurement without modifying it.

    Enforces Issue A: distinguishes 'negative' from 'zero' from 'missing' and 'non-finite'.
    Never mutates or floors the underlying value.
    """
    if val is None or pd.isna(val):
        return ValueStatus.MISSING
    try:
        f_val = float(val)
    except (ValueError, TypeError):
        return ValueStatus.NON_FINITE

    if not np.isfinite(f_val):
        return ValueStatus.NON_FINITE
    if f_val > 0.0:
        return ValueStatus.POSITIVE
    elif f_val == 0.0:
        return ValueStatus.ZERO
    else:
        return ValueStatus.NEGATIVE


@dataclass
class CanonicalMeasurement:
    """A single physical measurement observation in long format."""
    component_id: str
    lot_id: str
    parameter_name: str
    elapsed_hours: int
    value: float
    unit: str
    temperature_C: float
    test_condition: str
    instrument_id: Optional[str] = None
    channel_id: Optional[str] = None
    measurement_quality: str = "VALID"
    rework_count: int = 0
    absolute_limit_low: Optional[float] = None
    absolute_limit_high: Optional[float] = None
    source_type: str = "synthetic"

    # Synthetic-only ground truth fields (evaluation only)
    trajectory_class: Optional[str] = None
    first_abnormal_hour: Optional[int] = None
    abnormal_by_24h: Optional[bool] = None
    abnormal_by_96h: Optional[bool] = None
    abnormal_by_168h: Optional[bool] = None

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        """Validate single measurement integrity."""
        if not self.component_id:
            raise ValueError("component_id cannot be empty")
        if not self.lot_id:
            raise ValueError("lot_id cannot be empty")
        if not self.parameter_name:
            raise ValueError("parameter_name cannot be empty")
        if self.elapsed_hours < 0:
            raise ValueError(f"elapsed_hours must be >= 0, got {self.elapsed_hours}")
        if self.rework_count < 0:
            raise ValueError(f"rework_count must be >= 0, got {self.rework_count}")
        if self.measurement_quality not in VALID_MEASUREMENT_QUALITIES:
            raise ValueError(
                f"measurement_quality '{self.measurement_quality}' invalid. Expected one of {VALID_MEASUREMENT_QUALITIES}"
            )
        if self.source_type not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"source_type '{self.source_type}' invalid. Expected one of {VALID_SOURCE_TYPES}"
            )
        if self.trajectory_class is not None and self.trajectory_class not in VALID_TRAJECTORY_CLASSES:
            raise ValueError(
                f"trajectory_class '{self.trajectory_class}' invalid. Expected one of {VALID_TRAJECTORY_CLASSES}"
            )
        if self.absolute_limit_low is not None and self.absolute_limit_high is not None:
            if self.absolute_limit_low > self.absolute_limit_high:
                raise ValueError(
                    f"absolute_limit_low ({self.absolute_limit_low}) > absolute_limit_high ({self.absolute_limit_high})"
                )

    def to_dict(self, include_ground_truth: bool = True) -> Dict[str, Any]:
        """Convert measurement to dictionary."""
        d = asdict(self)
        if not include_ground_truth:
            for gt_col in GROUND_TRUTH_COLUMNS:
                d.pop(gt_col, None)
        return d


@dataclass(frozen=True)
class ParameterForecast:
    """Forecast of a component parameter at 168h produced by Module B.

    Enforces strict parameter scoping and unit lineage:
    - parameter_name and unit must strictly match the screening parameter observation.
    - interval_lower must be <= interval_upper.
    """
    parameter_name: str
    predicted_value: float
    unit: str
    interval_lower: float
    interval_upper: float
    interval_coverage: float = 0.90
    model_id: Optional[str] = None
    forecast_checkpoint: int = 168

    def __post_init__(self):
        if not self.parameter_name:
            raise ValueError("parameter_name cannot be empty")
        if not self.unit:
            raise ValueError("unit cannot be empty")
        if self.interval_lower > self.interval_upper:
            raise ValueError(
                f"Prediction interval lower bound ({self.interval_lower}) exceeds upper bound ({self.interval_upper})"
            )

    def validate_with_measurement(self, measurement: CanonicalMeasurement) -> None:
        """Enforce strict unit lineage and parameter scoping between observation and forecast."""
        if self.parameter_name != measurement.parameter_name:
            raise ValueError(
                f"Parameter mismatch between observation ('{measurement.parameter_name}') "
                f"and forecast ('{self.parameter_name}')"
            )
        if self.unit != measurement.unit:
            raise ValueError(
                f"Unit lineage mismatch for '{self.parameter_name}': observation unit is "
                f"'{measurement.unit}', but forecast unit is '{self.unit}'. "
                f"Forecast must be in identical engineering units as the screening parameter."
            )


@dataclass(frozen=True)
class QACard:
    """Plain-language QA Engineering Card for decision support (PRD FR4.1, FR6.2).

    Guarantees strict multi-channel evidence separation and mutual unit consistency:
    - value, unit, limit, unit, forecast, unit, interval, unit are explicit and consistent.
    - absolute_status, peer_status, trend_status are never conflated.
    - structurally prevents cross-parameter forecast contamination (e.g. 0.82 mA iddq forecast on 45 uA leakage card).
    """
    component_id: str
    lot_id: str
    parameter_name: str
    as_of_hours: int
    observed_value: float
    unit: str
    absolute_limit_low: Optional[float]
    absolute_limit_high: Optional[float]
    absolute_status: AbsoluteStatus
    peer_status: PeerStatus
    trend_status: TrendStatus
    decision_state: DecisionState
    plain_language_reason: str
    forecast: Optional[ParameterForecast] = None
    provenance_tag: str = "SYNTHETIC_EVALUATION"

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        """Validate card integrity and unit consistency."""
        if not self.component_id:
            raise ValueError("component_id cannot be empty")
        if not self.lot_id:
            raise ValueError("lot_id cannot be empty")
        if not self.parameter_name:
            raise ValueError("parameter_name cannot be empty")
        if not self.unit:
            raise ValueError("unit cannot be empty")

        # Absolute limit checks
        if self.absolute_limit_high is not None and self.observed_value > self.absolute_limit_high:
            if self.absolute_status == AbsoluteStatus.PASS:
                raise ValueError(
                    f"Integrity violation: observed value ({self.observed_value} {self.unit}) "
                    f"> upper limit ({self.absolute_limit_high} {self.unit}), but absolute_status is PASS."
                )
        if self.absolute_limit_low is not None and self.observed_value < self.absolute_limit_low:
            if self.absolute_status == AbsoluteStatus.PASS:
                raise ValueError(
                    f"Integrity violation: observed value ({self.observed_value} {self.unit}) "
                    f"< lower limit ({self.absolute_limit_low} {self.unit}), but absolute_status is PASS."
                )

        # Forecast unit consistency check
        if self.forecast is not None:
            if self.forecast.parameter_name != self.parameter_name:
                raise ValueError(
                    f"Cross-parameter forecast contamination: QA card is for '{self.parameter_name}', "
                    f"but attached forecast is for '{self.forecast.parameter_name}'."
                )
            if self.forecast.unit != self.unit:
                raise ValueError(
                    f"Unit lineage bug detected: QA card observation unit is '{self.unit}', "
                    f"but forecast unit is '{self.forecast.unit}'. Forecast must match observation unit."
                )


@dataclass
class ScreeningRun:
    """Metadata and screening parameters for a component screening campaign.

    Represents the Screening Run concept (CHANGE 5 & Audit Section 6):
    Component Identity -> Part Spec -> Screening Config -> Screening Run -> Measurements.

    Guarantees Screening Configuration Reproducibility:
    - Retains a frozen snapshot of the screening configuration (user limits, scale floors, etc.)
      that was active when the run was initialized/validated.
    - Subsequent changes to global configurations or component-family objects cannot alter
      the historical screening run's configuration snapshot.
    """
    run_id: str
    component_id: str
    lot_id: str
    component_family: str
    part_number: Optional[str] = None
    manufacturer: Optional[str] = None
    revision: Optional[str] = None
    wafer_id: Optional[str] = None
    screening_config_id: Optional[str] = "prototype-v1"
    # Parameter name -> (user_limit_low, user_limit_high)
    user_limits: Dict[str, Tuple[Optional[float], Optional[float]]] = field(default_factory=dict)
    # Frozen snapshot of the exact screening parameters used during this run
    frozen_screening_config: Dict[str, Any] = field(default_factory=dict)
    status: str = "INITIALIZED"  # INITIALIZED, VALIDATED, REVIEW_REQUIRED, COMPLETED
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    engineer_id: Optional[str] = None
    engineer_notes: Optional[str] = None

    def __post_init__(self):
        self.validate()
        # Automatically capture initial frozen snapshot if not provided
        if not self.frozen_screening_config and self.user_limits:
            self.freeze_configuration()

    def validate(self) -> None:
        """Validate screening run configuration."""
        if not self.run_id:
            raise ValueError("run_id cannot be empty")
        if not self.component_id:
            raise ValueError("component_id cannot be empty")
        if not self.lot_id:
            raise ValueError("lot_id cannot be empty")
        if not self.component_family:
            raise ValueError("component_family cannot be empty")
        for param, limits in self.user_limits.items():
            low, high = limits
            if low is not None and high is not None and low > high:
                raise ValueError(f"user_limits for parameter '{param}' invalid: {low} > {high}")

    def freeze_configuration(self, extra_config: Optional[Dict[str, Any]] = None) -> None:
        """Capture an immutable snapshot of the screening limits and metadata."""
        snapshot = {
            "screening_config_id": self.screening_config_id,
            "component_family": self.component_family,
            "user_limits": {k: (v[0], v[1]) for k, v in self.user_limits.items()},
            "frozen_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra_config:
            snapshot.update(extra_config)
        self.frozen_screening_config = snapshot

    def get_effective_screening_limits(self, param_name: str) -> Tuple[Optional[float], Optional[float]]:
        """Retrieve the immutable screening limits from the frozen snapshot."""
        if self.frozen_screening_config and "user_limits" in self.frozen_screening_config:
            limits = self.frozen_screening_config["user_limits"].get(param_name)
            if limits is not None:
                return (limits[0], limits[1])
        return self.user_limits.get(param_name, (None, None))


def get_observation_data(df: pd.DataFrame) -> pd.DataFrame:
    """Isolate observation data from evaluation-only ground truth fields.

    Audited requirement (Section 8): Downstream ML feature extractors must NEVER
    access trajectory classes or future time-indexed defect labels.
    """
    obs_cols = [c for c in CANONICAL_COLUMNS if c in df.columns]
    return df[obs_cols].copy()


def get_ground_truth_data(df: pd.DataFrame) -> pd.DataFrame:
    """Extract strictly evaluation-only ground truth fields along with device identifiers."""
    id_cols = [c for c in ["component_id", "lot_id", "parameter_name", "elapsed_hours"] if c in df.columns]
    gt_cols = [c for c in GROUND_TRUTH_COLUMNS if c in df.columns]
    return df[id_cols + gt_cols].copy()


def validate_feature_columns(feature_columns: List[str]) -> None:
    """Validate that no ground-truth column has leaked into a model feature set."""
    forbidden = set(feature_columns) & set(GROUND_TRUTH_COLUMNS)
    if forbidden:
        raise ValueError(
            f"Ground-truth leakage detected in feature columns: {forbidden}. "
            f"Ground truth columns are strictly evaluation-only."
        )


def to_dataframe(
    measurements: List[CanonicalMeasurement],
    include_ground_truth: bool = True
) -> pd.DataFrame:
    """Convert a list of CanonicalMeasurement objects into a standard pandas DataFrame."""
    if not measurements:
        cols = ALL_COLUMNS if include_ground_truth else CANONICAL_COLUMNS
        return pd.DataFrame(columns=cols)

    data = [m.to_dict(include_ground_truth=include_ground_truth) for m in measurements]
    df = pd.DataFrame(data)
    cols = [c for c in (ALL_COLUMNS if include_ground_truth else CANONICAL_COLUMNS) if c in df.columns]
    return df[cols]


def from_dataframe(df: pd.DataFrame) -> List[CanonicalMeasurement]:
    """Parse a pandas DataFrame into a list of CanonicalMeasurement objects."""
    measurements: List[CanonicalMeasurement] = []
    for _, row in df.iterrows():
        record_dict = row.to_dict()
        # Handle nan / None conversions
        clean_dict = {}
        for k, v in record_dict.items():
            if pd.isna(v):
                clean_dict[k] = None
            else:
                clean_dict[k] = v

        # Convert types where necessary
        clean_dict["elapsed_hours"] = int(clean_dict["elapsed_hours"])
        clean_dict["value"] = float(clean_dict["value"])
        clean_dict["temperature_C"] = float(clean_dict["temperature_C"])
        clean_dict["rework_count"] = int(clean_dict.get("rework_count", 0))

        if clean_dict.get("first_abnormal_hour") is not None:
            clean_dict["first_abnormal_hour"] = int(clean_dict["first_abnormal_hour"])
        if clean_dict.get("abnormal_by_24h") is not None:
            clean_dict["abnormal_by_24h"] = bool(clean_dict["abnormal_by_24h"])
        if clean_dict.get("abnormal_by_96h") is not None:
            clean_dict["abnormal_by_96h"] = bool(clean_dict["abnormal_by_96h"])
        if clean_dict.get("abnormal_by_168h") is not None:
            clean_dict["abnormal_by_168h"] = bool(clean_dict["abnormal_by_168h"])

        measurement = CanonicalMeasurement(**clean_dict)
        measurements.append(measurement)
    return measurements
