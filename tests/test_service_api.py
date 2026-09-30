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
