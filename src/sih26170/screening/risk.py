"""Cost-sensitive risk modeling and asymmetric loss evaluation for screening.

In high-reliability aerospace and defense screening (MIL-PRF-19500 / MIL-STD-883),
the operational cost of an undetected escape (False Negative) severely exceeds
the cost of an unnecessary re-test or scrap (False Positive).

Loss function:
    L(r) = C_FN * FN + C_FP * FP
Normalized per-component risk across cost ratios r = C_FN / C_FP (e.g., 20:1).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
import pandas as pd

from sih26170.screening.pipeline import screen_lot
from sih26170.screening.schema import ScreeningState
from sih26170.screening.specification import SPEC_LIMITS_CLASS_A

PRIMARY_PARAMETERS = ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]
DEFAULT_COST_RATIOS = [1.0, 2.0, 5.0, 10.0, 20.0, 50.0]


def compute_confusion_matrix(flagged_set: Set[str], lot_components: List[str], comp_gt: pd.DataFrame) -> Dict[str, int]:
    """Compute binary classification confusion matrix against ground truth."""
    tp = sum(1 for cid in lot_components if cid in flagged_set and comp_gt.loc[cid, "is_defective"])
    fp = sum(1 for cid in lot_components if cid in flagged_set and not comp_gt.loc[cid, "is_defective"])
    fn = sum(1 for cid in lot_components if cid not in flagged_set and comp_gt.loc[cid, "is_defective"])
    tn = sum(1 for cid in lot_components if cid not in flagged_set and not comp_gt.loc[cid, "is_defective"])
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def evaluate_cost_sensitive_risk(
    obs_df: pd.DataFrame,
    gt_df: pd.DataFrame,
    lot_ids: List[str],
    checkpoint: int = 24,
    cost_ratios: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Evaluates cost-sensitive threshold selection and total risk curves.

    Asymmetric cost model:
        Loss(r) = C_FN * FN + C_FP * FP, normalized per component.
    """
    if cost_ratios is None:
        cost_ratios = DEFAULT_COST_RATIOS

    available_lots = set(obs_df["lot_id"].unique())
    target_lots = [lid for lid in lot_ids if lid in available_lots]
    if not target_lots:
        raise ValueError(f"None of requested lots {lot_ids} exist in observation data.")

    # Build component-level ground truth: defective if degraded or spec failure over burn-in
    comp_gt = gt_df.groupby("component_id")[["is_degradation", "is_spec_failure"]].any()
    comp_gt["is_defective"] = comp_gt["is_degradation"] | comp_gt["is_spec_failure"]
    lot_components = obs_df[obs_df["lot_id"].isin(target_lots)]["component_id"].unique().tolist()
    n_total = len(lot_components)

    # 1. Evaluate Static Limits Only (Baseline)
    obs_ckpt = obs_df[(obs_df["component_id"].isin(lot_components)) & (obs_df["elapsed_hours"] == checkpoint)]
    static_flagged: Set[str] = set()
    for _, row in obs_ckpt.iterrows():
        p = row["parameter_name"]
        val = row["value"]
        lim = SPEC_LIMITS_CLASS_A.get(p, {})
        low = lim.get("low") if "low" in lim else lim.get("absolute_limit_low")
        high = lim.get("high") if "high" in lim else lim.get("absolute_limit_high")
        if (low is not None and val < low) or (high is not None and val > high):
            static_flagged.add(row["component_id"])

    # 2. Evaluate SCREENX Dynamic Screening Pipeline (with D_joint backstop)
    screenx_flagged: Set[str] = set()
    for lot_id in sorted(target_lots):
        results = screen_lot(obs_df, lot_id, checkpoint)
        for r in results:
            if r.final_state in (ScreeningState.ALERT, ScreeningState.HOLD, ScreeningState.FAIL):
                screenx_flagged.add(r.component_id)

    cm_static = compute_confusion_matrix(static_flagged, lot_components, comp_gt)
    cm_screenx = compute_confusion_matrix(screenx_flagged, lot_components, comp_gt)

    cost_curves = []
    for r in cost_ratios:
        c_fp = 1.0
        c_fn = float(r)

        static_total_cost = c_fn * cm_static["fn"] + c_fp * cm_static["fp"]
        screenx_total_cost = c_fn * cm_screenx["fn"] + c_fp * cm_screenx["fp"]

        static_norm_cost = static_total_cost / max(1, n_total)
        screenx_norm_cost = screenx_total_cost / max(1, n_total)

        ratio_improvement = static_total_cost / max(1e-9, screenx_total_cost)

        cost_curves.append({
            "cost_ratio_fn_to_fp": r,
            "c_fn": c_fn,
            "c_fp": c_fp,
            "static_total_cost": static_total_cost,
            "static_normalized_cost": float(round(static_norm_cost, 4)),
            "screenx_total_cost": screenx_total_cost,
            "screenx_normalized_cost": float(round(screenx_norm_cost, 4)),
            "cost_reduction_ratio": float(round(ratio_improvement, 3)),
        })

    # Detailed evaluation at standard aerospace critical ratio 20:1
    c20 = next(c for c in cost_curves if abs(c["cost_ratio_fn_to_fp"] - 20.0) < 1e-3)

    return {
        "metric_id": "1.1",
        "description": "Cost-sensitive risk minimization (asymmetric escape penalty)",
        "lots_evaluated": target_lots,
        "n_components": n_total,
        "static_confusion_matrix": cm_static,
        "screenx_confusion_matrix": cm_screenx,
        "aerospace_standard_ratio_20": c20,
        "cost_curves": cost_curves,
    }
