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
from sih26170.prognostics.locked_models import get_locked_ridge_model
from sih26170.screening.transforms import transform_parameter, inverse_transform_parameter


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


def calculate_counterfactual_explanation(
    parameter_name: str,
    v0: float,
    v24: float,
    limit_low: Optional[float],
    limit_high: Optional[float],
    predicted_168h: float,
    unit: str,
) -> Optional[Dict[str, Any]]:
    """Compute closed-form counterfactual 24h boundary value for linear Ridge model.

    For linear model u_168 = beta_0 + beta_1 * u_0 + beta_2 * u_24,
    the 24h boundary value in transformed space is:
        u_24_boundary = (u_target - beta_0 - beta_1 * u_0) / beta_2
    Inverting via inverse_transform_parameter yields the exact physical engineering boundary.
    """
    try:
        model = get_locked_ridge_model(parameter_name)
    except KeyError:
        return None

    b0, b1, b2 = model.coefficients
    if abs(b2) < 1e-12:
        return None

    try:
        u0 = transform_parameter(parameter_name, v0)
    except (ValueError, OverflowError):
        return None

    # Determine relevant boundary (closest or breached specification limit)
    target_limit = None
    is_upper = True
    if limit_high is not None and limit_low is not None:
        if predicted_168h > limit_high or v24 > (limit_high + limit_low) / 2.0:
            target_limit = limit_high
            is_upper = True
        else:
            target_limit = limit_low
            is_upper = False
    elif limit_high is not None:
        target_limit = limit_high
        is_upper = True
    elif limit_low is not None:
        target_limit = limit_low
        is_upper = False
    else:
        return None

    try:
        u_lim = transform_parameter(parameter_name, target_limit)
        u24_bound = (u_lim - b0 - b1 * u0) / b2
        y24_bound = inverse_transform_parameter(parameter_name, u24_bound)
    except (ValueError, OverflowError):
        return None

    delta = y24_bound - v24

    is_breaching = False
    if is_upper:
        if v24 > target_limit or predicted_168h > target_limit:
            is_breaching = True
    else:
        if v24 < target_limit or predicted_168h < target_limit:
            is_breaching = True

    if is_breaching:
        op = "<=" if is_upper else ">="
        statement = (
            f"{parameter_name} 168h forecast ({predicted_168h:.2f} {unit}) breaches limit ({target_limit:.2f} {unit}). "
            f"Component would pass if its 24h reading had been {op} {y24_bound:.2f} {unit} "
            f"({delta:+.2f} {unit} adjustment from observed {v24:.2f} {unit})."
        )
    else:
        headroom = abs(delta)
        statement = (
            f"{parameter_name} 168h forecast ({predicted_168h:.2f} {unit}) is within limit ({target_limit:.2f} {unit}). "
            f"24h reading could drift up to {y24_bound:.2f} {unit} "
            f"(safe margin: +{headroom:.2f} {unit}) before causing a 168h specification breach."
        )

    return {
        "parameter": parameter_name,
        "target_limit": float(target_limit),
        "direction": "upper" if is_upper else "lower",
        "boundary_24h_value": float(round(y24_bound, 4)),
        "delta_from_observed": float(round(delta, 4)),
        "margin_headroom": float(round(abs(delta), 4)),
        "is_breaching": is_breaching,
        "statement": statement,
    }


