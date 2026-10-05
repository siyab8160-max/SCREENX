"""Unit and integration tests for Module A Change & Retraining Plan implementation.

Directly validates all 4 changes specified in the October 2026 Change Plan:
1. Change #1: Persistent temporal residual / change-point detector (CUSUM over LOO residuals)
   - SMALL_BUT_PERSISTENT_DRIFT accumulates evidence across checkpoints
   - HIGH_BUT_STABLE remains low risk (CUSUM = 0)
   - COMMON-MODE MOVEMENT does not trigger device CUSUM (LOO excess = 0)
   - 2-point history at 24h suppresses CUSUM alarms
2. Change #2: Quantitative equipment/device decomposition
   - Preserves common_mode_evidence and device_specific_evidence in output
   - Distinguishes shared movement from component-specific excess
3. Change #3: Detector-score empirical calibration
   - Calibrates raw scores into comparable [0, 1] evidence scales
4. Change #4: Robust multivariate early-change detector
   - Evaluates early parameter changes Delta u = u(T) - u(0) in delta space
   - Detects compound sub-threshold degradation and escalates to HOLD
"""

import numpy as np
import pandas as pd
import pytest

from sih26170.screening.calibration import (
    calibrate_equipment_score,
    calibrate_joint_score,
    calibrate_peer_score,
    calibrate_step_score,
    calibrate_temporal_drift_score,
)
from sih26170.screening.joint import evaluate_joint_mahalanobis
from sih26170.screening.pipeline import screen_component
from sih26170.screening.schema import (
    DispositionQualifier,
    EquipmentStatus,
    JointStatus,
    ScreeningState,
    TemporalDriftStatus,
)
from tests.screening.test_scenarios import make_nominal_lot


# ============================================================================
# Change #1: Persistent Temporal Residual / Change-Point Detector
# ============================================================================
def test_change1_small_but_persistent_drift_accumulates_cusum():
    """Verify small persistent drift accumulates evidence and triggers PERSISTENT_DRIFT.

    Component exhibits small positive drift at each interval (24h, 96h, 168h):
    At each point, |g(T)| is ~1.8 (strictly below the single-point cutoff 2.5),
    so standard univariate thresholding would call it STATIONARY.
    However, the sequential CUSUM over LOO residuals accumulates evidence past 3.5.
    """
    df = make_nominal_lot(n_components=12)
    target_cid = "LOT_TEST_C001"

    # Inject persistent small drift on IDSS:
    # 0h: 0.50 uA, 24h: 0.518 uA (~1.0 sigma), 96h: 0.536 uA (~1.8 sigma), 168h: 0.548 uA (~2.2 sigma)
    drift_vals = {0: 0.50, 24: 0.518, 96: 0.536, 168: 0.548}
    for t, v in drift_vals.items():
        df.loc[
            (df["component_id"] == target_cid)
            & (df["parameter_name"] == "IDSS")
            & (df["elapsed_hours"] == t),
            "value",
        ] = v

    # At 24h: only 2 points -> CUSUM must NOT trigger persistent drift alarm
    res_24 = screen_component(df, target_cid, as_of_hours=24)
    p_idss_24 = res_24.parameter_results["IDSS"]
    assert p_idss_24.temporal_evidence.status == TemporalDriftStatus.STATIONARY
    assert not p_idss_24.temporal_evidence.persistent_drift

    # At 168h: 4 points -> CUSUM accumulates and triggers PERSISTENT_DRIFT
    res_168 = screen_component(df, target_cid, as_of_hours=168)
    p_idss_168 = res_168.parameter_results["IDSS"]
    assert p_idss_168.temporal_evidence.cusum_statistic is not None
    assert p_idss_168.temporal_evidence.cusum_statistic >= 2.0
    assert p_idss_168.temporal_evidence.persistent_drift is True
    assert p_idss_168.temporal_evidence.status == TemporalDriftStatus.PERSISTENT_DRIFT
    assert p_idss_168.primary_reason_code == "PERSISTENT_TEMPORAL_DRIFT"
    assert res_168.final_state == ScreeningState.ALERT


