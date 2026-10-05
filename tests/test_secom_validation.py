"""Tests for external UCI SECOM semiconductor manufacturing benchmark."""

from pathlib import Path
import pytest
from benchmarks.secom_validation import (
    load_secom_dataset,
    evaluate_module_a_on_secom,
    format_ascii_report,
    run_secom_benchmark,
)

DATA_DIR = Path("data/secom")


@pytest.mark.skipif(not (DATA_DIR / "secom.data").exists(), reason="SECOM dataset files not found")
def test_secom_dataset_loading():
    X, y = load_secom_dataset(DATA_DIR)
    assert X.shape == (1567, 590)
    assert len(y) == 1567
    assert sum(y) == 104
    assert 0.06 < (sum(y) / len(y)) < 0.07


@pytest.mark.skipif(not (DATA_DIR / "secom.data").exists(), reason="SECOM dataset files not found")
def test_secom_module_a_enrichment():
    X, y = load_secom_dataset(DATA_DIR)
    res = evaluate_module_a_on_secom(X, y)

    assert res["total_wafers"] == 1567
    assert res["actual_process_failures"] == 104
    assert res["informative_features_retained"] > 400

    top_20 = res["top_20_anomalous_summary"]
    assert top_20["flagged_wafers"] == 20
    assert top_20["true_process_failures"] >= 5
    assert top_20["lift_factor"] >= 3.0  # Greater than 3x baseline prevalence

    cohorts = res["cohort_evaluations"]
    assert len(cohorts) >= 4
    for c in cohorts:
        assert c["extreme_count_lift"] > 1.5  # Consistent positive lift across cohorts


@pytest.mark.skipif(not (DATA_DIR / "secom.data").exists(), reason="SECOM dataset files not found")
def test_secom_ascii_and_runner():
    res = run_secom_benchmark(data_dir=DATA_DIR)
    assert "UCI SECOM" in res["dataset_name"]
    report = format_ascii_report(res)
    assert "ISRO SCREENX // EXTERNAL SEMICONDUCTOR VALIDATION" in report
    assert "COHORT SCREENING ENRICHMENT TABLE" in report
