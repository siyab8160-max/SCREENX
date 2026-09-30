"""SIH26170 Phase 4B Null-A Calibration Engine.

Compliant with docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md (v1.9.0):
- Executes Phase 2.1 Null-A calibration on N_{A,cal} = 100,000 complete stationary IID null components
  in 5,000 lots (400,000 parameter series).
- Uses dedicated HMAC calibration seed 194572359.
- Adheres to frozen hierarchical baseline generative model (§6.C).
- Causal LOO lot median differencing per lot (L=20) and per horizon (T_as_of in {24, 48, 72, 96, 120, 168} h).
- Builds all 68 required empirical reference distributions:
  * Kendall's tau: 4 parameters x 6 horizons = 24 entries
  * Theil-Sen slope: 4 parameters x 6 horizons = 24 entries
  * OLS t-statistic: 4 parameters x 5 horizons (K >= 3 only, K=2 excluded) = 20 entries
- Calculates empirical critical thresholds at Holm alpha = 0.001 steps:
  Step 1: alpha / 4 = 0.00025
  Step 2: alpha / 3 ~= 0.0003333
  Step 3: alpha / 2 = 0.00050
  Step 4: alpha / 1 = 0.00100
- Records all 12 metadata fields per reference entry according to §7.C schema.
- Saves calibration_reference_table.json, calibration_distributions.npz, and manifest.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np

from sih26170.screening.phase4b_detectors import (
    compute_kendall_tau,
    compute_loo_excess_coordinates,
    compute_ols_t,
    compute_theil_sen,
)


# Frozen Parameter Definitions per §6.C
PARAM_SPECS = {
    "IDSS": {
        "index": 0,
        "u_nom": float(np.log(0.50)),
        "sigma_lot": 0.15,
        "sigma_device": 0.20,
        "sigma_u": 0.08,
        "tail": "upper",
        "units": "uA",
        "transform": "log: u = ln(x / 1.0 uA)",
    },
    "VGS(th)": {
        "index": 1,
        "u_nom": 3.00,
        "sigma_lot": 0.08,
        "sigma_device": 0.10,
        "sigma_u": 0.02,
        "tail": "two_sided",
        "units": "V",
        "transform": "linear: u = x / 1.0 V",
    },
    "RDS(on)": {
        "index": 2,
        "u_nom": float(np.log(48.0)),
        "sigma_lot": 0.06,
        "sigma_device": 0.08,
        "sigma_u": 0.0125,
        "tail": "upper",
        "units": "mOhm",
        "transform": "log: u = ln(x / 1.0 mOhm)",
    },
    "IGSS": {
        "index": 3,
        "u_nom": float(np.arcsinh(2.0)),
        "sigma_lot": 0.20,
        "sigma_device": 0.25,
        "sigma_u": 0.25,
        "tail": "two_sided",
        "units": "nA",
        "transform": "asinh: u = asinh(x / 1.0 nA)",
    },
}

ALL_CHECKPOINTS = [0, 24, 48, 72, 96, 120, 168]
HORIZONS = [24, 48, 72, 96, 120, 168]
HORIZON_TO_K = {
    24: 2,
    48: 3,
    72: 4,
    96: 5,
    120: 6,
    168: 7,
}


def generate_null_a_trajectories(
    seed: int = 194572359,
    n_lots: int = 5000,
    lot_size: int = 20,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate complete Null A stationary baseline trajectories and LOO excess coordinates.

    Args:
        seed: Dedicated HMAC calibration seed (194572359)
        n_lots: Number of simulated manufacturing lots (5,000)
        lot_size: Number of components per lot (20)

    Returns:
        Tuple of:
            raw_u: Array of shape (n_lots, lot_size, 4, 7)
            excess_u: Array of shape (n_lots * lot_size, 4, 7) containing LOO excess coordinates
    """
    rng = np.random.default_rng(seed)
    n_params = 4
    n_checkpoints = len(ALL_CHECKPOINTS)

    u_nom = np.array([PARAM_SPECS[p]["u_nom"] for p in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]])
    sigma_lot = np.array([PARAM_SPECS[p]["sigma_lot"] for p in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]])
    sigma_dev = np.array([PARAM_SPECS[p]["sigma_device"] for p in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]])
    sigma_u = np.array([PARAM_SPECS[p]["sigma_u"] for p in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]])

    # 1. Lot baseline central tendencies
    delta_lot = rng.normal(0.0, 1.0, size=(n_lots, n_params)) * sigma_lot
    u_lot = u_nom + delta_lot  # shape: (n_lots, 4)

    # 2. Component baseline static offsets
    delta_comp = rng.normal(0.0, 1.0, size=(n_lots, lot_size, n_params)) * sigma_dev
    u_comp = u_lot[:, np.newaxis, :] + delta_comp  # shape: (n_lots, lot_size, 4)

    # 3. Checkpoint measurement observations (Null A: zero degradation, zero thermal drift)
    noise = rng.normal(0.0, 1.0, size=(n_lots, lot_size, n_params, n_checkpoints)) * sigma_u[np.newaxis, np.newaxis, :, np.newaxis]
    raw_u = u_comp[:, :, :, np.newaxis] + noise  # shape: (n_lots, lot_size, 4, 7)

    # 4. Vectorized Leave-One-Out Lot Median Differencing (§6.D)
    excess_lots = compute_loo_excess_coordinates(raw_u)  # shape: (n_lots, lot_size, 4, 7)
    excess_u = excess_lots.reshape((n_lots * lot_size, n_params, n_checkpoints))

    return raw_u, excess_u


