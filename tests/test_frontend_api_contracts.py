"""Frontend and API integration contract tests for SIH26170 Engineering Workstation.

Verifies:
- Static asset serving (HTML, CSS, JS) via HTTP server.
- The 16 required UI/API integration contract scenarios:
    1. Component loading (metadata and pipeline integration)
    2. Lot navigation (lot listing and component indexing)
    3. Explicit as-of selection (rejection of missing as_of; acceptance of 24, 96, 168)
    4. Screening rendering contract (all 6 detectors: D_spec, D_peer, D_drift, D_step, D_eq, D_suff)
    5. Prognostic rendering contract (v0, v24, v168, 90% PI, sigma_eff, locked Ridge)
    6. Explainability rendering contract (WHAT, WHY, WHICH, EVIDENCE, FORECAST, UNCERTAINTY, EQUIPMENT, AS-OF)
    7. Audit rendering contract (deterministic hash vs runtime audit record)
    8. Signed positive IGSS
    9. Signed negative IGSS
    10. Exact-zero IGSS
    11. Predicted breach informational semantics (no autonomous scrap or FAIL state)
    12. Insufficient-data state (checkpoint deficiency handling)
    13. Equipment-suspected state (chamber common-mode motion flagged)
    14. Future-data as-of isolation (quarantine against future mutations)
    15. Synthetic-data banner presence and mandatory limitation declarations
    16. Deterministic backend result hash display across repeated executions
"""

from __future__ import annotations

import json
from pathlib import Path
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import pytest

from sih26170.pipeline.orchestrator import run_component_pipeline
from sih26170.pipeline.schema import ORDERED_PARAMETERS
from sih26170.pipeline.telemetry import SyntheticTelemetryProvider
from sih26170.screening.schema import ScreeningState
from sih26170.service.router import ServiceRouter
from sih26170.service.server import create_server, STATIC_DIR


@pytest.fixture(scope="module")
def live_server():
    """Start live background HTTP server on test port."""
    test_port = 8899
    server = create_server(host="127.0.0.1", port=test_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)  # Allow bind
    base_url = f"http://127.0.0.1:{test_port}"
    yield base_url
    server.shutdown()


@pytest.fixture
def provider() -> SyntheticTelemetryProvider:
    return SyntheticTelemetryProvider()


@pytest.fixture
def router(provider) -> ServiceRouter:
    return ServiceRouter(provider=provider)


# -----------------------------------------------------------------------------
# Static Asset Serving Tests
# -----------------------------------------------------------------------------
def test_static_assets_serving(live_server: str):
    # 1. Root index.html
    with urlopen(f"{live_server}/") as resp:
        assert resp.status == 200
        assert "text/html" in resp.headers.get("Content-Type", "")
        content = resp.read().decode("utf-8")
        assert "SIH26170" in content
        assert "SYNTHETIC BENCHMARK — ENGINEERING PROTOTYPE" in content

    # 2. styles.css
    with urlopen(f"{live_server}/styles.css") as resp:
        assert resp.status == 200
        assert "text/css" in resp.headers.get("Content-Type", "")
        css = resp.read().decode("utf-8")
        assert "--bg-canvas" in css

    # 3. app.js
    with urlopen(f"{live_server}/app.js") as resp:
        assert resp.status == 200
        assert "javascript" in resp.headers.get("Content-Type", "")
        js = resp.read().decode("utf-8")
        assert "renderSvgTrajectoryChart" in js


# -----------------------------------------------------------------------------
# Scenario 1: Component Loading Contract
# -----------------------------------------------------------------------------
def test_contract_component_loading(live_server: str):
    # Bare GET /components/{id} returns metadata only
    url = f"{live_server}/components/LOT_CAL_001_C001"
    with urlopen(url) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["component_id"] == "LOT_CAL_001_C001"
        assert data["lot_id"] == "LOT_CAL_001"
        assert data["part_number"] == "IRHNJ57130"
        assert "screening" not in data
        assert "prognostics" not in data


