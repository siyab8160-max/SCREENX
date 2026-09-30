"""Tests for Prognostics contracts, baselines, and evaluation metrics."""

import pytest
import numpy as np

from sih26170.prognostics.schema import PrognosticInput, PrognosticForecast
from sih26170.prognostics.baselines import (
    CarryForwardModel,
    TwoPointLinearModel,
    TheilSenExtrapolationModel,
)
from sih26170.prognostics.metrics import (
    calculate_winkler_score,
    evaluate_forecast_set,
)


def test_prognostic_input_validation():
    """Verify PrognosticInput enforces strict schema and lineage."""
    # Valid input
    inp = PrognosticInput(
        component_id="LOT_N01_C001",
        lot_id="LOT_N01",
        parameter_name="IDSS",
        unit="uA",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 1.0), (24, 1.1)),
    )
    assert inp.component_id == "LOT_N01_C001"
    assert inp.compute_sha256() is not None

    # as_of >= target rejected
    with pytest.raises(ValueError, match="as_of_hours .* must be strictly less than target_hours"):
        PrognosticInput(
            component_id="C1",
            lot_id="L1",
            parameter_name="IDSS",
            unit="uA",
            as_of_hours=168,
            target_hours=168,
            historical_observations=((0, 1.0), (24, 1.1)),
        )

    # observation > as_of rejected
    with pytest.raises(ValueError, match="Temporal leakage: observation at 96h exceeds as_of_hours"):
        PrognosticInput(
            component_id="C1",
            lot_id="L1",
            parameter_name="IDSS",
            unit="uA",
            as_of_hours=24,
            target_hours=168,
            historical_observations=((0, 1.0), (24, 1.1), (96, 1.2)),
        )

    # non-chronological rejected
    with pytest.raises(ValueError, match="Observations must be chronologically ordered"):
        PrognosticInput(
            component_id="C1",
            lot_id="L1",
            parameter_name="IDSS",
            unit="uA",
            as_of_hours=24,
            target_hours=168,
            historical_observations=((24, 1.1), (0, 1.0)),
        )


def test_prognostic_forecast_contract():
    """Verify PrognosticForecast enforces dual drift quantities and interval contracts."""
    # Valid forecast
    fc = PrognosticForecast(
        component_id="LOT_N01_C001",
        lot_id="LOT_N01",
        parameter_name="IDSS",
        unit="uA",
        as_of_hours=24,
        target_hours=168,
        predicted_value=1.5,
        forecast_change_from_origin=0.4,
        baseline_relative_forecast_change=0.5,
        interval_lower=1.3,
        interval_upper=1.7,
        sigma_eff=0.1,
    )
    assert fc.interval_width == pytest.approx(0.4)

    # Inverted interval rejected
    with pytest.raises(ValueError, match="Prediction interval lower bound .* exceeds upper bound"):
        PrognosticForecast(
            component_id="C1",
            lot_id="L1",
            parameter_name="IDSS",
            unit="uA",
            as_of_hours=24,
            target_hours=168,
            predicted_value=1.5,
            forecast_change_from_origin=0.4,
            baseline_relative_forecast_change=0.5,
            interval_lower=1.8,
            interval_upper=1.2,
        )


def test_carry_forward_baseline():
    """Verify CarryForwardModel outputs exactly the latest as-of observation."""
    inp = PrognosticInput(
        component_id="C1",
        lot_id="L1",
        parameter_name="VGS(th)",
        unit="V",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 3.2), (24, 3.25)),
    )
    model = CarryForwardModel()
    fc = model.predict_single(inp)

    assert fc.predicted_value == pytest.approx(3.25)
    assert fc.forecast_change_from_origin == pytest.approx(0.0)
    assert fc.baseline_relative_forecast_change == pytest.approx(0.05)


