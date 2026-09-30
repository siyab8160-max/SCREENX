"""Tests for Stage 2 prognostic models and strict anti-leakage invariants."""

import pytest
import pandas as pd
import numpy as np

from sih26170.prognostics.schema import PrognosticInput
from sih26170.prognostics.validation import build_prognostic_input
from sih26170.prognostics.stage2_models import AdaptiveDriftGatedModel, HierarchicalLotShrunkModel
from sih26170.prognostics.feature_extraction import extract_features_for_input


@pytest.fixture
def clean_stage2_telemetry_df() -> pd.DataFrame:
    """Create a minimal clean 3-component, 1-lot telemetry DataFrame across 0h, 24h, 96h, 168h."""
    rows = []
    components = ["LOT_T2_C001", "LOT_T2_C002", "LOT_T2_C003"]
    params = ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]
    units = {"IDSS": "uA", "VGS(th)": "V", "RDS(on)": "mOhm", "IGSS": "nA"}
    base_vals = {"IDSS": 1.2, "VGS(th)": 3.5, "RDS(on)": 45.0, "IGSS": 0.5}

    for cid in components:
        for p in params:
            u = units[p]
            bv = base_vals[p]
            for t in [0, 24, 96, 168]:
                # C001 is stable, C002 drifts slightly, C003 is stable
                drift_factor = 0.05 if cid == "LOT_T2_C002" else 0.0001
                val = bv + (drift_factor * t)
                rows.append({
                    "component_id": cid,
                    "lot_id": "LOT_T2",
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


def test_stage2_adversarial_future_corruption(clean_stage2_telemetry_df: pd.DataFrame):
    """Actively prove that Stage 2 models at T=24h are bit-for-bit invariant to 96h and 168h corruption."""
    df_clean = clean_stage2_telemetry_df.copy()
    cid = "LOT_T2_C001"
    param = "RDS(on)"
    as_of = 24
    target = 168

    inp_clean = build_prognostic_input(df_clean, cid, param, as_of_hours=as_of, target_hours=target)

    # Instantiate Stage 2 models
    gated_model = AdaptiveDriftGatedModel()
    shrunk_model = HierarchicalLotShrunkModel()

    pred_clean_gated = gated_model.predict_single(inp_clean)
    pred_clean_shrunk = shrunk_model.predict_single(inp_clean)

    # Corrupt future telemetry (96h, 168h) with extreme values
    df_corrupted = df_clean.copy()
    future_mask = (df_corrupted["component_id"] == cid) & (df_corrupted["elapsed_hours"] > as_of)
    df_corrupted.loc[future_mask, "value"] = 5.0e8

    inp_corrupted = build_prognostic_input(df_corrupted, cid, param, as_of_hours=as_of, target_hours=target)

    pred_corrupted_gated = gated_model.predict_single(inp_corrupted)
    pred_corrupted_shrunk = shrunk_model.predict_single(inp_corrupted)

    # Must be bit-for-bit identical
    assert pred_clean_gated.predicted_value == pred_corrupted_gated.predicted_value
    assert pred_clean_gated.forecast_change_from_origin == pred_corrupted_gated.forecast_change_from_origin
    assert pred_clean_gated.baseline_relative_forecast_change == pred_corrupted_gated.baseline_relative_forecast_change

    assert pred_clean_shrunk.predicted_value == pred_corrupted_shrunk.predicted_value
    assert pred_clean_shrunk.forecast_change_from_origin == pred_corrupted_shrunk.forecast_change_from_origin
    assert pred_clean_shrunk.baseline_relative_forecast_change == pred_corrupted_shrunk.baseline_relative_forecast_change


def test_stage2_adaptive_gating_behavior():
    """Verify that AdaptiveDriftGatedModel shrinks small slopes to Carry-Forward, but extrapolates large slopes."""
    model = AdaptiveDriftGatedModel(k_sigma=2.0)

    # Case 1: Minimal slope within noise floor (0.0001 V over 24h for VGS(th), noise floor is 0.01)
    inp_noise = PrognosticInput(
        component_id="C_NOISE",
        lot_id="LOT_1",
        parameter_name="VGS(th)",
        unit="V",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 3.500), (24, 3.5001)),
    )
    fc_noise = model.predict_single(inp_noise)
    # Shrunk slope must be exactly 0.0 -> exact Carry-Forward to 3.5001
    assert fc_noise.predicted_value == pytest.approx(3.5001)
    assert fc_noise.forecast_change_from_origin == pytest.approx(0.0)

    # Case 2: Genuine large degradation slope (0.3 V over 24h, well above noise floor)
    inp_drift = PrognosticInput(
        component_id="C_DRIFT",
        lot_id="LOT_1",
        parameter_name="VGS(th)",
        unit="V",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 3.50), (24, 3.80)),
    )
    fc_drift = model.predict_single(inp_drift)
    # Must extrapolate significantly beyond 3.80 V
    assert fc_drift.predicted_value > 4.50
    assert fc_drift.forecast_change_from_origin > 0.70


