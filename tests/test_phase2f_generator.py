"""Tests for SIH26170 Phase 2F Physics-Informed Synthetic Generator.

Validates:
- Epistemic layer ontology and parameter-selective trajectory vectors
- Critical anti-regression check (cross-parameter coupling << 99.75%)
- Strict separation between observation telemetry and ground truth
- Static limit breaches with stationary trajectories
- Subtle failure SNR calibration within benchmark difficulty interval [1.5, 2.5]
- Small-lot sensitivity sizes (N = 3, 5, 8, 12, 20, 50)
- Common-mode chamber drift and ATE channel bias
- Non-imputed missingness
- Cryptographic reproducibility and hash stability
"""

import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from sih26170.schema import CANONICAL_COLUMNS, GROUND_TRUTH_COLUMNS
from sih26170.synthetic.phase2f.config import (
    Phase2FConfig,
    Phase2FLotConfig,
    get_default_phase2f_config,
)
from sih26170.synthetic.phase2f.generator import Phase2FGenerator, derive_seed_hmac
from sih26170.synthetic.phase2f.scenarios import ParameterScenario


@pytest.fixture(scope="module")
def default_config() -> Phase2FConfig:
    return get_default_phase2f_config()


@pytest.fixture(scope="module")
def generated_run(default_config: Phase2FConfig):
    gen = Phase2FGenerator(default_config)
    return gen.generate()


def test_epistemic_configuration(default_config: Phase2FConfig):
    """Verify epistemic ontology layers and device anchors."""
    assert default_config.component_anchor == "IRHNJ57130 / JANSR2N7481U3"
    assert default_config.governing_specification == "MIL-PRF-19500/703"
    assert "SMD-0.5" in default_config.package_type

    params = default_config.parameters
    assert set(params.keys()) == {"IDSS", "VGS(th)", "RDS(on)", "IGSS"}

    # Epistemic classification verification
    assert "Layer A" in params["RDS(on)"].epistemic_layer
    assert "Layer B" in params["IDSS"].epistemic_layer
    assert "Layer B" in params["VGS(th)"].epistemic_layer
    assert "Layer B" in params["IGSS"].epistemic_layer


def test_hmac_seed_derivation():
    """Verify HMAC-SHA256 deterministic hierarchical seed derivation."""
    s1 = derive_seed_hmac(26170, "lot", "LOT_N01")
    s2 = derive_seed_hmac(26170, "lot", "LOT_N01")
    s3 = derive_seed_hmac(26170, "lot", "LOT_N02")
    assert s1 == s2
    assert s1 != s3
    assert 0 <= s1 < 2**31 - 1


def test_ground_truth_isolation(generated_run):
    """Ensure observations dataframe contains NO ground truth or latent columns."""
    obs_df = generated_run.observations_df
    gt_df = generated_run.ground_truth_df

    forbidden = set(GROUND_TRUTH_COLUMNS).union({
        "is_temporally_degraded", "is_spec_compliant", "achieved_snr",
        "parameter_scenario", "correlation_origin", "is_abnormal",
    })

    leaked = set(obs_df.columns).intersection(forbidden)
    assert len(leaked) == 0, f"Ground truth columns leaked into observations: {leaked}"

    # Required canonical columns
    for col in ["component_id", "lot_id", "elapsed_hours", "parameter_name", "value", "unit", "instrument_id", "channel_id"]:
        assert col in obs_df.columns


def test_critical_anti_regression_coupling(generated_run):
    """CRITICAL ANTI-REGRESSION CHECK:

    Verify parameter trajectory coupling is substantially lower than
    the Phase 2C historical pathology (~99.75%).
    """
    report = generated_run.forensic_report
    assert report.is_valid is True

    # Across all components, homogeneous coupling must be < 65% (measured ~43.7%)
    assert report.homogeneous_coupling_fraction < 0.65, (
        f"Overall coupling is {report.homogeneous_coupling_fraction:.2%}, "
        "reverting toward Phase 2C 99.75% pathology."
    )

    # Among abnormal/degrading components, coupling must be < 10% (measured ~5.45%)
    assert report.homogeneous_abnormal_coupling_fraction < 0.10, (
        f"Abnormal component coupling is {report.homogeneous_abnormal_coupling_fraction:.2%}, "
        "must be < 10%."
    )


