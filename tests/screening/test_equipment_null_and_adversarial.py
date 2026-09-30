"""Adversarial Null-Model and Failure Scenario Tests for Module A Screening.

Compliant with Phase 3C Pre-Implementation Amendments:
- Tests actual false-trigger behavior under the null via repeated seeded simulations
- Verifies sample-size suppression (N_k < 4)
- Tests genuinely biased channels across effect sizes
- Tests chamber shifts, high-but-stable baselines, component wearout, and confounded degradation
- Verifies transient/abrupt jump preservation
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sih26170.screening.equipment import (
    evaluate_fixture_channel_bias,
    evaluate_chamber_excursion,
    evaluate_equipment_environment,
    CHANNEL_BIAS_Z_THRESHOLD,
)
from sih26170.screening.pipeline import screen_component
from sih26170.screening.schema import (
    DispositionQualifier,
    EquipmentStatus,
    ScreeningState,
    TemporalDriftStatus,
)
from tests.screening.test_scenarios import make_nominal_lot


# ============================================================================
# Adversarial Test 1: No Channel Bias + Gaussian Noise + N_k = 2 (Suppression)
# ============================================================================
def test_adv_01_no_bias_small_sample_suppressed():
    """Verify that when N_k = 2, channel bias is suppressed to avoid false alarms."""
    df = make_nominal_lot(n_components=16)
    # Assign CH_01 to 2 components, CH_02 to 2 components, etc.
    for i in range(8):
        cids = [f"LOT_TEST_C{2*i+1:03d}", f"LOT_TEST_C{2*i+2:03d}"]
        df.loc[df["component_id"].isin(cids), "channel_id"] = f"CH_{i+1:02d}"

    curr_df = df[df["elapsed_hours"] == 0]
    ev = evaluate_fixture_channel_bias("VGS(th)", curr_df, channel_id="CH_01")
    assert ev.suppressed is True
    assert ev.suspected is False
    assert ev.reason_code == "CHANNEL_BIAS_SUPPRESSED_SMALL_SAMPLE"
    assert ev.n_channel == 2


# ============================================================================
# Adversarial Test 2: No Channel Bias + Gaussian Noise + N_k = 4 (Null Monte Carlo)
# ============================================================================
def test_adv_02_no_bias_nk4_false_positive_control():
    """Measure empirical false trigger rate across repeated seeded simulations for N_k = 4."""
    rng = np.random.default_rng(26170)
    num_sims = 1000
    n_k = 4
    n_other = 12  # Total lot = 16

    false_triggers = 0
    z_scores = []

    for _ in range(num_sims):
        vals = rng.normal(3.0, 0.1, size=16)  # Nominal VGS(th) ~ 3.0V, sigma=0.1V
        df = pd.DataFrame({
            "parameter_name": ["VGS(th)"] * 16,
            "value": vals,
            "channel_id": ["CH_01"] * n_k + ["CH_02"] * n_other,
        })
        ev = evaluate_fixture_channel_bias("VGS(th)", df, channel_id="CH_01")
        assert not ev.suppressed
        z_scores.append(ev.z_score)
        if ev.suspected:
            false_triggers += 1

    fpr = false_triggers / num_sims
    max_abs_z = max(abs(z) for z in z_scores)
    # Under Bonferroni |Z| >= 3.42, FPR should be strictly <= 1.0% in 1000 runs
    assert fpr <= 0.01, f"FPR too high under null: {fpr:.4f}"
    assert max_abs_z < 5.0, f"Unreasonable extreme Z: {max_abs_z:.2f}"


# ============================================================================
# Adversarial Test 3: No Channel Bias + Gaussian Noise + N_k = 20 (Null Calibration)
# ============================================================================
def test_adv_03_no_bias_nk20_null_calibration():
    """Measure empirical null distribution behavior for larger N_k = 20 across multiple channels."""
    rng = np.random.default_rng(26170)
    num_sims = 500
    n_k = 20
    n_other = 60  # Total lot = 80 across 4 channels

    false_triggers = 0
    for _ in range(num_sims):
        vals = rng.normal(3.0, 0.1, size=80)
        channels = ["CH_01"] * 20 + ["CH_02"] * 20 + ["CH_03"] * 20 + ["CH_04"] * 20
        df = pd.DataFrame({
            "parameter_name": ["VGS(th)"] * 80,
            "value": vals,
            "channel_id": channels,
        })
        ev = evaluate_fixture_channel_bias("VGS(th)", df, channel_id="CH_01")
        if ev.suspected:
            false_triggers += 1

    fpr = false_triggers / num_sims
    assert fpr <= 0.01, f"FPR for N_k=20 exceeded tolerance: {fpr:.4f}"


# ============================================================================
# Adversarial Test 4: One Genuinely Biased Channel (N_k >= 4)
# ============================================================================
def test_adv_04_single_genuinely_biased_channel():
    """Verify that a genuine channel offset (e.g. +4 sigma) is detected with high power without false alarms."""
    df = make_nominal_lot(n_components=16)
    # 4 components on CH_01, 12 on other channels
    cids_ch01 = [f"LOT_TEST_C{i:03d}" for i in range(1, 5)]
    df.loc[df["component_id"].isin(cids_ch01), "channel_id"] = "CH_01"
    for i in range(5, 17):
        df.loc[df["component_id"] == f"LOT_TEST_C{i:03d}", "channel_id"] = f"CH_{(i-5)//4 + 2:02d}"

    # Inject +0.5V offset on VGS(th) for CH_01 (sigma ~ 0.1V, so effect size ~ 5 sigma)
    df.loc[(df["channel_id"] == "CH_01") & (df["parameter_name"] == "VGS(th)"), "value"] += 0.50

    curr_df = df[df["elapsed_hours"] == 0]
    ev_ch01 = evaluate_fixture_channel_bias("VGS(th)", curr_df, channel_id="CH_01")
    assert ev_ch01.suspected is True
    assert ev_ch01.z_score >= 3.42
    assert ev_ch01.reason_code == "ATE_CHANNEL_FIXTURE_BIAS"

    # Unbiased channel CH_02 must NOT be suspected
    ev_ch02 = evaluate_fixture_channel_bias("VGS(th)", curr_df, channel_id="CH_02")
    assert ev_ch02.suspected is False
    assert abs(ev_ch02.z_score) < 3.42


# ============================================================================
# Adversarial Test 5: Multiple Genuinely Biased Channels
# ============================================================================
def test_adv_05_multiple_genuinely_biased_channels():
    """Verify that multiple independent biased channels are detected without cross-masking in a multi-channel fixture."""
    df = make_nominal_lot(n_components=32)
    # 8 channels with 4 components each
    for i in range(8):
        cids = [f"LOT_TEST_C{4*i+j:03d}" for j in range(1, 5)]
        df.loc[df["component_id"].isin(cids), "channel_id"] = f"CH_{i+1:02d}"

    # CH_01 has +0.8V bias, CH_02 has -0.8V bias on VGS(th)
    df.loc[(df["channel_id"] == "CH_01") & (df["parameter_name"] == "VGS(th)"), "value"] += 0.80
    df.loc[(df["channel_id"] == "CH_02") & (df["parameter_name"] == "VGS(th)"), "value"] -= 0.80

    curr_df = df[df["elapsed_hours"] == 0]
    ev_ch01 = evaluate_fixture_channel_bias("VGS(th)", curr_df, channel_id="CH_01")
    ev_ch02 = evaluate_fixture_channel_bias("VGS(th)", curr_df, channel_id="CH_02")
    ev_ch03 = evaluate_fixture_channel_bias("VGS(th)", curr_df, channel_id="CH_03")

    assert ev_ch01.suspected is True
    assert ev_ch01.z_score > 3.42
    assert ev_ch02.suspected is True
    assert ev_ch02.z_score < -3.42
    assert ev_ch03.suspected is False


# ============================================================================
# Adversarial Test 6: Chamber Shift Without Component Degradation
# ============================================================================
def test_adv_06_chamber_shift_without_component_degradation():
    """Verify that pure chamber excursion dispositions components as EQUIPMENT_SUSPECTED / EQUIPMENT_ONLY."""
    df = make_nominal_lot(n_components=12)
    # All 12 components experience synchronous +5 mOhm excursion on RDS(on) at 96h
    df.loc[(df["elapsed_hours"] == 96) & (df["parameter_name"] == "RDS(on)"), "value"] += 5.0

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=96)
    assert res.final_state == ScreeningState.EQUIPMENT_SUSPECTED
    assert res.disposition_qualifier == DispositionQualifier.EQUIPMENT_ONLY
    p_res = res.parameter_results["RDS(on)"]
    assert p_res.equipment_evidence.suspected is True
    assert abs(p_res.temporal_evidence.g_excess) < 2.5


# ============================================================================
# Adversarial Test 7: Component Degradation Without Equipment Shift
# ============================================================================
def test_adv_07_component_degradation_without_equipment_shift():
    """Verify that autonomous wearout on a single part is classified as COMPONENT_DEGRADATION."""
    df = make_nominal_lot(n_components=12)
    # Only component C001 experiences progressive wearout on RDS(on) from 45 -> 58 mOhm
    drift_map = {0: 45.0, 24: 48.0, 96: 53.0, 168: 58.0}
    for t, val in drift_map.items():
        df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "RDS(on)") & (df["elapsed_hours"] == t), "value"] = val

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=168)
    assert res.final_state in (ScreeningState.ALERT, ScreeningState.FAIL)
    assert res.disposition_qualifier == DispositionQualifier.COMPONENT_DEGRADATION
    p_res = res.parameter_results["RDS(on)"]
    assert p_res.equipment_evidence.suspected is False
    assert abs(p_res.temporal_evidence.normalized_drift) >= 2.5


# ============================================================================
# Adversarial Test 8: Equipment Shift + Component Excess Degradation
# ============================================================================
def test_adv_08_equipment_shift_with_excess_component_degradation():
    """Verify that a component degrading in excess of chamber shift receives CONFOUNDED_BY_EQUIPMENT."""
    df = make_nominal_lot(n_components=12)
    # Chamber shift: all parts shift by +5 mOhm at 96h
    df.loc[(df["elapsed_hours"] == 96) & (df["parameter_name"] == "RDS(on)"), "value"] += 5.0

    # Component C001 also has active wearout: extra +12 mOhm on top of chamber shift (total +17 mOhm)
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["elapsed_hours"] == 96) & (df["parameter_name"] == "RDS(on)"), "value"] += 12.0

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=96)
    assert res.final_state in (ScreeningState.ALERT, ScreeningState.FAIL)
    assert res.disposition_qualifier == DispositionQualifier.COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT
    p_res = res.parameter_results["RDS(on)"]
    assert p_res.equipment_evidence.suspected is True
    assert p_res.temporal_evidence.g_excess is not None
    assert abs(p_res.temporal_evidence.g_excess) >= 2.5


# ============================================================================
# Adversarial Test 9: Equipment Shift + High-But-Stable Baseline
# ============================================================================
def test_adv_09_equipment_shift_with_high_but_stable_baseline():
    """Verify that a high baseline stationary part in a shifted chamber is not called wearout."""
    df = make_nominal_lot(n_components=12)
    # Component C001 has high baseline (58 mOhm vs 45 mOhm lot median), but stationary
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "RDS(on)"), "value"] = 58.0

    # Chamber excursion affects all components by +3 mOhm at 96h
    df.loc[(df["elapsed_hours"] == 96) & (df["parameter_name"] == "RDS(on)"), "value"] += 3.0

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=96)
    # The component is a peer outlier, not physical wearout
    assert res.final_state in (ScreeningState.ALERT, ScreeningState.EQUIPMENT_SUSPECTED)
    assert res.disposition_qualifier in (DispositionQualifier.PEER_OUTLIER_STATIONARY, DispositionQualifier.EQUIPMENT_ONLY)
    # Must NEVER be misclassified as unconfounded component degradation
    assert res.disposition_qualifier != DispositionQualifier.COMPONENT_DEGRADATION


# ============================================================================
# Adversarial Test 10: Equipment Shift + Abrupt Component-Specific Step
# ============================================================================
def test_adv_10_equipment_shift_with_abrupt_step():
    """Verify abrupt step detection on individual component is preserved under chamber shift."""
    df = make_nominal_lot(n_components=12)
    # Synchronous chamber excursion: +2 mOhm on all components at 24h
    df.loc[(df["elapsed_hours"] == 24) & (df["parameter_name"] == "RDS(on)"), "value"] += 2.0

    # Component C001 has an abrupt jump of +15 mOhm at 24h
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["elapsed_hours"] == 24) & (df["parameter_name"] == "RDS(on)"), "value"] += 15.0

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=24)
    p_res = res.parameter_results["RDS(on)"]
    assert p_res.step_evidence.status.value == "ABRUPT_JUMP_ALERT"
    # Excess motion is established
    assert res.final_state in (ScreeningState.ALERT, ScreeningState.FAIL)


# ============================================================================
# Adversarial Test 11: Transient Excursion & Recovery (Evidence Preserved)
# ============================================================================
def test_adv_11_transient_excursion_recovery_preserved():
    """Verify that transient behavior (0h normal, 24h excursion, 96h recovery, 168h normal)
    does not become 'no degradation' merely because endpoint g_excess is small.
    """
    times = [0, 24, 96, 168]
    rows = []
    for cid in [f"LOT_TEST_C{i:03d}" for i in range(1, 13)]:
        for t in times:
            v = 45.0
            if cid == "LOT_TEST_C001" and t == 24:
                v = 65.0  # +20 mOhm transient excursion at 24h, recovered to 45.0 by 96h
            rows.append({
                "lot_id": "LOT_TEST",
                "component_id": cid,
                "elapsed_hours": t,
                "parameter_name": "RDS(on)",
                "value": v,
                "channel_id": "CH_01",
            })
            for p, nom in [("IDSS", 0.1), ("VGS(th)", 3.0), ("IGSS", 1.0)]:
                rows.append({
                    "lot_id": "LOT_TEST",
                    "component_id": cid,
                    "elapsed_hours": t,
                    "parameter_name": p,
                    "value": nom,
                    "channel_id": "CH_01",
                })
    df = pd.DataFrame(rows)

    # Evaluate at 168h where endpoint value has recovered to nominal
    res = screen_component(df, "LOT_TEST_C001", as_of_hours=168)
    p_res = res.parameter_results["RDS(on)"]

    # Endpoint g_excess is small because value returned to normal
    assert abs(p_res.temporal_evidence.g_excess) < 1.0

    # BUT abrupt step / transient excursion evidence is preserved
    assert p_res.step_evidence.status.value == "ABRUPT_JUMP_ALERT"
    assert p_res.step_evidence.step_ratio >= 4.0
    assert p_res.step_evidence.previous_checkpoint == 0
    assert p_res.step_evidence.current_checkpoint == 24

    # Must NOT become PASS / NOMINAL_STABLE
    assert res.final_state != ScreeningState.PASS
    assert res.disposition_qualifier != DispositionQualifier.NOMINAL_STABLE
    assert res.final_state == ScreeningState.FAIL
    assert res.disposition_qualifier == DispositionQualifier.COMPONENT_DEGRADATION

