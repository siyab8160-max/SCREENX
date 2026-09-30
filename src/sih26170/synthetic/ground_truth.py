"""SIH26170 Synthetic Ground Truth Evaluator.

Implements the independent synthetic ground-truth evaluation model strictly decoupled
from operational screening limits and detector algorithms:
- Dimensionless relative latent deviation:
    r_i,p(t) = [x*_i,p(t) - x*_i,p(0)] / x*_i,p(0)
    For log-space: exp(g_i,p(t)) - 1
    For linear: g_i,p(t) / x*_i,p(0)
- Parameter-specific synthetic benchmark thresholds:
    leakage_current: 0.50 (50% increase)
    iddq: 0.30 (30% increase)
    propagation_delay: 0.10 (10% increase)
- Event timing:
    trajectory_onset_hour: earliest checkpoint where |g(t)| > 0
    first_ground_truth_abnormal_hour: earliest checkpoint where |r(t)| >= θ or peer anomaly
    abnormal_by_24h, abnormal_by_96h, abnormal_by_168h

Conforms to docs/PHASE_2_SYNTHETIC_DATA_SPEC.md.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from sih26170.synthetic.config import SyntheticConfig
from sih26170.synthetic.latent import LatentState
from sih26170.synthetic.trajectories import TrajectoryClass, TrajectoryProfile


@dataclass(frozen=True)
class GroundTruthSummary:
    """Holds component-parameter-level ground truth summary labels."""
    component_id: str
    lot_id: str
    parameter_name: str
    trajectory_class: str
    trajectory_onset_hour: Optional[int]
    first_abnormal_hour: Optional[int]
    abnormal_by_24h: bool
    abnormal_by_96h: bool
    abnormal_by_168h: bool
    theta_threshold: float


@dataclass(frozen=True)
class GroundTruthRecord:
    """Checkpoint-level ground truth record containing latent state and defect labels."""
    component_id: str
    lot_id: str
    parameter_name: str
    elapsed_hours: int
    trajectory_class: str
    trajectory_onset_hour: Optional[int]
    first_abnormal_hour: Optional[int]
    abnormal_by_24h: bool
    abnormal_by_96h: bool
    abnormal_by_168h: bool
    latent_value: float
    relative_latent_deviation_r: float


def compute_relative_deviation(latent_series: List[LatentState]) -> Dict[int, float]:
    """Compute dimensionless relative latent deviation r(t) for each checkpoint.
    
    r(t) = [x*(t) - x*(0)] / x*(0)
    """
    if not latent_series:
        return {}
    
    # Sort by elapsed hours
    sorted_states = sorted(latent_series, key=lambda s: s.elapsed_hours)
    x_star_0 = sorted_states[0].latent_value

    r_map = {}
    for state in sorted_states:
        t = state.elapsed_hours
        if x_star_0 == 0.0:
            r_val = 0.0
        else:
            r_val = (state.latent_value - x_star_0) / x_star_0
        r_map[t] = float(r_val)
    return r_map


def evaluate_ground_truth(
    latent_series: List[LatentState],
    trajectory_profile: TrajectoryProfile,
    config: SyntheticConfig,
) -> Tuple[GroundTruthSummary, List[GroundTruthRecord]]:
    """Evaluate synthetic ground truth independently of detectors and screening limits."""
    sorted_states = sorted(latent_series, key=lambda s: s.elapsed_hours)
    component_id = sorted_states[0].component_id
    lot_id = sorted_states[0].lot_id
    parameter_name = sorted_states[0].parameter_name
    tc = trajectory_profile.trajectory_class

    param_config = config.get_parameter(parameter_name)
    theta = param_config.theta_abnormal

    # Compute dimensionless relative deviation r(t)
    r_map = compute_relative_deviation(sorted_states)

    # 1. Determine trajectory onset hour: earliest checkpoint where |g(t)| > 1e-6
    onset_hour: Optional[int] = None
    for state in sorted_states:
        if abs(state.trajectory_contribution) > 1e-6:
            onset_hour = state.elapsed_hours
            break

    # 2. Determine first ground truth abnormal hour
    first_abnormal: Optional[int] = None

    if tc in (TrajectoryClass.HIGH_BUT_STABLE, TrajectoryClass.LOT_OUTLIER):
        # Peer-level static anomaly present from hour 0
        first_abnormal = 0
        onset_hour = None  # Stationary: no dynamic drift onset

    elif tc == TrajectoryClass.STABLE:
        first_abnormal = None
        onset_hour = None

    elif tc in (TrajectoryClass.LINEAR_DRIFT, TrajectoryClass.ACCELERATING_DRIFT):
        # Earliest checkpoint where relative latent deviation |r(t)| >= theta
        for state in sorted_states:
            t = state.elapsed_hours
            if abs(r_map[t]) >= theta:
                first_abnormal = t
                break

    elif tc == TrajectoryClass.ABRUPT_FAILURE:
        # Catastrophic jump occurs at or before checkpoint
        jump_h = trajectory_profile.jump_hour
        for state in sorted_states:
            t = state.elapsed_hours
            if jump_h is not None and t >= jump_h:
                first_abnormal = t
                break

    # 3. Checkpoint evaluation flags
    abnormal_24 = bool(first_abnormal is not None and first_abnormal <= 24)
    abnormal_96 = bool(first_abnormal is not None and first_abnormal <= 96)
    abnormal_168 = bool(first_abnormal is not None and first_abnormal <= 168)

    summary = GroundTruthSummary(
        component_id=component_id,
        lot_id=lot_id,
        parameter_name=parameter_name,
        trajectory_class=tc.value,
        trajectory_onset_hour=onset_hour,
        first_abnormal_hour=first_abnormal,
        abnormal_by_24h=abnormal_24,
        abnormal_by_96h=abnormal_96,
        abnormal_by_168h=abnormal_168,
        theta_threshold=theta,
    )

    records: List[GroundTruthRecord] = []
    for state in sorted_states:
        t = state.elapsed_hours
        rec = GroundTruthRecord(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            elapsed_hours=t,
            trajectory_class=tc.value,
            trajectory_onset_hour=onset_hour,
            first_abnormal_hour=first_abnormal,
            abnormal_by_24h=abnormal_24,
            abnormal_by_96h=abnormal_96,
            abnormal_by_168h=abnormal_168,
            latent_value=state.latent_value,
            relative_latent_deviation_r=r_map[t],
        )
        records.append(rec)

    return summary, records