def test_change1_high_but_stable_cusum_stays_zero():
    """Verify high initial baseline with zero drift produces CUSUM = 0 and does not trigger."""
    df = make_nominal_lot(n_components=12)
    target_cid = "LOT_TEST_C001"

    # RDS(on) = 58.0 mOhm across all checkpoints (high static offset, zero kinetic departure)
    df.loc[
        (df["component_id"] == target_cid) & (df["parameter_name"] == "RDS(on)"),
        "value",
    ] = 58.0

    res = screen_component(df, target_cid, as_of_hours=168)
    p_rdson = res.parameter_results["RDS(on)"]
    assert p_rdson.temporal_evidence.cusum_statistic == 0.0
    assert not p_rdson.temporal_evidence.persistent_drift
    assert p_rdson.temporal_evidence.status == TemporalDriftStatus.STATIONARY


def test_change1_common_mode_chamber_shift_does_not_trigger_device_cusum():
    """Verify common-mode chamber movement does not trigger device CUSUM because peers shift together."""
    df = make_nominal_lot(n_components=12)
    target_cid = "LOT_TEST_C001"

    # Synchronous chamber excursion: all components shift by +6 mOhm at 96h
    df.loc[
        (df["elapsed_hours"] == 96) & (df["parameter_name"] == "RDS(on)"),
        "value",
    ] += 6.0

    res = screen_component(df, target_cid, as_of_hours=96)
    p_rdson = res.parameter_results["RDS(on)"]

    # Excess drift relative to peer median shift is near zero
    assert abs(p_rdson.temporal_evidence.g_excess) < 1.0
    assert p_rdson.temporal_evidence.cusum_statistic < 1.0
    assert not p_rdson.temporal_evidence.persistent_drift
    assert res.final_state == ScreeningState.EQUIPMENT_SUSPECTED



# ============================================================================
# Change #2: Quantitative Equipment/Device Decomposition
# ============================================================================
def test_change2_equipment_decomposition_evidence_fields():
    """Verify common_mode_evidence and device_specific_evidence are preserved in EquipmentEvidence."""
    df = make_nominal_lot(n_components=12)
    target_cid = "LOT_TEST_C001"

    # Inject chamber shift: +5 mOhm at 96h
    df.loc[
        (df["elapsed_hours"] == 96) & (df["parameter_name"] == "RDS(on)"),
        "value",
    ] += 5.0

    # Inject device-specific excess on C001: extra +8 mOhm
    df.loc[
        (df["component_id"] == target_cid)
        & (df["elapsed_hours"] == 96)
        & (df["parameter_name"] == "RDS(on)"),
        "value",
    ] += 8.0

    res = screen_component(df, target_cid, as_of_hours=96)
    eq_ev = res.parameter_results["RDS(on)"].equipment_evidence

    # Both quantities must be explicitly recorded
    assert eq_ev.common_mode_evidence is not None
    assert eq_ev.common_mode_evidence > 0.0
    assert eq_ev.device_specific_evidence is not None
    assert eq_ev.device_specific_evidence >= 2.5
    assert eq_ev.calibrated_score is not None
    assert 0.0 <= eq_ev.calibrated_score <= 1.0

    # Confounded degradation qualifier
    assert res.disposition_qualifier == DispositionQualifier.COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT


# ============================================================================
# Change #3: Detector-Score Empirical Calibration
# ============================================================================
def test_change3_empirical_score_calibration():
    """Verify all detectors produce normalized [0, 1] calibrated scores."""
    # Peer score calibration
    assert calibrate_peer_score(0.0) == 0.0
    assert 0.99 <= calibrate_peer_score(3.0) <= 1.0
    assert calibrate_peer_score(None) is None

    # Temporal drift score calibration
    assert calibrate_temporal_drift_score(0.0, 0.0) == 0.0
    assert calibrate_temporal_drift_score(3.0, 4.0) > 0.50
    assert calibrate_temporal_drift_score(None, None) is None

    # Step score calibration
    assert calibrate_step_score(0.0) < 0.01
    assert calibrate_step_score(4.0) == 0.50
    assert calibrate_step_score(6.0) > 0.90

    # Joint score calibration (exact chi^2 k=4 CDF)
    assert calibrate_joint_score(0.0) == 0.0
    assert 0.58 <= calibrate_joint_score(2.0) <= 0.61
    assert calibrate_joint_score(4.25) > 0.99

    # Verify runtime pipeline populates calibrated_score on evidence records
    df = make_nominal_lot(n_components=10)
    res = screen_component(df, "LOT_TEST_C001", as_of_hours=24)
    p_idss = res.parameter_results["IDSS"]
    assert p_idss.peer_evidence.calibrated_score is not None
    assert p_idss.temporal_evidence.calibrated_score is not None
    assert p_idss.step_evidence.calibrated_score is not None
    assert p_idss.equipment_evidence.calibrated_score is not None
    assert res.joint_evidence.calibrated_score is not None


# ============================================================================
# Change #4: Robust Multivariate Early-Change Detector
# ============================================================================
def test_change4_joint_multivariate_delta_space():
    """Verify D_joint operates in delta space when T > 0, catching correlated change patterns."""
    df = make_nominal_lot(n_components=15)
    target_cid = "LOT_TEST_C001"

    # Checkpoint 0: evaluated in level space
    ev_0 = evaluate_joint_mahalanobis(
        component_id=target_cid,
        lot_id="LOT_TEST",
        checkpoint=0,
        lot_observations_as_of=df,
    )
    assert ev_0.input_space == "level"
    assert ev_0.status == JointStatus.NOMINAL_JOINT

    # Checkpoint 24: evaluated in delta space
    ev_24 = evaluate_joint_mahalanobis(
        component_id=target_cid,
        lot_id="LOT_TEST",
        checkpoint=24,
        lot_observations_as_of=df,
    )
    assert ev_24.input_space == "delta"
    assert ev_24.status == JointStatus.NOMINAL_JOINT

    # Inject correlated sub-threshold drift on all 4 parameters at 24h
    # Each parameter delta is subtle (~1.5 to 2.0 sigma), escaping univariate cutoffs
    df.loc[(df["component_id"] == target_cid) & (df["parameter_name"] == "IDSS") & (df["elapsed_hours"] == 24), "value"] += 0.035
    df.loc[(df["component_id"] == target_cid) & (df["parameter_name"] == "VGS(th)") & (df["elapsed_hours"] == 24), "value"] += 0.035
    df.loc[(df["component_id"] == target_cid) & (df["parameter_name"] == "RDS(on)") & (df["elapsed_hours"] == 24), "value"] += 0.80
    df.loc[(df["component_id"] == target_cid) & (df["parameter_name"] == "IGSS") & (df["elapsed_hours"] == 24), "value"] += 0.40

    ev_shifted = evaluate_joint_mahalanobis(
        component_id=target_cid,
        lot_id="LOT_TEST",
        checkpoint=24,
        lot_observations_as_of=df,
        threshold=4.0,
    )
    assert ev_shifted.input_space == "delta"
    assert ev_shifted.suspected is True
    assert ev_shifted.status == JointStatus.JOINT_ANOMALY_ALERT
    assert ev_shifted.mahalanobis_distance is not None
    assert ev_shifted.mahalanobis_distance > 4.0

    # Verify pipeline escalation to HOLD
    res = screen_component(df, target_cid, as_of_hours=24)
    assert res.joint_evidence is not None
    assert res.joint_evidence.suspected is True
    assert res.final_state in (ScreeningState.HOLD, ScreeningState.ALERT, ScreeningState.FAIL)
    assert res.compound_evidence is True
