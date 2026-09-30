"""Evidence Fusion Engine for Module A.

Compliant with docs/PHASE_3A_MODULE_A_SPEC.md Sections 9, 10, & 11 & Phase 3C Pre-Implementation Amendments:
- Preserves the canonical 5 top-level states: PASS, ALERT, FAIL, INSUFFICIENT_DATA, EQUIPMENT_SUSPECTED
- Enriches screening dispositions with typed DispositionQualifier metadata:
  * SPECIFICATION_FAILURE
  * INSUFFICIENT_EVIDENCE
  * COMPONENT_DEGRADATION
  * COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT
  * EQUIPMENT_ONLY
  * PEER_OUTLIER_STATIONARY
  * NOMINAL_STABLE
- Strict epistemic semantics:
  * EQUIPMENT_SUSPECTED means available evidence is consistent with an equipment/common-mode explanation,
    so component-specific degradation cannot currently be established. (Does NOT mean component is healthy).
  * COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT means excess drift beyond common-mode reference
    indicates candidate wearout kinetics; however, complete independence from equipment interaction
    cannot be established without re-test. (Does NOT prove autonomous degradation).
- Evidence preservation: Precedence Level 3 handles Confounded Temporal Kinetics, ensuring that
  genuine wearout kinetics are NEVER erased by equipment alerts.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from sih26170.screening.schema import (
    AbruptStepStatus,
    DispositionQualifier,
    EquipmentEvidence,
    EquipmentStatus,
    ParameterScreeningResult,
    PeerDeviationStatus,
    PeerEvidence,
    ScreeningState,
    SpecificationEvidence,
    SpecificationStatus,
    StepEvidence,
    SufficiencyEvidence,
    TemporalDriftStatus,
    TemporalEvidence,
)


def fuse_parameter_evidence(
    spec_ev: SpecificationEvidence,
    peer_ev: PeerEvidence,
    temp_ev: TemporalEvidence,
    step_ev: StepEvidence,
    eq_ev: EquipmentEvidence,
    suff_ev: SufficiencyEvidence,
) -> Tuple[ScreeningState, DispositionQualifier, str, List[str]]:
    """Fuse detector outputs for an individual parameter adhering to strict precedence.

    Returns:
        (parameter_state, disposition_qualifier, primary_reason_code, all_reason_codes)
    """
    all_reasons: List[str] = [
        spec_ev.reason_code,
        peer_ev.reason_code,
        temp_ev.reason_code,
        step_ev.reason_code,
        eq_ev.reason_code,
        suff_ev.reason_code,
    ]

    # Precedence Level 1: Class A Absolute Specification Breach (Hard Veto)
    if spec_ev.status == SpecificationStatus.SPEC_BREACH:
        return (
            ScreeningState.FAIL,
            DispositionQualifier.SPECIFICATION_FAILURE,
            spec_ev.reason_code,
            all_reasons,
        )

    # Precedence Level 2: Data Sufficiency Failure
    if not suff_ev.sufficient:
        return (
            ScreeningState.INSUFFICIENT_DATA,
            DispositionQualifier.INSUFFICIENT_EVIDENCE,
            suff_ev.reason_code,
            all_reasons,
        )

    # Precedence Level 3: Equipment Suspicion Interacting with Temporal Kinetics
    if eq_ev.suspected:
        g_excess = temp_ev.g_excess if temp_ev.g_excess is not None else temp_ev.normalized_drift
        has_excess_degradation = (g_excess is not None and abs(g_excess) >= 2.5)

        if has_excess_degradation:
            state = (
                ScreeningState.FAIL
                if (temp_ev.status == TemporalDriftStatus.ACCELERATING_DRIFT or step_ev.status == AbruptStepStatus.ABRUPT_JUMP_ALERT)
                else ScreeningState.ALERT
            )
            prim_reason = (
                temp_ev.reason_code
                if temp_ev.status == TemporalDriftStatus.ACCELERATING_DRIFT
                else (step_ev.reason_code if step_ev.status == AbruptStepStatus.ABRUPT_JUMP_ALERT else "CONFOUNDED_TEMPORAL_DRIFT")
            )
            return (
                state,
                DispositionQualifier.COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT,
                prim_reason,
                all_reasons,
            )

        # When no excess degradation beyond the common-mode shift exists (|g_excess| < 2.5),
        # the component's movement is consistent with the equipment/chamber excursion.
        return (
            ScreeningState.EQUIPMENT_SUSPECTED,
            DispositionQualifier.EQUIPMENT_ONLY,
            eq_ev.reason_code,
            all_reasons,
        )

    # Precedence Level 4: Autonomous Temporal Kinetics (Equipment NOMINAL)
    if temp_ev.status == TemporalDriftStatus.ACCELERATING_DRIFT:
        return (
            ScreeningState.FAIL,
            DispositionQualifier.COMPONENT_DEGRADATION,
            temp_ev.reason_code,
            all_reasons,
        )

    if step_ev.status == AbruptStepStatus.ABRUPT_JUMP_ALERT:
        return (
            ScreeningState.FAIL,
            DispositionQualifier.COMPONENT_DEGRADATION,
            step_ev.reason_code,
            all_reasons,
        )

    if temp_ev.status == TemporalDriftStatus.SUBTLE_DRIFT:
        return (
            ScreeningState.ALERT,
            DispositionQualifier.COMPONENT_DEGRADATION,
            temp_ev.reason_code,
            all_reasons,
        )

    # Precedence Level 5: Class C Configured Screening Margin Breach (Tightened Flight Gate)
    if spec_ev.status == SpecificationStatus.SCREENING_MARGIN_BREACH:
        return (
            ScreeningState.ALERT,
            DispositionQualifier.SPECIFICATION_FAILURE,
            spec_ev.reason_code,
            all_reasons,
        )

    # Precedence Level 6: Peer Outlier Deviation
    if peer_ev.status in (PeerDeviationStatus.PEER_MILD_OUTLIER, PeerDeviationStatus.PEER_EXTREME_OUTLIER):
        if temp_ev.status == TemporalDriftStatus.STATIONARY:
            return (
                ScreeningState.ALERT,
                DispositionQualifier.PEER_OUTLIER_STATIONARY,
                "HIGH_BUT_STABLE_PEER_OUTLIER",
                all_reasons,
            )
        else:
            return (
                ScreeningState.ALERT,
                DispositionQualifier.PEER_OUTLIER_STATIONARY,
                peer_ev.reason_code,
                all_reasons,
            )

    # Precedence Level 7: Default Compliant
    return (
        ScreeningState.PASS,
        DispositionQualifier.NOMINAL_STABLE,
        "NOMINAL_SPEC_AND_STABLE_KINETICS",
        all_reasons,
    )


def fuse_component_evidence(
    param_results: Dict[str, ParameterScreeningResult]
) -> Tuple[ScreeningState, DispositionQualifier, str, List[str], bool]:
    """Fuse parameter-level screening results into component-level screening disposition.

    Returns:
        (final_state, disposition_qualifier, primary_reason_code, combined_reasons, compound_evidence)
    """
    all_reasons: List[str] = []
    failing_results: List[Tuple[str, ParameterScreeningResult]] = []
    insufficient_results: List[Tuple[str, ParameterScreeningResult]] = []
    alert_results: List[Tuple[str, ParameterScreeningResult]] = []
    equipment_results: List[Tuple[str, ParameterScreeningResult]] = []

    drifting_params: List[str] = []

    for p_name, res in param_results.items():
        all_reasons.extend(res.reason_codes)

        if res.parameter_state == ScreeningState.FAIL:
            failing_results.append((p_name, res))
        elif res.parameter_state == ScreeningState.INSUFFICIENT_DATA:
            insufficient_results.append((p_name, res))
        elif res.parameter_state == ScreeningState.ALERT:
            alert_results.append((p_name, res))
        elif res.parameter_state == ScreeningState.EQUIPMENT_SUSPECTED:
            equipment_results.append((p_name, res))

        # Check for active degradation drift or step changes
        if (
            res.temporal_evidence.status in (TemporalDriftStatus.SUBTLE_DRIFT, TemporalDriftStatus.ACCELERATING_DRIFT)
            or res.step_evidence.status == AbruptStepStatus.ABRUPT_JUMP_ALERT
            or res.disposition_qualifier == DispositionQualifier.COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT
        ):
            drifting_params.append(p_name)

    # Secondary explanatory flag for compound multi-parameter degradation
    non_nominal_count = len(failing_results) + len(alert_results)
    compound_evidence = (len(drifting_params) >= 2) or (non_nominal_count >= 2)

    # Precedence 1: Multi-parameter compound failure/drift -> FAIL with compound reason
    if len(drifting_params) >= 2 or len(failing_results) >= 2:
        comp_params = sorted(list(set(drifting_params + [p for p, _ in failing_results])))
        reasons_compound = f"COMPOUND_MULTI_PARAMETER_DRIFT_{'_'.join(comp_params)}"
        # Check if confounded by equipment
        has_confounding = any(
            res.disposition_qualifier == DispositionQualifier.COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT
            for _, res in param_results.items()
        )
        qualifier = (
            DispositionQualifier.COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT
            if has_confounding
            else DispositionQualifier.COMPONENT_DEGRADATION
        )
        return ScreeningState.FAIL, qualifier, reasons_compound, all_reasons, True

    # Precedence 2: Single parameter failed Class A spec or severe kinetics -> FAIL
    if failing_results:
        p_name, res = failing_results[0]
        return (
            ScreeningState.FAIL,
            res.disposition_qualifier,
            f"{p_name}:{res.primary_reason_code}",
            all_reasons,
            compound_evidence,
        )

    # Precedence 3: Insufficient telemetry data -> INSUFFICIENT_DATA
    if insufficient_results:
        p_name, res = insufficient_results[0]
        return (
            ScreeningState.INSUFFICIENT_DATA,
            DispositionQualifier.INSUFFICIENT_EVIDENCE,
            f"{p_name}:{res.primary_reason_code}",
            all_reasons,
            compound_evidence,
        )

    # Precedence 4: Parameter Alerts (Wearout kinetics or Outliers)
    if alert_results:
        # Prioritize degradation alerts over peer outliers
        degradation_alerts = [
            (p, res) for p, res in alert_results
            if res.disposition_qualifier in (
                DispositionQualifier.COMPONENT_DEGRADATION,
                DispositionQualifier.COMPONENT_DEGRADATION_CONFOUNDED_BY_EQUIPMENT,
            )
        ]
        chosen_p, chosen_res = degradation_alerts[0] if degradation_alerts else alert_results[0]
        return (
            ScreeningState.ALERT,
            chosen_res.disposition_qualifier,
            f"{chosen_p}:{chosen_res.primary_reason_code}",
            all_reasons,
            compound_evidence,
        )

    # Precedence 5: Pure Equipment Suspicion (all other parameters nominal)
    if equipment_results:
        p_name, res = equipment_results[0]
        return (
            ScreeningState.EQUIPMENT_SUSPECTED,
            DispositionQualifier.EQUIPMENT_ONLY,
            f"{p_name}:{res.primary_reason_code}",
            all_reasons,
            compound_evidence,
        )

    # Precedence 6: Default nominal -> PASS
    return (
        ScreeningState.PASS,
        DispositionQualifier.NOMINAL_STABLE,
        "NOMINAL_SPEC_AND_STABLE_KINETICS",
        all_reasons,
        False,
    )
