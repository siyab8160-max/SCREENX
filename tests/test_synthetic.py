"""SIH26170 Synthetic Generator Test Suite.

Verifies all frozen requirements from docs/PHASE_2_SYNTHETIC_DATA_SPEC.md:
- Deterministic reproducibility (same seed -> identical dataset, different seed -> different dataset)
- All 6 synthetic trajectory classes generated and verified
- Ground-truth independence from user screening limits
- Parameter-specific abnormality thresholds (0.50, 0.30, 0.10)
- Latent physical validity invariant (leakage >= 0, iddq >= 0, delay > 0)
- Negative observations preserved without flooring or clipping (LOG-020)
- Missing observations not confused with zero (missing vs zero vs negative)
- Equipment common-mode gain shift affects multiple components on rack
- Channel socket offset shifts
- Rework regimes (R0 neutral, R1 variance inflation, R2 risk shift)
- Canonical 45 uA demonstration fixture (PASS limit, peer abnormal, trend stable)
- Small-lot generation (N = 3, 5, 8, 30)
- Mixed adversarial scenarios (M01-M11)
- Strict information boundary: zero ground-truth leakage into observations
"""

import copy
import numpy as np
import pandas as pd
import pytest

from sih26170.schema import (
    CANONICAL_COLUMNS,
    GROUND_TRUTH_COLUMNS,
    ValueStatus,
    classify_measurement_value,
)
from sih26170.synthetic.config import LotSimConfig, SyntheticConfig, load_synthetic_config
from sih26170.synthetic.generator import SyntheticGenerator
from sih26170.synthetic.ground_truth import compute_relative_deviation, evaluate_ground_truth
from sih26170.synthetic.latent import LatentModel, LatentState
from sih26170.synthetic.measurement import EquipmentContext, MeasurementSimulator
from sih26170.synthetic.scenarios import ComponentPlan, ScenarioManager
from sih26170.synthetic.seeds import SeedHierarchy, derive_seed
from sih26170.synthetic.trajectories import (
    TrajectoryClass,
    TrajectoryProfile,
    create_trajectory_profile,
)
from sih26170.synthetic.validation import SyntheticValidator


@pytest.fixture
def base_config() -> SyntheticConfig:
    """Load default synthetic configuration."""
    return load_synthetic_config("configs/synthetic.yaml")


# 1. Reproducibility Tests
def test_reproducibility_same_seed(base_config):
    """Running generator twice with identical master_seed produces identical datasets."""
    gen1 = SyntheticGenerator(base_config)
    res1 = gen1.generate()

    gen2 = SyntheticGenerator(base_config)
    res2 = gen2.generate()

    # Verify identical observations
    pd.testing.assert_frame_equal(res1.observations_df, res2.observations_df)

    # Verify identical ground truth
    pd.testing.assert_frame_equal(res1.ground_truth_df, res2.ground_truth_df)


def test_reproducibility_different_seed(base_config):
    """Changing master seed produces different realizations."""
    # Modify seed using raw config dict
    cfg2_dict = copy.deepcopy(base_config.raw_config)
    cfg2_dict["master_seed"] = 99999999
    
    gen1 = SyntheticGenerator(base_config)
    res1 = gen1.generate()

    # Load custom config with altered seed
    from sih26170.synthetic.config import SyntheticConfig, ParameterSimConfig, LotSimConfig, EquipmentSimConfig, MissingnessSimConfig, CanonicalFixtureConfig
    cfg2 = copy.deepcopy(base_config)
    object.__setattr__(cfg2, "master_seed", 99999999)

    gen2 = SyntheticGenerator(cfg2)
    res2 = gen2.generate()

    assert not res1.observations_df.equals(res2.observations_df)


# 2. Trajectory Classes & Profiles
def test_all_trajectory_classes_present(base_config):
    """Verify all 6 canonical trajectory classes are generated in ground truth."""
    gen = SyntheticGenerator(base_config)
    res = gen.generate()
    classes_in_gt = set(res.ground_truth_df["trajectory_class"].unique())

    expected = {
        "stable",
        "high_but_stable",
        "lot_outlier",
        "linear_drift",
        "accelerating_drift",
        "abrupt_failure",
    }
    assert expected.issubset(classes_in_gt)


