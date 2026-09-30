"""Evaluation harness for Module B baselines.

SCIENTIFIC BOUNDARY:
The 398 benchmark components are synthetic simulated components. The
IRHNJ57130/JANSR2N7481U3 specification provides the physical/device anchor; it
does not mean that the 398 components represent 398 experimentally characterized
MOSFETs. Module B results therefore constitute algorithmic/benchmark evidence,
not real-device validation.

Implements:
1. Leave-One-Lot-Out (LOLO) - PRIMARY evaluation protocol.
2. Pristine-Lot -> Defect-Lot - SECONDARY stress experiment only.
3. Distinct evaluation for Task 1 (24h -> 168h) and Task 2 (96h -> 168h).
4. Full breakdown by parameter and scenario (ground truth loaded ONLY at evaluation time).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
import pandas as pd
import numpy as np

from sih26170.prognostics.schema import PrognosticInput, PrognosticForecast
from sih26170.prognostics.validation import (
    build_prognostic_input,
    assert_no_ground_truth_leakage,
)
from sih26170.prognostics.baselines import BasePrognosticModel
from sih26170.prognostics.metrics import (
    EvaluationSummary,
    evaluate_forecast_set,
)


def extract_prognostic_inputs_for_lot(
    df: pd.DataFrame,
    lot_id: str,
    as_of_hours: int,
    target_hours: int = 168,
    parameters: Sequence[str] = ("IDSS", "VGS(th)", "RDS(on)", "IGSS"),
    screening_results_map: Optional[Dict[str, Any]] = None,
) -> List[PrognosticInput]:
    """Build strictly validated PrognosticInputs for all components in a given lot."""
    assert_no_ground_truth_leakage(df)
    lot_df = df[df["lot_id"] == lot_id]
    components = sorted(lot_df["component_id"].unique())

    inputs: List[PrognosticInput] = []
    for cid in components:
        sr = screening_results_map.get(cid) if screening_results_map is not None else None
        for p in parameters:
            inp = build_prognostic_input(
                df=df,
                component_id=cid,
                parameter_name=p,
                as_of_hours=as_of_hours,
                target_hours=target_hours,
                screening_result=sr,
            )
            inputs.append(inp)
    return inputs


def extract_target_values_for_inputs(
    df: pd.DataFrame,
    inputs: Sequence[PrognosticInput],
    target_hours: int = 168,
) -> List[float]:
    """Extract true target values at target_hours for a set of inputs from telemetry."""
    # Lookup table for fast access
    target_df = df[df["elapsed_hours"] == target_hours]
    val_map = {
        (row["component_id"], row["parameter_name"]): float(row["value"])
        for _, row in target_df.iterrows()
    }

    targets: List[float] = []
    for inp in inputs:
        key = (inp.component_id, inp.parameter_name)
        val = val_map.get(key, float("nan"))
        targets.append(val)
    return targets


def run_lolo_evaluation(
    df: pd.DataFrame,
    model_factory: Callable[[], BasePrognosticModel],
    as_of_hours: int,
    target_hours: int = 168,
    parameters: Sequence[str] = ("IDSS", "VGS(th)", "RDS(on)", "IGSS"),
    screening_results_map: Optional[Dict[str, Any]] = None,
) -> List[PrognosticForecast]:
    """Execute Leave-One-Lot-Out (LOLO) Cross-Validation across all lots.

    This is the PRIMARY evaluation protocol.
    """
    assert_no_ground_truth_leakage(df)
    lots = sorted(df["lot_id"].unique())
    all_forecasts: List[PrognosticForecast] = []

    for test_lot in lots:
        train_lots = [l for l in lots if l != test_lot]

        # 1. Gather training inputs and training targets (at target_hours)
        train_inputs: List[PrognosticInput] = []
        for tr_lot in train_lots:
            train_inputs.extend(
                extract_prognostic_inputs_for_lot(
                    df=df,
                    lot_id=tr_lot,
                    as_of_hours=as_of_hours,
                    target_hours=target_hours,
                    parameters=parameters,
                    screening_results_map=screening_results_map,
                )
            )

        train_targets = extract_target_values_for_inputs(
            df=df,
            inputs=train_inputs,
            target_hours=target_hours,
        )

        # 2. Instantiate and fit model on training lots ONLY
        model = model_factory()
        model.fit(train_inputs=train_inputs, train_ground_truth=train_targets)

        # 3. Gather test inputs for test_lot and generate predictions
        test_inputs = extract_prognostic_inputs_for_lot(
            df=df,
            lot_id=test_lot,
            as_of_hours=as_of_hours,
            target_hours=target_hours,
            parameters=parameters,
            screening_results_map=screening_results_map,
        )

        if hasattr(model, "set_contemporaneous_lot_inputs"):
            model.set_contemporaneous_lot_inputs(test_inputs)

        for t_inp in test_inputs:
            forecast = model.predict_single(t_inp)
            all_forecasts.append(forecast)

    return all_forecasts


def run_pristine_to_defect_evaluation(
    df: pd.DataFrame,
    model_factory: Callable[[], BasePrognosticModel],
    as_of_hours: int,
    target_hours: int = 168,
    parameters: Sequence[str] = ("IDSS", "VGS(th)", "RDS(on)", "IGSS"),
    nominal_lots: Sequence[str] = ("LOT_N01", "LOT_N02"),
    screening_results_map: Optional[Dict[str, Any]] = None,
) -> List[PrognosticForecast]:
    """Execute Pristine-Lot -> Defect-Lot Evaluation.

    This is strictly a SECONDARY stress experiment and must NOT be used as the primary claim.
    """
    assert_no_ground_truth_leakage(df)
    all_lots = sorted(df["lot_id"].unique())
    test_lots = [l for l in all_lots if l not in nominal_lots]

    # 1. Fit model on nominal pristine lots ONLY
    train_inputs: List[PrognosticInput] = []
    for tr_lot in nominal_lots:
        train_inputs.extend(
            extract_prognostic_inputs_for_lot(
                df=df,
                lot_id=tr_lot,
                as_of_hours=as_of_hours,
                target_hours=target_hours,
                parameters=parameters,
                screening_results_map=screening_results_map,
            )
        )

    train_targets = extract_target_values_for_inputs(
        df=df,
        inputs=train_inputs,
        target_hours=target_hours,
    )

    model = model_factory()
    model.fit(train_inputs=train_inputs, train_ground_truth=train_targets)

    # 2. Predict on stress/defect lots
    forecasts: List[PrognosticForecast] = []
    for t_lot in test_lots:
        test_inputs = extract_prognostic_inputs_for_lot(
            df=df,
            lot_id=t_lot,
            as_of_hours=as_of_hours,
            target_hours=target_hours,
            parameters=parameters,
            screening_results_map=screening_results_map,
        )
        if hasattr(model, "set_contemporaneous_lot_inputs"):
            model.set_contemporaneous_lot_inputs(test_inputs)
        for t_inp in test_inputs:
            forecasts.append(model.predict_single(t_inp))

    return forecasts


def evaluate_forecasts_with_ground_truth(
    forecasts: Sequence[PrognosticForecast],
    df_observations: pd.DataFrame,
    df_ground_truth: Optional[pd.DataFrame] = None,
    target_hours: int = 168,
) -> Dict[str, Any]:
    """Compute comprehensive evaluation metrics partitioned by parameter and scenario.

    Ground truth is ingested strictly here at evaluation time.
    """
    # Build true 168h target value map from observations
    target_obs = df_observations[df_observations["elapsed_hours"] == target_hours]
    gt_val_map = {
        (row["component_id"], row["parameter_name"]): float(row["value"])
        for _, row in target_obs.iterrows()
    }

    # 1. Overall evaluation
    overall_summary = evaluate_forecast_set(forecasts, gt_val_map)

    # 2. Evaluation per parameter
    params = sorted(list(set(f.parameter_name for f in forecasts)))
    param_summaries: Dict[str, EvaluationSummary] = {}
    for p in params:
        p_forecasts = [f for f in forecasts if f.parameter_name == p]
        param_summaries[p] = evaluate_forecast_set(p_forecasts, gt_val_map)

    # 3. Evaluation per scenario category (if ground_truth.csv provided)
    scenario_summaries: Dict[str, Dict[str, EvaluationSummary]] = {}
    if df_ground_truth is not None:
        param_scenario_map = {}
        for _, row in df_ground_truth.iterrows():
            cid = str(row["component_id"])
            pname = str(row["parameter_name"])
            scen = str(row.get("parameter_scenario", row.get("scenario_name", "UNKNOWN")))
            param_scenario_map[(cid, pname)] = scen

        unique_scenarios = sorted(list(set(param_scenario_map.values())))
        for scen in unique_scenarios:
            scen_forecasts = [
                f for f in forecasts if param_scenario_map.get((f.component_id, f.parameter_name)) == scen
            ]
            if not scen_forecasts:
                continue
            scen_dict: Dict[str, EvaluationSummary] = {
                "OVERALL": evaluate_forecast_set(scen_forecasts, gt_val_map)
            }
            for p in params:
                scen_p_forecasts = [f for f in scen_forecasts if f.parameter_name == p]
                if scen_p_forecasts:
                    scen_dict[p] = evaluate_forecast_set(scen_p_forecasts, gt_val_map)
            scenario_summaries[scen] = scen_dict

    return {
        "overall": overall_summary,
        "per_parameter": param_summaries,
        "per_scenario": scenario_summaries,
    }