def test_two_point_linear_baseline():
    """Verify TwoPointLinearModel correctly extrapolates linear trajectory."""
    # VGS(th) linear domain: at 0h = 3.0, at 24h = 3.24 (slope = 0.01 V/h)
    # At 168h: 3.0 + 0.01 * 168 = 4.68 V
    inp = PrognosticInput(
        component_id="C1",
        lot_id="L1",
        parameter_name="VGS(th)",
        unit="V",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 3.0), (24, 3.24)),
    )
    model = TwoPointLinearModel()
    fc = model.predict_single(inp)

    assert fc.predicted_value == pytest.approx(4.68)
    assert fc.forecast_change_from_origin == pytest.approx(4.68 - 3.24)
    assert fc.baseline_relative_forecast_change == pytest.approx(4.68 - 3.0)


def test_theil_sen_baseline():
    """Verify TheilSenExtrapolationModel computes robust median slope."""
    # Observations at 0h: 10.0, 24h: 12.4 (slope=0.1), 96h: 19.6 (slope across 0->96 is 0.1, 24->96 is 0.1)
    inp = PrognosticInput(
        component_id="C1",
        lot_id="L1",
        parameter_name="VGS(th)",
        unit="V",
        as_of_hours=96,
        target_hours=168,
        historical_observations=((0, 10.0), (24, 12.4), (96, 19.6)),
    )
    model = TheilSenExtrapolationModel()
    fc = model.predict_single(inp)

    # 19.6 + 0.1 * (168 - 96) = 19.6 + 7.2 = 26.8
    assert fc.predicted_value == pytest.approx(26.8)
    assert fc.forecast_change_from_origin == pytest.approx(26.8 - 19.6)
    assert fc.baseline_relative_forecast_change == pytest.approx(26.8 - 10.0)


def test_uncertainty_calibration_and_metrics():
    """Verify fit() calibrates candidate sigma_eff on training fold and metrics evaluate correctly."""
    train_inputs = [
        PrognosticInput(
            component_id=f"C{i}",
            lot_id="L_TRAIN",
            parameter_name="VGS(th)",
            unit="V",
            as_of_hours=24,
            target_hours=168,
            historical_observations=((0, 3.0), (24, 3.24)),
        )
        for i in range(10)
    ]
    # True values at 168h have mean 4.68 + some residual noise
    train_targets = [4.68 + (0.1 if i % 2 == 0 else -0.1) for i in range(10)]

    model = TwoPointLinearModel()
    model.fit(train_inputs, train_targets)

    # Predict on test input
    test_inp = PrognosticInput(
        component_id="C_TEST",
        lot_id="L_TEST",
        parameter_name="VGS(th)",
        unit="V",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 3.0), (24, 3.24)),
    )
    fc = model.predict_single(test_inp)

    assert fc.interval_lower is not None
    assert fc.interval_upper is not None
    assert fc.interval_lower < fc.predicted_value < fc.interval_upper

    # Evaluate metrics
    gt_map = {("C_TEST", "VGS(th)"): 4.68}
    summary = evaluate_forecast_set([fc], gt_map)
    assert summary.valid_count == 1
    assert summary.coverage_rate == 1.0
    assert summary.mae == pytest.approx(0.0)
    assert summary.mean_winkler_score is not None


def test_winkler_score_properties():
    """Verify Winkler score penalizes interval breaches heavily."""
    # When true value is inside [10, 20]: score is interval width (10)
    score_inside = calculate_winkler_score(y_true=15.0, lower=10.0, upper=20.0, alpha=0.10)
    assert score_inside == pytest.approx(10.0)

    # When true value breaches upper bound: 25 vs 20: 10 + (2 / 0.1) * (25 - 20) = 10 + 20 * 5 = 110
    score_upper_breach = calculate_winkler_score(y_true=25.0, lower=10.0, upper=20.0, alpha=0.10)
    assert score_upper_breach == pytest.approx(110.0)

    # When true value breaches lower bound: 5 vs 10: 10 + (2 / 0.1) * (10 - 5) = 10 + 20 * 5 = 110
    score_lower_breach = calculate_winkler_score(y_true=5.0, lower=10.0, upper=20.0, alpha=0.10)
    assert score_lower_breach == pytest.approx(110.0)
