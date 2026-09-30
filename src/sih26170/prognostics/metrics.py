"""Evaluation metrics for Module B Prognostics.

Implements:
- MAE (Mean Absolute Error)
- RMSE (Root Mean Squared Error)
- Empirical Interval Coverage
- Mean Prediction Interval Width (MPIW)
- Winkler Score (Penalized Prediction Interval Score)
- Data sufficiency and validity accounting
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np

from sih26170.prognostics.schema import PrognosticForecast


@dataclass(frozen=True)
class EvaluationSummary:
    """Statistical summary of prognostic evaluation."""
    total_count: int
    valid_count: int
    excluded_count: int
    mae: Optional[float]
    rmse: Optional[float]
    coverage_rate: Optional[float]
    mean_interval_width: Optional[float]
    mean_winkler_score: Optional[float]
    unit: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_count": self.total_count,
            "valid_count": self.valid_count,
            "excluded_count": self.excluded_count,
            "mae": self.mae,
            "rmse": self.rmse,
            "coverage_rate": self.coverage_rate,
            "mean_interval_width": self.mean_interval_width,
            "mean_winkler_score": self.mean_winkler_score,
            "unit": self.unit,
        }


def calculate_winkler_score(
    y_true: float,
    lower: float,
    upper: float,
    alpha: float = 0.10,
) -> float:
    """Calculate single-point Winkler score for a (1 - alpha) prediction interval.

    W_alpha = (U - L) + (2 / alpha) * (L - y) * I(y < L) + (2 / alpha) * (y - U) * I(y > U)
    """
    width = upper - lower
    if width < 0:
        raise ValueError(f"Interval width cannot be negative: lower={lower}, upper={upper}")

    score = width
    if y_true < lower:
        score += (2.0 / alpha) * (lower - y_true)
    elif y_true > upper:
        score += (2.0 / alpha) * (y_true - upper)
    return score


def evaluate_forecast_set(
    forecasts: Sequence[PrognosticForecast],
    ground_truth_map: Dict[Tuple[str, str], float],
    alpha: float = 0.10,
) -> EvaluationSummary:
    """Evaluate a sequence of forecasts against true 168h values.

    Args:
        forecasts: Sequence of PrognosticForecast objects
        ground_truth_map: Dict mapping (component_id, parameter_name) -> true_value_at_target
        alpha: Nominal interval significance level (default 0.10 for 90% coverage)

    Returns:
        EvaluationSummary containing MAE, RMSE, coverage, width, Winkler, and counts.
    """
    total = len(forecasts)
    valid_count = 0
    excluded_count = 0

    errors: List[float] = []
    sq_errors: List[float] = []
    coverage_hits: List[int] = []
    widths: List[float] = []
    winkler_scores: List[float] = []
    unit_str = ""

    for f in forecasts:
        if not unit_str and f.unit:
            unit_str = f.unit

        key = (f.component_id, f.parameter_name)
        if key not in ground_truth_map:
            excluded_count += 1
            continue

        true_val = ground_truth_map[key]
        if not np.isfinite(true_val):
            excluded_count += 1
            continue

        if not f.is_valid or not np.isfinite(f.predicted_value):
            excluded_count += 1
            continue

        valid_count += 1
        err = abs(true_val - f.predicted_value)
        errors.append(err)
        sq_errors.append(err ** 2)

        # Interval evaluation if present
        if f.interval_lower is not None and f.interval_upper is not None:
            low = f.interval_lower
            high = f.interval_upper
            hit = 1 if (low <= true_val <= high) else 0
            coverage_hits.append(hit)
            widths.append(high - low)
            w_score = calculate_winkler_score(true_val, low, high, alpha=alpha)
            winkler_scores.append(w_score)

    mae = float(np.mean(errors)) if errors else None
    rmse = float(np.sqrt(np.mean(sq_errors))) if sq_errors else None
    cov = float(np.mean(coverage_hits)) if coverage_hits else None
    mean_w = float(np.mean(widths)) if widths else None
    mean_wink = float(np.mean(winkler_scores)) if winkler_scores else None

    return EvaluationSummary(
        total_count=total,
        valid_count=valid_count,
        excluded_count=excluded_count,
        mae=mae,
        rmse=rmse,
        coverage_rate=cov,
        mean_interval_width=mean_w,
        mean_winkler_score=mean_wink,
        unit=unit_str,
    )
