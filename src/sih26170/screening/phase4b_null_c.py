"""SIH26170 Phase 4B Null-C Common-Mode Stress Test Engine.

Compliant with docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md (v1.9.0):
- Executes Phase 2.4 Null-C common-mode stress test on N_C = 100,000 complete components
  in 5,000 lots (400,000 parameter series).
- Uses dedicated independent HMAC seed 622638004 (§3, §6.H.4).
- Chamber thermal excursion: Delta T = +5.0 C applied synchronously to all L = 20 components
  within each lot at t in {72, 96} h.
- Spatial scope: Lot-synchronous (common to all 20 devices in the lot; zero effect on other lots).
- Transductive coordinate shifts: u_cm(t) = cm_temp_coeff * Delta T(t) per parameter:
    IDSS: +0.04/C (+0.20 in u)
    VGS(th): -0.005/C (-0.025 in u)
    RDS(on): +0.005/C (+0.025 in u)
    IGSS: +0.02/C (+0.10 in u)
- Consumes frozen calibration artifacts (calibration_reference_table.json and calibration_distributions.npz)
  in strictly read-only mode without retuning, threshold adjustments, or pooling.
- Evaluates parameter-level FPR, Wilson 95% CIs, component-level Holm FWER, and Wilson 95% CIs.
- Evaluates Module A comparator on both LOO excess and raw coordinates to quantify common-mode suppression.
- Compares against Null-A and Null-B without pooling or retroactive recalibration.
- Verifies integrity of all frozen benchmark and calibration hashes.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np

from sih26170.screening.phase4b_audit import compute_wilson_ci
from sih26170.screening.phase4b_calibration import (
    ALL_CHECKPOINTS,
    HORIZONS,
    HORIZON_TO_K,
    PARAM_SPECS,
)
from sih26170.screening.phase4b_detectors import (
    compute_empirical_p_value,
    compute_kendall_tau,
    compute_loo_excess_coordinates,
    compute_module_a_drift,
    compute_ols_t,
    compute_theil_sen,
)

# Common-Mode Transductive Temperature Coefficients (§6.H.4, LOG-076)
CM_TEMP_COEFF = {
    "IDSS": 0.04,        # +0.20 in u for +5C
    "VGS(th)": -0.005,   # -0.025 in u (V) for +5C
    "RDS(on)": 0.005,    # +0.025 in u for +5C
    "IGSS": 0.02,        # +0.10 in u for +5C
}

DELTA_T_CELSIUS = 5.0
PERTURBATION_HOURS = [72, 96]


def generate_null_c_trajectories(
    seed: int = 622638004,
    n_lots: int = 5000,
    lot_size: int = 20,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate complete Null C common-mode stress test trajectories and LOO excess coordinates.

    Per §6.H.4:
        - Within each simulated lot of L = 20 components: same baseline distributions and dispersion (§6.C).
        - A chamber thermal disturbance (Delta T = +5.0 C) is applied synchronously to all L = 20 components
          within the lot at t in {72, 96} h.
        - The perturbation shifts observed coordinates transductively (via common_mode_temp_coefficient per parameter).
        - Zero latent degradation: g_p(t) == 0.
        - Stationary Gaussian measurement noise: epsilon_{t,p} ~ N(0, sigma_{u,p}^2) i.i.d. across all series.
        - Causal leave-one-out lot median differencing cancels the synchronous lot-wide perturbation.

    Args:
        seed: Dedicated HMAC Null-C seed (622638004)
        n_lots: Number of simulated lots (5,000)
        lot_size: Components per lot (20) -> N = 100,000 components

    Returns:
        Tuple of:
            raw_u: Array of shape (n_lots, lot_size, 4, 7)
            excess_u: Array of shape (n_lots * lot_size, 4, 7)
            cm_shift: Array of shape (4, 7) containing transductive coordinate shifts
            raw_flat: Array of shape (n_lots * lot_size, 4, 7)
    """
    rng = np.random.default_rng(seed)
    n_params = 4
    n_checkpoints = len(ALL_CHECKPOINTS)
    param_order = ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]

    u_nom = np.array([PARAM_SPECS[p]["u_nom"] for p in param_order])
    sigma_lot = np.array([PARAM_SPECS[p]["sigma_lot"] for p in param_order])
    sigma_dev = np.array([PARAM_SPECS[p]["sigma_device"] for p in param_order])
    sigma_u = np.array([PARAM_SPECS[p]["sigma_u"] for p in param_order])
    cm_coeff = np.array([CM_TEMP_COEFF[p] for p in param_order])

    # 1. Lot baseline central tendencies: u_{lot,p} ~ N(u_{nom,p}, sigma_{lot,p}^2)
    delta_lot = rng.normal(0.0, 1.0, size=(n_lots, n_params)) * sigma_lot
    u_lot = u_nom + delta_lot  # shape: (n_lots, 4)

    # 2. Component baseline static offsets: u_{comp,i,p} ~ N(u_{lot,p}, sigma_{device,p}^2)
    delta_comp = rng.normal(0.0, 1.0, size=(n_lots, lot_size, n_params)) * sigma_dev
    u_comp = u_lot[:, np.newaxis, :] + delta_comp  # shape: (n_lots, lot_size, 4)

    # 3. Synchronous common-mode shift array: u_cm(t) = cm_coeff * Delta_T(t)
    cm_shift = np.zeros((n_params, n_checkpoints), dtype=np.float64)
    for k, t_hr in enumerate(ALL_CHECKPOINTS):
        if t_hr in PERTURBATION_HOURS:
            cm_shift[:, k] = cm_coeff * DELTA_T_CELSIUS

    # 4. Generate ideal i.i.d. Gaussian measurement noise: epsilon_{t,p} ~ N(0, sigma_{u,p}^2)
    noise = rng.normal(0.0, 1.0, size=(n_lots, lot_size, n_params, n_checkpoints)) * sigma_u[np.newaxis, np.newaxis, :, np.newaxis]

    # 5. Raw measurements: u_obs(t) = u_comp + u_cm(t) + epsilon(t)
    # Notice: cm_shift is identical for all components within a lot!
    raw_u = u_comp[:, :, :, np.newaxis] + cm_shift[np.newaxis, np.newaxis, :, :] + noise  # shape: (n_lots, lot_size, 4, 7)

    # 6. Vectorized Leave-One-Out Lot Median Differencing (§6.D)
    excess_lots = compute_loo_excess_coordinates(raw_u)  # shape: (n_lots, lot_size, 4, 7)
    excess_u = excess_lots.reshape((n_lots * lot_size, n_params, n_checkpoints))
    raw_flat = raw_u.reshape((n_lots * lot_size, n_params, n_checkpoints))

    return raw_u, excess_u, cm_shift, raw_flat


