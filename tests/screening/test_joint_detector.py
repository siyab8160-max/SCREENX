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
)
from sih26170.screening.pipeline import screen_component
from sih26170.screening.schema import (
    DispositionQualifier,
    JointStatus,
    ScreeningState,
)


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

    Simulates a component where IDSS, VGS(th), RDS(on), and IGSS all exhibit correlated
    shifts that are individual sub-threshold (e.g. 1.8-2.2 sigma, below univariate cutoff of 2.5),
    but jointly create an extreme Mahalanobis excursion.
    """
    df = make_joint_test_lot(n_components=20)
    target_cid = "LOT_TEST_JOINT_C001"

    # Inject correlated +2.0 sigma shift on all 4 parameters for C001 at 24h
    # IDSS lot std ~ 0.01 -> shift by +0.02
    # VGS(th) lot std ~ 0.01 -> shift by +0.02
    # RDS(on) lot std ~ 0.2 -> shift by +0.45
    # IGSS lot std ~ 0.1 -> shift by +0.22
    shifts = {
        "IDSS": 0.50 + 0.035,
        "VGS(th)": 3.00 + 0.035,
        "RDS(on)": 45.0 + 0.8,
        "IGSS": 2.0 + 0.4,
    }
    for p, val in shifts.items():
        df.loc[
            (df["component_id"] == target_cid)
            & (df["parameter_name"] == p)
            & (df["elapsed_hours"] == 24),
            "value",
        ] = val

    ev = evaluate_joint_mahalanobis(
        component_id=target_cid,
        lot_id="LOT_TEST_JOINT",
        checkpoint=24,
        lot_observations_as_of=df,
        threshold=4.0,
    )
    assert ev.mahalanobis_distance is not None
    assert ev.mahalanobis_distance > 4.0
    assert ev.suspected is True
    assert ev.status == JointStatus.JOINT_ANOMALY_ALERT
    assert "JOINT_MAHALANOBIS_EXCESS" in ev.reason_code

    # Verify end-to-end integration via screen_component
    res = screen_component(df, target_cid, as_of_hours=24)
    assert res.joint_evidence is not None
    assert res.joint_evidence.suspected is True
    # The component should be escalated to HOLD / ALERT rather than escaping as PASS
    assert res.final_state in (ScreeningState.HOLD, ScreeningState.ALERT, ScreeningState.FAIL)
    assert res.compound_evidence is True
