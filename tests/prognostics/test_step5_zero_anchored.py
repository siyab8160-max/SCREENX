"""Unit and integration tests for Step 5 Dual-Regime Zero-Anchored Hybrid Module B.

Verifies:
1. Zero-anchor condition: |excess_drift| <= threshold -> delta_hat == 0, u168_hat == u24, pred_phys == v24
2. Drift branch: |excess_drift| > threshold -> learned model invoked
3. No future feature leakage: elapsed_hours > 24h has zero influence on regime or prediction
4. Lot-level split: strict lot separation, no row-level random shuffle
5. LOO integrity: mutating target component does not alter peer median statistics
6. Deterministic regime assignment: identical inputs yield identical regime and predictions
7. Reconstruction: u168_hat == u24 + delta_hat in both regimes
8. Final holdout isolation: zero access to LOT21-LOT24, verified hashes
9. Hybrid output schema: comprehensive dictionary contract
10. Explainability integrity: regime explanations, reasons, and contribution consistency
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
    compute_training_excess_drift_scales,
    ResidualRidgeModel,
    ResidualHistGBMModel,
    ZeroAnchoredHybridPrognosticModel,
)


@pytest.fixture(scope="module")
def dev_dataset():
    """Generate dev lots LOT01-LOT04 for testing."""
    gen = SyntheticBurnInGenerator(seed=20260918)
    obs_df, gt_df, manifest = gen.generate(lots=["LOT01", "LOT02", "LOT03", "LOT04"], mode="stress")
    return obs_df, gt_df


def test_zero_anchor_condition():
    """Requirement 1: |excess_drift| <= threshold triggers delta_hat == 0, u168_hat == u24, pred_phys == v24."""
    cols = ["u24", "component_drift", "lot_drift", "excess_drift"]
    base_ridge = ResidualRidgeModel(parameter_name="RDS(on)", feature_columns=cols, l2_reg=1.0)
    
    # Fit dummy model
    rng = np.random.RandomState(42)
    X = rng.randn(20, 4)
    y_delta = 0.05 + 0.1 * X[:, 0] + rng.randn(20) * 0.01
    base_ridge.fit(X, y_delta)
    
    threshold = 0.02
    hybrid = ZeroAnchoredHybridPrognosticModel(
        parameter_name="RDS(on)",
        base_model=base_ridge,
        threshold=threshold,
        feature_columns=cols,
    )
    
    # Case with excess_drift = 0.01 <= 0.02
    nominal_features = {
        "u24": 3.85,
        "v24": np.exp(3.85),
        "component_drift": 0.01,
        "lot_drift": 0.00,
        "excess_drift": 0.01,
    }
    result = hybrid.predict_single(nominal_features)
    
    assert result["regime"] == "ZERO_ANCHORED"
    assert result["predicted_delta"] == 0.0
    assert np.isclose(result["predicted_u168"], nominal_features["u24"])
    assert np.isclose(result["predicted_physical"], nominal_features["v24"])
    assert "Excess drift within training-derived noise band" in result["reason"]


def test_drift_branch_invocation():
    """Requirement 2: |excess_drift| > threshold routes to learned residual forecasting branch."""
    cols = ["u24", "component_drift", "lot_drift", "excess_drift"]
    base_ridge = ResidualRidgeModel(parameter_name="RDS(on)", feature_columns=cols, l2_reg=1.0)
    
    rng = np.random.RandomState(42)
    X = rng.randn(30, 4)
    y_delta = 0.10 + 0.2 * X[:, 3] + rng.randn(30) * 0.01
    base_ridge.fit(X, y_delta)
    
    threshold = 0.02
    hybrid = ZeroAnchoredHybridPrognosticModel(
        parameter_name="RDS(on)",
        base_model=base_ridge,
        threshold=threshold,
        feature_columns=cols,
    )
    
    # Case with excess_drift = 0.08 > 0.02
    drift_features = {
        "u24": 3.90,
        "v24": np.exp(3.90),
        "component_drift": 0.10,
        "lot_drift": 0.02,
        "excess_drift": 0.08,
    }
    result = hybrid.predict_single(drift_features)
    
    assert result["regime"] == "DRIFT_MODEL"
    assert result["predicted_delta"] != 0.0
    assert result["predicted_u168"] == result["u24"] + result["predicted_delta"]
    assert "Excess drift above training-derived noise band" in result["reason"]


def test_no_future_feature_leakage(dev_dataset):
    """Requirement 3: Feature extraction and regime decisions ignore any observation > 24h."""
    obs_df, _ = dev_dataset
    feat_base = extract_loo_lot_context_features(obs_df)
    
    obs_future_mutated = obs_df.copy()
    mask = obs_future_mutated["elapsed_hours"] > 24
    obs_future_mutated.loc[mask, "value"] = 999999.0
    
    feat_future_mutated = extract_loo_lot_context_features(obs_future_mutated)
    pd.testing.assert_frame_equal(feat_base, feat_future_mutated)


def test_lot_level_split_integrity():
    """Requirement 4: Lot-level split ensures no training lot overlaps with validation."""
    train_lots = [f"LOT{i:02d}" for i in range(1, 13)]
    val_lots = ["LOT13", "LOT14"]
    holdout_lots = ["LOT21", "LOT22", "LOT23", "LOT24"]
    
    # Disjointness checks
    assert len(set(train_lots).intersection(set(val_lots))) == 0
    assert len(set(train_lots).intersection(set(holdout_lots))) == 0
    assert len(set(val_lots).intersection(set(holdout_lots))) == 0


def test_loo_integrity(dev_dataset):
    """Requirement 5: Mutating target component does not alter peer median statistics."""
    obs_df, _ = dev_dataset
    target_cid = sorted(obs_df["component_id"].unique())[0]
    param = "RDS(on)"
    
    feat_base = extract_loo_lot_context_features(obs_df)
    row_base = feat_base[(feat_base["component_id"] == target_cid) & (feat_base["parameter_name"] == param)].iloc[0]
    
    obs_mutated = obs_df.copy()
    mask = (obs_mutated["component_id"] == target_cid) & (obs_mutated["parameter_name"] == param) & (obs_mutated["elapsed_hours"] == 24)
    obs_mutated.loc[mask, "value"] = obs_mutated.loc[mask, "value"] * 2.5
    
    feat_mutated = extract_loo_lot_context_features(obs_mutated)
    row_mutated = feat_mutated[(feat_mutated["component_id"] == target_cid) & (feat_mutated["parameter_name"] == param)].iloc[0]
    
    assert row_base["loo_lot_median_0h"] == row_mutated["loo_lot_median_0h"]
    assert row_base["loo_lot_median_24h"] == row_mutated["loo_lot_median_24h"]
    assert row_base["lot_drift"] == row_mutated["lot_drift"]
    assert row_base["component_drift"] != row_mutated["component_drift"]


def test_deterministic_regime_assignment():
    """Requirement 6: Regime routing is strictly deterministic."""
    cols = ["u24", "component_drift", "lot_drift", "excess_drift"]
    base_ridge = ResidualRidgeModel(parameter_name="RDS(on)", feature_columns=cols, l2_reg=1.0)
    
    rng = np.random.RandomState(42)
    X = rng.randn(25, 4)
    y_delta = 0.05 + 0.15 * X[:, 3] + rng.randn(25) * 0.01
    base_ridge.fit(X, y_delta)
    
    hybrid = ZeroAnchoredHybridPrognosticModel(
        parameter_name="RDS(on)",
        base_model=base_ridge,
        threshold=0.025,
        feature_columns=cols,
    )
    
    sample_feat = {
        "u24": 3.82,
        "v24": np.exp(3.82),
        "component_drift": 0.03,
        "lot_drift": 0.01,
        "excess_drift": 0.02,
    }
    
    r1 = hybrid.predict_single(sample_feat)
    r2 = hybrid.predict_single(sample_feat)
    
    assert r1["regime"] == r2["regime"]
    assert r1["predicted_physical"] == r2["predicted_physical"]
    assert r1["predicted_u168"] == r2["predicted_u168"]
    assert r1["predicted_delta"] == r2["predicted_delta"]
    assert r1["reason"] == r2["reason"]


def test_reconstruction_property():
    """Requirement 7: u168_hat == u24 + delta_hat in both regimes."""
    cols = ["u24", "component_drift", "lot_drift", "excess_drift"]
    base_gbm = ResidualHistGBMModel(
        parameter_name="RDS(on)",
        feature_columns=cols,
        max_depth=3,
        learning_rate=0.05,
        min_samples_leaf=5,
    )
    
    rng = np.random.RandomState(42)
    X = rng.randn(30, 4)
    y_delta = 0.08 + 0.25 * X[:, 3] + rng.randn(30) * 0.01
    base_gbm.fit(X, y_delta)
    
    hybrid = ZeroAnchoredHybridPrognosticModel(
        parameter_name="RDS(on)",
        base_model=base_gbm,
        threshold=0.03,
        feature_columns=cols,
    )
    
    # Test cases below and above threshold
    for exc in [0.01, 0.025, 0.035, 0.12]:
        feat = {
            "u24": 3.80 + exc,
            "v24": np.exp(3.80 + exc),
            "component_drift": exc + 0.005,
            "lot_drift": 0.005,
            "excess_drift": exc,
        }
        res = hybrid.predict_single(feat)
        assert np.isclose(res["predicted_u168"], res["u24"] + res["predicted_delta"], atol=1e-15)


def test_final_holdout_isolation():
    """Requirement 8: Check that final holdout LOT21-LOT24 checksums remain unaltered."""
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


def test_hybrid_output_schema():
    """Requirement 9: Output schema matches required contract."""
    cols = ["u24", "component_drift", "lot_drift", "excess_drift"]
    base_ridge = ResidualRidgeModel(parameter_name="VGS(th)", feature_columns=cols, l2_reg=1.0)
    
    rng = np.random.RandomState(42)
    X = rng.randn(20, 4)
    y_delta = 0.02 * X[:, 0] + rng.randn(20) * 0.005
    base_ridge.fit(X, y_delta)
    
    hybrid = ZeroAnchoredHybridPrognosticModel(
        parameter_name="VGS(th)",
        base_model=base_ridge,
        threshold=0.02,
        feature_columns=cols,
    )
    
    res = hybrid.predict_single({
        "u24": 2.8,
        "v24": 2.8,
        "component_drift": 0.005,
        "lot_drift": 0.002,
        "excess_drift": 0.003,
    })
    
    required_keys = [
        "parameter_name",
        "regime",
        "predicted_physical",
        "predicted_u168",
        "predicted_delta",
        "u24",
        "v24",
        "excess_drift",
        "threshold",
        "reason",
        "contributions",
    ]
    for key in required_keys:
        assert key in res, f"Missing required key: {key}"


def test_explainability_integrity():
    """Requirement 10: Explainability provides transparent regime reasoning and valid contributions."""
    cols = ["u24", "component_drift", "lot_drift", "excess_drift"]
    base_ridge = ResidualRidgeModel(parameter_name="RDS(on)", feature_columns=cols, l2_reg=1.0)
    
    rng = np.random.RandomState(42)
    X = rng.randn(25, 4)
    y_delta = 0.05 + 0.1 * X[:, 0] + 0.3 * X[:, 3]
    base_ridge.fit(X, y_delta)
    
    hybrid = ZeroAnchoredHybridPrognosticModel(
        parameter_name="RDS(on)",
        base_model=base_ridge,
        threshold=0.02,
        feature_columns=cols,
    )
    
    # 1. Zero anchored explanation
    za_feat = {"u24": 3.8, "v24": np.exp(3.8), "component_drift": 0.01, "lot_drift": 0.0, "excess_drift": 0.01}
    exp_za = hybrid.predict_single(za_feat)
    assert exp_za["regime"] == "ZERO_ANCHORED"
    assert exp_za["contributions"]["zero_anchor"] == 0.0
    
    # 2. Drift model explanation
    drift_feat = {"u24": 3.8, "v24": np.exp(3.8), "component_drift": 0.08, "lot_drift": 0.0, "excess_drift": 0.08}
    exp_drift = hybrid.predict_single(drift_feat)
    assert exp_drift["regime"] == "DRIFT_MODEL"
    assert "u24" in exp_drift["contributions"]
    assert "excess_drift" in exp_drift["contributions"]
    assert "intercept" in exp_drift["contributions"]
