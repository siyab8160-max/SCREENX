"""Tests for Stage 3 Prognostic Safety Architecture.

Compliant with LOG-069 and LOG-070:
1. Abrupt-step slope inhibition (switching to post-step Carry-Forward)
2. Equipment common-mode with insignificant excess motion (|g_excess| < 2.5)
3. Equipment confounding with significant excess motion (|g_excess| >= 2.5)
4. Full evidence preservation across all upstream detectors
5. Signed bipolar IGSS behavior (preservation of negative polarity, no abs())
6. Predicted specification breach metadata (positive and negative, zero clipping)
7. Actual non-finite inverse-transform fallback (OverflowError / isinf)
8. Preservation of raw divergent u_pred in metadata
9. Leakage and adversarial future-data isolation
"""

import pytest
import numpy as np
from types import SimpleNamespace
from unittest.mock import patch

from sih26170.prognostics.schema import PrognosticInput, PrognosticForecast
from sih26170.prognostics.stage2_models import AdaptiveDriftGatedModel
from sih26170.screening.schema import (
    AbruptStepStatus,
    EquipmentEvidence,
    EquipmentStatus,
    LimitClass,
    ParameterScreeningResult,
    PeerDeviationStatus,
    PeerEvidence,
    ScreeningState,
    SpecificationEvidence,
    SpecificationStatus,
    StepEvidence,
    SufficiencyEvidence,
    SufficiencyStatus,
    TemporalDriftStatus,
    TemporalEvidence,
)


def make_mock_screening_result(
    parameter: str = "IGSS",
    observed_value: float = 2.579,
    unit: str = "nA",
    step_status: AbruptStepStatus = AbruptStepStatus.NO_STEP,
    step_magnitude: float = 0.0,
    step_ratio: float = 0.0,
    eq_suspected: bool = False,
    eq_status: EquipmentStatus = EquipmentStatus.NOMINAL_EQUIPMENT,
    temp_status: TemporalDriftStatus = TemporalDriftStatus.STATIONARY,
    g_excess: float = None,
    spec_status: SpecificationStatus = SpecificationStatus.COMPLIANT,
    sufficient: bool = True,
) -> ParameterScreeningResult:
    """Construct a complete, valid ParameterScreeningResult for testing."""
    spec_ev = SpecificationEvidence(
        parameter=parameter,
        observed_value=observed_value,
        limit_low=-100.0 if parameter == "IGSS" else 2.0,
        limit_high=100.0 if parameter == "IGSS" else 4.0,
        limit_class=LimitClass.CLASS_A,
        status=spec_status,
        passed=(spec_status == SpecificationStatus.COMPLIANT),
        reason_code="SPEC_EVAL",
        provenance="MIL-PRF-19500/703 Table I",
    )
    peer_ev = PeerEvidence(
        parameter=parameter,
        observed_value=observed_value,
        transformed_value=0.0,
        peer_median=0.0,
        peer_mad=0.1,
        peer_scale=0.1,
        z_score=0.5,
        status=PeerDeviationStatus.PEER_NORMAL,
        peer_count=25,
        reason_code="PEER_EVAL",
    )
    temp_ev = TemporalEvidence(
        parameter=parameter,
        observations_used=2,
        checkpoints_used=[0, 24],
        time_range=(0, 24),
        slope_per_hour=0.05,
        normalized_drift=1.5,
        acceleration_evidence=None,
        status=temp_status,
        confounded_by_equipment=eq_suspected,
        reason_code="TEMP_EVAL",
        g_excess=g_excess,
    )
    step_ev = StepEvidence(
        parameter=parameter,
        previous_checkpoint=0,
        current_checkpoint=24,
        step_magnitude=step_magnitude,
        step_ratio=step_ratio,
        status=step_status,
        reason_code="STEP_EVAL",
    )
    eq_ev = EquipmentEvidence(
        lot_id="LOT_TEST",
        checkpoint=24,
        instrument_id="ATE_01",
        channel_id="CH_01",
        lot_median_shift=0.2,
        fraction_shifting=0.3,
        channel_offset=0.1,
        status=eq_status,
        suspected=eq_suspected,
        reason_code="EQ_EVAL",
    )
    suff_ev = SufficiencyEvidence(
        component_id="COMP_TEST",
        checkpoint=24,
        expected_checkpoints=[0, 24],
        available_checkpoints=[0, 24],
        lot_size=25,
        is_small_lot=False,
        status=SufficiencyStatus.SUFFICIENT if sufficient else SufficiencyStatus.INCOMPLETE_HISTORY,
        sufficient=sufficient,
        reason_code="SUFF_OK" if sufficient else "SUFF_INCOMPLETE",
    )
    return ParameterScreeningResult(
        parameter=parameter,
        observed_value=observed_value,
        unit=unit,
        transformed_value=0.0,
        spec_evidence=spec_ev,
        peer_evidence=peer_ev,
        temporal_evidence=temp_ev,
        step_evidence=step_ev,
        equipment_evidence=eq_ev,
        sufficiency_evidence=suff_ev,
        parameter_state=ScreeningState.PASS,
        primary_reason_code="REASON_OK",
        reason_codes=["REASON_OK"],
    )


