"""SIH26170 Synthetic Burn-In Dataset Generator.

Top-level orchestrator for generating reproducible, auditable, and decoupled synthetic
burn-in telemetry conforming strictly to docs/PHASE_2_SYNTHETIC_DATA_SPEC.md.

Produces:
- data/synthetic/observations.csv (pure observation telemetry without ground truth)
- data/synthetic/ground_truth.csv (quarantined evaluation ground truth)
- data/synthetic/generation_metadata.json (traceable configuration and seed provenance)
- data/synthetic/statistical_sanity_report.json / .md (dataset QA summary statistics)
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from sih26170.schema import CanonicalMeasurement
from sih26170.synthetic.config import SyntheticConfig, load_synthetic_config
from sih26170.synthetic.ground_truth import GroundTruthRecord, evaluate_ground_truth
from sih26170.synthetic.latent import LatentModel, LatentState
from sih26170.synthetic.measurement import MeasurementSimulator
from sih26170.synthetic.scenarios import ComponentPlan, ScenarioManager
from sih26170.synthetic.seeds import SeedHierarchy
from sih26170.synthetic.validation import (
    StatisticalSanityReport,
    SyntheticValidator,
    ValidationReport,
)


@dataclass
class GenerationResult:
    """Encapsulates the complete outputs of a synthetic generation run."""
    observations_df: pd.DataFrame
    ground_truth_df: pd.DataFrame
    validation_report: ValidationReport
    sanity_report: StatisticalSanityReport
    metadata: Dict[str, Any]


class SyntheticGenerator:
    """Orchestrates deterministic synthetic burn-in screening dataset generation."""

    def __init__(self, config: Optional[SyntheticConfig] = None, config_path: str = "configs/synthetic.yaml"):
        if config is not None:
            self.config = config
        else:
            self.config = load_synthetic_config(config_path)

        self.seeds = SeedHierarchy(self.config.master_seed)
        self.latent_model = LatentModel(self.config)
        self.scenario_manager = ScenarioManager(self.config)
        self.measurement_simulator = MeasurementSimulator(self.config)
        self.validator = SyntheticValidator(self.config)

    def generate(self) -> GenerationResult:
        """Execute full synthetic generation pipeline."""
        observations: List[CanonicalMeasurement] = []
        ground_truth_records: List[GroundTruthRecord] = []

        # Iterate over configured lots
        for lot_cfg in self.config.lots:
            lot_id = lot_cfg.lot_id
            lot_rng = self.seeds.get_rng("lot", lot_id)

            # 1. Sample lot baseline for each parameter
            lot_baselines: Dict[str, float] = {}
            for p_name, p_cfg in self.config.parameters.items():
                lot_baselines[p_name] = self.latent_model.sample_lot_baseline(p_cfg, lot_rng)

            # Special override for canonical high-stable lot baseline (10.0 uA for leakage)
            if lot_cfg.scenario == "canonical_high_stable":
                cf_cfg = self.config.canonical_fixture
                if cf_cfg.parameter in lot_baselines:
                    lot_baselines[cf_cfg.parameter] = cf_cfg.lot_baseline

            # 2. Plan components for this lot
            comp_plans: List[ComponentPlan] = self.scenario_manager.plan_lot(lot_cfg, lot_rng)

            # 3. Generate trajectories and observations for each component
            for plan in comp_plans:
                comp_id = plan.component_id

                for p_name, p_cfg in self.config.parameters.items():
                    param_rng = self.seeds.get_rng("lot", lot_id, "comp", comp_id, "param", p_name)
                    traj_profile = plan.trajectory_profiles[p_name]
                    override_val = plan.initial_value_overrides.get(p_name)

                    # Generate latent trajectory x*(t)
                    latent_states: List[LatentState] = self.latent_model.generate_component_trajectory(
                        component_id=comp_id,
                        lot_id=lot_id,
                        param_name=p_name,
                        lot_baseline=lot_baselines[p_name],
                        trajectory_profile=traj_profile,
                        variance_multiplier=plan.variance_multiplier,
                        rng=param_rng,
                        override_initial_value=override_val,
                    )

                    # Evaluate independent ground truth
                    _, gt_recs = evaluate_ground_truth(
                        latent_series=latent_states,
                        trajectory_profile=traj_profile,
                        config=self.config,
                    )
                    ground_truth_records.extend(gt_recs)

                    # Simulate sensor readouts across checkpoints
                    for state in latent_states:
                        t = state.elapsed_hours
                        meas_rng = self.seeds.get_rng("lot", lot_id, "comp", comp_id, "param", p_name, "meas", t)

                        # Missingness logic
                        is_missing = False
                        if t in plan.missing_checkpoints:
                            is_missing = True
                        elif meas_rng.uniform(0.0, 1.0) < self.config.missingness.random_dropout_rate:
                            is_missing = True

                        if is_missing:
                            continue  # Measurement omitted from observations.csv

                        # Resolve equipment context
                        eq_ctx = self.scenario_manager.resolve_equipment_context(
                            instrument_id=plan.instrument_id,
                            channel_id=plan.channel_id,
                            param_name=p_name,
                            lot_scenario=lot_cfg.scenario,
                        )

                        effective_noise_scale = self.config.noise_scale * plan.noise_scale_multiplier

                        outcome = self.measurement_simulator.simulate_readout(
                            latent_state=state,
                            equipment=eq_ctx,
                            rework_count=plan.rework_count,
                            noise_scale=effective_noise_scale,
                            rng=meas_rng,
                            is_dropout=False,
                        )

                        if outcome.measurement is not None:
                            observations.append(outcome.measurement)

        # Build DataFrames
        obs_dicts = [m.to_dict(include_ground_truth=False) for m in observations]
        observations_df = pd.DataFrame(obs_dicts)

        gt_dicts = [asdict(rec) for rec in ground_truth_records]
        ground_truth_df = pd.DataFrame(gt_dicts)

        # Run validation audit
        val_report = self.validator.validate(observations_df, ground_truth_df)
        if not val_report.is_valid:
            raise RuntimeError(f"Synthetic dataset validation failed with {len(val_report.errors)} errors: {val_report.errors}")

        # Generate statistical sanity report
        sanity_report = self.validator.generate_statistical_sanity_report(observations_df, ground_truth_df)

        # Build execution metadata
        cfg_str = json.dumps(self.config.raw_config, sort_keys=True)
        cfg_hash = hashlib.sha256(cfg_str.encode("utf-8")).hexdigest()[:16]

        metadata = {
            "generator_version": self.config.generator_version,
            "master_seed": self.config.master_seed,
            "configuration_hash": cfg_hash,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "lot_count": sanity_report.lot_count,
            "component_count": sanity_report.component_count,
            "parameter_count": sanity_report.parameter_count,
            "checkpoint_count": sanity_report.checkpoint_count,
            "total_observation_records": sanity_report.total_observation_records,
            "total_ground_truth_records": sanity_report.total_ground_truth_records,
            "parameters": list(self.config.parameters.keys()),
            "checkpoints": self.config.checkpoints,
        }

        return GenerationResult(
            observations_df=observations_df,
            ground_truth_df=ground_truth_df,
            validation_report=val_report,
            sanity_report=sanity_report,
            metadata=metadata,
        )

    def save_dataset(self, result: GenerationResult, output_dir: str | Path = "data/synthetic") -> Dict[str, Path]:
        """Write generated dataset, ground truth, and reports to disk."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        paths = {
            "observations": out_path / "observations.csv",
            "ground_truth": out_path / "ground_truth.csv",
            "metadata": out_path / "generation_metadata.json",
            "sanity_json": out_path / "statistical_sanity_report.json",
            "sanity_md": out_path / "statistical_sanity_report.md",
        }

        # Save observations (strictly observation columns)
        result.observations_df.to_csv(paths["observations"], index=False)

        # Save ground truth (quarantined)
        result.ground_truth_df.to_csv(paths["ground_truth"], index=False)

        # Save metadata
        with open(paths["metadata"], "w", encoding="utf-8") as f:
            json.dump(result.metadata, f, indent=2)

        # Save sanity reports
        with open(paths["sanity_json"], "w", encoding="utf-8") as f:
            json.dump(result.sanity_report.to_dict(), f, indent=2)

        with open(paths["sanity_md"], "w", encoding="utf-8") as f:
            f.write(result.sanity_report.to_markdown())

        return paths


def main():
    """Command-line entry point to run synthetic generation."""
    print("Initializing SIH26170 Synthetic Generator...")
    gen = SyntheticGenerator()
    print(f"Generating dataset with master_seed={gen.config.master_seed}...")
    result = gen.generate()
    paths = gen.save_dataset(result)
    print("Dataset generation complete!")
    print(f"  Observations:  {paths['observations']} ({len(result.observations_df)} records)")
    print(f"  Ground Truth:  {paths['ground_truth']} ({len(result.ground_truth_df)} records)")
    print(f"  Metadata:      {paths['metadata']}")
    print(f"  Sanity Report: {paths['sanity_md']}")
    print("\n" + result.sanity_report.to_markdown())


if __name__ == "__main__":
    main()
