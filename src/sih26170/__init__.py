"""SIH26170: AI-Driven Anomaly Detection in Component Burn-In & Screening.

Phase 1 Core Package:
- Canonical schema & Screening Run data structures
- Configuration system with 4-tier provenance verification
- Component family abstraction separating reference specs from user limits
- Validation layer and strict 'as-of' temporal contract enforcement
"""

from sih26170.config import (
    ParameterConfig,
    PrototypeConfig,
    ProvenanceCategory,
    ReferenceValueType,
    VerificationStatus,
    load_parameter_configs,
    load_prototype_config,
    verify_traceability,
)
from sih26170.schema import (
    ALL_COLUMNS,
    CANONICAL_COLUMNS,
    GROUND_TRUTH_COLUMNS,
    AbsoluteStatus,
    CanonicalMeasurement,
    DecisionState,
    PeerStatus,
    ScreeningRun,
    TrendStatus,
    ValueStatus,
    classify_measurement_value,
    from_dataframe,
    get_ground_truth_data,
    get_observation_data,
    to_dataframe,
    validate_feature_columns,
)
from sih26170.component_family import (
    ComponentFamily,
    get_component_family,
    list_component_families,
    register_component_family,
)
from sih26170.validation import (
    ValidationReport,
    assess_peer_sample_size,
    enforce_as_of,
    validate_dataset,
    validate_reference_spec,
    validate_user_limits,
)

__version__ = "0.1.0"

__all__ = [
    # Config
    "ParameterConfig",
    "PrototypeConfig",
    "ProvenanceCategory",
    "ReferenceValueType",
    "VerificationStatus",
    "load_parameter_configs",
    "load_prototype_config",
    "verify_traceability",
    # Schema
    "ALL_COLUMNS",
    "CANONICAL_COLUMNS",
    "GROUND_TRUTH_COLUMNS",
    "AbsoluteStatus",
    "CanonicalMeasurement",
    "DecisionState",
    "PeerStatus",
    "ScreeningRun",
    "TrendStatus",
    "ValueStatus",
    "classify_measurement_value",
    "from_dataframe",
    "get_ground_truth_data",
    "get_observation_data",
    "to_dataframe",
    "validate_feature_columns",
    # Component Family
    "ComponentFamily",
    "get_component_family",
    "list_component_families",
    "register_component_family",
    # Validation
    "ValidationReport",
    "assess_peer_sample_size",
    "enforce_as_of",
    "validate_dataset",
    "validate_reference_spec",
    "validate_user_limits",
]
