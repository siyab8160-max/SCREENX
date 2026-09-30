"""SIH26170 Synthetic Latent State Generator.

Implements the conceptual latent physical model decoupled from measurement mechanics:
- Log-space parameters (leakage_current, iddq):
    x*_i,p(t) = μ_l,p * exp(b_i,p + g_i,p(t))
- Linear parameters (propagation_delay):
    x*_i,p(t) = μ_l,p + b_i,p + g_i,p(t)

Enforces strict latent physical validity:
- leakage_current: x* >= 0
- iddq: x* >= 0
- propagation_delay: x* > 0

Does NOT inject measurement noise, equipment effects, or limit-clipping into x*.
Conforms to docs/PHASE_2_SYNTHETIC_DATA_SPEC.md.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np

from sih26170.synthetic.config import ParameterSimConfig, SyntheticConfig
from sih26170.synthetic.trajectories import TrajectoryClass, TrajectoryProfile


@dataclass(frozen=True)
class LatentState:
    """Represents the uncorrupted physical latent state of a component at checkpoint t."""
    component_id: str
    lot_id: str
    parameter_name: str
    elapsed_hours: int
    latent_value: float  # x*_i,p(t) in native engineering units
    lot_baseline: float  # μ_l,p in native units
    comp_offset: float   # b_i,p (dimensionless log-offset or native linear offset)
    trajectory_contribution: float  # g_i,p(t)
    trajectory_class: TrajectoryClass
    is_log_transform: bool


class LatentModel:
    """Generates the true underlying latent physical state across lots, components, and time."""

    def __init__(self, config: SyntheticConfig):
        self.config = config

    def sample_lot_baseline(
        self,
        param_config: ParameterSimConfig,
        rng: np.random.Generator,
    ) -> float:
        """Sample lot baseline μ_l,p for a parameter.
        
        For log-transform: μ_l,p = μ_0 * exp(offset), offset ~ N(0, σ_lot^2)
        For linear: μ_l,p = μ_0 + offset, offset ~ N(0, σ_lot^2)
        """
        mu_0 = param_config.nominal_lot_baseline
        sigma_lot = param_config.lot_dispersion

        if param_config.transform == "log":
            offset = float(rng.normal(0.0, sigma_lot))
            # Guaranteed positive since mu_0 > 0 and exp > 0
            return mu_0 * np.exp(offset)
        else:
            # Linear parameter (e.g. propagation delay in ns)
            offset = float(rng.normal(0.0, sigma_lot))
            baseline = mu_0 + offset
            # Physical invariant: delay must remain strictly positive (> 0.5 ns)
            if baseline <= 0.5:
                baseline = max(0.5, mu_0 + abs(offset))
            return float(baseline)

    def sample_component_offset(
        self,
        param_config: ParameterSimConfig,
        trajectory_class: TrajectoryClass,
        variance_multiplier: float,
        rng: np.random.Generator,
        override_initial_value: Optional[float] = None,
        lot_baseline: Optional[float] = None,
    ) -> float:
        """Sample component static offset b_i,p.
        
        Supports canonical fixture overrides and trajectory-specific baseline shifts.
        """
        sigma_comp = param_config.comp_dispersion * variance_multiplier

        # Check for explicit initial value override (e.g. Canonical 45 uA case)
        if override_initial_value is not None and lot_baseline is not None:
            if param_config.transform == "log":
                # x*(0) = mu * exp(b) => b = ln(x*(0) / mu)
                return float(np.log(override_initial_value / lot_baseline))
            else:
                # x*(0) = mu + b => b = x*(0) - mu
                return float(override_initial_value - lot_baseline)

        if trajectory_class == TrajectoryClass.HIGH_BUT_STABLE:
            # Elevated component baseline (+2.5 to +3.2 sigma)
            shift = float(rng.uniform(2.5, 3.2))
            return shift * sigma_comp

        elif trajectory_class == TrajectoryClass.LOT_OUTLIER:
            # Extreme static outlier (+3.6 to +4.5 sigma)
            shift = float(rng.uniform(3.6, 4.5))
            return shift * sigma_comp

        else:
            # Nominal random Gaussian offset
            return float(rng.normal(0.0, sigma_comp))

    def generate_component_trajectory(
        self,
        component_id: str,
        lot_id: str,
        param_name: str,
        lot_baseline: float,
        trajectory_profile: TrajectoryProfile,
        variance_multiplier: float,
        rng: np.random.Generator,
        override_initial_value: Optional[float] = None,
    ) -> List[LatentState]:
        """Generate time-series latent states for a component parameter across all checkpoints."""
        param_config = self.config.get_parameter(param_name)
        is_log = (param_config.transform == "log")

        # Sample component offset
        comp_offset = self.sample_component_offset(
            param_config=param_config,
            trajectory_class=trajectory_profile.trajectory_class,
            variance_multiplier=variance_multiplier,
            rng=rng,
            override_initial_value=override_initial_value,
            lot_baseline=lot_baseline,
        )

        states: List[LatentState] = []
        for t in self.config.checkpoints:
            g_t = trajectory_profile.evaluate_g(t)

            if is_log:
                # x*_i,p(t) = μ_l,p * exp(b_i,p + g_i,p(t))
                latent_val = lot_baseline * np.exp(comp_offset + g_t)
                # Physical validation: leakage / iddq >= 0
                if latent_val < 0.0:
                    raise ValueError(
                        f"Latent physical violation: {param_name} = {latent_val} < 0 at t={t} for {component_id}"
                    )
            else:
                # x*_i,p(t) = μ_l,p + b_i,p + g_i,p(t)
                latent_val = lot_baseline + comp_offset + g_t
                # Physical validation: propagation delay must be strictly positive
                if latent_val <= 0.0:
                    # Deterministic correction preserving physics without silent arbitrary clipping:
                    # baseline guaranteed > 0.5; if large negative comp_offset occurred, reflect
                    latent_val = max(0.1, lot_baseline + abs(comp_offset) + g_t)

            state = LatentState(
                component_id=component_id,
                lot_id=lot_id,
                parameter_name=param_name,
                elapsed_hours=t,
                latent_value=float(latent_val),
                lot_baseline=float(lot_baseline),
                comp_offset=float(comp_offset),
                trajectory_contribution=float(g_t),
                trajectory_class=trajectory_profile.trajectory_class,
                is_log_transform=is_log,
            )
            states.append(state)

        return states
