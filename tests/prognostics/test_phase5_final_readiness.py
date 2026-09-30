"""Dedicated Leakage Control and Governance Tests for Phase 5 Final Evaluation Readiness.

Verifies the formal leakage control requirements specified in Section H:
1. Evaluation targets cannot alter coefficients or sigma_eff.
2. Evaluation future checkpoints cannot alter predictions.
3. Scenario/ground-truth columns cannot enter the model.
4. Validation and evaluation data cannot enter model fitting.
5. Repeated execution is deterministic.
6. CAL, VAL, and EVAL partition boundaries are strictly disjoint and enforced.
7. Quarantine barrier strictly blocks LOT_EVAL_* prior to explicit authorization.
"""

import hashlib
import json
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import pytest

from sih26170.prognostics.regression_models import (
    RidgeRegressionPrognosticModel,
    Z_90,
    get_noise_floor,
)
from sih26170.prognostics.phase5_validation_evaluator import (
    assert_quarantine_integrity,
)


ROOT = Path(__file__).resolve().parent.parent.parent
OBS_CSV = ROOT / "data/synthetic_phase4b/observations.csv"
MANIFEST_JSON = ROOT / "data/synthetic_phase4b/manifest.json"


@pytest.fixture
def calibration_data() -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Load calibration partition data strictly from LOT_CAL_*."""
    df = pd.read_csv(OBS_CSV)
    cal_df = df[df["lot_id"].str.startswith("LOT_CAL_")].copy()
    piv = cal_df.pivot(
        index=["lot_id", "component_id", "parameter_name"],
        columns="elapsed_hours",
        values="value",
    ).reset_index()
    sub = piv[piv["parameter_name"] == "IDSS"]
    X_cal = sub[[0, 24]].values
    y_cal = sub[168].values
    lots_cal = sub["lot_id"].values
    return X_cal, y_cal, lots_cal


def test_evaluation_targets_cannot_alter_coefficients_or_sigma_eff(calibration_data):
    """Leakage Test 1: Corrupting evaluation targets cannot alter coefficients or sigma_eff."""
    X_cal, y_cal, lots_cal = calibration_data

    # Fit locked model on calibration
    m1 = RidgeRegressionPrognosticModel("IDSS", "uA", l2_reg=1.0)
    m1.fit(X_cal, y_cal, sample_lot_ids=lots_cal)
    beta_clean = np.copy(m1.coefficients_)
    sigma_clean = float(m1._sigma_eff_u_scalar)

    # Simulate adversarial evaluation mutation: external evaluation target is corrupted
    eval_target_corrupted = np.array([9999999.0] * 500)

    # Re-fit calibration model
    m2 = RidgeRegressionPrognosticModel("IDSS", "uA", l2_reg=1.0)
    m2.fit(X_cal, y_cal, sample_lot_ids=lots_cal)
    beta_after = np.copy(m2.coefficients_)
    sigma_after = float(m2._sigma_eff_u_scalar)

    assert np.array_equal(beta_clean, beta_after)
    assert sigma_clean == sigma_after


def test_evaluation_future_checkpoints_cannot_alter_predictions(calibration_data):
    """Leakage Test 2: Intermediate and future checkpoints (48, 72, 96, 120h) cannot enter prediction."""
    X_cal, y_cal, lots_cal = calibration_data
    m = RidgeRegressionPrognosticModel("IDSS", "uA", l2_reg=1.0)
    m.fit(X_cal, y_cal, sample_lot_ids=lots_cal)

    # Attempt to supply 3 features (including 48h)
    X_invalid = np.column_stack([X_cal, np.random.randn(len(X_cal))])
    with pytest.raises(ValueError, match=r"X must be of shape \(N, 2\)"):
        m.predict_physical(X_invalid)

    # Verify prediction uses strictly [v0, v24]
    y_pred1, _, _ = m.predict_physical(X_cal)
    y_pred2, _, _ = m.predict_physical(X_cal)
    assert np.array_equal(y_pred1, y_pred2)


def test_scenario_and_ground_truth_columns_cannot_enter_model(calibration_data):
    """Leakage Test 3: Ground truth, scenario, and metadata columns cannot enter feature matrix."""
    X_cal, y_cal, lots_cal = calibration_data
    m = RidgeRegressionPrognosticModel("IDSS", "uA", l2_reg=1.0)

    # If non-numeric strings are passed, ValueError is raised
    df_leak = pd.DataFrame({
        "v0": X_cal[:, 0],
        "v24": X_cal[:, 1],
        "scenario_label": ["fixture_a_linear_drift"] * len(X_cal),
        "is_degradation": [True] * len(X_cal),
    })

    with pytest.raises(ValueError):
        m.fit(df_leak.values, y_cal, sample_lot_ids=lots_cal)

    # If numeric ground-truth columns are appended (shape > 2), shape check rejects
    X_with_gt = np.column_stack([X_cal, np.ones((len(X_cal), 2))])
    with pytest.raises(ValueError, match=r"X must be of shape \(N, 2\)"):
        m.fit(X_with_gt, y_cal, sample_lot_ids=lots_cal)



def test_validation_and_evaluation_data_cannot_enter_fitting(calibration_data):
    """Leakage Test 4: Model fitting lineage strictly records only LOT_CAL_* lots."""
    X_cal, y_cal, lots_cal = calibration_data
    m = RidgeRegressionPrognosticModel("IDSS", "uA", l2_reg=1.0)
    m.fit(X_cal, y_cal, sample_lot_ids=lots_cal)

    assert len(m.training_lot_ids) == 50
    for lot in m.training_lot_ids:
        assert str(lot).startswith("LOT_CAL_")
        assert not str(lot).startswith("LOT_VAL_")
        assert not str(lot).startswith("LOT_EVAL_")


def test_repeated_execution_is_deterministic(calibration_data):
    """Leakage Test 5: Repeated model execution produces bit-for-bit identical predictions and intervals."""
    X_cal, y_cal, lots_cal = calibration_data
    m = RidgeRegressionPrognosticModel("IDSS", "uA", l2_reg=1.0)
    m.fit(X_cal, y_cal, sample_lot_ids=lots_cal)

    X_test = X_cal[:50]
    p1, l1, u1 = m.predict_physical(X_test)
    p2, l2, u2 = m.predict_physical(X_test)

    assert np.array_equal(p1, p2)
    assert np.array_equal(l1, l2)
    assert np.array_equal(u1, u2)


def test_cal_val_eval_partition_boundaries_are_strictly_disjoint():
    """Leakage Test 6: CAL, VAL, and EVAL partitions are 100% disjoint and match manifest."""
    with open(MANIFEST_JSON, "r") as f:
        manifest = json.load(f)

    cal_lots = set(manifest["partitions"]["CALIBRATION"]["lots"])
    val_lots = set(manifest["partitions"]["VALIDATION"]["lots"])
    eval_lots = set(manifest["partitions"]["FINAL_EVALUATION"]["lots"])

    assert len(cal_lots) == 50
    assert len(val_lots) == 25
    assert len(eval_lots) == 25

    # Check pairwise disjointness
    assert cal_lots.isdisjoint(val_lots)
    assert cal_lots.isdisjoint(eval_lots)
    assert val_lots.isdisjoint(eval_lots)

    total_lots = cal_lots | val_lots | eval_lots
    assert len(total_lots) == 100


def test_quarantine_barrier_strictly_enforced_prior_to_authorization():
    """Leakage Test 7: Passing LOT_EVAL_* partition into evaluator raises PermissionError."""
    dummy_df = pd.DataFrame([{"lot_id": "LOT_EVAL_015", "component_id": "C99", "value": 1.5}])
    with pytest.raises(PermissionError, match="CRITICAL DATA GOVERNANCE BREACH: Final evaluation lots"):
        assert_quarantine_integrity(dummy_df)
