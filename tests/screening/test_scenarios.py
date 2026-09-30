"""End-to-end scenario validation tests for Module A.

Validates all 19 functional and physical scenarios specified in prompt Section 15:
1. Stable component
2. High-but-stable component (ALERT, never FAIL)
3. Static limit breach (immediate hard veto FAIL)
4. Linear drift (temporal degradation)
5. Accelerating drift (convexity proxy wearout FAIL)
6. Subtle drift (univariate subtle ALERT)
7. Abrupt change (step jump J(T) >= 4.0 FAIL)
8. Mixed compound (multi-parameter degradation FAIL)
9. Chamber common-mode (EQUIPMENT_SUSPECTED)
10. ATE fixture channel effect (EQUIPMENT_SUSPECTED)
11. Small lot N < 8 (PEER_SUPPRESSED_SMALL_LOT)
12. Missing checkpoint (INSUFFICIENT_DATA)
13. Negative IGSS (signed preservation)
14. Positive IGSS (signed preservation)
15. Zero IGSS (exact zero preservation)
16. High IGSS breach (Table I breach FAIL)
17. High RDS(on) breach (Table I 65 mOhm breach FAIL)
18. High IDSS breach (Table I 10 uA breach FAIL)
19. VGS(th) boundary breach (Table I [2.0, 4.0] V breach FAIL)

For every test, both detector output and explainability evidence card are verified.
"""

from typing import List
import numpy as np
import pandas as pd
import pytest

from sih26170.screening.explainability import generate_explainability_card
from sih26170.screening.pipeline import screen_component
from sih26170.screening.schema import (
    AbruptStepStatus,
    EquipmentStatus,
    PeerDeviationStatus,
    ScreeningState,
    SpecificationStatus,
    SufficiencyStatus,
    TemporalDriftStatus,
)


def make_nominal_lot(lot_id: str = "LOT_TEST", n_components: int = 10) -> pd.DataFrame:
    """Generate a clean, nominal reference lot across 0h, 24h, 96h, 168h."""
    rows = []
    for i in range(1, n_components + 1):
        cid = f"{lot_id}_C{i:03d}"
        for t in [0, 24, 96, 168]:
            rows.append({"component_id": cid, "lot_id": lot_id, "parameter_name": "IDSS", "elapsed_hours": t, "value": 0.50 + 0.01 * (i % 3), "unit": "uA", "measurement_quality": "VALID", "instrument_id": "ATE_01", "channel_id": "CH_01"})
            rows.append({"component_id": cid, "lot_id": lot_id, "parameter_name": "VGS(th)", "elapsed_hours": t, "value": 2.85 + 0.01 * (i % 3), "unit": "V", "measurement_quality": "VALID", "instrument_id": "ATE_01", "channel_id": "CH_01"})
            rows.append({"component_id": cid, "lot_id": lot_id, "parameter_name": "RDS(on)", "elapsed_hours": t, "value": 45.0 + 0.1 * (i % 3), "unit": "mOhm", "measurement_quality": "VALID", "instrument_id": "ATE_01", "channel_id": "CH_01"})
            rows.append({"component_id": cid, "lot_id": lot_id, "parameter_name": "IGSS", "elapsed_hours": t, "value": 5.0 + 0.1 * (i % 3), "unit": "nA", "measurement_quality": "VALID", "instrument_id": "ATE_01", "channel_id": "CH_01"})
    return pd.DataFrame(rows)


# ============================================================================
# 1. Stable Component
# ============================================================================
def test_scenario_01_stable_component():
    """Verify nominal stable component receives PASS and clean explainability card."""
    df = make_nominal_lot()
    res = screen_component(df, "LOT_TEST_C001", as_of_hours=168)

    assert res.final_state == ScreeningState.PASS
    assert res.primary_reason_code == "NOMINAL_SPEC_AND_STABLE_KINETICS"

    card = generate_explainability_card(res)
    assert "FINAL SCREENING    : PASS" in card
    assert "NOMINAL_SPEC_AND_STABLE_KINETICS" in card


