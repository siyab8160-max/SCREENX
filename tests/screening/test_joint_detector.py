"""Unit tests for Detector J / D_joint (Multivariate Joint-Parameter Backstop).

Complies with Metric 1.2 Multivariate Joint Anomaly Detection:
- Verifies Mahalanobis distance across all 4 parameters jointly.
- Verifies Leave-One-Out (LOO) shrinkage covariance estimation.
- Verifies detection of correlated sub-threshold multi-parameter drift where
  individual parameters remain below univariate cutoffs (|g| < 2.5).
- Verifies small-lot guard behavior (N < 6).
- Verifies integration with pipeline and fusion engine.
"""

import numpy as np
import pandas as pd
import pytest

from sih26170.screening.joint import (
    DEFAULT_JOINT_MAHALANOBIS_THRESHOLD,
    evaluate_joint_mahalanobis,
    evaluate_multivariate_joint_backstop,
)
from sih26170.screening.pipeline import screen_component
from sih26170.screening.schema import (
    AbruptStepStatus,
    DispositionQualifier,
    JointStatus,
    PeerDeviationStatus,
    ScreeningState,
    TemporalDriftStatus,
)
from sih26170.screening.transforms import transform_parameter


def make_joint_test_lot(n_components: int = 15) -> pd.DataFrame:
    """Generate a clean reference lot with n_components at t=0 and t=24."""
    rng = np.random.default_rng(26170)
    rows = []
    lot_id = "LOT_TEST_JOINT"
    
    for i in range(1, n_components + 1):
        cid = f"{lot_id}_C{i:03d}"
        for t in [0, 24]:
            # Normal small fluctuations around nominal values
            idss = 0.50 + rng.normal(0, 0.01)
            vgs = 3.00 + rng.normal(0, 0.01)
            rds = 45.0 + rng.normal(0, 0.2)
            igss = 2.0 + rng.normal(0, 0.1)

            rows.append({"component_id": cid, "lot_id": lot_id, "parameter_name": "IDSS", "elapsed_hours": t, "value": idss, "unit": "uA", "instrument_id": "ATE_01", "channel_id": "CH_01"})
            rows.append({"component_id": cid, "lot_id": lot_id, "parameter_name": "VGS(th)", "elapsed_hours": t, "value": vgs, "unit": "V", "instrument_id": "ATE_01", "channel_id": "CH_01"})
            rows.append({"component_id": cid, "lot_id": lot_id, "parameter_name": "RDS(on)", "elapsed_hours": t, "value": rds, "unit": "mOhm", "instrument_id": "ATE_01", "channel_id": "CH_01"})
            rows.append({"component_id": cid, "lot_id": lot_id, "parameter_name": "IGSS", "elapsed_hours": t, "value": igss, "unit": "nA", "instrument_id": "ATE_01", "channel_id": "CH_01"})

    return pd.DataFrame(rows)


def test_joint_small_lot_guard():
    """Verify lots with N < 6 components suppress joint evaluation gracefully."""
    df = make_joint_test_lot(n_components=4)
    ev = evaluate_joint_mahalanobis(
        component_id="LOT_TEST_JOINT_C001",
        lot_id="LOT_TEST_JOINT",
        checkpoint=24,
        lot_observations_as_of=df,
    )
    assert ev.status == JointStatus.INSUFFICIENT_PEERS
    assert ev.suspected is False
    assert ev.mahalanobis_distance is None
    assert "INSUFFICIENT" in ev.reason_code


def test_joint_nominal_lot():
    """Verify all nominal components in a clean lot pass joint Mahalanobis evaluation."""
    df = make_joint_test_lot(n_components=15)
    for i in range(1, 16):
        cid = f"LOT_TEST_JOINT_C{i:03d}"
        ev = evaluate_joint_mahalanobis(
            component_id=cid,
            lot_id="LOT_TEST_JOINT",
            checkpoint=24,
            lot_observations_as_of=df,
        )
        assert ev.status == JointStatus.NOMINAL_JOINT
        assert ev.suspected is False
        assert ev.mahalanobis_distance is not None
        assert ev.mahalanobis_distance < DEFAULT_JOINT_MAHALANOBIS_THRESHOLD
        assert len(ev.feature_contributions) == 4


