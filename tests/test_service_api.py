"""Service API router verification tests for SIH26170 Engineering Prototype.

Complies strictly with post-Phase-5 engineering integration specifications:
- Tests all candidate REST endpoints:
    * GET /health
    * GET /lots
    * GET /lots/{lot_id}/components
    * GET /components/{component_id} (bare returns metadata only)
    * GET /components/{component_id}/pipeline (requires explicit as_of query param)
    * GET /components/{component_id}/screening?as_of=24
    * GET /components/{component_id}/forecast?as_of=24
    * GET /components/{component_id}/explainability?as_of=24
    * GET /components/{component_id}/audit?as_of=24
    * GET /model_lineage
- Verifies 400 Bad Request on missing as_of query parameter.
- Verifies 405 Method Not Allowed on non-GET methods.
- Verifies 404 Not Found on invalid routes or missing components.
"""

from __future__ import annotations

import pytest
from sih26170.pipeline.telemetry import SyntheticTelemetryProvider
from sih26170.service.router import ServiceRouter


@pytest.fixture
def router() -> ServiceRouter:
    return ServiceRouter()


def test_api_health_endpoint(router: ServiceRouter):
    status, body = router.dispatch("GET", "/health")
    assert status == 200
    assert body["status"] == "HEALTHY"
    assert body["model_lock"] == "LOCKED_IMMUTABLE"
    assert body["phase5_status"] == "COMPUTATIONALLY_CLOSED"
    assert body["safety_slope"] == "OPEN_EVIDENCE_GAP"
    assert body["predictive_rejection"] == "NOT_AUTHORIZED"


def test_api_lots_endpoints(router: ServiceRouter):
    # GET /lots
    status, body = router.dispatch("GET", "/lots")
    assert status == 200
    assert body["total_lots"] == 100
    assert len(body["lots"]) == 100

    # GET /lots/{lot_id}/components
    lot_id = body["lots"][0]
    status, comp_body = router.dispatch("GET", f"/lots/{lot_id}/components")
    assert status == 200
    assert comp_body["lot_id"] == lot_id
    assert comp_body["total_components"] == 20


def test_api_bare_component_metadata_only(router: ServiceRouter):
    # Bare /components/{id} returns metadata only (no screening, no prognostics)
    status, body = router.dispatch("GET", "/components/LOT_CAL_001_C001")
    assert status == 200
    assert body["component_id"] == "LOT_CAL_001_C001"
    assert body["part_number"] == "IRHNJ57130"
    assert "screening" not in body
    assert "prognostics" not in body
    assert "note" in body


def test_api_as_of_temporal_contract(router: ServiceRouter):
    # Calling pipeline without as_of query parameter MUST return 400 Bad Request
    status, body = router.dispatch("GET", "/components/LOT_CAL_001_C001/pipeline")
    assert status == 400
    assert "as_of" in body["error"]

    # Calling with non-integer as_of MUST return 400
    status, body = router.dispatch("GET", "/components/LOT_CAL_001_C001/pipeline?as_of=invalid")
    assert status == 400

    # Calling with explicit as_of MUST succeed with 200
    status, body = router.dispatch("GET", "/components/LOT_CAL_001_C001/pipeline?as_of=24")
    assert status == 200
    assert body["as_of_hours"] == 24
    assert "canonical_result_hash" in body
    assert "screening" in body
    assert "prognostics" in body


