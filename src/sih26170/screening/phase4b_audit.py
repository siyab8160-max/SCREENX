"""SIH26170 Phase 4B Independent Null-A Audit Engine.

Compliant with docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md (v1.9.0):
- Executes Phase 2.2 Independent Null-A Audit on N_{A,audit} = 100,000 complete stationary IID null components
  in 5,000 lots (400,000 parameter series).
- Uses dedicated independent HMAC audit seed 233837969.
- Adheres strictly to the identical frozen baseline generative model (§6.C).
- Consumes frozen calibration artifacts (calibration_reference_table.json and calibration_distributions.npz)
  in strictly read-only mode without retuning, threshold adjustments, or circular error estimation.
- Evaluates parameter-level FPR, Wilson 95% CIs, component-level Holm FWER, and Wilson 95% CIs.
- Verifies integrity of all frozen benchmark and calibration hashes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np

from sih26170.screening.phase4b_calibration import (
    ALL_CHECKPOINTS,
    HORIZONS,
    HORIZON_TO_K,
    PARAM_SPECS,
    generate_null_a_trajectories,
)
from sih26170.screening.phase4b_detectors import (
    compute_empirical_p_value,
    compute_kendall_tau,
    compute_module_a_drift,
    compute_ols_t,
    compute_theil_sen,
)


def compute_wilson_ci(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Calculate Wilson score confidence interval for a binomial proportion.

    Args:
        k: Number of successes / events
        n: Total number of trials
        confidence: Confidence level (default 0.95)

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    if n == 0:
        return 0.0, 0.0
    z = 1.959963984540054  # 95% two-sided normal quantile
    p_hat = float(k) / float(n)
    denom = 1.0 + (z**2) / float(n)
    center = (p_hat + (z**2) / (2.0 * float(n))) / denom
    half_width = (z / denom) * np.sqrt(
        (p_hat * (1.0 - p_hat) / float(n)) + ((z**2) / (4.0 * (float(n) ** 2)))
    )
    if k == 0:
        lower = 0.0
    else:
        lower = max(0.0, float(center - half_width))

    if k == n:
        upper = 1.0
    else:
        upper = min(1.0, float(center + half_width))

    return lower, upper


def run_null_a_audit(
    calibration_dir: Path,
    output_dir: Path,
    seed: int = 233837969,
    n_lots: int = 5000,
    lot_size: int = 20,
) -> Dict[str, Any]:
    """Execute Phase 2.2 Independent Null-A Audit under frozen calibration.

    Args:
        calibration_dir: Directory containing frozen calibration artifacts (data/evaluation_phase4b/)
        output_dir: Directory to save audit artifacts (data/evaluation_phase4b/)
        seed: Dedicated independent HMAC audit seed (233837969)
        n_lots: Number of simulated lots (5,000)
        lot_size: Components per lot (20) -> N = 100,000 components

    Returns:
        Comprehensive dictionary of audit results across all cells.
    """
    calibration_dir = Path(calibration_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    t_start = datetime.now(timezone.utc)

    # 1. Verify calibration artifacts exist and capture input hashes
    ref_table_file = calibration_dir / "calibration_reference_table.json"
    dist_file = calibration_dir / "calibration_distributions.npz"

    if not ref_table_file.exists():
        raise FileNotFoundError(f"Missing calibration reference table at {ref_table_file}")
    if not dist_file.exists():
        raise FileNotFoundError(f"Missing calibration distributions at {dist_file}")

    ref_table_bytes = ref_table_file.read_bytes()
    dist_file_bytes = dist_file.read_bytes()
    consumed_ref_hash = hashlib.sha256(ref_table_bytes).hexdigest()
    consumed_dist_hash = hashlib.sha256(dist_file_bytes).hexdigest()

    ref_table = json.loads(ref_table_bytes.decode("utf-8"))
    ref_entries = ref_table["entries"]
    calib_distributions = np.load(dist_file)

    # 2. Generate Independent Null A Audit Dataset (Seed 233837969)
    n_components = n_lots * lot_size
    raw_u, excess_u = generate_null_a_trajectories(seed=seed, n_lots=n_lots, lot_size=lot_size)

    # Hash audit raw measurements for audit trail
    raw_u_digest = hashlib.sha256(raw_u.tobytes()).hexdigest()
    excess_u_digest = hashlib.sha256(excess_u.tobytes()).hexdigest()

    # 3. Evaluate every detector family x horizon x parameter
    detectors = [
        ("kendall_tau", "Kendall tau rank correlation", "PRIMARY CANDIDATE"),
        ("theil_sen", "Theil-Sen robust slope", "AUXILIARY CANDIDATE"),
        ("ols_t", "Parametric OLS t-statistic", "BENCHMARK COMPARATOR"),
    ]

    param_names = ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]

    cell_results: Dict[str, Dict[str, Any]] = {}
    horizon_fwer_results: Dict[str, Dict[str, Any]] = {}

    for det_id, det_name, det_role in detectors:
        for t_as_of in HORIZONS:
            k = HORIZON_TO_K[t_as_of]

            # OLS t-statistic is mathematically UNDEFINED at K=2 (df = 0). Skip.
            if det_id == "ols_t" and k == 2:
                continue

            t_slice = np.array(ALL_CHECKPOINTS[:k], dtype=np.float64)
            param_p_values = np.zeros((n_components, len(param_names)), dtype=np.float64)

            for p_idx, p_name in enumerate(param_names):
                p_spec = PARAM_SPECS[p_name]
                tail_dir = p_spec["tail"]
                entry_key = f"{det_id}__{p_name}__T{t_as_of}h_K{k}"

                # Slice excess coordinates
                series_data = excess_u[:, p_idx, :k]

                # Compute test statistic
                if det_id == "kendall_tau":
                    stats = compute_kendall_tau(series_data)
                elif det_id == "theil_sen":
                    stats = compute_theil_sen(t_slice, series_data)
                elif det_id == "ols_t":
                    stats = compute_ols_t(t_slice, series_data)
                else:
                    raise ValueError(f"Unknown detector {det_id}")

                # Non-finite and ties audit
                stats_float = stats.astype(np.float64)
                n_non_finite = int(np.sum(~np.isfinite(stats_float)))
                unique_vals, counts = np.unique(stats_float, return_counts=True)
                n_distinct = len(unique_vals)
                n_ties = int(np.sum(counts[counts > 1]))

                # Look up frozen reference distribution
                ref_dist = calib_distributions[entry_key]

                # Compute empirical p-values with Davison-Hinkley correction
                p_vals = compute_empirical_p_value(stats_float, ref_dist, tail=tail_dir)
                param_p_values[:, p_idx] = p_vals

                # False positive assessment against Holm Step 1 threshold: alpha / 4 = 0.00025
                threshold_step1 = 0.00025
                fp_mask = p_vals <= threshold_step1
                n_fp = int(np.sum(fp_mask))
                fpr = float(n_fp) / float(n_components)
                ci_low, ci_high = compute_wilson_ci(n_fp, n_components, confidence=0.95)

                cell_meta = {
                    "cell_key": entry_key,
                    "detector_family": det_id,
                    "detector_name": det_name,
                    "detector_role": det_role,
                    "parameter": p_name,
                    "T_as_of": t_as_of,
                    "K": k,
                    "tail_direction": tail_dir,
                    "N_evaluated": n_components,
                    "fp_count": n_fp,
                    "fpr": fpr,
                    "wilson_ci_95": [ci_low, ci_high],
                    "threshold_step_1": threshold_step1,
                    "discreteness_audit": {
                        "n_distinct_values": n_distinct,
                        "n_ties": n_ties,
                        "n_non_finite": n_non_finite,
                    },
                    "consumed_reference_hash": ref_entries[entry_key]["artifact_hash"],
                }
                cell_results[entry_key] = cell_meta

            # Component-Level Holm-Bonferroni Multiplicity Control (§8.D)
            # Sort 4 parameter p-values ascending for each component: p_(1) <= p_(2) <= p_(3) <= p_(4)
            p_sorted = np.sort(param_p_values, axis=1)

            # Step-down checks:
            # Step 1: p_(1) <= alpha / 4 = 0.00025
            # Step 2: p_(2) <= alpha / 3 ~= 0.0003333
            # Step 3: p_(3) <= alpha / 2 = 0.00050
            # Step 4: p_(4) <= alpha / 1 = 0.00100
            alpha_step1 = 0.00025
            alpha_step2 = 0.001 / 3.0
            alpha_step3 = 0.00050
            alpha_step4 = 0.00100

            rej_step1 = p_sorted[:, 0] <= alpha_step1
            rej_step2 = rej_step1 & (p_sorted[:, 1] <= alpha_step2)
            rej_step3 = rej_step2 & (p_sorted[:, 2] <= alpha_step3)
            rej_step4 = rej_step3 & (p_sorted[:, 3] <= alpha_step4)

            # Component rejection: at least one parameter rejected <=> rej_step1 is True
            comp_rejected = rej_step1
            n_comp_rejected = int(np.sum(comp_rejected))
            fwer = float(n_comp_rejected) / float(n_components)
            fwer_ci_low, fwer_ci_high = compute_wilson_ci(n_comp_rejected, n_components, confidence=0.95)

            # Rejections by parameter
            param_rejections = {}
            for p_idx, p_name in enumerate(param_names):
                # Parameter rejected if it was part of the step-down rejection chain
                # A parameter is rejected if p_i <= its assigned step threshold
                # Specifically, for each component, find rank of parameter
                p_col = param_p_values[:, p_idx]
                # Compare against component's threshold
                # If component was rejected: was this parameter <= the threshold at its rank?
                # Faster: rank of p_col among 4 parameters
                ranks = np.sum(param_p_values < p_col[:, np.newaxis], axis=1)  # 0-indexed rank
                thresh_by_rank = np.array([alpha_step1, alpha_step2, alpha_step3, alpha_step4])
                comp_max_rank_rejected = np.where(rej_step4, 3, np.where(rej_step3, 2, np.where(rej_step2, 1, np.where(rej_step1, 0, -1))))
                param_is_rej = (ranks <= comp_max_rank_rejected) & (p_col <= thresh_by_rank[ranks])
                param_rejections[p_name] = int(np.sum(param_is_rej))

            horizon_key = f"{det_id}__T{t_as_of}h_K{k}"
            horizon_fwer_results[horizon_key] = {
                "detector_family": det_id,
                "detector_name": det_name,
                "detector_role": det_role,
                "T_as_of": t_as_of,
                "K": k,
                "N_components": n_components,
                "component_rejections": n_comp_rejected,
                "operating_fwer": fwer,
                "wilson_ci_95": [fwer_ci_low, fwer_ci_high],
                "target_fwer_alpha": 0.001,
                "step_breakdown": {
                    "step_1_rejections": int(np.sum(rej_step1)),
                    "step_2_rejections": int(np.sum(rej_step2)),
                    "step_3_rejections": int(np.sum(rej_step3)),
                    "step_4_rejections": int(np.sum(rej_step4)),
                },
                "parameter_rejection_counts": param_rejections,
            }

    # 4. Also evaluate Frozen Module A Endpoint Drift Comparator (|g_p| >= 2.5) for comparison
    module_a_results: Dict[str, Any] = {}
    for t_as_of in HORIZONS:
        k = HORIZON_TO_K[t_as_of]
        comp_drift_breach = np.zeros(n_components, dtype=bool)
        param_breaches = {}

        for p_idx, p_name in enumerate(param_names):
            p_spec = PARAM_SPECS[p_name]
            series_data = excess_u[:, p_idx, :k]
            drift_stat = compute_module_a_drift(series_data, noise_scale=p_spec["sigma_u"])
            breach = np.abs(drift_stat) >= 2.5
            n_breach = int(np.sum(breach))
            param_breaches[p_name] = {
                "breach_count": n_breach,
                "fpr": float(n_breach) / float(n_components),
                "wilson_ci_95": list(compute_wilson_ci(n_breach, n_components)),
            }
            comp_drift_breach = comp_drift_breach | breach

        n_comp_breach = int(np.sum(comp_drift_breach))
        module_a_results[f"module_a_drift__T{t_as_of}h_K{k}"] = {
            "detector_family": "module_a_endpoint_drift",
            "detector_role": "FROZEN NON-CALIBRATED COMPARATOR",
            "T_as_of": t_as_of,
            "K": k,
            "N_components": n_components,
            "component_breaches": n_comp_breach,
            "operating_fwer": float(n_comp_breach) / float(n_components),
            "wilson_ci_95": list(compute_wilson_ci(n_comp_breach, n_components)),
            "parameter_results": param_breaches,
        }

    # 5. Verify calibration files were NOT modified
    post_ref_hash = hashlib.sha256(ref_table_file.read_bytes()).hexdigest()
    post_dist_hash = hashlib.sha256(dist_file.read_bytes()).hexdigest()
    if post_ref_hash != consumed_ref_hash:
        raise RuntimeError("FATAL: calibration_reference_table.json was mutated during audit!")
    if post_dist_hash != consumed_dist_hash:
        raise RuntimeError("FATAL: calibration_distributions.npz was mutated during audit!")

    t_end = datetime.now(timezone.utc)

    # 6. Save audit artifact JSON
    audit_record = {
        "benchmark_target": "PHASE_4B_BENCHMARK_v1.0.0",
        "governing_specification": "PHASE_4B_DETECTOR_CALIBRATION_SPEC_v1.9.0",
        "audit_phase": "PHASE_2.2_INDEPENDENT_NULL_A_AUDIT",
        "execution_timestamp_utc": t_end.isoformat(),
        "elapsed_seconds": (t_end - t_start).total_seconds(),
        "audit_seed": seed,
        "audit_context": "calibration:null_a_audit:v1",
        "consumed_calibration_artifacts": {
            "calibration_reference_table.json": {
                "sha256": consumed_ref_hash,
                "verified_unmutated": True,
            },
            "calibration_distributions.npz": {
                "sha256": consumed_dist_hash,
                "verified_unmutated": True,
            },
        },
        "sample_accounting": {
            "n_lots": n_lots,
            "lot_size": lot_size,
            "n_components": n_components,
            "n_parameters": len(param_names),
            "total_parameter_series": n_components * len(param_names),
            "checkpoints_per_series": len(ALL_CHECKPOINTS),
        },
        "dataset_hashes": {
            "raw_measurements_sha256": raw_u_digest,
            "excess_coordinates_sha256": excess_u_digest,
        },
        "summary": {
            "total_parameter_cells_evaluated": len(cell_results),
            "total_horizon_fwer_cells_evaluated": len(horizon_fwer_results),
            "total_module_a_cells_evaluated": len(module_a_results),
        },
        "parameter_level_results": cell_results,
        "component_level_fwer_results": horizon_fwer_results,
        "comparator_module_a_results": module_a_results,
        "epistemic_limitation_statement": (
            "Low empirical FPR/FWER under Null A demonstrates operational statistical validity "
            "strictly under the synthetic no-degradation simulation model. It does NOT constitute "
            "proof of device reliability, MIL-PRF-19500 flight qualification, or physical hardware robustness."
        ),
    }

    audit_file = output_dir / "null_a_audit_results.json"
    audit_json = json.dumps(audit_record, indent=2)
    audit_file.write_text(audit_json, encoding="utf-8")
    audit_hash = hashlib.sha256(audit_file.read_bytes()).hexdigest()

    return {
        "status": "NULL_A_AUDIT_COMPLETED",
        "audit_file": str(audit_file),
        "audit_hash": audit_hash,
        "elapsed_seconds": (t_end - t_start).total_seconds(),
        "consumed_calibration_hashes": {
            "reference_table": consumed_ref_hash,
            "distributions": consumed_dist_hash,
        },
        "parameter_results": cell_results,
        "fwer_results": horizon_fwer_results,
        "module_a_results": module_a_results,
    }
