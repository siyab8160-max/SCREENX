"""Backward-compatible entrypoint for Empirical Technical Evaluation.

Preserves full API compatibility for scripts and modules importing from
benchmarks.empirical_improvements_study.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from benchmarks.empirical_study import (
    load_benchmark_datasets,
    run_full_empirical_study,
    main,
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
from sih26170.screening.joint import evaluate_multivariate_joint_backstop
from sih26170.screening.risk import evaluate_cost_sensitive_risk

# Backward compatibility aliases
run_full_empirical_study = run_full_empirical_study
audit_explainability_and_counterfactuals = audit_counterfactual_inversions

__all__ = [
    "load_benchmark_datasets",
    "run_full_empirical_study",
    "run_full_empirical_study",
    "audit_counterfactual_inversions",
    "audit_explainability_and_counterfactuals",
    "get_known_limitations_disclosure",
    "evaluate_nested_cv_lambda_sweep",
    "evaluate_regime_conditional_conformal",
    "evaluate_relative_vs_direct_drift",
    "evaluate_multivariate_joint_backstop",
    "evaluate_cost_sensitive_risk",
    "main",
]

if __name__ == "__main__":
    main()