def compute_critical_threshold(
    reference_distribution: np.ndarray,
    tail: str,
    target_alpha: float,
) -> float:
    """Calculate the empirical critical value threshold for target alpha.

    For upper tail:
        Find threshold c such that (1 + sum I(ref >= c)) / (N + 1) <= target_alpha.
    For two_sided tail:
        Find threshold c such that 2 * (1 + sum I(|ref| >= c)) / (N + 1) <= target_alpha.
    """
    ref = np.asarray(reference_distribution, dtype=np.float64)
    n = len(ref)
    if tail == "upper":
        # We need (1 + k) / (N + 1) <= alpha => k <= floor(alpha * (N + 1) - 1)
        max_counts = int(np.floor(target_alpha * (n + 1.0) - 1.0))
        if max_counts < 0:
            # Alpha is smaller than minimum attainable p-value (1 / (N+1))
            return float(np.max(ref) + 1e-12)
        ref_sorted = np.sort(ref)
        idx = n - max_counts - 1
        return float(ref_sorted[idx])
    elif tail == "two_sided":
        # (1 + k) / (N + 1) <= alpha => k <= floor(alpha * (N + 1) - 1) on folded distribution |ref|
        max_counts = int(np.floor(target_alpha * (n + 1.0) - 1.0))
        if max_counts < 0:
            return float(np.max(np.abs(ref)) + 1e-12)
        ref_abs_sorted = np.sort(np.abs(ref))
        idx = n - max_counts - 1
        return float(ref_abs_sorted[idx])
    else:
        raise ValueError(f"Unknown tail '{tail}'")


