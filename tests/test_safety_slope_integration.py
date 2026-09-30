"""Comprehensive Verification of the Module B Safety-Slope & Early-Rejection Layer in SIH26170_UNIFIED."""

import pytest
import math
from pathlib import Path

from sih26170.prognostics.safety import (
    SafetyConfig,
    SafetyDecision,
    SafetyDirection,
    SafetySlopeEvaluator,
    assert_no_safety_leakage,
)
from sih26170.pipeline.orchestrator import run_component_pipeline
from sih26170.pipeline.telemetry import SyntheticTelemetryProvider
from sih26170.service.router import ServiceRouter


def test_safety_config_loading():
    cfg_path = Path(__file__).resolve().parents[1] / "configs/safety_config.yaml"
    cfg = SafetyConfig.from_yaml(cfg_path)

    assert cfg.horizon_delta_hours == 144
    assert cfg.as_of_hours == 24
    assert cfg.target_horizon_hours == 168

    assert "IDSS" in cfg.thresholds
    assert cfg.thresholds["IDSS"].safety_threshold_high == 10.0
    assert cfg.thresholds["IDSS"].direction == SafetyDirection.UPPER
    assert cfg.thresholds["IDSS"].unit == "uA"

    assert "VGS(th)" in cfg.thresholds
    assert cfg.thresholds["VGS(th)"].safety_threshold_high == 4.0
    assert cfg.thresholds["VGS(th)"].safety_threshold_low == 2.0
    assert cfg.thresholds["VGS(th)"].direction == SafetyDirection.TWO_SIDED

    assert "RDS(on)" in cfg.thresholds
    assert cfg.thresholds["RDS(on)"].safety_threshold_high == 60.0


def test_safety_slope_arithmetic_and_algebraic_equivalence():
    cfg = SafetyConfig.default()
    evaluator = SafetySlopeEvaluator(config=cfg)

    # Upper bound breach
    res = evaluator.evaluate_single(
        component_id="C001",
        parameter_name="IDSS",
        value_24h=2.0,
        predicted_value_168h=12.0,
    )
    assert res.decision == SafetyDecision.EARLY_REJECT
    assert pytest.approx(res.predicted_drift_rate, 1e-6) == 10.0 / 144.0
    assert pytest.approx(res.safety_slope, 1e-6) == 8.0 / 144.0
    assert res.predicted_drift_rate > res.safety_slope
    assert "CRITICAL" in res.reason

    # Nominal drift
    res_nom = evaluator.evaluate_single(
        component_id="C002",
        parameter_name="IDSS",
        value_24h=1.0,
        predicted_value_168h=3.0,
    )
    assert res_nom.decision == SafetyDecision.CONTINUE
    assert res_nom.predicted_drift_rate <= res_nom.safety_slope
    assert "NOMINAL" in res_nom.reason

    # Exact equality -> CONTINUE
    res_exact = evaluator.evaluate_single(
        component_id="C003",
        parameter_name="IDSS",
        value_24h=2.0,
        predicted_value_168h=10.0,
    )
    assert res_exact.decision == SafetyDecision.CONTINUE


def test_safety_slope_anti_leakage_guard():
    with pytest.raises(ValueError, match="Safety decision leakage violation"):
        assert_no_safety_leakage(["component_id", "value_24h", "value_168h"])

    with pytest.raises(ValueError, match="Safety decision leakage violation"):
        assert_no_safety_leakage(["component_id", "ground_truth", "value_24h"])

    assert_no_safety_leakage(["component_id", "lot_id", "value_24h", "predicted_value_168h"])


def test_pipeline_end_to_end_safety_integration():
    provider = SyntheticTelemetryProvider()
    lot_id = provider.get_lot_ids()[0]
    comp_id = provider.get_component_ids(lot_id)[0]

    comp_tel = provider.get_component_telemetry(comp_id, as_of_hours=24)
    lot_tel = provider.get_lot_telemetry(lot_id, as_of_hours=24)

    result = run_component_pipeline(
        telemetry=comp_tel,
        component_id=comp_id,
        as_of_hours=24,
        lot_telemetry=lot_tel,
    )

    assert hasattr(result, "safety_decisions")
    assert isinstance(result.safety_decisions, dict)
    assert len(result.safety_decisions) == 4

    for p in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]:
        assert p in result.safety_decisions
        s_res = result.safety_decisions[p]
        assert "decision" in s_res
        assert s_res["decision"] in ("CONTINUE", "EARLY_REJECT", "INSUFFICIENT_DATA")
        assert "predicted_drift_rate" in s_res
        assert "safety_slope" in s_res
        assert "reason" in s_res

    res_dict = result.to_dict()
    assert "safety_decisions" in res_dict
    assert "component_early_rejection" in res_dict


def test_service_router_safety_sub_resource():
    router = ServiceRouter()
    provider = SyntheticTelemetryProvider()
    lot_id = provider.get_lot_ids()[0]
    comp_id = provider.get_component_ids(lot_id)[0]

    status_code, body = router.dispatch("GET", f"/components/{comp_id}/safety?as_of=24")
    assert status_code == 200
    assert body["component_id"] == comp_id
    assert body["as_of_hours"] == 24
    assert "early_rejection" in body
    assert "safety_decisions" in body
    assert len(body["safety_decisions"]) == 4

    bad_code, bad_body = router.dispatch("GET", f"/components/{comp_id}/safety")
    assert bad_code == 400
    assert "as_of" in bad_body["error"]