# =========================================================================
# 1. Abrupt-Step Slope Inhibition
# =========================================================================

def test_abrupt_step_slope_inhibition():
    """Verify that when D_step flags an abrupt step, slope is inhibited to post-step Carry-Forward."""
    model = AdaptiveDriftGatedModel(k_sigma=2.0)

    # Component with abrupt jump from 0.771 nA to 2.579 nA at 24h
    sr = make_mock_screening_result(
        parameter="IGSS",
        observed_value=2.579,
        unit="nA",
        step_status=AbruptStepStatus.ABRUPT_JUMP_ALERT,
        step_magnitude=1.808,
        step_ratio=5.2,
        temp_status=TemporalDriftStatus.SUBTLE_DRIFT,
    )
    inp = PrognosticInput(
        component_id="LOT_M01_C003",
        lot_id="LOT_M01",
        parameter_name="IGSS",
        unit="nA",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 0.771), (24, 2.579)),
        screening_result=sr,
    )

    forecast = model.predict_single(inp)

    # Must be exact level carry-forward from post-step value 2.579 nA
    assert forecast.predicted_value == pytest.approx(2.579, abs=1e-6)
    assert forecast.step_candidate_status == "STEP_CANDIDATE_UNVERIFIED_PERSISTENCE"
    assert "STEP_CANDIDATE_UNVERIFIED_PERSISTENCE" in forecast.metadata["flags"]
    assert forecast.metadata["shrunk_slope"] == 0.0


# =========================================================================
# 2. Equipment Common-Mode with Insignificant Excess Motion
# =========================================================================

def test_equipment_common_mode_insignificant_excess_motion():
    """Verify that under equipment suspicion with |g_excess| < 2.5, slope is shrunk to Carry-Forward."""
    model = AdaptiveDriftGatedModel(k_sigma=2.0)

    # Component in equipment-suspected lot, but g_excess = 0.8 (< 2.5)
    sr = make_mock_screening_result(
        parameter="RDS(on)",
        observed_value=53.0,
        unit="mOhm",
        eq_suspected=True,
        eq_status=EquipmentStatus.CHAMBER_EXCURSION_SUSPECTED,
        temp_status=TemporalDriftStatus.SUBTLE_DRIFT,
        g_excess=0.8,
    )
    inp = PrognosticInput(
        component_id="LOT_E01_C005",
        lot_id="LOT_E01",
        parameter_name="RDS(on)",
        unit="mOhm",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 50.0), (24, 53.0)),
        screening_result=sr,
    )

    forecast = model.predict_single(inp)

    # Insignificant excess motion -> Carry-Forward
    assert forecast.predicted_value == pytest.approx(53.0, abs=1e-6)
    assert forecast.equipment_confounded is True
    assert "NO_SIGNIFICANT_EXCESS_MOTION_DETECTED" in forecast.metadata["flags"]
    assert "EQUIPMENT_CONFOUNDED" in forecast.metadata["flags"]
    assert forecast.metadata["shrunk_slope"] == 0.0


# =========================================================================
# 3. Equipment Confounding with Significant Excess Motion
# =========================================================================

