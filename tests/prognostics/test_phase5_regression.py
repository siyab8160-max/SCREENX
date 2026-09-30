"""Comprehensive Unit and Integration Tests for Phase 5 Module B Predictive Regression.

Verifies the 12 required test dimensions authorized in docs/PHASE_5_MODULE_B_REGRESSION_SPEC.md:
1. Feature contract: strictly [Value_0h, Value_24h]
2. Transformation correctness across all 4 parameters
3. Signed IGSS semantics (never abs, never clipped)
4. Train/test lot separation (strict LOLO isolation)
5. Preprocessing fit only on training data
6. No future checkpoint access (as-of invariance)
7. No ground-truth or scenario label access
8. Deterministic reproducibility
9. Finite prediction rate and interval consistency
10. Divergence detection and deterministic fallback
11. Parameter-decoupled one-model-per-parameter topology
12. Baseline comparison interface compatibility
"""

import math
import numpy as np
import pandas as pd
import pytest

from sih26170.prognostics.schema import PrognosticInput, PrognosticForecast
from sih26170.prognostics.baselines import CarryForwardModel, TwoPointLinearModel
from sih26170.prognostics.regression_models import (
    BaseSupervisedRegressionModel,
    RidgeRegressionPrognosticModel,
    HuberRegressionPrognosticModel,
    ParameterDecoupledRegressionPipeline,
)
from sih26170.screening.transforms import (
    transform_parameter,
    inverse_transform_parameter,
    IGSS_SCALE_NA,
)
from sih26170.prognostics.validation import (
    build_prognostic_input,
    assert_no_ground_truth_leakage,
)
from sih26170.prognostics.phase5_lolo_evaluator import compute_metrics_for_predictions


@pytest.fixture
def synthetic_training_population() -> dict:
    """Fixture providing synthetic training data for 4 parameters across 3 lots."""
    rng = np.random.RandomState(42)
    n_per_lot = 20
    lots = ["LOT_CAL_001", "LOT_CAL_002", "LOT_CAL_003"]
    data = {}

    for param, unit, base in [
        ("IDSS", "uA", 0.5),
        ("VGS(th)", "V", 3.2),
        ("RDS(on)", "mOhm", 42.0),
        ("IGSS", "nA", -1.5),  # Intentionally negative to test signed behavior
    ]:
        v0_list, v24_list, v168_list = [], [], []
        lot_labels = []
        comp_ids = []

        for lot in lots:
            for c in range(n_per_lot):
                cid = f"{lot}_C{c+1:03d}"
                comp_ids.append(cid)
                lot_labels.append(lot)
                noise0 = rng.normal(0, 0.05 * abs(base))
                noise24 = rng.normal(0, 0.05 * abs(base))
                drift = rng.normal(0.02 * abs(base), 0.01 * abs(base))

                v0 = base + noise0
                v24 = v0 + (drift * 0.2) + noise24
                v168 = v0 + drift + rng.normal(0, 0.03 * abs(base))

                v0_list.append(v0)
                v24_list.append(v24)
                v168_list.append(v168)

        X = np.column_stack([v0_list, v24_list])
        y = np.array(v168_list)
        data[param] = {
            "X": X,
            "y": y,
            "lots": lot_labels,
            "comp_ids": comp_ids,
            "unit": unit,
        }
    return data


# ==============================================================================
# DIMENSION 1: FEATURE CONTRACT
# ==============================================================================

def test_feature_contract_strict_shape_and_inputs(synthetic_training_population):
    """Model must strictly accept (N, 2) features and reject invalid shapes."""
    param = "IDSS"
    d = synthetic_training_population[param]
    model = RidgeRegressionPrognosticModel(parameter_name=param, unit=d["unit"])

    # Valid (N, 2) fits cleanly
    model.fit(d["X"], d["y"])
    assert model.is_fitted

    # Invalid feature dimensions must raise ValueError
    with pytest.raises(ValueError, match=r"X must be of shape \(N, 2\)"):
        model.fit(np.column_stack([d["X"], d["y"]]), d["y"])  # (N, 3)

    with pytest.raises(ValueError, match=r"X must be of shape \(N, 2\)"):
        model.fit(d["X"][:, 0:1], d["y"])  # (N, 1)

    with pytest.raises(ValueError, match=r"X must be of shape \(N, 2\)"):
        model.fit(d["X"].ravel(), d["y"])  # 1D