def test_trajectory_mathematics():
    """Verify mathematical behavior of g(t) for all trajectory classes."""
    checkpoints = [0, 24, 96, 168]
    rng = np.random.default_rng(42)

    # Stable: g(t) == 0
    stable_prof = create_trajectory_profile(
        TrajectoryClass.STABLE, "leakage_current", True, rng, checkpoints
    )
    for t in checkpoints:
        assert stable_prof.evaluate_g(t) == 0.0

    # Linear drift: g(t) = beta * (t / 168)
    lin_prof = create_trajectory_profile(
        TrajectoryClass.LINEAR_DRIFT, "leakage_current", True, rng, checkpoints
    )
    assert lin_prof.evaluate_g(0) == 0.0
    assert lin_prof.evaluate_g(168) > 0.4  # beta in [0.45, 0.85]
    assert lin_prof.evaluate_g(96) < lin_prof.evaluate_g(168)

    # Accelerating drift: superlinear
    acc_prof = create_trajectory_profile(
        TrajectoryClass.ACCELERATING_DRIFT, "leakage_current", True, rng, checkpoints
    )
    g_0 = acc_prof.evaluate_g(0)
    g_24 = acc_prof.evaluate_g(24)
    g_96 = acc_prof.evaluate_g(96)
    g_168 = acc_prof.evaluate_g(168)
    assert g_0 == 0.0
    assert g_24 < g_96 < g_168
    # Acceleration check: difference between later checkpoints exceeds earlier
    rate_early = (g_96 - g_24) / (96 - 24)
    rate_late = (g_168 - g_96) / (168 - 96)
    assert rate_late > rate_early

    # Abrupt failure: 0 before jump, delta at and after jump
    abrupt_prof = create_trajectory_profile(
        TrajectoryClass.ABRUPT_FAILURE, "leakage_current", True, rng, checkpoints
    )
    jh = abrupt_prof.jump_hour
    assert jh in [24, 96, 168]
    for t in checkpoints:
        if t < jh:
            assert abrupt_prof.evaluate_g(t) == 0.0
        else:
            assert abrupt_prof.evaluate_g(t) == abrupt_prof.delta_failure


# 3. Ground Truth Independence from Screening Limits
def test_ground_truth_independent_of_screening_limits(base_config):
    """Altering user screening limits does NOT alter latent state or ground truth abnormality."""
    gen1 = SyntheticGenerator(base_config)
    res1 = gen1.generate()

    # Create config with drastically altered screening limits
    altered_params = {}
    for p_name, p_cfg in base_config.parameters.items():
        altered_p = copy.deepcopy(p_cfg)
        object.__setattr__(altered_p, "user_limit_high", 1.0)  # Very tight limit
        altered_params[p_name] = altered_p

    cfg_altered = copy.deepcopy(base_config)
    object.__setattr__(cfg_altered, "parameters", altered_params)

    gen2 = SyntheticGenerator(cfg_altered)
    res2 = gen2.generate()

    # Ground truth must be 100% identical!
    pd.testing.assert_frame_equal(res1.ground_truth_df, res2.ground_truth_df)


# 4. Parameter-Specific Abnormality Thresholds
def test_parameter_specific_abnormality_thresholds(base_config):
    """Verify thresholds: 0.50 (leakage), 0.30 (iddq), 0.10 (delay)."""
    leakage_cfg = base_config.get_parameter("leakage_current")
    iddq_cfg = base_config.get_parameter("iddq")
    delay_cfg = base_config.get_parameter("propagation_delay")

    assert leakage_cfg.theta_abnormal == 0.50
    assert iddq_cfg.theta_abnormal == 0.30
    assert delay_cfg.theta_abnormal == 0.10


