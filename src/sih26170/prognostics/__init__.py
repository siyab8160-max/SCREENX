"""Module B: Temporal Drift Prediction / Prognostics for High-Reliability Electronics.

SCIENTIFIC BOUNDARY & DATASET STATUS:
The 398 benchmark components are synthetic simulated components. The
IRHNJ57130/JANSR2N7481U3 specification provides the physical/device anchor; it
does not mean that the 398 components represent 398 experimentally characterized
MOSFETs. Module B results therefore constitute algorithmic/benchmark evidence,
not real-device validation.

This module implements:
- PrognosticInput: Minimal strictly-as-of input contract
- PrognosticForecast: Fully scoped forecast contract with dual drift quantities
- Baseline models: Carry-Forward, Two-Point Linear (24h->168h), Theil-Sen (96h->168h)
- Strict as-of validation and leakage prevention
- LOLO (primary) and pristine-to-defect (secondary) evaluation pipelines
"""

from sih26170.prognostics.schema import (
    PrognosticInput,
    PrognosticForecast,
)
from sih26170.prognostics.baselines import (
    CarryForwardModel,
    TwoPointLinearModel,
    TheilSenExtrapolationModel,
)
from sih26170.prognostics.regression_models import (
    BaseSupervisedRegressionModel,
    RidgeRegressionPrognosticModel,
    HuberRegressionPrognosticModel,
    ParameterDecoupledRegressionPipeline,
)

__all__ = [
    "PrognosticInput",
    "PrognosticForecast",
    "CarryForwardModel",
    "TwoPointLinearModel",
    "TheilSenExtrapolationModel",
    "BaseSupervisedRegressionModel",
    "RidgeRegressionPrognosticModel",
    "HuberRegressionPrognosticModel",
    "ParameterDecoupledRegressionPipeline",
]

