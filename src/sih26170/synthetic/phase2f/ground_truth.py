"""SIH26170 Phase 2F Ground Truth Evaluation Engine.

Generates quarantined evaluation ground truth strictly separated from observation data:
- Evaluates temporal degradation vs specification compliance independently
- Handles static_limit_breach where temporal degradation = False and spec compliance = False
- Records exact correlation engine origins and subtle failure SNR metrics
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from sih26170.synthetic.phase2f.config import Phase2FConfig, Phase2FParameterConfig
from sih26170.synthetic.phase2f.latent import Phase2FLatentState
from sih26170.synthetic.phase2f.scenarios import ParameterScenario, Phase2FComponentPlan


@dataclass(frozen=True)
class Phase2FGroundTruthRecord:
    """Quarantined evaluation record for component i, parameter p, at checkpoint t."""
    component_id: str
    lot_id: str
    parameter_name: str
    elapsed_hours: int
    parameter_scenario: str
    is_temporally_degraded: bool
    is_spec_compliant: bool
    is_abnormal: bool
    first_abnormal_hour: Optional[int]
    achieved_snr: Optional[float]
    correlation_origin: str
    as_of_hours: int


def evaluate_phase2f_ground_truth(
    latent_states: List[Phase2FLatentState],
    plan: Phase2FComponentPlan,
    param_cfg: Phase2FParameterConfig,
) -> List[Phase2FGroundTruthRecord]:
    """Evaluate ground truth for a parameter time-series."""
    p_name = param_cfg.name
    scenario = getattr(plan.trajectory_vector, p_name.replace("(th)", "th").replace("(on)", "on"))
    corr_origin = plan.correlation_origins.get(p_name, "independent_nominal")

    # 1. Determine temporal degradation status
    # Stationary scenarios have is_temporally_degraded = False!
    is_degraded = scenario in (
        ParameterScenario.LINEAR_DRIFT,
        ParameterScenario.ACCELERATING_DRIFT,
        ParameterScenario.SUBTLE_ABRUPT_CHANGE,
    )

    # 2. Determine first abnormal hour
    first_abnormal: Optional[int] = None
    if scenario in (ParameterScenario.STATIC_LIMIT_BREACH, ParameterScenario.LOT_OUTLIER):
        first_abnormal = 0
    elif scenario in (ParameterScenario.LINEAR_DRIFT, ParameterScenario.ACCELERATING_DRIFT):
        first_abnormal = 24  # early departure
    elif scenario == ParameterScenario.SUBTLE_ABRUPT_CHANGE:
        first_abnormal = 96
    elif scenario == ParameterScenario.EQUIPMENT_COMMON_MODE:
        first_abnormal = 96

    records: List[Phase2FGroundTruthRecord] = []
    achieved_snr = latent_states[-1].snr  # SNR at 168h if available

    for state in latent_states:
        t = state.elapsed_hours
        val = state.true_value

        # 3. Check specification compliance against Table I limits
        is_compliant = True
        if param_cfg.absolute_max is not None and val > param_cfg.absolute_max:
            is_compliant = False
        if param_cfg.absolute_min is not None and val < param_cfg.absolute_min:
            is_compliant = False

        # 4. Determine overall anomaly status
        # Anomaly if degraded OR non-compliant OR extreme lot outlier OR common-mode
        is_abnormal = False
        if not is_compliant:
            is_abnormal = True
        elif is_degraded and t >= (first_abnormal or 999):
            is_abnormal = True
        elif scenario == ParameterScenario.LOT_OUTLIER:
            is_abnormal = True
        elif scenario == ParameterScenario.EQUIPMENT_COMMON_MODE and t == 96:
            is_abnormal = True

        records.append(Phase2FGroundTruthRecord(
            component_id=plan.component_id,
            lot_id=plan.lot_id,
            parameter_name=p_name,
            elapsed_hours=t,
            parameter_scenario=scenario.value,
            is_temporally_degraded=is_degraded,
            is_spec_compliant=is_compliant,
            is_abnormal=is_abnormal,
            first_abnormal_hour=first_abnormal if is_abnormal else None,
            achieved_snr=achieved_snr if is_degraded else None,
            correlation_origin=corr_origin,
            as_of_hours=t,
        ))

    return records
