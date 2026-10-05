"""Backward-compatible test runner for SCREENX Empirical Technical Evaluation.

Maintains complete continuity with tests/test_competitor_improvements.py
and delegates directly to the comprehensive evaluation suite in tests/test_empirical_study.py.
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

import pytest

# Import all fixtures and tests from test_empirical_study
from tests.test_empirical_study import (
    benchmark_data,
    test_metric_1_1_cost_sensitive_monotonicity,
    test_metric_1_2_joint_mahalanobis_backstop,
    test_metric_1_3_union_fusion_precedence,
    test_metric_2_1_relative_vs_direct_drift,
    test_metric_2_2_regularization_cv_valley,
    test_metric_2_3_regime_conditional_conformal,
    test_metric_3_counterfactual_exact_inversion,
    test_metric_3_known_limitations_disclosure,
    test_full_empirical_study_fast_execution,
)

__all__ = [
    "benchmark_data",
    "test_metric_1_1_cost_sensitive_monotonicity",
    "test_metric_1_2_joint_mahalanobis_backstop",
    "test_metric_1_3_union_fusion_precedence",
    "test_metric_2_1_relative_vs_direct_drift",
    "test_metric_2_2_regularization_cv_valley",
    "test_metric_2_3_regime_conditional_conformal",
    "test_metric_3_counterfactual_exact_inversion",
    "test_metric_3_known_limitations_disclosure",
    "test_full_empirical_study_fast_execution",
]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
