"""SIH26170 Phase 4B Independent Benchmark Generator Package.

Implements the implementation-ready benchmark specification defined by LOG-076.
Produces PHASE_4B_BENCHMARK_v1.0.0 with dense temporal support (K=7, S1 schedule),
independent null models (A, B, C), and calibrated weak degradation fixtures (A-F).
"""

from sih26170.synthetic.phase4b.config import (
    Phase4BConfig,
    Phase4BFixtureType,
    Phase4BLotConfig,
    Phase4BParameterConfig,
    Phase4BPartition,
    get_default_phase4b_config,
)
from sih26170.synthetic.phase4b.generator import (
    Phase4BGenerationResult,
    Phase4BGenerator,
    generate_phase4b_benchmark,
)

__all__ = [
    "Phase4BConfig",
    "Phase4BFixtureType",
    "Phase4BLotConfig",
    "Phase4BParameterConfig",
    "Phase4BPartition",
    "get_default_phase4b_config",
    "Phase4BGenerationResult",
    "Phase4BGenerator",
    "generate_phase4b_benchmark",
]
