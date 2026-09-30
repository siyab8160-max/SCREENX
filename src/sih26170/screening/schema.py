"""Module A screening schema and data structures.

Compliant with docs/PHASE_3A_MODULE_A_SPEC.md:
- Exact five screening states: PASS, ALERT, FAIL, INSUFFICIENT_DATA, EQUIPMENT_SUSPECTED
- Five-tier epistemic limit classification (Class A to Class E)
- Structured evidence models for all six detectors (D_spec, D_peer, D_drift, D_step, D_eq, D_suff)
- Parameter and component screening results with full audit metadata
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ScreeningState(str, Enum):
    """Canonical screening states for Module A (Spec Section 10)."""
    PASS = "PASS"
    ALERT = "ALERT"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    EQUIPMENT_SUSPECTED = "EQUIPMENT_SUSPECTED"


class LimitClass(str, Enum):
    """Five-tier epistemic classification framework (Spec Section 5)."""
    CLASS_A = "Class A"  # Verified Device Specification (MIL-PRF-19500/703 Table I)
    CLASS_B = "Class B"  # Verified Military Standard Requirement (PDA)
    CLASS_C = "Class C"  # Configured Screening Acceptance Criterion (PD-97217)
    CLASS_D = "Class D"  # Engineering Heuristic (Small-lot N < 8, DPAT multipliers)
    CLASS_E = "Class E"  # Synthetic Benchmark Design Parameter (Difficulty SNR)


class SpecificationStatus(str, Enum):
    """Status emitted by Detector A (D_spec)."""
    COMPLIANT = "COMPLIANT"
    SPEC_BREACH = "SPEC_BREACH"  # Class A limit breach -> FAIL
    SCREENING_MARGIN_BREACH = "SCREENING_MARGIN_BREACH"  # Class C limit breach -> ALERT
    NOT_EVALUATED = "NOT_EVALUATED"


class PeerDeviationStatus(str, Enum):
    """Status emitted by Detector B (D_peer)."""
    PEER_NORMAL = "PEER_NORMAL"
    PEER_MILD_OUTLIER = "PEER_MILD_OUTLIER"  # |z| >= 3.0
    PEER_EXTREME_OUTLIER = "PEER_EXTREME_OUTLIER"  # |z| >= 5.0
    PEER_SUPPRESSED_SMALL_LOT = "PEER_SUPPRESSED_SMALL_LOT"  # N < 8 policy
    INSUFFICIENT_PEERS = "INSUFFICIENT_PEERS"


class TemporalDriftStatus(str, Enum):
    """Status emitted by Detector C (D_drift)."""
    STATIONARY = "STATIONARY"  # |g(T)| < 2.5
    SUBTLE_DRIFT = "SUBTLE_DRIFT"  # |g(T)| >= 2.5
    ACCELERATING_DRIFT = "ACCELERATING_DRIFT"  # |g(T)| >= 3.0 and kappa * beta > 0
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"  # Only 1 observation (t=0)
    TEMPORALLY_CONFOUNDED_BY_EQUIPMENT = "TEMPORALLY_CONFOUNDED_BY_EQUIPMENT"


class AbruptStepStatus(str, Enum):
    """Status emitted by Detector D (D_step)."""
    NO_STEP = "NO_STEP"
    ABRUPT_JUMP_ALERT = "ABRUPT_JUMP_ALERT"  # J(T) >= 4.0
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


class EquipmentStatus(str, Enum):
    """Status emitted by Detector E (D_eq)."""
    NOMINAL_EQUIPMENT = "NOMINAL_EQUIPMENT"
    CHAMBER_EXCURSION_SUSPECTED = "CHAMBER_EXCURSION_SUSPECTED"
    CHANNEL_BIAS_SUSPECTED = "CHANNEL_BIAS_SUSPECTED"
    CHANNEL_BIAS_SUPPRESSED_SMALL_SAMPLE = "CHANNEL_BIAS_SUPPRESSED_SMALL_SAMPLE"
    EQUIPMENT_HOLD = "EQUIPMENT_HOLD"


class DispositionQualifier(str, Enum):
    """Epistemic qualifier enriching canonical 5 screening states (Spec Section 10)."""
    SPECIFICATION_FAILURE = "SPECIFICATION_FAILURE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    COMPONENT_DEGRADATION = "COMPONENT_DEGRADATION"
    COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT = "COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT"
    EQUIPMENT_ONLY = "EQUIPMENT_ONLY"
    PEER_OUTLIER_STATIONARY = "PEER_OUTLIER_STATIONARY"
    NOMINAL_STABLE = "NOMINAL_STABLE"


class SufficiencyStatus(str, Enum):
    """Status emitted by Detector F (D_suff)."""
    SUFFICIENT = "SUFFICIENT"
    INCOMPLETE_HISTORY = "INCOMPLETE_HISTORY"
    CORRUPTED_MEASUREMENT = "CORRUPTED_MEASUREMENT"
    SMALL_LOT_RESTRICTION = "SMALL_LOT_RESTRICTION"


@dataclass
class SpecificationEvidence:
    """Explicit evidence record for Detector A (Absolute Specification)."""
    parameter: str
    observed_value: float
    limit_low: Optional[float]
    limit_high: Optional[float]
    limit_class: LimitClass
    status: SpecificationStatus
    passed: bool
    reason_code: str
    provenance: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter": self.parameter,
            "observed_value": self.observed_value,
            "limit_low": self.limit_low,
            "limit_high": self.limit_high,
            "limit_class": self.limit_class.value,
            "status": self.status.value,
            "passed": self.passed,
            "reason_code": self.reason_code,
            "provenance": self.provenance,
        }


@dataclass
class PeerEvidence:
    """Explicit evidence record for Detector B (Lot/Peer Relative Deviation)."""
    parameter: str
    observed_value: float
    transformed_value: float
    peer_median: Optional[float]
    peer_mad: Optional[float]
    peer_scale: Optional[float]
    z_score: Optional[float]
    status: PeerDeviationStatus
    peer_count: int
    reason_code: str
    reference_slice: str = "PER-LOT BASELINE REFERENCE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter": self.parameter,
            "observed_value": self.observed_value,
            "transformed_value": self.transformed_value,
            "peer_median": self.peer_median,
            "peer_mad": self.peer_mad,
            "peer_scale": self.peer_scale,
            "z_score": self.z_score,
            "status": self.status.value,
            "peer_count": self.peer_count,
            "reason_code": self.reason_code,
            "reference_slice": self.reference_slice,
        }


@dataclass
class TemporalEvidence:
    """Explicit evidence record for Detector C (Temporal Drift)."""
    parameter: str
    observations_used: int
    checkpoints_used: List[int]
    time_range: Tuple[int, int]
    slope_per_hour: Optional[float]
    normalized_drift: Optional[float]
    acceleration_evidence: Optional[float]
    status: TemporalDriftStatus
    confounded_by_equipment: bool
    reason_code: str
    g_lot: Optional[float] = None
    g_excess: Optional[float] = None
    lot_reference_note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter": self.parameter,
            "observations_used": self.observations_used,
            "checkpoints_used": list(self.checkpoints_used),
            "time_range": list(self.time_range),
            "slope_per_hour": self.slope_per_hour,
            "normalized_drift": self.normalized_drift,
            "acceleration_evidence": self.acceleration_evidence,
            "status": self.status.value,
            "confounded_by_equipment": self.confounded_by_equipment,
            "reason_code": self.reason_code,
            "g_lot": self.g_lot,
            "g_excess": self.g_excess,
            "lot_reference_note": self.lot_reference_note,
        }


@dataclass
class StepEvidence:
    """Explicit evidence record for Detector D (Abrupt Change)."""
    parameter: str
    previous_checkpoint: Optional[int]
    current_checkpoint: int
    step_magnitude: Optional[float]
    step_ratio: Optional[float]
    status: AbruptStepStatus
    reason_code: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter": self.parameter,
            "previous_checkpoint": self.previous_checkpoint,
            "current_checkpoint": self.current_checkpoint,
            "step_magnitude": self.step_magnitude,
            "step_ratio": self.step_ratio,
            "status": self.status.value,
            "reason_code": self.reason_code,
        }


@dataclass
class ChamberEvidence:
    """Explicit evidence record for chamber thermal excursions."""
    lot_median_shift: Optional[float]
    fraction_shifting: Optional[float]
    suspected: bool
    reason_code: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lot_median_shift": self.lot_median_shift,
            "fraction_shifting": self.fraction_shifting,
            "suspected": self.suspected,
            "reason_code": self.reason_code,
        }


@dataclass
class AteEvidence:
    """Explicit evidence record for ATE fixture channel offsets."""
    channel_id: Optional[str]
    n_channel: int
    n_lot_other: int
    channel_offset: Optional[float]
    z_score: Optional[float]
    suppressed: bool
    suspected: bool
    reason_code: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "n_channel": self.n_channel,
            "n_lot_other": self.n_lot_other,
            "channel_offset": self.channel_offset,
            "z_score": self.z_score,
            "suppressed": self.suppressed,
            "suspected": self.suspected,
            "reason_code": self.reason_code,
        }


@dataclass
class EquipmentEvidence:
    """Explicit evidence record for Detector E (Common-Mode / Equipment)."""
    lot_id: str
    checkpoint: int
    instrument_id: Optional[str]
    channel_id: Optional[str]
    lot_median_shift: Optional[float]
    fraction_shifting: Optional[float]
    channel_offset: Optional[float]
    status: EquipmentStatus
    suspected: bool
    reason_code: str
    chamber_evidence: Optional[ChamberEvidence] = None
    ate_evidence: Optional[AteEvidence] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lot_id": self.lot_id,
            "checkpoint": self.checkpoint,
            "instrument_id": self.instrument_id,
            "channel_id": self.channel_id,
            "lot_median_shift": self.lot_median_shift,
            "fraction_shifting": self.fraction_shifting,
            "channel_offset": self.channel_offset,
            "status": self.status.value,
            "suspected": self.suspected,
            "reason_code": self.reason_code,
            "chamber_evidence": self.chamber_evidence.to_dict() if self.chamber_evidence else None,
            "ate_evidence": self.ate_evidence.to_dict() if self.ate_evidence else None,
        }


@dataclass
class SufficiencyEvidence:
    """Explicit evidence record for Detector F (Data Sufficiency)."""
    component_id: str
    checkpoint: int
    expected_checkpoints: List[int]
    available_checkpoints: List[int]
    lot_size: int
    is_small_lot: bool
    status: SufficiencyStatus
    sufficient: bool
    reason_code: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "checkpoint": self.checkpoint,
            "expected_checkpoints": list(self.expected_checkpoints),
            "available_checkpoints": list(self.available_checkpoints),
            "lot_size": self.lot_size,
            "is_small_lot": self.is_small_lot,
            "status": self.status.value,
            "sufficient": self.sufficient,
            "reason_code": self.reason_code,
        }


@dataclass
class ParameterScreeningResult:
    """Complete evaluation results for an individual parameter on a component."""
    parameter: str
    observed_value: float
    unit: str
    transformed_value: float
    spec_evidence: SpecificationEvidence
    peer_evidence: PeerEvidence
    temporal_evidence: TemporalEvidence
    step_evidence: StepEvidence
    equipment_evidence: EquipmentEvidence
    sufficiency_evidence: SufficiencyEvidence
    parameter_state: ScreeningState
    primary_reason_code: str
    reason_codes: List[str]
    disposition_qualifier: DispositionQualifier = DispositionQualifier.NOMINAL_STABLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter": self.parameter,
            "observed_value": self.observed_value,
            "unit": self.unit,
            "transformed_value": self.transformed_value,
            "spec_evidence": self.spec_evidence.to_dict(),
            "peer_evidence": self.peer_evidence.to_dict(),
            "temporal_evidence": self.temporal_evidence.to_dict(),
            "step_evidence": self.step_evidence.to_dict(),
            "equipment_evidence": self.equipment_evidence.to_dict(),
            "sufficiency_evidence": self.sufficiency_evidence.to_dict(),
            "parameter_state": self.parameter_state.value,
            "primary_reason_code": self.primary_reason_code,
            "reason_codes": list(self.reason_codes),
            "disposition_qualifier": self.disposition_qualifier.value,
        }


@dataclass
class ComponentScreeningResult:
    """Machine-readable screening output for a component at checkpoint T."""
    component_id: str
    lot_id: str
    checkpoint: int
    final_state: ScreeningState
    primary_reason_code: str
    reason_codes: List[str]
    compound_evidence: bool
    parameter_results: Dict[str, ParameterScreeningResult]
    as_of_hours: int
    audit_hash: str
    disposition_qualifier: DispositionQualifier = DispositionQualifier.NOMINAL_STABLE
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "lot_id": self.lot_id,
            "checkpoint": self.checkpoint,
            "final_state": self.final_state.value,
            "primary_reason_code": self.primary_reason_code,
            "reason_codes": list(self.reason_codes),
            "compound_evidence": self.compound_evidence,
            "disposition_qualifier": self.disposition_qualifier.value,
            "parameter_results": {
                p: res.to_dict() for p, res in self.parameter_results.items()
            },
            "as_of_hours": self.as_of_hours,
            "audit_hash": self.audit_hash,
            "created_at": self.created_at,
        }
