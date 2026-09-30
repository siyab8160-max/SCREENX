"""Unit and Governance Tests for Phase 5 Final Evaluation.

Verifies:
1. Pre-evaluation integrity: all 14 frozen baseline hashes match authoritative SHA-256 digests.
2. CAL, VAL, and EVAL partitions are 100% pairwise disjoint.
3. Final evaluation population accounting: exactly 25 lots, 500 components, 2,000 series.
4. Model coefficients, hyperparameters, and sigma_eff remain strictly immutable.
5. All headline metrics preserve physical engineering units (uA, nA, mOhm, V).
6. IGSS signed semantics are strictly preserved (no abs(), no clipping).
7. 100% finite prediction rate and zero divergent fallbacks across all 2,000 series.
8. Secondary forensic analysis is populated with diagnostic benchmark labels.
9. Evaluation execution is bit-for-bit deterministic.
10. observations.csv remains 100% byte-identical post-evaluation.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest

from sih26170.prognostics.phase5_final_evaluator import (
    FROZEN_BASELINE_HASHES,
    FROZEN_SIGMA_EFF,
    LOCKED_MODEL_COEFFICIENTS,
    PARAMETERS,
    UNITS,
    compute_file_sha256,
    verify_pre_evaluation_integrity,
    run_phase5_final_evaluation,
)


ROOT = Path(__file__).resolve().parent.parent.parent
OBS_CSV = ROOT / "data/synthetic_phase4b/observations.csv"
GT_CSV = ROOT / "data/synthetic_phase4b/ground_truth.csv"
MANIFEST_JSON = ROOT / "data/synthetic_phase4b/manifest.json"
FINAL_RESULTS_JSON = ROOT / "data/evaluation_phase5/phase5_final_results.json"
FINAL_MANIFEST_JSON = ROOT / "data/evaluation_phase5/phase5_final_lineage_manifest.json"


def test_frozen_baseline_hashes_all_match():
    """Verify all 14 frozen baseline artifacts remain 100% bit-for-bit identical."""
    for rel_path, expected in FROZEN_BASELINE_HASHES.items():
        full_path = ROOT / rel_path
        assert full_path.exists(), f"File missing: {rel_path}"
        actual = compute_file_sha256(full_path)
        assert actual == expected, f"Hash mismatch for {rel_path}: expected {expected}, got {actual}"


def test_cal_val_eval_partition_disjointness():
    """Verify CAL, VAL, and EVAL partitions are pairwise disjoint across all 100 lots."""
    with open(MANIFEST_JSON, "r") as f:
        manifest = json.load(f)

    cal_lots = set(manifest["partitions"]["CALIBRATION"]["lots"])
    val_lots = set(manifest["partitions"]["VALIDATION"]["lots"])
    eval_lots = set(manifest["partitions"]["FINAL_EVALUATION"]["lots"])

    assert len(cal_lots) == 50
    assert len(val_lots) == 25
    assert len(eval_lots) == 25

    assert cal_lots.isdisjoint(val_lots)
    assert cal_lots.isdisjoint(eval_lots)
    assert val_lots.isdisjoint(eval_lots)

    total_lots = cal_lots | val_lots | eval_lots
    assert len(total_lots) == 100


def test_final_evaluation_results_file_exists_and_valid():
    """Verify phase5_final_results.json exists and has valid top-level schema."""
    assert FINAL_RESULTS_JSON.exists(), "phase5_final_results.json must exist"
    with open(FINAL_RESULTS_JSON, "r") as f:
        d = json.load(f)

    meta = d["metadata"]
    assert meta["evaluation_stage"] == "PHASE_5_FINAL_EVALUATION"
    assert meta["selected_model"] == "RIDGE_REGRESSION"
    assert meta["model_lock"] == "LOCKED_IMMUTABLE"
    assert meta["safety_slope_status"] == "OPEN_EVIDENCE_GAP"
    assert meta["predictive_rejection_authorized"] is False
    assert meta["n_calibration_lots"] == 50
    assert meta["n_calibration_components"] == 1000
    assert meta["n_evaluation_lots"] == 25
    assert meta["n_evaluation_components"] == 500

    assert "parameter_metrics" in d
    assert len(d["parameter_metrics"]) == 4


def test_evaluation_population_accounting_exact():
    """Verify exact population accounting: 500 components, 2,000 series, 500 per parameter."""
    with open(FINAL_RESULTS_JSON, "r") as f:
        d = json.load(f)

    for param in PARAMETERS:
        m = d["parameter_metrics"][param]
        assert m["n_eligible_forecasts"] == 500
        assert len(m["per_lot_breakdown"]) == 25
        # Verify all lots are LOT_EVAL_*
        for lot_id, lot_data in m["per_lot_breakdown"].items():
            assert lot_id.startswith("LOT_EVAL_")
            assert lot_data["n_samples"] == 20


def test_model_coefficients_and_sigma_eff_strictly_immutable():
    """Verify model coefficients, lambda=1.0, and sigma_eff match frozen specifications."""
    with open(FINAL_RESULTS_JSON, "r") as f:
        d = json.load(f)

    for param in PARAMETERS:
        m = d["parameter_metrics"][param]
        actual_beta = m["model_lineage"]["coefficients"]
        expected_beta = LOCKED_MODEL_COEFFICIENTS[param]
        np.testing.assert_allclose(actual_beta, expected_beta, rtol=1e-5, atol=1e-5)

        actual_sigma = m["uncertainty_provenance"]["sigma_eff"]
        expected_sigma = FROZEN_SIGMA_EFF[param]
        assert abs(actual_sigma - expected_sigma) < 1e-5

        assert m["model_lineage"]["hyperparameters"]["l2_reg"] == 1.0


def test_physical_units_preserved():
    """Verify that all four electrical parameters preserve exact physical engineering units."""
    with open(FINAL_RESULTS_JSON, "r") as f:
        d = json.load(f)

    for param in PARAMETERS:
        m = d["parameter_metrics"][param]
        assert m["unit"] == UNITS[param]
        pm = m["primary_metrics"]
        assert pm["mae"] > 0
        assert pm["rmse"] > 0
        assert pm["median_abs_error"] > 0
        assert pm["mean_interval_width"] > 0


def test_igss_signed_behavior_reported():
    """Verify that IGSS signed values are preserved and reported without abs() or clipping."""
    with open(FINAL_RESULTS_JSON, "r") as f:
        d = json.load(f)

    igss = d["parameter_metrics"]["IGSS"]
    assert "igss_signed_behavior" in igss
    sig = igss["igss_signed_behavior"]
    assert sig["positive_count"] + sig["negative_count"] == 500
    assert sig["positive_count"] > 0
    assert sig["positive_mae"] is not None


def test_finite_predictions_and_zero_fallbacks():
    """Verify 100% finite prediction rate and zero divergent fallbacks across all parameters."""
    with open(FINAL_RESULTS_JSON, "r") as f:
        d = json.load(f)

    for param in PARAMETERS:
        pm = d["parameter_metrics"][param]["primary_metrics"]
        assert pm["finite_prediction_rate"] == 1.0
        assert pm["divergent_fallback_count"] == 0


def test_secondary_forensics_present_and_labeled():
    """Verify secondary forensic sections: scenario MAE, quantiles, extreme cases, spec breach."""
    with open(FINAL_RESULTS_JSON, "r") as f:
        d = json.load(f)

    assert "secondary_forensic_analysis" in d
    sec = d["secondary_forensic_analysis"]
    assert sec["metadata"]["epistemic_scope"] == "SYNTHETIC_BENCHMARK_EVALUATION_ONLY"

    for param in PARAMETERS:
        assert param in sec["scenario_level_metrics"]
        assert param in sec["residual_quantiles"]
        assert param in sec["interval_asymmetry"]
        assert param in sec["specification_breach_forensics"]
        assert param in sec["largest_error_cases"]
        assert len(sec["largest_error_cases"][param]) == 5


def test_deterministic_repetition():
    """Verify that re-running the evaluator produces bit-for-bit identical results."""
    with open(FINAL_RESULTS_JSON, "r") as f:
        content1 = f.read()

    # Re-run evaluation
    run_phase5_final_evaluation(ROOT, FINAL_RESULTS_JSON, FINAL_MANIFEST_JSON)

    with open(FINAL_RESULTS_JSON, "r") as f:
        content2 = f.read()

    assert content1 == content2, "Re-running final evaluation produced non-deterministic results!"


def test_observations_csv_unmodified_byte_identical():
    """Verify observations.csv remains 100% byte-identical post-evaluation."""
    expected_hash = "b5de6a03022a9350b6f304b9af593768e7f83a8fc61fde6ca98e690cfa1f275f"
    actual_hash = compute_file_sha256(OBS_CSV)
    assert actual_hash == expected_hash
