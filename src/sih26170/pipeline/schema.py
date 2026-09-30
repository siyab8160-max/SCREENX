"""Canonical application-level contracts for SIH26170 Engineering Prototype.

Complies strictly with post-Phase-5 engineering integration specifications:
- Physical MOSFET parameters only: IDSS (uA), VGS(th) (V), RDS(on) (mOhm), IGSS (nA).
- Preserves signed IGSS throughout (never abs, never clipped).
- Explicit decoupling: Measured Specification Failure != Predicted Future Breach.
- Predictive spec breach is informational prognostic evidence only (no autonomous rejection).
- Clear separation: deterministic canonical result payload vs. non-deterministic runtime audit metadata.
- Engineering explainability object using physical evidence (no AI buzzwords).
- Prototype-grade engineering implementation (not production-qualified).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from typing import Any, Dict, List, Optional

from sih26170.screening.schema import (
    ComponentScreeningResult,
    DispositionQualifier,
    ScreeningState,
)
from sih26170.prognostics.schema import PrognosticForecast


class PhysicalParameter(str, Enum):
    """Canonical physical parameters for Infineon IRHNJ57130 Power MOSFET."""
    IDSS = "IDSS"
    VGS_TH = "VGS(th)"
    RDS_ON = "RDS(on)"
    IGSS = "IGSS"


CANONICAL_PARAM_UNITS: Dict[str, str] = {
    PhysicalParameter.IDSS.value: "uA",
    PhysicalParameter.VGS_TH.value: "V",
    PhysicalParameter.RDS_ON.value: "mOhm",
    PhysicalParameter.IGSS.value: "nA",
}

ORDERED_PARAMETERS: List[str] = [
    PhysicalParameter.IDSS.value,
    PhysicalParameter.VGS_TH.value,
    PhysicalParameter.RDS_ON.value,
    PhysicalParameter.IGSS.value,
]


@dataclass(frozen=True)
class ForecastInterpretation:
    """Explicit interpretation decoupling measured state from prognostic forecast."""
    parameter: str
    measured_spec_failure: bool
    predicted_spec_breach: bool
    predicted_breach_lower: bool
    predicted_breach_upper: bool
    measured_value: Optional[float]
    predicted_value: Optional[float]
    limit_low: Optional[float]
    limit_high: Optional[float]
    unit: str
    disposition_recommendation: str = (
        "INFORMATIONAL PROGNOSTIC EVIDENCE ONLY — NO AUTONOMOUS REJECTION AUTHORIZED"
    )
    predicted_drift_rate: Optional[float] = None
    calculated_safety_slope: Optional[float] = None
    safety_threshold: Optional[float] = None
    early_rejection_flag: bool = False
    safety_decision: str = "CONTINUE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EngineeringExplainability:
    """Objective engineering explainability evidence card."""
    what_happened: str
    why_flagged: str
    which_parameter: Optional[str]
    what_evidence: Dict[str, Any]
    what_predicted: Dict[str, Any]
    how_uncertain: Dict[str, Any]
    was_equipment_present: bool
    equipment_details: Dict[str, Any]
    what_info_available_as_of: Dict[str, Any]
    ascii_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PipelineAuditRecord:
    """Forensic audit record containing execution context and deterministic lineage."""
    run_id: str
    created_at: str  # Runtime timestamp (omitted from canonical_result_hash)
    component_id: str
    lot_id: str
    as_of_hours: int
    input_hash: str
    canonical_result_hash: str
    model_lineage_hash: str
    software_context: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass(frozen=True)
class ModelLineageInfo:
    """Immutable model metadata record for downstream consumers."""
    model_family: str = "RIDGE_REGRESSION"
    model_status: str = "LOCKED_IMMUTABLE"
    lambda_reg: float = 1.0
    training_partition: str = "LOT_CAL_001_TO_LOT_CAL_050"
    validation_partition: str = "LOT_VAL_001_TO_LOT_VAL_025"
    evaluation_partition: str = "LOT_EVAL_001_TO_LOT_EVAL_025"
    manifest_hash: str = "bde6989e24d195ab4b53f93c46c2156d1c336fe820baf149d76d32943e135667"
    coefficients: Dict[str, List[float]] = field(default_factory=dict)
    sigma_eff: Dict[str, float] = field(default_factory=dict)
    scope: str = "SYNTHETIC_BENCHMARK_PROTOTYPE"
    physical_validation: str = "NOT_ESTABLISHED"
    safety_slope: str = "OPEN_EVIDENCE_GAP"
    predictive_rejection: str = "NOT_AUTHORIZED"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComponentPipelineResult:
    """Single canonical, structured result from the end-to-end engineering prototype pipeline."""
    component_id: str
    lot_id: str
    as_of_hours: int
    screening_result: ComponentScreeningResult
    prognostic_forecasts: Dict[str, PrognosticForecast]
    interpretations: Dict[str, ForecastInterpretation]
    explainability: EngineeringExplainability
    input_hash: str
    canonical_result_hash: str
    audit_record: Optional[PipelineAuditRecord] = None
    model_lineage: Optional[ModelLineageInfo] = None
    safety_decisions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    component_early_rejection: bool = False

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Produce deterministic canonical dictionary representation for cryptographic hashing.

        STRICT DETERMINISM RULES:
        - Excludes runtime execution timestamps (e.g. audit_record.created_at).
        - Excludes host/execution context and random UUID run IDs.
        - Orders all parameter dictionary keys deterministically.
        - Serializes numbers with exact mathematical stability.
        """
        screening_dict = self.screening_result.to_dict()
        # Remove non-deterministic runtime timestamp from screening if present
        screening_dict.pop("created_at", None)

        forecasts_dict = {}
        for p in ORDERED_PARAMETERS:
            if p in self.prognostic_forecasts:
                f_dict = self.prognostic_forecasts[p].to_dict()
                forecasts_dict[p] = f_dict

        interp_dict = {}
        for p in ORDERED_PARAMETERS:
            if p in self.interpretations:
                interp_dict[p] = self.interpretations[p].to_dict()

        explain_dict = self.explainability.to_dict()
        # Exclude ASCII representation from canonical hash to avoid layout variance
        explain_canonical = {
            k: v for k, v in explain_dict.items() if k != "ascii_summary"
        }

        return {
            "component_id": self.component_id,
            "lot_id": self.lot_id,
            "as_of_hours": int(self.as_of_hours),
            "input_hash": self.input_hash,
            "screening_state": self.screening_result.final_state.value,
            "disposition_qualifier": self.screening_result.disposition_qualifier.value,
            "primary_reason_code": self.screening_result.primary_reason_code,
            "screening_details": screening_dict,
            "prognostic_forecasts": forecasts_dict,
            "interpretations": interp_dict,
            "explainability": explain_canonical,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize full result including runtime audit record and model lineage."""
        return {
            "component_id": self.component_id,
            "lot_id": self.lot_id,
            "as_of_hours": self.as_of_hours,
            "final_screening_state": self.screening_result.final_state.value,
            "disposition_qualifier": self.screening_result.disposition_qualifier.value,
            "primary_reason_code": self.screening_result.primary_reason_code,
            "input_hash": self.input_hash,
            "canonical_result_hash": self.canonical_result_hash,
            "screening": self.screening_result.to_dict(),
            "prognostics": {p: f.to_dict() for p, f in self.prognostic_forecasts.items()},
            "interpretations": {p: i.to_dict() for p, i in self.interpretations.items()},
            "safety_decisions": self.safety_decisions,
            "component_early_rejection": self.component_early_rejection,
            "explainability": self.explainability.to_dict(),
            "audit_record": self.audit_record.to_dict() if self.audit_record else None,
            "model_lineage": self.model_lineage.to_dict() if self.model_lineage else None,
        }
