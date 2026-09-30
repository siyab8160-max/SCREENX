"""SIH26170 Module A: High-Reliability Dynamic Screening Package.

Provides:
- Independent six-detector architecture (D_spec, D_peer, D_drift, D_step, D_eq, D_suff)
- Parameter-specific representations (positive log, signed asinh, bounded linear)
- Five-tier epistemic limit categorization (Class A spec vs Class C margin)
- Deterministic rules-based evidence fusion engine (PASS, ALERT, FAIL, INSUFFICIENT_DATA, EQUIPMENT_SUSPECTED)
- Self-contained explainability card and forensic audit records
- Strict As-Of historical contract enforcement and ground-truth quarantine
"""

from sih26170.screening.abrupt import evaluate_abrupt_step
from sih26170.screening.audit import (
    AuditRecord,
    compute_telemetry_hash,
    create_audit_record,
)
from sih26170.screening.equipment import evaluate_equipment_environment
from sih26170.screening.explainability import (
    export_explainability_dict,
    format_parameter_card,
    generate_explainability_card,
)
from sih26170.screening.fusion import (
    fuse_component_evidence,
    fuse_parameter_evidence,
)
from sih26170.screening.peer import evaluate_peer_deviation
from sih26170.screening.pipeline import (
    assert_ground_truth_quarantine,
    enforce_as_of_slice,
    screen_component,
    screen_dataset,
    screen_lot,
)
from sih26170.screening.schema import (
    AbruptStepStatus,
    AteEvidence,
    ChamberEvidence,
    ComponentScreeningResult,
    DispositionQualifier,
    EquipmentEvidence,
    EquipmentStatus,
    LimitClass,
    ParameterScreeningResult,
    PeerDeviationStatus,
    PeerEvidence,
    ScreeningState,
    SpecificationEvidence,
    SpecificationStatus,
    StepEvidence,
    SufficiencyEvidence,
    SufficiencyStatus,
    TemporalDriftStatus,
    TemporalEvidence,
)
from sih26170.screening.specification import evaluate_specification
from sih26170.screening.sufficiency import evaluate_data_sufficiency
from sih26170.screening.temporal import evaluate_temporal_drift
from sih26170.screening.transforms import (
    get_noise_floor,
    inverse_transform_parameter,
    transform_parameter,
)

__all__ = [
    # States & Enums
    "ScreeningState",
    "DispositionQualifier",
    "LimitClass",
    "SpecificationStatus",
    "PeerDeviationStatus",
    "TemporalDriftStatus",
    "AbruptStepStatus",
    "EquipmentStatus",
    "SufficiencyStatus",
    # Evidence & Results
    "SpecificationEvidence",
    "PeerEvidence",
    "TemporalEvidence",
    "StepEvidence",
    "EquipmentEvidence",
    "ChamberEvidence",
    "AteEvidence",
    "SufficiencyEvidence",
    "ParameterScreeningResult",
    "ComponentScreeningResult",
    # Detectors
    "evaluate_specification",
    "evaluate_peer_deviation",
    "evaluate_temporal_drift",
    "evaluate_abrupt_step",
    "evaluate_equipment_environment",
    "evaluate_data_sufficiency",
    # Transforms
    "transform_parameter",
    "inverse_transform_parameter",
    "get_noise_floor",
    # Fusion
    "fuse_parameter_evidence",
    "fuse_component_evidence",
    # Explainability & Audit
    "generate_explainability_card",
    "format_parameter_card",
    "export_explainability_dict",
    "create_audit_record",
    "compute_telemetry_hash",
    "AuditRecord",
    # Pipeline
    "screen_component",
    "screen_lot",
    "screen_dataset",
    "enforce_as_of_slice",
    "assert_ground_truth_quarantine",
]
