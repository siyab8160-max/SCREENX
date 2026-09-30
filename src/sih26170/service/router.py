"""Lightweight REST-style service router for SIH26170 Engineering Prototype.

Complies strictly with post-Phase-5 engineering integration specifications:
- Pure Python standard library implementation: Zero external web framework dependencies.
- API Temporal Contract:
    * Bare GET /components/{component_id} returns metadata only.
    * All evaluation endpoints (/screening, /forecast, /explainability, /audit, /pipeline)
      strictly REQUIRE an explicit `as_of` query parameter.
    * NO implicit 'latest' inference path.
- Single Canonical Execution: All endpoint views derive from a single underlying
  ComponentPipelineResult; no duplicated inference logic.
- Zero ground-truth endpoints.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from sih26170.pipeline.demo import DemoScenarioLoader
from sih26170.pipeline.schema import ModelLineageInfo
from sih26170.pipeline.telemetry import BaseTelemetryProvider, SyntheticTelemetryProvider


class ServiceRouter:
    """REST API request dispatcher for the engineering prototype."""

    def __init__(self, provider: Optional[BaseTelemetryProvider] = None) -> None:
        if provider is None:
            provider = SyntheticTelemetryProvider()
        self.provider = provider
        self.demo_loader = DemoScenarioLoader(provider=self.provider)

    def dispatch(
        self,
        method: str,
        uri_path: str,
    ) -> Tuple[int, Dict[str, Any]]:
        """Dispatch HTTP-like request to the appropriate route handler.

        Args:
            method: HTTP verb ('GET', etc.)
            uri_path: Full URI path including query parameters (e.g. '/components/C01/pipeline?as_of=24')

        Returns:
            Tuple of (status_code, response_body_dict)
        """
        if method.upper() != "GET":
            return 405, {"error": f"Method '{method}' not allowed. Only GET is supported."}

        parsed = urlparse(uri_path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        # Route: GET /health
        if path == "/health" or path == "":
            return 200, {
                "status": "HEALTHY",
                "system": "SIH26170_ENGINEERING_PROTOTYPE",
                "phase5_status": "COMPUTATIONALLY_CLOSED",
                "model_lock": "LOCKED_IMMUTABLE",
                "safety_slope": "OPEN_EVIDENCE_GAP",
                "predictive_rejection": "NOT_AUTHORIZED",
                "physical_validation": "NOT_ESTABLISHED",
            }

        # Route: GET /model_lineage
        if path == "/model_lineage":
            info = ModelLineageInfo()
            return 200, info.to_dict()

        # Route: GET /lots
        if path == "/lots":
            lots = self.demo_loader.list_lots()
            return 200, {"total_lots": len(lots), "lots": lots}

        # Route: GET /lots/{lot_id}/components
        parts = [p for p in path.split("/") if p]
        if len(parts) == 3 and parts[0] == "lots" and parts[2] == "components":
            lot_id = parts[1]
            try:
                comps = self.demo_loader.list_components(lot_id)
                return 200, {"lot_id": lot_id, "total_components": len(comps), "components": comps}
            except KeyError as e:
                return 404, {"error": str(e)}

        # Route: Component Endpoints
        # Pattern: /components/{component_id}[/{sub_resource}]
        if len(parts) >= 2 and parts[0] == "components":
            component_id = parts[1]
            sub_resource = parts[2] if len(parts) >= 3 else None

            # 1. Bare /components/{component_id}: Metadata ONLY
            if sub_resource is None:
                try:
                    meta = self.demo_loader.get_component_info(component_id)
                    meta["note"] = (
                        "Bare component endpoint returns metadata only. "
                        "To evaluate screening or prognostics, use /components/{id}/pipeline?as_of=T "
                        "with an explicit as_of query parameter."
                    )
                    return 200, meta
                except KeyError as e:
                    return 404, {"error": str(e)}

            # 2. Evaluation Sub-resources REQUIRE explicit as_of query parameter
            as_of_list = query.get("as_of")
            if not as_of_list or not as_of_list[0].strip():
                return 400, {
                    "error": (
                        "Missing required 'as_of' query parameter (e.g. ?as_of=24). "
                        "Strict temporal causality requires an explicit as-of checkpoint. "
                        "Implicit 'latest' inference is prohibited."
                    )
                }

            try:
                as_of_hours = int(as_of_list[0])
            except ValueError:
                return 400, {"error": f"Invalid 'as_of' value '{as_of_list[0]}'. Must be an integer."}

            try:
                # Execute single underlying pipeline execution
                pipeline_result = self.demo_loader.run_scenario(
                    component_id=component_id,
                    as_of_hours=as_of_hours,
                )
            except KeyError as e:
                return 404, {"error": str(e)}
            except ValueError as e:
                return 400, {"error": str(e)}

            # Dispatch sub-resource view
            if sub_resource == "pipeline":
                resp_data = pipeline_result.to_dict()
                try:
                    comp_tel = self.provider.get_component_telemetry(component_id, as_of_hours)
                    resp_data["observed_telemetry"] = comp_tel[
                        ["elapsed_hours", "parameter_name", "value", "unit"]
                    ].to_dict(orient="records")
                except Exception:
                    resp_data["observed_telemetry"] = []
                return 200, resp_data
            elif sub_resource == "screening":
                return 200, {
                    "component_id": component_id,
                    "as_of_hours": as_of_hours,
                    "screening": pipeline_result.screening_result.to_dict(),
                }
            elif sub_resource == "forecast":
                return 200, {
                    "component_id": component_id,
                    "as_of_hours": as_of_hours,
                    "prognostics": {
                        p: fc.to_dict() for p, fc in pipeline_result.prognostic_forecasts.items()
                    },
                    "interpretations": {
                        p: interp.to_dict() for p, interp in pipeline_result.interpretations.items()
                    },
                }
            elif sub_resource == "explainability":
                return 200, {
                    "component_id": component_id,
                    "as_of_hours": as_of_hours,
                    "explainability": pipeline_result.explainability.to_dict(),
                }
            elif sub_resource == "safety":
                return 200, {
                    "component_id": component_id,
                    "as_of_hours": as_of_hours,
                    "early_rejection": pipeline_result.component_early_rejection,
                    "safety_decisions": pipeline_result.safety_decisions,
                }
            elif sub_resource == "audit":
                return 200, {
                    "component_id": component_id,
                    "as_of_hours": as_of_hours,
                    "audit_record": pipeline_result.audit_record.to_dict() if pipeline_result.audit_record else None,
                }
            else:
                return 404, {"error": f"Unknown sub-resource '{sub_resource}' for component."}

        return 404, {"error": f"Path '{path}' not found."}
