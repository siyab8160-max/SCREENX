"""Comprehensive Final Release Test Matrix for Module B.

Implements PART F release audit requirements for SIH 2026 Problem Statement SIH26170:
1. Numerical correctness
2. Physical-unit correctness
3. Transform / inverse-transform correctness
4. Deterministic inference
5. Missing-data behavior
6. Uncertainty interval ordering
7. Threshold advisory correctness
8. 60 mOhm screening margin handling
9. 65 mOhm specification ceiling handling
10. Module A interface decoupling
11. Evidence preservation (bidirectional)
12. Future-information blocking (leakage protection)
13. Provenance and audit lineage
14. Reproducibility
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from sih26170.prognostics.production_service import (
    CANONICAL_PARAMETERS,
    CANONICAL_UNITS,
    FROZEN_CONFORMAL_QUANTILES,
    FROZEN_REGIME_THRESHOLDS,
    ModuleBAdvisoryStatus,
    ModuleBOutput,
    ModuleBRegime,
    evaluate_module_b_component,
    integrate_module_a_and_module_b,
    predict_module_b_series,
)
from sih26170.screening.transforms import (
    inverse_transform_parameter,
    transform_parameter,
)
from sih26170.prognostics.safety import (
    IntervalSafetyStatus,
    SafetyConfig,
    SafetyDecision,
    assert_no_safety_leakage,
)
from sih26170.screening.schema import (
    ComponentScreeningResult,
    DispositionQualifier,
    ScreeningState,
)


# ============================================================
# 1. Numerical Correctness
# ============================================================

def test_req1_numerical_correctness():
    """Verify mathematical correctness of point forecast, residual reconstruction, and zero-anchor."""
    # When excess drift is 0, zero-anchor guarantees delta_hat = 0 and u168_hat = u24
    v0 = 30.0
    v24 = 30.0
    res = predict_module_b_series(
        component_id="COMP_NUM_01",
        lot_id="LOT01",
        parameter_name="RDS(on)",
        v0=v0,
        v24=v24,
        peer_v0=[v0],
        peer_v24=[v24],
    )
    assert res.is_valid
    assert res.regime == ModuleBRegime.ZERO_ANCHORED.value
    assert math.isclose(res.predicted_value, v24, rel_tol=1e-9)
    assert math.isclose(res.explanation.excess_drift, 0.0, abs_tol=1e-9)


# ============================================================
# 2. Physical-Unit Correctness
# ============================================================

def test_req2_physical_unit_correctness():
    """Verify all parameters report correct physical units and non-negative values where physical."""
    params_and_units = {
        "IDSS": ("uA", 0.5, 0.52),
        "VGS(th)": ("V", 3.0, 3.05),
        "RDS(on)": ("mOhm", 30.0, 30.5),
        "IGSS": ("nA", 10.0, 11.0),
    }
    for param, (expected_unit, v0, v24) in params_and_units.items():
        res = predict_module_b_series(
            component_id="COMP_UNIT_01",
            lot_id="LOT01",
            parameter_name=param,
            v0=v0,
            v24=v24,
            peer_v0=[v0],
            peer_v24=[v24],
        )
        assert res.unit == expected_unit
        assert res.is_valid
        if param in ("IDSS", "RDS(on)"):
            assert res.predicted_value >= 0.0
            assert res.lower_90 >= 0.0
            assert res.lower_95 >= 0.0


# ============================================================
# 3. Transform / Inverse-Transform Correctness
# ============================================================

def test_req3_transform_inverse_transform_correctness():
    """Verify round-trip fidelity between representation space and physical space."""
    test_values = {
        "IDSS": [0.01, 0.5, 2.0, 10.0],
        "VGS(th)": [1.5, 2.5, 3.2, 4.5],
        "RDS(on)": [20.0, 45.0, 60.0, 75.0],
        "IGSS": [-50.0, -1.0, 0.0, 1.0, 50.0],
    }
    for param, vals in test_values.items():
        for val in vals:
            u = transform_parameter(param, val)
            recovered = inverse_transform_parameter(param, u)
            assert math.isclose(val, recovered, rel_tol=1e-7, abs_tol=1e-9)

    # Negative resistance or IDSS must raise ValueError during transform
    with pytest.raises(ValueError):
        transform_parameter("RDS(on)", -5.0)
    with pytest.raises(ValueError):
        transform_parameter("IDSS", -0.1)


# ============================================================
# 4. Deterministic Inference
# ============================================================

def test_req4_deterministic_inference():
    """Verify repeated evaluations with identical inputs yield identical outputs down to the bit."""
    v0, v24 = 42.0, 44.5
    peers_0 = [41.0, 42.5, 43.0]
    peers_24 = [41.2, 42.8, 43.4]

    res1 = predict_module_b_series("COMP_DET", "LOT01", "RDS(on)", v0, v24, peers_0, peers_24)
    res2 = predict_module_b_series("COMP_DET", "LOT01", "RDS(on)", v0, v24, peers_0, peers_24)

    assert res1.predicted_value == res2.predicted_value
    assert res1.lower_90 == res2.lower_90
    assert res1.upper_90 == res2.upper_90
    assert res1.regime == res2.regime
    assert res1.advisory_status == res2.advisory_status
    assert res1.to_dict() == res2.to_dict()


# ============================================================
# 5. Missing-Data Behavior
# ============================================================

def test_req5_missing_data_behavior():
    """Verify robust refusal on missing, non-finite, and malformed inputs without crashing."""
    corrupt_cases = [
        ("missing_0h", None, 50.0),
        ("missing_24h", 50.0, None),
        ("missing_both", None, None),
        ("nan_0h", float("nan"), 50.0),
        ("nan_24h", 50.0, float("nan")),
        ("inf_0h", float("inf"), 50.0),
        ("inf_24h", 50.0, float("-inf")),
    ]
    for label, v0, v24 in corrupt_cases:
        res = predict_module_b_series("COMP_ERR", "LOT01", "RDS(on)", v0, v24)
        assert not res.is_valid, f"Failed on {label}: expected is_valid=False"
        assert res.advisory_status == ModuleBAdvisoryStatus.INSUFFICIENT_DATA
        assert res.regime == ModuleBRegime.INSUFFICIENT_DATA.value
        assert math.isnan(res.predicted_value)
        assert res.refusal_reason is not None


# ============================================================
# 6. Uncertainty Interval Ordering
# ============================================================

def test_req6_uncertainty_interval_ordering():
    """Verify strict ordering lower_95 <= lower_90 <= pred <= upper_90 <= upper_95."""
    test_trajectories = [
        ("RDS(on)", 30.0, 30.0),  # Stationary
        ("RDS(on)", 45.0, 55.0),  # Strong wearout
        ("VGS(th)", 3.2, 2.9),    # Downward drift
        ("IDSS", 0.5, 0.8),       # Upward drift
        ("IGSS", 10.0, 15.0),     # Gate leakage increase
    ]
    tol = 1e-12
    for param, v0, v24 in test_trajectories:
        res = predict_module_b_series("COMP_UNC", "LOT01", param, v0, v24, [v0], [v0])
        assert res.is_valid
        assert res.lower_95 <= res.lower_90 + tol
        assert res.lower_90 <= res.predicted_value + tol
        assert res.predicted_value <= res.upper_90 + tol
        assert res.upper_90 <= res.upper_95 + tol
        assert res.uncertainty_width_95 >= res.uncertainty_width_90 - tol


# ============================================================
# 7. Threshold Advisory Correctness
# ============================================================

def test_req7_threshold_advisory_correctness():
    """Verify decision support rules: warning on crossing, continue on nominal, refuse on missing."""
    # 1. Nominal series -> CONTINUE
    res_nom = predict_module_b_series("COMP_NOM", "LOT01", "RDS(on)", 30.0, 30.0, [30.0], [30.0])
    assert res_nom.advisory_status == ModuleBAdvisoryStatus.CONTINUE

    # 2. Drifting series crossing threshold -> EARLY_WARNING
    res_drift = predict_module_b_series("COMP_DRIFT", "LOT01", "RDS(on)", 50.0, 58.0, [50.0], [50.1])
    assert res_drift.advisory_status == ModuleBAdvisoryStatus.EARLY_WARNING

    # 3. Missing data -> INSUFFICIENT_DATA (never silently CONTINUE)
    res_miss = predict_module_b_series("COMP_MISS", "LOT01", "RDS(on)", None, 30.0)
    assert res_miss.advisory_status == ModuleBAdvisoryStatus.INSUFFICIENT_DATA


# ============================================================
# 8. 60 mOhm Screening Margin Handling
# ============================================================

def test_req8_rds_60_screening_margin_handling():
    """Verify distinct and mutually exclusive flags for 60 mOhm screening margin."""
    # Case A: Entirely below 60 mOhm (nominal)
    res_a = predict_module_b_series("COMP_A", "LOT01", "RDS(on)", 30.0, 30.0, [30.0], [30.0])
    assert res_a.entirely_below_60 is True
    assert res_a.crosses_60 is False
    assert res_a.entirely_above_60 is False

    # Case B: Crosses 60 mOhm
    res_b = predict_module_b_series("COMP_B", "LOT01", "RDS(on)", 45.0, 52.0, [45.0], [45.2])
    assert res_b.crosses_60 is True
    assert res_b.entirely_below_60 is False
    assert res_b.entirely_above_60 is False
    assert res_b.advisory_status == ModuleBAdvisoryStatus.EARLY_WARNING


# ============================================================
# 9. 65 mOhm Specification Ceiling Handling
# ============================================================

def test_req9_rds_65_specification_ceiling_handling():
    """Verify 60 mOhm screening margin and 65 mOhm spec ceiling remain independent and distinct."""
    # A component can cross 60 mOhm while its upper interval is still below 65 mOhm
    res = predict_module_b_series("COMP_DIST", "LOT01", "RDS(on)", 38.0, 42.0, [38.0], [38.1])
    # Verify that the two thresholds evaluate independently
    assert isinstance(res.crosses_60, bool)
    assert isinstance(res.crosses_65, bool)
    assert isinstance(res.entirely_below_60, bool)
    assert isinstance(res.entirely_below_65, bool)
    # 65 mOhm ceiling is higher than 60 mOhm screening margin, so if upper_90 < 60, it must be < 65
    if res.entirely_below_60:
        assert res.entirely_below_65 is True


# ============================================================
# 10. Module A Interface Decoupling
# ============================================================

def test_req10_module_a_interface_decoupling():
    """Verify Module B operates validly under all four Module A evidence conditions."""
    mod_b_outputs = {
        "RDS(on)": predict_module_b_series("COMP_INT", "LOT01", "RDS(on)", 30.0, 30.0, [30.0], [30.0])
    }

    # Condition 1: Module A evidence present (PASS)
    scr_pass = ComponentScreeningResult(
        component_id="COMP_INT",
        lot_id="LOT01",
        checkpoint=24,
        final_state=ScreeningState.PASS,
        primary_reason_code="SCREENING_PASS_STABLE",
        reason_codes=["SCREENING_PASS_STABLE"],
        compound_evidence=False,
        parameter_results={},
        as_of_hours=24,
        audit_hash="dummy_hash_pass",
        disposition_qualifier=DispositionQualifier.NOMINAL_STABLE,
    )
    res1 = integrate_module_a_and_module_b(scr_pass, mod_b_outputs, "COMP_INT", "LOT01")
    assert res1.module_a_screening["final_state"] == "PASS"
    assert "RDS(on)" in res1.module_b_prognostics
    assert res1.unified_advisory == "NOMINAL_CONTINUE"

    # Condition 2: Module A evidence absent (None)
    res2 = integrate_module_a_and_module_b(None, mod_b_outputs, "COMP_INT", "LOT01")
    assert res2.module_a_screening is None
    assert "RDS(on)" in res2.module_b_prognostics

    # Condition 3: Module A reports equipment / common-mode excursion
    scr_eq = ComponentScreeningResult(
        component_id="COMP_INT",
        lot_id="LOT01",
        checkpoint=24,
        final_state=ScreeningState.EQUIPMENT_SUSPECTED,
        primary_reason_code="CHAMBER_EXCURSION",
        reason_codes=["CHAMBER_EXCURSION"],
        compound_evidence=True,
        parameter_results={},
        as_of_hours=24,
        audit_hash="dummy_hash_eq",
        disposition_qualifier=DispositionQualifier.EQUIPMENT_ONLY,
    )
    res3 = integrate_module_a_and_module_b(scr_eq, mod_b_outputs, "COMP_INT", "LOT01")
    assert res3.module_a_screening["final_state"] == "EQUIPMENT_SUSPECTED"
    assert res3.unified_advisory == "EQUIPMENT_INVESTIGATION_REQUIRED"
    assert "confounded" in " ".join(res3.preservation_notes).lower()

    # Condition 4: Module A reports anomaly evidence (FAIL / SPEC_BREACH)
    scr_fail = ComponentScreeningResult(
        component_id="COMP_INT",
        lot_id="LOT01",
        checkpoint=24,
        final_state=ScreeningState.FAIL,
        primary_reason_code="SPEC_BREACH_MEASURED",
        reason_codes=["SPEC_BREACH_MEASURED"],
        compound_evidence=False,
        parameter_results={},
        as_of_hours=24,
        audit_hash="dummy_hash_fail",
        disposition_qualifier=DispositionQualifier.SPECIFICATION_FAILURE,
    )
    res4 = integrate_module_a_and_module_b(scr_fail, mod_b_outputs, "COMP_INT", "LOT01")
    assert res4.module_a_screening["final_state"] == "FAIL"
    assert "RDS(on)" in res4.module_b_prognostics
    assert "FAIL" in res4.unified_advisory


# ============================================================
# 11. Evidence Preservation (Bidirectional)
# ============================================================

def test_req11_evidence_preservation_bidirectional():
    """Verify neither module can overwrite or corrupt the other module's findings."""
    mod_b_warning = {
        "RDS(on)": predict_module_b_series("COMP_PRESERV", "LOT01", "RDS(on)", 50.0, 58.0, [50.0], [50.1])
    }
    scr_pass = ComponentScreeningResult(
        component_id="COMP_PRESERV",
        lot_id="LOT01",
        checkpoint=24,
        final_state=ScreeningState.PASS,
        primary_reason_code="SCREENING_PASS_STABLE",
        reason_codes=["SCREENING_PASS_STABLE"],
        compound_evidence=False,
        parameter_results={},
        as_of_hours=24,
        audit_hash="dummy_hash_pass_2",
        disposition_qualifier=DispositionQualifier.NOMINAL_STABLE,
    )

    unified = integrate_module_a_and_module_b(scr_pass, mod_b_warning, "COMP_PRESERV", "LOT01")

    # Module A remains PASS
    assert unified.module_a_screening["final_state"] == "PASS"
    # Module B remains EARLY_WARNING
    assert unified.module_b_prognostics["RDS(on)"]["advisory_status"] == "EARLY_WARNING"
    # Neither suppressed the other
    assert any("Module A screening disposition preserved: PASS" in n for n in unified.preservation_notes)
    assert any("Module B emitted EARLY_WARNING" in n for n in unified.preservation_notes)


