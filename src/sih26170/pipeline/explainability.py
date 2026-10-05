"""Engineering explainability card generator for SIH26170 Engineering Prototype.

Complies strictly with post-Phase-5 engineering integration specifications:
- Concrete physical evidence instead of AI buzzwords (zero 'AI confidence', 'AI thinks').
- Answers the 8 canonical engineering questions:
    1. WHAT happened?
    2. WHY was the component flagged?
    3. WHICH parameter caused concern?
    4. WHAT evidence supports it?
    5. WHAT did the model predict?
    6. HOW uncertain is the prediction?
    7. WAS equipment/common-mode evidence present?
    8. WHAT information was available as-of the decision?
- Decouples measured specification status from predictive breach flags.
- Emphasizes: PREDICTIVE EVIDENCE ONLY — NO AUTONOMOUS REJECTION.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd

from sih26170.pipeline.schema import (
    EngineeringExplainability,
    ForecastInterpretation,
    ORDERED_PARAMETERS,
)
from sih26170.screening.schema import ComponentScreeningResult, ScreeningState
from sih26170.prognostics.schema import PrognosticForecast


def build_engineering_explainability(
    component_id: str,
    lot_id: str,
    as_of_hours: int,
    screening_result: ComponentScreeningResult,
    prognostic_forecasts: Dict[str, PrognosticForecast],
    interpretations: Dict[str, ForecastInterpretation],
    input_telemetry: pd.DataFrame,
) -> EngineeringExplainability:
    """Construct structured and plain-language engineering explainability object."""
    state = screening_result.final_state.value
    qualifier = screening_result.disposition_qualifier.value
    reasons = screening_result.reason_codes

    # 1. WHAT happened?
    what_happened = (
        f"Component '{component_id}' (Lot '{lot_id}') evaluated at T={as_of_hours}h: "
        f"Screening State = [{state}], Disposition Qualifier = [{qualifier}]. "
        f"Locked Ridge regression generated 168h prognostics for {len(prognostic_forecasts)} parameter(s)."
    )

    # 2. WHY was the component flagged?
    flagged_params: List[str] = []
    breached_params: List[str] = []
    pred_breached_params: List[str] = []

    for p, res in screening_result.parameter_results.items():
        if res.parameter_state in (ScreeningState.ALERT, ScreeningState.FAIL):
            flagged_params.append(f"{p} ({res.primary_reason_code})")
        if not res.spec_evidence.passed:
            breached_params.append(p)

    for p, interp in interpretations.items():
        if interp.predicted_spec_breach:
            pred_breached_params.append(p)

    if state == "PASS":
        why_flagged = "Component showed nominal behavior across all parameters with zero specification breaches."
    elif state == "HOLD":
        why_flagged = (
            "Component placed on engineering quarantine HOLD pending second-pass re-test or Material Review Board (MRB) review. "
            "Space hardware is preserved from premature scrap."
        )
    elif state == "EQUIPMENT_SUSPECTED":
        why_flagged = (
            "Screening flagged common-mode equipment/chamber motion; "
            "individual component degradation cannot be confirmed without re-test."
        )
    elif state == "FAIL":
        why_flagged = (
            f"Component violated hard specification limits on parameter(s): {', '.join(breached_params)}."
        )
    elif state == "INSUFFICIENT_DATA":
        why_flagged = "Available telemetry did not satisfy minimum checkpoint or history requirements."
    else:
        why_flagged = f"Screening alerts triggered on: {', '.join(flagged_params)}."

    # 3. WHICH parameter caused concern?
    which_parameter = flagged_params[0].split()[0] if flagged_params else (
        breached_params[0] if breached_params else (
            pred_breached_params[0] if pred_breached_params else None
        )
    )

    # 4. WHAT evidence supports it?
    what_evidence: Dict[str, Any] = {}
    for p in ORDERED_PARAMETERS:
        if p in screening_result.parameter_results:
            pres = screening_result.parameter_results[p]
            what_evidence[p] = {
                "observed_value": pres.observed_value,
                "unit": pres.unit,
                "parameter_state": pres.parameter_state.value,
                "D_spec": pres.spec_evidence.status.value,
                "D_peer": pres.peer_evidence.status.value,
                "D_drift": pres.temporal_evidence.status.value,
                "D_step": pres.step_evidence.status.value,
                "D_eq": pres.equipment_evidence.status.value,
                "D_suff": pres.sufficiency_evidence.status.value,
                "peer_z_score": pres.peer_evidence.z_score,
                "theil_sen_slope_per_hour": pres.temporal_evidence.slope_per_hour,
                "g_excess": pres.temporal_evidence.g_excess,
                "step_ratio_J": pres.step_evidence.step_ratio,
            }

    # 5. WHAT did the model predict?
    what_predicted: Dict[str, Any] = {}
    how_uncertain: Dict[str, Any] = {}
    for p in ORDERED_PARAMETERS:
        if p in prognostic_forecasts:
            fc = prognostic_forecasts[p]
            shap_info = fc.metadata.get("shap", {})
            what_predicted[p] = {
                "target_hours": fc.target_hours,
                "predicted_value": fc.predicted_value,
                "unit": fc.unit,
                "forecast_change_from_as_of": fc.forecast_change_from_origin,
                "baseline_relative_change": fc.baseline_relative_forecast_change,
                "is_divergent_fallback": fc.is_divergent_fallback,
                "model_id": fc.model_id,
                "shap_attributions": fc.shap_attributions or shap_info.get("shap_values"),
                "primary_driver": fc.primary_driver or shap_info.get("primary_driver"),
                "shap_explanation": shap_info.get("explanation"),
            }
            how_uncertain[p] = {
                "interval_90_lower": fc.interval_lower,
                "interval_90_upper": fc.interval_upper,
                "interval_width": fc.interval_width,
                "sigma_eff": fc.sigma_eff,
                "coverage_nominal": 0.90,
                "coverage_disclaimer": "Nominal coverage is a population property; no individual sample guarantee.",
            }

    # 7. WAS equipment/common-mode evidence present?
    was_equipment_present = False
    eq_details: Dict[str, Any] = {}
    for p, pres in screening_result.parameter_results.items():
        if pres.equipment_evidence.suspected:
            was_equipment_present = True
        eq_details[p] = {
            "status": pres.equipment_evidence.status.value,
            "suspected": pres.equipment_evidence.suspected,
            "lot_median_shift": pres.equipment_evidence.lot_median_shift,
            "fraction_shifting": pres.equipment_evidence.fraction_shifting,
            "channel_offset": pres.equipment_evidence.channel_offset,
        }

    # 8. WHAT information was available as-of the decision?
    available_checkpoints = sorted(input_telemetry["elapsed_hours"].unique().tolist())
    what_info_available_as_of = {
        "as_of_hours": as_of_hours,
        "available_checkpoints": available_checkpoints,
        "total_records_used": len(input_telemetry),
        "quarantine_guarantee": "Elapsed hours strictly <= as_of_hours; future checkpoints quarantined.",
    }

    # ASCII Summary Card
    ascii_lines = [
        "================================================================================",
        "             ENGINEERING PROTOTYPE SCREENING & PROGNOSTIC EVIDENCE CARD        ",
        "================================================================================",
        f"Component ID       : {component_id}",
        f"Lot ID             : {lot_id}",
        f"As-Of Checkpoint   : {as_of_hours}h (Historical filter: elapsed_hours <= {as_of_hours})",
        f"FINAL SCREENING    : {state}",
        f"Disposition Qual.  : {qualifier}",
        f"Primary Reason Code: {screening_result.primary_reason_code}",
        f"Equipment Suspected: {was_equipment_present}",
        "--------------------------------------------------------------------------------",
        "PARAMETER-BY-PARAMETER EVIDENCE & PROGNOSTIC FORECASTS:",
    ]

    for p in ORDERED_PARAMETERS:
        if p in what_evidence:
            ev = what_evidence[p]
            fc = what_predicted.get(p, {})
            unc = how_uncertain.get(p, {})
            interp = interpretations.get(p)

            pred_val = fc.get("predicted_value")
            pred_str = f"{pred_val:.4f} {ev['unit']}" if pred_val is not None else "N/A"
            low = unc.get("interval_90_lower")
            upp = unc.get("interval_90_upper")
            int_str = f"[{low:.4f}, {upp:.4f}]" if low is not None and upp is not None else "N/A"

            safety_note = ""
            if interp and getattr(interp, 'early_rejection_flag', False):
                dr = getattr(interp, 'predicted_drift_rate', 0.0) or 0.0
                ss = getattr(interp, 'calculated_safety_slope', 0.0) or 0.0
                safety_note = f" [EARLY REJECT: Drift Rate ({dr:+.5f}) > Safety Slope ({ss:+.5f})]"
            elif interp and getattr(interp, 'calculated_safety_slope', None) is not None:
                dr = getattr(interp, 'predicted_drift_rate', 0.0) or 0.0
                ss = getattr(interp, 'calculated_safety_slope', 0.0) or 0.0
                safety_note = f" [CONTINUE: Drift Rate ({dr:+.5f}) <= Safety Slope ({ss:+.5f})]"
            elif interp and interp.predicted_spec_breach:
                safety_note = " [PREDICTED SPEC BREACH AT 168h]"

            lines_to_add = [
                f"  [{p}]: Observed = {ev['observed_value']:.4f} {ev['unit']} | State = {ev['parameter_state']}",
                f"       Screening: D_spec={ev['D_spec']}, D_drift={ev['D_drift']}, D_peer={ev['D_peer']}, D_eq={ev['D_eq']}",
                f"       Ridge 168h Forecast: {pred_str} | 90% PI: {int_str}{safety_note}",
            ]
            if fc.get("shap_explanation"):
                lines_to_add.append(f"       Linear SHAP Driver: {fc['shap_explanation']}")
            ascii_lines.extend(lines_to_add)

    ascii_lines.extend([
        "--------------------------------------------------------------------------------",
        "EPISTEMIC BOUNDARY & DISPOSITION POLICY:",
        "  - Measured spec failures represent objective as-of test results.",
        "  - Predicted future breaches are prognostic informational evidence only.",
        "  - Zero autonomous scrap or rejection is authorized based on predictions.",
        "================================================================================",
    ])
    ascii_summary = "\n".join(ascii_lines)

    return EngineeringExplainability(
        what_happened=what_happened,
        why_flagged=why_flagged,
        which_parameter=which_parameter,
        what_evidence=what_evidence,
        what_predicted=what_predicted,
        how_uncertain=how_uncertain,
        was_equipment_present=was_equipment_present,
        equipment_details=eq_details,
        what_info_available_as_of=what_info_available_as_of,
        ascii_summary=ascii_summary,
    )
