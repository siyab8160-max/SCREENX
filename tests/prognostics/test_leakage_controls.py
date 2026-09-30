"""Mandatory Leakage Control Tests for Module B Prognostics.

Verifies the five mandatory anti-leakage invariants:
1. test_leakage_future_telemetry_blocked
2. test_leakage_future_lot_stats
3. test_leakage_future_component_baseline
4. test_leakage_ground_truth_quarantined
5. test_leakage_post_t_screening_evidence
"""

import pytest
import pandas as pd
import numpy as np

from sih26170.prognostics.schema import PrognosticInput
from sih26170.prognostics.validation import (
    build_prognostic_input,
    filter_as_of_telemetry,
    assert_no_ground_truth_leakage,
)
from sih26170.prognostics.baselines import (
    CarryForwardModel,
    TwoPointLinearModel,
    TheilSenExtrapolationModel,
)


@pytest.fixture
def synthetic_telemetry_df() -> pd.DataFrame:
    """Create a minimal clean 2-component, 1-lot telemetry DataFrame across 0h, 24h, 96h, 168h."""
    rows = []
    components = ["LOT_TEST_C001", "LOT_TEST_C002"]
    params = ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]
    units = {"IDSS": "uA", "VGS(th)": "V", "RDS(on)": "mOhm", "IGSS": "nA"}
    base_vals = {"IDSS": 1.2, "VGS(th)": 3.5, "RDS(on)": 45.0, "IGSS": 0.5}

    for cid in components:
        for p in params:
            u = units[p]
            bv = base_vals[p]
            for t in [0, 24, 96, 168]:
                # Slight drift over time
                val = bv + (0.01 * t)
                rows.append({
                    "component_id": cid,
                    "lot_id": "LOT_TEST",
                    "parameter_name": p,
                    "elapsed_hours": t,
                    "value": val,
                    "unit": u,
                    "temperature_C": 25.0,
                    "test_condition": "ROOM_TEMP",
                    "instrument_id": "INST_01",
                    "channel_id": "CH_01",
                    "measurement_quality": "GOOD",
                    "rework_count": 0,
                    "absolute_limit_low": 0.0,
                    "absolute_limit_high": 100.0,
                    "source_type": "PRIMARY",
                })
    return pd.DataFrame(rows)


def test_leakage_future_telemetry_blocked(synthetic_telemetry_df: pd.DataFrame):
    """Actively prove that predictions at T=24h CANNOT change when future telemetry (96h, 168h) is corrupted."""
    df_clean = synthetic_telemetry_df.copy()
    cid = "LOT_TEST_C001"
    param = "IDSS"
    as_of = 24
    target = 168

    # Uncorrupted baseline predictions
    inp_clean = build_prognostic_input(df_clean, cid, param, as_of_hours=as_of, target_hours=target)
    cf_model = CarryForwardModel()
    tp_model = TwoPointLinearModel()

    pred_clean_cf = cf_model.predict_single(inp_clean)
    pred_clean_tp = tp_model.predict_single(inp_clean)

    # Corrupt future telemetry at 96h and 168h with extreme numbers
    df_corrupted = df_clean.copy()
    future_mask = (df_corrupted["component_id"] == cid) & (df_corrupted["elapsed_hours"] > as_of)
    df_corrupted.loc[future_mask, "value"] = 1.0e9  # Massive corruption

    inp_corrupted = build_prognostic_input(df_corrupted, cid, param, as_of_hours=as_of, target_hours=target)
    pred_corrupted_cf = cf_model.predict_single(inp_corrupted)
    pred_corrupted_tp = tp_model.predict_single(inp_corrupted)

    # Invariants:
    # 1. Corrupted observations must not be ingested
    for t, v in inp_corrupted.historical_observations:
        assert t <= as_of
        assert v < 1.0e8

    # 2. Predictions must be bit-for-bit identical
    assert pred_clean_cf.predicted_value == pred_corrupted_cf.predicted_value
    assert pred_clean_cf.forecast_change_from_origin == pred_corrupted_cf.forecast_change_from_origin
    assert pred_clean_cf.baseline_relative_forecast_change == pred_corrupted_cf.baseline_relative_forecast_change

    assert pred_clean_tp.predicted_value == pred_corrupted_tp.predicted_value
    assert pred_clean_tp.forecast_change_from_origin == pred_corrupted_tp.forecast_change_from_origin
    assert pred_clean_tp.baseline_relative_forecast_change == pred_corrupted_tp.baseline_relative_forecast_change