def test_static_limit_breach_separation(generated_run):
    """Verify static limit breaches are non-compliant, abnormal, but temporally stationary."""
    gt_df = generated_run.ground_truth_df
    static_rows = gt_df[gt_df["parameter_scenario"] == "static_limit_breach"]
    assert len(static_rows) > 0

    # Must be stationary over time
    assert (static_rows["is_temporally_degraded"] == False).all()

    # Must breach specifications
    assert (static_rows["is_spec_compliant"] == False).all()

    # Must be flagged as abnormal at t=0
    assert (static_rows["is_abnormal"] == True).all()
    assert (static_rows["first_abnormal_hour"] == 0).all()


def test_subtle_failure_snr_calibration(generated_run):
    """Verify subtle temporal anomalies achieve SNR strictly within [1.5, 2.5]."""
    report = generated_run.forensic_report
    snr_dist = report.subtle_snr_distribution

    assert "min" in snr_dist and "max" in snr_dist
    assert snr_dist["min"] >= 1.50
    assert snr_dist["max"] <= 2.50
    assert 1.80 <= snr_dist["mean"] <= 2.30


def test_small_lot_sensitivity_coverage(generated_run):
    """Verify planned sensitivity sizes N = 3, 5, 8, 12, 20, 50 are present."""
    report = generated_run.forensic_report
    small_counts = set(report.small_lot_counts.values())

    expected_sizes = {3, 5, 8, 12, 20, 50}
    assert expected_sizes.issubset(small_counts), (
        f"Missing sensitivity lot sizes. Expected {expected_sizes}, got {small_counts}"
    )


def test_common_mode_measurable_shift(generated_run):
    """Verify chamber common-mode temperature drift produces measurable shared shift."""
    obs_df = generated_run.observations_df
    e01 = obs_df[(obs_df["lot_id"] == "LOT_E01") & (obs_df["parameter_name"] == "IDSS")]
    piv = e01.pivot(index="component_id", columns="elapsed_hours", values="value")

    assert 96 in piv.columns and 24 in piv.columns
    diffs = piv[96] - piv[24]

    # Every component in the chamber must show positive IDSS shift at 96h (+5°C excursion)
    assert (diffs > 0).all()
    assert float(diffs.mean()) > 0.10


def test_non_imputed_missingness(generated_run):
    """Verify missing observations are omitted rather than imputed with NaNs or zeros."""
    obs_df = generated_run.observations_df
    assert not obs_df["value"].isna().any()

    # Total possible slots vs actual observations
    total_slots = 398 * 4 * 4  # 398 components * 4 params * 4 checkpoints = 6368
    actual_obs = len(obs_df)
    assert actual_obs < total_slots
    assert total_slots - actual_obs == 7  # Exactly 7 omitted observations


def test_deterministic_reproducibility(default_config: Phase2FConfig):
    """Verify running generation twice with the same configuration produces byte-identical output."""
    gen1 = Phase2FGenerator(default_config)
    res1 = gen1.generate()

    gen2 = Phase2FGenerator(default_config)
    res2 = gen2.generate()

    csv_obs1 = res1.observations_df.to_csv(index=False)
    csv_obs2 = res2.observations_df.to_csv(index=False)
    assert csv_obs1 == csv_obs2

    csv_gt1 = res1.ground_truth_df.to_csv(index=False)
    csv_gt2 = res2.ground_truth_df.to_csv(index=False)
    assert csv_gt1 == csv_gt2


def test_dataset_save_and_manifest(tmp_path, generated_run, default_config):
    """Verify saving dataset produces all development artifacts with matching hashes."""
    gen = Phase2FGenerator(default_config)
    paths = gen.save_dataset(generated_run, tmp_path)

    for key, path in paths.items():
        assert path.exists(), f"Missing artifact: {key} at {path}"

    manifest_data = json.loads(paths["manifest"].read_text())
    assert manifest_data["status"] == "DEVELOPMENT_ONLY_NOT_FROZEN"
    assert manifest_data["artifact_type"] == "PHASE_2F_DEVELOPMENT_SYNTHETIC_DATASET"

    # Verify sha256 in manifest matches actual file content
    obs_sha = hashlib.sha256(paths["observations"].read_bytes()).hexdigest()
    assert manifest_data["files"]["observations.csv"]["sha256"] == obs_sha


