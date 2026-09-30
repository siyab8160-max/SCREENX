"""End-to-End Dynamic Screening Pipeline for Module A.

Compliant with docs/PHASE_3A_MODULE_A_SPEC.md:
- Canonical schema enforcement and strict ground-truth isolation
- Strict As-Of historical slice filtering V_T = sigma_{elapsed_hours <= T}(D)
- Execution of all six independent detectors (D_spec, D_peer, D_drift, D_step, D_eq, D_suff)
- Deterministic rules-based evidence fusion engine
- Produces stable machine-readable ComponentScreeningResult and AuditRecord
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set
import numpy as np
import pandas as pd

from sih26170.screening.abrupt import evaluate_abrupt_step
from sih26170.screening.audit import compute_telemetry_hash
from sih26170.screening.equipment import evaluate_equipment_environment
from sih26170.screening.fusion import (
    fuse_component_evidence,
    fuse_parameter_evidence,
)
from sih26170.screening.peer import evaluate_peer_deviation
from sih26170.screening.schema import (
    AbruptStepStatus,
    ComponentScreeningResult,
    EquipmentEvidence,
    EquipmentStatus,
    LimitClass,
    ParameterScreeningResult,
    PeerDeviationStatus,
    PeerEvidence,
    ScreeningState,
    SpecificationEvidence,
    SpecificationStatus,
    StepEvidence,
    SufficiencyEvidence,
    SufficiencyStatus,
    TemporalDriftStatus,
    TemporalEvidence,
)
from sih26170.screening.specification import evaluate_specification
from sih26170.screening.sufficiency import evaluate_data_sufficiency
from sih26170.screening.temporal import evaluate_temporal_drift
from sih26170.screening.transforms import (
    get_noise_floor,
    transform_parameter,
)

# Standard four electrical parameters
PRIMARY_PARAMETERS = ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]

# Canonical units mapping
CANONICAL_UNITS = {
    "IDSS": "uA",
    "VGS(th)": "V",
    "RDS(on)": "mOhm",
    "IGSS": "nA",
}

# Quarantined ground truth columns that must never enter runtime screening
FORBIDDEN_GROUND_TRUTH_COLUMNS: Set[str] = {
    "trajectory_class",
    "first_abnormal_hour",
    "abnormal_by_24h",
    "abnormal_by_96h",
    "abnormal_by_168h",
    "is_temporally_degraded",
    "is_spec_compliant",
    "is_abnormal",
    "parameter_scenario",
    "achieved_snr",
    "dominant_mechanism",
    "scenario_class",
}


def assert_ground_truth_quarantine(df: pd.DataFrame) -> None:
    """Verify that runtime input telemetry is free of evaluation ground-truth labels."""
    forbidden_found = FORBIDDEN_GROUND_TRUTH_COLUMNS.intersection(set(df.columns))
    if forbidden_found:
        raise ValueError(
            f"Ground truth quarantine violation: input dataframe contains forbidden evaluation columns: {sorted(forbidden_found)}. "
            "Evaluation ground truth must NEVER enter Module A feature generation or screening decisions."
        )


def enforce_as_of_slice(df: pd.DataFrame, as_of_hours: int) -> pd.DataFrame:
    """Extract historical observation slice V_T = sigma_{elapsed_hours <= as_of_hours}(df)."""
    assert_ground_truth_quarantine(df)
    if "elapsed_hours" not in df.columns:
        raise KeyError("Input dataframe must contain 'elapsed_hours' column.")
    return df[df["elapsed_hours"] <= as_of_hours].copy()


def screen_component(
    df: pd.DataFrame,
    component_id: str,
    as_of_hours: int,
) -> ComponentScreeningResult:
    """Execute complete Module A screening on a target component up to checkpoint as_of_hours.

    Args:
        df: Input telemetry dataframe (may contain multiple components, lots, and checkpoints)
        component_id: Unique target component identifier
        as_of_hours: Evaluation checkpoint T in {0, 24, 96, 168}

    Returns:
        ComponentScreeningResult containing fused state, reason codes, and detector evidence.
    """
    # 1. Enforce strict As-Of boundary and ground-truth quarantine
    as_of_df = enforce_as_of_slice(df, as_of_hours)

    comp_df = as_of_df[as_of_df["component_id"] == component_id]
    if comp_df.empty:
        raise ValueError(
            f"Component '{component_id}' has no telemetry records at or before as-of checkpoint {as_of_hours}h."
        )

    lot_id = str(comp_df["lot_id"].iloc[0])
    lot_df = as_of_df[as_of_df["lot_id"] == lot_id]
    total_lot_components = int(lot_df["component_id"].nunique())

    param_results: Dict[str, ParameterScreeningResult] = {}

    # 2. Evaluate each parameter independently
    for param in PRIMARY_PARAMETERS:
        comp_p_df = comp_df[comp_df["parameter_name"] == param].sort_values("elapsed_hours")
        lot_p_df = lot_df[lot_df["parameter_name"] == param]

        # Available history for this component & parameter
        available_ts = comp_p_df["elapsed_hours"].tolist()
        qualities = comp_p_df["measurement_quality"].tolist() if "measurement_quality" in comp_p_df.columns else ["VALID"] * len(available_ts)
        has_current_obs = as_of_hours in available_ts

        # A. Detector F: Data Sufficiency
        suff_ev = evaluate_data_sufficiency(
            component_id=component_id,
            checkpoint=as_of_hours,
            available_checkpoints=available_ts,
            measurement_qualities=qualities,
            lot_size=total_lot_components,
        )

        if not has_current_obs:
            # Observation missing at current checkpoint
            # Create stub evidence for other detectors
            unit = CANONICAL_UNITS.get(param, "")
            obs_val = float("nan")
            trans_val = float("nan")

            spec_ev = SpecificationEvidence(
                parameter=param,
                observed_value=obs_val,
                limit_low=None,
                limit_high=None,
                limit_class=LimitClass.CLASS_A,
                status=SpecificationStatus.NOT_EVALUATED,
                passed=False,
                reason_code="MISSING_OBSERVATION_AT_CHECKPOINT",
                provenance="N/A",
            )
            peer_ev = PeerEvidence(
                parameter=param,
                observed_value=obs_val,
                transformed_value=trans_val,
                peer_median=None,
                peer_mad=None,
                peer_scale=None,
                z_score=None,
                status=PeerDeviationStatus.INSUFFICIENT_PEERS,
                peer_count=0,
                reason_code="MISSING_OBSERVATION",
            )
            temp_ev = TemporalEvidence(
                parameter=param,
                observations_used=len(available_ts),
                checkpoints_used=available_ts,
                time_range=(available_ts[0], available_ts[-1]) if available_ts else (0, 0),
                slope_per_hour=None,
                normalized_drift=None,
                acceleration_evidence=None,
                status=TemporalDriftStatus.INSUFFICIENT_HISTORY,
                confounded_by_equipment=False,
                reason_code="MISSING_CURRENT_OBSERVATION",
            )
            step_ev = StepEvidence(
                parameter=param,
                previous_checkpoint=available_ts[-1] if available_ts else None,
                current_checkpoint=as_of_hours,
                step_magnitude=None,
                step_ratio=None,
                status=AbruptStepStatus.INSUFFICIENT_HISTORY,
                reason_code="MISSING_CURRENT_OBSERVATION",
            )
            eq_ev = EquipmentEvidence(
                lot_id=lot_id,
                checkpoint=as_of_hours,
                instrument_id=None,
                channel_id=None,
                lot_median_shift=None,
                fraction_shifting=None,
                channel_offset=None,
                status=EquipmentStatus.NOMINAL_EQUIPMENT,
                suspected=False,
                reason_code="NOT_EVALUATED",
            )
        else:
            curr_row = comp_p_df[comp_p_df["elapsed_hours"] == as_of_hours].iloc[-1]
            obs_val = float(curr_row["value"])
            unit = str(curr_row["unit"]) if "unit" in curr_row else CANONICAL_UNITS.get(param, "")
            inst_id = str(curr_row["instrument_id"]) if "instrument_id" in curr_row and pd.notna(curr_row["instrument_id"]) else None
            chan_id = str(curr_row["channel_id"]) if "channel_id" in curr_row and pd.notna(curr_row["channel_id"]) else None

            try:
                trans_val = transform_parameter(param, obs_val)
            except ValueError:
                trans_val = float("nan")

            # B. Detector A: Absolute Specification Gate
            lim_low = float(curr_row["absolute_limit_low"]) if "absolute_limit_low" in curr_row and pd.notna(curr_row["absolute_limit_low"]) else None
            lim_high = float(curr_row["absolute_limit_high"]) if "absolute_limit_high" in curr_row and pd.notna(curr_row["absolute_limit_high"]) else None
            spec_ev = evaluate_specification(param, obs_val, lim_low, lim_high)

            # C. Detector E: Equipment & Chamber Environment
            eq_ev = evaluate_equipment_environment(
                lot_id=lot_id,
                checkpoint=as_of_hours,
                parameter=param,
                lot_df_as_of=lot_p_df,
                target_component_id=component_id,
                instrument_id=inst_id,
                channel_id=chan_id,
            )

            # D. Detector B: Robust Leave-One-Out Peer Relative Deviation
            curr_lot_p = lot_p_df[lot_p_df["elapsed_hours"] == as_of_hours]
            peer_dict = dict(zip(curr_lot_p["component_id"], curr_lot_p["value"]))
            peer_ev = evaluate_peer_deviation(
                component_id=component_id,
                lot_id=lot_id,
                parameter=param,
                observed_value=obs_val,
                lot_observations=peer_dict,
            )

            # E. Detector C: Temporal Drift
            history_list = list(zip(comp_p_df["elapsed_hours"].astype(int), comp_p_df["value"].astype(float)))

            # Derive baseline scale sigma_0 from lot at t=0h if available
            t0_lot = lot_p_df[lot_p_df["elapsed_hours"] == 0]
            baseline_scale: Optional[float] = None
            if not t0_lot.empty and total_lot_components >= 8:
                u_t0: List[float] = []
                for v in t0_lot["value"]:
                    try:
                        u_t0.append(transform_parameter(param, v))
                    except ValueError:
                        pass
                if len(u_t0) >= 7:
                    u_t0_arr = np.array(u_t0)
                    med_t0 = np.median(u_t0_arr)
                    mad_t0 = np.median(np.abs(u_t0_arr - med_t0))
                    baseline_scale = max(1.4826 * float(mad_t0), get_noise_floor(param))

            # Construct lot peer history dictionary for leave-one-out calculation
            lot_peer_history: Dict[str, List[Tuple[int, float]]] = {}
            for peer_cid, peer_group in lot_p_df.groupby("component_id"):
                lot_peer_history[str(peer_cid)] = list(
                    zip(peer_group["elapsed_hours"].astype(int), peer_group["value"].astype(float))
                )

            temp_ev = evaluate_temporal_drift(
                parameter=param,
                history=history_list,
                as_of_hours=as_of_hours,
                baseline_lot_scale=baseline_scale,
                confounded_by_equipment=eq_ev.suspected,
                lot_peer_history=lot_peer_history,
                target_component_id=component_id,
            )

            # F. Detector D: Abrupt Step Change
            # Derive previous checkpoint lot scale if available
            lot_scale_prev: Optional[float] = None
            if as_of_hours > 0 and len(history_list) >= 2:
                t_prev = history_list[-2][0]
                t_prev_lot = lot_p_df[lot_p_df["elapsed_hours"] == t_prev]
                if not t_prev_lot.empty and total_lot_components >= 8:
                    u_tp: List[float] = []
                    for v in t_prev_lot["value"]:
                        try:
                            u_tp.append(transform_parameter(param, v))
                        except ValueError:
                            pass
                    if len(u_tp) >= 7:
                        u_tp_arr = np.array(u_tp)
                        med_tp = np.median(u_tp_arr)
                        mad_tp = np.median(np.abs(u_tp_arr - med_tp))
                        lot_scale_prev = max(1.4826 * float(mad_tp), get_noise_floor(param))

            step_ev = evaluate_abrupt_step(
                parameter=param,
                history=history_list,
                as_of_hours=as_of_hours,
                lot_scale_prev=lot_scale_prev,
            )

        # G. Fuse evidence for this parameter
        p_state, p_qualifier, p_prim_reason, p_reasons = fuse_parameter_evidence(
            spec_ev=spec_ev,
            peer_ev=peer_ev,
            temp_ev=temp_ev,
            step_ev=step_ev,
            eq_ev=eq_ev,
            suff_ev=suff_ev,
        )

        param_results[param] = ParameterScreeningResult(
            parameter=param,
            observed_value=obs_val,
            unit=unit,
            transformed_value=trans_val,
            spec_evidence=spec_ev,
            peer_evidence=peer_ev,
            temporal_evidence=temp_ev,
            step_evidence=step_ev,
            equipment_evidence=eq_ev,
            sufficiency_evidence=suff_ev,
            parameter_state=p_state,
            primary_reason_code=p_prim_reason,
            reason_codes=p_reasons,
            disposition_qualifier=p_qualifier,
        )

    # 3. Component-level evidence fusion across all four parameters
    comp_state, comp_qualifier, comp_primary_reason, comp_all_reasons, compound_flag = fuse_component_evidence(
        param_results
    )

    # 4. Generate deterministic audit hash
    input_hash = compute_telemetry_hash(comp_df)

    return ComponentScreeningResult(
        component_id=component_id,
        lot_id=lot_id,
        checkpoint=as_of_hours,
        final_state=comp_state,
        primary_reason_code=comp_primary_reason,
        reason_codes=comp_all_reasons,
        compound_evidence=compound_flag,
        parameter_results=param_results,
        as_of_hours=as_of_hours,
        audit_hash=input_hash,
        disposition_qualifier=comp_qualifier,
    )


def screen_lot(
    df: pd.DataFrame,
    lot_id: str,
    as_of_hours: int,
) -> List[ComponentScreeningResult]:
    """Execute Module A screening across all components in a lot at checkpoint as_of_hours."""
    as_of_df = enforce_as_of_slice(df, as_of_hours)
    lot_df = as_of_df[as_of_df["lot_id"] == lot_id]
    if lot_df.empty:
        raise ValueError(f"Lot '{lot_id}' has no records at or before {as_of_hours}h.")

    components = sorted(lot_df["component_id"].unique())
    return [screen_component(df, cid, as_of_hours) for cid in components]


def screen_dataset(
    df: pd.DataFrame,
    as_of_hours: int,
) -> List[ComponentScreeningResult]:
    """Execute Module A screening across all components in dataset at checkpoint as_of_hours."""
    as_of_df = enforce_as_of_slice(df, as_of_hours)
    components = sorted(as_of_df["component_id"].unique())
    return [screen_component(df, cid, as_of_hours) for cid in components]