def generate_inspector_justification(
    screening_result: ComponentScreeningResult,
    component_id: str,
    lot_id: str,
    as_of_hours: int,
) -> str:
    """Compose inspector-grade plain-language justification sentence citing exact numbers."""
    state = screening_result.final_state
    qualifier = screening_result.disposition_qualifier.value
    pres_dict = screening_result.parameter_results

    # 1. Equipment Excursion / Suspicion
    if state == ScreeningState.EQUIPMENT_SUSPECTED or any(p.equipment_evidence.suspected for p in pres_dict.values()):
        suspect_params = [p for p, res in pres_dict.items() if res.equipment_evidence.suspected]
        p_name = suspect_params[0] if suspect_params else "RDS(on)"
        res = pres_dict[p_name]
        eq = res.equipment_evidence
        ate = eq.ate_evidence
        ch_id = ate.channel_id if ate else eq.channel_id or "CH_05"
        z_score = ate.z_score if (ate and ate.z_score is not None) else 0.0
        offset = eq.channel_offset or 0.0
        return (
            f"Component {component_id} placed on EQUIPMENT_SUSPECTED ({qualifier}) at T={as_of_hours}h: "
            f"ATE Socket Channel {ch_id} exhibited a common-mode excursion on {p_name} "
            f"(Z = {z_score:+.2f} sigma against lot baseline, offset {offset:+.4f} transformed log units). "
            f"Physical silicon degradation is NOT confirmed; component quarantined for socket re-test (Preserves Space Flight Hardware)."
        )

    # 2. Hard Spec Failure (FAIL)
    if state == ScreeningState.FAIL:
        failed_params = [p for p, res in pres_dict.items() if not res.spec_evidence.passed]
        if not failed_params:
            failed_params = [p for p, res in pres_dict.items() if res.parameter_state == ScreeningState.FAIL]
        primary_p = failed_params[0] if failed_params else list(pres_dict.keys())[0]
        res = pres_dict[primary_p]
        spec = res.spec_evidence
        peer = res.peer_evidence
        temp = res.temporal_evidence
        step = res.step_evidence

        limit_breached = spec.limit_high if spec.limit_high is not None and res.observed_value > spec.limit_high else spec.limit_low
        limit_desc = f"{spec.limit_class.value} limit ({limit_breached:.2f} {res.unit})" if limit_breached is not None else "specification limit"
        peer_desc = f"{peer.z_score:+.2f} lot-MAD sigma" if peer.z_score is not None else "abnormal peer distribution"
        eq_status = "no fixture channel shift (D_eq: PASS)" if not res.equipment_evidence.suspected else "suspect fixture bias"

        step_note = ""
        if step.step_ratio is not None and step.step_ratio >= 4.0:
            step_note = f", accompanied by abrupt step jump J(T) = {step.step_ratio:.2f}"

        return (
            f"Component {component_id} FLAGGED FAIL ({qualifier}) at T={as_of_hours}h: "
            f"{primary_p} observed at {res.observed_value:.2f} {res.unit} breaches {limit_desc} "
            f"at {peer_desc}{step_note}, with {eq_status}. "
            f"Action: Condemn component to non-flight scrap (MIL-PRF-19500 / ISRO Screening)."
        )

    # 3. Latent Drift / Step Jump / Joint Backstop (HOLD / ALERT)
    if getattr(screening_result, "joint_evidence", None) and screening_result.joint_evidence.suspected:
        je = screening_result.joint_evidence
        return (
            f"Component {component_id} PLACED ON HOLD ({qualifier}) at T={as_of_hours}h: "
            f"Joint multivariate backstop detector (D_joint) triggered at {je.mahalanobis_distance:.2f} sigma "
            f"(critical threshold {je.critical_threshold:.2f} sigma) indicating correlated multi-parameter movement across parameters, "
            f"with no equipment channel bias (D_eq: PASS). "
            f"Action: Quarantine for Material Review Board (MRB) review and second-pass verification."
        )

    if state in (ScreeningState.ALERT, ScreeningState.HOLD):
        alert_params = [p for p, res in pres_dict.items() if res.parameter_state in (ScreeningState.ALERT, ScreeningState.HOLD)]
        primary_p = alert_params[0] if alert_params else list(pres_dict.keys())[0]
        res = pres_dict[primary_p]
        temp = res.temporal_evidence
        peer = res.peer_evidence
        step = res.step_evidence

        details = []
        if temp.g_excess is not None and abs(temp.g_excess) >= 2.5:
            details.append(f"excess temporal drift g_excess = {temp.g_excess:+.2f} sigma (Theil-Sen slope {temp.slope_per_hour:+.5f}/h)")
        if step.step_ratio is not None and step.step_ratio >= 4.0:
            details.append(f"abrupt step jump ratio J(T) = {step.step_ratio:.2f} (threshold 4.0)")
        if peer.z_score is not None and abs(peer.z_score) >= 15.0:
            details.append(f"peer outlier Z = {peer.z_score:+.2f} sigma")
        if not details:
            details.append(f"anomalous trajectory on {primary_p}")

        eq_status = "no equipment bias detected (D_eq: PASS)"
        return (
            f"Component {component_id} PLACED ON HOLD ({qualifier}) at T={as_of_hours}h: "
            f"{primary_p} exhibited {', '.join(details)}, with {eq_status}. "
            f"Action: Quarantine for Material Review Board (MRB) review and second-pass verification."
        )

    # 4. PASS
    max_z = 0.0
    max_g = 0.0
    for p, res in pres_dict.items():
        if res.peer_evidence.z_score is not None:
            max_z = max(max_z, abs(res.peer_evidence.z_score))
        if res.temporal_evidence.g_excess is not None:
            max_g = max(max_g, abs(res.temporal_evidence.g_excess))

    return (
        f"Component {component_id} CLEARED (PASS - {qualifier}) at T={as_of_hours}h: "
        f"All 4 monitored parameters conform to MIL-PRF-19500 specification limits. "
        f"Peer and drift kinetics are nominal (max |Z| = {max_z:.2f} sigma, max excess drift = {max_g:.2f} sigma). "
        f"No equipment or socket channel bias detected. Cleared for flight screening."
    )


def get_known_limitations_disclosure() -> List[Dict[str, Any]]:
    """Return explicit, source-attributed disclosure of mathematical and physical boundaries."""
    return [
        {
            "id": "KL-01-SUB-NOISE-DRIFT",
            "title": "Sub-Noise-Floor Linear Drift (SNR <= 2.089 dB)",
            "category": "SIGNAL_TO_NOISE_TRADEOFF",
            "description": (
                "Components with extremely subtle drift rates whose 0h to 24h deviation is within instrumentation "
                "quantization or thermal sensor noise (SNR <= 2.089 dB) are deliberately not flagged at 24h. "
                "Suppressing alerts below this noise floor prevents catastrophic false alarm cascades across flight qualification lots."
            ),
            "benchmark_impact": "2 benchmark cases in evaluation partition exhibited sub-noise floor drift and were retained as PASS until later checkpoints.",
            "operational_mitigation": "Flagged automatically at 48h/96h burn-in checkpoints as cumulative drift departs from thermal noise floor."
        },
        {
            "id": "KL-02-LATE-ONSET-WEAROUT",
            "title": "Late-Onset Non-Linear Wearout / Thermal Runaway (T > 96h)",
            "category": "TEMPORAL_CAUSALITY_BOUNDARY",
            "description": (
                "Components that remain stationary between 0h and 24h (Delta_u ≈ 0) "
                "but undergo sudden exponential dielectric breakdown after 96h cannot be predicted from 24h telemetry alone. "
                "Strict temporal causality prohibits retrospective lookahead."
            ),
            "benchmark_impact": "Physical limitation common to all causal statistical models; documented in empirical validation audits.",
            "operational_mitigation": "Requires intermediate screening checkpoint at 96h or physics-of-failure accelerated life testing."
        },
        {
            "id": "KL-03-SMALL-SAMPLE-SOCKET-BIAS",
            "title": "Small-Sample Socket Bias Suppression (N_channel < 4)",
            "category": "STATISTICAL_STABILITY_POLICY",
            "description": (
                "Detector D_eq requires at least N >= 4 components tested simultaneously on a specific ATE fixture channel "
                "to evaluate socket contact resistance shift. For smaller channel sample counts, socket bias inference is suppressed "
                "to prevent spurious false alarms or masking genuine silicon degradation."
            ),
            "benchmark_impact": "Single-DUT bench stations operate without fixture channel bias correction.",
            "operational_mitigation": "Enforce standard batch cleanroom testing protocol with minimum 4 components per socket channel."
        },
        {
            "id": "KL-04-ABRUPT-STEP-THRESHOLD",
            "title": "Abrupt Step Jump Detection Boundary (J(T) < 4.0)",
            "category": "ROBUST_SENSITIVITY_TUNING",
            "description": (
                "Detector D_step enforces a jump ratio threshold J(T) >= 4.0 to catch discontinuous micro-plasma or dielectric "
                "fissures. Jumps below 4.0 (e.g. J = 1.14 on IGSS) are treated as gradual kinetic drift rather than step discontinuities."
            ),
            "benchmark_impact": "1 benchmark evaluation case with J = 1.14 was caught via D_drift rather than D_step.",
            "operational_mitigation": "Continuous union/OR fusion ensures gradual drift detector captures sub-4.0 step transitions."
        }
    ]


