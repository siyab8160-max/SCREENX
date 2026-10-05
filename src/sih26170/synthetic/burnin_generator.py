"""Controlled synthetic burn-in telemetry generator for Module B.

Formally tied to the specifications in docs/B4_UNCERTAINTY_ARCHITECTURE_PLAN.md and
docs/MODULE_B_PHASE_B5_TEST_REPORT.md.

Features:
- Decoupled physical hierarchy: lot effect, device baseline, degradation trajectory, measurement noise.
- Parameter-specific behaviors: IDSS (log), VGS(th) (linear), RDS(on) (log), IGSS (signed asinh).
- Deterministic RNG ownership: instance-level default_rng with child stream derivation.
- Separation of observations and quarantined ground truth with SHA-256 provenance manifest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from sih26170.screening.transforms import (
    transform_parameter,
    inverse_transform_parameter,
    NOISE_FLOORS,
)


class ParameterName(str, Enum):
    """Canonical electrical parameters under MIL-PRF-19500/703."""
    IDSS = "IDSS"
    VGSTH = "VGS(th)"
    RDSON = "RDS(on)"
    IGSS = "IGSS"

    @classmethod
    def from_string(cls, s: str) -> "ParameterName":
        normalized = s.strip()
        for member in cls:
            if member.value == normalized:
                return member
        # Fallbacks for variant spellings
        norm_upper = normalized.upper().replace("-", "").replace("_", "").replace(" ", "")
        if "IDSS" in norm_upper:
            return cls.IDSS
        if "VGSTH" in norm_upper or "VGS" in norm_upper:
            return cls.VGSTH
        if "RDSON" in norm_upper or "RDS" in norm_upper:
            return cls.RDSON
        if "IGSS" in norm_upper:
            return cls.IGSS
        raise ValueError(f"Unknown parameter name: {s}")


PARAM_TO_UNIT: Dict[str, str] = {
    ParameterName.IDSS.value: "uA",
    ParameterName.VGSTH.value: "V",
    ParameterName.RDSON.value: "mOhm",
    ParameterName.IGSS.value: "nA",
}


class ScenarioLabel(str, Enum):
    """Benchmark scenario labels for synthetic burn-in trajectory generator."""
    STABLE = "stable"
    HIGH_BUT_STABLE = "high_but_stable"
    LINEAR_DRIFT = "linear_drift"
    ACCELERATING_DRIFT = "accelerating_drift"
    SUBTLE_ABRUPT_CHANGE = "subtle_abrupt_change"
    EQUIPMENT_COMMON_MODE = "equipment_common_mode"
    MISSING_OBSERVATIONS = "missing_observations"
    INSUFFICIENT_DATA = "insufficient_data"
    MIXED_COMPOUND = "mixed_compound"


@dataclass(frozen=True)
class BenchmarkScenario:
    """Mathematical specification of a degradation scenario."""
    label: ScenarioLabel
    description: str

    def compute_kinetics(
        self,
        t_hours: np.ndarray,
        param_name: str,
        delta_effect_size: float = 2.0,
        acceleration_exponent: float = 2.0,
        abrupt_event_hour: float = 48.0,
        abrupt_magnitude_mult: float = 1.0,
    ) -> np.ndarray:
        """Compute deterministic degradation trajectory gamma_p(t) in analysis space."""
        norm_t = np.asarray(t_hours, dtype=float) / 168.0
        sign = 1.0

        if self.label == ScenarioLabel.STABLE:
            return np.zeros_like(norm_t)

        elif self.label == ScenarioLabel.HIGH_BUT_STABLE:
            return np.zeros_like(norm_t)

        elif self.label == ScenarioLabel.LINEAR_DRIFT:
            return sign * delta_effect_size * norm_t

        elif self.label == ScenarioLabel.ACCELERATING_DRIFT:
            return sign * delta_effect_size * (norm_t ** acceleration_exponent)

        elif self.label == ScenarioLabel.SUBTLE_ABRUPT_CHANGE:
            kinetics = np.zeros_like(norm_t)
            t_flt = np.asarray(t_hours, dtype=float)
            abrupt_mask = t_flt >= abrupt_event_hour
            if np.any(abrupt_mask):
                post_elapsed = np.maximum(0.0, t_flt[abrupt_mask] - abrupt_event_hour)
                post_progression = 0.60 + 0.40 * (post_elapsed / 144.0)
                kinetics[abrupt_mask] = sign * delta_effect_size * post_progression * abrupt_magnitude_mult
            return kinetics

        elif self.label == ScenarioLabel.EQUIPMENT_COMMON_MODE:
            return np.zeros_like(norm_t)

        elif self.label == ScenarioLabel.MISSING_OBSERVATIONS:
            return sign * delta_effect_size * 0.5 * norm_t

        elif self.label == ScenarioLabel.INSUFFICIENT_DATA:
            return sign * delta_effect_size * 0.5 * norm_t

        elif self.label == ScenarioLabel.MIXED_COMPOUND:
            t_flt = np.asarray(t_hours, dtype=float)
            kinetics = np.zeros_like(norm_t)
            seg1 = (t_flt > 24.0) & (t_flt <= 96.0)
            seg2 = t_flt > 96.0

            kinetics[seg1] = sign * delta_effect_size * 0.30 * ((t_flt[seg1] - 24.0) / 72.0)
            kinetics[seg2] = sign * delta_effect_size * (
                0.30 + 0.70 * (((t_flt[seg2] - 96.0) / 72.0) ** 2)
            )
            return kinetics

        else:
            raise ValueError(f"Unknown scenario label: {self.label}")


def get_default_scenarios() -> Dict[ScenarioLabel, BenchmarkScenario]:
    """Return canonical set of scenarios for synthetic benchmark."""
    return {
        ScenarioLabel.STABLE: BenchmarkScenario(
            label=ScenarioLabel.STABLE,
            description="Stationary component exhibiting no systematic temporal degradation.",
        ),
        ScenarioLabel.HIGH_BUT_STABLE: BenchmarkScenario(
            label=ScenarioLabel.HIGH_BUT_STABLE,
            description="High initial baseline offset but perfectly stationary temporal trajectory.",
        ),
        ScenarioLabel.LINEAR_DRIFT: BenchmarkScenario(
            label=ScenarioLabel.LINEAR_DRIFT,
            description="Linear drift with constant degradation velocity across burn-in.",
        ),
        ScenarioLabel.ACCELERATING_DRIFT: BenchmarkScenario(
            label=ScenarioLabel.ACCELERATING_DRIFT,
            description="Accelerating (convex) degradation with increasing velocity over time.",
        ),
        ScenarioLabel.SUBTLE_ABRUPT_CHANGE: BenchmarkScenario(
            label=ScenarioLabel.SUBTLE_ABRUPT_CHANGE,
            description="Stationary early period followed by a discrete post-24h step shift.",
        ),
        ScenarioLabel.EQUIPMENT_COMMON_MODE: BenchmarkScenario(
            label=ScenarioLabel.EQUIPMENT_COMMON_MODE,
            description="Shared equipment excursion affecting all devices on a common instrument/channel.",
        ),
        ScenarioLabel.MISSING_OBSERVATIONS: BenchmarkScenario(
            label=ScenarioLabel.MISSING_OBSERVATIONS,
            description="Drifting component with missing non-critical checkpoint (e.g., 0h fallback).",
        ),
        ScenarioLabel.INSUFFICIENT_DATA: BenchmarkScenario(
            label=ScenarioLabel.INSUFFICIENT_DATA,
            description="Trajectory with missing 24h as-of checkpoint requiring forecast refusal.",
        ),
        ScenarioLabel.MIXED_COMPOUND: BenchmarkScenario(
            label=ScenarioLabel.MIXED_COMPOUND,
            description="Compound piecewise trajectory: stationary -> linear drift -> accelerating drift.",
        ),
    }


# Default canonical parameters calibrated to MIL-PRF-19500/703
DEFAULT_PARAM_SPECS: Dict[str, Dict[str, Any]] = {
    ParameterName.IDSS.value: {
        "nominal_phys": 0.50,  # 0.50 uA
        "unit": "uA",
        "sigma_lot": 0.15,
        "sigma_device": 0.20,
        "sigma_meas": 0.08,
        "delta_drift": 1.5,     # drift effect size in sigma_u
        "test_condition": "VDS=80V, VGS=0V",
    },
    ParameterName.VGSTH.value: {
        "nominal_phys": 3.00,  # 3.00 V
        "unit": "V",
        "sigma_lot": 0.08,
        "sigma_device": 0.10,
        "sigma_meas": 0.02,
        "delta_drift": 0.5,     # drift effect size in volts
        "test_condition": "VDS=VGS, ID=1mA",
    },
    ParameterName.RDSON.value: {
        "nominal_phys": 48.0,  # 48.0 mOhm
        "unit": "mOhm",
        "sigma_lot": 0.06,
        "sigma_device": 0.08,
        "sigma_meas": 0.0125,
        "delta_drift": 0.35,    # drift effect size in log mOhm
        "test_condition": "VGS=12V, ID=22A",
    },
    ParameterName.IGSS.value: {
        "nominal_phys": 2.00,  # 2.00 nA
        "unit": "nA",
        "sigma_lot": 0.20,
        "sigma_device": 0.25,
        "sigma_meas": 0.25,
        "delta_drift": 2.0,     # drift effect size in asinh space
        "test_condition": "VGS=20V, VDS=0V",
    },
}

DEFAULT_SCENARIO_PROBS: Dict[ScenarioLabel, float] = {
    ScenarioLabel.STABLE: 0.40,
    ScenarioLabel.HIGH_BUT_STABLE: 0.10,
    ScenarioLabel.LINEAR_DRIFT: 0.10,
    ScenarioLabel.ACCELERATING_DRIFT: 0.12,
    ScenarioLabel.SUBTLE_ABRUPT_CHANGE: 0.08,
    ScenarioLabel.EQUIPMENT_COMMON_MODE: 0.04,
    ScenarioLabel.MISSING_OBSERVATIONS: 0.04,
    ScenarioLabel.INSUFFICIENT_DATA: 0.06,
    ScenarioLabel.MIXED_COMPOUND: 0.06,
}


class SyntheticBurnInGenerator:
    """Canonical synthetic burn-in telemetry generator for Module B.

    Complies with B4/B5 architecture:
    - 4 canonical electrical parameters: IDSS, VGS(th), RDS(on), IGSS
    - 4 canonical checkpoints: 0, 24, 96, 168 hours
    - Rigorous physical transforms and inverse transforms
    - Complete separation of observations and quarantined ground truth
    """

    def __init__(
        self,
        seed: int = 20261005,
        temperature_C: float = 125.0,
        checkpoints: Optional[List[int]] = None,
        param_specs: Optional[Dict[str, Dict[str, Any]]] = None,
        scenario_probs: Optional[Dict[ScenarioLabel, float]] = None,
    ):
        self.seed = int(seed)
        self.temperature_C = float(temperature_C)
        self.checkpoints = checkpoints or [0, 24, 96, 168]
        self.param_specs = param_specs or DEFAULT_PARAM_SPECS
        self.scenario_probs = scenario_probs or DEFAULT_SCENARIO_PROBS
        self.scenarios = get_default_scenarios()
        self.master_rng = np.random.default_rng(self.seed)

    def generate(
        self,
        lots: Optional[List[str]] = None,
        components_per_lot: int = 20,
        mode: str = "stress",
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
        """Generate benchmark observations, ground truth records, and cryptographic manifest."""
        if lots is None:
            lots = [f"LOT{i:02d}" for i in range(1, 15)]

        checkpoints_arr = np.array(self.checkpoints, dtype=float)
        obs_records: List[Dict[str, Any]] = []
        gt_records: List[Dict[str, Any]] = []

        scenario_counts: Dict[str, int] = {k.value: 0 for k in ScenarioLabel}
        missing_checkpoint_counts: Dict[int, int] = {h: 0 for h in self.checkpoints}

        u_nom: Dict[str, float] = {}
        for p_name, p_spec in self.param_specs.items():
            u_nom[p_name] = transform_parameter(p_name, p_spec["nominal_phys"])

        for lot_idx, lot_id in enumerate(lots):
            alpha_lot: Dict[str, float] = {}
            for p_name, p_spec in self.param_specs.items():
                alpha_lot[p_name] = float(
                    self.master_rng.normal(0.0, p_spec["sigma_lot"])
                )

            rework_regimes = [0, 1, 2]
            rework_probs = [0.70, 0.20, 0.10]
            rework_regime = int(self.master_rng.choice(rework_regimes, p=rework_probs))

            instruments = ["ATE_BENCH_01", "ATE_BENCH_02"]
            eta_equipment: Dict[Tuple[str, str], np.ndarray] = {}
            for inst in instruments:
                for p_name, p_spec in self.param_specs.items():
                    step_dir = 1.0 if self.master_rng.uniform() > 0.5 else -1.0
                    excursion = np.zeros_like(checkpoints_arr, dtype=float)
                    excursion[checkpoints_arr >= 24.0] = (
                        step_dir * 1.5 * p_spec["sigma_meas"]
                    )
                    eta_equipment[(inst, p_name)] = excursion

            for c_idx in range(1, components_per_lot + 1):
                component_id = f"{lot_id}_C{c_idx:02d}"
                inst_id = instruments[c_idx % len(instruments)]
                channel_id = f"CH_{(c_idx - 1) % 10 + 1:02d}"

                if rework_regime == 0:
                    rework_count = 0
                elif rework_regime == 1:
                    rework_count = int(self.master_rng.choice([1, 2], p=[0.75, 0.25]))
                else:
                    rework_count = int(self.master_rng.choice([1, 2, 3], p=[0.50, 0.35, 0.15]))

                drift_multiplier = 1.0 + 0.30 * rework_count
                noise_mult = 1.0 if rework_count == 0 else 1.25

                acceleration_exponent = float(self.master_rng.uniform(1.8, 2.5))
                abrupt_event_hour = float(self.master_rng.choice([48.0, 72.0, 96.0]))
                abrupt_magnitude_mult = float(self.master_rng.uniform(0.8, 1.4))

                for p_name, p_spec in self.param_specs.items():
                    unit = p_spec["unit"]
                    condition = p_spec["test_condition"]

                    labels = list(self.scenario_probs.keys())
                    probs = np.array([self.scenario_probs[k] for k in labels], dtype=float)
                    probs = probs / np.sum(probs)

                    chosen_idx = int(self.master_rng.choice(len(labels), p=probs))
                    chosen_scenario_label: ScenarioLabel = labels[chosen_idx]
                    scenario_obj = self.scenarios[chosen_scenario_label]
                    scenario_counts[chosen_scenario_label.value] += 1

                    if chosen_scenario_label == ScenarioLabel.HIGH_BUT_STABLE:
                        beta_device = 2.5 * p_spec["sigma_device"] + float(
                            self.master_rng.normal(0.0, 0.2 * p_spec["sigma_device"])
                        )
                    else:
                        beta_device = float(
                            self.master_rng.normal(0.0, p_spec["sigma_device"])
                        )

                    gamma_t = scenario_obj.compute_kinetics(
                        checkpoints_arr,
                        param_name=p_name,
                        delta_effect_size=p_spec["delta_drift"] * drift_multiplier,
                        acceleration_exponent=acceleration_exponent,
                        abrupt_event_hour=abrupt_event_hour,
                        abrupt_magnitude_mult=abrupt_magnitude_mult,
                    )

                    if chosen_scenario_label == ScenarioLabel.EQUIPMENT_COMMON_MODE:
                        eta_t = eta_equipment[(inst_id, p_name)]
                    else:
                        eta_t = np.zeros_like(checkpoints_arr, dtype=float)

                    eps_t = self.master_rng.normal(
                        0.0, p_spec["sigma_meas"] * noise_mult, size=len(checkpoints_arr)
                    )

                    u_t = (
                        u_nom[p_name]
                        + alpha_lot[p_name]
                        + beta_device
                        + gamma_t
                        + eta_t
                        + eps_t
                    )

                    for t_idx, t_hour in enumerate(self.checkpoints):
                        omit_observation = False

                        if chosen_scenario_label == ScenarioLabel.MISSING_OBSERVATIONS:
                            if (c_idx % 2 == 0) and (t_hour == 0):
                                omit_observation = True
                            elif (c_idx % 2 != 0) and (t_hour == 96):
                                omit_observation = True

                        elif chosen_scenario_label == ScenarioLabel.INSUFFICIENT_DATA:
                            if (c_idx % 2 == 0) and (t_hour in [0, 24]):
                                omit_observation = True
                            elif (c_idx % 2 != 0) and (t_hour == 24):
                                omit_observation = True

                        if omit_observation:
                            missing_checkpoint_counts[int(t_hour)] += 1
                            continue

                        y_val = inverse_transform_parameter(p_name, u_t[t_idx])

                        obs_records.append({
                            "component_id": component_id,
                            "lot_id": lot_id,
                            "parameter_name": p_name,
                            "elapsed_hours": int(t_hour),
                            "value": float(y_val),
                            "unit": unit,
                            "temperature_C": self.temperature_C,
                            "test_condition": condition,
                            "instrument_id": inst_id,
                            "channel_id": channel_id,
                            "measurement_quality": "VALID",
                            "rework_count": rework_count,
                        })

                    true_168_phys = inverse_transform_parameter(p_name, u_t[-1])

                    first_abnormal: Optional[int] = None
                    event_hr: Optional[int] = None

                    if chosen_scenario_label in [ScenarioLabel.LINEAR_DRIFT, ScenarioLabel.ACCELERATING_DRIFT]:
                        first_abnormal = 24
                    elif chosen_scenario_label == ScenarioLabel.SUBTLE_ABRUPT_CHANGE:
                        event_hr = 48
                        first_abnormal = 96
                    elif chosen_scenario_label == ScenarioLabel.EQUIPMENT_COMMON_MODE:
                        event_hr = 24
                        first_abnormal = 24
                    elif chosen_scenario_label == ScenarioLabel.MIXED_COMPOUND:
                        event_hr = 24
                        first_abnormal = 96

                    gt_records.append({
                        "component_id": component_id,
                        "lot_id": lot_id,
                        "parameter_name": p_name,
                        "target_horizon_hours": 168,
                        "actual_value": float(true_168_phys),
                        "scenario_label": chosen_scenario_label.value,
                        "first_abnormal_hour": first_abnormal,
                        "event_hour": event_hr,
                    })

        obs_df = pd.DataFrame(obs_records)
        gt_df = pd.DataFrame(gt_records)

        obs_csv_bytes = obs_df.to_csv(index=False).encode("utf-8")
        gt_csv_bytes = gt_df.to_csv(index=False).encode("utf-8")

        obs_hash = hashlib.sha256(obs_csv_bytes).hexdigest()
        gt_hash = hashlib.sha256(gt_csv_bytes).hexdigest()

        manifest: Dict[str, Any] = {
            "generator_seed": self.seed,
            "generator_version": "v2.0.0",
            "generation_mode": mode,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_observations": len(obs_df),
            "total_ground_truth_records": len(gt_df),
            "total_components": len(lots) * components_per_lot,
            "lots": lots,
            "checkpoints_hours": self.checkpoints,
            "parameters": list(self.param_specs.keys()),
            "scenario_counts": scenario_counts,
            "missing_checkpoint_counts": missing_checkpoint_counts,
            "observations_sha256": obs_hash,
            "ground_truth_sha256": gt_hash,
            "provenance_statement": (
                "SYNTHETIC PROTOTYPE EVALUATION DATASET ONLY. "
                "DO NOT CLAIM VALIDATION ON ISRO FLIGHT OR PRODUCTION TELEMETRY."
            ),
        }

        return obs_df, gt_df, manifest

    def save_dataset(
        self,
        output_dir: Path,
        lots: Optional[List[str]] = None,
        components_per_lot: int = 20,
        mode: str = "stress",
    ) -> Dict[str, Any]:
        """Generate and persist dataset files and checksum manifest."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        obs_df, gt_df, manifest = self.generate(
            lots=lots, components_per_lot=components_per_lot, mode=mode
        )

        obs_path = output_dir / "observations.csv"
        gt_path = output_dir / "ground_truth.csv"
        manifest_path = output_dir / "manifest.json"

        obs_df.to_csv(obs_path, index=False)
        gt_df.to_csv(gt_path, index=False)

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest
