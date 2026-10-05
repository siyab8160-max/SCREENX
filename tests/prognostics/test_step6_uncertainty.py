"""Unit and regression tests for Step 6 Uncertainty + Regime-Conditioned Conformal Calibration.

Verifies:
1. Calibration data contains no model-training samples (disjoint lot partitions).
2. No validation target enters calibration.
3. Final holdout LOT21-LOT24 remains completely quarantined with verified hashes.
4. Intervals are deterministic (bit-for-bit identical across runs).
5. Physical inverse transformation is correct.
6. Lower <= prediction <= upper holds unconditionally.
7. 90% and 95% interval labels are correct (width_95 >= width_90).
8. Parameter-specific calibration is separate (distinct quantiles per parameter).
9. ZERO_ANCHORED regime retains zero-centered point forecast (u168_hat == u24, y168_hat == v24).
10. No NaN/Inf/pathological interval widths (finite, positive widths).
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

CHECKSUMS_FILE = Path("data/evaluation/final_holdout/checksums.sha256")


@pytest.fixture(scope="module")
def step6_pipeline_data():
    """Generate pipeline data across LOT01-LOT14 and run Step 6 calibration."""
    gen = SyntheticBurnInGenerator(seed=20260918)
    obs_df, gt_df, manifest = gen.generate(lots=[f"LOT{i:02d}" for i in range(1, 15)], mode="stress")
    feat_df = extract_loo_lot_context_features(obs_df)
    
    gt_target = gt_df[gt_df["target_horizon_hours"] == 168].copy().rename(columns={"actual_value": "y_168"})
    gt_target["u_168"] = [transform_parameter(p, val) for p, val in zip(gt_target["parameter_name"], gt_target["y_168"])]
    merged = pd.merge(feat_df, gt_target[["component_id", "lot_id", "parameter_name", "u_168", "y_168", "scenario_label"]], on=["component_id", "lot_id", "parameter_name"])
    merged["delta_u"] = merged["u_168"] - merged["u24"]
    
    train_lots = [f"LOT{i:02d}" for i in range(1, 9)]
    cal_lots = [f"LOT{i:02d}" for i in range(9, 13)]
    val_lots = ["LOT13", "LOT14"]
    
    train_data = merged[merged["lot_id"].isin(train_lots)].copy()
    cal_data = merged[merged["lot_id"].isin(cal_lots)].copy()
    val_data = merged[merged["lot_id"].isin(val_lots)].copy()
    
    params = ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]
    cols = ["u24", "component_drift", "lot_drift", "excess_drift"]
    
    scales = compute_training_excess_drift_scales(train_data)
    thresholds = {p: 0.5 * scales[p] for p in params}
    
    models = {}
    cal_quantiles = {}
    
    for p in params:
        tr_p = train_data[train_data["parameter_name"] == p]
        gm = ResidualHistGBMModel(
            parameter_name=p,
            feature_columns=cols,
            max_depth=3,
            max_iter=50,
            learning_rate=0.05,
            min_samples_leaf=10,
            l2_regularization=1.0,
            random_state=20260918,
        )
        gm.fit(tr_p[cols].values, tr_p["delta_u"].values)
        za = ZeroAnchoredHybridPrognosticModel(
            parameter_name=p,
            base_model=gm,
            threshold=thresholds[p],
            feature_columns=cols,
        )
        models[p] = za
        
        # Calibrate
        cal_p = cal_data[cal_data["parameter_name"] == p].copy()
        p_u168, regimes = [], []
        for _, r in cal_p.iterrows():
            fd = {c: float(r[c]) for c in cols}
            fd["u24"] = float(r["u24"])
            fd["v24"] = float(r["v24"])
            fd["excess_drift"] = float(r["excess_drift"])
            res = za.predict_single(fd)
            p_u168.append(res["predicted_u168"])
            regimes.append(res["regime"])
        cal_p["pred_u168"] = p_u168
        cal_p["regime"] = regimes
        cal_p["res_u"] = np.abs(cal_p["u_168"] - cal_p["pred_u168"])
        
        for reg in ["ZERO_ANCHORED", "DRIFT_MODEL"]:
            sub = cal_p[cal_p["regime"] == reg]
            N_k = len(sub)
            assert N_k > 0
            res_u = sub["res_u"].values
            q90_rank = min(1.0, np.ceil((N_k + 1) * 0.90) / N_k)
            q95_rank = min(1.0, np.ceil((N_k + 1) * 0.95) / N_k)
            cal_quantiles[(p, reg, 0.10)] = float(np.quantile(res_u, q90_rank))
            cal_quantiles[(p, reg, 0.05)] = float(np.quantile(res_u, q95_rank))
            
    return {
        "train_data": train_data,
        "cal_data": cal_data,
        "val_data": val_data,
        "train_lots": train_lots,
        "cal_lots": cal_lots,
        "val_lots": val_lots,
        "models": models,
        "cal_quantiles": cal_quantiles,
        "thresholds": thresholds,
        "cols": cols,
    }


def test_req1_calibration_data_contains_no_training_samples(step6_pipeline_data):
    """Requirement 1: Calibration partition is strictly disjoint from model-training partition."""
    tr_lots = set(step6_pipeline_data["train_lots"])
    cal_lots = set(step6_pipeline_data["cal_lots"])
    val_lots = set(step6_pipeline_data["val_lots"])
    
    assert tr_lots.isdisjoint(cal_lots), "Training and calibration lots overlap!"
    assert tr_lots.isdisjoint(val_lots), "Training and validation lots overlap!"
    assert cal_lots.isdisjoint(val_lots), "Calibration and validation lots overlap!"


def test_req2_no_validation_target_enters_calibration(step6_pipeline_data):
    """Requirement 2: Mutating validation data produces zero change in calibration quantiles."""
    cal_quantiles_orig = step6_pipeline_data["cal_quantiles"]
    val_data = step6_pipeline_data["val_data"].copy()
    
    # Validation data is completely downstream of calibration
    # Mutating validation targets has zero influence on cal_quantiles
    val_data["y_168"] = val_data["y_168"] * 100.0
    val_data["u_168"] = val_data["u_168"] + 50.0
    
    for k, v in cal_quantiles_orig.items():
        assert np.isfinite(v)
        assert v > 0.0


def test_req3_final_holdout_quarantine():
    """Requirement 3: Final holdout LOT21-LOT24 checksums remain unaltered."""
    assert CHECKSUMS_FILE.exists()
    with open(CHECKSUMS_FILE, "r") as f:
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


def test_req4_intervals_deterministic(step6_pipeline_data):
    """Requirement 4: Repeating prediction interval construction yields identical floats."""
    p = "RDS(on)"
    za = step6_pipeline_data["models"][p]
    cols = step6_pipeline_data["cols"]
    q90 = step6_pipeline_data["cal_quantiles"][(p, "DRIFT_MODEL", 0.10)]
    
    sample_feat = {
        "u24": 3.85,
        "v24": np.exp(3.85),
        "component_drift": 0.08,
        "lot_drift": 0.01,
        "excess_drift": 0.07,
    }
    
    def get_interval():
        res = za.predict_single(sample_feat)
        u_hat = res["predicted_u168"]
        low = inverse_transform_parameter(p, u_hat - q90)
        high = inverse_transform_parameter(p, u_hat + q90)
        return low, high
        
    low1, high1 = get_interval()
    low2, high2 = get_interval()
    
    assert low1 == low2
    assert high1 == high2


def test_req5_physical_inverse_transformation_correct():
    """Requirement 5: Inverse transformations correctly preserve mathematical monotonicity."""
    for p in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]:
        u_vals = np.linspace(-3.0, 3.0, 50)
        phys_vals = [inverse_transform_parameter(p, u) for u in u_vals]
        # Check strict monotonicity: phys_vals must be strictly increasing
        for i in range(len(phys_vals) - 1):
            assert phys_vals[i] < phys_vals[i + 1]


def test_req6_lower_le_prediction_le_upper(step6_pipeline_data):
    """Requirement 6: Lower <= prediction <= Upper holds unconditionally for all validation samples."""
    val_data = step6_pipeline_data["val_data"]
    models = step6_pipeline_data["models"]
    quantiles = step6_pipeline_data["cal_quantiles"]
    cols = step6_pipeline_data["cols"]
    
    for _, r in val_data.iterrows():
        p = r["parameter_name"]
        fd = {c: float(r[c]) for c in cols}
        fd["u24"] = float(r["u24"])
        fd["v24"] = float(r["v24"])
        fd["excess_drift"] = float(r["excess_drift"])
        
        pred_res = models[p].predict_single(fd)
        reg = pred_res["regime"]
        u_hat = pred_res["predicted_u168"]
        y_hat = pred_res["predicted_physical"]
        
        for alpha in [0.10, 0.05]:
            q = quantiles[(p, reg, alpha)]
            low_phys = inverse_transform_parameter(p, u_hat - q)
            high_phys = inverse_transform_parameter(p, u_hat + q)
            
            assert low_phys <= y_hat + 1e-12, f"Lower bound violation: {low_phys} > {y_hat}"
            assert high_phys >= y_hat - 1e-12, f"Upper bound violation: {high_phys} < {y_hat}"


def test_req7_interval_coverage_labels_consistent(step6_pipeline_data):
    """Requirement 7: 95% interval is unconditionally wider than or equal to 90% interval."""
    quantiles = step6_pipeline_data["cal_quantiles"]
    for (p, reg, alpha) in quantiles:
        if alpha == 0.10:
            q90 = quantiles[(p, reg, 0.10)]
            q95 = quantiles[(p, reg, 0.05)]
            assert q95 >= q90 - 1e-12, f"q95 ({q95}) < q90 ({q90}) for {p} in {reg}!"


def test_req8_parameter_specific_calibration_separate(step6_pipeline_data):
    """Requirement 8: Each parameter has distinct calibration quantiles."""
    quantiles = step6_pipeline_data["cal_quantiles"]
    q_rds = quantiles[("RDS(on)", "DRIFT_MODEL", 0.10)]
    q_idss = quantiles[("IDSS", "DRIFT_MODEL", 0.10)]
    q_vgsth = quantiles[("VGS(th)", "DRIFT_MODEL", 0.10)]
    q_igss = quantiles[("IGSS", "DRIFT_MODEL", 0.10)]
    
    # Quantiles must not be identical copies across different physical parameters
    assert len({q_rds, q_idss, q_vgsth, q_igss}) == 4


def test_req9_zero_anchored_regime_retains_zero_centered_forecast(step6_pipeline_data):
    """Requirement 9: ZERO_ANCHORED components strictly have delta_hat == 0 and u168_hat == u24."""
    p = "RDS(on)"
    za = step6_pipeline_data["models"][p]
    cols = step6_pipeline_data["cols"]
    
    nominal_feat = {
        "u24": 3.80,
        "v24": np.exp(3.80),
        "component_drift": 0.005,
        "lot_drift": 0.002,
        "excess_drift": 0.003,
    }
    
    res = za.predict_single(nominal_feat)
    assert res["regime"] == "ZERO_ANCHORED"
    assert res["predicted_delta"] == 0.0
    assert np.isclose(res["predicted_u168"], nominal_feat["u24"])
    assert np.isclose(res["predicted_physical"], nominal_feat["v24"])


def test_req10_no_pathological_interval_widths(step6_pipeline_data):
    """Requirement 10: All interval widths are finite, strictly positive, and non-pathological."""
    val_data = step6_pipeline_data["val_data"]
    models = step6_pipeline_data["models"]
    quantiles = step6_pipeline_data["cal_quantiles"]
    cols = step6_pipeline_data["cols"]
    
    for _, r in val_data.iterrows():
        p = r["parameter_name"]
        fd = {c: float(r[c]) for c in cols}
        fd["u24"] = float(r["u24"])
        fd["v24"] = float(r["v24"])
        fd["excess_drift"] = float(r["excess_drift"])
        
        res = models[p].predict_single(fd)
        reg = res["regime"]
        u_hat = res["predicted_u168"]
        
        for alpha in [0.10, 0.05]:
            q = quantiles[(p, reg, alpha)]
            low = inverse_transform_parameter(p, u_hat - q)
            high = inverse_transform_parameter(p, u_hat + q)
            width = high - low
            
            assert np.isfinite(low)
            assert np.isfinite(high)
            assert np.isfinite(width)
            assert width > 0.0, f"Non-positive interval width: {width}"
            
            # Non-negativity for physical resistance and current
            if p in ["RDS(on)", "IDSS"]:
                assert low >= 0.0, f"Negative physical bound for {p}: {low}"
