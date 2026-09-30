"""SIH26170 Phase 4B Independent Power Sweep Engine.

Compliant with docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md (v1.9.0) §9:
- Executes Phase 4B independent power calibration sweep across all six fixture morphologies
  and all four pre-registered effect sizes delta in {1.0, 1.5, 2.0, 2.5} sigma_{u,p}.
- Uses dedicated independent HMAC seed 15152878 (§3, §9.A.2).
- Evaluates N = 10,000 components per morphology x delta cell (24 cells = 240,000 components total).
- Preserves causal as-of boundary (T_as_of in {24, 48, 72, 96, 120, 168} h).
- Preserves LOO lot-median topology and signed IGSS semantics.
- Evaluates parameter-level detection power and component-level Holm step-down detection power
  under frozen Null-A calibration reference distributions (strictly read-only, zero retuning).
- Quantifies impact of lot-synchronous common-mode structure vs outlier component degradation.
- Reports empirical power with Wilson 95% confidence intervals across:
  Power = f(Morphology, delta, Parameter, T_as_of, Detector Family).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
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
from sih26170.screening.phase4b_null_c import CM_TEMP_COEFF, DELTA_T_CELSIUS, PERTURBATION_HOURS


class Morphology(str, Enum):
    FIXTURE_A_LINEAR_DRIFT = "fixture_a_linear_drift"
    FIXTURE_B_ACCELERATING_DRIFT = "fixture_b_accelerating_drift"
    FIXTURE_C_ABRUPT_STEP = "fixture_c_abrupt_step"
    FIXTURE_D_CONFOUNDED_DRIFT = "fixture_d_confounded_drift"
    FIXTURE_E_HETEROSCEDASTIC_NOISE = "fixture_e_heteroscedastic_noise"
    FIXTURE_F_STAGGERED_ONSET = "fixture_f_staggered_onset"


ALL_MORPHOLOGIES = [
    Morphology.FIXTURE_A_LINEAR_DRIFT,
    Morphology.FIXTURE_B_ACCELERATING_DRIFT,
    Morphology.FIXTURE_C_ABRUPT_STEP,
    Morphology.FIXTURE_D_CONFOUNDED_DRIFT,
    Morphology.FIXTURE_E_HETEROSCEDASTIC_NOISE,
    Morphology.FIXTURE_F_STAGGERED_ONSET,
]

SWEEP_DELTAS = [1.0, 1.5, 2.0, 2.5]


def evaluate_degradation_kinetics(
    morphology: Morphology,
    delta: float,
    param_name: str,
    sign_p: float,
    checkpoints: List[int],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate deterministic degradation kinetics g_p(t) and noise scale for a morphology.

    Args:
        morphology: Target morphology enum
        delta: Effect size in units of sigma_{u,p}
        param_name: Parameter name (IDSS, VGS(th), RDS(on), IGSS)
        sign_p: Sign of degradation (+1.0 or -1.0)
        checkpoints: List of elapsed hours [0, 24, 48, 72, 96, 120, 168]

    Returns:
        Tuple of:
            g_t: 1D array of shape (K,) containing latent degradation kinetics
            sigma_t: 1D array of shape (K,) containing measurement noise scale
            cm_shift_t: 1D array of shape (K,) containing common-mode thermal shift
    """
    p_spec = PARAM_SPECS[param_name]
    sig_u = p_spec["sigma_u"]
    k_len = len(checkpoints)
    t_arr = np.array(checkpoints, dtype=np.float64)

    g_t = np.zeros(k_len, dtype=np.float64)
    sigma_t = np.full(k_len, sig_u, dtype=np.float64)
    cm_shift_t = np.zeros(k_len, dtype=np.float64)

    # 1. Kinetic morphologies
    if morphology == Morphology.FIXTURE_A_LINEAR_DRIFT:
        g_t = sign_p * delta * sig_u * (t_arr / 168.0)
    elif morphology == Morphology.FIXTURE_B_ACCELERATING_DRIFT:
        g_t = sign_p * delta * sig_u * ((t_arr / 168.0) ** 2.1)
    elif morphology == Morphology.FIXTURE_C_ABRUPT_STEP:
        step_t = 72.0  # Midpoint step hour
        g_t = np.where(t_arr < step_t, 0.0, sign_p * delta * sig_u)
    elif morphology == Morphology.FIXTURE_D_CONFOUNDED_DRIFT:
        g_t = sign_p * delta * sig_u * (t_arr / 168.0)
        # Thermal excursion +5C at 72h and 96h
        for k, t_hr in enumerate(checkpoints):
            if t_hr in PERTURBATION_HOURS:
                cm_shift_t[k] = CM_TEMP_COEFF[param_name] * DELTA_T_CELSIUS
    elif morphology == Morphology.FIXTURE_E_HETEROSCEDASTIC_NOISE:
        g_t = sign_p * delta * sig_u * (t_arr / 168.0)
        sigma_t = sig_u * (1.0 + 0.5 * (t_arr / 168.0))
    elif morphology == Morphology.FIXTURE_F_STAGGERED_ONSET:
        onset_t = 48.0  # Staggered onset hour
        g_t = np.where(t_arr <= onset_t, 0.0, sign_p * delta * sig_u * ((t_arr - onset_t) / (168.0 - onset_t)))

    return g_t, sigma_t, cm_shift_t