def test_equipment_confounding_significant_excess_motion():
    """Verify that under equipment suspicion with |g_excess| >= 2.5, regularized slope is retained."""
    model = AdaptiveDriftGatedModel(k_sigma=2.0)

    # Component in equipment-suspected lot with strong excess drift g_excess = 3.5 (>= 2.5)
    sr = make_mock_screening_result(
        parameter="RDS(on)",
        observed_value=56.0,
        unit="mOhm",
        eq_suspected=True,
        eq_status=EquipmentStatus.CHAMBER_EXCURSION_SUSPECTED,
        temp_status=TemporalDriftStatus.ACCELERATING_DRIFT,
        g_excess=3.5,
    )
    inp = PrognosticInput(
        component_id="LOT_E01_C012",
        lot_id="LOT_E01",
        parameter_name="RDS(on)",
        unit="mOhm",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 50.0), (24, 56.0)),
        screening_result=sr,
    )

    forecast = model.predict_single(inp)

    # Significant excess motion -> active regularized extrapolation
    assert forecast.predicted_value > 56.0
    assert forecast.equipment_confounded is True
    assert "CANDIDATE_EXCESS_DRIFT_CONFOUNDED" in forecast.metadata["flags"]
    assert "EQUIPMENT_CONFOUNDED" in forecast.metadata["flags"]
    assert forecast.metadata["shrunk_slope"] > 0.0


# =========================================================================
# 4. Evidence Preservation
# =========================================================================

def test_evidence_preservation():
    """Verify that all upstream detector evidence is faithfully preserved in forecast metadata."""
    model = AdaptiveDriftGatedModel(k_sigma=2.0)

    sr = make_mock_screening_result(
        parameter="IGSS",
        observed_value=2.579,
        unit="nA",
        step_status=AbruptStepStatus.ABRUPT_JUMP_ALERT,
        step_magnitude=1.808,
        step_ratio=5.2,
        eq_suspected=True,
        eq_status=EquipmentStatus.CHANNEL_BIAS_SUSPECTED,
        temp_status=TemporalDriftStatus.SUBTLE_DRIFT,
        g_excess=1.2,
        spec_status=SpecificationStatus.COMPLIANT,
        sufficient=True,
    )
    inp = PrognosticInput(
        component_id="LOT_M01_C003",
        lot_id="LOT_M01",
        parameter_name="IGSS",
        unit="nA",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 0.771), (24, 2.579)),
        screening_result=sr,
    )

    forecast = model.predict_single(inp)

    # Verify complete metadata preservation
    sc_ev = forecast.metadata.get("screening_evidence")
    assert sc_ev is not None
    assert sc_ev["step_status"] == "ABRUPT_JUMP_ALERT"
    assert sc_ev["step_magnitude"] == pytest.approx(1.808, abs=1e-4)
    assert sc_ev["step_ratio"] == pytest.approx(5.2, abs=1e-4)
    assert sc_ev["equipment_status"] == "CHANNEL_BIAS_SUSPECTED"
    assert sc_ev["equipment_suspected"] is True
    assert sc_ev["temporal_status"] == "SUBTLE_DRIFT"
    assert sc_ev["g_excess"] == pytest.approx(1.2, abs=1e-4)
    assert sc_ev["spec_status"] == "COMPLIANT"
    assert sc_ev["sufficiency_status"] == "SUFFICIENT"


# =========================================================================
# 5. Signed Bipolar IGSS Behavior
# =========================================================================

def test_signed_bipolar_igss_behavior():
    """Verify that negative IGSS polarity is strictly preserved across forecasting without abs()."""
    model = AdaptiveDriftGatedModel(k_sigma=2.0)

    # Negative IGSS drifting from -20 nA to -50 nA
    inp = PrognosticInput(
        component_id="LOT_POL_C001",
        lot_id="LOT_POL",
        parameter_name="IGSS",
        unit="nA",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, -20.0), (24, -50.0)),
    )

    forecast = model.predict_single(inp)

    # Must preserve negative polarity and extrapolate in negative direction
    assert forecast.predicted_value < -50.0
    assert np.sign(forecast.predicted_value) == -1.0


# =========================================================================
# 6. Predicted Specification Breach Metadata
# =========================================================================

