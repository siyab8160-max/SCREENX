"""SIH26170 Synthetic Trajectory Models.

Implements the 6 synthetic benchmark trajectory classes defined in docs/PHASE_2_SYNTHETIC_DATA_SPEC.md:
- stable
- high_but_stable
- lot_outlier
- linear_drift
- accelerating_drift
- abrupt_failure
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import numpy as np


class TrajectoryClass(str, Enum):
    """The 6 canonical synthetic trajectory classes."""
    STABLE = "stable"
    HIGH_BUT_STABLE = "high_but_stable"
    LOT_OUTLIER = "lot_outlier"
    LINEAR_DRIFT = "linear_drift"
    ACCELERATING_DRIFT = "accelerating_drift"
    ABRUPT_FAILURE = "abrupt_failure"


@dataclass(frozen=True)
class TrajectoryProfile:
    """Holds the mathematical parameters and time evaluation for a trajectory."""
    trajectory_class: TrajectoryClass
    parameter_name: str
    is_log_transform: bool
    trajectory_onset_hour: Optional[int]
    beta: float = 0.0
    gamma: float = 0.0
    jump_hour: Optional[int] = None
    delta_failure: float = 0.0

    def evaluate_g(self, t: int) -> float:
        """Evaluate latent trajectory contribution g(t).
        
        For log parameters: g(t) is dimensionless.
        For linear parameters: g(t) has native units (e.g. ns).
        """
        tc = self.trajectory_class
        if tc in (TrajectoryClass.STABLE, TrajectoryClass.HIGH_BUT_STABLE, TrajectoryClass.LOT_OUTLIER):
            return 0.0
        elif tc == TrajectoryClass.LINEAR_DRIFT:
            # Linear scaling with normalized time t / 168
            normalized_t = t / 168.0
            return self.beta * normalized_t
        elif tc == TrajectoryClass.ACCELERATING_DRIFT:
            normalized_t = t / 168.0
            return self.beta * normalized_t + self.gamma * (normalized_t ** 2)
        elif tc == TrajectoryClass.ABRUPT_FAILURE:
            if self.jump_hour is not None and t >= self.jump_hour:
                return self.delta_failure
            return 0.0
        return 0.0


def create_trajectory_profile(
    trajectory_class: TrajectoryClass,
    parameter_name: str,
    is_log_transform: bool,
    rng: np.random.Generator,
    checkpoints: List[int],
) -> TrajectoryProfile:
    """Generate a parameterized trajectory profile based on class and parameter type."""
    if trajectory_class in (TrajectoryClass.STABLE, TrajectoryClass.HIGH_BUT_STABLE, TrajectoryClass.LOT_OUTLIER):
        return TrajectoryProfile(
            trajectory_class=trajectory_class,
            parameter_name=parameter_name,
            is_log_transform=is_log_transform,
            trajectory_onset_hour=None,
        )

    elif trajectory_class == TrajectoryClass.LINEAR_DRIFT:
        # Onset hour: starts at hour 0
        onset_hour = 0
        if is_log_transform:
            # Dimensionless log drift: beta in [0.4, 0.8] yields exp(beta)-1 ~ +50% to +120% drift at 168h
            beta = float(rng.uniform(0.45, 0.85))
        else:
            # Linear delay drift in ns: beta in [0.5, 1.5] ns at 168h
            beta = float(rng.uniform(0.6, 1.4))
        return TrajectoryProfile(
            trajectory_class=trajectory_class,
            parameter_name=parameter_name,
            is_log_transform=is_log_transform,
            trajectory_onset_hour=onset_hour,
            beta=beta,
        )

    elif trajectory_class == TrajectoryClass.ACCELERATING_DRIFT:
        onset_hour = 0
        if is_log_transform:
            # Mild initial linear slope, strong quadratic acceleration
            beta = float(rng.uniform(0.15, 0.35))
            gamma = float(rng.uniform(0.60, 1.10))
        else:
            beta = float(rng.uniform(0.2, 0.5))
            gamma = float(rng.uniform(0.8, 1.5))
        return TrajectoryProfile(
            trajectory_class=trajectory_class,
            parameter_name=parameter_name,
            is_log_transform=is_log_transform,
            trajectory_onset_hour=onset_hour,
            beta=beta,
            gamma=gamma,
        )

    elif trajectory_class == TrajectoryClass.ABRUPT_FAILURE:
        # Jump hour chosen from available post-baseline checkpoints (24, 96, or 168)
        candidate_jumps = [cp for cp in checkpoints if cp > 0]
        jump_hour = int(rng.choice(candidate_jumps))
        onset_hour = jump_hour
        if is_log_transform:
            # Large jump in log space: delta ~ 2.0 to 3.5 (exp(3) ~ 20x jump)
            delta = float(rng.uniform(2.2, 3.8))
        else:
            # Large jump in delay (e.g. +5.0 to +10.0 ns)
            delta = float(rng.uniform(5.0, 9.0))
        return TrajectoryProfile(
            trajectory_class=trajectory_class,
            parameter_name=parameter_name,
            is_log_transform=is_log_transform,
            trajectory_onset_hour=onset_hour,
            jump_hour=jump_hour,
            delta_failure=delta,
        )

    raise ValueError(f"Unknown trajectory class: {trajectory_class}")
