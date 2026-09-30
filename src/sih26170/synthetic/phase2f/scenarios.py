"""SIH26170 Phase 2F Scenario Manager.

Implements parameter-selective trajectory vectors T_i = [T_i(IDSS), T_i(VGSth), T_i(RDSon), T_i(IGSS)]
and the Phase 2E statistical scenario taxonomy.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import numpy as np

from sih26170.synthetic.phase2f.config import Phase2FConfig, Phase2FLotConfig


class ParameterScenario(str, Enum):
    """Statistical scenario taxonomy for individual physical parameters.
    
    Names reflect benchmark evaluation roles, NOT certified physical failure modes.
    """
    STABLE = "stable"
    HIGH_BUT_STABLE = "high_but_stable"
    STATIC_LIMIT_BREACH = "static_limit_breach"  # Temporally stationary, specification non-compliant at t=0
    LOT_OUTLIER = "lot_outlier"
    LINEAR_DRIFT = "linear_drift"
    ACCELERATING_DRIFT = "accelerating_drift"
    SUBTLE_ABRUPT_CHANGE = "subtle_abrupt_change"
    EQUIPMENT_COMMON_MODE = "equipment_common_mode"
    MIXED_COMPOUND = "mixed_compound"
    INSUFFICIENT_DATA = "insufficient_data"


class ComponentScenario(str, Enum):
    """Component-level benchmark role taxonomy.
    
    Classifies the role of the physical component under test.
    """
    STABLE = "stable"
    HIGH_BUT_STABLE = "high_but_stable"
    STATIC_LIMIT_BREACH = "static_limit_breach"
    LOT_OUTLIER = "lot_outlier"
    LINEAR_DRIFT = "linear_drift"
    ACCELERATING_DRIFT = "accelerating_drift"
    SUBTLE_ABRUPT_CHANGE = "subtle_abrupt_change"
    EQUIPMENT_COMMON_MODE = "equipment_common_mode"
    MIXED_COMPOUND = "mixed_compound"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class ComponentTrajectoryVector:
    """Independent parameter trajectory vector T_i for component i."""
    IDSS: ParameterScenario
    VGSth: ParameterScenario
    RDSon: ParameterScenario
    IGSS: ParameterScenario

    def to_dict(self) -> Dict[str, str]:
        return {
            "IDSS": self.IDSS.value,
            "VGS(th)": self.VGSth.value,
            "RDS(on)": self.RDSon.value,
            "IGSS": self.IGSS.value,
        }

    def is_homogeneous(self) -> bool:
        """Returns True if all four parameters share the exact same scenario profile.
        
        Used for the critical anti-regression check against the 99.75% Phase 2C pathology.
        """
        return self.IDSS == self.VGSth == self.RDSon == self.IGSS

    def is_any_abnormal(self) -> bool:
        """Returns True if any parameter is non-stable."""
        return any(
            s not in (ParameterScenario.STABLE, ParameterScenario.HIGH_BUT_STABLE)
            for s in (self.IDSS, self.VGSth, self.RDSon, self.IGSS)
        )


@dataclass(frozen=True)
class Phase2FComponentPlan:
    """Plan specifying generative attributes for a single component in Phase 2F."""
    component_id: str
    lot_id: str
    rework_count: int
    chamber_id: str
    instrument_id: str
    channel_id: str
    socket_id: str
    trajectory_vector: ComponentTrajectoryVector
    scenario_tag: str
    component_scenario: str = "stable"
    initial_value_overrides: Dict[str, float] = field(default_factory=dict)
    snr_targets: Dict[str, float] = field(default_factory=dict)
    missing_checkpoints: Dict[str, List[int]] = field(default_factory=dict)
    correlation_origins: Dict[str, str] = field(default_factory=dict)


class Phase2FScenarioManager:
    """Orchestrates parameter-selective component scenario planning across lots."""

    def __init__(self, config: Phase2FConfig):
        self.config = config

    def plan_lot(
        self,
        lot_cfg: Phase2FLotConfig,
        rng_lot: np.random.Generator,
    ) -> List[Phase2FComponentPlan]:
        """Generate component plans for an entire lot according to its profile."""
        plans: List[Phase2FComponentPlan] = []
        n_comps = lot_cfg.size
        instruments = self.config.equipment.instruments
        ch_per_inst = self.config.equipment.channels_per_instrument

        profile = lot_cfg.scenario_profile

        for i in range(n_comps):
            comp_id = f"{lot_cfg.lot_id}_C{i+1:03d}"
            inst_idx = (i // ch_per_inst) % len(instruments)
            inst_id = instruments[inst_idx]
            ch_idx = (i % ch_per_inst) + 1
            ch_id = f"CH_{ch_idx:02d}"
            socket_id = f"{lot_cfg.chamber_id}_SOCK_{i+1:03d}"

            # Baseline assignment: realistic wafer spatial variation (edge effects, radial gradients)
            # In physical semiconductor fabrication, ~50% of dice are central pure nominals,
            # while ~50% have parameter-selective baseline variations (e.g. edge surface leakage,
            # radial oxide thickness, or epilayer resistivity) while remaining stable and compliant.
            overrides: Dict[str, float] = {}
            snr_targets: Dict[str, float] = {}
            missing_pts: Dict[str, List[int]] = {}
            corr_origins: Dict[str, str] = {
                "IDSS": "independent_nominal",
                "VGS(th)": "independent_nominal",
                "RDS(on)": "independent_nominal",
                "IGSS": "independent_nominal",
            }

            comp_scenario = ComponentScenario.STABLE.value

            if (i % 6) == 1:
                vec = ComponentTrajectoryVector(
                    IDSS=ParameterScenario.HIGH_BUT_STABLE,
                    VGSth=ParameterScenario.STABLE,
                    RDSon=ParameterScenario.STABLE,
                    IGSS=ParameterScenario.STABLE,
                )
                scenario_tag = "wafer_edge_idss_high"
                comp_scenario = ComponentScenario.HIGH_BUT_STABLE.value
                overrides["IDSS"] = float(rng_lot.uniform(1.8, 3.2))
                corr_origins["IDSS"] = "lot_level_process_variation"
            elif (i % 6) == 3:
                vec = ComponentTrajectoryVector(
                    IDSS=ParameterScenario.STABLE,
                    VGSth=ParameterScenario.HIGH_BUT_STABLE,
                    RDSon=ParameterScenario.STABLE,
                    IGSS=ParameterScenario.STABLE,
                )
                scenario_tag = "wafer_radial_vgsth_variation"
                comp_scenario = ComponentScenario.HIGH_BUT_STABLE.value
                overrides["VGS(th)"] = float(rng_lot.uniform(3.35, 3.75))
                corr_origins["VGS(th)"] = "lot_level_process_variation"
            elif (i % 6) == 5:
                vec = ComponentTrajectoryVector(
                    IDSS=ParameterScenario.STABLE,
                    VGSth=ParameterScenario.STABLE,
                    RDSon=ParameterScenario.HIGH_BUT_STABLE,
                    IGSS=ParameterScenario.STABLE,
                )
                scenario_tag = "epilayer_thickness_rdson_variation"
                comp_scenario = ComponentScenario.HIGH_BUT_STABLE.value
                overrides["RDS(on)"] = float(rng_lot.uniform(53.0, 58.0))
                corr_origins["RDS(on)"] = "lot_level_process_variation"
            else:
                vec = ComponentTrajectoryVector(
                    IDSS=ParameterScenario.STABLE,
                    VGSth=ParameterScenario.STABLE,
                    RDSon=ParameterScenario.STABLE,
                    IGSS=ParameterScenario.STABLE,
                )
                scenario_tag = "nominal_stable"
                comp_scenario = ComponentScenario.STABLE.value

            # Selective assignment based on lot scenario profile
            if profile == "small_lot_insufficient_data":
                # Small lot (< 8) where peer statistics are insufficient
                vec = ComponentTrajectoryVector(
                    IDSS=ParameterScenario.INSUFFICIENT_DATA,
                    VGSth=ParameterScenario.INSUFFICIENT_DATA,
                    RDSon=ParameterScenario.INSUFFICIENT_DATA,
                    IGSS=ParameterScenario.INSUFFICIENT_DATA,
                )
                scenario_tag = "small_lot_insufficient_data"
                comp_scenario = ComponentScenario.INSUFFICIENT_DATA.value

            elif profile == "htrb_leakage_drift":
                # Parameter-selective: HTRB mobile ion drift affects IDSS only!
                if i in (0, 1, 2):  # 3 abnormal components out of 30
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.LINEAR_DRIFT,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STABLE,
                    )
                    scenario_tag = "htrb_idss_drift"
                    comp_scenario = ComponentScenario.LINEAR_DRIFT.value
                    corr_origins["IDSS"] = "parameter_specific_degradation"

            elif profile == "htgb_threshold_drift":
                # Parameter-selective: HTGB BTI shifts VGS(th) only!
                if i in (0, 1, 2):
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.STABLE,
                        VGSth=ParameterScenario.LINEAR_DRIFT,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STABLE,
                    )
                    scenario_tag = "htgb_vgsth_drift"
                    comp_scenario = ComponentScenario.LINEAR_DRIFT.value
                    corr_origins["VGS(th)"] = "parameter_specific_degradation"

            elif profile == "thermal_power_drift":
                # Parameter-selective: Thermal fatigue voiding affects RDS(on) only!
                if i in (0, 1, 2):
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.STABLE,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.ACCELERATING_DRIFT,
                        IGSS=ParameterScenario.STABLE,
                    )
                    scenario_tag = "thermal_rdson_accel_drift"
                    comp_scenario = ComponentScenario.ACCELERATING_DRIFT.value
                    corr_origins["RDS(on)"] = "parameter_specific_degradation"

            elif profile == "subtle_failure_drift":
                # Subtle failures calibrated to SNR 1.5 - 2.5
                if i in (0, 1, 2):
                    snr_val = float(rng_lot.uniform(self.config.subtle_snr_min, self.config.subtle_snr_max))
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.LINEAR_DRIFT,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STABLE,
                    )
                    scenario_tag = "subtle_idss_drift"
                    comp_scenario = ComponentScenario.LINEAR_DRIFT.value
                    snr_targets["IDSS"] = snr_val
                    corr_origins["IDSS"] = "parameter_specific_degradation"

            elif profile == "static_limit_breach_lot":
                # Stationary components exceeding limits at t=0 without temporal drift
                if i in (0, 1):
                    # Breach on IDSS: starts at 11.5 uA > 10.0 uA limit, perfectly stationary
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.STATIC_LIMIT_BREACH,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STABLE,
                    )
                    overrides["IDSS"] = 11.50
                    scenario_tag = "static_limit_breach_idss"
                    comp_scenario = ComponentScenario.STATIC_LIMIT_BREACH.value
                    corr_origins["IDSS"] = "independent_anomaly_injection"
                elif i == 2:
                    # Breach on VGS(th): starts at 1.85 V < 2.0 V min limit, perfectly stationary
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.STABLE,
                        VGSth=ParameterScenario.STATIC_LIMIT_BREACH,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STABLE,
                    )
                    overrides["VGS(th)"] = 1.85
                    scenario_tag = "static_limit_breach_vgsth"
                    comp_scenario = ComponentScenario.STATIC_LIMIT_BREACH.value
                    corr_origins["VGS(th)"] = "independent_anomaly_injection"
                elif i == 3:
                    # Negative breach on IGSS: starts at -115 nA < -100 nA min limit, perfectly stationary
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.STABLE,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STATIC_LIMIT_BREACH,
                    )
                    overrides["IGSS"] = -115.0
                    scenario_tag = "static_limit_breach_igss_neg"
                    comp_scenario = ComponentScenario.STATIC_LIMIT_BREACH.value
                    corr_origins["IGSS"] = "independent_anomaly_injection"
                elif i == 4:
                    # Positive breach on IGSS: starts at +120 nA > +100 nA max limit, perfectly stationary
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.STABLE,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STATIC_LIMIT_BREACH,
                    )
                    overrides["IGSS"] = 120.0
                    scenario_tag = "static_limit_breach_igss_pos"
                    comp_scenario = ComponentScenario.STATIC_LIMIT_BREACH.value
                    corr_origins["IGSS"] = "independent_anomaly_injection"
                elif i == 5:
                    # Breach on RDS(on): starts at 68.0 mOhm > 60.0 mOhm max limit, perfectly stationary
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.STABLE,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.STATIC_LIMIT_BREACH,
                        IGSS=ParameterScenario.STABLE,
                    )
                    overrides["RDS(on)"] = 68.0
                    scenario_tag = "static_limit_breach_rdson"
                    comp_scenario = ComponentScenario.STATIC_LIMIT_BREACH.value
                    corr_origins["RDS(on)"] = "independent_anomaly_injection"
                elif i == 6:
                    # Explicit stationary zero IGSS component
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.STABLE,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STABLE,
                    )
                    overrides["IGSS"] = 0.0
                    scenario_tag = "stationary_zero_igss"
                    comp_scenario = ComponentScenario.STABLE.value
                elif i == 7:
                    # Explicit stationary near-zero IGSS component (-0.05 nA)
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.STABLE,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STABLE,
                    )
                    overrides["IGSS"] = -0.05
                    scenario_tag = "stationary_near_zero_igss"
                    comp_scenario = ComponentScenario.STABLE.value

            elif profile == "chamber_common_mode":
                # Chamber temperature drift affects temperature-dependent parameters
                vec = ComponentTrajectoryVector(
                    IDSS=ParameterScenario.EQUIPMENT_COMMON_MODE,
                    VGSth=ParameterScenario.EQUIPMENT_COMMON_MODE,
                    RDSon=ParameterScenario.EQUIPMENT_COMMON_MODE,
                    IGSS=ParameterScenario.STABLE,
                )
                scenario_tag = "chamber_common_mode_drift"
                comp_scenario = ComponentScenario.EQUIPMENT_COMMON_MODE.value
                corr_origins["IDSS"] = "chamber_common_mode_effect"
                corr_origins["VGS(th)"] = "chamber_common_mode_effect"
                corr_origins["RDS(on)"] = "chamber_common_mode_effect"

            elif profile == "channel_calibration_bias":
                # Channel bias on biased channel sockets
                if lot_cfg.bias_channel_id and ch_id == lot_cfg.bias_channel_id:
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.EQUIPMENT_COMMON_MODE,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STABLE,
                    )
                    scenario_tag = "ate_channel_bias"
                    comp_scenario = ComponentScenario.EQUIPMENT_COMMON_MODE.value
                    corr_origins["IDSS"] = "ate_channel_bias"

            elif profile == "mixed_compound_anomaly":
                # Complex mixed anomalies: discordant trajectories across parameters
                if i in (0, 1):
                    comp_scenario = ComponentScenario.MIXED_COMPOUND.value
                if i == 0:
                    # IDSS linear drift + VGS(th) subtle abrupt change
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.LINEAR_DRIFT,
                        VGSth=ParameterScenario.SUBTLE_ABRUPT_CHANGE,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STABLE,
                    )
                    scenario_tag = "compound_leakage_and_threshold"
                    corr_origins["IDSS"] = "shared_latent_degradation"
                    corr_origins["VGS(th)"] = "shared_latent_degradation"
                elif i == 1:
                    # High but stable on IDSS + accelerating drift on RDSon
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.HIGH_BUT_STABLE,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.ACCELERATING_DRIFT,
                        IGSS=ParameterScenario.STABLE,
                    )
                    overrides["IDSS"] = 2.50
                    scenario_tag = "static_high_and_thermal_drift"
                    corr_origins["RDS(on)"] = "parameter_specific_degradation"
                elif i == 2:
                    # Dielectric pinhole rupture on IGSS only!
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.STABLE,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.SUBTLE_ABRUPT_CHANGE,
                    )
                    scenario_tag = "igss_dielectric_rupture"
                    comp_scenario = ComponentScenario.SUBTLE_ABRUPT_CHANGE.value
                    corr_origins["IGSS"] = "parameter_specific_degradation"

            elif profile == "wafer_sensitivity_large":
                # Large lot (N=50) with diverse isolated anomalies
                if i == 0:
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.HIGH_BUT_STABLE,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STABLE,
                    )
                    overrides["IDSS"] = 3.20
                    scenario_tag = "high_but_stable_isolated"
                    comp_scenario = ComponentScenario.HIGH_BUT_STABLE.value
                elif i == 1:
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.LINEAR_DRIFT,
                        VGSth=ParameterScenario.STABLE,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STABLE,
                    )
                    scenario_tag = "idss_linear_isolated"
                    comp_scenario = ComponentScenario.LINEAR_DRIFT.value
                elif i == 2:
                    vec = ComponentTrajectoryVector(
                        IDSS=ParameterScenario.STABLE,
                        VGSth=ParameterScenario.LOT_OUTLIER,
                        RDSon=ParameterScenario.STABLE,
                        IGSS=ParameterScenario.STABLE,
                    )
                    overrides["VGS(th)"] = 3.65
                    scenario_tag = "vgsth_lot_outlier"
                    comp_scenario = ComponentScenario.LOT_OUTLIER.value

            # Missingness assignment (deterministic non-imputed dropout)
            if rng_lot.uniform(0.0, 1.0) < self.config.missingness.random_dropout_rate:
                # Randomly drop checkpoint 96 for one parameter
                drop_param = str(rng_lot.choice(["IDSS", "VGS(th)", "RDS(on)", "IGSS"]))
                missing_pts[drop_param] = [96]

            plans.append(Phase2FComponentPlan(
                component_id=comp_id,
                lot_id=lot_cfg.lot_id,
                rework_count=lot_cfg.rework_count,
                chamber_id=lot_cfg.chamber_id,
                instrument_id=inst_id,
                channel_id=ch_id,
                socket_id=socket_id,
                trajectory_vector=vec,
                scenario_tag=scenario_tag,
                component_scenario=comp_scenario,
                initial_value_overrides=overrides,
                snr_targets=snr_targets,
                missing_checkpoints=missing_pts,
                correlation_origins=corr_origins,
            ))

        return plans
