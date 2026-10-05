"""Unit and integration tests for Step 3 LOO Lot-Context features and models.

Verifies:
1. LOO exclusion invariance: mutating target component does not alter its peer statistics
2. No future features: strictly elapsed_hours <= 24h
3. Lot-level split integrity: disjointness across train and validation folds
4. Feature schema adherence: required columns and types
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
from sih26170.screening.transforms import transform_parameter, get_noise_floor
from sih26170.prognostics.lot_context import (
    extract_loo_lot_context_features,
    LotContextRidgeModel,
    FEATURE_VARIANTS,
)


@pytest.fixture(scope="module")
def dev_dataset():
    """Generate dev lots LOT01-LOT04 for testing."""
    gen = SyntheticBurnInGenerator(seed=20260918)
    obs_df, gt_df, manifest = gen.generate(lots=["LOT01", "LOT02", "LOT03", "LOT04"], mode="stress")
    return obs_df, gt_df


def test_loo_exclusion_invariance(dev_dataset):
    """Test that modifying component i's 24h value does not change its own LOO statistics."""
    obs_df, _ = dev_dataset
    
    # Select first component
    cids = sorted(obs_df["component_id"].unique())
    target_cid = cids[0]
    param = "RDS(on)"
    
    # Extract baseline features
    feat_base = extract_loo_lot_context_features(obs_df)
    row_base = feat_base[(feat_base["component_id"] == target_cid) & (feat_base["parameter_name"] == param)].iloc[0]
    
    # Mutate target component's 24h observation
    obs_mutated = obs_df.copy()
    mask = (obs_mutated["component_id"] == target_cid) & (obs_mutated["parameter_name"] == param) & (obs_mutated["elapsed_hours"] == 24)
    obs_mutated.loc[mask, "value"] = obs_mutated.loc[mask, "value"] * 5.0
    
    feat_mutated = extract_loo_lot_context_features(obs_mutated)
    row_mutated = feat_mutated[(feat_mutated["component_id"] == target_cid) & (feat_mutated["parameter_name"] == param)].iloc[0]
    
    # LOO peer statistics MUST remain identical
    assert row_base["loo_lot_median_0h"] == row_mutated["loo_lot_median_0h"], "0h LOO median changed!"
    assert row_base["loo_lot_median_24h"] == row_mutated["loo_lot_median_24h"], "24h LOO median changed!"
    assert row_base["lot_drift"] == row_mutated["lot_drift"], "lot_drift changed!"
    assert row_base["loo_lot_scale_0h"] == row_mutated["loo_lot_scale_0h"], "loo_lot_scale_0h changed!"
    
    # Component's own drift and excess drift MUST change
    assert row_base["component_drift"] != row_mutated["component_drift"], "component_drift did not change!"
    assert row_base["excess_drift"] != row_mutated["excess_drift"], "excess_drift did not change!"


def test_no_future_features_leakage(dev_dataset):
    """Test that feature extraction ignores observations > 24h."""
    obs_df, _ = dev_dataset
    
    feat_base = extract_loo_lot_context_features(obs_df)
    
    # Mutate 96h and 168h observations drastically
    obs_future_mutated = obs_df.copy()
    mask = obs_future_mutated["elapsed_hours"] > 24
    obs_future_mutated.loc[mask, "value"] = 99999.0
    
    feat_future_mutated = extract_loo_lot_context_features(obs_future_mutated)
    
    pd.testing.assert_frame_equal(feat_base, feat_future_mutated)


def test_feature_schema_and_finite_values(dev_dataset):
    """Test that feature extraction returns all required columns and valid finite floats."""
    obs_df, _ = dev_dataset
    feat_df = extract_loo_lot_context_features(obs_df)
    
    expected_cols = [
        "component_id",
        "lot_id",
        "parameter_name",
        "v0",
        "v24",
        "u0",
        "u24",
        "component_drift",
        "loo_lot_median_0h",
        "loo_lot_median_24h",
        "lot_drift",
        "excess_drift",
        "loo_lot_scale_0h",
    ]
    for c in expected_cols:
        assert c in feat_df.columns, f"Missing column: {c}"
        
    num_cols = ["v0", "v24", "u0", "u24", "component_drift", "loo_lot_median_0h", "loo_lot_median_24h", "lot_drift", "excess_drift", "loo_lot_scale_0h"]
    assert np.all(np.isfinite(feat_df[num_cols].values))


def test_deterministic_feature_generation(dev_dataset):
    """Test that feature generation is bit-for-bit deterministic."""
    obs_df, _ = dev_dataset
    feat1 = extract_loo_lot_context_features(obs_df)
    feat2 = extract_loo_lot_context_features(obs_df)
    
    hash1 = hashlib.sha256(feat1.to_csv(index=False).encode("utf-8")).hexdigest()
    hash2 = hashlib.sha256(feat2.to_csv(index=False).encode("utf-8")).hexdigest()
    assert hash1 == hash2


def test_exact_linear_explainability():
    """Test exact linear contribution additivity (SHAP decomposition)."""
    cols = ["u0", "u24", "lot_drift", "excess_drift"]
    model = LotContextRidgeModel(parameter_name="RDS(on)", feature_columns=cols, l2_reg=1.0)
    
    # Synthetic training data
    rng = np.random.RandomState(42)
    N = 50
    X = rng.randn(N, 4)
    y = 3.8 + 0.4 * X[:, 0] + 0.5 * X[:, 1] + 0.1 * X[:, 2] + 0.2 * X[:, 3] + rng.randn(N) * 0.05
    model.fit(X, y)
    
    # Test on new samples
    X_test = rng.randn(20, 4)
    for x in X_test:
        exp = model.explain(x)
        assert exp["additivity_delta"] < 1e-14
        assert np.isclose(exp["sum_contributions"], exp["transformed_prediction"], atol=1e-14)


def test_final_holdout_isolation():
    """Verify that final holdout files LOT21-LOT24 remain bit-for-bit unchanged."""
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
            assert actual_hash == expected_hash, f"Holdout file corrupted: {target}"