def test_leakage_future_lot_stats(synthetic_telemetry_df: pd.DataFrame):
    """Actively prove that predictions at T=24h cannot change when future lot peer readings are corrupted."""
    df_clean = synthetic_telemetry_df.copy()
    cid = "LOT_TEST_C001"
    peer_cid = "LOT_TEST_C002"
    param = "RDS(on)"
    as_of = 24
    target = 168

    inp_clean = build_prognostic_input(df_clean, cid, param, as_of_hours=as_of, target_hours=target)
    model = TwoPointLinearModel()
    pred_clean = model.predict_single(inp_clean)

    # Corrupt peer readings in the same lot at t=96h and t=168h
    df_corrupted = df_clean.copy()
    peer_future_mask = (df_corrupted["component_id"] == peer_cid) & (df_corrupted["elapsed_hours"] > as_of)
    df_corrupted.loc[peer_future_mask, "value"] = 999999.0

    inp_corrupted = build_prognostic_input(df_corrupted, cid, param, as_of_hours=as_of, target_hours=target)
    pred_corrupted = model.predict_single(inp_corrupted)

    assert pred_clean.predicted_value == pred_corrupted.predicted_value
    assert pred_clean.forecast_change_from_origin == pred_corrupted.forecast_change_from_origin
    assert pred_clean.baseline_relative_forecast_change == pred_corrupted.baseline_relative_forecast_change


def test_leakage_future_component_baseline(synthetic_telemetry_df: pd.DataFrame):
    """Actively prove that component baseline (0h) and forecast change are unaffected by future component corruption."""
    df_clean = synthetic_telemetry_df.copy()
    cid = "LOT_TEST_C001"
    param = "VGS(th)"
    as_of = 96
    target = 168

    inp_clean = build_prognostic_input(df_clean, cid, param, as_of_hours=as_of, target_hours=target)
    ts_model = TheilSenExtrapolationModel()
    pred_clean = ts_model.predict_single(inp_clean)

    # Corrupt target checkpoint (168h) for this component
    df_corrupted = df_clean.copy()
    target_mask = (df_corrupted["component_id"] == cid) & (df_corrupted["elapsed_hours"] == 168)
    df_corrupted.loc[target_mask, "value"] = -9999.0

    inp_corrupted = build_prognostic_input(df_corrupted, cid, param, as_of_hours=as_of, target_hours=target)
    pred_corrupted = ts_model.predict_single(inp_corrupted)

    assert inp_clean.get_baseline_observation() == inp_corrupted.get_baseline_observation()
    assert pred_clean.predicted_value == pred_corrupted.predicted_value
    assert pred_clean.forecast_change_from_origin == pred_corrupted.forecast_change_from_origin
    assert pred_clean.baseline_relative_forecast_change == pred_corrupted.baseline_relative_forecast_change


def test_leakage_ground_truth_quarantined(synthetic_telemetry_df: pd.DataFrame):
    """Actively prove that supplying quarantined ground-truth columns raises a hard ValueError."""
    quarantined_columns = [
        "is_anomaly",
        "anomaly_type",
        "true_defect_type",
        "defect_channel",
        "scenario_name",
        "ground_truth_label",
        "ground_truth_category",
        "failure_mechanism",
    ]

    for col in quarantined_columns:
        df_contaminated = synthetic_telemetry_df.copy()
        df_contaminated[col] = "CONTAMINATED_GROUND_TRUTH_DATA"

        # assert_no_ground_truth_leakage must raise ValueError
        with pytest.raises(ValueError, match="Ground truth leakage detected"):
            assert_no_ground_truth_leakage(df_contaminated)

        # filter_as_of_telemetry must raise ValueError
        with pytest.raises(ValueError, match="Ground truth leakage detected"):
            filter_as_of_telemetry(df_contaminated, as_of_hours=24)

        # build_prognostic_input must raise ValueError
        with pytest.raises(ValueError, match="Ground truth leakage detected"):
            build_prognostic_input(
                df=df_contaminated,
                component_id="LOT_TEST_C001",
                parameter_name="IDSS",
                as_of_hours=24,
            )


def test_leakage_post_t_screening_evidence(synthetic_telemetry_df: pd.DataFrame):
    """Actively prove that passing post-T Module A screening evidence raises a hard ValueError."""
    # Mock screening result from 96h
    class MockScreeningResult:
        def __init__(self, as_of: int):
            self.as_of_hours = as_of
            self.final_state = "PASS"

    sr_post_t = MockScreeningResult(as_of=96)

    # Attempting to build PrognosticInput at T=24h with 96h screening result must fail
    with pytest.raises(ValueError, match="Screening evidence leakage"):
        build_prognostic_input(
            df=synthetic_telemetry_df,
            component_id="LOT_TEST_C001",
            parameter_name="IDSS",
            as_of_hours=24,
            target_hours=168,
            screening_result=sr_post_t,
        )

    # Attempting to directly construct PrognosticInput with post-T screening result must also fail
    with pytest.raises(ValueError, match="Temporal leakage: screening_result as_of_hours"):
        PrognosticInput(
            component_id="LOT_TEST_C001",
            lot_id="LOT_TEST",
            parameter_name="IDSS",
            unit="uA",
            as_of_hours=24,
            target_hours=168,
            historical_observations=((0, 1.2), (24, 1.22)),
            screening_result=sr_post_t,
        )