# 5. Latent Physical Non-Negativity Invariant
def test_latent_state_never_physically_negative(base_config):
    """Verify that x*(t) is strictly >= 0 for leakage/iddq, and > 0 for delay."""
    gen = SyntheticGenerator(base_config)
    res = gen.generate()
    gt = res.ground_truth_df

    # Leakage
    leakage_gt = gt[gt["parameter_name"] == "leakage_current"]
    assert (leakage_gt["latent_value"] >= 0.0).all()

    # Iddq
    iddq_gt = gt[gt["parameter_name"] == "iddq"]
    assert (iddq_gt["latent_value"] >= 0.0).all()

    # Propagation delay strictly > 0
    delay_gt = gt[gt["parameter_name"] == "propagation_delay"]
    assert (delay_gt["latent_value"] > 0.0).all()


# 6. Raw Negative Observations Preserved (LOG-020)
def test_negative_observations_preserved_unfloored(base_config):
    """Verify negative sensor readings exist, are unfloored, and classified as NEGATIVE."""
    gen = SyntheticGenerator(base_config)
    res = gen.generate()
    obs = res.observations_df

    neg_obs = obs[obs["value"] < 0.0]
    assert len(neg_obs) > 0, "Expected at least one negative observation artifact in benchmark"

    for _, row in neg_obs.iterrows():
        val = row["value"]
        assert val < 0.0
        # Classified as NEGATIVE
        assert classify_measurement_value(val) == ValueStatus.NEGATIVE


# 7. Missingness Semantics: Rows Absent vs Zero
def test_missing_observations_not_confused_with_zero(base_config):
    """Missing observations are absent rows, never represented as 0.0."""
    gen = SyntheticGenerator(base_config)
    res = gen.generate()
    obs = res.observations_df
    gt = res.ground_truth_df

    # Total ground truth records represents total expected checkpoint coverage
    assert len(gt) > len(obs), "Missing observations should cause obs row count < gt row count"
    
    # Confirm no NaN in value column of observations
    assert not obs["value"].isna().any()

    # ValueStatus for valid numbers is not MISSING
    for val in obs["value"].sample(min(100, len(obs)), random_state=42):
        assert classify_measurement_value(val) != ValueStatus.MISSING


# 8. Equipment Common-Mode Gain Shift
def test_equipment_common_mode_gain_shift(base_config):
    """Verify common-mode gain shift affects all components on INST_01 in Lot L13."""
    gen = SyntheticGenerator(base_config)
    res = gen.generate()
    obs = res.observations_df
    gt = res.ground_truth_df

    # Lot L13 on INST_01
    l13_inst1_obs = obs[(obs["lot_id"] == "L13") & (obs["instrument_id"] == "INST_01")]
    assert len(l13_inst1_obs) > 0

    # For stable components on INST_01, observed readings are systematically elevated by ~15%
    stable_gt = gt[(gt["lot_id"] == "L13") & (gt["trajectory_class"] == "stable")]
    stable_ids = set(stable_gt["component_id"].unique())

    stable_inst1_obs = l13_inst1_obs[l13_inst1_obs["component_id"].isin(stable_ids)]
    ratios = []
    for _, r in stable_inst1_obs.iterrows():
        cid = r["component_id"]
        param = r["parameter_name"]
        h = r["elapsed_hours"]
        gt_match = gt[(gt["component_id"] == cid) & (gt["parameter_name"] == param) & (gt["elapsed_hours"] == h)]
        if not gt_match.empty:
            latent_v = gt_match.iloc[0]["latent_value"]
            obs_v = r["value"]
            if latent_v > 0.1:
                ratios.append(obs_v / latent_v)

    # Median ratio should be close to 1 + common_mode_gain_shift = 1.15 within aleatory noise
    med_ratio = np.median(ratios)
    assert 1.10 <= med_ratio <= 1.20, f"Expected median ratio ~1.15, got {med_ratio:.3f}"


