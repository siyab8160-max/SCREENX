"""Tests for exact closed-form Ridge SHAP linear attributions.

Verifies:
1. Exact Efficiency / Additivity: phi_0 + phi_baseline + phi_slope == u_hat
2. Accurate primary driver identification:
   - Drifting component: 'slope_0_24' is primary driver
   - High-but-stationary component: 'baseline_0h' is primary driver
3. Integration with PrognosticForecast contracts and EngineeringExplainability
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from sih26170.pipeline.orchestrator import run_component_pipeline
from sih26170.pipeline.schema import ORDERED_PARAMETERS
from sih26170.prognostics.locked_models import get_locked_ridge_model
from tests.screening.test_scenarios import make_nominal_lot


def test_exact_shap_efficiency_and_additivity():
    """Verify that Shapley attributions satisfy the mathematical efficiency axiom bit-for-bit."""
    test_cases = {
        "IDSS": (0.08, 0.15),
        "VGS(th)": (3.1, 2.9),
        "RDS(on)": (46.0, 54.0),
        "IGSS": (0.2, 0.8),
    }

    for param, (v0, v24) in test_cases.items():
        model = get_locked_ridge_model(param)
        eff_u, raw_u, is_div = model.predict_transformed(v0, v24)
        shap_res = model.compute_shap_attributions(v0, v24)

        phi_0 = shap_res["base_value_u"]
        phi_base = shap_res["shap_values"]["baseline_0h"]
        phi_slope = shap_res["shap_values"]["slope_0_24"]

        reconstructed_u = phi_0 + phi_base + phi_slope
        assert math.isclose(reconstructed_u, raw_u, rel_tol=1e-10, abs_tol=1e-10), (
            f"SHAP efficiency violation for {param}: {reconstructed_u} != {raw_u}"
        )


def test_shap_identifies_slope_as_primary_driver_on_drifting_component():
    """Verify that a component undergoing burn-in drift identifies slope_0_24 as primary driver."""
    model = get_locked_ridge_model("RDS(on)")
    # Baseline at nominal (45 mOhm) but active drift to 56 mOhm at 24h
    shap_res = model.compute_shap_attributions(45.0, 56.0)

    assert shap_res["primary_driver"] == "slope_0_24"
    assert shap_res["shap_values"]["slope_0_24"] > 0
    assert abs(shap_res["shap_values"]["slope_0_24"]) > abs(shap_res["shap_values"]["baseline_0h"])
    assert "slope_0_24 was the primary driver" in shap_res["explanation"]


def test_shap_identifies_baseline_as_primary_driver_on_stationary_component():
    """Verify that a high baseline stationary component identifies baseline_0h as primary driver."""
    model = get_locked_ridge_model("RDS(on)")
    # High baseline (58 mOhm vs 45 mOhm nominal) but completely stationary (58 mOhm at 24h)
    shap_res = model.compute_shap_attributions(58.0, 58.0)

    assert shap_res["primary_driver"] == "baseline_0h"
    assert math.isclose(shap_res["shap_values"]["slope_0_24"], 0.0, abs_tol=1e-10)
    assert abs(shap_res["shap_values"]["baseline_0h"]) > 0
    assert "baseline_0h was the primary driver" in shap_res["explanation"]


def test_pipeline_integration_contains_shap_metadata():
    """Verify that run_component_pipeline embeds SHAP attributions in forecasts and explainability."""
    df = make_nominal_lot(n_components=10)
    # Set C001 to have active IDSS drift
    df.loc[(df["component_id"] == "LOT_TEST_C001") & (df["parameter_name"] == "IDSS") & (df["elapsed_hours"] == 24), "value"] = 0.5

    result = run_component_pipeline(telemetry=df, component_id="LOT_TEST_C001", as_of_hours=24)

    fc = result.prognostic_forecasts["IDSS"]
    assert fc.shap_attributions is not None
    assert "slope_0_24" in fc.shap_attributions
    assert fc.primary_driver in ("slope_0_24", "baseline_0h")

    # Check explainability card
    exp = result.explainability
    assert "IDSS" in exp.what_predicted
    assert exp.what_predicted["IDSS"]["primary_driver"] is not None
    assert "Linear SHAP Driver:" in exp.ascii_summary
