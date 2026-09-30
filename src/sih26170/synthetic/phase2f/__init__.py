"""SIH26170 Phase 2F Physics-Informed Synthetic Data Generator.

Canonical implementation of the Phase 2E Physics-Informed Synthetic Model Design
Specification for space-grade semiconductor burn-in screening.

Target Device: IRHNJ57130 / JANSR2N7481U3 (MIL-PRF-19500/703)
Primary Observables: IDSS, VGS(th), RDS(on), IGSS
Status: DEVELOPMENT GENERATOR (NOT FROZEN)
"""

from sih26170.synthetic.phase2f.config import (
    Phase2FConfig,
    Phase2FLotConfig,
    Phase2FParameterConfig,
    load_phase2f_config,
)
from sih26170.synthetic.phase2f.generator import (
    Phase2FGenerationResult,
    Phase2FGenerator,
)
from sih26170.synthetic.phase2f.scenarios import (
    ComponentTrajectoryVector,
    ParameterScenario,
    Phase2FScenarioManager,
)
from sih26170.synthetic.phase2f.validator import (
    Phase2FForensicReport,
    Phase2FValidator,
)

__all__ = [
    "Phase2FConfig",
    "Phase2FLotConfig",
    "Phase2FParameterConfig",
    "load_phase2f_config",
    "ParameterScenario",
    "ComponentTrajectoryVector",
    "Phase2FScenarioManager",
    "Phase2FGenerator",
    "Phase2FGenerationResult",
    "Phase2FValidator",
    "Phase2FForensicReport",
]
