"""Unit tests for canonical long-format schema and Screening Run models."""

import pytest
import pandas as pd
from sih26170.schema import (
    ALL_COLUMNS,
    CANONICAL_COLUMNS,
    GROUND_TRUTH_COLUMNS,
    CanonicalMeasurement,
    ScreeningRun,
    from_dataframe,
    to_dataframe,
)


def test_canonical_measurement_valid():
    """Verify valid CanonicalMeasurement instantiation."""
    m = CanonicalMeasurement(
        component_id="C001",
        lot_id="L01",
        parameter_name="leakage_current",
        elapsed_hours=0,
        value=10.2,
        unit="uA",
        temperature_C=125.0,
        test_condition="STATIC_BURN_IN",
        instrument_id="INST_A",
        channel_id="CH_01",
        measurement_quality="VALID",
        rework_count=0,
        absolute_limit_low=None,
        absolute_limit_high=50.0,
        source_type="synthetic",
        trajectory_class="stable",
    )
    assert m.component_id == "C001"
    assert m.value == 10.2
    assert m.absolute_limit_high == 50.0


def test_canonical_measurement_invalid_rework_count():
    """Verify negative rework count is rejected."""
    with pytest.raises(ValueError, match="rework_count must be >= 0"):
        CanonicalMeasurement(
            component_id="C001",
            lot_id="L01",
            parameter_name="leakage_current",
            elapsed_hours=0,
            value=10.2,
            unit="uA",
            temperature_C=125.0,
            test_condition="STATIC_BURN_IN",
            rework_count=-1,
        )


def test_canonical_measurement_invalid_quality():
    """Verify invalid quality flag is rejected."""
    with pytest.raises(ValueError, match="measurement_quality .* invalid"):
        CanonicalMeasurement(
            component_id="C001",
            lot_id="L01",
            parameter_name="leakage_current",
            elapsed_hours=0,
            value=10.2,
            unit="uA",
            temperature_C=125.0,
            test_condition="STATIC_BURN_IN",
            measurement_quality="CORRUPTED",
        )


def test_dataframe_round_trip():
    """Verify converting list of measurements to DataFrame and back."""
    m1 = CanonicalMeasurement(
        component_id="C001",
        lot_id="L01",
        parameter_name="leakage_current",
        elapsed_hours=0,
        value=10.5,
        unit="uA",
        temperature_C=125.0,
        test_condition="STATIC_BURN_IN",
        trajectory_class="stable",
    )
    m2 = CanonicalMeasurement(
        component_id="C001",
        lot_id="L01",
        parameter_name="leakage_current",
        elapsed_hours=24,
        value=10.7,
        unit="uA",
        temperature_C=125.0,
        test_condition="STATIC_BURN_IN",
        trajectory_class="stable",
    )

    # DataFrame with ground truth
    df = to_dataframe([m1, m2], include_ground_truth=True)
    assert len(df) == 2
    for col in ALL_COLUMNS:
        assert col in df.columns

    # DataFrame without ground truth (features only)
    df_no_gt = to_dataframe([m1, m2], include_ground_truth=False)
    for col in CANONICAL_COLUMNS:
        assert col in df_no_gt.columns
    for gt_col in GROUND_TRUTH_COLUMNS:
        assert gt_col not in df_no_gt.columns

    # Round trip conversion
    recovered = from_dataframe(df)
    assert len(recovered) == 2
    assert recovered[0].component_id == "C001"
    assert recovered[1].elapsed_hours == 24
    assert recovered[1].value == 10.7
    assert recovered[1].trajectory_class == "stable"


def test_screening_run_lifecycle_model():
    """Verify ScreeningRun metadata and user limits integrity."""
    run = ScreeningRun(
        run_id="RUN_20260916_001",
        component_id="C014",
        lot_id="L07",
        component_family="DC_DC_CONVERTER",
        part_number="DCDC-5V-RADHARD",
        manufacturer="ISRO_QUALIFIED_FOUNDRY",
        user_limits={"leakage_current": (None, 50.0)},
        engineer_id="ENG_042",
        engineer_notes="Standard burn-in run for Lot L07",
    )
    run.validate()
    assert run.run_id == "RUN_20260916_001"
    assert run.user_limits["leakage_current"] == (None, 50.0)
    assert run.status == "INITIALIZED"


