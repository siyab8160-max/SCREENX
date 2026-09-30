"""SIH26170 Phase 2F Physics-Informed Synthetic Generator Orchestrator.

Coordinates hierarchical generation, parameter-selective scenario execution,
quarantined ground truth evaluation, and cryptographic artifact manifestation.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from sih26170.schema import CanonicalMeasurement
from sih26170.synthetic.phase2f.config import (
    Phase2FConfig,
    Phase2FLotConfig,
    get_default_phase2f_config,
)
from sih26170.synthetic.phase2f.ground_truth import (
    Phase2FGroundTruthRecord,
    evaluate_phase2f_ground_truth,
)
from sih26170.synthetic.phase2f.latent import (
    Phase2FLatentModel,
    Phase2FLatentState,
)
from sih26170.synthetic.phase2f.measurement import Phase2FMeasurementSimulator
from sih26170.synthetic.phase2f.scenarios import (
    Phase2FComponentPlan,
    Phase2FScenarioManager,
)
from sih26170.synthetic.phase2f.validator import (
    Phase2FForensicReport,
    Phase2FValidator,
)


def derive_seed_hmac(parent_seed: int, *path_elements: Any) -> int:
    """Derive deterministic integer seed via HMAC-SHA256 for cryptographic reproducibility."""
    msg = ":".join(str(elem) for elem in path_elements).encode("utf-8")
    key = str(parent_seed).encode("utf-8")
    h = hmac.new(key, msg, hashlib.sha256).digest()
    # Convert first 8 bytes to unsigned 64-bit integer, modulo 2^31 - 1
    int_val = int.from_bytes(h[:8], byteorder="big", signed=False)
    return int_val % (2**31 - 1)


@dataclass
class Phase2FGenerationResult:
    """Encapsulates output artifacts of a Phase 2F synthetic generation run."""
    observations_df: pd.DataFrame
    ground_truth_df: pd.DataFrame
    forensic_report: Phase2FForensicReport
    metadata: Dict[str, Any]
    scenario_manifest: Dict[str, Any]
    component_plans: List[Phase2FComponentPlan]


class Phase2FGenerator:
    """Orchestrates deterministic Phase 2F physics-informed synthetic data generation."""

    def __init__(self, config: Optional[Phase2FConfig] = None):
        self.config = config or get_default_phase2f_config()
        self.latent_model = Phase2FLatentModel(self.config)
        self.scenario_manager = Phase2FScenarioManager(self.config)
        self.measurement_simulator = Phase2FMeasurementSimulator(self.config)
        self.validator = Phase2FValidator(self.config)

    def generate(self) -> Phase2FGenerationResult:
        """Execute complete causal DAG generation pipeline."""
        observations: List[CanonicalMeasurement] = []
        ground_truth_records: List[Phase2FGroundTruthRecord] = []
        all_plans: List[Phase2FComponentPlan] = []

        master_seed = self.config.master_seed

        # Iterate over manufacturing lots
        for lot_cfg in self.config.lots:
            lot_seed = derive_seed_hmac(master_seed, "lot", lot_cfg.lot_id)
            rng_lot = np.random.default_rng(lot_seed)

            # 1. Sample lot central tendencies mu_l,p
            lot_baselines = self.latent_model.sample_lot_baselines(rng_lot)

            # 2. Plan components with parameter-selective scenario vectors
            comp_plans = self.scenario_manager.plan_lot(lot_cfg, rng_lot)
            all_plans.extend(comp_plans)

            # 3. Generate component trajectories and measurements
            for plan in comp_plans:
                comp_seed = derive_seed_hmac(lot_seed, "comp", plan.component_id)
                rng_comp = np.random.default_rng(comp_seed)

                # Sample initial component baselines with wafer-level physical covariance
                comp_baselines = self.latent_model.sample_component_baselines(
                    lot_baselines=lot_baselines,
                    rng_comp=rng_comp,
                    comp_id=plan.component_id,
                )

                for p_name, p_cfg in self.config.parameters.items():
                    param_seed = derive_seed_hmac(comp_seed, "param", p_name)
                    rng_param = np.random.default_rng(param_seed)

                    # Generate latent time-series x*(t)
                    init_b = comp_baselines[p_name]
                    latent_states = self.latent_model.generate_component_parameter_series(
                        component_plan=plan,
                        param_name=p_name,
                        initial_baseline=init_b,
                        rng_param=rng_param,
                    )

                    # Evaluate quarantined ground truth
                    gt_recs = evaluate_phase2f_ground_truth(
                        latent_states=latent_states,
                        plan=plan,
                        param_cfg=p_cfg,
                    )
                    ground_truth_records.extend(gt_recs)

                    # Simulate sensor readouts across checkpoints
                    for state in latent_states:
                        t = state.elapsed_hours
                        meas_seed = derive_seed_hmac(param_seed, "meas", t)
                        rng_meas = np.random.default_rng(meas_seed)

                        outcome = self.measurement_simulator.simulate_readout(
                            latent_state=state,
                            plan=plan,
                            lot_cfg=lot_cfg,
                            rng_meas=rng_meas,
                        )

                        if outcome.measurement is not None:
                            observations.append(outcome.measurement)

        # Build DataFrames
        obs_dicts = [m.to_dict(include_ground_truth=False) for m in observations]
        observations_df = pd.DataFrame(obs_dicts)

        gt_dicts = [asdict(rec) for rec in ground_truth_records]
        ground_truth_df = pd.DataFrame(gt_dicts)

        # Execute forensic validation audit
        report = self.validator.validate(observations_df, ground_truth_df, all_plans)
        if not report.is_valid:
            raise RuntimeError(f"Phase 2F validation failed with errors: {report.errors}")

        # Compute configuration SHA-256
        cfg_dump = json.dumps({
            "generator_version": self.config.generator_version,
            "master_seed": self.config.master_seed,
            "component_anchor": self.config.component_anchor,
            "spec": self.config.governing_specification,
            "params": list(self.config.parameters.keys()),
            "lots": [asdict(l) for l in self.config.lots],
        }, sort_keys=True)
        cfg_hash = hashlib.sha256(cfg_dump.encode("utf-8")).hexdigest()

        metadata = {
            "dataset_status": "PHASE_2F_DEVELOPMENT",
            "is_frozen": False,
            "generator_version": self.config.generator_version,
            "master_seed": self.config.master_seed,
            "configuration_hash": cfg_hash,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "component_anchor": self.config.component_anchor,
            "governing_specification": self.config.governing_specification,
            "package_type": self.config.package_type,
            "total_lots": report.lot_count,
            "total_components": report.component_count,
            "total_observations": report.observation_count,
            "missingness_rate": report.missingness_rate,
            "homogeneous_coupling_fraction": report.homogeneous_coupling_fraction,
            "parameters": list(self.config.parameters.keys()),
            "checkpoints": self.config.checkpoints,
        }

        # Scenario manifest summarizing component-level trajectory vectors
        scenario_manifest = {
            "dataset_status": "PHASE_2F_DEVELOPMENT",
            "component_count": len(all_plans),
            "components": [
                {
                    "component_id": p.component_id,
                    "lot_id": p.lot_id,
                    "component_scenario": p.component_scenario,
                    "scenario_tag": p.scenario_tag,
                    "trajectory_vector": p.trajectory_vector.to_dict(),
                    "is_homogeneous": p.trajectory_vector.is_homogeneous(),
                    "correlation_origins": p.correlation_origins,
                }
                for p in all_plans
            ]
        }

        return Phase2FGenerationResult(
            observations_df=observations_df,
            ground_truth_df=ground_truth_df,
            forensic_report=report,
            metadata=metadata,
            scenario_manifest=scenario_manifest,
            component_plans=all_plans,
        )

    def save_dataset(
        self,
        result: Phase2FGenerationResult,
        output_dir: str | Path = "data/synthetic_phase2f_dev",
    ) -> Dict[str, Path]:
        """Save Phase 2F development dataset artifacts strictly to development location."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        paths = {
            "observations": out_path / "observations.csv",
            "ground_truth": out_path / "ground_truth.csv",
            "manifest": out_path / "manifest.json",
            "scenario_manifest": out_path / "scenario_manifest.json",
            "generation_metadata": out_path / "generation_metadata.json",
            "config_snapshot": out_path / "configuration_snapshot.json",
        }

        # Save dataframes
        result.observations_df.to_csv(paths["observations"], index=False)
        result.ground_truth_df.to_csv(paths["ground_truth"], index=False)

        # Compute dataset SHA-256 digests
        obs_hash = hashlib.sha256(paths["observations"].read_bytes()).hexdigest()
        gt_hash = hashlib.sha256(paths["ground_truth"].read_bytes()).hexdigest()

        # Update metadata with dataset hashes
        result.metadata["observations_sha256"] = obs_hash
        result.metadata["ground_truth_sha256"] = gt_hash

        # Write metadata
        with open(paths["generation_metadata"], "w", encoding="utf-8") as f:
            json.dump(result.metadata, f, indent=2)

        # Write scenario manifest
        with open(paths["scenario_manifest"], "w", encoding="utf-8") as f:
            json.dump(result.scenario_manifest, f, indent=2)

        # Write configuration snapshot
        cfg_dict = {
            "generator_version": self.config.generator_version,
            "master_seed": self.config.master_seed,
            "component_anchor": self.config.component_anchor,
            "governing_specification": self.config.governing_specification,
            "package_type": self.config.package_type,
            "checkpoints": self.config.checkpoints,
            "small_lot_threshold_policy": self.config.small_lot_threshold_policy,
            "parameters": {k: asdict(v) for k, v in self.config.parameters.items()},
            "lots": [asdict(l) for l in self.config.lots],
            "equipment": asdict(self.config.equipment),
            "missingness": asdict(self.config.missingness),
        }
        with open(paths["config_snapshot"], "w", encoding="utf-8") as f:
            json.dump(cfg_dict, f, indent=2)

        # Write top-level manifest
        manifest = {
            "artifact_type": "PHASE_2F_DEVELOPMENT_SYNTHETIC_DATASET",
            "status": "DEVELOPMENT_ONLY_NOT_FROZEN",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "generator_version": self.config.generator_version,
            "master_seed": self.config.master_seed,
            "files": {
                "observations.csv": {
                    "records": len(result.observations_df),
                    "sha256": obs_hash,
                },
                "ground_truth.csv": {
                    "records": len(result.ground_truth_df),
                    "sha256": gt_hash,
                },
            },
            "forensic_summary": result.forensic_report.to_dict(),
        }
        with open(paths["manifest"], "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return paths