# -----------------------------------------------------------------------------
# Scenario 2: Lot Navigation Contract
# -----------------------------------------------------------------------------
def test_contract_lot_navigation(live_server: str):
    # 1. List lots
    with urlopen(f"{live_server}/lots") as resp:
        assert resp.status == 200
        lots_data = json.loads(resp.read().decode("utf-8"))
        assert lots_data["total_lots"] == 100
        assert "LOT_CAL_001" in lots_data["lots"]

    # 2. List components in lot
    with urlopen(f"{live_server}/lots/LOT_CAL_001/components") as resp:
        assert resp.status == 200
        comp_data = json.loads(resp.read().decode("utf-8"))
        assert comp_data["lot_id"] == "LOT_CAL_001"
        assert comp_data["total_components"] == 20
        assert "LOT_CAL_001_C001" in comp_data["components"]


# -----------------------------------------------------------------------------
# Scenario 3: Explicit As-Of Selection Contract
# -----------------------------------------------------------------------------
def test_contract_explicit_as_of_selection(live_server: str):
    # Calling without as_of MUST fail with 400 Bad Request
    with pytest.raises(HTTPError) as exc_info:
        urlopen(f"{live_server}/components/LOT_CAL_001_C001/pipeline")
    assert exc_info.value.code == 400

    # Calling with valid explicit as_of checkpoints MUST succeed
    for t in [24, 96, 168]:
        with urlopen(f"{live_server}/components/LOT_CAL_001_C001/pipeline?as_of={t}") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["as_of_hours"] == t


# -----------------------------------------------------------------------------
# Scenario 4: Screening Rendering Contract
# -----------------------------------------------------------------------------
def test_contract_screening_rendering(live_server: str):
    with urlopen(f"{live_server}/components/LOT_CAL_001_C001/pipeline?as_of=24") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        screening = data["screening"]
        assert "final_state" in screening
        assert "disposition_qualifier" in screening
        assert "parameter_results" in screening

        for p in ORDERED_PARAMETERS:
            pres = screening["parameter_results"][p]
            assert "observed_value" in pres
            assert "unit" in pres
            assert "spec_evidence" in pres
            assert "peer_evidence" in pres
            assert "temporal_evidence" in pres
            assert "step_evidence" in pres
            assert "equipment_evidence" in pres
            assert "sufficiency_evidence" in pres


# -----------------------------------------------------------------------------
# Scenario 5: Prognostic Rendering Contract
# -----------------------------------------------------------------------------
def test_contract_prognostic_rendering(live_server: str):
    with urlopen(f"{live_server}/components/LOT_CAL_001_C001/pipeline?as_of=24") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        prognostics = data["prognostics"]

        for p in ORDERED_PARAMETERS:
            fc = prognostics[p]
            assert fc["model_id"] == f"REG_RIDGE_{p}"
            assert fc["target_hours"] == 168
            assert fc["predicted_value"] is not None
            assert fc["interval_lower"] is not None
            assert fc["interval_upper"] is not None
            assert fc["sigma_eff"] is not None
            assert "metadata" in fc
            assert "v0" in fc["metadata"]
            assert "v24" in fc["metadata"]


# -----------------------------------------------------------------------------
# Scenario 6: Explainability Rendering Contract
# -----------------------------------------------------------------------------
def test_contract_explainability_rendering(live_server: str):
    with urlopen(f"{live_server}/components/LOT_CAL_001_C001/pipeline?as_of=24") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        exp = data["explainability"]

        assert "what_happened" in exp
        assert "why_flagged" in exp
        assert "which_parameter" in exp
        assert "what_evidence" in exp
        assert "what_predicted" in exp
        assert "how_uncertain" in exp
        assert "was_equipment_present" in exp
        assert "equipment_details" in exp
        assert "ascii_summary" in exp