def test_api_sub_resource_views(router: ServiceRouter):
    cid = "LOT_CAL_001_C001"

    # 1. Screening view
    s_status, s_body = router.dispatch("GET", f"/components/{cid}/screening?as_of=24")
    assert s_status == 200
    assert s_body["component_id"] == cid
    assert "final_state" in s_body["screening"]

    # 2. Forecast view
    f_status, f_body = router.dispatch("GET", f"/components/{cid}/forecast?as_of=24")
    assert f_status == 200
    assert "prognostics" in f_body
    assert "interpretations" in f_body
    assert "IDSS" in f_body["prognostics"]

    # 3. Explainability view
    e_status, e_body = router.dispatch("GET", f"/components/{cid}/explainability?as_of=24")
    assert e_status == 200
    assert "what_happened" in e_body["explainability"]
    assert "what_predicted" in e_body["explainability"]

    # 4. Audit view
    a_status, a_body = router.dispatch("GET", f"/components/{cid}/audit?as_of=24")
    assert a_status == 200
    assert "canonical_result_hash" in a_body["audit_record"]

    # 5. Unified Explain view (Item 3.1 & API Interoperability)
    exp_status, exp_body = router.dispatch("GET", f"/components/{cid}/explain?as_of=24")
    assert exp_status == 200
    assert exp_body["component_id"] == cid
    assert exp_body["as_of_hours"] == 24
    assert "disposition" in exp_body
    assert "inspector_justification" in exp_body
    assert "detector_evidence" in exp_body
    assert "prognostics" in exp_body
    assert "known_limitations" in exp_body
    assert len(exp_body["known_limitations"]) == 4

    # Check detector evidence contains all 6 detectors
    rds_ev = exp_body["detector_evidence"]["RDS(on)"]
    for det in ["D_spec", "D_peer", "D_drift", "D_step", "D_eq", "D_suff"]:
        assert det in rds_ev

    # Check prognostics contains SHAP, 90% interval, and counterfactual
    rds_prog = exp_body["prognostics"]["RDS(on)"]
    assert "conformal_interval_90" in rds_prog
    assert "shap_decomposition" in rds_prog
    assert "safety_slope" in rds_prog
    assert "counterfactual" in rds_prog
    assert "boundary_24h_value" in rds_prog["counterfactual"]

    # 6. /api/v1 prefix route normalization
    api_status, api_body = router.dispatch("GET", f"/api/v1/components/{cid}/explain?as_of=24")
    assert api_status == 200
    assert api_body["component_id"] == cid


def test_api_known_limitations(router: ServiceRouter):
    status, body = router.dispatch("GET", "/known_limitations")
    assert status == 200
    assert body["status"] == "DISCLOSED"
    assert body["total_limitations"] == 4
    assert len(body["known_limitations"]) == 4
    ids = [item["id"] for item in body["known_limitations"]]
    assert "KL-01-SUB-NOISE-DRIFT" in ids
    assert "KL-02-LATE-ONSET-WEAROUT" in ids
    assert "KL-03-SMALL-SAMPLE-SOCKET-BIAS" in ids
    assert "KL-04-ABRUPT-STEP-THRESHOLD" in ids


def test_api_counterfactual_exactness(router: ServiceRouter):
    # Test on known defective component LOT_CAL_001_C017 (RDS(on) failure)
    status, body = router.dispatch("GET", "/components/LOT_CAL_001_C017/explain?as_of=24")
    assert status == 200
    rds_cf = body["prognostics"]["RDS(on)"]["counterfactual"]
    assert rds_cf["is_breaching"] is True
    # At boundary, predicted value should match target limit 60.0 mOhm
    from sih26170.prognostics.locked_models import get_locked_ridge_model
    model = get_locked_ridge_model("RDS(on)")
    v0 = body["prognostics"]["RDS(on)"]["v0"]
    y24_bound = rds_cf["boundary_24h_value"]
    pred_at_bound, _, _, _, _ = model.predict_physical(v0, y24_bound)
    assert abs(pred_at_bound - 60.0) < 1e-4


def test_api_model_lineage(router: ServiceRouter):
    status, body = router.dispatch("GET", "/model_lineage")
    assert status == 200
    assert body["model_family"] == "RIDGE_REGRESSION"
    assert body["model_status"] == "LOCKED_IMMUTABLE"
    assert body["lambda_reg"] == 1.0


def test_api_error_handling(router: ServiceRouter):
    # Method not allowed
    status, body = router.dispatch("POST", "/health")
    assert status == 405

    # Not found route
    status, body = router.dispatch("GET", "/non_existent_route")
    assert status == 404

    # Missing component
    status, body = router.dispatch("GET", "/components/DOES_NOT_EXIST")
    assert status == 404
