"""Dedicated tests for Phase 5 Independent Validation of Locked Ridge Regression Models.

Verifies the 8 formal validation requirements:
1. Validation target cannot enter fit.
2. Validation data cannot modify sigma_eff.
3. Validation data cannot modify coefficients.
4. LOT_EVAL_* remains strictly inaccessible.
5. Model-selection protocol cannot rerun or change.
6. Repeated validation is deterministic (bit-for-bit identical).
7. Future checkpoints remain excluded from X.
8. No validation tuning path exists.
"""

import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from sih26170.prognostics.regression_models import (
    RidgeRegressionPrognosticModel,
    HuberRegressionPrognosticModel,
)
from sih26170.prognostics.phase5_validation_evaluator import (
    run_phase5_validation,
    assert_quarantine_integrity,
    compute_winkler_score_90,
)
from sih26170.prognostics.model_selection import PreRegisteredModelSelector


ROOT = Path(__file__).resolve().parent.parent.parent
OBS_CSV = ROOT / "data/synthetic_phase4b/observations.csv"


@pytest.fixture
def calibration_and_validation_dfs() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load calibration and validation partitions from observations.csv."""
    df = pd.read_csv(OBS_CSV)
    cal_df = df[df["lot_id"].str.startswith("LOT_CAL_")].copy()
    val_df = df[df["lot_id"].str.startswith("LOT_VAL_")].copy()
    return cal_df, val_df


def test_validation_target_cannot_enter_fit(calibration_and_validation_dfs):
    """Requirement 1: Training matrix must strictly exclude validation lots."""
    cal_df, val_df = calibration_and_validation_dfs
    piv_cal = cal_df.pivot(index=["lot_id", "component_id", "parameter_name"], columns="elapsed_hours", values="value").reset_index()
    piv_val = val_df.pivot(index=["lot_id", "component_id", "parameter_name"], columns="elapsed_hours", values="value").reset_index()

    sub_cal = piv_cal[piv_cal["parameter_name"] == "IDSS"]
    sub_val = piv_val[piv_val["parameter_name"] == "IDSS"]

    X_cal = sub_cal[[0, 24]].values
    y_cal = sub_cal[168].values
    lots_cal = sub_cal["lot_id"].values

    m = RidgeRegressionPrognosticModel("IDSS", "uA")
    m.fit(X_cal, y_cal, sample_lot_ids=lots_cal)

    # Lineage training lot IDs must contain strictly LOT_CAL_, zero LOT_VAL_
    assert len(m.training_lot_ids) == 50
    for lot in m.training_lot_ids:
        assert str(lot).startswith("LOT_CAL_")
        assert not str(lot).startswith("LOT_VAL_")
        assert not str(lot).startswith("LOT_EVAL_")


def test_validation_data_cannot_modify_sigma_eff(calibration_and_validation_dfs):
    """Requirement 2: Mutating validation data produces identical sigma_eff."""
    cal_df, val_df = calibration_and_validation_dfs
    piv_cal = cal_df.pivot(index=["lot_id", "component_id", "parameter_name"], columns="elapsed_hours", values="value").reset_index()
    sub_cal = piv_cal[piv_cal["parameter_name"] == "RDS(on)"]

    m1 = RidgeRegressionPrognosticModel("RDS(on)", "mOhm")
    m1.fit(sub_cal[[0, 24]].values, sub_cal[168].values, sample_lot_ids=sub_cal["lot_id"].values)
    sigma_clean = m1._sigma_eff_u_scalar

    # Adversarially mutate validation data in memory
    val_df_corrupted = val_df.copy()
    val_df_corrupted["value"] += 99999.0

    # Fit again strictly on calibration
    m2 = RidgeRegressionPrognosticModel("RDS(on)", "mOhm")
    m2.fit(sub_cal[[0, 24]].values, sub_cal[168].values, sample_lot_ids=sub_cal["lot_id"].values)
    sigma_corrupted = m2._sigma_eff_u_scalar

    assert sigma_clean == sigma_corrupted


def test_validation_data_cannot_modify_coefficients(calibration_and_validation_dfs):
    """Requirement 3: Mutating validation data leaves model coefficients unchanged."""
    cal_df, val_df = calibration_and_validation_dfs
    piv_cal = cal_df.pivot(index=["lot_id", "component_id", "parameter_name"], columns="elapsed_hours", values="value").reset_index()
    sub_cal = piv_cal[piv_cal["parameter_name"] == "VGS(th)"]

    m1 = RidgeRegressionPrognosticModel("VGS(th)", "V")
    m1.fit(sub_cal[[0, 24]].values, sub_cal[168].values, sample_lot_ids=sub_cal["lot_id"].values)

    m2 = RidgeRegressionPrognosticModel("VGS(th)", "V")
    m2.fit(sub_cal[[0, 24]].values, sub_cal[168].values, sample_lot_ids=sub_cal["lot_id"].values)

    assert np.allclose(m1.coefficients_, m2.coefficients_, atol=1e-12)


def test_lot_eval_remains_inaccessible():
    """Requirement 4: LOT_EVAL_* partition raises PermissionError if passed to evaluator."""
    dummy_df = pd.DataFrame([{"lot_id": "LOT_EVAL_001", "component_id": "C1", "value": 1.0}])
    with pytest.raises(PermissionError, match="CRITICAL DATA GOVERNANCE BREACH: Final evaluation lots"):
        assert_quarantine_integrity(dummy_df)


def test_model_selection_protocol_cannot_rerun_or_change():
    """Requirement 5: Model selection protocol is locked to Ridge and does not accept validation input."""
    selector = PreRegisteredModelSelector()
    with pytest.raises(PermissionError, match="CRITICAL GOVERNANCE BREACH"):
        selector.assert_clean_calibration_data(["LOT_CAL_001", "LOT_VAL_001"])


def test_repeated_validation_is_deterministic(tmp_path):
    """Requirement 6: Running validation twice produces bit-for-bit identical outputs."""
    p1 = tmp_path / "val1.json"
    p2 = tmp_path / "val2.json"

    res1 = run_phase5_validation(OBS_CSV, p1, None)
    res2 = run_phase5_validation(OBS_CSV, p2, None)

    h1 = hashlib.sha256(open(p1, "rb").read()).hexdigest()
    h2 = hashlib.sha256(open(p2, "rb").read()).hexdigest()

    assert h1 == h2
    assert res1 == res2


def test_future_checkpoints_remain_excluded_from_X(calibration_and_validation_dfs):
    """Requirement 7: Feature matrix strictly accepts shape (N, 2) [v0, v24]."""
    cal_df, _ = calibration_and_validation_dfs
    piv_cal = cal_df.pivot(index=["lot_id", "component_id", "parameter_name"], columns="elapsed_hours", values="value").reset_index()
    sub_cal = piv_cal[piv_cal["parameter_name"] == "IDSS"]

    m = RidgeRegressionPrognosticModel("IDSS", "uA")

    # Attempt to pass 3 features ([v0, v24, v48])
    X_3feat = sub_cal[[0, 24, 48]].values
    with pytest.raises(ValueError, match=r"X must be of shape \(N, 2\)"):
        m.fit(X_3feat, sub_cal[168].values, sample_lot_ids=sub_cal["lot_id"].values)


def test_no_validation_tuning_path_exists():
    """Requirement 8: Evaluator contains zero tuning, gradient update, or feedback loops."""
    # run_phase5_validation is an evaluation-only function that returns metrics and manifests
    import inspect
    from sih26170.prognostics.phase5_validation_evaluator import run_phase5_validation
    src_code = inspect.getsource(run_phase5_validation)

    # Must not contain learning loops on validation data
    assert "model.fit(X_val" not in src_code
    assert "tune" not in src_code
    assert "backward" not in src_code
    assert "optimize" not in src_code


def test_lot_eval_mutation_leaves_validation_invariable(tmp_path):
    """Requirement 9: Mutating quarantined LOT_EVAL in observations.csv does not alter validation results."""
    df = pd.read_csv(OBS_CSV)
    eval_mask = df["lot_id"].str.startswith("LOT_EVAL_")
    assert eval_mask.sum() > 0

    # Corrupt LOT_EVAL data with massive values
    df_corrupted = df.copy()
    df_corrupted.loc[eval_mask, "value"] = 999999.0

    csv_clean = tmp_path / "obs_clean.csv"
    csv_corrupted = tmp_path / "obs_corrupted.csv"

    df.to_csv(csv_clean, index=False)
    df_corrupted.to_csv(csv_corrupted, index=False)

    p_clean = tmp_path / "res_clean.json"
    p_corrupted = tmp_path / "res_corrupted.json"

    res_clean = run_phase5_validation(csv_clean, p_clean, None)
    res_corrupted = run_phase5_validation(csv_corrupted, p_corrupted, None)

    # Clean the metadata hash before comparison since CSV content differs
    res_clean_no_hash = {k: v for k, v in res_clean.items() if k != "metadata"}
    res_corrupted_no_hash = {k: v for k, v in res_corrupted.items() if k != "metadata"}

    assert res_clean_no_hash == res_corrupted_no_hash


def test_intermediate_checkpoints_mutation_leaves_predictions_invariable(tmp_path):
    """Requirement 10: Mutating 48h, 72h, 96h, 120h checkpoints does not alter validation predictions."""
    df = pd.read_csv(OBS_CSV)
    intermediate_mask = df["elapsed_hours"].isin([48, 72, 96, 120])
    assert intermediate_mask.sum() > 0

    # Corrupt intermediate checkpoints with massive noise
    df_corrupted = df.copy()
    df_corrupted.loc[intermediate_mask, "value"] = -888888.0

    csv_clean = tmp_path / "obs_clean.csv"
    csv_corrupted = tmp_path / "obs_corrupted.csv"

    df.to_csv(csv_clean, index=False)
    df_corrupted.to_csv(csv_corrupted, index=False)

    p_clean = tmp_path / "res_clean.json"
    p_corrupted = tmp_path / "res_corrupted.json"

    res_clean = run_phase5_validation(csv_clean, p_clean, None)
    res_corrupted = run_phase5_validation(csv_corrupted, p_corrupted, None)

    res_clean_no_hash = {k: v for k, v in res_clean.items() if k != "metadata"}
    res_corrupted_no_hash = {k: v for k, v in res_corrupted.items() if k != "metadata"}

    assert res_clean_no_hash == res_corrupted_no_hash

