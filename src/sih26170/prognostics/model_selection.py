"""Phase 5 Module B Pre-Registered Model Selection Protocol.

Implements the deterministic decision rules for selecting between candidate
regression models (Ridge vs. Huber) based strictly on controlled Stage 1 / Stage 1A
Leave-One-Lot-Out (LOLO) cross-validation evidence.

Strict Governance:
- Validation (LOT_VAL_) and final evaluation (LOT_EVAL_) data are strictly prohibited.
- Scenario labels, drift classes, fixture names, and Module A scores are strictly prohibited.
- Zero retraining or hyperparameter tuning is permitted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from sih26170.screening.transforms import NOISE_FLOORS


# Pre-registered negligible difference tolerance: 0.5% relative MAE difference.
# Differences smaller than 0.5% are within empirical ATE repeatability noise.
DEFAULT_RELATIVE_TOLERANCE_MAE: float = 0.005

# Pre-registered nominal empirical coverage window [85.0%, 95.0%] for nominal 90% intervals
COVERAGE_WINDOW_LOWER: float = 0.850
COVERAGE_WINDOW_UPPER: float = 0.950


@dataclass(frozen=True)
class ParameterEvidence:
    """Evidence metrics for a candidate model on a single parameter."""

    parameter_name: str
    unit: str
    model_family: str
    n_samples: int
    mae: float
    rmse: float
    med_ae: float
    coverage_90: float
    mean_interval_width: float
    winkler_score: float
    fold_mae_std: float


@dataclass(frozen=True)
class SelectionDecision:
    """Pre-registered deterministic decision outcome for a parameter."""

    parameter_name: str
    unit: str
    selected_model: str
    primary_metric_name: str
    ridge_metric: float
    huber_metric: float
    metric_difference: float
    relative_difference: float
    decision_tier: str
    decision_rationale: str
    evidence_ridge: ParameterEvidence
    evidence_huber: ParameterEvidence


@dataclass
class ProtocolSummary:
    """Overall pre-registered selection outcome across parameters."""

    selection_unit: str  # 'PARAMETER_DECOUPLED' or 'GLOBAL_CONSENSUS'
    parameter_decisions: Dict[str, SelectionDecision] = field(default_factory=dict)
    global_consensus_family: Optional[str] = None
    win_counts: Dict[str, int] = field(default_factory=dict)
    relative_tolerance_mae: float = DEFAULT_RELATIVE_TOLERANCE_MAE


def compute_winkler_score_90(y_true: np.ndarray, y_lower: np.ndarray, y_upper: np.ndarray) -> float:
    """Compute Winkler score for a 90% prediction interval (alpha = 0.10).

    W = (U - L) + (2/alpha)*(L - y)*I(y < L) + (2/alpha)*(y - U)*I(y > U)
    where 2/alpha = 20 for alpha = 0.10.
    """
    y = np.asarray(y_true, dtype=np.float64)
    l = np.asarray(y_lower, dtype=np.float64)
    u = np.asarray(y_upper, dtype=np.float64)

    width = u - l
    below = np.maximum(0.0, l - y)
    above = np.maximum(0.0, y - u)

    score = width + 20.0 * below + 20.0 * above
    return float(np.mean(score))


class PreRegisteredModelSelector:
    """Pre-registered selection engine executing the frozen decision hierarchy."""

    def __init__(self, relative_tolerance_mae: float = DEFAULT_RELATIVE_TOLERANCE_MAE) -> None:
        self.relative_tolerance_mae = float(relative_tolerance_mae)

    @staticmethod
    def assert_clean_calibration_data(lot_ids: Sequence[str]) -> None:
        """Enforce strict partition quarantine: only LOT_CAL_ lots allowed."""
        for lot in lot_ids:
            lot_str = str(lot)
            if lot_str.startswith("LOT_VAL_"):
                raise PermissionError(
                    f"CRITICAL GOVERNANCE BREACH: Validation lot {lot_str} detected in model selection input."
                )
            if lot_str.startswith("LOT_EVAL_"):
                raise PermissionError(
                    f"CRITICAL GOVERNANCE BREACH: Evaluation lot {lot_str} detected in model selection input."
                )
            if not lot_str.startswith("LOT_CAL_"):
                raise ValueError(
                    f"Unauthorized partition data detected: lot {lot_str} does not belong to calibration set."
                )

    def select_for_parameter(
        self,
        evidence_ridge: ParameterEvidence,
        evidence_huber: ParameterEvidence,
    ) -> SelectionDecision:
        """Apply deterministic 4-tier hierarchy for a single parameter.

        Hierarchy:
        - Tier 1: Primary Physical-Unit MAE.
          If |MAE_ridge - MAE_huber| / min(MAE_ridge, MAE_huber) > tolerance, pick lower MAE.
        - Tier 2: Prediction Interval Quality (Winkler Score).
          If Tier 1 is tied within tolerance, compare mean Winkler score.
        - Tier 3: Cross-Fold Stability (Fold MAE Std).
          If Tier 2 is tied within 0.5% relative tolerance, pick lower fold-to-fold MAE std.
        - Tier 4: Deterministic Tie-Break (Ridge).
          If Tier 3 is tied, default to Ridge due to closed-form analytical simplicity.
        """
        assert evidence_ridge.parameter_name == evidence_huber.parameter_name
        param = evidence_ridge.parameter_name
        unit = evidence_ridge.unit

        mae_r = evidence_ridge.mae
        mae_h = evidence_huber.mae
        min_mae = min(mae_r, mae_h)
        abs_diff_mae = abs(mae_r - mae_h)
        rel_diff_mae = abs_diff_mae / min_mae if min_mae > 1e-12 else 0.0

        # Tier 1: Primary MAE Check
        if rel_diff_mae > self.relative_tolerance_mae:
            if mae_r < mae_h:
                return SelectionDecision(
                    parameter_name=param,
                    unit=unit,
                    selected_model="RIDGE",
                    primary_metric_name="MAE",
                    ridge_metric=mae_r,
                    huber_metric=mae_h,
                    metric_difference=mae_r - mae_h,
                    relative_difference=rel_diff_mae,
                    decision_tier="TIER_1_POINT_MAE",
                    decision_rationale=(
                        f"Ridge achieved lower physical MAE ({mae_r:.5f} {unit}) than Huber "
                        f"({mae_h:.5f} {unit}) with relative difference {rel_diff_mae*100:.2f}% "
                        f"> tolerance {self.relative_tolerance_mae*100:.2f}%."
                    ),
                    evidence_ridge=evidence_ridge,
                    evidence_huber=evidence_huber,
                )
            else:
                return SelectionDecision(
                    parameter_name=param,
                    unit=unit,
                    selected_model="HUBER",
                    primary_metric_name="MAE",
                    ridge_metric=mae_r,
                    huber_metric=mae_h,
                    metric_difference=mae_h - mae_r,
                    relative_difference=rel_diff_mae,
                    decision_tier="TIER_1_POINT_MAE",
                    decision_rationale=(
                        f"Huber achieved lower physical MAE ({mae_h:.5f} {unit}) than Ridge "
                        f"({mae_r:.5f} {unit}) with relative difference {rel_diff_mae*100:.2f}% "
                        f"> tolerance {self.relative_tolerance_mae*100:.2f}%."
                    ),
                    evidence_ridge=evidence_ridge,
                    evidence_huber=evidence_huber,
                )

        # Tier 2: Prediction Interval Quality (Winkler Score)
        ws_r = evidence_ridge.winkler_score
        ws_h = evidence_huber.winkler_score
        min_ws = min(ws_r, ws_h)
        rel_diff_ws = abs(ws_r - ws_h) / min_ws if min_ws > 1e-12 else 0.0

        if rel_diff_ws > self.relative_tolerance_mae:
            if ws_r < ws_h:
                return SelectionDecision(
                    parameter_name=param,
                    unit=unit,
                    selected_model="RIDGE",
                    primary_metric_name="WINKLER_SCORE",
                    ridge_metric=ws_r,
                    huber_metric=ws_h,
                    metric_difference=ws_r - ws_h,
                    relative_difference=rel_diff_ws,
                    decision_tier="TIER_2_UNCERTAINTY_WINKLER",
                    decision_rationale=(
                        f"Point MAE tied within tolerance ({rel_diff_mae*100:.3f}% <= "
                        f"{self.relative_tolerance_mae*100:.2f}%). Ridge achieved superior "
                        f"interval quality with lower Winkler score ({ws_r:.4f} vs {ws_h:.4f})."
                    ),
                    evidence_ridge=evidence_ridge,
                    evidence_huber=evidence_huber,
                )
            else:
                return SelectionDecision(
                    parameter_name=param,
                    unit=unit,
                    selected_model="HUBER",
                    primary_metric_name="WINKLER_SCORE",
                    ridge_metric=ws_r,
                    huber_metric=ws_h,
                    metric_difference=ws_h - ws_r,
                    relative_difference=rel_diff_ws,
                    decision_tier="TIER_2_UNCERTAINTY_WINKLER",
                    decision_rationale=(
                        f"Point MAE tied within tolerance ({rel_diff_mae*100:.3f}% <= "
                        f"{self.relative_tolerance_mae*100:.2f}%). Huber achieved superior "
                        f"interval quality with lower Winkler score ({ws_h:.4f} vs {ws_r:.4f})."
                    ),
                    evidence_ridge=evidence_ridge,
                    evidence_huber=evidence_huber,
                )

        # Tier 3: Cross-Fold Stability (Fold MAE Std)
        std_r = evidence_ridge.fold_mae_std
        std_h = evidence_huber.fold_mae_std
        min_std = min(std_r, std_h)
        rel_diff_std = abs(std_r - std_h) / min_std if min_std > 1e-12 else 0.0

        if rel_diff_std > self.relative_tolerance_mae:
            chosen = "RIDGE" if std_r < std_h else "HUBER"
            better_std = min(std_r, std_h)
            worse_std = max(std_r, std_h)
            return SelectionDecision(
                parameter_name=param,
                unit=unit,
                selected_model=chosen,
                primary_metric_name="FOLD_MAE_STD",
                ridge_metric=std_r,
                huber_metric=std_h,
                metric_difference=std_r - std_h,
                relative_difference=rel_diff_std,
                decision_tier="TIER_3_FOLD_STABILITY",
                decision_rationale=(
                    f"Point MAE and Winkler score tied within tolerance. {chosen} exhibited "
                    f"lower fold-to-fold error dispersion ({better_std:.5f} vs {worse_std:.5f})."
                ),
                evidence_ridge=evidence_ridge,
                evidence_huber=evidence_huber,
            )

        # Tier 4: Deterministic Default Tie-Break (Ridge)
        return SelectionDecision(
            parameter_name=param,
            unit=unit,
            selected_model="RIDGE",
            primary_metric_name="DETERMINISTIC_TIE_BREAK",
            ridge_metric=mae_r,
            huber_metric=mae_h,
            metric_difference=0.0,
            relative_difference=0.0,
            decision_tier="TIER_4_DETERMINISTIC_DEFAULT",
            decision_rationale=(
                "All performance, uncertainty, and stability metrics tied within tolerance. "
                "Defaulting to Ridge based on closed-form analytical simplicity and zero iterative optimization."
            ),
            evidence_ridge=evidence_ridge,
            evidence_huber=evidence_huber,
        )

    def execute_protocol(
        self,
        evidence_dict: Dict[str, Dict[str, ParameterEvidence]],
    ) -> ProtocolSummary:
        """Execute pre-registered protocol across all parameters."""
        summary = ProtocolSummary(
            selection_unit="PARAMETER_DECOUPLED",
            relative_tolerance_mae=self.relative_tolerance_mae,
        )

        win_counts = {"RIDGE": 0, "HUBER": 0}

        for param, models in evidence_dict.items():
            ev_r = models["RIDGE"]
            ev_h = models["HUBER"]
            decision = self.select_for_parameter(ev_r, ev_h)
            summary.parameter_decisions[param] = decision
            win_counts[decision.selected_model] += 1

        summary.win_counts = win_counts

        # Global consensus rule: majority win count (>= 3 out of 4)
        if win_counts["RIDGE"] >= 3:
            summary.global_consensus_family = "RIDGE"
        elif win_counts["HUBER"] >= 3:
            summary.global_consensus_family = "HUBER"
        else:
            summary.global_consensus_family = "SPLIT"

        return summary