def test_joint_correlated_sub_threshold_drift():
    """Verify that coordinated sub-threshold shifts across multiple parameters trigger D_joint.

    Proves the differentiation claim: 'D_joint catches what no single detector can.'
    Specifically:
    1. Every parameter individually sits strictly below univariate outlier cutoffs:
       - Detector B (D_peer): |z_peer| < 3.0 sigma (MILD outlier threshold is 3.0; status is PEER_NORMAL)
       - Detector C (D_drift): |g_drift| < 2.5 sigma (SUBTLE drift threshold is 2.5; status is STATIONARY)
       - Detector A (Specification): passes limits
       - Detector D (Step Change): status is STEP_NORMAL
       - Detector E (Equipment): suspected is False
       Consequently, every parameter individually evaluates to parameter_state == ScreeningState.PASS.
    2. None of the individual detectors flag the component.
    3. However, the joint Mahalanobis distance D_joint across all 4 parameters exceeds
       DEFAULT_JOINT_MAHALANOBIS_THRESHOLD (4.25 ~ chi^2_4 upper 0.1% quantile).
    4. The fusion engine escalates the component to HOLD (with JOINT_MAHALANOBIS_EXCESS reason).
    """
    df = make_joint_test_lot(n_components=20)
    target_cid = "LOT_TEST_JOINT_C001"

    # Read target component baseline values at t=0h in transformed space
    u0_idss = transform_parameter("IDSS", df.loc[(df["component_id"] == target_cid) & (df["parameter_name"] == "IDSS") & (df["elapsed_hours"] == 0), "value"].iloc[0])
    u0_vgs = transform_parameter("VGS(th)", df.loc[(df["component_id"] == target_cid) & (df["parameter_name"] == "VGS(th)") & (df["elapsed_hours"] == 0), "value"].iloc[0])
    u0_rds = transform_parameter("RDS(on)", df.loc[(df["component_id"] == target_cid) & (df["parameter_name"] == "RDS(on)") & (df["elapsed_hours"] == 0), "value"].iloc[0])
    u0_igss = transform_parameter("IGSS", df.loc[(df["component_id"] == target_cid) & (df["parameter_name"] == "IGSS") & (df["elapsed_hours"] == 0), "value"].iloc[0])

    # Inject calibrated 1.9 sigma shifts in Delta u space:
    # - IDSS (log scale): +0.05 * 1.9 -> produces |z| = 2.03 < 3.0, |g| = 1.90 < 2.5
    # - VGS(th) (linear): +0.010 * 1.9 -> produces |z| = 0.34 < 3.0, |g| = 1.84 < 2.5
    # - RDS(on) (log scale): +0.010 * 1.9 -> produces |z| = 2.58 < 3.0, |g| = 1.90 < 2.5
    # - IGSS (asinh scale): +0.10 * 1.9 -> produces |z| = 1.82 < 3.0, |g| = 1.90 < 2.5
    shifts = {
        "IDSS": float(np.exp(u0_idss + 0.05 * 1.9)),
        "VGS(th)": float(u0_vgs + 0.010 * 1.9),
        "RDS(on)": float(np.exp(u0_rds + 0.010 * 1.9)),
        "IGSS": float(np.sinh(u0_igss + 0.10 * 1.9)),
    }
    for p, val in shifts.items():
        df.loc[
            (df["component_id"] == target_cid)
            & (df["parameter_name"] == p)
            & (df["elapsed_hours"] == 24),
            "value",
        ] = val

    # 1. Direct evaluation of Detector J / D_joint with canonical threshold (4.25)
    ev = evaluate_joint_mahalanobis(
        component_id=target_cid,
        lot_id="LOT_TEST_JOINT",
        checkpoint=24,
        lot_observations_as_of=df,
        threshold=DEFAULT_JOINT_MAHALANOBIS_THRESHOLD,
    )
    assert ev.mahalanobis_distance is not None
    assert ev.mahalanobis_distance > DEFAULT_JOINT_MAHALANOBIS_THRESHOLD
    assert ev.suspected is True
    assert ev.status == JointStatus.JOINT_ANOMALY_ALERT
    assert "JOINT_MAHALANOBIS_EXCESS" in ev.reason_code

    # 2. End-to-end pipeline evaluation via screen_component
    res = screen_component(df, target_cid, as_of_hours=24)

    # Rigorous differentiation assertions:
    # Verify that Detector B (Peer) does NOT independently flag ANY parameter (|z| < 3.0)
    for p_name, p_res in res.parameter_results.items():
        # Detector B check
        assert p_res.peer_evidence.status == PeerDeviationStatus.PEER_NORMAL, (
            f"Expected {p_name} Detector B to be PEER_NORMAL, got {p_res.peer_evidence.status}"
        )
        assert abs(p_res.peer_evidence.z_score) < 3.0, (
            f"{p_name} z_score {p_res.peer_evidence.z_score} exceeded mild threshold 3.0"
        )

        # Detector C check
        assert p_res.temporal_evidence.status == TemporalDriftStatus.STATIONARY, (
            f"Expected {p_name} Detector C to be STATIONARY, got {p_res.temporal_evidence.status}"
        )
        assert abs(p_res.temporal_evidence.normalized_drift) < 2.5, (
            f"{p_name} normalized drift {p_res.temporal_evidence.normalized_drift} exceeded subtle threshold 2.5"
        )

        # Single parameter state must remain PASS
        assert p_res.parameter_state == ScreeningState.PASS, (
            f"Expected univariate parameter {p_name} to PASS, got {p_res.parameter_state}"
        )

    # 3. Confirm D_joint fired and successfully escalated the component to HOLD
    assert res.joint_evidence is not None
    assert res.joint_evidence.suspected is True
    assert res.joint_evidence.status == JointStatus.JOINT_ANOMALY_ALERT
    assert res.joint_evidence.mahalanobis_distance > DEFAULT_JOINT_MAHALANOBIS_THRESHOLD
    assert res.final_state in (ScreeningState.HOLD, ScreeningState.ALERT)
    assert "JOINT_MAHALANOBIS_EXCESS" in res.primary_reason_code