# ==============================================================================
# DIMENSION 2: TRANSFORMATION CORRECTNESS
# ==============================================================================

def test_transformation_correctness_all_parameters():
    """Verify coordinate transforms match specification for all 4 parameters."""
    # IDSS: positive log u = ln(y)
    idss_val = 0.85
    u_idss = transform_parameter("IDSS", idss_val)
    assert math.isclose(u_idss, math.log(idss_val), rel_tol=1e-9)
    assert math.isclose(inverse_transform_parameter("IDSS", u_idss), idss_val, rel_tol=1e-9)

    # RDS(on): positive log u = ln(y)
    rds_val = 43.5
    u_rds = transform_parameter("RDS(on)", rds_val)
    assert math.isclose(u_rds, math.log(rds_val), rel_tol=1e-9)
    assert math.isclose(inverse_transform_parameter("RDS(on)", u_rds), rds_val, rel_tol=1e-9)

    # VGS(th): identity u = y
    vgs_val = 3.42
    u_vgs = transform_parameter("VGS(th)", vgs_val)
    assert math.isclose(u_vgs, vgs_val, rel_tol=1e-9)
    assert math.isclose(inverse_transform_parameter("VGS(th)", u_vgs), vgs_val, rel_tol=1e-9)

    # IGSS: signed asinh u = asinh(y / 1.0 nA)
    igss_val = 2.75
    u_igss = transform_parameter("IGSS", igss_val)
    expected_u = math.asinh(igss_val / IGSS_SCALE_NA)
    assert math.isclose(u_igss, expected_u, rel_tol=1e-9)
    assert math.isclose(inverse_transform_parameter("IGSS", u_igss), igss_val, rel_tol=1e-9)


# ==============================================================================
# DIMENSION 3: SIGNED IGSS SEMANTICS (NEVER ABS, NEVER CLIPPED)
# ==============================================================================

def test_signed_igss_semantics():
    """IGSS must preserve negative signs, must NEVER use abs(), and NEVER clip to +-100 nA."""
    neg_igss = -4.82
    u_neg = transform_parameter("IGSS", neg_igss)
    assert u_neg < 0.0, "Transformed negative IGSS must remain strictly negative"

    inv_neg = inverse_transform_parameter("IGSS", u_neg)
    assert math.isclose(inv_neg, neg_igss, rel_tol=1e-9)
    assert inv_neg < 0.0, "Inverted negative IGSS must preserve negative sign exactly"

    # Anti-symmetry: u(-y) == -u(y)
    pos_igss = 4.82
    u_pos = transform_parameter("IGSS", pos_igss)
    assert math.isclose(u_neg, -u_pos, rel_tol=1e-9)

    # Extreme value test: no clipping to +-100 nA
    large_igss = -150.0  # Beyond +-100 nA
    u_large = transform_parameter("IGSS", large_igss)
    inv_large = inverse_transform_parameter("IGSS", u_large)
    assert math.isclose(inv_large, -150.0, rel_tol=1e-9), "Extreme IGSS must not be cosmetically clipped"


# ==============================================================================
# DIMENSION 4: TRAIN/TEST LOT SEPARATION (LOLO ISOLATION)
# ==============================================================================

def test_train_test_lot_separation(synthetic_training_population):
    """Held-out lot must be strictly excluded from model training."""
    d = synthetic_training_population["VGS(th)"]
    held_out = "LOT_CAL_001"
    train_mask = [lot != held_out for lot in d["lots"]]

    X_train = d["X"][train_mask]
    y_train = d["y"][train_mask]
    train_lots = sorted(list(set(l for l in d["lots"] if l != held_out)))

    model = RidgeRegressionPrognosticModel(parameter_name="VGS(th)", unit=d["unit"])
    model.fit(X_train, y_train, training_lot_ids=train_lots)

    lineage = model.get_lineage()
    assert held_out not in lineage["training_lot_ids"]
    assert len(lineage["training_lot_ids"]) == 2
    assert "LOT_CAL_002" in lineage["training_lot_ids"]
    assert "LOT_CAL_003" in lineage["training_lot_ids"]