def test_predicted_specification_breach_metadata():
    """Verify positive and negative predicted specification breach flags without clipping."""
    model = AdaptiveDriftGatedModel(k_sigma=2.0)

    # Positive breach on IGSS (> 100 nA)
    inp_pos = PrognosticInput(
        component_id="LOT_POS_C001",
        lot_id="LOT_POS",
        parameter_name="IGSS",
        unit="nA",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 20.0), (24, 60.0)),
    )
    forecast_pos = model.predict_single(inp_pos)
    assert forecast_pos.predicted_value > 100.0  # NOT clipped to 100.0!
    assert forecast_pos.predicted_spec_breach == "PREDICTED_SPEC_BREACH_POSITIVE"
    assert "PREDICTED_SPEC_BREACH_POSITIVE" in forecast_pos.metadata["flags"]

    # Negative breach on IGSS (< -100 nA)
    inp_neg = PrognosticInput(
        component_id="LOT_NEG_C001",
        lot_id="LOT_NEG",
        parameter_name="IGSS",
        unit="nA",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, -20.0), (24, -60.0)),
    )
    forecast_neg = model.predict_single(inp_neg)
    assert forecast_neg.predicted_value < -100.0  # NOT clipped to -100.0!
    assert forecast_neg.predicted_spec_breach == "PREDICTED_SPEC_BREACH_NEGATIVE"
    assert "PREDICTED_SPEC_BREACH_NEGATIVE" in forecast_neg.metadata["flags"]

    # Compliant IGSS (within [-100, 100])
    inp_comp = PrognosticInput(
        component_id="LOT_COMP_C001",
        lot_id="LOT_COMP",
        parameter_name="IGSS",
        unit="nA",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 2.0), (24, 2.1)),
    )
    forecast_comp = model.predict_single(inp_comp)
    assert abs(forecast_comp.predicted_value) < 100.0
    assert forecast_comp.predicted_spec_breach is None


# =========================================================================
# 7. Actual Non-Finite Inverse-Transform Fallback
# =========================================================================

def test_actual_non_finite_inverse_transform_fallback():
    """Verify that when inverse transform overflows or produces non-finite, fallback is triggered."""
    model = AdaptiveDriftGatedModel(k_sigma=2.0)

    inp = PrognosticInput(
        component_id="LOT_DIV_C001",
        lot_id="LOT_DIV",
        parameter_name="IGSS",
        unit="nA",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 1.0), (24, 10.0)),
    )

    # Patch inverse_transform_parameter to simulate mathematical overflow
    with patch("sih26170.prognostics.stage2_models.inverse_transform_parameter", side_effect=OverflowError("Math overflow")):
        forecast = model.predict_single(inp)

    # Fallback to latest physical observation
    assert forecast.predicted_value == pytest.approx(10.0, abs=1e-6)
    assert forecast.is_divergent_fallback is True
    assert "DIVERGENT_RUNAWAY_PREDICTION" in forecast.metadata["flags"]


# =========================================================================
# 8. Preservation of Raw Divergent u_pred
# =========================================================================

def test_preservation_of_raw_divergent_u_pred():
    """Verify that the unconstrained transformed forecast coordinate is preserved in metadata."""
    model = AdaptiveDriftGatedModel(k_sigma=2.0)

    inp = PrognosticInput(
        component_id="LOT_RAW_C001",
        lot_id="LOT_RAW",
        parameter_name="IGSS",
        unit="nA",
        as_of_hours=24,
        target_hours=168,
        historical_observations=((0, 1.0), (24, 5.0)),
    )

    with patch("sih26170.prognostics.stage2_models.inverse_transform_parameter", return_value=float("inf")):
        forecast = model.predict_single(inp)

    assert forecast.is_divergent_fallback is True
    assert forecast.raw_unconstrained_u_pred is not None
    assert np.isfinite(forecast.raw_unconstrained_u_pred)
    assert forecast.metadata["raw_unconstrained_u_pred"] == forecast.raw_unconstrained_u_pred


# =========================================================================
# 9. Leakage & Adversarial Future-Data Isolation
# =========================================================================

def test_leakage_and_adversarial_future_data_isolation():
    """Verify strict temporal causality and isolation against future observation tampering."""
    # Attempting to include observation at 96h when as_of_hours=24h must be rejected
    with pytest.raises(ValueError, match="Temporal leakage: observation at 96h exceeds as_of_hours"):
        PrognosticInput(
            component_id="COMP_ADV",
            lot_id="LOT_ADV",
            parameter_name="IDSS",
            unit="uA",
            as_of_hours=24,
            target_hours=168,
            historical_observations=((0, 1.0), (24, 1.2), (96, 1.5)),
        )

    # Screening result with future as-of timestamp must be rejected
    mock_future_sr = SimpleNamespace(as_of_hours=96)
    with pytest.raises(ValueError, match="Temporal leakage: screening_result as_of_hours .* exceeds input as_of_hours"):
        PrognosticInput(
            component_id="COMP_ADV",
            lot_id="LOT_ADV",
            parameter_name="IDSS",
            unit="uA",
            as_of_hours=24,
            target_hours=168,
            historical_observations=((0, 1.0), (24, 1.2)),
            screening_result=mock_future_sr,
        )