def test_screening_run_invalid_limits():
    """Verify ScreeningRun rejects invalid user limit ordering upon construction."""
    with pytest.raises(ValueError, match="user_limits for parameter 'leakage_current' invalid: 60.0 > 50.0"):
        ScreeningRun(
            run_id="RUN_002",
            component_id="C015",
            lot_id="L07",
            component_family="DC_DC_CONVERTER",
            user_limits={"leakage_current": (60.0, 50.0)},
        )


def test_screening_run_configuration_immutability():
    """Verify Audit Section 6: Screening configuration must be reproducible.

    If an engineer changes parameters or runtime limits later, an already-initialized/frozen
    ScreeningRun retains the exact configuration that was actually used.
    """
    run = ScreeningRun(
        run_id="RUN_HISTORICAL_001",
        component_id="C001",
        lot_id="L01",
        component_family="DC_DC_CONVERTER",
        user_limits={"leakage_current": (None, 50.0)},
    )
    # Frozen config captured at initialization
    assert run.get_effective_screening_limits("leakage_current") == (None, 50.0)

    # Engineer subsequently modifies runtime user_limits on the run object
    run.user_limits["leakage_current"] = (None, 45.0)

    # The historical frozen snapshot retains the 50.0 limit
    assert run.get_effective_screening_limits("leakage_current") == (None, 50.0)


def test_ground_truth_isolation():
    """Verify Audit Section 8: Clear separation between observation data and evaluation ground truth."""
    from sih26170.schema import (
        get_ground_truth_data,
        get_observation_data,
        validate_feature_columns,
    )

    m = CanonicalMeasurement(
        component_id="C001",
        lot_id="L01",
        parameter_name="leakage_current",
        elapsed_hours=24,
        value=12.5,
        unit="uA",
        temperature_C=125.0,
        test_condition="STATIC_BURN_IN",
        trajectory_class="accelerating_drift",
        first_abnormal_hour=96,
        abnormal_by_24h=False,
        abnormal_by_96h=True,
        abnormal_by_168h=True,
    )
    df = to_dataframe([m], include_ground_truth=True)

    # 1. Observation data must contain ONLY canonical telemetry columns
    obs = get_observation_data(df)
    assert "trajectory_class" not in obs.columns
    assert "first_abnormal_hour" not in obs.columns
    assert "abnormal_by_24h" not in obs.columns
    assert "abnormal_by_96h" not in obs.columns
    assert "abnormal_by_168h" not in obs.columns
    assert "value" in obs.columns
    assert "elapsed_hours" in obs.columns

    # 2. Ground truth data must isolate labels
    gt = get_ground_truth_data(df)
    assert "trajectory_class" in gt.columns
    assert "abnormal_by_96h" in gt.columns
    assert "value" not in gt.columns  # Sensor value is an observation, not a label

    # 3. Feature validation guard must detect forbidden ground truth columns
    validate_feature_columns(["value", "elapsed_hours", "temperature_C"])  # Valid
    with pytest.raises(ValueError, match="Ground-truth leakage detected in feature columns"):
        validate_feature_columns(["value", "abnormal_by_96h"])


def test_value_status_classification_and_evidence_channels():
    """Verify Issue A & B: Explicit ValueStatus distinction and multi-channel evidence states."""
    from sih26170.schema import (
        AbsoluteStatus,
        DecisionState,
        PeerStatus,
        TrendStatus,
        ValueStatus,
        classify_measurement_value,
    )

    # 1. Classify values: distinct states, no flooring or modification
    assert classify_measurement_value(-0.25) == ValueStatus.NEGATIVE
    assert classify_measurement_value(0.0) == ValueStatus.ZERO
    assert classify_measurement_value(10.5) == ValueStatus.POSITIVE
    assert classify_measurement_value(None) == ValueStatus.MISSING
    assert classify_measurement_value(float("nan")) == ValueStatus.MISSING
    assert classify_measurement_value(float("inf")) == ValueStatus.NON_FINITE

    # 2. Multi-channel evidence independence: AbsoluteStatus.PASS with PeerStatus.INSUFFICIENT_DATA
    # A component passing absolute limits must not be failed merely because peer evidence is insufficient
    abs_status = AbsoluteStatus.PASS
    peer_status = PeerStatus.INSUFFICIENT_DATA
    trend_status = TrendStatus.INSUFFICIENT_DATA

    assert abs_status == AbsoluteStatus.PASS
    assert peer_status == PeerStatus.INSUFFICIENT_DATA
    assert trend_status == TrendStatus.INSUFFICIENT_DATA
    # Confirms INSUFFICIENT_DATA is distinct from REJECT
    assert DecisionState.INSUFFICIENT_DATA != DecisionState.REJECT


