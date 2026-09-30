"""Deterministic Explainability Card Generator for Module A.

Compliant with docs/PHASE_3A_MODULE_A_SPEC.md Sections 11 & 13 & Phase 3C Pre-Implementation Amendments:
- Fully deterministic, self-contained evidence card
- Obeying strict as-of historical boundary (no lookahead fields)
- Human-readable ASCII layout and machine-readable dictionary representation
- Every field traceable to explicit detector outputs and specification provenance
- Preserves epistemic distinctions between equipment suspicion, component health,
  and confounded wearout kinetics
"""

from __future__ import annotations

from typing import Any, Dict
from sih26170.screening.schema import (
    ComponentScreeningResult,
    ParameterScreeningResult,
)


def format_parameter_card(
    component_id: str,
    lot_id: str,
    checkpoint: int,
    res: ParameterScreeningResult,
) -> str:
    """Format single parameter evaluation into standard explainability ASCII block."""
    spec = res.spec_evidence
    peer = res.peer_evidence
    temp = res.temporal_evidence
    step = res.step_evidence
    eq = res.equipment_evidence
    suff = res.sufficiency_evidence

    lim_low_str = f"{spec.limit_low}" if spec.limit_low is not None else "None"
    lim_high_str = f"{spec.limit_high}" if spec.limit_high is not None else "None"
    peer_med_str = f"{peer.peer_median:.4f}" if peer.peer_median is not None else "N/A"
    peer_scale_str = f"{peer.peer_scale:.4f}" if peer.peer_scale is not None else "N/A"
    z_str = f"{peer.z_score:+.3f}" if peer.z_score is not None else "N/A"
    slope_str = f"{temp.slope_per_hour:+.6f}" if temp.slope_per_hour is not None else "N/A"
    g_str = f"{temp.normalized_drift:+.3f}" if temp.normalized_drift is not None else "N/A"
    g_lot_str = f"{temp.g_lot:+.3f}" if temp.g_lot is not None else "N/A"
    g_excess_str = f"{temp.g_excess:+.3f}" if temp.g_excess is not None else "N/A"
    accel_str = f"{temp.acceleration_evidence:+.6f}" if temp.acceleration_evidence is not None else "N/A"
    j_str = f"{step.step_ratio:.3f}" if step.step_ratio is not None else "N/A"

    chamber_shift_str = f"{eq.lot_median_shift:+.4f}" if eq.lot_median_shift is not None else "N/A"
    frac_shift_str = f"{eq.fraction_shifting:.1%}" if eq.fraction_shifting is not None else "N/A"
    chan_offset_str = f"{eq.channel_offset:+.4f}" if eq.channel_offset is not None else "N/A"
    ate_z_str = f"{eq.ate_evidence.z_score:+.3f}" if (eq.ate_evidence and eq.ate_evidence.z_score is not None) else "N/A"
    ate_supp_str = f"{eq.ate_evidence.suppressed}" if eq.ate_evidence else "N/A"

    card = [
        "--------------------------------------------------------------------------------",
        f"PARAMETER: {res.parameter} | RAW VALUE: {res.observed_value:.4f} {res.unit} | TRANSFORMED: {res.transformed_value:.4f}",
        f"  DISPOSITION QUALIFIER: {res.disposition_qualifier.value}",
        "--------------------------------------------------------------------------------",
        f"  SPECIFICATION (D_spec): [{spec.status.value}] Passed: {spec.passed}",
        f"    Limits: [{lim_low_str}, {lim_high_str}] | Class: {spec.limit_class.value}",
        f"    Provenance: {spec.provenance}",
        f"    Reason Code: {spec.reason_code}",
        f"  PEER CONTEXT (D_peer): [{peer.status.value}]",
        f"    Peers: N={peer.peer_count} | LOO Median: {peer_med_str} | Scale: {peer_scale_str}",
        f"    Robust Z-Score: {z_str} | Slice: {peer.reference_slice}",
        f"    Reason Code: {peer.reason_code}",
        f"  TEMPORAL KINETICS (D_drift): [{temp.status.value}] Confounded: {temp.confounded_by_equipment}",
        f"    Observations: {temp.observations_used} | Checkpoints: {temp.checkpoints_used}",
        f"    Theil-Sen Slope: {slope_str}/h | Acceleration Proxy: {accel_str}",
        f"    Drift g(T): {g_str} sigma | g_lot,-i: {g_lot_str} | g_excess: {g_excess_str}",
        f"    LOO Note: {temp.lot_reference_note or 'LOO Reference Valid'}",
        f"    Reason Code: {temp.reason_code}",
        f"  ABRUPT STEP (D_step): [{step.status.value}]",
        f"    Interval: [{step.previous_checkpoint}, {step.current_checkpoint}] | Jump Ratio J(T): {j_str}",
        f"    Reason Code: {step.reason_code}",
        f"  EQUIPMENT & CHAMBER (D_eq): [{eq.status.value}] Suspected: {eq.suspected}",
        f"    Chamber Shift: {chamber_shift_str} | Fraction Shifting: {frac_shift_str}",
        f"    ATE Socket: {eq.channel_id or 'N/A'} | Offset: {chan_offset_str} | Z-Score: {ate_z_str} | Suppressed: {ate_supp_str}",
        f"    Reason Code: {eq.reason_code}",
        f"  DATA SUFFICIENCY (D_suff): [{suff.status.value}] Sufficient: {suff.sufficient}",
        f"    Expected: {suff.expected_checkpoints} | Available: {suff.available_checkpoints}",
        f"    Reason Code: {suff.reason_code}",
        f"  PARAMETER STATE: {res.parameter_state.value}",
    ]
    return "\n".join(card)


def generate_explainability_card(result: ComponentScreeningResult) -> str:
    """Generate complete ASCII explainability card for component decision at checkpoint T."""
    header = [
        "================================================================================",
        "MODULE A SCREENING EXPLAINABILITY EVIDENCE CARD",
        "================================================================================",
        f"Component ID       : {result.component_id}",
        f"Lot ID             : {result.lot_id}",
        f"As-Of Checkpoint   : {result.checkpoint}h (Elapsed Hours <= {result.as_of_hours})",
        f"FINAL SCREENING    : {result.final_state.value}",
        f"Disposition Qual.  : {result.disposition_qualifier.value}",
        f"Primary Reason Code: {result.primary_reason_code}",
        f"Compound Evidence  : {result.compound_evidence}",
        f"Audit Hash         : {result.audit_hash[:16]}...",
        f"Generated At       : {result.created_at}",
        "================================================================================",
    ]

    param_blocks = [
        format_parameter_card(
            result.component_id,
            result.lot_id,
            result.checkpoint,
            p_res,
        )
        for p_res in result.parameter_results.values()
    ]

    footer = [
        "================================================================================",
        f"COMBINED REASON CODES: {', '.join(result.reason_codes[:10])}",
        "EPISTEMIC BOUNDARY NOTE:",
        "  - EQUIPMENT_SUSPECTED indicates available telemetry is consistent with",
        "    an equipment/common-mode shift; it does NOT establish device health.",
        "  - CONFOUNDED_BY_EQUIPMENT indicates excess motion beyond reference exists,",
        "    but interaction with equipment cannot be excluded without re-test.",
        "================================================================================",
    ]

    return "\n".join(header + param_blocks + footer)


def export_explainability_dict(result: ComponentScreeningResult) -> Dict[str, Any]:
    """Export machine-readable dictionary representation of the explainability card."""
    return result.to_dict()