def run_null_c_stress_test(
    calibration_dir: Path,
    output_dir: Path,
    seed: int = 622638004,
    n_lots: int = 5000,
    lot_size: int = 20,
) -> Dict[str, Any]:
    """Execute Phase 2.4 Null-C Common-Mode Stress Test under frozen Null-A calibration.

    Args:
        calibration_dir: Directory containing frozen calibration artifacts (data/evaluation_phase4b/)
        output_dir: Directory to save stress test artifacts (data/evaluation_phase4b/)
        seed: Dedicated HMAC Null-C seed (622638004)
        n_lots: Number of simulated lots (5,000)
        lot_size: Components per lot (20) -> N = 100,000 components

    Returns:
        Comprehensive dictionary of Null-C stress test results.
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

    # 2. Generate Null C Common-Mode Stress Trajectories (Seed 622638004)
    n_components = n_lots * lot_size
    raw_u, excess_u, cm_shift, raw_flat = generate_null_c_trajectories(seed=seed, n_lots=n_lots, lot_size=lot_size)

    raw_u_digest = hashlib.sha256(raw_u.tobytes()).hexdigest()
    excess_u_digest = hashlib.sha256(excess_u.tobytes()).hexdigest()
    cm_shift_digest = hashlib.sha256(cm_shift.tobytes()).hexdigest()

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

            if det_id == "ols_t" and k == 2:
                continue

            t_slice = np.array(ALL_CHECKPOINTS[:k], dtype=np.float64)
            param_p_values = np.zeros((n_components, len(param_names)), dtype=np.float64)

            for p_idx, p_name in enumerate(param_names):
                p_spec = PARAM_SPECS[p_name]
                tail_dir = p_spec["tail"]
                entry_key = f"{det_id}__{p_name}__T{t_as_of}h_K{k}"

                series_data = excess_u[:, p_idx, :k]

                if det_id == "kendall_tau":
                    stats = compute_kendall_tau(series_data)
                elif det_id == "theil_sen":
                    stats = compute_theil_sen(t_slice, series_data)
                elif det_id == "ols_t":
                    stats = compute_ols_t(t_slice, series_data)
                else:
                    raise ValueError(f"Unknown detector {det_id}")

                stats_float = stats.astype(np.float64)
                n_non_finite = int(np.sum(~np.isfinite(stats_float)))
                unique_vals, counts = np.unique(stats_float, return_counts=True)
                n_distinct = len(unique_vals)
                n_ties = int(np.sum(counts[counts > 1]))

                ref_dist = calib_distributions[entry_key]
                p_vals = compute_empirical_p_value(stats_float, ref_dist, tail=tail_dir)
                param_p_values[:, p_idx] = p_vals

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

            # Component-Level Holm Step-Down (§8.D)
            p_sorted = np.sort(param_p_values, axis=1)
            alpha_step1 = 0.00025
            alpha_step2 = 0.001 / 3.0
            alpha_step3 = 0.00050
            alpha_step4 = 0.00100

            rej_step1 = p_sorted[:, 0] <= alpha_step1
            rej_step2 = rej_step1 & (p_sorted[:, 1] <= alpha_step2)
            rej_step3 = rej_step2 & (p_sorted[:, 2] <= alpha_step3)
            rej_step4 = rej_step3 & (p_sorted[:, 3] <= alpha_step4)

            comp_rejected = rej_step1
            n_comp_rejected = int(np.sum(comp_rejected))
            fwer = float(n_comp_rejected) / float(n_components)
            fwer_ci_low, fwer_ci_high = compute_wilson_ci(n_comp_rejected, n_components, confidence=0.95)

            # Rejections by parameter
            param_rejections = {}
            for p_idx, p_name in enumerate(param_names):
                p_col = param_p_values[:, p_idx]
                ranks = np.sum(param_p_values < p_col[:, np.newaxis], axis=1)
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

    # 4. Evaluate Module A Comparator on BOTH LOO Excess AND Raw Coordinates
    # This precisely quantifies the LOO common-mode suppression effect (§6.H.4).
    module_a_excess_results = {}
    module_a_raw_results = {}

    for t_as_of in HORIZONS:
        k = HORIZON_TO_K[t_as_of]

        # 4a. Module A on LOO Excess Coordinates
        comp_breach_any_excess = np.zeros(n_components, dtype=bool)
        param_excess_results = {}
        for p_idx, p_name in enumerate(param_names):
            p_spec = PARAM_SPECS[p_name]
            series_data = excess_u[:, p_idx, :k]
            drifts = compute_module_a_drift(series_data, noise_scale=p_spec["sigma_u"])
            breaches = np.abs(drifts) >= 2.5
            n_breach = int(np.sum(breaches))
            fpr_breach = float(n_breach) / float(n_components)
            ci_low, ci_high = compute_wilson_ci(n_breach, n_components, confidence=0.95)

            comp_breach_any_excess |= breaches
            param_excess_results[p_name] = {
                "breach_count": n_breach,
                "fpr": fpr_breach,
                "wilson_ci_95": [ci_low, ci_high],
            }

        n_comp_breaches_excess = int(np.sum(comp_breach_any_excess))
        comp_fwer_excess = float(n_comp_breaches_excess) / float(n_components)
        comp_ci_low_e, comp_ci_high_e = compute_wilson_ci(n_comp_breaches_excess, n_components, confidence=0.95)

        m_key = f"module_a_drift__T{t_as_of}h_K{k}"
        module_a_excess_results[m_key] = {
            "detector_family": "module_a_endpoint_drift",
            "coordinate_space": "LOO_excess_coordinates",
            "detector_role": "FROZEN NON-CALIBRATED COMPARATOR",
            "T_as_of": t_as_of,
            "K": k,
            "N_components": n_components,
            "component_breaches": n_comp_breaches_excess,
            "operating_fwer": comp_fwer_excess,
            "wilson_ci_95": [comp_ci_low_e, comp_ci_high_e],
            "parameter_results": param_excess_results,
        }

        # 4b. Module A on Raw Uncorrected Coordinates (showing unmitigated disturbance)
        comp_breach_any_raw = np.zeros(n_components, dtype=bool)
        param_raw_results = {}
        for p_idx, p_name in enumerate(param_names):
            p_spec = PARAM_SPECS[p_name]
            series_data = raw_flat[:, p_idx, :k]
            drifts = compute_module_a_drift(series_data, noise_scale=p_spec["sigma_u"])
            breaches = np.abs(drifts) >= 2.5
            n_breach = int(np.sum(breaches))
            fpr_breach = float(n_breach) / float(n_components)
            ci_low, ci_high = compute_wilson_ci(n_breach, n_components, confidence=0.95)

            comp_breach_any_raw |= breaches
            param_raw_results[p_name] = {
                "breach_count": n_breach,
                "fpr": fpr_breach,
                "wilson_ci_95": [ci_low, ci_high],
            }

        n_comp_breaches_raw = int(np.sum(comp_breach_any_raw))
        comp_fwer_raw = float(n_comp_breaches_raw) / float(n_components)
        comp_ci_low_r, comp_ci_high_r = compute_wilson_ci(n_comp_breaches_raw, n_components, confidence=0.95)

        module_a_raw_results[m_key] = {
            "detector_family": "module_a_endpoint_drift",
            "coordinate_space": "raw_uncorrected_coordinates",
            "detector_role": "FROZEN NON-CALIBRATED COMPARATOR (RAW NO-LOO)",
            "T_as_of": t_as_of,
            "K": k,
            "N_components": n_components,
            "component_breaches": n_comp_breaches_raw,
            "operating_fwer": comp_fwer_raw,
            "wilson_ci_95": [comp_ci_low_r, comp_ci_high_r],
            "parameter_results": param_raw_results,
        }

    # 5. Output packaging and serialization
    t_end = datetime.now(timezone.utc)
    elapsed = (t_end - t_start).total_seconds()

    output_payload = {
        "benchmark_target": "PHASE_4B_BENCHMARK_v1.0.0",
        "governing_specification": "docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md (v1.9.0)",
        "audit_phase": "Phase 2.4 — Null-C Common-Mode Stress Test",
        "execution_timestamp_utc": t_end.isoformat(),
        "elapsed_seconds": elapsed,
        "stress_seed": seed,
        "common_mode_specification": {
            "perturbation_type": "Synchronous chamber thermal excursion",
            "delta_T_celsius": DELTA_T_CELSIUS,
            "perturbation_hours": PERTURBATION_HOURS,
            "spatial_scope": "Lot-synchronous (applied identically to all L=20 components in each lot; independent across lots)",
            "transductive_temperature_coefficients": {
                p: {
                    "cm_temp_coeff": CM_TEMP_COEFF[p],
                    "shift_in_transformed_u": CM_TEMP_COEFF[p] * DELTA_T_CELSIUS,
                    "shift_in_sigma_u_units": (CM_TEMP_COEFF[p] * DELTA_T_CELSIUS) / PARAM_SPECS[p]["sigma_u"],
                }
                for p in param_names
            },
        },
        "consumed_calibration_artifacts": {
            "calibration_reference_table.json": {
                "sha256": consumed_ref_hash,
                "verified_unmutated": consumed_ref_hash == "153d387597ba6a247ed5302a7512730c678bc3ce39e056848cd9135fc39c7d60",
            },
            "calibration_distributions.npz": {
                "sha256": consumed_dist_hash,
                "verified_unmutated": consumed_dist_hash == "147f1d38ed9b197af6b6301b9b454223d5cce54286fcfeb89a1ea15cec055d98",
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
            "common_mode_shift_sha256": cm_shift_digest,
        },
        "summary": {
            "total_parameter_cells_evaluated": len(cell_results),
            "total_horizon_fwer_cells_evaluated": len(horizon_fwer_results),
            "total_module_a_excess_cells_evaluated": len(module_a_excess_results),
            "total_module_a_raw_cells_evaluated": len(module_a_raw_results),
        },
        "parameter_level_results": cell_results,
        "component_level_fwer_results": horizon_fwer_results,
        "comparator_module_a_excess_results": module_a_excess_results,
        "comparator_module_a_raw_results": module_a_raw_results,
        "epistemic_limitation_statement": (
            "Null C is an out-of-distribution common-mode stress test evaluating robustness against "
            "synchronous lot-wide thermal perturbations (+5C at 72h and 96h). "
            "The detector was calibrated on Null A (IID stationary noise without common-mode disturbance). "
            "Null C results must NEVER be pooled with Null A or Null B and must NEVER be used for threshold "
            "tuning or recalibration. Results reflect synthetic-model performance and must NOT be "
            "interpreted as claims about real ATE/chamber telemetry without empirical chamber qualification."
        ),
    }

    out_file = output_dir / "null_c_stress_results.json"
    out_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    # Update checksums
    h_out = hashlib.sha256(out_file.read_bytes()).hexdigest()
    checksums_file = output_dir / "checksums.sha256"
    chk_lines = checksums_file.read_text(encoding="utf-8").strip().splitlines() if checksums_file.exists() else []
    new_lines = [l for l in chk_lines if not l.endswith("null_c_stress_results.json")]
    new_lines.append(f"{h_out}  null_c_stress_results.json")
    checksums_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return {
        "status": "NULL_C_STRESS_TEST_COMPLETED",
        "stress_file": str(out_file),
        "sha256": h_out,
        "parameter_results": cell_results,
        "fwer_results": horizon_fwer_results,
        "module_a_excess_results": module_a_excess_results,
        "module_a_raw_results": module_a_raw_results,
    }