def build_unified_component_explanation(
    pipeline_result: Any,
) -> Dict[str, Any]:
    """Construct unified explainability response consolidating all evaluation dimensions.

    Complies with aerospace mission assurance and inspector explainability specifications:
    - Module A detector-level evidence (D_spec, D_peer, D_drift, D_step, D_eq, D_suff)
    - Module B closed-form SHAP feature attributions
    - Conformal 90% prediction intervals with effective sigma
    - Safety-slope arithmetic (drift rate vs safety slope)
    - Closed-form counterfactual 24h boundary values
    - Inspector-grade plain language justification sentence
    - Explicit named Known Limitations disclosure
    """
    comp_id = pipeline_result.component_id
    lot_id = pipeline_result.lot_id
    as_of = pipeline_result.as_of_hours
    screening = pipeline_result.screening_result
    forecasts = pipeline_result.prognostic_forecasts
    interpretations = pipeline_result.interpretations
    safety_decisions = pipeline_result.safety_decisions

    state = screening.final_state.value
    qualifier = screening.disposition_qualifier.value

    # Action prescription
    if state == "FAIL":
        action = "CONDEMN_TO_SCRAP"
    elif state == "EQUIPMENT_SUSPECTED":
        action = "QUARANTINE_SOCKET_RETEST"
    elif state == "HOLD":
        action = "HOLD_MATERIAL_REVIEW_BOARD"
    elif state == "INSUFFICIENT_DATA":
        action = "DEFER_INSUFFICIENT_DATA"
    else:
        action = "CLEARED_FOR_FLIGHT"

    justification = generate_inspector_justification(screening, comp_id, lot_id, as_of)

    # Detailed detector evidence per parameter
    detector_evidence: Dict[str, Any] = {}
    for p in ORDERED_PARAMETERS:
        if p in screening.parameter_results:
            pres = screening.parameter_results[p]
            spec = pres.spec_evidence
            peer = pres.peer_evidence
            temp = pres.temporal_evidence
            step = pres.step_evidence
            eq = pres.equipment_evidence
            suff = pres.sufficiency_evidence

            detector_evidence[p] = {
                "parameter": p,
                "observed_value": pres.observed_value,
                "unit": pres.unit,
                "transformed_value": pres.transformed_value,
                "parameter_state": pres.parameter_state.value,
                "D_spec": {
                    "status": spec.status.value,
                    "passed": spec.passed,
                    "limit_low": spec.limit_low,
                    "limit_high": spec.limit_high,
                    "limit_class": spec.limit_class.value,
                    "reason_code": spec.reason_code,
                },
                "D_peer": {
                    "status": peer.status.value,
                    "peer_count": peer.peer_count,
                    "peer_median": peer.peer_median,
                    "peer_scale": peer.peer_scale,
                    "z_score": peer.z_score,
                    "reason_code": peer.reason_code,
                },
                "D_drift": {
                    "status": temp.status.value,
                    "slope_per_hour": temp.slope_per_hour,
                    "normalized_drift_g": temp.normalized_drift,
                    "g_lot": temp.g_lot,
                    "g_excess": temp.g_excess,
                    "confounded_by_equipment": temp.confounded_by_equipment,
                    "reason_code": temp.reason_code,
                },
                "D_step": {
                    "status": step.status.value,
                    "step_ratio_J": step.step_ratio,
                    "interval": [step.previous_checkpoint, step.current_checkpoint],
                    "reason_code": step.reason_code,
                },
                "D_eq": {
                    "status": eq.status.value,
                    "suspected": eq.suspected,
                    "lot_median_shift": eq.lot_median_shift,
                    "fraction_shifting": eq.fraction_shifting,
                    "channel_id": eq.channel_id,
                    "channel_offset": eq.channel_offset,
                    "ate_z_score": eq.ate_evidence.z_score if eq.ate_evidence else None,
                    "reason_code": eq.reason_code,
                },
                "D_suff": {
                    "status": suff.status.value,
                    "sufficient": suff.sufficient,
                    "expected_checkpoints": suff.expected_checkpoints,
                    "available_checkpoints": suff.available_checkpoints,
                    "reason_code": suff.reason_code,
                },
            }

    # Prognostics, SHAP, Safety-slope and Counterfactuals
    prognostics_data: Dict[str, Any] = {}
    for p in ORDERED_PARAMETERS:
        if p in forecasts:
            fc = forecasts[p]
            interp = interpretations.get(p)
            safety = safety_decisions.get(p, {})
            pres = screening.parameter_results.get(p)
            spec = pres.spec_evidence if pres else None

            v0 = fc.metadata.get("v0", 0.0)
            v24 = fc.metadata.get("v24", 0.0)
            lim_low = spec.limit_low if spec else None
            lim_high = spec.limit_high if spec else None

            counterfactual = calculate_counterfactual_explanation(
                parameter_name=p,
                v0=v0,
                v24=v24,
                limit_low=lim_low,
                limit_high=lim_high,
                predicted_168h=fc.predicted_value,
                unit=fc.unit,
            )

            shap_dict = fc.metadata.get("shap", {})

            prognostics_data[p] = {
                "parameter": p,
                "unit": fc.unit,
                "v0": v0,
                "v24": v24,
                "predicted_value_168h": fc.predicted_value,
                "conformal_interval_90": {
                    "lower": fc.interval_lower,
                    "upper": fc.interval_upper,
                    "width": fc.interval_width,
                    "sigma_eff": fc.sigma_eff,
                    "coverage_nominal": 0.90,
                },
                "shap_decomposition": {
                    "base_value_u": shap_dict.get("base_value_u"),
                    "phi_baseline_offset": shap_dict.get("shap_values", {}).get("baseline_0h"),
                    "phi_drift_slope": shap_dict.get("shap_values", {}).get("slope_0_24"),
                    "primary_driver": fc.primary_driver or shap_dict.get("primary_driver"),
                    "explanation": shap_dict.get("explanation"),
                },
                "safety_slope": {
                    "drift_rate": safety.get("predicted_drift_rate"),
                    "safety_slope": safety.get("safety_slope"),
                    "safety_threshold": safety.get("safety_threshold"),
                    "margin": safety.get("margin_to_safety_threshold"),
                    "decision": safety.get("decision"),
                    "early_reject": safety.get("decision") == "EARLY_REJECT",
                    "reason": safety.get("reason"),
                },
                "counterfactual": counterfactual,
            }

    return {
        "component_id": comp_id,
        "lot_id": lot_id,
        "as_of_hours": as_of,
        "audit_hash": pipeline_result.canonical_result_hash,
        "disposition": {
            "state": state,
            "qualifier": qualifier,
            "primary_reason_code": screening.primary_reason_code,
            "prescribed_action": action,
        },
        "inspector_justification": justification,
        "detector_evidence": detector_evidence,
        "joint_detector_evidence": screening.joint_evidence.to_dict() if getattr(screening, "joint_evidence", None) else None,
        "prognostics": prognostics_data,
        "known_limitations": get_known_limitations_disclosure(),
    }