# ==============================================================================
# DIMENSION 5: PREPROCESSING FIT ONLY ON TRAINING DATA
# ==============================================================================

def test_preprocessing_fit_only_on_training_data(synthetic_training_population):
    """Standardization parameters must be calculated solely on training folds."""
    d = synthetic_training_population["RDS(on)"]
    held_out = "LOT_CAL_001"
    train_mask = [lot != held_out for lot in d["lots"]]

    X_train = d["X"][train_mask]
    y_train = d["y"][train_mask]

    model = RidgeRegressionPrognosticModel(parameter_name="RDS(on)", unit=d["unit"])
    model.fit(X_train, y_train)

    stored_mean_u0 = model.preprocessor_params_["u0_mean"]
    stored_std_u0 = model.preprocessor_params_["u0_std"]

    # Calculate expected mean and std strictly on training set transformed values
    u0_train = [transform_parameter("RDS(on)", v) for v in X_train[:, 0]]
    assert math.isclose(stored_mean_u0, np.mean(u0_train), rel_tol=1e-9)
    assert math.isclose(stored_std_u0, np.std(u0_train, ddof=0), rel_tol=1e-9)

    # Predicting on arbitrary test inputs must not alter preprocessor parameters
    test_input = PrognosticInput(
        component_id="TEST_C001",
        lot_id=held_out,
        parameter_name="RDS(on)",
        unit=d["unit"],
        as_of_hours=24,
        target_hours=168,
        historical_observations=[(0, 55.0), (24, 56.0)],
        data_sufficiency_passed=True,
    )
    model.predict_single(test_input)
    assert model.preprocessor_params_["u0_mean"] == stored_mean_u0
    assert model.preprocessor_params_["u0_std"] == stored_std_u0


# ==============================================================================
# DIMENSION 6: NO FUTURE CHECKPOINT ACCESS
# ==============================================================================

def test_no_future_checkpoint_access(synthetic_training_population):
    """Input at T=24h must be strictly invariant to any future values."""
    d = synthetic_training_population["IDSS"]
    model = HuberRegressionPrognosticModel(parameter_name="IDSS", unit=d["unit"])
    model.fit(d["X"], d["y"])

    # Normal input with observations at 0h and 24h
    input_clean = PrognosticInput(
        component_id="C001",
        lot_id="LOT_TEST",
        parameter_name="IDSS",
        unit=d["unit"],
        as_of_hours=24,
        target_hours=168,
        historical_observations=[(0, 0.52), (24, 0.54)],
        data_sufficiency_passed=True,
    )
    forecast_clean = model.predict_single(input_clean)

    # Model input extracts observations as-of 24h.
    # If historical_observations mistakenly had a future point, schema validates or model ignores
    # But more directly, PrognosticInput at as_of_hours=24 built from telemetry excludes t > 24h
    df = pd.DataFrame([
        {"component_id": "C001", "lot_id": "LOT_T", "parameter_name": "IDSS", "elapsed_hours": 0, "value": 0.52, "unit": "uA", "temperature_C": 25.0, "test_condition": "RT", "instrument_id": "I1", "channel_id": "C1", "measurement_quality": "GOOD", "rework_count": 0, "absolute_limit_low": 0.0, "absolute_limit_high": 10.0, "source_type": "PRIMARY"},
        {"component_id": "C001", "lot_id": "LOT_T", "parameter_name": "IDSS", "elapsed_hours": 24, "value": 0.54, "unit": "uA", "temperature_C": 25.0, "test_condition": "RT", "instrument_id": "I1", "channel_id": "C1", "measurement_quality": "GOOD", "rework_count": 0, "absolute_limit_low": 0.0, "absolute_limit_high": 10.0, "source_type": "PRIMARY"},
        {"component_id": "C001", "lot_id": "LOT_T", "parameter_name": "IDSS", "elapsed_hours": 96, "value": 999.0, "unit": "uA", "temperature_C": 25.0, "test_condition": "RT", "instrument_id": "I1", "channel_id": "C1", "measurement_quality": "GOOD", "rework_count": 0, "absolute_limit_low": 0.0, "absolute_limit_high": 10.0, "source_type": "PRIMARY"},
        {"component_id": "C001", "lot_id": "LOT_T", "parameter_name": "IDSS", "elapsed_hours": 168, "value": 9999.0, "unit": "uA", "temperature_C": 25.0, "test_condition": "RT", "instrument_id": "I1", "channel_id": "C1", "measurement_quality": "GOOD", "rework_count": 0, "absolute_limit_low": 0.0, "absolute_limit_high": 10.0, "source_type": "PRIMARY"},
    ])

    inp_from_df = build_prognostic_input(df, "C001", "IDSS", as_of_hours=24, target_hours=168)
    forecast_from_df = model.predict_single(inp_from_df)

    assert math.isclose(forecast_clean.predicted_value, forecast_from_df.predicted_value, rel_tol=1e-12)
    # Check that 96h and 168h corruptions had zero effect on the input
    assert len(inp_from_df.historical_observations) == 2
    assert [t for t, _ in inp_from_df.historical_observations] == [0, 24]