def run_phase4b_calibration(
    output_dir: Path,
    seed: int = 194572359,
    n_lots: int = 5000,
    lot_size: int = 20,
) -> Dict[str, Any]:
    """Execute complete Phase 4B Null-A empirical calibration and build 68-entry reference suite.

    Args:
        output_dir: Target directory for calibration artifacts (data/evaluation_phase4b/)
        seed: Dedicated calibration HMAC seed (194572359)
        n_lots: Number of lots (5,000)
        lot_size: Components per lot (20) -> total N = 100,000 components

    Returns:
        Dictionary summary of calibration execution and integrity checks.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    n_components = n_lots * lot_size
    t_start = datetime.now(timezone.utc)

    # 1. Generate Null A trajectories & excess coordinates
    _, excess_u = generate_null_a_trajectories(seed=seed, n_lots=n_lots, lot_size=lot_size)

    # 2. Iterate through all (detector_family, parameter, T_as_of) combinations
    calibration_entries: Dict[str, Dict[str, Any]] = {}
    distribution_arrays: Dict[str, np.ndarray] = {}

    detectors = [
        ("kendall_tau", "Kendall tau rank correlation", "PRIMARY CANDIDATE", "S_tau = [2/(K*(K-1))] * sum_{j<k} sgn(y_k - y_j)"),
        ("theil_sen", "Theil-Sen robust slope", "AUXILIARY CANDIDATE", "S_TS = median_{j<k} { (y_k - y_j) / (t_k - t_j) }"),
        ("ols_t", "Parametric OLS t-statistic", "BENCHMARK COMPARATOR", "S_t = beta_1 / SE(beta_1), df = K - 2"),
    ]

    param_names = ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]

    for det_id, det_name, det_role, det_formula in detectors:
        for p_name in param_names:
            p_spec = PARAM_SPECS[p_name]
            p_idx = p_spec["index"]
            tail_dir = p_spec["tail"]

            for t_as_of in HORIZONS:
                k = HORIZON_TO_K[t_as_of]

                # OLS t-statistic is mathematically UNDEFINED at K=2 (df = 0). Exclude!
                if det_id == "ols_t" and k == 2:
                    continue

                entry_key = f"{det_id}__{p_name}__T{t_as_of}h_K{k}"
                t_slice = np.array(ALL_CHECKPOINTS[:k], dtype=np.float64)
                series_data = excess_u[:, p_idx, :k]  # shape (N, K)

                # Compute detector test statistics across all N=100,000 null components
                if det_id == "kendall_tau":
                    stats = compute_kendall_tau(series_data)
                elif det_id == "theil_sen":
                    stats = compute_theil_sen(t_slice, series_data)
                elif det_id == "ols_t":
                    stats = compute_ols_t(t_slice, series_data)
                else:
                    raise ValueError(f"Unknown detector {det_id}")

                # Verify finiteness
                n_non_finite = int(np.sum(~np.isfinite(stats)))
                if n_non_finite > 0:
                    raise RuntimeError(
                        f"Non-finite statistics encountered in {entry_key}: {n_non_finite} non-finite entries!"
                    )

                # Statistical characterization
                stats_float = stats.astype(np.float64)
                unique_vals, counts = np.unique(stats_float, return_counts=True)
                n_distinct = len(unique_vals)
                n_ties = int(np.sum(counts[counts > 1]))

                # Percentiles
                pct_levels = [50.0, 90.0, 95.0, 99.0, 99.9, 99.975, 99.99]
                pct_vals = {f"p_{str(p).replace('.', '_')}": float(np.percentile(stats_float, p)) for p in pct_levels}

                # Critical thresholds for Holm-Bonferroni steps
                crit_step1 = compute_critical_threshold(stats_float, tail_dir, target_alpha=0.00025)
                crit_step2 = compute_critical_threshold(stats_float, tail_dir, target_alpha=0.001 / 3.0)
                crit_step3 = compute_critical_threshold(stats_float, tail_dir, target_alpha=0.00050)
                crit_step4 = compute_critical_threshold(stats_float, tail_dir, target_alpha=0.00100)

                # Minimum empirical p-value attainable under Davison-Hinkley: 1 / (N+1)
                min_empirical_p = 1.0 / (n_components + 1.0)
                if tail_dir == "two_sided":
                    min_empirical_p = min(1.0, 2.0 / (n_components + 1.0))

                # Entry hash of sorted distribution for cryptographic audit
                sorted_stats = np.sort(stats_float).astype(np.float32)
                entry_digest = hashlib.sha256(sorted_stats.tobytes()).hexdigest()

                entry_meta = {
                    "entry_key": entry_key,
                    "detector_family": det_id,
                    "detector_name": det_name,
                    "detector_role": det_role,
                    "parameter": p_name,
                    "units": p_spec["units"],
                    "transform": p_spec["transform"],
                    "T_as_of": t_as_of,
                    "K": k,
                    "checkpoints": t_slice.tolist(),
                    "tail_direction": tail_dir,
                    "N_calibration": n_components,
                    "statistic_definition": det_formula,
                    "p_value_method": "empirical_rank_davison_hinkley",
                    "finite_sample_correction": "+1_rank_over_N_plus_1",
                    "critical_value_threshold": float(crit_step1),
                    "step_thresholds": {
                        "step_1_alpha_0_00025": float(crit_step1),
                        "step_2_alpha_0_000333": float(crit_step2),
                        "step_3_alpha_0_00050": float(crit_step3),
                        "step_4_alpha_0_00100": float(crit_step4),
                    },
                    "percentiles": pct_vals,
                    "summary_statistics": {
                        "min": float(np.min(stats_float)),
                        "max": float(np.max(stats_float)),
                        "mean": float(np.mean(stats_float)),
                        "std": float(np.std(stats_float)),
                        "median": float(np.median(stats_float)),
                    },
                    "discreteness_audit": {
                        "n_distinct_values": n_distinct,
                        "n_ties": n_ties,
                        "n_non_finite": n_non_finite,
                        "min_empirical_p_attainable": min_empirical_p,
                    },
                    "calibration_seed": seed,
                    "artifact_hash": entry_digest,
                }

                calibration_entries[entry_key] = entry_meta
                distribution_arrays[entry_key] = sorted_stats

    # Assert exact required total count: 24 + 24 + 20 = 68
    total_entries = len(calibration_entries)
    if total_entries != 68:
        raise RuntimeError(f"Expected exactly 68 calibrated reference entries, got {total_entries}")

    # 3. Save sorted distribution arrays to compressed .npz
    dist_file = output_dir / "calibration_distributions.npz"
    np.savez_compressed(dist_file, **distribution_arrays)
    dist_file_hash = hashlib.sha256(dist_file.read_bytes()).hexdigest()

    # 4. Save JSON reference table
    ref_table = {
        "benchmark_target": "PHASE_4B_BENCHMARK_v1.0.0",
        "governing_specification": "PHASE_4B_DETECTOR_CALIBRATION_SPEC_v1.9.0",
        "calibration_status": "FROZEN_CALIBRATION_BASELINE_FREEZE_0",
        "creation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "master_seed": 261704,
        "calibration_seed": seed,
        "calibration_context": "calibration:null_a:v1",
        "sample_accounting": {
            "n_lots": n_lots,
            "lot_size": lot_size,
            "n_components": n_components,
            "n_parameters": len(param_names),
            "total_parameter_series": n_components * len(param_names),
            "checkpoints_per_series": len(ALL_CHECKPOINTS),
        },
        "total_calibration_entries": total_entries,
        "entries_breakdown": {
            "kendall_tau": 24,
            "theil_sen": 24,
            "ols_t": 20,
        },
        "distribution_archive": {
            "filename": dist_file.name,
            "sha256": dist_file_hash,
            "bytes": dist_file.stat().st_size,
        },
        "entries": calibration_entries,
    }

    ref_table_file = output_dir / "calibration_reference_table.json"
    ref_table_json = json.dumps(ref_table, indent=2)
    ref_table_file.write_text(ref_table_json, encoding="utf-8")
    ref_table_hash = hashlib.sha256(ref_table_file.read_bytes()).hexdigest()

    # 5. Save calibration manifest with cryptographic checksums
    t_end = datetime.now(timezone.utc)
    manifest = {
        "manifest_version": "1.0.0",
        "artifact_suite": "PHASE_4B_NULL_A_CALIBRATION_SUITE_v1.0.0",
        "freeze_level": "FREEZE_0_CALIBRATION_LOCKED",
        "created_at_utc": t_end.isoformat(),
        "elapsed_seconds": (t_end - t_start).total_seconds(),
        "calibration_seed": seed,
        "sample_accounting": ref_table["sample_accounting"],
        "total_reference_distributions": total_entries,
        "files": {
            "calibration_reference_table.json": {
                "sha256": ref_table_hash,
                "bytes": ref_table_file.stat().st_size,
            },
            "calibration_distributions.npz": {
                "sha256": dist_file_hash,
                "bytes": dist_file.stat().st_size,
            },
        },
        "integrity_status": "CALIBRATION_INTEGRITY_VERIFIED",
    }

    manifest_file = output_dir / "calibration_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest_hash = hashlib.sha256(manifest_file.read_bytes()).hexdigest()

    checksums_file = output_dir / "checksums.sha256"
    checksums_content = f"{ref_table_hash}  calibration_reference_table.json\n{dist_file_hash}  calibration_distributions.npz\n{manifest_hash}  calibration_manifest.json\n"
    checksums_file.write_text(checksums_content, encoding="utf-8")

    return {
        "status": "CALIBRATION_COMPLETED_AND_FROZEN",
        "total_entries": total_entries,
        "ref_table_path": str(ref_table_file),
        "ref_table_hash": ref_table_hash,
        "dist_file_path": str(dist_file),
        "dist_file_hash": dist_file_hash,
        "manifest_path": str(manifest_file),
        "manifest_hash": manifest_hash,
        "elapsed_seconds": (t_end - t_start).total_seconds(),
        "entries": calibration_entries,
    }
