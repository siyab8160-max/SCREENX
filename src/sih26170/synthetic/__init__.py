"""SIH26170 Synthetic Burn-In Data Generator Package.

Provides reproducible, auditable, and decoupled synthetic burn-in telemetry generation
conforming strictly to docs/PHASE_2_SYNTHETIC_DATA_SPEC.md.
"""

from sih26170.synthetic.config import (
    EquipmentSimConfig,
    LotSimConfig,
    MissingnessSimConfig,
    ParameterSimConfig,
    SyntheticConfig,
    load_synthetic_config,
)
from sih26170.synthetic.generator import GenerationResult, SyntheticGenerator
from sih26170.synthetic.ground_truth import (
    GroundTruthRecord,
    GroundTruthSummary,
    evaluate_ground_truth,
)
from sih26170.synthetic.latent import LatentModel, LatentState
from sih26170.synthetic.measurement import EquipmentContext, MeasurementSimulator
from sih26170.synthetic.scenarios import ComponentPlan, ScenarioManager
from sih26170.synthetic.seeds import SeedHierarchy, derive_seed
from sih26170.synthetic.trajectories import (
    TrajectoryClass,
    TrajectoryProfile,
    create_trajectory_profile,
)
from sih26170.synthetic.validation import (
    StatisticalSanityReport,
    SyntheticValidator,
    ValidationReport,
)

__all__ = [
    "derive_seed",
    "SeedHierarchy",
    "ParameterSimConfig",
    "LotSimConfig",
    "EquipmentSimConfig",
    "MissingnessSimConfig",
    "SyntheticConfig",
    "load_synthetic_config",
    "TrajectoryClass",
    "TrajectoryProfile",
    "create_trajectory_profile",
    "LatentState",
    "LatentModel",
    "EquipmentContext",
    "MeasurementSimulator",
    "GroundTruthSummary",
    "GroundTruthRecord",
    "evaluate_ground_truth",
    "ComponentPlan",
    "ScenarioManager",
    "ValidationReport",
    "StatisticalSanityReport",
    "SyntheticValidator",
    "GenerationResult",
    "SyntheticGenerator",
]