def test_stage2_hierarchical_shrinkage_behavior():
    """Verify HierarchicalLotShrunkModel uses lot context to shrink noisy component slopes."""
    model = HierarchicalLotShrunkModel()

    # Create lot context where peers are flat (0.0 slope)
    peer_inputs = [
        PrognosticInput(
            component_id=f"PEER_{i}",
            lot_id="LOT_STABLE",
            parameter_name="IDSS",
            unit="uA",
            as_of_hours=24,
            target_hours=168,
            historical_observations=((0, 1.0), (24, 1.0)),
        )
        for i in range(10)
    ]
    # Add target component with slight noise jitter
    target_inp = PrognosticInput(
        component_id="TARGET_COMP",
        lot_id="LOT_STABLE",
        parameter_name="IDSS",
        unit="uA",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 1.0), (24, 1.002)),
    )
    all_lot = peer_inputs + [target_inp]
    model.set_contemporaneous_lot_inputs(all_lot)

    fc = model.predict_single(target_inp)
    # In a stable lot with tiny noise, slope must be shrunk to lot median (0.0)
    assert fc.predicted_value == pytest.approx(1.002)
    assert fc.forecast_change_from_origin == pytest.approx(0.0)


def test_stage2_peer_future_corruption(clean_stage2_telemetry_df: pd.DataFrame):
    """Actively prove that HierarchicalLotShrunkModel predictions at T=24h cannot change when peer components have future corruption at 96h/168h."""
    df_clean = clean_stage2_telemetry_df.copy()
    cid = "LOT_T2_C001"
    peer_cid = "LOT_T2_C002"
    param = "RDS(on)"
    as_of = 24
    target = 168

    # Uncorrupted run
    inps_clean = [
        build_prognostic_input(df_clean, c, param, as_of_hours=as_of, target_hours=target)
        for c in ["LOT_T2_C001", "LOT_T2_C002", "LOT_T2_C003"]
    ]
    model_clean = HierarchicalLotShrunkModel()
    model_clean.set_contemporaneous_lot_inputs(inps_clean)
    pred_clean = model_clean.predict_single(inps_clean[0])

    # Corrupt peer readings at 96h and 168h
    df_corrupted = df_clean.copy()
    peer_future = (df_corrupted["component_id"] == peer_cid) & (df_corrupted["elapsed_hours"] > as_of)
    df_corrupted.loc[peer_future, "value"] = 99999999.0

    inps_corrupted = [
        build_prognostic_input(df_corrupted, c, param, as_of_hours=as_of, target_hours=target)
        for c in ["LOT_T2_C001", "LOT_T2_C002", "LOT_T2_C003"]
    ]
    model_corrupted = HierarchicalLotShrunkModel()
    model_corrupted.set_contemporaneous_lot_inputs(inps_corrupted)
    pred_corrupted = model_corrupted.predict_single(inps_corrupted[0])

    assert pred_clean.predicted_value == pred_corrupted.predicted_value
    assert pred_clean.forecast_change_from_origin == pred_corrupted.forecast_change_from_origin
    assert pred_clean.baseline_relative_forecast_change == pred_corrupted.baseline_relative_forecast_change