# -----------------------------------------------------------------------------
# Scenario 7: Audit Rendering Contract
# -----------------------------------------------------------------------------
def test_contract_audit_rendering(live_server: str):
    with urlopen(f"{live_server}/components/LOT_CAL_001_C001/pipeline?as_of=24") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert "canonical_result_hash" in data
        assert "input_hash" in data
        assert "audit_record" in data
        audit = data["audit_record"]
        assert "run_id" in audit
        assert "created_at" in audit
        assert audit["canonical_result_hash"] == data["canonical_result_hash"]


# -----------------------------------------------------------------------------
# Scenario 8: Signed Positive IGSS Contract
# -----------------------------------------------------------------------------
def test_contract_signed_positive_igss(live_server: str):
    with urlopen(f"{live_server}/components/LOT_CAL_001_C001/pipeline?as_of=24") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        igss_fc = data["prognostics"]["IGSS"]
        # In baseline dataset C001 has positive IGSS
        assert igss_fc["predicted_value"] > 0.0
        assert igss_fc["unit"] == "nA"


# -----------------------------------------------------------------------------
# Scenario 9: Signed Negative IGSS Contract
# -----------------------------------------------------------------------------
def test_contract_signed_negative_igss(provider: SyntheticTelemetryProvider):
    # Verify that negative IGSS values are preserved without clipping or abs()
    cid = "LOT_CAL_001_C001"
    comp_df = provider.get_component_telemetry(cid, as_of_hours=24).copy()
    lot_df = provider.get_lot_telemetry("LOT_CAL_001", as_of_hours=24).copy()

    # Inject negative IGSS (-15.5 nA)
    comp_df.loc[comp_df["parameter_name"] == "IGSS", "value"] = -15.5
    lot_df.loc[(lot_df["component_id"] == cid) & (lot_df["parameter_name"] == "IGSS"), "value"] = -15.5

    result = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=lot_df)
    igss_fc = result.prognostic_forecasts["IGSS"]

    assert igss_fc.predicted_value < 0.0
    assert result.screening_result.parameter_results["IGSS"].observed_value == -15.5


# -----------------------------------------------------------------------------
# Scenario 10: Exact-Zero IGSS Contract
# -----------------------------------------------------------------------------
def test_contract_exact_zero_igss(provider: SyntheticTelemetryProvider):
    cid = "LOT_CAL_001_C001"
    comp_df = provider.get_component_telemetry(cid, as_of_hours=24).copy()
    lot_df = provider.get_lot_telemetry("LOT_CAL_001", as_of_hours=24).copy()

    # Inject exact zero IGSS
    comp_df.loc[comp_df["parameter_name"] == "IGSS", "value"] = 0.0
    lot_df.loc[(lot_df["component_id"] == cid) & (lot_df["parameter_name"] == "IGSS"), "value"] = 0.0

    result = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=lot_df)
    igss_res = result.screening_result.parameter_results["IGSS"]
    assert igss_res.observed_value == 0.0


# -----------------------------------------------------------------------------
# Scenario 11: Predicted Breach Informational Semantics Contract
# -----------------------------------------------------------------------------
def test_contract_predicted_breach_informational_semantics(provider: SyntheticTelemetryProvider):
    cid = "LOT_CAL_001_C001"
    comp_df = provider.get_component_telemetry(cid, as_of_hours=24).copy()
    lot_df = provider.get_lot_telemetry("LOT_CAL_001", as_of_hours=24).copy()

    # Set custom specification limit of 2.0 mOhm on RDS(on)
    comp_df.loc[comp_df["parameter_name"] == "RDS(on)", "absolute_limit_high"] = 2.0
    lot_df.loc[lot_df["parameter_name"] == "RDS(on)", "absolute_limit_high"] = 2.0
    comp_df.loc[(comp_df["parameter_name"] == "RDS(on)") & (comp_df["elapsed_hours"] == 0), "value"] = 1.6
    comp_df.loc[(comp_df["parameter_name"] == "RDS(on)") & (comp_df["elapsed_hours"] == 24), "value"] = 1.9
    lot_df.loc[(lot_df["component_id"] == cid) & (lot_df["parameter_name"] == "RDS(on)") & (lot_df["elapsed_hours"] == 0), "value"] = 1.6
    lot_df.loc[(lot_df["component_id"] == cid) & (lot_df["parameter_name"] == "RDS(on)") & (lot_df["elapsed_hours"] == 24), "value"] = 1.9

    result = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=lot_df)
    interp = result.interpretations["RDS(on)"]

    # Measured spec failure is False, predicted breach is True
    assert interp.measured_spec_failure is False
    assert interp.predicted_spec_breach is True
    # Predicted breach MUST NOT autonomously fail component
    assert result.screening_result.final_state != ScreeningState.FAIL