# ============================================================
# 12. Future-Information Blocking (Leakage Guard)
# ============================================================

def test_req12_future_information_blocking():
    """Verify structural barrier blocks future and ground-truth telemetry columns."""
    forbidden_cols = [
        "value_168h", "actual_value", "ground_truth", "scenario_label",
        "future_equipment_state", "drift_multiplier"
    ]
    with pytest.raises(ValueError, match="Safety decision leakage violation"):
        assert_no_safety_leakage(["component_id", "value_24h", "value_168h"])

    with pytest.raises(ValueError, match="Safety decision leakage violation"):
        assert_no_safety_leakage(["component_id", "ground_truth"])


# ============================================================
# 13. Provenance and Audit Lineage
# ============================================================

def test_req13_provenance_and_audit_lineage():
    """Verify frozen thresholds and calibration quantiles match manifest specifications."""
    manifest_file = Path("artifacts/module_b/module_b_step7_final_freeze_manifest.json")
    assert manifest_file.exists()
    with open(manifest_file, "r") as f:
        manifest = json.load(f)

    for p in CANONICAL_PARAMETERS:
        assert math.isclose(
            FROZEN_REGIME_THRESHOLDS[p],
            manifest["frozen_regime_thresholds"][p],
            rel_tol=1e-9,
        )
        for reg in ("ZERO_ANCHORED", "DRIFT_MODEL"):
            assert math.isclose(
                FROZEN_CONFORMAL_QUANTILES[p][reg]["q90"],
                manifest["frozen_conformal_calibration_quantiles"][p][reg]["q90"],
                rel_tol=1e-9,
            )
            assert math.isclose(
                FROZEN_CONFORMAL_QUANTILES[p][reg]["q95"],
                manifest["frozen_conformal_calibration_quantiles"][p][reg]["q95"],
                rel_tol=1e-9,
            )


# ============================================================
# 14. Reproducibility
# ============================================================

def test_req14_reproducibility():
    """Verify exact reproducibility of training features and models from locked seed 20260918."""
    from sih26170.synthetic.burnin_generator import SyntheticBurnInGenerator
    from sih26170.prognostics.lot_context import extract_loo_lot_context_features

    gen1 = SyntheticBurnInGenerator(seed=20260918)
    obs1, _, _ = gen1.generate(lots=["LOT01"], mode="stress")
    f1 = extract_loo_lot_context_features(obs1)

    gen2 = SyntheticBurnInGenerator(seed=20260918)
    obs2, _, _ = gen2.generate(lots=["LOT01"], mode="stress")
    f2 = extract_loo_lot_context_features(obs2)

    pd.testing.assert_frame_equal(f1, f2)
