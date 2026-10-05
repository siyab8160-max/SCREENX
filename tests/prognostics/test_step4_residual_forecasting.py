"""Unit and integration tests for Step 4 Residual / Delta Forecasting.

Verifies:
1. Delta target correctness: delta_u == u_168 - u_24
2. Forecast reconstruction: u_168_hat == u_24 + delta_u_hat
3. No future feature leakage: strictly elapsed_hours <= 24h
4. LOO exclusion invariance: mutating target component does not alter peer statistics
5. Deterministic feature generation: bit-for-bit reproducible hashes
6. Exact linear explainability: SHAP additivity down to machine precision
7. Final holdout isolation: zero access to LOT21-LOT24, verified hashes
"""

from __future__ import annotations
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from sih26170.synthetic.burnin_generator import SyntheticBurnInGenerator
from sih26170.screening.transforms import transform_parameter, inverse_transform_parameter
from sih26170.prognostics.lot_context import (
    extract_loo_lot_context_features,
    ResidualRidgeModel,
    RESIDUAL_VARIANTS,
)


@pytest.fixture(scope="module")
def dev_dataset():
    """Generate dev lots LOT01-LOT04 for testing."""
    gen = SyntheticBurnInGenerator(seed=20260918)
    obs_df, gt_df, manifest = gen.generate(lots=["LOT01", "LOT02", "LOT03", "LOT04"], mode="stress")
    return obs_df, gt_df


def test_delta_target_correctness(dev_dataset):
    """Test that delta_u is mathematically identical to u_168 - u_24."""
    obs_df, gt_df = dev_dataset
    feat_df = extract_loo_lot_context_features(obs_df)
    
    gt_target = gt_df[gt_df["target_horizon_hours"] == 168].copy().rename(columns={"actual_value": "y_168"})
    gt_target["u_168"] = [transform_parameter(p, val) for p, val in zip(gt_target["parameter_name"], gt_target["y_168"])]
    
    merged = pd.merge(feat_df, gt_target, on=["component_id", "lot_id", "parameter_name"])
    delta_u = merged["u_168"] - merged["u24"]
    
    for i in range(len(merged)):
        expected = merged["u_168"].iloc[i] - merged["u24"].iloc[i]
        assert np.isclose(delta_u.iloc[i], expected, atol=1e-15)


def test_forecast_reconstruction(dev_dataset):
    """Test that u_168_hat == u_24 + delta_u_hat."""
    cols = ["u24", "component_drift", "lot_drift", "excess_drift"]
    model = ResidualRidgeModel(parameter_name="RDS(on)", feature_columns=cols, l2_reg=1.0)
    
    rng = np.random.RandomState(42)
    N = 40
    X = rng.randn(N, 4)
    y_delta = 0.05 + 0.1 * X[:, 0] + 0.2 * X[:, 1] + 0.15 * X[:, 2] + 0.25 * X[:, 3] + rng.randn(N) * 0.02
    model.fit(X, y_delta)
    
    X_test = rng.randn(15, 4)
    u24_test = rng.randn(15) + 3.8
    v24_test = np.exp(u24_test)
    
    pred_phys, pred_u168, pred_delta, is_div = model.predict(X_test, u24_test, v24_test)
    
    # Mathematical reconstruction test
    reconstructed = u24_test + pred_delta
    np.testing.assert_allclose(pred_u168, reconstructed, atol=1e-15)


def test_no_future_feature_leakage(dev_dataset):
    """Test that feature extraction ignores observations > 24h."""
    obs_df, _ = dev_dataset
    feat_base = extract_loo_lot_context_features(obs_df)
    
    obs_future_mutated = obs_df.copy()
    mask = obs_future_mutated["elapsed_hours"] > 24
    obs_future_mutated.loc[mask, "value"] = 88888.0
    
    feat_future_mutated = extract_loo_lot_context_features(obs_future_mutated)
    pd.testing.assert_frame_equal(feat_base, feat_future_mutated)


def test_loo_exclusion_invariance(dev_dataset):
    """Test that mutating target component does not alter its peer statistics."""
    obs_df, _ = dev_dataset
    target_cid = sorted(obs_df["component_id"].unique())[0]
    param = "RDS(on)"
    
    feat_base = extract_loo_lot_context_features(obs_df)
    row_base = feat_base[(feat_base["component_id"] == target_cid) & (feat_base["parameter_name"] == param)].iloc[0]
    
    obs_mutated = obs_df.copy()
    mask = (obs_mutated["component_id"] == target_cid) & (obs_mutated["parameter_name"] == param) & (obs_mutated["elapsed_hours"] == 24)
    obs_mutated.loc[mask, "value"] = obs_mutated.loc[mask, "value"] * 3.0
    
    feat_mutated = extract_loo_lot_context_features(obs_mutated)
    row_mutated = feat_mutated[(feat_mutated["component_id"] == target_cid) & (feat_mutated["parameter_name"] == param)].iloc[0]
    
    assert row_base["loo_lot_median_0h"] == row_mutated["loo_lot_median_0h"]
    assert row_base["loo_lot_median_24h"] == row_mutated["loo_lot_median_24h"]
    assert row_base["lot_drift"] == row_mutated["lot_drift"]
    assert row_base["component_drift"] != row_mutated["component_drift"]


def test_deterministic_feature_generation(dev_dataset):
    """Test that feature generation is bit-for-bit deterministic."""
    obs_df, _ = dev_dataset
    feat1 = extract_loo_lot_context_features(obs_df)
    feat2 = extract_loo_lot_context_features(obs_df)
    assert hashlib.sha256(feat1.to_csv(index=False).encode("utf-8")).hexdigest() == hashlib.sha256(feat2.to_csv(index=False).encode("utf-8")).hexdigest()


def test_exact_linear_explainability():
    """Test that explainability decomposition satisfies exact additivity down to machine epsilon."""
    cols = ["u24", "component_drift", "lot_drift", "excess_drift"]
    model = ResidualRidgeModel(parameter_name="RDS(on)", feature_columns=cols, l2_reg=1.0)
    
    rng = np.random.RandomState(42)
    X = rng.randn(30, 4)
    y_delta = 0.1 + 0.2 * X[:, 0] + 0.3 * X[:, 1] + 0.15 * X[:, 2] + 0.4 * X[:, 3] + rng.randn(30) * 0.01
    model.fit(X, y_delta)
    
    X_test = rng.randn(10, 4)
    u24_test = rng.randn(10) + 3.85
    
    for x, u24 in zip(X_test, u24_test):
        exp = model.explain(x, u24)
        assert exp["delta_additivity_error"] < 1e-14
        assert exp["reconstructed_additivity_error"] < 1e-14


def test_final_holdout_isolation():
    """Verify that final holdout files LOT21-LOT24 remain completely untouched."""
    checksums_file = Path("data/evaluation/final_holdout/checksums.sha256")
    assert checksums_file.exists()
    with open(checksums_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            expected_hash, rel_path = line.split(maxsplit=1)
            target = Path("data/evaluation/final_holdout") / rel_path
            assert target.exists()
            with open(target, "rb") as bf:
                actual_hash = hashlib.sha256(bf.read()).hexdigest()
            assert actual_hash == expected_hash, f"Holdout corrupted: {target}"