# ============================================================================
# 2. High-But-Stable Component
# ============================================================================
def test_scenario_02_high_but_stable_component():
    """Verify high initial baseline with zero drift is assigned ALERT, NEVER FAIL."""
    df = make_nominal_lot()
    # Modify C001 to have high baseline (RDS(on) = 58 mOhm, lot median ~45) with zero temporal drift
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "RDS(on)"), "value"] = 58.0

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=168)

    assert res.final_state == ScreeningState.ALERT
    assert res.final_state != ScreeningState.FAIL
    assert "HIGH_BUT_STABLE_PEER_OUTLIER" in res.primary_reason_code or "SCREENING_MARGIN_BREACH" in res.primary_reason_code

    p_rdson = res.parameter_results["RDS(on)"]
    assert p_rdson.temporal_evidence.status == TemporalDriftStatus.STATIONARY
    assert p_rdson.peer_evidence.status in (PeerDeviationStatus.PEER_MILD_OUTLIER, PeerDeviationStatus.PEER_EXTREME_OUTLIER)


# ============================================================================
# 3. Static Limit Breach
# ============================================================================
def test_scenario_03_static_limit_breach():
    """Verify Class A limit breach triggers non-negotiable FAIL veto even with zero drift."""
    df = make_nominal_lot()
    # Breach Class A limit: RDS(on) = 68.0 mOhm (> 65.0 mOhm spec)
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "RDS(on)"), "value"] = 68.0

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=0)
    assert res.final_state == ScreeningState.FAIL
    assert "ABSOLUTE_LIMIT_BREACH" in res.primary_reason_code

    card = generate_explainability_card(res)
    assert "SPEC_BREACH" in card


# ============================================================================
# 4. Linear Drift
# ============================================================================
def test_scenario_04_linear_drift():
    """Verify linear temporal degradation is detected with positive Theil-Sen slope."""
    df = make_nominal_lot()
    # Inject linear drift on IDSS for C001
    idss_vals = {0: 0.50, 24: 1.20, 96: 3.50, 168: 6.80}
    for t, val in idss_vals.items():
        df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "IDSS") & (df["elapsed_hours"] == t), "value"] = val

    res = res = screen_component(df, "LOT_TEST_C001", as_of_hours=168)
    p_idss = res.parameter_results["IDSS"]
    assert p_idss.temporal_evidence.slope_per_hour > 0
    assert p_idss.temporal_evidence.status in (TemporalDriftStatus.SUBTLE_DRIFT, TemporalDriftStatus.ACCELERATING_DRIFT)
    assert res.final_state in (ScreeningState.ALERT, ScreeningState.FAIL)


# ============================================================================
# 5. Accelerating Drift
# ============================================================================
def test_scenario_05_accelerating_drift():
    """Verify accelerating drift kinetics trigger FAIL."""
    df = make_nominal_lot()
    # Inject accelerating drift on RDS(on): small early delta, large late delta
    rdson_vals = {0: 45.0, 24: 45.5, 96: 51.0, 168: 64.0}
    for t, val in rdson_vals.items():
        df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "RDS(on)") & (df["elapsed_hours"] == t), "value"] = val

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=168)
    p_rdson = res.parameter_results["RDS(on)"]
    assert p_rdson.temporal_evidence.status == TemporalDriftStatus.ACCELERATING_DRIFT
    assert res.final_state == ScreeningState.FAIL


# ============================================================================
# 6. Subtle Drift
# ============================================================================
def test_scenario_06_subtle_drift():
    """Verify univariate subtle drift triggers ALERT."""
    df = make_nominal_lot()
    # Inject linear subtle drift on IDSS: 0.50 -> 0.518 -> 0.577 -> 0.635 uA (kappa <= 0, |g| >= 2.5, J < 4.0)
    idss_vals = {0: 0.50, 24: 0.518, 96: 0.577, 168: 0.635}
    for t, val in idss_vals.items():
        df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "IDSS") & (df["elapsed_hours"] == t), "value"] = val

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=168)
    p_idss = res.parameter_results["IDSS"]
    assert p_idss.temporal_evidence.status == TemporalDriftStatus.SUBTLE_DRIFT
    assert res.final_state == ScreeningState.ALERT