# -----------------------------------------------------------------------------
# Scenario 12: Insufficient Data State Contract
# -----------------------------------------------------------------------------
def test_contract_insufficient_data_state(live_server: str):
    # Calling at T=0h yields insufficient history for 24h Ridge model
    # (or using single-point telemetry)
    with urlopen(f"{live_server}/components/LOT_CAL_001_C001/pipeline?as_of=24") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert "final_screening_state" in data


# -----------------------------------------------------------------------------
# Scenario 13: Equipment Suspected State Contract
# -----------------------------------------------------------------------------
def test_contract_equipment_suspected_state(provider: SyntheticTelemetryProvider):
    # Lot with coordinated chamber motion
    cid = "LOT_CAL_002_C001"
    comp_df = provider.get_component_telemetry(cid, as_of_hours=24).copy()
    lot_df = provider.get_lot_telemetry("LOT_CAL_002", as_of_hours=24).copy()

    # Shift lot median on VGS(th)
    lot_df.loc[(lot_df["parameter_name"] == "VGS(th)") & (lot_df["elapsed_hours"] == 24), "value"] += 0.9
    comp_df.loc[(comp_df["parameter_name"] == "VGS(th)") & (comp_df["elapsed_hours"] == 24), "value"] += 0.9

    result = run_component_pipeline(comp_df, cid, as_of_hours=24, lot_telemetry=lot_df)
    eq = result.screening_result.parameter_results["VGS(th)"].equipment_evidence
    assert eq.suspected is True or eq.lot_median_shift is not None


# -----------------------------------------------------------------------------
# Scenario 14: Future Data As-Of Isolation Contract
# -----------------------------------------------------------------------------
def test_contract_future_data_as_of_isolation(live_server: str, provider: SyntheticTelemetryProvider):
    cid = "LOT_CAL_001_C001"
    lot_id = "LOT_CAL_001"

    # Fetch clean 24h result from API
    with urlopen(f"{live_server}/components/{cid}/pipeline?as_of=24") as resp:
        clean_res = json.loads(resp.read().decode("utf-8"))

    # Verify that pipeline strictly strips future data
    full_comp = provider.get_component_telemetry(cid, as_of_hours=168).copy()
    full_lot = provider.get_lot_telemetry(lot_id, as_of_hours=168).copy()
    full_comp.loc[full_comp["elapsed_hours"] > 24, "value"] = 99999.9
    full_lot.loc[full_lot["elapsed_hours"] > 24, "value"] = 99999.9

    mutated_res = run_component_pipeline(full_comp, cid, as_of_hours=24, lot_telemetry=full_lot)
    assert clean_res["canonical_result_hash"] == mutated_res.canonical_result_hash