def test_igss_signed_measurement_model(generated_run):
    """BLOCKER 1: Verify IGSS preserves sign, zero, small magnitudes, and evaluates +/- 100 nA limits."""
    obs_df = generated_run.observations_df
    igss_vals = obs_df[obs_df["parameter_name"] == "IGSS"]["value"]

    # 1. Positive values present
    pos_vals = igss_vals[igss_vals > 0.1]
    assert len(pos_vals) > 0, "No positive IGSS observations found"

    # 2. Negative values present (sign preserved, no abs() truncation)
    neg_vals = igss_vals[igss_vals < -0.1]
    assert len(neg_vals) > 0, "No negative IGSS observations found; sign not preserved"

    # 3. Exact zero values present
    zero_vals = igss_vals[igss_vals == 0.0]
    assert len(zero_vals) > 0, "No exact zero IGSS observations found"

    # 4. Near-zero values present (sub-100 pA)
    near_zero = igss_vals[(igss_vals.abs() > 0.0) & (igss_vals.abs() < 0.1)]
    assert len(near_zero) > 0, "No near-zero IGSS observations found"

    # 5. Absolute limit evaluation at +/- 100 nA
    gt_df = generated_run.ground_truth_df
    igss_gt = gt_df[gt_df["parameter_name"] == "IGSS"]

    pos_breach = igss_gt[igss_gt["component_id"] == "LOT_L01_C005"]
    assert (pos_breach["is_spec_compliant"] == False).all()

    neg_breach = igss_gt[igss_gt["component_id"] == "LOT_L01_C004"]
    assert (neg_breach["is_spec_compliant"] == False).all()


def test_real_as_of_leakage(generated_run):
    """BLOCKER 2: Real forensic as-of leakage audit across all checkpoints."""
    report = generated_run.forensic_report
    assert report.as_of_leakage_clean is True

    audit = report.as_of_leakage_audit
    assert audit.get("all_slices_immutable") is True

    # Verify each checkpoint slice
    checkpoints = [0, 24, 96, 168]
    for T in checkpoints:
        k = f"checkpoint_{T}h"
        assert k in audit
        assert audit[k]["future_records_count"] == 0
        assert audit[k]["ground_truth_columns_count"] == 0
        assert audit[k]["max_elapsed_hours"] <= T


def test_distinct_scenario_count_semantics(generated_run):
    """BLOCKER 3: Verify semantic distinction between component, parameter, and observation scenario counts."""
    report = generated_run.forensic_report

    # Component-level counts (sum must equal 398 components)
    comp_scens = report.component_scenario_counts
    assert sum(comp_scens.values()) == 398

    # All 10 required component scenarios must be instantiated
    required = {
        "stable", "high_but_stable", "static_limit_breach", "lot_outlier",
        "linear_drift", "accelerating_drift", "subtle_abrupt_change",
        "equipment_common_mode", "mixed_compound", "insufficient_data"
    }
    assert required.issubset(set(comp_scens.keys()))
    assert comp_scens["mixed_compound"] >= 2  # Mixed/compound explicitly instantiated

    # Parameter-level counts (sum must equal 398 * 4 = 1,592)
    param_scens = report.parameter_scenario_counts
    assert sum(param_scens.values()) == 1592

    # Observation-level counts (sum must equal 6,368 ground truth records)
    obs_scens = report.observation_scenario_counts
    assert sum(obs_scens.values()) == 6368


def test_coupling_audit_conditional_probabilities(generated_run):
    """COUPLING AUDIT: Verify conditional drift probabilities on degrading components."""
    report = generated_run.forensic_report

    # Critical anti-regression contracts
    assert report.p_all_same_degrading == 0.0, "Degrading components must not have 4 identical parameters"
    assert report.p_four_drift_degrading == 0.0, "Simultaneous 4-parameter drift must be 0%"
    assert report.p_single_drift_degrading > 0.85, "Primary single-mechanism drift must be > 85%"
    assert report.p_two_drift_degrading > 0.0, "Compound two-parameter drift must be present"


def test_physical_positivity_classification(generated_run):
    """PHYSICAL POSITIVITY AUDIT: Validate parameter domain physical constraints."""
    obs_df = generated_run.observations_df

    # IDSS is strictly positive (reverse junction leakage)
    idss_vals = obs_df[obs_df["parameter_name"] == "IDSS"]["value"]
    assert (idss_vals > 0).all(), "IDSS must be strictly positive"

    # RDS(on) is strictly positive (channel ohmic resistance)
    rdson_vals = obs_df[obs_df["parameter_name"] == "RDS(on)"]["value"]
    assert (rdson_vals > 0).all(), "RDS(on) must be strictly positive"

    # IGSS is signed (contains both positive and negative values)
    igss_vals = obs_df[obs_df["parameter_name"] == "IGSS"]["value"]
    assert (igss_vals > 0).any() and (igss_vals < 0).any(), "IGSS must be signed"

    # VGS(th) is bounded enhancement mode threshold in [0.5, 6.0] V
    vgsth_vals = obs_df[obs_df["parameter_name"] == "VGS(th)"]["value"]
    assert (vgsth_vals >= 0.5).all() and (vgsth_vals <= 6.0).all()

