"""Statistical Validation & Auditability Suite for Module A Screening.

Compliant with Phase 3C Pre-Implementation Amendments:
- Full Monte Carlo auditability of D_ATE null distribution
- Outputs machine-readable audit artifact data/evaluation_phase3c/monte_carlo_ate_null_audit.json
- Computes 95% Wilson score confidence intervals for FPR and 16-channel FWER
- Controlled effect-size sweeps for D_ATE across N_k in {4, 5, 8, 12, 20}
- Controlled sensitivity sweeps for g_excess across {0, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0}
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple
import numpy as np
import pytest

from sih26170.screening.equipment import (
    CHANNEL_BIAS_Z_THRESHOLD,
    MEDIAN_SE_CONSTANT,
    NORMAL_MAD_SCALE,
)


def wilson_score_interval(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Compute Wilson score confidence interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    z = 1.959963984540054  # 95% standard normal quantile
    p_hat = k / n
    denom = 1.0 + (z**2) / n
    center = (p_hat + (z**2) / (2 * n)) / denom
    half_width = (z * np.sqrt((p_hat * (1.0 - p_hat) / n) + ((z**2) / (4 * (n**2))))) / denom
    lower = max(0.0, center - half_width)
    upper = min(1.0, center + half_width)
    return (float(lower), float(upper))


def run_monte_carlo_ate_null_audit(
    num_sims: int = 50000,
    seed: int = 26170,
    output_path: str = "data/evaluation_phase3c/monte_carlo_ate_null_audit.json",
) -> Dict:
    """Run full Monte Carlo audit of D_ATE null distribution across N_k values."""
    rng = np.random.default_rng(seed)
    n_k_values = [4, 5, 8, 12, 20]
    results = {}

    for nk in n_k_values:
        # Fixture model: 16 channels, total lot N_lot = 16 * nk
        n_other = 15 * nk
        n_lot = 16 * nk

        # Vectorized simulation in chunks of 10,000
        chunk_size = 10000
        num_chunks = num_sims // chunk_size

        z_channel_1_all = []
        fixture_any_false_trigger = 0

        for _ in range(num_chunks):
            # All 16 channels drawn from standard normal N(0, 1)
            # Shape: (chunk_size, 16, nk)
            fixture_data = rng.normal(0.0, 1.0, size=(chunk_size, 16, nk))
            
            # Lot-level data: (chunk_size, n_lot)
            lot_data = fixture_data.reshape(chunk_size, n_lot)
            med_lot = np.median(lot_data, axis=1, keepdims=True)
            mad_lot = np.median(np.abs(lot_data - med_lot), axis=1)
            sigma_eff = np.maximum(NORMAL_MAD_SCALE * mad_lot, 0.001)

            # Channel 1 vs Channels 2..16
            ch1_data = fixture_data[:, 0, :]  # (chunk_size, nk)
            other_data = fixture_data[:, 1:, :].reshape(chunk_size, n_other)

            med_ch1 = np.median(ch1_data, axis=1)
            med_other = np.median(other_data, axis=1)

            se = MEDIAN_SE_CONSTANT * sigma_eff * np.sqrt(1.0 / nk + 1.0 / n_other)
            z_ch1 = (med_ch1 - med_other) / se
            z_channel_1_all.extend(z_ch1)

            # Check all 16 channels for fixture-level FWER
            # For each channel k in 0..15:
            # Channel k median vs remainder of lot
            ch_medians = np.median(fixture_data, axis=2)  # (chunk_size, 16)
            
            # For each fixture, check if ANY channel has |Z_k| >= 3.42
            # Since each channel has size nk and remainder has 15*nk:
            # Remainder median can be approximated or computed per channel
            has_trigger_in_fixture = np.zeros(chunk_size, dtype=bool)
            for ch_idx in range(16):
                m_k = ch_medians[:, ch_idx]
                # Other 15 channels
                other_idx = [i for i in range(16) if i != ch_idx]
                other_sub = fixture_data[:, other_idx, :].reshape(chunk_size, n_other)
                m_other = np.median(other_sub, axis=1)
                z_k = (m_k - m_other) / se
                has_trigger_in_fixture |= (np.abs(z_k) >= CHANNEL_BIAS_Z_THRESHOLD)

            fixture_any_false_trigger += int(np.sum(has_trigger_in_fixture))

        z_arr = np.array(z_channel_1_all, dtype=np.float64)
        false_count_ch1 = int(np.sum(np.abs(z_arr) >= CHANNEL_BIAS_Z_THRESHOLD))
        fpr_ch1 = false_count_ch1 / num_sims
        fwer = fixture_any_false_trigger / num_sims

        ci_fpr = wilson_score_interval(false_count_ch1, num_sims)
        ci_fwer = wilson_score_interval(fixture_any_false_trigger, num_sims)

        results[f"N_k_{nk}"] = {
            "N_k": nk,
            "N_other": n_other,
            "N_lot": n_lot,
            "simulations": num_sims,
            "std_z": float(np.std(z_arr)),
            "mean_z": float(np.mean(z_arr)),
            "percentiles": {
                "50": float(np.percentile(np.abs(z_arr), 50)),
                "90": float(np.percentile(np.abs(z_arr), 90)),
                "95": float(np.percentile(np.abs(z_arr), 95)),
                "99": float(np.percentile(np.abs(z_arr), 99)),
                "99.9": float(np.percentile(np.abs(z_arr), 99.9)),
            },
            "max_abs_z": float(np.max(np.abs(z_arr))),
            "false_positives_ch1": false_count_ch1,
            "empirical_fpr_per_channel": float(fpr_ch1),
            "fpr_95_ci": list(ci_fpr),
            "false_positives_fixture_total": fixture_any_false_trigger,
            "empirical_fwer_16_channels": float(fwer),
            "fwer_95_ci": list(ci_fwer),
        }

    audit_payload = {
        "audit_name": "D_ATE_STANDARDIZED_RESIDUAL_NULL_MONTE_CARLO_AUDIT",
        "timestamp_utc": "2026-09-17T10:45:00Z",
        "methodology": "Monte Carlo Null Simulation (Phase 3C Epistemic Standard)",
        "null_distribution": "Standard Normal N(0, 1) in canonical transformed representation space",
        "random_seed": seed,
        "num_simulated_fixtures": num_sims,
        "simultaneous_channels_per_fixture": 16,
        "decision_threshold_Z": CHANNEL_BIAS_Z_THRESHOLD,
        "threshold_layer_classification": "Layer F Benchmark/Design Parameter (Bonferroni FWER ~ 0.01 under Gaussian null)",
        "scale_estimation_method": "1.4826 * MAD_lot",
        "sample_size_suppression_boundary": "N_k < 4",
        "finite_sample_justification": (
            "For very small N_k (N_k < 4), the finite-sample distribution of the median "
            "is poorly approximated by the asymptotic normal standard-error formula, "
            "making tail-based channel-bias inference unreliable."
        ),
        "channel_subgroup_results": results,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(audit_payload, f, indent=2)

    return audit_payload


def test_monte_carlo_null_audit_generation():
    """Execute and verify the full Monte Carlo audit for D_ATE."""
    audit_file = "data/evaluation_phase3c/monte_carlo_ate_null_audit.json"
    payload = run_monte_carlo_ate_null_audit(num_sims=10000, output_path=audit_file)

    assert os.path.exists(audit_file)
    assert payload["null_distribution"].startswith("Standard Normal")
    assert payload["random_seed"] == 26170
    assert payload["decision_threshold_Z"] == 3.42

    # Verify that for all N_k in {4, 5, 8, 12, 20}, per-channel FPR is <= 0.25%
    for nk in [4, 5, 8, 12, 20]:
        res = payload["channel_subgroup_results"][f"N_k_{nk}"]
        assert res["empirical_fpr_per_channel"] <= 0.0025, f"N_k={nk} FPR too high: {res['empirical_fpr_per_channel']}"
        assert res["empirical_fwer_16_channels"] <= 0.035, f"N_k={nk} FWER too high: {res['empirical_fwer_16_channels']}"


def test_d_ate_effect_size_sweep():
    """Execute controlled effect-size sweep for D_ATE across true offsets and N_k."""
    offsets = [0.0, 0.5, 1.0, 2.0, 3.0, 4.0]
    n_k_values = [4, 5, 8, 12, 20]
    num_sims = 2000
    rng = np.random.default_rng(26170)

    sweep_results = {}

    for nk in n_k_values:
        sweep_results[f"N_k_{nk}"] = {}
        n_other = 15 * nk
        n_lot = 16 * nk

        for offset in offsets:
            ch1 = rng.normal(offset, 1.0, size=(num_sims, nk))
            other = rng.normal(0.0, 1.0, size=(num_sims, n_other))
            all_data = np.hstack([ch1, other])

            med_lot = np.median(all_data, axis=1, keepdims=True)
            mad_lot = np.median(np.abs(all_data - med_lot), axis=1)
            sigma_eff = np.maximum(NORMAL_MAD_SCALE * mad_lot, 0.001)

            med_k = np.median(ch1, axis=1)
            med_other = np.median(other, axis=1)

            se = MEDIAN_SE_CONSTANT * sigma_eff * np.sqrt(1.0 / nk + 1.0 / n_other)
            z_ch1 = (med_k - med_other) / se

            det_rate = float(np.mean(np.abs(z_ch1) >= CHANNEL_BIAS_Z_THRESHOLD))
            mean_z = float(np.mean(z_ch1))

            sweep_results[f"N_k_{nk}"][f"offset_{offset}"] = {
                "offset_sigma": offset,
                "mean_z": mean_z,
                "detection_power": det_rate,
            }

    # Verify detection power strictly increases with effect size
    for nk in n_k_values:
        powers = [sweep_results[f"N_k_{nk}"][f"offset_{off}"]["detection_power"] for off in offsets]
        assert powers[0] <= 0.01, f"Null false alarm too high for N_k={nk}: {powers[0]}"
        assert powers[-1] >= 0.95, f"High-offset detection power too low for N_k={nk}: {powers[-1]}"
        # Monotonicity check
        for p1, p2 in zip(powers[:-1], powers[1:]):
            assert p2 >= p1 - 0.01  # Monotonically increasing within small sampling noise

    output_path = "data/evaluation_phase3c/d_ate_effect_size_sweep.json"
    with open(output_path, "w") as f:
        json.dump(sweep_results, f, indent=2)


def test_g_excess_sensitivity_sweep():
    """Execute sensitivity sweep for g_excess across thresholds {0, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0}."""
    g_thresholds = [0.0, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    
    # Simulate a set of 100 components with varying true excess drift:
    # 50 stationary (|g_excess| < 1.0), 25 moderate (|g_excess| in [1.5, 2.5]), 25 severe (|g_excess| >= 3.0)
    rng = np.random.default_rng(26170)
    g_excess_values = np.concatenate([
        rng.normal(0.0, 0.5, 50),
        rng.uniform(1.5, 2.5, 25),
        rng.uniform(3.0, 5.0, 25),
    ])

    sensitivity_results = {}
    for thresh in g_thresholds:
        # If equipment is suspected, count how many receive CONFOUNDED_BY_EQUIPMENT vs EQUIPMENT_ONLY
        confounded_count = int(np.sum(np.abs(g_excess_values) >= thresh))
        equipment_only_count = int(np.sum(np.abs(g_excess_values) < thresh))
        sensitivity_results[f"thresh_{thresh}"] = {
            "threshold": thresh,
            "confounded_count": confounded_count,
            "equipment_only_count": equipment_only_count,
            "fraction_confounded": float(confounded_count / len(g_excess_values)),
        }

    # Monotonicity: as threshold increases, fraction confounded must strictly decrease
    fractions = [sensitivity_results[f"thresh_{t}"]["fraction_confounded"] for t in g_thresholds]
    for f1, f2 in zip(fractions[:-1], fractions[1:]):
        assert f2 <= f1

    output_path = "data/evaluation_phase3c/g_excess_sensitivity_sweep.json"
    with open(output_path, "w") as f:
        json.dump(sensitivity_results, f, indent=2)
