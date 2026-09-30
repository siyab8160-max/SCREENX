"""Core end-to-end pipeline orchestrator for SIH26170 Engineering Prototype.

Complies strictly with post-Phase-5 engineering integration specifications:
- 12-step execution flow:
    Telemetry -> Validation -> Module A -> Evidence Preservation -> Module B Locked Ridge
    -> Prediction Intervals -> Spec Interpretation -> Explainability -> Deterministic Hash
    -> Audit Record -> Canonical Result.
- Mandatory Lot Context: Peer and equipment detectors require lot cohort context.
    If lot context is unavailable (N=1), peer/equipment evidence is explicitly represented
    as unavailable/insufficient according to Module A contracts; never fabricated.
- Strict As-Of Causality: Only observations with elapsed_hours <= as_of_hours are accessible.
- Decoupled Specification Semantics:
    * measured_spec_failure = objective test against applicable limits.
    * predicted_spec_breach = informational prognostic risk evidence only.
    * Predicted breaches NEVER alter Module A final_state, and NEVER trigger autonomous scrap.
- Divergence Policy: |u| > 10.0 is a LOCKED PHASE-5 NUMERICAL POLICY triggering deterministic
    fallback to Carry-Forward (v24).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from sih26170.pipeline.audit import (
    compute_canonical_result_hash,
    compute_telemetry_hash,
    create_pipeline_audit_record,
    LINEAGE_MANIFEST_HASH,
)
from sih26170.pipeline.explainability import build_engineering_explainability
from sih26170.pipeline.schema import (
    CANONICAL_PARAM_UNITS,
    ComponentPipelineResult,
    ForecastInterpretation,
    ModelLineageInfo,
    ORDERED_PARAMETERS,
)
from sih26170.pipeline.telemetry import assert_ground_truth_quarantine
from sih26170.prognostics.locked_models import (
    get_locked_ridge_model,
    LOCKED_COEFFICIENTS_HEX,
    FROZEN_SIGMA_EFF_HEX,
)
from sih26170.prognostics.safety import (
    SafetyConfig,
    SafetyDecision,
    SafetySlopeEvaluator,
)
from pathlib import Path
from sih26170.prognostics.schema import PrognosticForecast
from sih26170.screening.pipeline import screen_component
from sih26170.screening.schema import ComponentScreeningResult, ScreeningState
from sih26170.screening.specification import SPEC_LIMITS_CLASS_A


def get_applicable_limits(
    param: str,
    as_of_df: pd.DataFrame,
) -> tuple[Optional[float], Optional[float]]:
    """Retrieve applicable specification limits from telemetry metadata or project registry."""
    sub = as_of_df[as_of_df["parameter_name"] == param]
    if not sub.empty:
        row = sub.iloc[-1]
        lim_low = row.get("absolute_limit_low")
        lim_high = row.get("absolute_limit_high")
        if pd.notna(lim_low) or pd.notna(lim_high):
            return (
                float(lim_low) if pd.notna(lim_low) else None,
                float(lim_high) if pd.notna(lim_high) else None,
            )

    # Fallback to project verified Class A limits if not specified per-row
    if param in SPEC_LIMITS_CLASS_A:
        spec = SPEC_LIMITS_CLASS_A[param]
        return (spec.get("low"), spec.get("high"))

    return (None, None)


def run_component_pipeline(
    telemetry: pd.DataFrame,
    component_id: str,
    as_of_hours: int,
    lot_telemetry: Optional[pd.DataFrame] = None,
    run_id: Optional[str] = None,
) -> ComponentPipelineResult:
    """Execute complete end-to-end screening, prognostics, explainability, and audit.

    Args:
        telemetry: Historical telemetry containing at least component_id observations.
        component_id: Target component identifier.
        as_of_hours: Evaluation checkpoint T.
        lot_telemetry: Optional lot cohort observations. If None, telemetry is inspected.
        run_id: Optional unique run identifier for audit record.

    Returns:
        ComponentPipelineResult containing full machine-readable results, explainability, and audit hash.
    """
    # 1. Input validation & ground truth quarantine
    if telemetry.empty or "elapsed_hours" not in telemetry.columns:
        raise ValueError(
            f"Component '{component_id}' has no records at or before checkpoint {as_of_hours}h."
        )

    assert_ground_truth_quarantine(telemetry)
    if lot_telemetry is not None:
        assert_ground_truth_quarantine(lot_telemetry)

    if as_of_hours < 0:
        raise ValueError(f"as_of_hours must be >= 0, got {as_of_hours}")

    # 2. Strict As-Of Historical Slicing (elapsed_hours <= as_of_hours)
    telemetry_as_of = telemetry[telemetry["elapsed_hours"] <= as_of_hours].copy()
    comp_df = telemetry_as_of[telemetry_as_of["component_id"] == component_id]

    if comp_df.empty:
        raise ValueError(
            f"Component '{component_id}' has no records at or before checkpoint {as_of_hours}h."
        )

    lot_id = str(comp_df["lot_id"].iloc[0])

    # 3. Lot Context Assembly
    # Module A peer and equipment detectors require lot cohort context.
    if lot_telemetry is not None:
        lot_as_of = lot_telemetry[lot_telemetry["elapsed_hours"] <= as_of_hours].copy()
        combined_df = pd.concat([telemetry_as_of, lot_as_of], ignore_index=True).drop_duplicates(
            subset=["component_id", "parameter_name", "elapsed_hours"]
        )
    else:
        combined_df = telemetry_as_of.copy()

    # 4. Input Telemetry Hash
    input_hash = compute_telemetry_hash(comp_df)

    # 5. Module A Dynamic Screening Execution
    screening_result: ComponentScreeningResult = screen_component(
        df=combined_df,
        component_id=component_id,
        as_of_hours=as_of_hours,
    )

    # 6. Module B Locked Ridge Prognostics & Safety-Slope Decision Layer
    prognostic_forecasts: Dict[str, PrognosticForecast] = {}
    interpretations: Dict[str, ForecastInterpretation] = {}
    safety_decisions: Dict[str, Dict[str, Any]] = {}
    component_early_rejection = False

    # Load safety configuration
    safety_cfg_path = Path(__file__).resolve().parents[3] / "configs/safety_config.yaml"
    safety_config = SafetyConfig.from_yaml(safety_cfg_path) if safety_cfg_path.exists() else SafetyConfig.default()
    safety_evaluator = SafetySlopeEvaluator(config=safety_config)

    for param in ORDERED_PARAMETERS:
        param_comp = comp_df[comp_df["parameter_name"] == param].sort_values("elapsed_hours")
        unit = CANONICAL_PARAM_UNITS.get(param, "")
        lim_low, lim_high = get_applicable_limits(param, comp_df)

        t_available = param_comp["elapsed_hours"].tolist()
        has_t0 = 0 in t_available
        has_t24 = 24 in t_available

        curr_row = param_comp[param_comp["elapsed_hours"] == as_of_hours]
        curr_obs = float(curr_row["value"].iloc[-1]) if not curr_row.empty else None

        measured_spec_failure = False
        if curr_obs is not None:
            if lim_high is not None and curr_obs > lim_high:
                measured_spec_failure = True
            if lim_low is not None and curr_obs < lim_low:
                measured_spec_failure = True

        # Module B Ridge operates on [v0, v24] -> v168
        if as_of_hours < 24 or not (has_t0 and has_t24):
            # Insufficient history for 24h Ridge model
            forecast = PrognosticForecast(
                component_id=component_id,
                lot_id=lot_id,
                parameter_name=param,
                unit=unit,
                as_of_hours=as_of_hours,
                target_hours=168,
                predicted_value=float("nan"),
                forecast_change_from_origin=float("nan"),
                baseline_relative_forecast_change=float("nan"),
                interval_lower=None,
                interval_upper=None,
                interval_coverage=0.90,
                sigma_eff=None,
                model_id=f"REG_RIDGE_{param}",
                is_valid=False,
                exclusion_reason="Missing 0h baseline or 24h intermediate readout for Ridge prognostics",
            )
            prognostic_forecasts[param] = forecast
            safety_res = safety_evaluator.evaluate_single(
                component_id=component_id,
                parameter_name=param,
                value_24h=float("nan"),
                predicted_value_168h=float("nan"),
                model_id=f"REG_RIDGE_{param}",
                upstream_disposition="INSUFFICIENT_DATA",
            )
            safety_decisions[param] = safety_res.to_dict()
            interpretations[param] = ForecastInterpretation(
                parameter=param,
                measured_spec_failure=measured_spec_failure,
                predicted_spec_breach=False,
                predicted_breach_lower=False,
                predicted_breach_upper=False,
                measured_value=curr_obs,
                predicted_value=None,
                limit_low=lim_low,
                limit_high=lim_high,
                unit=unit,
                disposition_recommendation=(
                    "INSUFFICIENT HISTORY FOR PROGNOSTICS (< 24h baseline) — "
                    "DISPOSITION GOVERNED BY MODULE A SCREENING"
                ),
                predicted_drift_rate=None,
                calculated_safety_slope=None,
                safety_threshold=None,
                early_rejection_flag=False,
                safety_decision="INSUFFICIENT_DATA",
            )
        else:
            v0 = float(param_comp[param_comp["elapsed_hours"] == 0]["value"].iloc[-1])
            v24 = float(param_comp[param_comp["elapsed_hours"] == 24]["value"].iloc[-1])

            model = get_locked_ridge_model(param)
            fc_as_of = as_of_hours if as_of_hours < 168 else 24
            forecast = model.forecast_single(
                v0=v0,
                v24=v24,
                component_id=component_id,
                lot_id=lot_id,
                as_of_hours=fc_as_of,
                target_hours=168,
                screening_result=screening_result,
            )
            prognostic_forecasts[param] = forecast

            # Specification breach interpretation (informational only)
            pred_y = forecast.predicted_value
            pred_breach_lower = False
            pred_breach_upper = False
            predicted_spec_breach = False

            if np.isfinite(pred_y):
                if lim_high is not None and pred_y > lim_high:
                    pred_breach_upper = True
                    predicted_spec_breach = True
                if lim_low is not None and pred_y < lim_low:
                    pred_breach_lower = True
                    predicted_spec_breach = True

            # Safety-Slope / Early-Rejection Decision Layer
            safety_res = safety_evaluator.evaluate_single(
                component_id=component_id,
                parameter_name=param,
                value_24h=v24,
                predicted_value_168h=pred_y if np.isfinite(pred_y) else float("nan"),
                model_id=forecast.model_id,
                upstream_disposition="PREDICTED" if np.isfinite(pred_y) else "INSUFFICIENT_DATA",
                lower_bound=forecast.interval_lower,
                upper_bound=forecast.interval_upper,
            )
            safety_decisions[param] = safety_res.to_dict()
            is_early_reject = (safety_res.decision == SafetyDecision.EARLY_REJECT)
            if is_early_reject:
                component_early_rejection = True

            recom = safety_res.reason

            interpretations[param] = ForecastInterpretation(
                parameter=param,
                measured_spec_failure=measured_spec_failure,
                predicted_spec_breach=predicted_spec_breach,
                predicted_breach_lower=pred_breach_lower,
                predicted_breach_upper=pred_breach_upper,
                measured_value=curr_obs,
                predicted_value=pred_y if np.isfinite(pred_y) else None,
                limit_low=lim_low,
                limit_high=lim_high,
                unit=unit,
                disposition_recommendation=recom,
                predicted_drift_rate=safety_res.predicted_drift_rate if np.isfinite(safety_res.predicted_drift_rate) else None,
                calculated_safety_slope=safety_res.safety_slope if np.isfinite(safety_res.safety_slope) else None,
                safety_threshold=safety_res.safety_threshold if np.isfinite(safety_res.safety_threshold) else None,
                early_rejection_flag=is_early_reject,
                safety_decision=safety_res.decision.value,
            )

    # 7. Explainability Construction
    explainability = build_engineering_explainability(
        component_id=component_id,
        lot_id=lot_id,
        as_of_hours=as_of_hours,
        screening_result=screening_result,
        prognostic_forecasts=prognostic_forecasts,
        interpretations=interpretations,
        input_telemetry=comp_df,
    )

    # 8. Model Lineage Construction
    coeffs_dict = {
        p: [float.fromhex(h) for h in LOCKED_COEFFICIENTS_HEX[p]] for p in ORDERED_PARAMETERS
    }
    sigma_dict = {
        p: float.fromhex(FROZEN_SIGMA_EFF_HEX[p]) for p in ORDERED_PARAMETERS
    }
    model_lineage = ModelLineageInfo(
        coefficients=coeffs_dict,
        sigma_eff=sigma_dict,
    )

    # 9. Assembly of Pre-Hash Result
    result = ComponentPipelineResult(
        component_id=component_id,
        lot_id=lot_id,
        as_of_hours=as_of_hours,
        screening_result=screening_result,
        prognostic_forecasts=prognostic_forecasts,
        interpretations=interpretations,
        explainability=explainability,
        input_hash=input_hash,
        canonical_result_hash="",  # Populated in step 10
        model_lineage=model_lineage,
        safety_decisions=safety_decisions,
        component_early_rejection=component_early_rejection,
    )

    # 10. Deterministic Canonical Result Hash
    canonical_dict = result.to_canonical_dict()
    canonical_result_hash = compute_canonical_result_hash(canonical_dict)
    result.canonical_result_hash = canonical_result_hash

    # 11. Pipeline Audit Record (holds runtime execution context)
    audit_record = create_pipeline_audit_record(
        component_id=component_id,
        lot_id=lot_id,
        as_of_hours=as_of_hours,
        input_hash=input_hash,
        canonical_result_hash=canonical_result_hash,
        run_id=run_id,
    )
    result.audit_record = audit_record

    return result
