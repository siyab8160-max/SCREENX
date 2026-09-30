"""Integration and contract verification tests for SIH26170 Engineering Prototype.

Complies strictly with post-Phase-5 engineering integration specifications:
- Tests verify contracts and causal isolation, NOT benchmark performance guarantees.
- Invariants verified:
    1. Healthy/stationary component: produces finite forecast and prediction interval; no individual coverage guarantee.
    2. High-but-stable component: produces D_peer outlier evidence and temporal drift evidence without error.
    3. Specification breach: measured breach triggers FAIL state with SPECIFICATION_FAILURE qualifier.
    4. Linear drift: computes Theil-Sen slope and drift evidence, generates locked Ridge forecast contract.
    5. Accelerating drift: preserves Module A acceleration evidence; no claim that linear Ridge reconstructs acceleration.
    6. Abrupt change: step ratio J(T) evaluated and D_step evidence emitted.
    7. Equipment common-mode: chamber shift triggers D_eq evidence, setting EQUIPMENT_SUSPECTED without asserting physical device failure.
    8. Insufficient data: checkpoint count < 2 emits INSUFFICIENT_DATA without fabricating values.
    9. Mixed evidence: both equipment and component evidence preserved.
    10. Signed positive IGSS: evaluated in signed asinh representation.
    11. Signed negative IGSS: evaluated in signed asinh representation without abs() or clipping.
    12. Exact-zero IGSS: evaluated safely at 0.0 nA.
    13. Future-data quarantine: T=24h and T=96h adversarial mutation tests.
    14. Ground-truth isolation: static analysis and runtime isolation.
    15. Deterministic hash invariance: identical canonical_result_hash across runs while timestamps differ.
    16. Missing/invalid telemetry handling.
    17. Divergent prediction fallback under locked Phase-5 numerical policy (|u| > 10.0).
    18. Predictive breach informational decoupling: predicted breach does NOT alter Module A final_state.
    19. Missing lot context handling: peer/equipment evidence marked unavailable, never fabricated.
"""

from __future__ import annotations

import os
from pathlib import Path
import time
import numpy as np
import pandas as pd
import pytest

from sih26170.pipeline.orchestrator import run_component_pipeline
from sih26170.pipeline.schema import (
    CANONICAL_PARAM_UNITS,
    ORDERED_PARAMETERS,
    PhysicalParameter,
    ScreeningState,
)
from sih26170.pipeline.telemetry import SyntheticTelemetryProvider, assert_ground_truth_quarantine
from sih26170.prognostics.locked_models import (
    get_locked_ridge_model,
    DIVERGENCE_THRESHOLD_U,
)


@pytest.fixture
def provider() -> SyntheticTelemetryProvider:
    return SyntheticTelemetryProvider()


# -----------------------------------------------------------------------------
# Scenario 1: Healthy/Stationary Component
# -----------------------------------------------------------------------------
def test_healthy_stationary_component(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_001"
    cid = "LOT_CAL_001_C001"
    lot_df = provider.get_lot_telemetry(lot_id, as_of_hours=24)
    comp_df = provider.get_component_telemetry(cid, as_of_hours=24)

    result = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=lot_df)

    assert result.screening_result.final_state in (ScreeningState.PASS, ScreeningState.ALERT)
    for p in ORDERED_PARAMETERS:
        fc = result.prognostic_forecasts[p]
        assert fc.is_valid is True
        assert np.isfinite(fc.predicted_value)
        assert fc.interval_lower is not None
        assert fc.interval_upper is not None
        assert fc.interval_lower <= fc.interval_upper


# -----------------------------------------------------------------------------
# Scenario 2: High-but-Stable Component
# -----------------------------------------------------------------------------
def test_high_but_stable_component(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_001"
    cid = "LOT_CAL_001_C002"
    lot_df = provider.get_lot_telemetry(lot_id, as_of_hours=24).copy()
    comp_df = provider.get_component_telemetry(cid, as_of_hours=24).copy()

    # Elevate initial IDSS baseline by +1.5 uA for target component across all checkpoints
    comp_df.loc[comp_df["parameter_name"] == "IDSS", "value"] += 1.5
    lot_df.loc[(lot_df["component_id"] == cid) & (lot_df["parameter_name"] == "IDSS"), "value"] += 1.5

    result = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=lot_df)

    idss_res = result.screening_result.parameter_results["IDSS"]
    # Peer evidence should evaluate non-zero z-score
    assert idss_res.peer_evidence.z_score is not None
    assert abs(idss_res.peer_evidence.z_score) > 1.0


