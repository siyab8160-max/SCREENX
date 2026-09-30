"""Strict as-of validation and leakage controls for Module B.

Ensures:
- Ground-truth telemetry columns are strictly quarantined and rejected if present.
- Observations with elapsed_hours > as_of_hours are blocked.
- Post-T screening results are blocked.
- Lineage (component_id, lot_id, parameter_name, unit) is strictly preserved.
"""

from __future__ import annotations

from typing import Any, Optional, Set, Tuple
import pandas as pd
import numpy as np

from sih26170.prognostics.schema import PrognosticInput

# Quarantined ground truth columns that must NEVER enter feature extraction or prediction
QUARANTINED_COLUMNS: Set[str] = {
    "is_anomaly",
    "anomaly_type",
    "true_defect_type",
    "defect_channel",
    "scenario_name",
    "ground_truth_label",
    "ground_truth_category",
    "failure_mechanism",
    "defect_mechanism",
    "true_drift_rate",
    "true_step_time",
}


def assert_no_ground_truth_leakage(df: pd.DataFrame) -> None:
    """Raise ValueError if any quarantined ground truth column is present in df."""
    leakage_cols = set(df.columns).intersection(QUARANTINED_COLUMNS)
    if leakage_cols:
        raise ValueError(
            f"Ground truth leakage detected: DataFrame contains quarantined columns: {sorted(leakage_cols)}"
        )


def filter_as_of_telemetry(df: pd.DataFrame, as_of_hours: int) -> pd.DataFrame:
    """Filter telemetry DataFrame strictly to elapsed_hours <= as_of_hours.

    Also asserts that no quarantined ground-truth columns are present.
    """
    assert_no_ground_truth_leakage(df)
    if "elapsed_hours" not in df.columns:
        raise ValueError("Telemetry DataFrame must contain 'elapsed_hours' column")

    filtered = df[df["elapsed_hours"] <= as_of_hours].copy()
    return filtered


def build_prognostic_input(
    df: pd.DataFrame,
    component_id: str,
    parameter_name: str,
    as_of_hours: int,
    target_hours: int = 168,
    screening_result: Optional[Any] = None,
) -> PrognosticInput:
    """Construct a strictly validated PrognosticInput from raw telemetry.

    Args:
        df: Telemetry DataFrame (observations.csv)
        component_id: Unique component ID (e.g. 'LOT_N01_C001')
        parameter_name: Canonical parameter name (e.g. 'IDSS')
        as_of_hours: Maximum allowable observation time (e.g. 24 or 96)
        target_hours: Future forecast horizon (default: 168)
        screening_result: Optional upstream ComponentScreeningResult from Module A

    Returns:
        PrognosticInput instance satisfying all strict as-of and lineage contracts.

    Raises:
        ValueError: If leakage detected, invalid timestamps, or missing required fields.
    """
    # 1. Quarantined ground-truth check
    assert_no_ground_truth_leakage(df)

    # 2. Screening result post-T leakage check
    if screening_result is not None:
        sr_as_of = getattr(screening_result, "as_of_hours", None)
        if sr_as_of is not None and sr_as_of > as_of_hours:
            raise ValueError(
                f"Screening evidence leakage: screening_result is as-of {sr_as_of}h, "
                f"which exceeds requested as_of_hours ({as_of_hours}h)"
            )

    # 3. Filter DataFrame strictly to component, parameter, and as-of time
    mask = (
        (df["component_id"] == component_id)
        & (df["parameter_name"] == parameter_name)
        & (df["elapsed_hours"] <= as_of_hours)
    )
    comp_df = df[mask].sort_values("elapsed_hours")

    if comp_df.empty:
        # Determine lot_id and unit if available from any row for this component
        any_comp_df = df[df["component_id"] == component_id]
        lot_id = any_comp_df["lot_id"].iloc[0] if not any_comp_df.empty else "UNKNOWN"
        unit = "UNKNOWN"
        return PrognosticInput(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            unit=unit,
            as_of_hours=as_of_hours,
            target_hours=target_hours,
            historical_observations=(),
            screening_result=screening_result,
            data_sufficiency_passed=False,
            insufficient_reason="No observations available for component and parameter at or before as_of_hours",
        )

    lot_id = str(comp_df["lot_id"].iloc[0])
    unit = str(comp_df["unit"].iloc[0])

    # 4. Extract chronologically ordered (elapsed_hours, value) pairs
    obs_list = []
    for _, row in comp_df.iterrows():
        t = int(row["elapsed_hours"])
        v = float(row["value"])
        obs_list.append((t, v))

    obs_tuple = tuple(obs_list)

    # 5. Build input object and calculate cryptographic audit hash
    prog_input = PrognosticInput(
        component_id=component_id,
        lot_id=lot_id,
        parameter_name=parameter_name,
        unit=unit,
        as_of_hours=as_of_hours,
        target_hours=target_hours,
        historical_observations=obs_tuple,
        screening_result=screening_result,
        data_sufficiency_passed=True,
        insufficient_reason=None,
    )

    audit_hash = prog_input.compute_sha256()
    return PrognosticInput(
        component_id=prog_input.component_id,
        lot_id=prog_input.lot_id,
        parameter_name=prog_input.parameter_name,
        unit=prog_input.unit,
        as_of_hours=prog_input.as_of_hours,
        target_hours=prog_input.target_hours,
        historical_observations=prog_input.historical_observations,
        screening_result=prog_input.screening_result,
        data_sufficiency_passed=prog_input.data_sufficiency_passed,
        insufficient_reason=prog_input.insufficient_reason,
        audit_hash=audit_hash,
    )
