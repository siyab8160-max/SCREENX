"""Tests for the dedicated Equipment Excursion Demo Scenario (Socket CH_05 Drift).

Verifies the primary architectural differentiator of SCREENX:
Separating ATE socket fixture drift from true silicon degradation, saving $4,000 of flight hardware.
"""

from __future__ import annotations

import pytest

from sih26170.service.router import ServiceRouter
from sih26170.synthetic.equipment_excursion_demo import (
    generate_equipment_drift_demo_lot,
    run_equipment_drift_comparison,
)


def test_equipment_drift_demo_scenario_preserves_hardware():
    """Verify that SCREENX outputs EQUIPMENT_SUSPECTED while naive screener falsely condemns."""
    res = run_equipment_drift_comparison(as_of_hours=24)

    assert res["scenario_name"] == "ATE_SOCKET_CHANNEL_CH05_DRIFT_EXCURSION"
    assert res["affected_channel"] == "CH_05"
    assert len(res["affected_components"]) == 4

    # SCREENX preserves all 4 components on socket CH_05
    assert res["screenx_eq_suspected_count"] == 4
    for cid in res["affected_components"]:
        comp_disp = res["screenx_dispositions"][cid]
        assert comp_disp["final_state"] == "EQUIPMENT_SUSPECTED"
        assert comp_disp["disposition_qualifier"] == "EQUIPMENT_ONLY"
        assert comp_disp["equipment_status"] == "CHANNEL_BIAS_SUSPECTED"
        assert comp_disp["channel_z_score"] >= 3.42

    # Naive screener would scrap all 4 components
    assert res["naive_reject_count"] == 4
    for cid in res["affected_components"]:
        assert res["naive_dispositions"][cid]["decision"] == "REJECT"

    # Business/Operational Impact
    assert res["hardware_saved_count"] == 4
    assert res["economic_value_saved_usd"] == 4000
    assert "60-Second Judge Moment" in res["pitch_60s"]


def test_router_serves_equipment_drift_demo():
    """Verify that ServiceRouter dispatches GET /demo/equipment_excursion cleanly."""
    router = ServiceRouter()
    status_code, body = router.dispatch("GET", "/demo/equipment_excursion?as_of=24")

    assert status_code == 200
    assert body["scenario_name"] == "ATE_SOCKET_CHANNEL_CH05_DRIFT_EXCURSION"
    assert body["screenx_eq_suspected_count"] == 4
    assert body["hardware_saved_count"] == 4
    assert "pitch_60s" in body


def test_router_serves_equipment_drift_lot_and_pipeline():
    """Verify that LOT_DEMO_EXCURSION components and pipeline are directly inspectable via router."""
    router = ServiceRouter()

    # 1. Verify components endpoint for LOT_DEMO_EXCURSION
    status, comps_body = router.dispatch("GET", "/lots/LOT_DEMO_EXCURSION/components")
    assert status == 200
    assert comps_body["lot_id"] == "LOT_DEMO_EXCURSION"
    assert comps_body["total_components"] == 16
    assert "LOT_DEMO_EXCURSION_C013" in comps_body["components"]

    # 2. Verify component metadata endpoint
    status, meta_body = router.dispatch("GET", "/components/LOT_DEMO_EXCURSION_C013")
    assert status == 200
    assert meta_body["component_id"] == "LOT_DEMO_EXCURSION_C013"
    assert meta_body["lot_id"] == "LOT_DEMO_EXCURSION"

    # 3. Verify pipeline evaluation endpoint for affected CH_05 component
    status, pipe_body = router.dispatch("GET", "/components/LOT_DEMO_EXCURSION_C013/pipeline?as_of=24")
    assert status == 200
    assert pipe_body["screening"]["final_state"] == "EQUIPMENT_SUSPECTED"
    assert pipe_body["screening"]["disposition_qualifier"] == "EQUIPMENT_ONLY"
    assert len(pipe_body["observed_telemetry"]) > 0

    # 4. Verify nominal component in same lot
    status, nom_body = router.dispatch("GET", "/components/LOT_DEMO_EXCURSION_C001/pipeline?as_of=24")
    assert status == 200
    assert nom_body["screening"]["final_state"] == "PASS"