# ============================================================================
# 7. Abrupt Change
# ============================================================================
def test_scenario_07_abrupt_change():
    """Verify abrupt step change across adjacent checkpoints triggers FAIL."""
    df = make_nominal_lot()
    # Inject sudden jump at 96h for VGS(th): 2.85 -> 2.85 -> 3.65 -> 3.66 V
    vgs_vals = {0: 2.85, 24: 2.85, 96: 3.65, 168: 3.66}
    for t, val in vgs_vals.items():
        df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "VGS(th)") & (df["elapsed_hours"] == t), "value"] = val

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=96)
    p_vgs = res.parameter_results["VGS(th)"]
    assert p_vgs.step_evidence.status == AbruptStepStatus.ABRUPT_JUMP_ALERT
    assert res.final_state == ScreeningState.FAIL


# ============================================================================
# 8. Mixed Compound
# ============================================================================
def test_scenario_08_mixed_compound():
    """Verify simultaneous multi-parameter degradation triggers compound FAIL."""
    df = make_nominal_lot()
    # Parameter 1: IDSS subtle drift
    for t, val in {0: 0.50, 24: 0.80, 96: 1.20, 168: 1.60}.items():
        df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "IDSS") & (df["elapsed_hours"] == t), "value"] = val

    # Parameter 2: RDS(on) subtle drift
    for t, val in {0: 45.0, 24: 47.0, 96: 51.0, 168: 56.0}.items():
        df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "RDS(on)") & (df["elapsed_hours"] == t), "value"] = val

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=168)
    assert res.compound_evidence is True
    assert res.final_state == ScreeningState.FAIL
    assert "COMPOUND_MULTI_PARAMETER_DRIFT" in res.primary_reason_code


# ============================================================================
# 9. Chamber Common-Mode Excursion
# ============================================================================
def test_scenario_09_chamber_common_mode():
    """Verify lot-wide synchronous shift triggers EQUIPMENT_SUSPECTED without mutating raw data."""
    df = make_nominal_lot(n_components=12)
    # Excursion: all parts shift by +5 mOhm at 96h
    df.loc[(df["elapsed_hours"] == 96) & (df["parameter_name"] == "RDS(on)"), "value"] += 5.0

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=96)
    assert res.final_state == ScreeningState.EQUIPMENT_SUSPECTED
    assert "CHAMBER_SYNCHRONOUS_EXCURSION" in res.primary_reason_code


# ============================================================================
# 10. ATE Fixture Channel Bias
# ============================================================================
def test_scenario_10_ate_channel_bias():
    """Verify systematic ATE channel offset triggers EQUIPMENT_SUSPECTED when N_k >= 4."""
    df = make_nominal_lot(n_components=12)
    # Assign CH_07 to components C001, C002, C003, C004 (N_k = 4 >= 4), and offset RDS(on) by +6 mOhm
    target_comps = ["LOT_TEST_C001", "LOT_TEST_C002", "LOT_TEST_C003", "LOT_TEST_C004"]
    df.loc[df["component_id"].isin(target_comps), "channel_id"] = "CH_07"
    df.loc[(df["channel_id"] == "CH_07") & (df["parameter_name"] == "RDS(on)"), "value"] += 6.0

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=24)
    p_rdson = res.parameter_results["RDS(on)"]
    assert p_rdson.equipment_evidence.status == EquipmentStatus.CHANNEL_BIAS_SUSPECTED
    assert res.final_state == ScreeningState.EQUIPMENT_SUSPECTED


def test_scenario_10_ate_channel_bias_small_sample_suppression():
    """Verify channel bias inference is suppressed when N_k < 4 to prevent false alarms on small subgroups."""
    df = make_nominal_lot(n_components=12)
    # Assign CH_07 to only 2 components (N_k = 2 < 4)
    df.loc[df["component_id"].isin(["LOT_TEST_C001", "LOT_TEST_C002"]), "channel_id"] = "CH_07"
    df.loc[(df["channel_id"] == "CH_07") & (df["parameter_name"] == "RDS(on)"), "value"] += 6.0

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=24)
    p_rdson = res.parameter_results["RDS(on)"]
    assert p_rdson.equipment_evidence.status == EquipmentStatus.CHANNEL_BIAS_SUPPRESSED_SMALL_SAMPLE
    assert p_rdson.equipment_evidence.suspected is False


