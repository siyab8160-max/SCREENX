"""Tests for the space hardware HOLD quarantine disposition.

Operational Rationale:
Space flight hardware (e.g. Rad-Hard IRHNJ57130 MOSFETs) is extremely high-value ($500-$2,000+ each).
Binary scrap (PASS vs REJECT) is economically and operationally unacceptable when an anomaly
is non-catastrophic (e.g. Class C flight screening margin breach with subtle kinetics without
Class A absolute failure).

The HOLD disposition quarantines the device for diagnostic re-test, bake-out, or Material Review
Board (MRB) review rather than falsely condemning good flight hardware to scrap.
"""

from __future__ import annotations

import pandas as pd
import pytest

from sih26170.pipeline.orchestrator import run_component_pipeline
from sih26170.screening.pipeline import screen_component
from sih26170.screening.schema import (
    DispositionQualifier,
    ScreeningState,
    SpecificationStatus,
    TemporalDriftStatus,
)
from tests.screening.test_scenarios import make_nominal_lot


def test_hold_disposition_screening_margin_with_drift():
    """Verify that Class C margin breach accompanied by subtle drift triggers HOLD."""
    df = make_nominal_lot(n_components=12)

    # Component C001 starts at 58.5 mOhm (within 60 mOhm margin) and drifts smoothly to 61.5 mOhm at 168h
    # 61.5 mOhm > 60 mOhm (Class C margin breach) but < 65 mOhm (Class A spec compliant)
    drift_profile = {0: 58.5, 24: 59.5, 96: 60.5, 168: 61.5}
    for t, val in drift_profile.items():
        df.loc[
            (df["component_id"] == "LOT_TEST_C001")
            & (df["parameter_name"] == "RDS(on)")
            & (df["elapsed_hours"] == t),
            "value",
        ] = val

    res = screen_component(df, "LOT_TEST_C001", as_of_hours=168)

    # Must be placed on HOLD, not scrapped (FAIL) and not passed (PASS)
    assert res.final_state == ScreeningState.HOLD
    assert res.final_state != ScreeningState.FAIL
    assert res.final_state != ScreeningState.PASS

    p_res = res.parameter_results["RDS(on)"]
    assert p_res.parameter_state == ScreeningState.HOLD
    assert p_res.spec_evidence.status == SpecificationStatus.SCREENING_MARGIN_BREACH
    assert p_res.temporal_evidence.status == TemporalDriftStatus.SUBTLE_DRIFT
    assert p_res.disposition_qualifier == DispositionQualifier.HOLD_SCREENING_MARGIN


def test_hold_pipeline_orchestration_and_explainability():
    """Verify that full pipeline produces HOLD state and coherent plain-language explainability."""
    df = make_nominal_lot(n_components=12)
    drift_profile = {0: 58.5, 24: 59.5, 96: 60.5, 168: 61.5}
    for t, val in drift_profile.items():
        df.loc[
            (df["component_id"] == "LOT_TEST_C001")
            & (df["parameter_name"] == "RDS(on)")
            & (df["elapsed_hours"] == t),
            "value",
        ] = val

    res = run_component_pipeline(
        telemetry=df,
        component_id="LOT_TEST_C001",
        as_of_hours=168,
    )

    assert res.screening_result.final_state == ScreeningState.HOLD
    assert "HOLD" in res.explainability.why_flagged
    assert "quarantine" in res.explainability.why_flagged.lower()
    assert "premature scrap" in res.explainability.why_flagged.lower()