# ==============================================================================
# DIMENSION 7: NO GROUND-TRUTH OR SCENARIO ACCESS
# ==============================================================================

def test_no_ground_truth_or_scenario_access():
    """Telemetry containing ground-truth or scenario leakage columns must be rejected."""
    df_leakage = pd.DataFrame([
        {
            "component_id": "C001",
            "lot_id": "LOT_T",
            "parameter_name": "IDSS",
            "elapsed_hours": 0,
            "value": 0.52,
            "scenario_name": "DEGRADING",  # QUARANTINED LEAKAGE COLUMN
        }
    ])
    with pytest.raises(ValueError, match="Ground truth leakage detected"):
        assert_no_ground_truth_leakage(df_leakage)


# ==============================================================================
# DIMENSION 8: DETERMINISTIC REPRODUCIBILITY
# ==============================================================================

def test_deterministic_reproducibility(synthetic_training_population):
    """Refitting models on identical data yields identical coefficients and forecasts."""
    d = synthetic_training_population["IGSS"]

    # Ridge reproducibility
    r1 = RidgeRegressionPrognosticModel("IGSS", d["unit"], l2_reg=1.0)
    r2 = RidgeRegressionPrognosticModel("IGSS", d["unit"], l2_reg=1.0)
    r1.fit(d["X"], d["y"])
    r2.fit(d["X"], d["y"])
    assert np.allclose(r1.coefficients_, r2.coefficients_, atol=1e-12)

    # Huber reproducibility
    h1 = HuberRegressionPrognosticModel("IGSS", d["unit"], delta_scale=1.345, max_iter=50)
    h2 = HuberRegressionPrognosticModel("IGSS", d["unit"], delta_scale=1.345, max_iter=50)
    h1.fit(d["X"], d["y"])
    h2.fit(d["X"], d["y"])
    assert np.allclose(h1.coefficients_, h2.coefficients_, atol=1e-12)

    inp = PrognosticInput(
        component_id="C_DET",
        lot_id="LOT_DET",
        parameter_name="IGSS",
        unit=d["unit"],
        as_of_hours=24,
        target_hours=168,
        historical_observations=[(0, -1.2), (24, -1.3)],
        data_sufficiency_passed=True,
    )
    f1 = h1.predict_single(inp)
    f2 = h2.predict_single(inp)
    assert f1.predicted_value == f2.predicted_value


# ==============================================================================
# DIMENSION 9: FINITE PREDICTIONS AND PROPER INTERVAL ORDERING
# ==============================================================================

def test_finite_predictions_and_interval_bounds(synthetic_training_population):
    """Clean inputs produce finite forecasts with valid [L, U] bounds."""
    for param, d in synthetic_training_population.items():
        model = RidgeRegressionPrognosticModel(param, d["unit"])
        model.fit(d["X"], d["y"])

        inp = PrognosticInput(
            component_id="C_TEST",
            lot_id="LOT_TEST",
            parameter_name=param,
            unit=d["unit"],
            as_of_hours=24,
            target_hours=168,
            historical_observations=[(0, float(d["X"][0, 0])), (24, float(d["X"][0, 1]))],
            data_sufficiency_passed=True,
        )
        forecast = model.predict_single(inp)

        assert forecast.is_valid
        assert np.isfinite(forecast.predicted_value)
        assert forecast.interval_lower is not None
        assert forecast.interval_upper is not None
        assert forecast.interval_lower <= forecast.predicted_value <= forecast.interval_upper


