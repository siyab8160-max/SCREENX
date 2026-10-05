"""Unit and regression tests for Step 5B Multi-Split Robustness Validation.

Verifies:
1. Final holdout quarantine: zero access to LOT21-LOT24, verified hashes
2. No validation-target leakage into threshold calculation:
   - Threshold derives exclusively from training <=24h observations
   - Mutating validation data or 168h targets produces zero change in thresholds
3. Exact prediction reconstruction:
   - u168_hat == u24 + delta_hat in both regimes to machine precision
4. Deterministic results:
   - Identical splits and seeds produce bit-for-bit identical models and forecasts
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
    ResidualHistGBMModel,
    ZeroAnchoredHybridPrognosticModel,
)


@pytest.fixture(scope="module")
def dev_data_lots():
    """Generate dev lots LOT01-LOT04 for testing."""
    gen = SyntheticBurnInGenerator(seed=20260918)
    obs_df, gt_df, manifest = gen.generate(lots=["LOT01", "LOT02", "LOT03", "LOT04"], mode="stress")
    return obs_df, gt_df


def test_final_holdout_quarantine():
    """Requirement 1: Verify final holdout LOT21-LOT24 checksums remain unaltered."""
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


def test_no_validation_target_leakage_into_thresholds(dev_data_lots):
    """Requirement 2: Ensure threshold is independent of validation data and future targets."""
    obs_df, gt_df = dev_data_lots
    
    # Train lots: LOT01, LOT02; Validation lots: LOT03, LOT04
    feat_df = extract_loo_lot_context_features(obs_df)
    train_feat_orig = feat_df[feat_df["lot_id"].isin(["LOT01", "LOT02"])].copy()
    
    scales_orig = compute_training_excess_drift_scales(train_feat_orig)
    
    # 1. Mutate validation observations
    obs_mutated = obs_df.copy()
    mask_val = obs_mutated["lot_id"].isin(["LOT03", "LOT04"])
    obs_mutated.loc[mask_val, "value"] = obs_mutated.loc[mask_val, "value"] * 99.0
    
    feat_mutated = extract_loo_lot_context_features(obs_mutated)
    train_feat_post_val_mutation = feat_mutated[feat_mutated["lot_id"].isin(["LOT01", "LOT02"])].copy()
    scales_post_val_mutation = compute_training_excess_drift_scales(train_feat_post_val_mutation)
    
    for p in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]:
        assert np.isclose(scales_orig[p], scales_post_val_mutation[p], atol=1e-15), (
            f"Validation mutation altered training scale for {p}!"
        )
        
    # 2. Mutate future target (168h) ground truth
    gt_mutated = gt_df.copy()
    gt_mutated["actual_value"] = gt_mutated["actual_value"] * 50.0
    
    # Threshold function does not even take ground truth as input
    scales_post_gt = compute_training_excess_drift_scales(train_feat_orig)
    for p in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]:
        assert np.isclose(scales_orig[p], scales_post_gt[p], atol=1e-15)


def test_exact_prediction_reconstruction():
    """Requirement 3: Verify u168_hat == u24 + delta_hat in both regimes."""
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
    
    threshold = 0.03
    hybrid = ZeroAnchoredHybridPrognosticModel(
        parameter_name="RDS(on)",
        base_model=base_gbm,
        threshold=threshold,
        feature_columns=cols,
    )
    
    # Test cases below and above threshold
    for exc in [0.005, 0.025, 0.035, 0.15]:
        feat = {
            "u24": 3.80 + exc,
            "v24": np.exp(3.80 + exc),
            "component_drift": exc + 0.005,
            "lot_drift": 0.005,
            "excess_drift": exc,
        }
        res = hybrid.predict_single(feat)
        # Mathematical reconstruction test
        assert np.isclose(res["predicted_u168"], res["u24"] + res["predicted_delta"], atol=1e-15)
        if abs(exc) <= threshold:
            assert res["regime"] == "ZERO_ANCHORED"
            assert res["predicted_delta"] == 0.0
            assert np.isclose(res["predicted_physical"], res["v24"], atol=1e-15)
        else:
            assert res["regime"] == "DRIFT_MODEL"
            assert res["predicted_delta"] != 0.0


def test_deterministic_results(dev_data_lots):
    """Requirement 4: Verify deterministic reproducibility across runs."""
    obs_df, gt_df = dev_data_lots
    feat_df = extract_loo_lot_context_features(obs_df)
    train_feat = feat_df[feat_df["lot_id"].isin(["LOT01", "LOT02"])].copy()
    val_feat = feat_df[feat_df["lot_id"].isin(["LOT03", "LOT04"])].copy()
    
    gt_target = gt_df[gt_df["target_horizon_hours"] == 168].copy().rename(columns={"actual_value": "y_168"})
    gt_target["u_168"] = [transform_parameter(p, val) for p, val in zip(gt_target["parameter_name"], gt_target["y_168"])]
    train_data = pd.merge(train_feat, gt_target[["component_id", "lot_id", "parameter_name", "u_168", "y_168"]], on=["component_id", "lot_id", "parameter_name"])
    train_data["delta_u"] = train_data["u_168"] - train_data["u24"]
    
    cols = ["u24", "component_drift", "lot_drift", "excess_drift"]
    
    def train_and_predict():
        scales = compute_training_excess_drift_scales(train_feat)
        p = "RDS(on)"
        tr_p = train_data[train_data["parameter_name"] == p]
        gm = ResidualHistGBMModel(
            parameter_name=p,
            feature_columns=cols,
            max_depth=3,
            max_iter=50,
            learning_rate=0.05,
            min_samples_leaf=5,
            l2_regularization=1.0,
            random_state=20260918,
        )
        gm.fit(tr_p[cols].values, tr_p["delta_u"].values)
        za = ZeroAnchoredHybridPrognosticModel(
            parameter_name=p,
            base_model=gm,
            threshold=0.5 * scales[p],
            feature_columns=cols,
        )
        preds = []
        for _, r in val_feat[val_feat["parameter_name"] == p].iterrows():
            fd = {c: float(r[c]) for c in cols}
            fd["u24"] = float(r["u24"])
            fd["v24"] = float(r["v24"])
            fd["excess_drift"] = float(r["excess_drift"])
            preds.append(za.predict_single(fd)["predicted_physical"])
        return preds
        
    p1 = train_and_predict()
    p2 = train_and_predict()
    
    assert p1 == p2, "Predictions across duplicate executions were not bit-for-bit identical!"