# 9. Rework Regimes
def test_rework_regimes(base_config):
    """Verify R0 (neutral), R1 (variance inflation), R2 (risk shift)."""
    scenario_mgr = ScenarioManager(base_config)
    rng = np.random.default_rng(123)

    # R0: Rework exists on stable parts
    r0_cfg = LotSimConfig(lot_id="TEST_R0", size=30, partition="train", scenario="nominal", rework_regime="R0")
    r0_plans = scenario_mgr.plan_lot(r0_cfg, rng)
    r0_reworked = [p for p in r0_plans if p.rework_count > 0]
    assert len(r0_reworked) > 0
    # In R0, variance multiplier is 1.0
    for p in r0_reworked:
        assert p.variance_multiplier == 1.0

    # R1: Rework inflates variance multiplier to 1.5
    r1_cfg = LotSimConfig(lot_id="TEST_R1", size=30, partition="train", scenario="nominal", rework_regime="R1")
    r1_plans = scenario_mgr.plan_lot(r1_cfg, rng)
    r1_reworked = [p for p in r1_plans if p.rework_count > 0]
    for p in r1_reworked:
        assert p.variance_multiplier == 1.5

    # R2: Trajectory class sampling shifts probability of drift
    r2_classes = [scenario_mgr.sample_trajectory_class(rework_count=1, rework_regime="R2", rng=rng) for _ in range(200)]
    drift_count = sum(1 for c in r2_classes if c == TrajectoryClass.LINEAR_DRIFT)
    # Expected drift rate ~15% (30 out of 200, tolerate 15-50)
    assert 15 <= drift_count <= 55


# 10. Canonical 45 µA Case
def test_canonical_45ua_fixture(base_config):
    """Verify CANONICAL_C45 properties: limit PASS, peer abnormal, trend stable."""
    gen = SyntheticGenerator(base_config)
    res = gen.generate()
    obs = res.observations_df
    gt = res.ground_truth_df

    c45_obs = obs[(obs["component_id"] == "CANONICAL_C45") & (obs["parameter_name"] == "leakage_current")]
    c45_gt = gt[(gt["component_id"] == "CANONICAL_C45") & (gt["parameter_name"] == "leakage_current")]

    assert not c45_obs.empty
    assert not c45_gt.empty

    # 1. Latent initial value is 45.0 uA
    assert np.isclose(c45_gt.iloc[0]["latent_value"], 45.0)

    # 2. Observed values stay strictly below screening limit 50.0 uA (PASS)
    assert (c45_obs["value"] < 50.0).all()

    # 3. Trajectory class is high_but_stable
    assert (c45_gt["trajectory_class"] == "high_but_stable").all()

    # 4. Ground truth abnormality begins at hour 0 (peer outlier)
    assert (c45_gt["first_abnormal_hour"] == 0).all()
    assert (c45_gt["abnormal_by_24h"]).all()

    # 5. Trend is flat (relative deviation r(t) == 0)
    assert np.allclose(c45_gt["relative_latent_deviation_r"], 0.0)


# 11. Small-Lot Support
def test_small_lot_scenarios(base_config):
    """Verify generator supports N in {3, 5, 8, 30}."""
    for n in [3, 5, 8, 30]:
        small_cfg = copy.deepcopy(base_config)
        small_lot = LotSimConfig(lot_id=f"SMALL_N{n}", size=n, partition="test", scenario="small_lot", rework_regime="R0")
        object.__setattr__(small_cfg, "lots", [small_lot])

        gen = SyntheticGenerator(small_cfg)
        res = gen.generate()

        assert res.sanity_report.component_count == n
        assert res.sanity_report.lot_count == 1


# 12. Strict Information Boundary (Zero Data Leakage)
def test_strict_ground_truth_isolation(base_config):
    """Verify observation DataFrame has ZERO ground truth columns."""
    gen = SyntheticGenerator(base_config)
    res = gen.generate()
    obs = res.observations_df

    for gt_col in GROUND_TRUTH_COLUMNS:
        assert gt_col not in obs.columns, f"Data leakage: {gt_col} found in observations!"

    assert set(obs.columns) == set(CANONICAL_COLUMNS)