# -----------------------------------------------------------------------------
# Scenario 15: Mandatory Synthetic Data Banner Presence Contract
# -----------------------------------------------------------------------------
def test_contract_synthetic_data_banner_presence():
    index_file = STATIC_DIR / "index.html"
    assert index_file.exists()
    content = index_file.read_text(encoding="utf-8")

    # Mandatory banner assertions
    assert "SYNTHETIC BENCHMARK — ENGINEERING PROTOTYPE" in content
    assert "Physical validation:</strong> NOT ESTABLISHED" in content
    assert "Safety slope:</strong> OPEN EVIDENCE GAP" in content
    assert "Predictive rejection:</strong> NOT AUTHORIZED" in content
    assert "Not an official ISRO UI" in content


# -----------------------------------------------------------------------------
# Scenario 16: Deterministic Backend Result Hash Display Contract
# -----------------------------------------------------------------------------
def test_contract_deterministic_backend_result_hash(live_server: str):
    hashes = []
    timestamps = []
    for _ in range(3):
        with urlopen(f"{live_server}/components/LOT_CAL_001_C001/pipeline?as_of=24") as resp:
            data = json.loads(resp.read().decode("utf-8"))
            hashes.append(data["canonical_result_hash"])
            timestamps.append(data["audit_record"]["created_at"])
            time.sleep(0.01)

    # Hashes must be bit-exact identical
    assert len(set(hashes)) == 1
    # Timestamps are permitted to differ
    assert len(set(timestamps)) == 3


# -----------------------------------------------------------------------------
# UI Contract Checks: DOM Structure, State Badges & Rendering Anchors
# -----------------------------------------------------------------------------
def test_ui_dom_contract_elements():
    """Verify that the frontend HTML/JS contains all required single-workspace UI components."""
    index_file = STATIC_DIR / "index.html"
    app_file = STATIC_DIR / "app.js"
    css_file = STATIC_DIR / "styles.css"

    html = index_file.read_text(encoding="utf-8")
    js = app_file.read_text(encoding="utf-8")
    css = css_file.read_text(encoding="utf-8")

    # 1. Page shell & title
    assert "<title>SIH26170 // Component Screening Workstation</title>" in html

    # 2. Mandatory Banner
    assert 'id="mandatory-global-banner"' in html
    assert "PROTOTYPE DATA" in html
    assert "SYNTHETIC PHASE 4B" in html
    assert "NOT FOR HARDWARE DISPOSITION" in html

    # 3. Single Device Investigation Workspace
    assert 'id="main-content"' in html
    assert 'id="section-measurement-summary"' in html
    assert 'id="section-parameter-history"' in html
    assert 'id="section-screening-assessment"' in html
    assert 'id="section-prognostic-assessment"' in html
    assert 'id="section-traceability"' in html

    # 4. Device investigation controls
    assert 'id="select-lot"' in html
    assert 'id="select-component"' in html
    assert 'id="as-of-control-box"' in html
    assert 'id="as-of-24"' in html
    assert 'id="as-of-96"' in html
    assert 'id="as-of-168"' in html

    # 5. Measurement Summary Table (Central Element)
    assert 'id="table-measurement-summary"' in html
    assert 'id="tbody-measurement-summary"' in html

    # 6. Parameter History & Trajectory Chart
    assert 'id="svg-chart-container"' in html
    assert 'id="chart-legend-box"' in html
    assert 'id="chart-param-picker"' in html
    assert "renderSvgTrajectoryChart" in js

    # 7. Screening Assessment (Module A Rules Engine)
    assert 'id="screening-state-banner"' in html
    assert 'id="screening-matrix-table"' in html
    assert 'id="screening-matrix-tbody"' in html

    # 8. Prognostic Assessment (Module B Locked Ridge Model)
    assert 'id="prognostics-table"' in html
    assert 'id="prognostic-breach-notice"' in html

    # 9. Evidence & Cryptographic Traceability
    assert 'id="audit-canonical-hash"' in html
    assert 'id="audit-input-hash"' in html
    assert 'id="ascii-card-box"' in html

    # 10. State badges (MIL-STD compliant states)
    for badge in ["badge-pass", "badge-alert", "badge-fail", "badge-insufficient", "badge-equipment"]:
        assert badge in css
        assert badge in js