def test_joint_benchmark_frozen_dataset_precision():
    """Verify precision benchmark on the frozen 398-component synthetic benchmark.

    Demonstrates that evaluating D_joint at t=24h with calibrated threshold D_crit=4.25
    achieves exactly 66.7% precision (2 True Positives, 1 False Positive out of 3 flagged parts)
    on data/synthetic_phase2f_frozen.
    """
    from pathlib import Path
    repo_root = Path(__file__).resolve().parent.parent.parent
    data_dir = repo_root / "data/synthetic_phase2f_frozen"
    if not (data_dir / "observations.csv").exists():
        pytest.skip("Frozen benchmark dataset not present.")

    obs_df = pd.read_csv(data_dir / "observations.csv")
    gt_df = pd.read_csv(data_dir / "ground_truth.csv")
    lots = sorted(obs_df["lot_id"].unique())

    res = evaluate_multivariate_joint_backstop(
        obs_df=obs_df,
        gt_df=gt_df,
        lot_ids=lots,
        checkpoint=24,
        threshold=DEFAULT_JOINT_MAHALANOBIS_THRESHOLD,
    )

    c = res["contingency"]
    assert c["tp"] == 2
    assert c["fp"] == 1
    assert c["flagged"] == 3
    assert c["precision"] == 0.667