def generate_power_cell_trajectories(
    morphology: Morphology,
    delta: float,
    seed: int,
    n_components: int = 10000,
    lot_size: int = 20,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate power sweep trajectories for a single morphology x delta cell.

    Topology: Each degraded component i is placed in a manufacturing lot of size L = 20
    with 19 stationary peer components. This models individual component outlier screening
    where the lot median is formed by non-degraded peers.

    Args:
        morphology: Target morphology enum
        delta: Signal delta in sigma_{u,p}
        seed: PRNG seed for this cell
        n_components: Number of evaluated degraded components (10,000)
        lot_size: Total components per lot (20)

    Returns:
        Tuple of:
            excess_u: Array of shape (n_components, 4, 7) containing LOO excess coordinates
            raw_u: Array of shape (n_components, 4, 7) containing raw coordinates
    """
    rng = np.random.default_rng(seed)
    n_params = 4
    n_checkpoints = len(ALL_CHECKPOINTS)
    param_order = ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]

    u_nom = np.array([PARAM_SPECS[p]["u_nom"] for p in param_order])
    sigma_lot = np.array([PARAM_SPECS[p]["sigma_lot"] for p in param_order])
    sigma_dev = np.array([PARAM_SPECS[p]["sigma_device"] for p in param_order])

    # In each lot of 20: component 0 is degraded, components 1..19 are stationary null peers
    # 1. Lot baseline central tendencies
    delta_lot = rng.normal(0.0, 1.0, size=(n_components, n_params)) * sigma_lot
    u_lot = u_nom + delta_lot  # shape: (n_components, 4)

    # 2. Component static offsets within each lot
    delta_comp = rng.normal(0.0, 1.0, size=(n_components, lot_size, n_params)) * sigma_dev
    u_comp = u_lot[:, np.newaxis, :] + delta_comp  # shape: (n_components, lot_size, 4)

    # 3. Trajectory generation across checkpoints
    raw_lots = np.zeros((n_components, lot_size, n_params, n_checkpoints), dtype=np.float64)

    for p_idx, p_name in enumerate(param_order):
        # Determine signs: IDSS/RDS(on) positive (+1.0); VGS(th)/IGSS alternating (+1.0 for even, -1.0 for odd)
        comp_indices = np.arange(n_components)
        if p_name in ["IDSS", "RDS(on)"]:
            sign_p = np.ones(n_components, dtype=np.float64)
        else:
            sign_p = np.where(comp_indices % 2 == 0, 1.0, -1.0)

        # Kinetic degradation g(t) for component 0
        g_t_base, sigma_t, cm_shift = evaluate_degradation_kinetics(
            morphology=morphology,
            delta=delta,
            param_name=p_name,
            sign_p=1.0,
            checkpoints=ALL_CHECKPOINTS,
        )

        # Scale by component-specific sign
        g_t_comp0 = sign_p[:, np.newaxis] * g_t_base[np.newaxis, :]  # shape: (n_components, 7)

        # Measurement noise for all 20 devices in each lot
        # For degraded device (comp 0), noise scale is sigma_t (which expands in heteroscedastic fixture)
        noise_comp0 = rng.normal(0.0, 1.0, size=(n_components, n_checkpoints)) * sigma_t[np.newaxis, :]
        # For peer devices (comp 1..19), stationary white noise sigma_u
        p_sig_u = PARAM_SPECS[p_name]["sigma_u"]
        noise_peers = rng.normal(0.0, 1.0, size=(n_components, lot_size - 1, n_checkpoints)) * p_sig_u

        # Assemble component 0: u_comp + g_t + cm_shift + noise
        raw_lots[:, 0, p_idx, :] = (
            u_comp[:, 0, p_idx, np.newaxis]
            + g_t_comp0
            + cm_shift[np.newaxis, :]
            + noise_comp0
        )

        # Assemble peer components 1..19: u_comp + cm_shift + noise (zero degradation)
        raw_lots[:, 1:, p_idx, :] = (
            u_comp[:, 1:, p_idx, np.newaxis]
            + cm_shift[np.newaxis, np.newaxis, :]
            + noise_peers
        )

    # 4. Leave-One-Out Lot Median Differencing
    excess_lots = compute_loo_excess_coordinates(raw_lots)
    excess_u = excess_lots[:, 0, :, :]  # Degraded component 0: shape (n_components, 4, 7)
    raw_u = raw_lots[:, 0, :, :]        # Raw coordinates of component 0: shape (n_components, 4, 7)

    return excess_u, raw_u


def run_phase4b_power_sweep(
    calibration_dir: Path,
    output_dir: Path,
    seed: int = 15152878,
    n_per_cell: int = 10000,
    lot_size: int = 20,
) -> Dict[str, Any]:
    """Execute Phase 4B Independent Power Sweep across all 24 morphology x delta cells.

    Args:
        calibration_dir: Directory containing frozen calibration artifacts (data/evaluation_phase4b/)
        output_dir: Directory to save power sweep artifacts (data/evaluation_phase4b/)
        seed: Dedicated HMAC Power Sweep seed (15152878)
        n_per_cell: Number of evaluated components per cell (10,000)
        lot_size: Components per lot (20)

    Returns:
        Comprehensive dictionary of power sweep results.
    """
    calibration_dir = Path(calibration_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    t_start = datetime.now(timezone.utc)

    # 1. Verify and capture calibration artifact hashes
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

    # 2. Setup detector configurations
    detectors = [
        ("kendall_tau", "Kendall tau rank correlation", "PRIMARY CANDIDATE"),
        ("theil_sen", "Theil-Sen robust slope", "AUXILIARY CANDIDATE"),
        ("ols_t", "Parametric OLS t-statistic", "BENCHMARK COMPARATOR"),
    ]

    param_names = ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]
    master_rng = np.random.default_rng(seed)

    cell_power_results: Dict[str, Any] = {}
    total_trajectories_evaluated = 0

    # 3. Sweep across all 6 morphologies x 4 delta levels
    for morph in ALL_MORPHOLOGIES:
        for delta in SWEEP_DELTAS:
            cell_key = f"{morph.value}__delta_{delta:.1f}sigma"
            cell_seed = int(master_rng.integers(0, 2**31 - 1))

            excess_u, raw_u = generate_power_cell_trajectories(
                morphology=morph,
                delta=delta,
                seed=cell_seed,
                n_components=n_per_cell,
                lot_size=lot_size,
            )
            total_trajectories_evaluated += n_per_cell

            detector_results: Dict[str, Any] = {}

            # Evaluate each detector family
            for det_id, det_name, det_role in detectors:
                horizon_results: Dict[str, Any] = {}

                for t_as_of in HORIZONS:
                    k = HORIZON_TO_K[t_as_of]

                    if det_id == "ols_t" and k == 2:
                        continue

                    t_slice = np.array(ALL_CHECKPOINTS[:k], dtype=np.float64)
                    param_p_values = np.zeros((n_per_cell, len(param_names)), dtype=np.float64)
                    param_power_data = {}

                    # Evaluate parameter-level power
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
                        ref_dist = calib_distributions[entry_key]
                        p_vals = compute_empirical_p_value(stats_float, ref_dist, tail=tail_dir)
                        param_p_values[:, p_idx] = p_vals

                        # Step-1 detection power
                        threshold_step1 = 0.00025
                        det_mask = p_vals <= threshold_step1
                        n_det = int(np.sum(det_mask))
                        p_det = float(n_det) / float(n_per_cell)
                        ci_low, ci_high = compute_wilson_ci(n_det, n_per_cell, confidence=0.95)

                        param_power_data[p_name] = {
                            "detected_count": n_det,
                            "detection_power": p_det,
                            "wilson_ci_95": [ci_low, ci_high],
                        }

                    # Component-Level Holm Step-Down Detection Power (§8.D)
                    p_sorted = np.sort(param_p_values, axis=1)
                    alpha_step1 = 0.00025
                    comp_rejected = p_sorted[:, 0] <= alpha_step1
                    n_comp_det = int(np.sum(comp_rejected))
                    comp_power = float(n_comp_det) / float(n_per_cell)
                    comp_ci_low, comp_ci_high = compute_wilson_ci(n_comp_det, n_per_cell, confidence=0.95)

                    h_key = f"T{t_as_of}h_K{k}"
                    horizon_results[h_key] = {
                        "T_as_of": t_as_of,
                        "K": k,
                        "component_detected_count": n_comp_det,
                        "component_power": comp_power,
                        "component_wilson_ci_95": [comp_ci_low, comp_ci_high],
                        "parameter_power": param_power_data,
                    }

                detector_results[det_id] = {
                    "detector_name": det_name,
                    "detector_role": det_role,
                    "horizons": horizon_results,
                }

            # Evaluate Module A Drift Comparator on excess coordinates
            module_a_power = {}
            for t_as_of in HORIZONS:
                k = HORIZON_TO_K[t_as_of]
                comp_breach_any = np.zeros(n_per_cell, dtype=bool)
                param_drift_data = {}

                for p_idx, p_name in enumerate(param_names):
                    p_spec = PARAM_SPECS[p_name]
                    series_data = excess_u[:, p_idx, :k]
                    drifts = compute_module_a_drift(series_data, noise_scale=p_spec["sigma_u"])
                    breaches = np.abs(drifts) >= 2.5
                    n_breach = int(np.sum(breaches))
                    p_breach = float(n_breach) / float(n_per_cell)
                    ci_low, ci_high = compute_wilson_ci(n_breach, n_per_cell, confidence=0.95)

                    comp_breach_any |= breaches
                    param_drift_data[p_name] = {
                        "breach_count": n_breach,
                        "power": p_breach,
                        "wilson_ci_95": [ci_low, ci_high],
                    }

                n_comp_breaches = int(np.sum(comp_breach_any))
                comp_p_breach = float(n_comp_breaches) / float(n_per_cell)
                c_ci_low, c_ci_high = compute_wilson_ci(n_comp_breaches, n_per_cell, confidence=0.95)

                module_a_power[f"T{t_as_of}h_K{k}"] = {
                    "component_breaches": n_comp_breaches,
                    "component_power": comp_p_breach,
                    "component_wilson_ci_95": [c_ci_low, c_ci_high],
                    "parameter_power": param_drift_data,
                }

            cell_power_results[cell_key] = {
                "morphology": morph.value,
                "delta": delta,
                "n_components": n_per_cell,
                "detectors": detector_results,
                "module_a_comparator": module_a_power,
            }

    t_end = datetime.now(timezone.utc)
    elapsed = (t_end - t_start).total_seconds()

    output_payload = {
        "benchmark_target": "PHASE_4B_BENCHMARK_v1.0.0",
        "governing_specification": "docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md (v1.9.0) §9",
        "phase": "Phase 4B — Independent Power Calibration Sweep",
        "execution_timestamp_utc": t_end.isoformat(),
        "elapsed_seconds": elapsed,
        "power_seed": seed,
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
            "n_morphologies": len(ALL_MORPHOLOGIES),
            "n_deltas": len(SWEEP_DELTAS),
            "total_cells": len(cell_power_results),
            "n_components_per_cell": n_per_cell,
            "total_components_evaluated": total_trajectories_evaluated,
            "total_parameter_series_evaluated": total_trajectories_evaluated * len(param_names),
        },
        "sweep_grid": {
            "morphologies": [m.value for m in ALL_MORPHOLOGIES],
            "deltas": SWEEP_DELTAS,
            "horizons": HORIZONS,
        },
        "cell_power_results": cell_power_results,
        "epistemic_limitation_statement": (
            "Independent power sweep results quantify empirical detection power strictly within the "
            "pre-registered synthetic model. Results do not constitute empirical evidence of real semiconductor "
            "or chamber physics, and must not be used to tune thresholds retroactively."
        ),
    }

    out_file = output_dir / "power_sweep_results.json"
    out_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    # Update checksums
    h_out = hashlib.sha256(out_file.read_bytes()).hexdigest()
    checksums_file = output_dir / "checksums.sha256"
    chk_lines = checksums_file.read_text(encoding="utf-8").strip().splitlines() if checksums_file.exists() else []
    new_lines = [l for l in chk_lines if not l.endswith("power_sweep_results.json")]
    new_lines.append(f"{h_out}  power_sweep_results.json")
    checksums_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return {
        "status": "POWER_SWEEP_COMPLETED",
        "output_file": str(out_file),
        "sha256": h_out,
        "n_cells": len(cell_power_results),
        "total_components": total_trajectories_evaluated,
        "elapsed_seconds": elapsed,
        "cell_power_results": cell_power_results,
    }
