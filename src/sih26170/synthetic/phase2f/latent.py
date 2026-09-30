"""SIH26170 Phase 2F Physics-Informed Latent State Generator.

Implements the latent physical state model decoupled from measurement mechanics:
- Log-space parameters (IDSS, RDS(on), IGSS): x*_i,p(t) = b_i,p * exp(g_i,p(t)) > 0 strictly
- Linear parameter (VGS(th)): x*_i,th(t) = b_i,th + g_i,th(t)
- Sourced physical baseline coupling at t=0 (wafer doping and gate oxide physics)
- Strict parameter-level drift kinetics g_i,p(t) satisfying g_i,p(0) = 0
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

from sih26170.synthetic.phase2f.config import Phase2FConfig, Phase2FParameterConfig
from sih26170.synthetic.phase2f.scenarios import (
    ComponentTrajectoryVector,
    ParameterScenario,
    Phase2FComponentPlan,
)


@dataclass(frozen=True)
class Phase2FLatentState:
    """Represents uncorrupted physical latent state x*(t) of component i, parameter p, at time t."""
    component_id: str
    lot_id: str
    parameter_name: str
    elapsed_hours: int
    true_value: float          # x*(t) in native physical units
    baseline_value: float      # b_{i,p} (value at t=0)
    drift_contribution: float  # g_{i,p}(t) in transform domain
    parameter_scenario: ParameterScenario
    transform: str
    snr: Optional[float] = None


class Phase2FLatentModel:
    """Generates the true underlying latent physical state across lots, components, and time."""

    def __init__(self, config: Phase2FConfig):
        self.config = config

    def sample_lot_baselines(
        self,
        rng_lot: np.random.Generator,
    ) -> Dict[str, float]:
        """Sample lot central tendencies mu_l,p for each parameter."""
        baselines: Dict[str, float] = {}
        for p_name, p_cfg in self.config.parameters.items():
            if p_cfg.transform == "log":
                offset = float(rng_lot.normal(0.0, p_cfg.lot_dispersion))
                baselines[p_name] = p_cfg.nominal_baseline * np.exp(offset)
            else:
                offset = float(rng_lot.normal(0.0, p_cfg.lot_dispersion))
                baselines[p_name] = p_cfg.nominal_baseline + offset
        return baselines

    def sample_component_baselines(
        self,
        lot_baselines: Dict[str, float],
        rng_comp: np.random.Generator,
        comp_id: str = "",
    ) -> Dict[str, float]:
        """Sample component initial baselines b_{i,p} with physical wafer-level covariance.
        
        Physics-informed correlations at wafer baseline:
        - Wafer doping coupling: rho_doping = -0.45 between ln(IDSS) and ln(RDS(on))
        - Gate oxide coupling: rho_oxide = +0.35 between VGS(th) and asinh(IGSS/scale)
        """
        # 1. Sample standard normals
        z_doping = float(rng_comp.normal(0.0, 1.0))
        z_idss_indep = float(rng_comp.normal(0.0, 1.0))
        z_rdson_indep = float(rng_comp.normal(0.0, 1.0))

        z_oxide = float(rng_comp.normal(0.0, 1.0))
        z_vgsth_indep = float(rng_comp.normal(0.0, 1.0))
        z_igss_indep = float(rng_comp.normal(0.0, 1.0))

        # 2. Correlated log-offsets for doping (rho = -0.45)
        rho_d = -0.45
        c_d = np.sqrt(1.0 - rho_d**2)
        eta_idss = (0.7 * z_doping + 0.7 * z_idss_indep) * self.config.parameters["IDSS"].device_dispersion
        eta_rdson = (rho_d * 0.7 * z_doping + c_d * z_rdson_indep) * self.config.parameters["RDS(on)"].device_dispersion

        # 3. Correlated offsets for gate oxide (rho = +0.35)
        rho_ox = 0.35
        c_ox = np.sqrt(1.0 - rho_ox**2)
        eta_vgsth = (0.6 * z_oxide + 0.8 * z_vgsth_indep) * self.config.parameters["VGS(th)"].device_dispersion
        eta_igss = (rho_ox * 0.6 * z_oxide + c_ox * z_igss_indep) * self.config.parameters["IGSS"].device_dispersion

        comp_baselines: Dict[str, float] = {}
        # Strictly positive log parameters: IDSS > 0, RDS(on) > 0
        comp_baselines["IDSS"] = lot_baselines["IDSS"] * np.exp(eta_idss)
        comp_baselines["RDS(on)"] = lot_baselines["RDS(on)"] * np.exp(eta_rdson)
        
        # Bounded linear parameter: VGS(th)
        comp_baselines["VGS(th)"] = lot_baselines["VGS(th)"] + eta_vgsth

        # Signed asinh parameter: IGSS in [-100, +100] nA
        # Polarity depends on gate bias condition (+20V vs -20V per MIL-PRF-19500/703 Table I)
        scale_igss = self.config.parameters["IGSS"].scale
        comp_idx = 1
        if "_C" in comp_id:
            try:
                comp_idx = int(comp_id.split("_C")[-1])
            except ValueError:
                comp_idx = 1

        sign_igss = 1.0 if (comp_idx % 2 == 1) else -1.0
        if comp_idx % 25 == 0:
            base_mag = 0.0  # Exactly zero gate leakage
        elif comp_idx % 25 == 12:
            base_mag = 0.02  # Near-zero leakage (20 pA)
        else:
            base_mag = lot_baselines["IGSS"]

        if base_mag == 0.0:
            comp_baselines["IGSS"] = 0.0
        else:
            u_0 = np.arcsinh(base_mag / scale_igss) + eta_igss
            comp_baselines["IGSS"] = sign_igss * scale_igss * float(np.sinh(max(0.0, u_0)))

        return comp_baselines

    def generate_component_parameter_series(
        self,
        component_plan: Phase2FComponentPlan,
        param_name: str,
        initial_baseline: float,
        rng_param: np.random.Generator,
    ) -> List[Phase2FLatentState]:
        """Generate latent time-series x*(t) for parameter p across checkpoints."""
        p_cfg = self.config.parameters[param_name]
        scenario = getattr(component_plan.trajectory_vector, param_name.replace("(th)", "th").replace("(on)", "on"))

        # Determine effective baseline at t=0
        if param_name in component_plan.initial_value_overrides:
            b_0 = component_plan.initial_value_overrides[param_name]
        else:
            b_0 = initial_baseline

        checkpoints = self.config.checkpoints
        states: List[Phase2FLatentState] = []
        achieved_snr: Optional[float] = None

        # Direction of degradation
        sign_drift = np.sign(b_0) if b_0 != 0.0 else 1.0
        s = p_cfg.scale

        # Determine drift trajectory g(t) in transform domain
        for t in checkpoints:
            g_t = 0.0

            if scenario in (
                ParameterScenario.STABLE,
                ParameterScenario.HIGH_BUT_STABLE,
                ParameterScenario.STATIC_LIMIT_BREACH,
                ParameterScenario.LOT_OUTLIER,
                ParameterScenario.INSUFFICIENT_DATA,
            ):
                # Strictly stationary across all checkpoints!
                g_t = 0.0

            elif scenario == ParameterScenario.LINEAR_DRIFT:
                # Monotonic linear wearout drift (e.g. HTRB mobile ion drift)
                if t > 0:
                    fraction = t / 168.0
                    if param_name in component_plan.snr_targets:
                        target_snr = component_plan.snr_targets[param_name]
                        delta_req = target_snr * p_cfg.noise_std
                        if p_cfg.transform == "log":
                            g_max = np.log(1.0 + (delta_req / abs(b_0)))
                        elif p_cfg.transform == "asinh":
                            u_target = np.arcsinh((b_0 + sign_drift * delta_req) / s)
                            g_max = abs(u_target - np.arcsinh(b_0 / s))
                        else:
                            g_max = delta_req
                        g_t = g_max * fraction
                    else:
                        rate = float(rng_param.uniform(0.6, 1.2))  # log drift ~ 1.8x to 3.3x
                        if p_cfg.transform == "linear":
                            rate = float(rng_param.uniform(0.25, 0.45))  # linear V drift
                        elif p_cfg.transform == "asinh":
                            rate = float(rng_param.uniform(0.8, 1.5))
                        g_t = rate * fraction

            elif scenario == ParameterScenario.ACCELERATING_DRIFT:
                # Accelerating power-law curvature (e.g. Coffin-Manson packaging fatigue)
                if t > 0:
                    fraction = (t / 168.0) ** 2.1
                    rate = float(rng_param.uniform(0.25, 0.50))  # ~ 30% to 65% increase in RDS(on)
                    if p_cfg.transform == "asinh":
                        rate = float(rng_param.uniform(0.5, 1.0))
                    g_t = rate * fraction

            elif scenario == ParameterScenario.SUBTLE_ABRUPT_CHANGE:
                # Abrupt step change emerging at t >= 96h (e.g. localized dielectric rupture)
                if t >= 96:
                    if param_name in component_plan.snr_targets:
                        target_snr = component_plan.snr_targets[param_name]
                        delta_req = target_snr * p_cfg.noise_std
                        if p_cfg.transform == "log":
                            g_t = np.log(1.0 + (delta_req / abs(b_0)))
                        elif p_cfg.transform == "asinh":
                            u_target = np.arcsinh((b_0 + sign_drift * delta_req) / s)
                            g_t = abs(u_target - np.arcsinh(b_0 / s))
                        else:
                            g_t = delta_req
                    else:
                        step_jump = float(rng_param.uniform(1.2, 1.8))
                        g_t = step_jump
                else:
                    g_t = 0.0

            elif scenario == ParameterScenario.EQUIPMENT_COMMON_MODE:
                # Equipment drift handled in measurement/common-mode layer; latent die remains nominal
                g_t = 0.0

            # Calculate true uncorrupted physical value x*(t)
            if p_cfg.transform == "log":
                # Strict positivity guaranteed: b_0 > 0, exp(g_t) > 0
                x_star = b_0 * np.exp(g_t)
            elif p_cfg.transform == "asinh":
                # Signed asinh transform for IGSS: preserves sign, zero, and small magnitudes
                u_0 = np.arcsinh(b_0 / s)
                u_t = u_0 + sign_drift * g_t
                x_star = s * np.sinh(u_t)
            else:
                x_star = b_0 + g_t
                # Guardrail: Silicon bandgap boundary clamping [0.5, 6.0] V
                x_star = float(np.clip(x_star, 0.5, 6.0))

            # Compute latent SNR strictly from latent state drift at t=168
            if t == 168:
                delta_phys = abs(x_star - b_0)
                achieved_snr = float(delta_phys / p_cfg.noise_std)

            states.append(Phase2FLatentState(
                component_id=component_plan.component_id,
                lot_id=component_plan.lot_id,
                parameter_name=param_name,
                elapsed_hours=t,
                true_value=float(x_star),
                baseline_value=float(b_0),
                drift_contribution=float(g_t),
                parameter_scenario=scenario,
                transform=p_cfg.transform,
                snr=achieved_snr if t == 168 else None,
            ))

        return states
