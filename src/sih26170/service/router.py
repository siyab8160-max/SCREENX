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
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import pandas as pd

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
        self.uploaded_telemetry: Optional[pd.DataFrame] = None

    def register_uploaded_telemetry(self, records: list[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate and retain a user-supplied telemetry dataset for inference only."""
        required = {"component_id", "lot_id", "parameter_name", "elapsed_hours", "value", "unit"}
        df = pd.DataFrame(records)
        missing = sorted(required.difference(df.columns))
        if df.empty or missing:
            raise ValueError(f"Uploaded telemetry is missing required fields: {missing}")
        for column in ("elapsed_hours", "value"):
            df[column] = pd.to_numeric(df[column], errors="coerce")
        if df[["elapsed_hours", "value"]].isna().any().any():
            raise ValueError("Uploaded telemetry contains non-numeric elapsed_hours or value fields.")
        from sih26170.pipeline.telemetry import assert_ground_truth_quarantine
        assert_ground_truth_quarantine(df)
        self.uploaded_telemetry = df.copy()
        return {
            "lots": sorted(df["lot_id"].astype(str).unique().tolist()),
            "components": sorted(df["component_id"].astype(str).unique().tolist()),
            "rows": len(df),
        }

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

        # Normalize /api/v1 prefix if present for API interoperability
        if path.startswith("/api/v1"):
            path = path[7:]
            if not path:
                path = "/"

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

        # Route: GET /known_limitations
        if path == "/known_limitations":
            from sih26170.pipeline.explainability import get_known_limitations_disclosure
            return 200, {
                "system": "SIH26170_SCREENX",
                "status": "DISCLOSED",
                "total_limitations": len(get_known_limitations_disclosure()),
                "known_limitations": get_known_limitations_disclosure(),
            }

        # Route: GET /model_lineage
        if path == "/model_lineage":
            info = ModelLineageInfo()
            return 200, info.to_dict()

        # Route: GET /demo/equipment_excursion
        if path == "/demo/equipment_excursion":
            from sih26170.synthetic.equipment_excursion_demo import run_equipment_drift_comparison
            as_of_hours = 24
            if "as_of" in query and query["as_of"]:
                try:
                    as_of_hours = int(query["as_of"][0])
                except ValueError:
                    as_of_hours = 24
            data = run_equipment_drift_comparison(as_of_hours=as_of_hours)
            return 200, data

        # Route: GET /lots
        if path == "/lots":
            if self.uploaded_telemetry is not None:
                lots = sorted(self.uploaded_telemetry["lot_id"].astype(str).unique().tolist())
                return 200, {"total_lots": len(lots), "lots": lots}
            lots = self.demo_loader.list_lots()
            # If explicit include_demo query param is present, prepend the excursion scenario lot
            if query.get("include_demo") and "LOT_DEMO_EXCURSION" not in lots:
                lots = ["LOT_DEMO_EXCURSION"] + lots
            return 200, {"total_lots": len(lots), "lots": lots}

        # Route: GET /lots/{lot_id}/components
        parts = [p for p in path.split("/") if p]
        if len(parts) == 3 and parts[0] == "lots" and parts[2] == "components":
            lot_id = parts[1]
            if self.uploaded_telemetry is not None:
                comps = sorted(self.uploaded_telemetry.loc[
                    self.uploaded_telemetry["lot_id"].astype(str) == lot_id, "component_id"
                ].astype(str).unique().tolist())
                if comps:
                    return 200, {"lot_id": lot_id, "total_components": len(comps), "components": comps}
            if lot_id == "LOT_DEMO_EXCURSION":
                comps = [f"LOT_DEMO_EXCURSION_C{i:03d}" for i in range(1, 17)]
                return 200, {"lot_id": lot_id, "total_components": len(comps), "components": comps}
            try:
                comps = self.demo_loader.list_components(lot_id)
                return 200, {"lot_id": lot_id, "total_components": len(comps), "components": comps}
            except KeyError as e:
                return 404, {"error": str(e)}

        # Route: GET /lots/{lot_id}/equipment_diagnostics
        if len(parts) == 3 and parts[0] == "lots" and parts[2] == "statuses":
            as_of_list = query.get("as_of", ["24"])
            try:
                as_of_hours = int(as_of_list[0])
            except ValueError:
                return 400, {"error": "as_of must be an integer."}
            lot_id = parts[1]
            if self.uploaded_telemetry is not None:
                df = self.uploaded_telemetry
                lot_df = df[(df["lot_id"].astype(str) == lot_id) & (df["elapsed_hours"] <= as_of_hours)]
                component_ids = sorted(lot_df["component_id"].astype(str).unique().tolist())

                def uploaded_status(component_id: str) -> tuple[str, str]:
                    from sih26170.pipeline.orchestrator import run_component_pipeline
                    component_df = lot_df[lot_df["component_id"].astype(str) == component_id]
                    result = run_component_pipeline(component_df, component_id, as_of_hours, lot_df)
                    return component_id, result.screening_result.final_state.value
                evaluator = uploaded_status
            else:
                try:
                    component_ids = self.demo_loader.list_components(lot_id)
                except KeyError as exc:
                    return 404, {"error": str(exc)}

                def demo_status(component_id: str) -> tuple[str, str]:
                    result = self.demo_loader.run_scenario(component_id, as_of_hours)
                    return component_id, result.screening_result.final_state.value
                evaluator = demo_status

            with ThreadPoolExecutor(max_workers=min(8, max(1, len(component_ids)))) as executor:
                statuses = dict(executor.map(evaluator, component_ids))
            return 200, {"lot_id": lot_id, "as_of_hours": as_of_hours, "statuses": statuses}

        if len(parts) == 3 and parts[0] == "lots" and parts[2] == "equipment_diagnostics":
            lot_id = parts[1]
            as_of_list = query.get("as_of")
            as_of_hours = 24
            if as_of_list:
                try:
                    as_of_hours = int(as_of_list[0])
                except ValueError:
                    as_of_hours = 24

            from sih26170.screening.equipment import (
                evaluate_fixture_channel_bias,
                evaluate_chamber_excursion,
                CHANNEL_BIAS_Z_THRESHOLD,
            )

            if lot_id == "LOT_DEMO_EXCURSION":
                from sih26170.synthetic.equipment_excursion_demo import generate_equipment_drift_demo_lot
                df = generate_equipment_drift_demo_lot()
            else:
                try:
                    df = self.provider.get_lot_telemetry(lot_id, as_of_hours)
                except Exception as e:
                    return 404, {"error": f"Lot '{lot_id}' not found or telemetry unavailable: {str(e)}"}

            curr_checkpoint_df = df[df["elapsed_hours"] == as_of_hours]
            history_df = df[df["elapsed_hours"] <= as_of_hours]

            # 1. Chamber excursion evaluation for primary parameter RDS(on)
            chamber_ev = evaluate_chamber_excursion("RDS(on)", history_df, as_of_hours)

            # 2. Channel bias evaluation across available channels in the lot
            channels_list = []
            has_suspect_channels = False
            suspect_channels = []
            affected_components = []

            available_channels = sorted(curr_checkpoint_df["channel_id"].dropna().unique().tolist()) if "channel_id" in curr_checkpoint_df.columns else []

            for ch_id in available_channels:
                ch_df = curr_checkpoint_df[curr_checkpoint_df["channel_id"] == ch_id]
                ch_comps = sorted(ch_df["component_id"].unique().tolist())
                ev = evaluate_fixture_channel_bias("RDS(on)", curr_checkpoint_df, ch_id)
                status = "DRIFT_SUSPECTED" if ev.suspected else ("SUPPRESSED" if ev.suppressed else "NOMINAL")
                action = "QUARANTINE_SOCKET_FIXTURE" if ev.suspected else ("SAMPLE_INSUFFICIENT" if ev.suppressed else "ACCEPT_FOR_FLIGHT")

                if ev.suspected:
                    has_suspect_channels = True
                    suspect_channels.append(ch_id)
                    affected_components.extend(ch_comps)

                channels_list.append({
                    "channel_id": ch_id,
                    "n_components": len(ch_comps),
                    "components": ch_comps,
                    "parameter": "RDS(on)",
                    "channel_offset_mohm": round(ev.channel_offset, 4) if ev.channel_offset is not None else 0.0,
                    "z_score": round(ev.z_score, 2) if ev.z_score is not None else 0.0,
                    "critical_threshold": CHANNEL_BIAS_Z_THRESHOLD,
                    "suppressed": ev.suppressed,
                    "suspected": ev.suspected,
                    "status": status,
                    "reason_code": ev.reason_code,
                    "prescribed_action": action,
                })

            if has_suspect_channels:
                sop = {
                    "fixture_status": "EXCURSION_DETECTED",
                    "fixture_action": f"Quarantine socket card ({', '.join(suspect_channels)}). Issue maintenance ticket for pogo pin cleaning & Kelvin 4-wire resistance calibration.",
                    "component_action": f"Mark {len(affected_components)} components as EQUIPMENT_SUSPECTED. Route to non-destructive re-test on alternate socket. Do NOT condemn to scrap.",
                    "lot_action": "Remaining sockets exhibit nominal contact kinetics and are cleared for flight screening.",
                    "capital_preserved_usd": len(affected_components) * 1000,
                }
            else:
                sop = {
                    "fixture_status": "NOMINAL",
                    "fixture_action": "All fixture socket channels within statistical limits (|Z| < 3.42). No fixture maintenance required.",
                    "component_action": "All observed component kinetics reflect intrinsic semiconductor behavior. Proceed with flight screening.",
                    "lot_action": "Lot cleared under standard MIL-PRF-19500 / ISRO qualification protocols.",
                    "capital_preserved_usd": 0,
                }

            return 200, {
                "lot_id": lot_id,
                "as_of_hours": as_of_hours,
                "total_channels": len(available_channels),
                "has_suspect_channels": has_suspect_channels,
                "suspect_channels": suspect_channels,
                "affected_components": affected_components,
                "chamber_evaluation": {
                    "chamber_suspected": chamber_ev.suspected,
                    "lot_median_shift": chamber_ev.lot_median_shift,
                    "fraction_shifting": chamber_ev.fraction_shifting,
                    "reason_code": chamber_ev.reason_code,
                },
                "channels": channels_list,
                "qa_corrective_protocol": sop,
            }

        # Route: Component Endpoints
        # Pattern: /components/{component_id}[/{sub_resource}]
        if len(parts) >= 2 and parts[0] == "components":
            component_id = parts[1]
            sub_resource = parts[2] if len(parts) >= 3 else None

            # 1. Bare /components/{component_id}: Metadata ONLY
            if sub_resource is None:
                if self.uploaded_telemetry is not None and component_id in set(self.uploaded_telemetry["component_id"].astype(str)):
                    df = self.uploaded_telemetry
                    component_df = df[df["component_id"].astype(str) == component_id]
                    return 200, {
                        "component_id": component_id,
                        "lot_id": str(component_df["lot_id"].iloc[0]),
                        "part_number": "USER_SUPPLIED",
                        "source_type": "USER_UPLOADED",
                        "available_checkpoints": sorted(component_df["elapsed_hours"].unique().tolist()),
                        "monitored_parameters": sorted(component_df["parameter_name"].astype(str).unique().tolist()),
                        "note": "Bare component endpoint returns metadata only.",
                    }
                elif component_id.startswith("LOT_DEMO_EXCURSION"):
                    return 200, {
                        "component_id": component_id,
                        "lot_id": "LOT_DEMO_EXCURSION",
                        "part_number": "IRHNJ57130",
                        "slash_sheet": "MIL-PRF-19500/703",
                        "package": "SMD-0.5",
                        "source_type": "SYNTHETIC_EXCURSION_DEMO",
                        "available_checkpoints": [0, 24, 48, 72, 96, 120, 144, 168],
                        "monitored_parameters": ["IDSS", "VGS(th)", "RDS(on)", "IGSS"],
                        "note": (
                            "Bare component endpoint returns metadata only. "
                            "To evaluate screening or prognostics, use /components/{id}/pipeline?as_of=T "
                            "with an explicit as_of query parameter."
                        ),
                    }
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
                if self.uploaded_telemetry is not None and component_id in set(self.uploaded_telemetry["component_id"].astype(str)):
                    from sih26170.pipeline.orchestrator import run_component_pipeline
                    df = self.uploaded_telemetry
                    comp_df = df[(df["component_id"].astype(str) == component_id) & (df["elapsed_hours"] <= as_of_hours)]
                    if comp_df.empty:
                        return 404, {"error": f"Component '{component_id}' has no data at {as_of_hours}h."}
                    lot_id = str(comp_df["lot_id"].iloc[0])
                    lot_df = df[(df["lot_id"].astype(str) == lot_id) & (df["elapsed_hours"] <= as_of_hours)]
                    pipeline_result = run_component_pipeline(comp_df, component_id, as_of_hours, lot_df)
                elif component_id.startswith("LOT_DEMO_EXCURSION"):
                    from sih26170.synthetic.equipment_excursion_demo import generate_equipment_drift_demo_lot
                    from sih26170.pipeline.orchestrator import run_component_pipeline
                    df = generate_equipment_drift_demo_lot()
                    comp_df = df[(df["component_id"] == component_id) & (df["elapsed_hours"] <= as_of_hours)]
                    lot_df = df[df["elapsed_hours"] <= as_of_hours]
                    if comp_df.empty:
                        return 404, {"error": f"Component '{component_id}' not found in LOT_DEMO_EXCURSION"}
                    pipeline_result = run_component_pipeline(
                        telemetry=comp_df,
                        component_id=component_id,
                        as_of_hours=as_of_hours,
                        lot_telemetry=lot_df,
                    )
                else:
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
                from sih26170.pipeline.explainability import build_unified_component_explanation
                unified_exp = build_unified_component_explanation(pipeline_result)
                resp_data["unified_explanation"] = unified_exp
                resp_data["inspector_justification"] = unified_exp["inspector_justification"]
                resp_data["counterfactuals"] = {
                    p: p_data["counterfactual"] for p, p_data in unified_exp["prognostics"].items()
                }
                resp_data["known_limitations"] = unified_exp["known_limitations"]

                if self.uploaded_telemetry is not None and component_id in set(self.uploaded_telemetry["component_id"].astype(str)):
                    df = self.uploaded_telemetry
                    comp_df = df[(df["component_id"].astype(str) == component_id) & (df["elapsed_hours"] <= as_of_hours)]
                    resp_data["observed_telemetry"] = comp_df[
                        ["elapsed_hours", "parameter_name", "value", "unit"]
                    ].to_dict(orient="records")
                elif component_id.startswith("LOT_DEMO_EXCURSION"):
                    from sih26170.synthetic.equipment_excursion_demo import generate_equipment_drift_demo_lot
                    df = generate_equipment_drift_demo_lot()
                    comp_df = df[(df["component_id"] == component_id) & (df["elapsed_hours"] <= as_of_hours)]
                    resp_data["observed_telemetry"] = comp_df[
                        ["elapsed_hours", "parameter_name", "value", "unit"]
                    ].to_dict(orient="records")
                else:
                    try:
                        comp_tel = self.provider.get_component_telemetry(component_id, as_of_hours)
                        resp_data["observed_telemetry"] = comp_tel[
                            ["elapsed_hours", "parameter_name", "value", "unit"]
                        ].to_dict(orient="records")
                    except Exception:
                        resp_data["observed_telemetry"] = []
                return 200, resp_data
            elif sub_resource == "explain":
                from sih26170.pipeline.explainability import build_unified_component_explanation
                return 200, build_unified_component_explanation(pipeline_result)
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