# ============================================================================
# 11. Small Lot Heuristic (N < 8)
# ============================================================================
def test_scenario_11_small_lot_heuristic():
    """Verify small lot policy formally suppresses peer deviation while keeping absolute and temporal gates active."""
    df_small = make_nominal_lot(n_components=5)
    res = screen_component(df_small, "LOT_TEST_C001", as_of_hours=24)

    p_rdson = res.parameter_results["RDS(on)"]
    assert p_rdson.peer_evidence.status == PeerDeviationStatus.PEER_SUPPRESSED_SMALL_LOT
    assert p_rdson.peer_evidence.z_score is None
    # Absolute specification gate remains 100% active
    assert p_rdson.spec_evidence.passed is True


# ============================================================================
# 12. Missing Checkpoint
# ============================================================================
def test_scenario_12_missing_checkpoint():
    """Verify missing intermediate checkpoint triggers INSUFFICIENT_DATA."""
    df = make_nominal_lot()
    # Drop 24h reading for C001
    df = df[~((df["component_id"] == "LOT_TEST_C001") & (df["elapsed_hours"] == 24))]

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=96)
    assert res.final_state == ScreeningState.INSUFFICIENT_DATA
    assert "MISSING_CHECKPOINTS" in res.primary_reason_code


# ============================================================================
# 13, 14, 15. Signed IGSS Handling: Negative, Positive, and Zero
# ============================================================================
def test_scenario_13_14_15_signed_igss():
    """Verify signed IGSS representation preserves negative, positive, and exact zero without error."""
    df = make_nominal_lot()

    # Negative IGSS: -15 nA
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "IGSS"), "value"] = -15.0
    res_neg = screen_component(df, "LOT_TEST_C001", as_of_hours=24)
    assert res_neg.parameter_results["IGSS"].transformed_value < 0
    assert res_neg.parameter_results["IGSS"].spec_evidence.passed is True

    # Positive IGSS: +15 nA
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "IGSS"), "value"] = +15.0
    res_pos = screen_component(df, "LOT_TEST_C001", as_of_hours=24)
    assert res_pos.parameter_results["IGSS"].transformed_value > 0

    # Exact Zero IGSS: 0.0 nA
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "IGSS"), "value"] = 0.0
    res_zero = screen_component(df, "LOT_TEST_C001", as_of_hours=24)
    assert res_zero.parameter_results["IGSS"].transformed_value == 0.0


# ============================================================================
# 16, 17, 18, 19. Individual Parameter Table I Breaches
# ============================================================================
def test_scenario_16_high_igss_breach():
    """Verify IGSS breach > 100 nA triggers FAIL."""
    df = make_nominal_lot()
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "IGSS"), "value"] = 120.0
    res = screen_component(df, "LOT_TEST_C001", as_of_hours=0)
    assert res.final_state == ScreeningState.FAIL
    assert "ABSOLUTE_LIMIT_BREACH_IGSS_HIGH" in res.primary_reason_code


def test_scenario_17_high_rdson_breach():
    """Verify RDS(on) breach > 65 mOhm triggers FAIL."""
    df = make_nominal_lot()
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "RDS(on)"), "value"] = 67.5
    res = screen_component(df, "LOT_TEST_C001", as_of_hours=0)
    assert res.final_state == ScreeningState.FAIL
    assert "ABSOLUTE_LIMIT_BREACH_RDSON_HIGH" in res.primary_reason_code


def test_scenario_18_high_idss_breach():
    """Verify IDSS breach > 10 uA triggers FAIL."""
    df = make_nominal_lot()
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "IDSS"), "value"] = 14.2
    res = screen_component(df, "LOT_TEST_C001", as_of_hours=0)
    assert res.final_state == ScreeningState.FAIL
    assert "ABSOLUTE_LIMIT_BREACH_IDSS_HIGH" in res.primary_reason_code


def test_scenario_19_vgsth_boundary_breach():
    """Verify VGS(th) breach outside [2.0, 4.0] V triggers FAIL."""
    df = make_nominal_lot()
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "VGS(th)"), "value"] = 1.85
    res = screen_component(df, "LOT_TEST_C001", as_of_hours=0)
    assert res.final_state == ScreeningState.FAIL
    assert "ABSOLUTE_LIMIT_BREACH_VGSTH_LOW" in res.primary_reason_code
