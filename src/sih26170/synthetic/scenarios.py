"""SIH26170 Synthetic Scenario Manager.

Orchestrates lot populations, component assignments, rework regimes (R0, R1, R2),
equipment test-bench configurations, and the 11 canonical adversarial mixed scenarios (M01–M11):
- M01: high_but_stable + noise
- M02: high_but_stable + missing checkpoint (96h)
- M03: linear_drift + noise
- M04: linear_drift + equipment shift
- M05: accelerating_drift + missing checkpoint (96h)
- M06: lot_outlier + small lot (N=5)
- M07: stable + channel shift
- M08: reworked + stable (R0/R1)
- M09: reworked + genuine drift (R2)
- M10: equipment shift + 1 real defect
- M11: lot masking (4 defects in N=30)
- Canonical 45 uA fixture

Conforms to docs/PHASE_2_SYNTHETIC_DATA_SPEC.md.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np

from sih26170.synthetic.config import LotSimConfig, SyntheticConfig
from sih26170.synthetic.measurement import EquipmentContext
from sih26170.synthetic.trajectories import (
    TrajectoryClass,
    TrajectoryProfile,
    create_trajectory_profile,
)


@dataclass(frozen=True)
class ComponentPlan:
    """Plan specifying generative attributes for a single component."""
    component_id: str
    lot_id: str
    rework_count: int
    variance_multiplier: float
    instrument_id: str
    channel_id: str
    scenario_tag: str
    # parameter_name -> TrajectoryProfile
    trajectory_profiles: Dict[str, TrajectoryProfile]
    # parameter_name -> initial value override (optional, e.g. 45.0 for canonical)
    initial_value_overrides: Dict[str, float] = field(default_factory=dict)
    # Checkpoints to drop for missingness simulation (e.g. {96})
    missing_checkpoints: List[int] = field(default_factory=list)
    # Parameter-specific noise scale multiplier
    noise_scale_multiplier: float = 1.0


class ScenarioManager:
    """Manages scenario generation and component assignments across lots."""

    def __init__(self, config: SyntheticConfig):
        self.config = config

    def sample_rework_count(self, regime: str, rng: np.random.Generator) -> int:
        """Sample rework count based on lot rework regime."""
        if regime in ("R0", "R1"):
            # Rework assigned independently of defect status (e.g. 80% 0, 15% 1, 5% 2)
            p = [0.80, 0.15, 0.05]
            return int(rng.choice([0, 1, 2], p=p))
        elif regime == "R2":
            # R2 regime: slightly elevated rework frequency
            p = [0.70, 0.20, 0.10]
            return int(rng.choice([0, 1, 2], p=p))
        return 0

    def sample_trajectory_class(
        self,
        rework_count: int,
        rework_regime: str,
        rng: np.random.Generator,
    ) -> TrajectoryClass:
        """Sample trajectory class based on configuration and rework regime."""
        probs = dict(self.config.trajectory_probabilities)

        if rework_regime == "R2" and rework_count > 0:
            # Regime R2 (Risk Shift): rework increases drift probability to 15%
            drift_boost = 0.15 - probs.get("linear_drift", 0.04)
            if drift_boost > 0:
                probs["linear_drift"] = 0.15
                # Reduce stable probability accordingly
                probs["stable"] = max(0.1, probs.get("stable", 0.85) - drift_boost)

        # Normalize probabilities
        classes = list(probs.keys())
        p_vals = np.array([probs[c] for c in classes], dtype=float)
        p_vals /= p_vals.sum()

        chosen_str = rng.choice(classes, p=p_vals)
        return TrajectoryClass(chosen_str)

    def plan_lot(
        self,
        lot_cfg: LotSimConfig,
        rng_lot: np.random.Generator,
    ) -> List[ComponentPlan]:
        """Generate component plans for an entire lot according to its scenario."""
        plans: List[ComponentPlan] = []
        n_comps = lot_cfg.size
        instruments = self.config.equipment.instruments
        ch_per_inst = self.config.equipment.channels_per_instrument

        # Handle specialized scenarios
        if lot_cfg.scenario == "canonical_high_stable":
            plans = self._plan_canonical_high_stable_lot(lot_cfg, rng_lot)
        elif lot_cfg.scenario in ("instrument_shift", "instrument_common_mode_shift"):
            plans = self._plan_instrument_shift_lot(lot_cfg, rng_lot)
        elif lot_cfg.scenario in ("lot_masking", "multi_defect_masking"):
            plans = self._plan_lot_masking_lot(lot_cfg, rng_lot)
        elif lot_cfg.scenario == "adversarial_mix":
            plans = self._plan_adversarial_mix_lot(lot_cfg, rng_lot)
        else:
            # Nominal lot (or small_lot with nominal behavior)
            plans = self._plan_nominal_lot(lot_cfg, rng_lot)

        return plans

    def _plan_nominal_lot(
        self, lot_cfg: LotSimConfig, rng_lot: np.random.Generator
    ) -> List[ComponentPlan]:
        plans = []
        instruments = self.config.equipment.instruments
        ch_per_inst = self.config.equipment.channels_per_instrument

        for i in range(lot_cfg.size):
            comp_id = f"{lot_cfg.lot_id}_C{i+1:03d}"
            # Socket assignment
            inst_idx = (i // ch_per_inst) % len(instruments)
            inst_id = instruments[inst_idx]
            ch_id = f"CH_{(i % ch_per_inst) + 1:02d}"

            # Rework
            rework = self.sample_rework_count(lot_cfg.rework_regime, rng_lot)
            var_mult = 1.5 if (lot_cfg.rework_regime == "R1" and rework > 0) else 1.0

            # Trajectory class
            tc = self.sample_trajectory_class(rework, lot_cfg.rework_regime, rng_lot)

            # Generate parameter profiles (multivariate: assign primary parameter drift or all)
            profiles = {}
            for p_name, p_cfg in self.config.parameters.items():
                is_log = (p_cfg.transform == "log")
                profiles[p_name] = create_trajectory_profile(
                    trajectory_class=tc,
                    parameter_name=p_name,
                    is_log_transform=is_log,
                    rng=rng_lot,
                    checkpoints=self.config.checkpoints,
                )

            plan = ComponentPlan(
                component_id=comp_id,
                lot_id=lot_cfg.lot_id,
                rework_count=rework,
                variance_multiplier=var_mult,
                instrument_id=inst_id,
                channel_id=ch_id,
                scenario_tag=f"{lot_cfg.scenario}_{tc.value}",
                trajectory_profiles=profiles,
            )
            plans.append(plan)
        return plans

    def _plan_canonical_high_stable_lot(
        self, lot_cfg: LotSimConfig, rng_lot: np.random.Generator
    ) -> List[ComponentPlan]:
        """Plan Lot L11: contains the canonical 45 uA component (CANONICAL_C45)."""
        plans = self._plan_nominal_lot(lot_cfg, rng_lot)
        cf_cfg = self.config.canonical_fixture

        # Component 0 is designated as the canonical 45 uA demonstration case
        c0_profiles = {}
        for p_name, p_cfg in self.config.parameters.items():
            is_log = (p_cfg.transform == "log")
            tc = TrajectoryClass.HIGH_BUT_STABLE if p_name == cf_cfg.parameter else TrajectoryClass.STABLE
            c0_profiles[p_name] = create_trajectory_profile(
                trajectory_class=tc,
                parameter_name=p_name,
                is_log_transform=is_log,
                rng=rng_lot,
                checkpoints=self.config.checkpoints,
            )

        plans[0] = ComponentPlan(
            component_id=cf_cfg.component_id,
            lot_id=lot_cfg.lot_id,
            rework_count=0,
            variance_multiplier=1.0,
            instrument_id=plans[0].instrument_id,
            channel_id=plans[0].channel_id,
            scenario_tag="canonical_high_stable_fixture",
            trajectory_profiles=c0_profiles,
            initial_value_overrides={cf_cfg.parameter: cf_cfg.initial_value},
        )
        return plans

    def _plan_instrument_shift_lot(
        self, lot_cfg: LotSimConfig, rng_lot: np.random.Generator
    ) -> List[ComponentPlan]:
        """Plan Lot L13: test-bench shift on INST_01 with 1 real defect (M10)."""
        plans = self._plan_nominal_lot(lot_cfg, rng_lot)
        # Ensure all components on INST_01 are mostly stable, with exactly one real linear drift
        inst_01_indices = [i for i, p in enumerate(plans) if p.instrument_id == "INST_01"]
        if inst_01_indices:
            # Force first to linear drift (real defect)
            defect_idx = inst_01_indices[0]
            profiles = {}
            for p_name, p_cfg in self.config.parameters.items():
                profiles[p_name] = create_trajectory_profile(
                    trajectory_class=TrajectoryClass.LINEAR_DRIFT,
                    parameter_name=p_name,
                    is_log_transform=(p_cfg.transform == "log"),
                    rng=rng_lot,
                    checkpoints=self.config.checkpoints,
                )
            plans[defect_idx] = ComponentPlan(
                component_id=plans[defect_idx].component_id,
                lot_id=lot_cfg.lot_id,
                rework_count=plans[defect_idx].rework_count,
                variance_multiplier=1.0,
                instrument_id=plans[defect_idx].instrument_id,
                channel_id=plans[defect_idx].channel_id,
                scenario_tag="M10_defect_on_shifting_bench",
                trajectory_profiles=profiles,
            )

            # Force remaining on INST_01 to stable
            for idx in inst_01_indices[1:]:
                profiles = {}
                for p_name, p_cfg in self.config.parameters.items():
                    profiles[p_name] = create_trajectory_profile(
                        trajectory_class=TrajectoryClass.STABLE,
                        parameter_name=p_name,
                        is_log_transform=(p_cfg.transform == "log"),
                        rng=rng_lot,
                        checkpoints=self.config.checkpoints,
                    )
                plans[idx] = ComponentPlan(
                    component_id=plans[idx].component_id,
                    lot_id=lot_cfg.lot_id,
                    rework_count=plans[idx].rework_count,
                    variance_multiplier=1.0,
                    instrument_id=plans[idx].instrument_id,
                    channel_id=plans[idx].channel_id,
                    scenario_tag="M10_stable_on_shifting_bench",
                    trajectory_profiles=profiles,
                )

        # On INST_02, assign a low-current component to socket CH_07 to demonstrate
        # negative observation sensor offset artifact near zero (LOG-020)
        inst_02_ch7_indices = [
            i for i, p in enumerate(plans)
            if p.instrument_id == "INST_02" and p.channel_id in ("CH_07", "CH_7")
        ]
        if inst_02_ch7_indices:
            neg_idx = inst_02_ch7_indices[0]
            profiles = {
                p_name: create_trajectory_profile(
                    TrajectoryClass.STABLE, p_name, p_cfg.transform == "log", rng_lot, self.config.checkpoints
                )
                for p_name, p_cfg in self.config.parameters.items()
            }
            plans[neg_idx] = ComponentPlan(
                component_id=plans[neg_idx].component_id,
                lot_id=lot_cfg.lot_id,
                rework_count=0,
                variance_multiplier=1.0,
                instrument_id=plans[neg_idx].instrument_id,
                channel_id=plans[neg_idx].channel_id,
                scenario_tag="M07_negative_offset_artifact",
                trajectory_profiles=profiles,
                initial_value_overrides={"leakage_current": 0.005},
            )

        return plans

    def _plan_lot_masking_lot(
        self, lot_cfg: LotSimConfig, rng_lot: np.random.Generator
    ) -> List[ComponentPlan]:
        """Plan Lot L14: multi-defect lot masking challenge (4 defects in N=30, M11)."""
        plans = self._plan_nominal_lot(lot_cfg, rng_lot)
        # Inject 4 linear drift defects into indices 0, 1, 2, 3
        for idx in range(min(4, len(plans))):
            profiles = {}
            for p_name, p_cfg in self.config.parameters.items():
                profiles[p_name] = create_trajectory_profile(
                    trajectory_class=TrajectoryClass.LINEAR_DRIFT,
                    parameter_name=p_name,
                    is_log_transform=(p_cfg.transform == "log"),
                    rng=rng_lot,
                    checkpoints=self.config.checkpoints,
                )
            plans[idx] = ComponentPlan(
                component_id=plans[idx].component_id,
                lot_id=lot_cfg.lot_id,
                rework_count=plans[idx].rework_count,
                variance_multiplier=1.0,
                instrument_id=plans[idx].instrument_id,
                channel_id=plans[idx].channel_id,
                scenario_tag="M11_multi_defect_masking",
                trajectory_profiles=profiles,
            )
        return plans

    def _plan_adversarial_mix_lot(
        self, lot_cfg: LotSimConfig, rng_lot: np.random.Generator
    ) -> List[ComponentPlan]:
        """Plan lot incorporating mixed scenarios M01–M09."""
        plans = self._plan_nominal_lot(lot_cfg, rng_lot)

        # M01: high_but_stable + noise (index 0)
        if len(plans) > 0:
            profiles = {
                p_name: create_trajectory_profile(
                    TrajectoryClass.HIGH_BUT_STABLE, p_name, p_cfg.transform == "log", rng_lot, self.config.checkpoints
                )
                for p_name, p_cfg in self.config.parameters.items()
            }
            plans[0] = ComponentPlan(
                component_id=plans[0].component_id,
                lot_id=lot_cfg.lot_id,
                rework_count=0,
                variance_multiplier=1.0,
                instrument_id=plans[0].instrument_id,
                channel_id=plans[0].channel_id,
                scenario_tag="M01_high_stable_noise",
                trajectory_profiles=profiles,
                noise_scale_multiplier=2.0,  # elevated noise
            )

        # M02: high_but_stable + missing 96h (index 1)
        if len(plans) > 1:
            profiles = {
                p_name: create_trajectory_profile(
                    TrajectoryClass.HIGH_BUT_STABLE, p_name, p_cfg.transform == "log", rng_lot, self.config.checkpoints
                )
                for p_name, p_cfg in self.config.parameters.items()
            }
            plans[1] = ComponentPlan(
                component_id=plans[1].component_id,
                lot_id=lot_cfg.lot_id,
                rework_count=0,
                variance_multiplier=1.0,
                instrument_id=plans[1].instrument_id,
                channel_id=plans[1].channel_id,
                scenario_tag="M02_high_stable_missing_96h",
                trajectory_profiles=profiles,
                missing_checkpoints=[96],
            )

        # M03: linear_drift + noise (index 2)
        if len(plans) > 2:
            profiles = {
                p_name: create_trajectory_profile(
                    TrajectoryClass.LINEAR_DRIFT, p_name, p_cfg.transform == "log", rng_lot, self.config.checkpoints
                )
                for p_name, p_cfg in self.config.parameters.items()
            }
            plans[2] = ComponentPlan(
                component_id=plans[2].component_id,
                lot_id=lot_cfg.lot_id,
                rework_count=0,
                variance_multiplier=1.0,
                instrument_id=plans[2].instrument_id,
                channel_id=plans[2].channel_id,
                scenario_tag="M03_linear_drift_noise",
                trajectory_profiles=profiles,
                noise_scale_multiplier=2.0,
            )

        # M05: accelerating_drift + missing 96h (index 3)
        if len(plans) > 3:
            profiles = {
                p_name: create_trajectory_profile(
                    TrajectoryClass.ACCELERATING_DRIFT, p_name, p_cfg.transform == "log", rng_lot, self.config.checkpoints
                )
                for p_name, p_cfg in self.config.parameters.items()
            }
            plans[3] = ComponentPlan(
                component_id=plans[3].component_id,
                lot_id=lot_cfg.lot_id,
                rework_count=0,
                variance_multiplier=1.0,
                instrument_id=plans[3].instrument_id,
                channel_id=plans[3].channel_id,
                scenario_tag="M05_accel_drift_missing_96h",
                trajectory_profiles=profiles,
                missing_checkpoints=[96],
            )

        # M08: reworked + stable (index 4)
        if len(plans) > 4:
            profiles = {
                p_name: create_trajectory_profile(
                    TrajectoryClass.STABLE, p_name, p_cfg.transform == "log", rng_lot, self.config.checkpoints
                )
                for p_name, p_cfg in self.config.parameters.items()
            }
            plans[4] = ComponentPlan(
                component_id=plans[4].component_id,
                lot_id=lot_cfg.lot_id,
                rework_count=2,
                variance_multiplier=1.5,
                instrument_id=plans[4].instrument_id,
                channel_id=plans[4].channel_id,
                scenario_tag="M08_reworked_stable",
                trajectory_profiles=profiles,
            )

        # M09: reworked + genuine drift (index 5)
        if len(plans) > 5:
            profiles = {
                p_name: create_trajectory_profile(
                    TrajectoryClass.ACCELERATING_DRIFT, p_name, p_cfg.transform == "log", rng_lot, self.config.checkpoints
                )
                for p_name, p_cfg in self.config.parameters.items()
            }
            plans[5] = ComponentPlan(
                component_id=plans[5].component_id,
                lot_id=lot_cfg.lot_id,
                rework_count=2,
                variance_multiplier=1.5,
                instrument_id=plans[5].instrument_id,
                channel_id=plans[5].channel_id,
                scenario_tag="M09_reworked_genuine_drift",
                trajectory_profiles=profiles,
            )

        return plans

    def resolve_equipment_context(
        self,
        instrument_id: str,
        channel_id: str,
        param_name: str,
        lot_scenario: str,
    ) -> EquipmentContext:
        """Determine equipment gain shifts and socket offsets."""
        eq_cfg = self.config.equipment

        # Check if instrument has common-mode shift (e.g. Lot L13 where INST_01 shifts)
        gain_shift = 0.0
        if lot_scenario in ("instrument_shift", "instrument_common_mode_shift") and instrument_id == "INST_01":
            gain_shift = eq_cfg.common_mode_gain_shift

        # Check for socket channel offset across possible representations:
        # direct: eq_cfg.channel_offset_shifts["CH_4"] or ["CH_04"]
        # nested: eq_cfg.channel_offset_shifts["INST_01"]["CH_4"]
        chan_offset = 0.0
        shifts = eq_cfg.channel_offset_shifts

        # Normalize channel strings: e.g. "CH_04" and "CH_4"
        ch_variants = [channel_id]
        if "_" in channel_id:
            prefix, num_part = channel_id.split("_", 1)
            try:
                num_int = int(num_part)
                ch_variants.append(f"{prefix}_{num_int}")
                ch_variants.append(f"{prefix}_{num_int:02d}")
            except ValueError:
                pass

        # 1. Direct channel lookup
        for v in ch_variants:
            if v in shifts and isinstance(shifts[v], dict):
                if param_name in shifts[v]:
                    chan_offset = float(shifts[v][param_name])
                    break

        # 2. Nested under instrument_id
        if chan_offset == 0.0 and instrument_id in shifts and isinstance(shifts[instrument_id], dict):
            inst_shifts = shifts[instrument_id]
            for v in ch_variants:
                if v in inst_shifts and isinstance(inst_shifts[v], dict):
                    if param_name in inst_shifts[v]:
                        chan_offset = float(inst_shifts[v][param_name])
                        break

        return EquipmentContext(
            instrument_id=instrument_id,
            channel_id=channel_id,
            common_mode_gain_shift=gain_shift,
            channel_offset=chan_offset,
        )