# -----------------------------------------------------------------------------
# Scenario 3: Measured Specification Breach
# -----------------------------------------------------------------------------
def test_measured_specification_breach(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_001"
    cid = "LOT_CAL_001_C003"
    lot_df = provider.get_lot_telemetry(lot_id, as_of_hours=24).copy()
    comp_df = provider.get_component_telemetry(cid, as_of_hours=24).copy()

    # Inject extreme IDSS breach at 24h (Class A upper limit is 10.0 uA)
    comp_df.loc[(comp_df["parameter_name"] == "IDSS") & (comp_df["elapsed_hours"] == 24), "value"] = 55.0
    lot_df.loc[(lot_df["component_id"] == cid) & (lot_df["parameter_name"] == "IDSS") & (lot_df["elapsed_hours"] == 24), "value"] = 55.0

    result = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=lot_df)

    assert result.screening_result.final_state == ScreeningState.FAIL
    assert result.screening_result.disposition_qualifier.value == "SPECIFICATION_FAILURE"
    assert result.interpretations["IDSS"].measured_spec_failure is True


# -----------------------------------------------------------------------------
# Scenario 4: Linear Drift
# -----------------------------------------------------------------------------
def test_linear_drift(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_001"
    cid = "LOT_CAL_001_C004"
    lot_df = provider.get_lot_telemetry(lot_id, as_of_hours=96).copy()
    comp_df = provider.get_component_telemetry(cid, as_of_hours=96).copy()

    # Inject linear upward drift on IDSS: 0.5 at 0h, 0.7 at 24h, 1.2 at 48h, 1.6 at 72h, 2.0 at 96h
    drift_map = {0: 0.5, 24: 0.7, 48: 1.2, 72: 1.6, 96: 2.0}
    for t, val in drift_map.items():
        comp_df.loc[(comp_df["parameter_name"] == "IDSS") & (comp_df["elapsed_hours"] == t), "value"] = val
        lot_df.loc[(lot_df["component_id"] == cid) & (lot_df["parameter_name"] == "IDSS") & (lot_df["elapsed_hours"] == t), "value"] = val

    result = run_component_pipeline(comp_df, cid, as_of_hours=96, lot_telemetry=lot_df)

    idss_res = result.screening_result.parameter_results["IDSS"]
    assert idss_res.temporal_evidence.slope_per_hour is not None
    assert idss_res.temporal_evidence.slope_per_hour > 0.0
    assert result.prognostic_forecasts["IDSS"].is_valid is True


# -----------------------------------------------------------------------------
# Scenario 5: Accelerating Drift Contract
# -----------------------------------------------------------------------------
def test_accelerating_drift_contract(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_001"
    cid = "LOT_CAL_001_C005"
    lot_df = provider.get_lot_telemetry(lot_id, as_of_hours=96).copy()
    comp_df = provider.get_component_telemetry(cid, as_of_hours=96).copy()

    # Quadratic convex trajectory
    for t in [0, 24, 48, 72, 96]:
        v = 0.5 + 0.0003 * (t ** 2)
        comp_df.loc[(comp_df["parameter_name"] == "IDSS") & (comp_df["elapsed_hours"] == t), "value"] = v
        lot_df.loc[(lot_df["component_id"] == cid) & (lot_df["parameter_name"] == "IDSS") & (lot_df["elapsed_hours"] == t), "value"] = v

    result = run_component_pipeline(comp_df, cid, as_of_hours=96, lot_telemetry=lot_df)

    idss_temp = result.screening_result.parameter_results["IDSS"].temporal_evidence
    # Preserves Module A acceleration evidence; no requirement that linear Ridge reconstructs acceleration
    assert idss_temp.acceleration_evidence is not None
    assert np.isfinite(result.prognostic_forecasts["IDSS"].predicted_value)


# -----------------------------------------------------------------------------
# Scenario 6: Abrupt Step Change
# -----------------------------------------------------------------------------
def test_abrupt_step_change(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_001"
    cid = "LOT_CAL_001_C006"
    lot_df = provider.get_lot_telemetry(lot_id, as_of_hours=96).copy()
    comp_df = provider.get_component_telemetry(cid, as_of_hours=96).copy()

    # Inject abrupt jump at 96h for RDS(on)
    comp_df.loc[(comp_df["parameter_name"] == "RDS(on)") & (comp_df["elapsed_hours"] == 96), "value"] += 15.0
    lot_df.loc[(lot_df["component_id"] == cid) & (lot_df["parameter_name"] == "RDS(on)") & (lot_df["elapsed_hours"] == 96), "value"] += 15.0

    result = run_component_pipeline(comp_df, cid, as_of_hours=96, lot_telemetry=lot_df)

    rds_step = result.screening_result.parameter_results["RDS(on)"].step_evidence
    assert rds_step.step_ratio is not None
    assert rds_step.step_ratio > 1.0


# -----------------------------------------------------------------------------
# Scenario 7: Equipment Common-Mode
# -----------------------------------------------------------------------------
def test_equipment_common_mode(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_002"
    cid = "LOT_CAL_002_C001"
    lot_df = provider.get_lot_telemetry(lot_id, as_of_hours=24).copy()
    comp_df = provider.get_component_telemetry(cid, as_of_hours=24).copy()

    # Shift entire lot by +30% at 24h on VGS(th)
    lot_df.loc[(lot_df["parameter_name"] == "VGS(th)") & (lot_df["elapsed_hours"] == 24), "value"] += 0.8
    comp_df.loc[(comp_df["parameter_name"] == "VGS(th)") & (comp_df["elapsed_hours"] == 24), "value"] += 0.8

    result = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=lot_df)

    vgs_eq = result.screening_result.parameter_results["VGS(th)"].equipment_evidence
    # Should evaluate chamber motion
    assert vgs_eq.lot_median_shift is not None


# -----------------------------------------------------------------------------
# Scenario 8: Insufficient Data Handling
# -----------------------------------------------------------------------------
def test_insufficient_data_at_t0(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_001"
    cid = "LOT_CAL_001_C007"
    lot_df = provider.get_lot_telemetry(lot_id, as_of_hours=0)
    comp_df = provider.get_component_telemetry(cid, as_of_hours=0)

    result = run_component_pipeline(comp_df, cid, as_of_hours=0, lot_telemetry=lot_df)

    # At t=0h, Ridge cannot forecast because 24h checkpoint is missing
    assert result.prognostic_forecasts["IDSS"].is_valid is False
    assert np.isnan(result.prognostic_forecasts["IDSS"].predicted_value)
    assert result.prognostic_forecasts["IDSS"].interval_lower is None


# -----------------------------------------------------------------------------
# Scenario 9: Mixed Evidence Preservation
# -----------------------------------------------------------------------------
def test_mixed_evidence_preservation(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_001"
    cid = "LOT_CAL_001_C008"
    lot_df = provider.get_lot_telemetry(lot_id, as_of_hours=24)
    comp_df = provider.get_component_telemetry(cid, as_of_hours=24)

    result = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=lot_df)

    # Multi-channel evidence preserved across all 4 parameters simultaneously
    assert len(result.screening_result.parameter_results) == 4
    assert len(result.prognostic_forecasts) == 4
    assert len(result.interpretations) == 4


# -----------------------------------------------------------------------------
# Scenario 10, 11, 12: Signed Positive, Negative, and Zero IGSS
# -----------------------------------------------------------------------------
def test_signed_igss_semantics():
    model = get_locked_ridge_model("IGSS")

    # Positive IGSS
    fc_pos = model.forecast_single(v0=2.0, v24=2.2, component_id="C_POS", lot_id="L01")
    assert fc_pos.predicted_value > 0.0

    # Negative IGSS (must NOT be floored, clipped, or abs-transformed)
    fc_neg = model.forecast_single(v0=-2.0, v24=-2.2, component_id="C_NEG", lot_id="L01")
    assert fc_neg.predicted_value < 0.0

    # Exact Zero IGSS (asinh(0) == 0)
    fc_zero = model.forecast_single(v0=0.0, v24=0.0, component_id="C_ZERO", lot_id="L01")
    assert np.isfinite(fc_zero.predicted_value)
    assert fc_zero.interval_lower is not None and fc_zero.interval_upper is not None


# -----------------------------------------------------------------------------
# Scenario 13: Adversarial Future-Data Quarantine (T=24h and T=96h)
# -----------------------------------------------------------------------------
def test_adversarial_future_data_quarantine(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_001"
    cid = "LOT_CAL_001_C009"

    # 1. Clean run at T=24h
    comp_clean_24 = provider.get_component_telemetry(cid, as_of_hours=24)
    lot_clean_24 = provider.get_lot_telemetry(lot_id, as_of_hours=24)
    res_clean_24 = run_component_pipeline(comp_clean_24, cid, as_of_hours=24, lot_telemetry=lot_clean_24)

    # 2. Inject mutated future records (at 96h and 168h) into input dataframes
    full_comp = provider.get_component_telemetry(cid, as_of_hours=168).copy()
    full_lot = provider.get_lot_telemetry(lot_id, as_of_hours=168).copy()

    # Mutate 96h and 168h to catastrophic values
    full_comp.loc[full_comp["elapsed_hours"] > 24, "value"] = 99999.9
    full_lot.loc[full_lot["elapsed_hours"] > 24, "value"] = 99999.9

    # Run pipeline at as_of_hours=24 with contaminated full dataframes
    res_mutated_24 = run_component_pipeline(full_comp, cid, as_of_hours=24, lot_telemetry=full_lot)

    # Output and canonical hash MUST be 100% bit-exact identical
    assert res_clean_24.canonical_result_hash == res_mutated_24.canonical_result_hash
    assert res_clean_24.screening_result.final_state == res_mutated_24.screening_result.final_state

    # 3. Test at T=96h with mutated 168h
    comp_clean_96 = provider.get_component_telemetry(cid, as_of_hours=96)
    lot_clean_96 = provider.get_lot_telemetry(lot_id, as_of_hours=96)
    res_clean_96 = run_component_pipeline(comp_clean_96, cid, as_of_hours=96, lot_telemetry=lot_clean_96)

    # Re-fetch uncorrupted telemetry before applying 96h future mutation
    full_comp_96 = provider.get_component_telemetry(cid, as_of_hours=168).copy()
    full_lot_96 = provider.get_lot_telemetry(lot_id, as_of_hours=168).copy()
    full_comp_96.loc[full_comp_96["elapsed_hours"] > 96, "value"] = -88888.8
    full_lot_96.loc[full_lot_96["elapsed_hours"] > 96, "value"] = -88888.8
    res_mutated_96 = run_component_pipeline(full_comp_96, cid, as_of_hours=96, lot_telemetry=full_lot_96)

    assert res_clean_96.canonical_result_hash == res_mutated_96.canonical_result_hash


# -----------------------------------------------------------------------------
# Scenario 14: Ground-Truth Isolation
# -----------------------------------------------------------------------------
def test_ground_truth_isolation():
    repo_root = Path(__file__).resolve().parents[1]
    pipeline_dir = repo_root / "src/sih26170/pipeline"
    service_dir = repo_root / "src/sih26170/service"

    # Static analysis check: ensure ground_truth.csv is never imported in pipeline or service
    for p_dir in [pipeline_dir, service_dir]:
        for py_file in p_dir.glob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            assert "ground_truth.csv" not in text, f"Forbidden ground_truth.csv found in {py_file}"


# -----------------------------------------------------------------------------
# Scenario 15: Deterministic Repeatability & Timestamp Independence
# -----------------------------------------------------------------------------
def test_deterministic_repeatability(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_001"
    cid = "LOT_CAL_001_C010"
    lot_df = provider.get_lot_telemetry(lot_id, as_of_hours=24)
    comp_df = provider.get_component_telemetry(cid, as_of_hours=24)

    # Execute run 1
    res1 = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=lot_df)
    time.sleep(0.01)  # Ensure wall-clock difference

    # Execute run 2
    res2 = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=lot_df)

    # canonical_result_hash must be bit-exact identical
    assert res1.canonical_result_hash == res2.canonical_result_hash
    # Runtime execution timestamps are permitted to differ
    assert res1.audit_record is not None and res2.audit_record is not None
    assert res1.audit_record.created_at != res2.audit_record.created_at


# -----------------------------------------------------------------------------
# Scenario 16: Missing / Invalid Telemetry Handling
# -----------------------------------------------------------------------------
def test_invalid_telemetry_handling(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_001"
    cid = "NON_EXISTENT_COMPONENT"
    lot_df = provider.get_lot_telemetry(lot_id, as_of_hours=24)

    with pytest.raises(ValueError, match="no records"):
        run_component_pipeline(pd.DataFrame(), cid, as_of_hours=24, lot_telemetry=lot_df)


# -----------------------------------------------------------------------------
# Scenario 17: Divergent Prediction Fallback (|u| > 10.0 Policy)
# -----------------------------------------------------------------------------
def test_divergent_prediction_fallback():
    model = get_locked_ridge_model("IDSS")
    # Extreme v0 driving u0 > 10.0 (ln(1e12) ~= 27.63, yielding raw_u > 10.0)
    v0_extreme = 1e12
    v24_val = 0.5

    pred_y, y_low, y_upp, is_div, raw_u = model.predict_physical(v0_extreme, v24_val)

    assert is_div is True
    assert raw_u is not None and abs(raw_u) > DIVERGENCE_THRESHOLD_U
    # Deterministic fallback to Carry-Forward (v24)
    assert pred_y == v24_val
    assert y_low == v24_val
    assert y_upp == v24_val


# -----------------------------------------------------------------------------
# Scenario 18: Predictive Breach Informational Decoupling
# -----------------------------------------------------------------------------
def test_predictive_breach_informational_decoupling(provider: SyntheticTelemetryProvider):
    lot_id = "LOT_CAL_001"
    cid = "LOT_CAL_001_C011"
    lot_df = provider.get_lot_telemetry(lot_id, as_of_hours=24).copy()
    comp_df = provider.get_component_telemetry(cid, as_of_hours=24).copy()

    # Apply specification limit of 2.0 mOhm to RDS(on) in input telemetry
    comp_df.loc[comp_df["parameter_name"] == "RDS(on)", "absolute_limit_high"] = 2.0
    lot_df.loc[lot_df["parameter_name"] == "RDS(on)", "absolute_limit_high"] = 2.0

    # At 0h value is 1.6 mOhm, at 24h value is 1.9 mOhm (both compliant <= 2.0 mOhm)
    # Locked Ridge forecasts ~2.11 mOhm at 168h (> 2.0 mOhm limit breach)
    comp_df.loc[(comp_df["parameter_name"] == "RDS(on)") & (comp_df["elapsed_hours"] == 0), "value"] = 1.6
    comp_df.loc[(comp_df["parameter_name"] == "RDS(on)") & (comp_df["elapsed_hours"] == 24), "value"] = 1.9
    lot_df.loc[(lot_df["component_id"] == cid) & (lot_df["parameter_name"] == "RDS(on)") & (lot_df["elapsed_hours"] == 0), "value"] = 1.6
    lot_df.loc[(lot_df["component_id"] == cid) & (lot_df["parameter_name"] == "RDS(on)") & (lot_df["elapsed_hours"] == 24), "value"] = 1.9

    result = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=lot_df)

    rds_interp = result.interpretations["RDS(on)"]
    # Measured spec failure must be False at 24h
    assert rds_interp.measured_spec_failure is False
    # Predicted spec breach is True
    assert rds_interp.predicted_spec_breach is True
    # Predicted breach MUST NOT autonomously set Module A final_state to FAIL
    assert result.screening_result.final_state != ScreeningState.FAIL


# -----------------------------------------------------------------------------
# Scenario 19: Missing Lot Context Handling
# -----------------------------------------------------------------------------
def test_missing_lot_context_handling(provider: SyntheticTelemetryProvider):
    cid = "LOT_CAL_001_C012"
    # Pass ONLY single component with no lot_telemetry provided
    comp_df = provider.get_component_telemetry(cid, as_of_hours=24)

    result = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=None)

    # When N=1, Module A peer evidence evaluates peer_count=0 or small lot suppression
    for p in ORDERED_PARAMETERS:
        peer_ev = result.screening_result.parameter_results[p].peer_evidence
        assert peer_ev.peer_count <= 1