def test_stage2_feature_quarantine_enforcement():
    """Verify that extract_features_for_input rejects post-T screening evidence."""
    class MockScreeningResult:
        def __init__(self, as_of: int):
            self.as_of_hours = as_of
            self.final_state = "ALERT"

    # Input at 24h with 96h screening result must be rejected
    prog_inp = PrognosticInput(
        component_id="C1",
        lot_id="L1",
        parameter_name="IDSS",
        unit="uA",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 1.0), (24, 1.1)),
    )
    # Manually attach post-T screening result to test feature extractor defensive check
    object.__setattr__(prog_inp, "screening_result", MockScreeningResult(as_of=96))

    with pytest.raises(ValueError, match="Leakage detected: Module A screening result is as-of 96h"):
        extract_features_for_input(prog_inp)


def test_stage2_adversarial_future_corruption_t96(clean_stage2_telemetry_df: pd.DataFrame):
    """Actively prove that Stage 2 models at T=96h are bit-for-bit invariant to 168h future corruption."""
    df_clean = clean_stage2_telemetry_df.copy()
    cid = "LOT_T2_C001"
    param = "RDS(on)"
    as_of = 96
    target = 168

    inps_clean = [
        build_prognostic_input(df_clean, c, param, as_of_hours=as_of, target_hours=target)
        for c in ["LOT_T2_C001", "LOT_T2_C002", "LOT_T2_C003"]
    ]

    gated_model = AdaptiveDriftGatedModel()
    shrunk_model = HierarchicalLotShrunkModel()
    shrunk_model.set_contemporaneous_lot_inputs(inps_clean)

    pred_clean_gated = gated_model.predict_single(inps_clean[0])
    pred_clean_shrunk = shrunk_model.predict_single(inps_clean[0])

    # Corrupt 168h future telemetry for both target component and peer components
    df_corrupted = df_clean.copy()
    future_mask = df_corrupted["elapsed_hours"] > as_of
    df_corrupted.loc[future_mask, "value"] = 8.88e8

    inps_corrupted = [
        build_prognostic_input(df_corrupted, c, param, as_of_hours=as_of, target_hours=target)
        for c in ["LOT_T2_C001", "LOT_T2_C002", "LOT_T2_C003"]
    ]

    shrunk_model_corrupted = HierarchicalLotShrunkModel()
    shrunk_model_corrupted.set_contemporaneous_lot_inputs(inps_corrupted)

    pred_corrupted_gated = gated_model.predict_single(inps_corrupted[0])
    pred_corrupted_shrunk = shrunk_model_corrupted.predict_single(inps_corrupted[0])

    # Must be bit-for-bit identical
    assert pred_clean_gated.predicted_value == pred_corrupted_gated.predicted_value
    assert pred_clean_gated.forecast_change_from_origin == pred_corrupted_gated.forecast_change_from_origin
    assert pred_clean_gated.baseline_relative_forecast_change == pred_corrupted_gated.baseline_relative_forecast_change

    assert pred_clean_shrunk.predicted_value == pred_corrupted_shrunk.predicted_value
    assert pred_clean_shrunk.forecast_change_from_origin == pred_corrupted_shrunk.forecast_change_from_origin
    assert pred_clean_shrunk.baseline_relative_forecast_change == pred_corrupted_shrunk.baseline_relative_forecast_change


def test_stage2_quarantined_columns_rejection(clean_stage2_telemetry_df: pd.DataFrame):
    """Verify that injecting quarantined scenario metadata or ground truth columns raises a hard ValueError."""
    from sih26170.prognostics.validation import QUARANTINED_COLUMNS

    for col in sorted(QUARANTINED_COLUMNS):
        df_leak = clean_stage2_telemetry_df.copy()
        df_leak[col] = "LEAKED_VALUE"
        with pytest.raises(ValueError, match="Ground truth leakage detected"):
            build_prognostic_input(df_leak, "LOT_T2_C001", "RDS(on)", as_of_hours=24, target_hours=168)