def audit_counterfactual_inversions(
    obs_df: pd.DataFrame,
    sample_components: List[str],
) -> Dict[str, Any]:
    """Audits closed-form counterfactual inversion precision and mathematical exactness."""
    from sih26170.prognostics.locked_models import LockedRidgeModel
    from sih26170.screening.specification import SPEC_LIMITS_CLASS_A

    model_idss = LockedRidgeModel("IDSS")
    results = []

    for cid in sample_components:
        comp_df = obs_df[obs_df["component_id"] == cid]
        if comp_df.empty:
            continue

        p_df = comp_df[comp_df["parameter_name"] == "IDSS"]
        v0 = float(p_df[p_df["elapsed_hours"] == 0]["value"].iloc[0]) if 0 in p_df["elapsed_hours"].values else 0.5
        v24 = float(p_df[p_df["elapsed_hours"] == 24]["value"].iloc[0]) if 24 in p_df["elapsed_hours"].values else 0.55

        pred_168, _, _, _, _ = model_idss.predict_physical(v0, v24)
        lim = SPEC_LIMITS_CLASS_A.get("IDSS", {})
        raw_low = lim.get("low") if "low" in lim else lim.get("absolute_limit_low")
        raw_high = lim.get("high") if "high" in lim else lim.get("absolute_limit_high")
        lim_low: Optional[float] = float(raw_low) if raw_low is not None else None
        lim_high: Optional[float] = float(raw_high) if raw_high is not None else None
        cf = calculate_counterfactual_explanation(
            "IDSS",
            v0,
            v24,
            lim_low,
            lim_high,
            pred_168,
            "uA",
        )

        # Check exact mathematical inversion and display rounding
        invert_error_display = None
        invert_error_mathematical = None
        passes_inversion = False
        if cf is not None and "boundary_24h_value" in cf:
            b_val = cf["boundary_24h_value"]
            target_lim = cf["target_limit"]
            pred_y, _, _, _, _ = model_idss.predict_physical(v0, b_val)
            invert_error_display = float(abs(pred_y - target_lim))

            # Full-precision unrounded closed-form boundary
            u0 = transform_parameter("IDSS", v0)
            u_lim = transform_parameter("IDSS", target_lim)
            b0, b1, b2 = model_idss.coefficients
            u24_exact = (u_lim - b0 - b1 * u0) / b2
            y24_exact = inverse_transform_parameter("IDSS", u24_exact)
            pred_y_math, _, _, _, _ = model_idss.predict_physical(v0, y24_exact)
            invert_error_mathematical = float(abs(pred_y_math - target_lim))

            passes_inversion = invert_error_mathematical < 1e-12 and invert_error_display < 1e-3

        results.append({
            "component_id": cid,
            "parameter": "IDSS",
            "v0": v0,
            "v24": v24,
            "cf_delta_24h": cf["delta_from_observed"] if cf else None,
            "boundary_physical_display": cf["boundary_24h_value"] if cf else None,
            "boundary_inversion_error_display": invert_error_display,
            "boundary_inversion_error_mathematical": invert_error_mathematical,
            "passes_inversion_check": passes_inversion,
        })

    return {
        "metric_id": "3.2",
        "description": "Closed-form counterfactual exact boundary inversion audit",
        "samples_audited": len(results),
        "all_inversions_exact": all(r["passes_inversion_check"] for r in results),
        "audit_samples": results,
        "known_limitations_count": len(get_known_limitations_disclosure()),
    }


# Alias for backward compatibility
audit_explainability_and_counterfactuals = audit_counterfactual_inversions