# ==============================================================================
# DIMENSION 10: DIVERGENCE DETECTION AND DETERMINISTIC FALLBACK
# ==============================================================================

def test_divergence_fallback_and_no_cosmetic_clipping(synthetic_training_population):
    """When transformed space forecast explodes, divergence fallback triggers without clipping."""
    d = synthetic_training_population["IDSS"]
    model = RidgeRegressionPrognosticModel("IDSS", d["unit"])
    model.fit(d["X"], d["y"])

    # Adversarially manipulate intercept to force extreme u_pred = 100.0 > 10.0
    model.coefficients_ = np.array([100.0, 0.0, 0.0])

    inp = PrognosticInput(
        component_id="C_DIV",
        lot_id="LOT_DIV",
        parameter_name="IDSS",
        unit=d["unit"],
        as_of_hours=24,
        target_hours=168,
        historical_observations=[(0, 0.5), (24, 0.8)],
        data_sufficiency_passed=True,
    )
    forecast = model.predict_single(inp)

    # Must flag divergence
    assert forecast.is_divergent_fallback is True
    # Must fallback deterministically to Carry-Forward (v24 = 0.8)
    assert math.isclose(forecast.predicted_value, 0.8, rel_tol=1e-9)
    # Must record raw unconstrained u prediction
    assert forecast.raw_unconstrained_u_pred is not None
    assert forecast.raw_unconstrained_u_pred >= 100.0


# ==============================================================================
# DIMENSION 11: ONE-MODEL-PER-PARAMETER TOPOLOGY
# ==============================================================================

def test_one_model_per_parameter_topology():
    """ParameterDecoupledRegressionPipeline maintains 4 completely independent models."""
    pipeline = ParameterDecoupledRegressionPipeline(model_family="RIDGE")

    assert len(pipeline.models) == 4
    for p in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]:
        assert p in pipeline.models
        m = pipeline.get_model(p)
        assert m.parameter_name == p
        assert isinstance(m, RidgeRegressionPrognosticModel)


# ==============================================================================
# DIMENSION 12: BASELINE COMPARISON INTERFACE COMPATIBILITY
# ==============================================================================

def test_baseline_comparison_interface_compatibility(synthetic_training_population):
    """Trained models and baselines must implement the exact same prediction contract."""
    d = synthetic_training_population["VGS(th)"]
    inp = PrognosticInput(
        component_id="C_COMP",
        lot_id="LOT_COMP",
        parameter_name="VGS(th)",
        unit=d["unit"],
        as_of_hours=24,
        target_hours=168,
        historical_observations=[(0, 3.20), (24, 3.25)],
        data_sufficiency_passed=True,
    )

    ridge = RidgeRegressionPrognosticModel("VGS(th)", d["unit"]).fit(d["X"], d["y"])
    huber = HuberRegressionPrognosticModel("VGS(th)", d["unit"]).fit(d["X"], d["y"])
    cf = CarryForwardModel()
    tpl = TwoPointLinearModel()

    f_ridge = ridge.predict_single(inp)
    f_huber = huber.predict_single(inp)
    f_cf = cf.predict_single(inp)
    f_tpl = tpl.predict_single(inp)

    for f in [f_ridge, f_huber, f_cf, f_tpl]:
        assert isinstance(f, PrognosticForecast)
        assert f.is_valid
        assert np.isfinite(f.predicted_value)
        assert f.parameter_name == "VGS(th)"
        assert f.unit == "V"

    # Baseline expectations
    assert math.isclose(f_cf.predicted_value, 3.25, rel_tol=1e-9)
    # TPL: 3.20 + (3.25 - 3.20) / 24 * 168 = 3.20 + 0.05 * 7 = 3.55
    assert math.isclose(f_tpl.predicted_value, 3.55, rel_tol=1e-9)

    # Metrics calculation across heterogeneous models works cleanly
    y_true = np.array([3.30])
    m_ridge = compute_metrics_for_predictions(y_true, np.array([f_ridge.predicted_value]), "V")
    m_cf = compute_metrics_for_predictions(y_true, np.array([f_cf.predicted_value]), "V")
    assert m_ridge["mae"] is not None
    assert m_cf["mae"] is not None
