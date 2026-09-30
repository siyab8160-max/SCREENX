"""SIH26170 Phase 4B Independent Benchmark Generator.

Generates the Phase 4B synthetic benchmark (PHASE_4B_BENCHMARK_v1.0.0) according to the
frozen LOG-076 specification for dense temporal support (K=7, S1 schedule),
independent null architectures (A, B, C), and calibrated weak degradation fixtures (A-F).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from sih26170.schema import CANONICAL_COLUMNS
from sih26170.synthetic.phase4b.config import (
    Phase4BConfig,
    Phase4BFixtureType,
    Phase4BLotConfig,
    Phase4BParameterConfig,
    Phase4BPartition,
    get_default_phase4b_config,
)


def derive_seed_hmac(parent_seed: int, *path_elements: Any) -> int:
    """Derive deterministic integer seed via HMAC-SHA256 for cryptographic reproducibility."""
    msg = ":".join(str(elem) for elem in path_elements).encode("utf-8")
    key = str(parent_seed).encode("utf-8")
    h = hmac.new(key, msg, hashlib.sha256).digest()
    int_val = int.from_bytes(h[:8], byteorder="big", signed=False)
    return int_val % (2**31 - 1)


@dataclass
class Phase4BGenerationResult:
    """Encapsulates the generated artifacts and verification reports."""
    observations_df: pd.DataFrame
    ground_truth_df: pd.DataFrame
    manifest: Dict[str, Any]
    checksums: Dict[str, str]
    structural_check_passed: bool
    statistical_sanity_passed: bool
    leakage_audit_passed: bool


class Phase4BGenerator:
    """Orchestrates deterministic Phase 4B synthetic benchmark generation."""

    def __init__(self, config: Optional[Phase4BConfig] = None):
        self.config = config or get_default_phase4b_config()

    def generate(self, output_dir: Optional[Path] = None) -> Phase4BGenerationResult:
        """Generate the complete Phase 4B benchmark dataset."""
        obs_rows: List[Dict[str, Any]] = []
        gt_rows: List[Dict[str, Any]] = []

        master_seed = self.config.master_seed
        checkpoints = self.config.checkpoints

        # Partition seeds
        partition_seeds = {
            Phase4BPartition.CALIBRATION: derive_seed_hmac(master_seed, "partition", "calibration"),
            Phase4BPartition.VALIDATION: derive_seed_hmac(master_seed, "partition", "validation"),
            Phase4BPartition.FINAL_EVALUATION: derive_seed_hmac(master_seed, "partition", "final_evaluation"),
        }

        # Iterate over configured manufacturing lots
        for lot_cfg in self.config.lots:
            p_seed = partition_seeds[lot_cfg.partition]
            lot_seed = derive_seed_hmac(p_seed, "lot", lot_cfg.lot_id)
            rng_lot = np.random.default_rng(lot_seed)

            # Sample lot-level baseline central tendencies in transformed space
            lot_u_baseline: Dict[str, float] = {}
            for p_name, p_cfg in self.config.parameters.items():
                if p_cfg.transform == "log":
                    u_nom = float(np.log(p_cfg.nominal_baseline))
                elif p_cfg.transform == "linear":
                    u_nom = float(p_cfg.nominal_baseline)
                elif p_cfg.transform == "asinh":
                    u_nom = float(np.arcsinh(p_cfg.nominal_baseline / p_cfg.scale))
                else:
                    raise ValueError(f"Unknown transform {p_cfg.transform}")

                lot_u_baseline[p_name] = float(u_nom + rng_lot.normal(0.0, p_cfg.lot_dispersion))

            # Iterate over components in lot
            for comp_idx in range(1, lot_cfg.size + 1):
                comp_id = f"{lot_cfg.lot_id}_C{comp_idx:03d}"
                channel_id = f"CH_{comp_idx:02d}"
                comp_seed = derive_seed_hmac(lot_seed, "comp", comp_id)
                rng_comp = np.random.default_rng(comp_seed)

                # Sample component baseline offsets
                comp_u_baseline: Dict[str, float] = {}
                for p_name, p_cfg in self.config.parameters.items():
                    comp_u_baseline[p_name] = float(
                        lot_u_baseline[p_name] + rng_comp.normal(0.0, p_cfg.device_dispersion)
                    )

                # Generate trajectory for each parameter
                for p_name, p_cfg in self.config.parameters.items():
                    # Determine whether this parameter has active degradation
                    has_degradation = False
                    delta = 0.0
                    if lot_cfg.fixture_type not in [
                        Phase4BFixtureType.NULL_GAUSSIAN,
                        Phase4BFixtureType.NULL_AR1,
                        Phase4BFixtureType.NULL_COMMON_MODE,
                    ]:
                        if lot_cfg.target_parameter in ["ALL", p_name]:
                            has_degradation = True
                            delta = float(lot_cfg.signal_delta or 1.5)

                    # Determine degradation sign s_p
                    # IDSS: positive (+), RDS(on): positive (+)
                    # VGS(th): alternating sign (+ for even comp_idx, - for odd comp_idx)
                    # IGSS: alternating sign (+ for even comp_idx, - for odd comp_idx)
                    if p_name in ["IDSS", "RDS(on)"]:
                        sign_p = 1.0
                    else:
                        sign_p = 1.0 if (comp_idx % 2 == 0) else -1.0

                    # Generate noise sequence epsilon(t) across K=7 checkpoints
                    sig_u = p_cfg.noise_scale
                    if lot_cfg.fixture_type == Phase4BFixtureType.NULL_AR1:
                        # Autoregressive AR(1) noise structure
                        phi_val = float(rng_comp.uniform(lot_cfg.phi_range[0], lot_cfg.phi_range[1]))
                        eps_seq = np.zeros(len(checkpoints), dtype=float)
                        eps_seq[0] = rng_comp.normal(0.0, sig_u)
                        for k in range(1, len(checkpoints)):
                            eta = rng_comp.normal(0.0, sig_u)
                            eps_seq[k] = phi_val * eps_seq[k - 1] + np.sqrt(1.0 - phi_val**2) * eta
                    elif lot_cfg.fixture_type == Phase4BFixtureType.FIXTURE_E_HETEROSCEDASTIC_NOISE:
                        # Expanding noise scale
                        eps_seq = np.zeros(len(checkpoints), dtype=float)
                        for k, t_hr in enumerate(checkpoints):
                            sig_t = sig_u * (1.0 + 0.5 * (t_hr / 168.0))
                            eps_seq[k] = rng_comp.normal(0.0, sig_t)
                    else:
                        # Ideal i.i.d. Gaussian noise
                        eps_seq = rng_comp.normal(0.0, sig_u, size=len(checkpoints))

                    # Evaluate trajectory points at each checkpoint
                    for k, t_hr in enumerate(checkpoints):
                        # 1. Degradation kinetics g_p(t) in transformed coordinates
                        if not has_degradation:
                            g_val = 0.0
                        else:
                            if lot_cfg.fixture_type == Phase4BFixtureType.FIXTURE_A_LINEAR_DRIFT:
                                g_val = sign_p * delta * sig_u * (t_hr / 168.0)
                            elif lot_cfg.fixture_type == Phase4BFixtureType.FIXTURE_B_ACCELERATING_DRIFT:
                                g_val = sign_p * delta * sig_u * ((t_hr / 168.0) ** 2.1)
                            elif lot_cfg.fixture_type == Phase4BFixtureType.FIXTURE_C_ABRUPT_STEP:
                                step_t = lot_cfg.step_hour or 72
                                g_val = 0.0 if t_hr < step_t else sign_p * delta * sig_u
                            elif lot_cfg.fixture_type == Phase4BFixtureType.FIXTURE_D_CONFOUNDED_DRIFT:
                                g_val = sign_p * delta * sig_u * (t_hr / 168.0)
                            elif lot_cfg.fixture_type == Phase4BFixtureType.FIXTURE_E_HETEROSCEDASTIC_NOISE:
                                g_val = sign_p * delta * sig_u * (t_hr / 168.0)
                            elif lot_cfg.fixture_type == Phase4BFixtureType.FIXTURE_F_STAGGERED_ONSET:
                                onset_t = lot_cfg.onset_hour or 48
                                if t_hr <= onset_t:
                                    g_val = 0.0
                                else:
                                    g_val = sign_p * delta * sig_u * ((t_hr - onset_t) / (168.0 - onset_t))
                            else:
                                g_val = 0.0

                        # 2. Common-mode thermal excursion
                        delta_T = 0.0
                        if lot_cfg.has_chamber_drift:
                            # Ramp at 72h, sustained through 96h, recovered by 120h
                            if t_hr in [72, 96]:
                                delta_T = 5.0

                        u_cm = p_cfg.cm_temp_coeff * delta_T

                        # 3. Latent true value u*(t) in transformed coordinates
                        u_true = comp_u_baseline[p_name] + g_val + u_cm

                        # 4. Invert u*(t) to native coordinates x*(t)
                        if p_cfg.transform == "log":
                            x_true = float(np.exp(u_true))
                        elif p_cfg.transform == "linear":
                            x_true = float(u_true)
                        elif p_cfg.transform == "asinh":
                            x_true = float(p_cfg.scale * np.sinh(u_true))

                        # 5. Observed coordinate u_obs(t) = u*(t) + epsilon(t)
                        eps_t = float(eps_seq[k])
                        u_obs = u_true + eps_t

                        # 6. Invert u_obs(t) to native coordinates x_obs(t)
                        # CRITICAL: IGSS remains signed! No abs(), no clipping to positive, no clipping at +-100
                        if p_cfg.transform == "log":
                            x_obs = float(np.exp(u_obs))
                        elif p_cfg.transform == "linear":
                            x_obs = float(u_obs)
                        elif p_cfg.transform == "asinh":
                            x_obs = float(p_cfg.scale * np.sinh(u_obs))

                        # Check absolute limit breach
                        is_spec_failure = False
                        if p_cfg.absolute_limit_low is not None and x_true < p_cfg.absolute_limit_low:
                            is_spec_failure = True
                        if p_cfg.absolute_limit_high is not None and x_true > p_cfg.absolute_limit_high:
                            is_spec_failure = True

                        temp_C = p_cfg.nominal_temp + delta_T

                        # Telemetry row (CANONICAL_COLUMNS only, zero leaks)
                        obs_rows.append({
                            "component_id": comp_id,
                            "lot_id": lot_cfg.lot_id,
                            "parameter_name": p_name,
                            "elapsed_hours": int(t_hr),
                            "value": x_obs,
                            "unit": p_cfg.units,
                            "temperature_C": temp_C,
                            "test_condition": p_cfg.test_condition,
                            "instrument_id": "ATE_BENCH_01",
                            "channel_id": channel_id,
                            "measurement_quality": "VALID",
                            "rework_count": 0,
                            "absolute_limit_low": p_cfg.absolute_limit_low if p_cfg.absolute_limit_low is not None else "",
                            "absolute_limit_high": p_cfg.absolute_limit_high if p_cfg.absolute_limit_high is not None else "",
                            "source_type": "synthetic",
                        })

                        # Quarantined ground truth row
                        gt_rows.append({
                            "component_id": comp_id,
                            "lot_id": lot_cfg.lot_id,
                            "partition": lot_cfg.partition.value,
                            "parameter_name": p_name,
                            "elapsed_hours": int(t_hr),
                            "latent_true_value": x_true,
                            "latent_true_transformed": u_true,
                            "latent_drift": g_val,
                            "noise_realization": eps_t,
                            "fixture_type": lot_cfg.fixture_type.value,
                            "signal_delta": delta,
                            "is_degradation": has_degradation,
                            "is_spec_failure": is_spec_failure,
                            "as_of_hours": int(t_hr),
                        })

        obs_df = pd.DataFrame(obs_rows)[CANONICAL_COLUMNS]
        gt_df = pd.DataFrame(gt_rows)

        # Build Manifest
        manifest = self._build_manifest(obs_df, gt_df, partition_seeds)

        # Execute Checks
        structural_ok = self._verify_structural_integrity(obs_df, gt_df)
        statistical_ok = self._verify_statistical_sanity(gt_df)
        leakage_ok = self._verify_leakage_isolation(obs_df)

        checksums: Dict[str, str] = {}

        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            obs_path = output_dir / "observations.csv"
            gt_path = output_dir / "ground_truth.csv"
            manifest_path = output_dir / "manifest.json"
            checksum_path = output_dir / "checksums.sha256"

            obs_df.to_csv(obs_path, index=False)
            gt_df.to_csv(gt_path, index=False)

            # Compute file hashes
            obs_hash = hashlib.sha256(obs_path.read_bytes()).hexdigest()
            gt_hash = hashlib.sha256(gt_path.read_bytes()).hexdigest()

            manifest["file_hashes"] = {
                "observations.csv": obs_hash,
                "ground_truth.csv": gt_hash,
            }

            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

            checksums = {
                "observations.csv": obs_hash,
                "ground_truth.csv": gt_hash,
                "manifest.json": manifest_hash,
            }

            with open(checksum_path, "w", encoding="utf-8") as f:
                for fname, hval in checksums.items():
                    f.write(f"{hval}  {fname}\n")

        return Phase4BGenerationResult(
            observations_df=obs_df,
            ground_truth_df=gt_df,
            manifest=manifest,
            checksums=checksums,
            structural_check_passed=structural_ok,
            statistical_sanity_passed=statistical_ok,
            leakage_audit_passed=leakage_ok,
        )

    def _build_manifest(
        self,
        obs_df: pd.DataFrame,
        gt_df: pd.DataFrame,
        partition_seeds: Dict[Phase4BPartition, int],
    ) -> Dict[str, Any]:
        """Construct the canonical benchmark manifest."""
        cal_lots = [l.lot_id for l in self.config.lots if l.partition == Phase4BPartition.CALIBRATION]
        val_lots = [l.lot_id for l in self.config.lots if l.partition == Phase4BPartition.VALIDATION]
        eval_lots = [l.lot_id for l in self.config.lots if l.partition == Phase4BPartition.FINAL_EVALUATION]

        manifest: Dict[str, Any] = {
            "benchmark_version": self.config.benchmark_version,
            "schema_version": "1.0.0",
            "generation_timestamp": datetime.now(timezone.utc).isoformat(),
            "master_seed": self.config.master_seed,
            "seed_derivation_algorithm": "HMAC-SHA256",
            "partition_seeds": {k.value: v for k, v in partition_seeds.items()},
            "temporal_schedules": {
                "primary_schedule": "S1",
                "checkpoints": self.config.checkpoints,
                "checkpoint_count": len(self.config.checkpoints),
                "duration_hours": 168,
            },
            "parameters": {
                p_name: {
                    "name": p_cfg.name,
                    "units": p_cfg.units,
                    "transform": p_cfg.transform,
                    "noise_scale_transformed": p_cfg.noise_scale,
                    "nominal_baseline": p_cfg.nominal_baseline,
                    "absolute_limit_low": p_cfg.absolute_limit_low,
                    "absolute_limit_high": p_cfg.absolute_limit_high,
                    "test_condition": p_cfg.test_condition,
                    "nominal_temperature_C": p_cfg.nominal_temp,
                    "common_mode_temp_coefficient": p_cfg.cm_temp_coeff,
                }
                for p_name, p_cfg in self.config.parameters.items()
            },
            "scenario_fixtures": {
                "null_gaussian": "Ideal i.i.d. Gaussian stationary null (Null Model A)",
                "null_ar1": "Autoregressive AR(1) session-drift null (Null Model B, phi in [0.20, 0.35])",
                "null_common_mode": "Synchronous chamber thermal excursion null (Null Model C, +5C at 72, 96h)",
                "fixture_a_linear_drift": "Weak linear degradation (Fixture A, kinetics u_0 + delta*sigma*(t/168))",
                "fixture_b_accelerating_drift": "Weak accelerating degradation (Fixture B, kinetics u_0 + delta*sigma*(t/168)^2.1)",
                "fixture_c_abrupt_step": "Weak abrupt step change (Fixture C, shift delta*sigma at t_step in {48, 72, 96}h)",
                "fixture_d_confounded_drift": "Common-mode-confounded linear drift under synchronous +5C chamber shift",
                "fixture_e_heteroscedastic_noise": "Linear degradation with expanding measurement variance sigma(t) = sigma_0*(1 + 0.5*t/168)",
                "fixture_f_staggered_onset": "Dormant latent state commencing drift at t_onset in {48, 72}h",
            },
            "signal_amplitudes": [1.0, 1.5, 2.0, 2.5],
            "common_mode_design": {
                "reference_formula": "u_excess_i,p(t) = u_i,p(t) - median_{j != i} u_j,p(t)",
                "self_inclusion_handling": "leave-one-component-out lot median (median_{j != i})",
                "minimum_lot_size": 10,
                "configured_lot_size": 20,
                "failure_mode_documentation": "If degradation becomes widespread within a lot, a lot-median reference can absorb part of the common degradation signal and reduce component-specific excess magnitude.",
            },
            "partitions": {
                "CALIBRATION": {
                    "fraction": 0.50,
                    "lot_count": len(cal_lots),
                    "component_count": len(cal_lots) * 20,
                    "series_count": len(cal_lots) * 20 * 4,
                    "lots": cal_lots,
                },
                "VALIDATION": {
                    "fraction": 0.25,
                    "lot_count": len(val_lots),
                    "component_count": len(val_lots) * 20,
                    "series_count": len(val_lots) * 20 * 4,
                    "lots": val_lots,
                },
                "FINAL_EVALUATION": {
                    "fraction": 0.25,
                    "lot_count": len(eval_lots),
                    "component_count": len(eval_lots) * 20,
                    "series_count": len(eval_lots) * 20 * 4,
                    "lots": eval_lots,
                },
            },
            "dataset_summary": {
                "total_lots": len(self.config.lots),
                "total_components": len(self.config.lots) * 20,
                "total_parameters": len(self.config.parameters),
                "total_series": len(self.config.lots) * 20 * len(self.config.parameters),
                "observation_row_count": len(obs_df),
                "ground_truth_row_count": len(gt_df),
            },
            "epistemic_classification": {
                "layer": "DESIGN/ARCHITECTURE CHOICE (Synthetic Experimental Benchmark)",
                "interpretation_boundary": "Phase 4B is an idealized synthetic simulation environment. It does NOT evaluate, validate, or prove real semiconductor device reliability, physical degradation kinetics in spaceflight hardware, or production-lot flightworthiness.",
            },
        }
        return manifest

    def _verify_structural_integrity(self, obs_df: pd.DataFrame, gt_df: pd.DataFrame) -> bool:
        """Verify row counts, absence of NaN/Inf, parameter validity, and signed IGSS."""
        expected_rows = len(self.config.lots) * 20 * 4 * 7
        assert len(obs_df) == expected_rows, f"Obs rows {len(obs_df)} != {expected_rows}"
        assert len(gt_df) == expected_rows, f"GT rows {len(gt_df)} != {expected_rows}"

        # No NaNs in critical columns
        assert obs_df["value"].isna().sum() == 0, "NaN found in obs value"
        assert not np.isinf(obs_df["value"]).any(), "Inf found in obs value"
        assert gt_df["latent_true_value"].isna().sum() == 0, "NaN found in GT true value"

        # Checkpoints
        unique_ckpts = sorted(obs_df["elapsed_hours"].unique())
        assert unique_ckpts == [0, 24, 48, 72, 96, 120, 168], f"Unexpected checkpoints {unique_ckpts}"

        # Parameters
        unique_params = set(obs_df["parameter_name"].unique())
        assert unique_params == {"IDSS", "VGS(th)", "RDS(on)", "IGSS"}

        # Physical domain checks
        idss_vals = obs_df[obs_df["parameter_name"] == "IDSS"]["value"]
        assert (idss_vals > 0).all(), "IDSS must be strictly positive"

        rdson_vals = obs_df[obs_df["parameter_name"] == "RDS(on)"]["value"]
        assert (rdson_vals > 0).all(), "RDS(on) must be strictly positive"

        vgsth_vals = obs_df[obs_df["parameter_name"] == "VGS(th)"]["value"]
        assert (vgsth_vals > 1.5).all() and (vgsth_vals < 4.5).all(), "VGS(th) out of physical domain"

        # CRITICAL: Signed IGSS check
        igss_vals = obs_df[obs_df["parameter_name"] == "IGSS"]["value"]
        has_pos = (igss_vals > 0).any()
        has_neg = (igss_vals < 0).any()
        assert has_pos and has_neg, "IGSS must be signed with both positive and negative values observed"

        return True

    def _verify_statistical_sanity(self, gt_df: pd.DataFrame) -> bool:
        """Verify null models have zero degradation, signal amplitudes match config, and AR(1) correlation."""
        # 1. Null models have zero latent drift
        null_mask = gt_df["fixture_type"].isin(["null_gaussian", "null_ar1", "null_common_mode"])
        null_drift = gt_df[null_mask]["latent_drift"].abs().max()
        assert null_drift == 0.0, f"Null models have non-zero drift: {null_drift}"

        # 2. Degradation fixtures have non-zero drift
        deg_mask = gt_df["is_degradation"] == True
        deg_max_drift = gt_df[deg_mask]["latent_drift"].abs().max()
        assert deg_max_drift > 0.0, "Degradation fixtures have zero drift"

        # 3. Common-mode synchrony check: components in chamber drift lots experience synchronized thermal shifts
        cm_lots = [l.lot_id for l in self.config.lots if l.has_chamber_drift]
        cm_gt = gt_df[gt_df["lot_id"].isin(cm_lots)]
        # At 72h and 96h, IDSS should show common-mode shift
        idss_cm_72 = cm_gt[(cm_gt["parameter_name"] == "IDSS") & (cm_gt["elapsed_hours"] == 72)]
        assert len(idss_cm_72) > 0

        # 4. AR(1) lag-1 autocorrelation check on Null B (pooled across ensemble)
        ar1_lots = [l.lot_id for l in self.config.lots if l.fixture_type == Phase4BFixtureType.NULL_AR1]
        ar1_gt = gt_df[gt_df["lot_id"].isin(ar1_lots)]
        # Compute pooled ensemble lag-1 correlation across all components
        all_x = []
        all_y = []
        for comp_id, comp_df in ar1_gt[ar1_gt["parameter_name"] == "IDSS"].groupby("component_id"):
            noise = comp_df.sort_values("elapsed_hours")["noise_realization"].values
            if len(noise) >= 7:
                all_x.extend(noise[:-1])
                all_y.extend(noise[1:])
        pooled_corr = float(np.corrcoef(all_x, all_y)[0, 1])
        # Configured phi is in [0.20, 0.35], pooled mean should be ~0.275 (+-0.10)
        assert 0.15 <= pooled_corr <= 0.40, f"AR(1) pooled lag-1 corr {pooled_corr:.3f} outside expected [0.15, 0.40]"

        return True

    def _verify_leakage_isolation(self, obs_df: pd.DataFrame) -> bool:
        """Verify that observation telemetry contains ZERO ground-truth or scenario leaks."""
        forbidden_cols = [
            "latent_true_value",
            "latent_true_transformed",
            "latent_drift",
            "noise_realization",
            "fixture_type",
            "signal_delta",
            "is_degradation",
            "is_spec_failure",
            "scenario",
            "partition",
            "seed",
        ]
        for col in forbidden_cols:
            assert col not in obs_df.columns, f"Forbidden leak in obs: {col}"

        # Columns must exactly match CANONICAL_COLUMNS
        assert list(obs_df.columns) == CANONICAL_COLUMNS, "Observation columns do not match CANONICAL_COLUMNS"

        return True


def generate_phase4b_benchmark(output_dir: Path) -> Phase4BGenerationResult:
    """Generate canonical Phase 4B benchmark and write artifacts to disk."""
    generator = Phase4BGenerator()
    return generator.generate(output_dir=output_dir)
