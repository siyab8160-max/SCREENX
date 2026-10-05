"""Automated test suite for SCREENX Empirical Verification and Technical Evaluation.

Validates core technical capabilities:
1. Metric 1: Cost-sensitive risk minimization, multivariate joint Mahalanobis backstop (D_joint),
   and union/OR fusion precedence.
2. Metric 2: Relative drift target evaluation, nested CV lambda sweeps, and regime-conditional
   conformal calibration.
3. Metric 3: Closed-form counterfactual boundary inversion and explicit known limitations disclosure.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root and src/ are in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import numpy as np
import pandas as pd
import pytest

from benchmarks.empirical_study import (
    load_benchmark_datasets,
    run_full_empirical_study,
)
from sih26170.pipeline.explainability import (
    audit_counterfactual_inversions,
    get_known_limitations_disclosure,
)
from sih26170.prognostics.empirical_validation import (
    evaluate_nested_cv_lambda_sweep,
    evaluate_regime_conditional_conformal,
    evaluate_relative_vs_direct_drift,
)
from sih26170.screening.joint import (
    DEFAULT_JOINT_MAHALANOBIS_THRESHOLD,
    evaluate_multivariate_joint_backstop,
)
from sih26170.screening.risk import evaluate_cost_sensitive_risk

DATA_DIR = REPO_ROOT / "data/synthetic_phase4b"


@pytest.fixture(scope="module")
def benchmark_data():
    """Loads observations and ground truth once for the test module."""
    obs_df, gt_df = load_benchmark_datasets(DATA_DIR)
    return obs_df, gt_df


def test_metric_1_1_cost_sensitive_monotonicity(benchmark_data):
    """Metric 1.1: Verify cost-sensitive risk evaluation and asymmetric cost curves."""
    obs_df, gt_df = benchmark_data
    lots = ["LOT_VAL_001", "LOT_VAL_002", "LOT_VAL_003"]
    res = evaluate_cost_sensitive_risk(obs_df, gt_df, lots, cost_ratios=[1.0, 5.0, 20.0])

    assert res["metric_id"] == "1.1"
    assert len(res["cost_curves"]) == 3

    # As C_FN increases, total cost must monotonically increase for static screening
    static_costs = [c["static_total_cost"] for c in res["cost_curves"]]
    assert static_costs[0] <= static_costs[1] <= static_costs[2]

    # Verify confusion matrix keys
    assert "tp" in res["static_confusion_matrix"]
    assert "fn" in res["static_confusion_matrix"]
    assert "screenx_confusion_matrix" in res


def test_metric_1_2_joint_mahalanobis_backstop(benchmark_data):
    """Metric 1.2: Verify multivariate backstop detector D_joint discrimination."""
    obs_df, gt_df = benchmark_data
    lots = ["LOT_VAL_001", "LOT_VAL_002"]
    res = evaluate_multivariate_joint_backstop(obs_df, gt_df, lots)

    assert res["metric_id"] == "1.2"
    assert res["components_evaluated"] > 0
    assert res["threshold"] == DEFAULT_JOINT_MAHALANOBIS_THRESHOLD
    assert np.isfinite(res["mean_mahalanobis_nominal"])


def test_metric_1_3_union_fusion_precedence(benchmark_data):
    """Metric 1.3: Verify union logic precedence cascade without AND bottlenecks."""
    from sih26170.screening.fusion import fuse_component_evidence
    from sih26170.screening.pipeline import screen_component
    from sih26170.screening.schema import JointEvidence, JointStatus, ScreeningState

    obs_df, _ = benchmark_data
    res = screen_component(obs_df, "LOT_CAL_001_C001", 24)

    dummy_joint = JointEvidence(
        component_id="LOT_CAL_001_C001",
        checkpoint=24,
        mahalanobis_distance=5.2,
        critical_threshold=4.25,
        status=JointStatus.JOINT_ANOMALY_ALERT,
        suspected=True,
        reason_code="JOINT_DRIFT_EXCESS",
    )

    state, qual, reason, all_reasons, comp_flag = fuse_component_evidence(
        res.parameter_results,
        joint_evidence=dummy_joint,
    )

    assert state == ScreeningState.HOLD
    assert comp_flag is True
    assert "JOINT_DRIFT_EXCESS" in all_reasons


def test_metric_2_1_relative_vs_direct_drift(benchmark_data):
    """Metric 2.1: Verify relative drift target comparison across parameters."""
    obs_df, _ = benchmark_data
    cal_lots = ["LOT_CAL_001", "LOT_CAL_002", "LOT_CAL_003"]
    eval_lots = ["LOT_VAL_001", "LOT_VAL_002"]

    res = evaluate_relative_vs_direct_drift(obs_df, cal_lots, eval_lots)

    assert res["metric_id"] == "2.1"
    for param in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]:
        pr = res["parameter_results"][param]
        assert pr["direct_mae"] > 0
        assert pr["relative_mae"] > 0
        assert pr["optimal_target"] in ("relative_delta", "direct_level")


def test_metric_2_2_regularization_cv_valley(benchmark_data):
    """Metric 2.2: Verify lambda sweep confirms lambda=1.0 is in optimal valley."""
    obs_df, _ = benchmark_data
    cal_lots = ["LOT_CAL_001", "LOT_CAL_002", "LOT_CAL_003", "LOT_CAL_004", "LOT_CAL_005"]

    res = evaluate_nested_cv_lambda_sweep(obs_df, cal_lots, lambdas=[0.1, 1.0, 10.0], n_folds=3)

    assert res["metric_id"] == "2.2"
    for param in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]:
        ps = res["parameter_sweeps"][param]
        assert ps["locked_lambda"] == 1.0
        assert ps["gap_to_optimum_pct"] < 10.0


def test_metric_2_3_regime_conditional_conformal(benchmark_data):
    """Metric 2.3: Verify regime-conditional conformal calibration."""
    obs_df, _ = benchmark_data
    cal_lots = ["LOT_CAL_001", "LOT_CAL_002", "LOT_CAL_003"]
    eval_lots = ["LOT_VAL_001", "LOT_VAL_002"]

    res = evaluate_regime_conditional_conformal(obs_df, cal_lots, eval_lots)

    assert res["metric_id"] == "2.3"
    for param in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]:
        pr = res["parameter_results"][param]
        assert 0.0 <= pr["uniform_coverage_overall"] <= 1.0
        assert 0.0 <= pr["regime_conditional_coverage_overall"] <= 1.0


def test_metric_3_counterfactual_exact_inversion(benchmark_data):
    """Metric 3.2: Verify closed-form counterfactual boundary inversion exactness."""
    obs_df, _ = benchmark_data
    cids = obs_df["component_id"].unique()[:3].tolist()
    res = audit_counterfactual_inversions(obs_df, cids)

    assert res["metric_id"] == "3.2"
    assert res["samples_audited"] == 3
    assert res["all_inversions_exact"] is True


def test_metric_3_known_limitations_disclosure():
    """Metric 3.3: Verify explicit known limitations catalog."""
    limitations = get_known_limitations_disclosure()
    assert len(limitations) == 4
    ids = [item["id"] for item in limitations]
    assert any(i.startswith("KL-01") for i in ids)
    assert any(i.startswith("KL-02") for i in ids)
    assert any(i.startswith("KL-03") for i in ids)
    assert any(i.startswith("KL-04") for i in ids)

    for item in limitations:
        assert "title" in item
        assert "category" in item
        assert "description" in item
        assert "benchmark_impact" in item
        assert "operational_mitigation" in item


def test_full_empirical_study_fast_execution(tmp_path):
    """End-to-End: Test fast execution of run_full_empirical_study."""
    out_file = tmp_path / "study_test_report.json"

    report = run_full_empirical_study(
        data_dir=DATA_DIR,
        output_path=out_file,
        lot_limit=3,
    )

    assert "metric_1_anomaly_detection" in report
    assert "metric_2_drift_prediction" in report
    assert "metric_3_explainability" in report
    assert out_file.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