# 13. Channel Socket Shift
def test_channel_socket_shift(base_config):
    """Verify socket channel offset affects only the specified socket."""
    scenario_mgr = ScenarioManager(base_config)

    # Socket CH_04 has configured shifts
    ctx_ch4 = scenario_mgr.resolve_equipment_context(
        instrument_id="INST_01", channel_id="CH_04", param_name="leakage_current", lot_scenario="nominal"
    )
    assert ctx_ch4.channel_offset == 0.10

    # Socket CH_02 has no shift
    ctx_ch2 = scenario_mgr.resolve_equipment_context(
        instrument_id="INST_01", channel_id="CH_02", param_name="leakage_current", lot_scenario="nominal"
    )
    assert ctx_ch2.channel_offset == 0.0


# 14. Mixed Adversarial Scenarios (M01-M11)
def test_mixed_adversarial_scenarios(base_config):
    """Verify generation of mixed interaction scenarios (M01-M11)."""
    scenario_mgr = ScenarioManager(base_config)
    rng = np.random.default_rng(999)

    # Test adversarial mix lot planning
    adv_lot_cfg = LotSimConfig(lot_id="TEST_ADV", size=30, partition="test", scenario="adversarial_mix", rework_regime="R1")
    plans = scenario_mgr.plan_lot(adv_lot_cfg, rng)

    # M01: high_but_stable + noise
    p_m01 = plans[0]
    assert p_m01.scenario_tag == "M01_high_stable_noise"
    assert p_m01.noise_scale_multiplier == 2.0
    assert p_m01.trajectory_profiles["leakage_current"].trajectory_class == TrajectoryClass.HIGH_BUT_STABLE

    # M02: high_but_stable + missing 96h
    p_m02 = plans[1]
    assert p_m02.scenario_tag == "M02_high_stable_missing_96h"
    assert 96 in p_m02.missing_checkpoints

    # M03: linear drift + noise
    p_m03 = plans[2]
    assert p_m03.scenario_tag == "M03_linear_drift_noise"
    assert p_m03.noise_scale_multiplier == 2.0
    assert p_m03.trajectory_profiles["leakage_current"].trajectory_class == TrajectoryClass.LINEAR_DRIFT

    # M05: accelerating drift + missing 96h
    p_m05 = plans[3]
    assert p_m05.scenario_tag == "M05_accel_drift_missing_96h"
    assert 96 in p_m05.missing_checkpoints

    # M08: reworked + stable
    p_m08 = plans[4]
    assert p_m08.scenario_tag == "M08_reworked_stable"
    assert p_m08.rework_count == 2
    assert p_m08.trajectory_profiles["leakage_current"].trajectory_class == TrajectoryClass.STABLE

    # M09: reworked + genuine drift
    p_m09 = plans[5]
    assert p_m09.scenario_tag == "M09_reworked_genuine_drift"
    assert p_m09.rework_count == 2
    assert p_m09.trajectory_profiles["leakage_current"].trajectory_class == TrajectoryClass.ACCELERATING_DRIFT

    # M10: instrument shift lot (L13) has INST_01 shift and 1 real defect
    l13_cfg = LotSimConfig(lot_id="L13", size=30, partition="test", scenario="instrument_common_mode_shift", rework_regime="R0")
    l13_plans = scenario_mgr.plan_lot(l13_cfg, rng)
    m10_defects = [p for p in l13_plans if "defect" in p.scenario_tag]
    assert len(m10_defects) == 1

    # M11: lot masking lot (L14) has 4 defects
    l14_cfg = LotSimConfig(lot_id="L14", size=30, partition="test", scenario="multi_defect_masking", rework_regime="R2")
    l14_plans = scenario_mgr.plan_lot(l14_cfg, rng)
    m11_defects = [p for p in l14_plans if p.scenario_tag == "M11_multi_defect_masking"]
    assert len(m11_defects) == 4


# 15. Validator Integrity
def test_validator_catches_tampering(base_config):
    """Verify SyntheticValidator catches ground truth leakage or corrupted data."""
    gen = SyntheticGenerator(base_config)
    res = gen.generate()
    validator = SyntheticValidator(base_config)

    # Leak a column
    tampered_obs = res.observations_df.copy()
    tampered_obs["trajectory_class"] = "stable"
    report = validator.validate(tampered_obs, res.ground_truth_df)
    assert not report.is_valid
    assert any("DATA LEAKAGE" in err for err in report.errors)
