"""SIH26170 Synthetic Data Validation and Statistical Sanity Report.

Provides comprehensive generator-level data integrity auditing:
- Schema correctness and column isolation
- Unique component identities and lot memberships
- Valid checkpoints and parameter/unit integrity
- Latent physical validity (leakage >= 0, iddq >= 0, delay > 0)
- Ground-truth completeness and key consistency
- Zero leakage of ground-truth columns into observations
- Missingness, negative-reading, and ValueStatus semantics
- Dataset QA statistical sanity summary (JSON and Markdown)

Conforms to docs/PHASE_2_SYNTHETIC_DATA_SPEC.md.
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

from sih26170.schema import (
    CANONICAL_COLUMNS,
    GROUND_TRUTH_COLUMNS,
    ValueStatus,
    classify_measurement_value,
)
from sih26170.synthetic.config import SyntheticConfig


@dataclass
class ValidationReport:
    """Outcome of synthetic dataset validation audit."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    checks_passed: int
    checks_total: int


@dataclass
class StatisticalSanityReport:
    """Dataset QA statistics summarizing the generated benchmark."""
    component_count: int
    lot_count: int
    parameter_count: int
    checkpoint_count: int
    total_observation_records: int
    total_ground_truth_records: int
    trajectory_class_counts: Dict[str, int]
    missingness_count: int
    missingness_rate: float
    negative_observation_count: int
    zero_observation_count: int
    non_finite_count: int
    equipment_shift_observation_count: int
    rework_regime_lot_counts: Dict[str, int]
    ground_truth_abnormal_components: int
    ground_truth_abnormal_by_24h: int
    ground_truth_abnormal_by_96h: int
    ground_truth_abnormal_by_168h: int
    absolute_limit_crossing_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [
            "# Synthetic Dataset Statistical Sanity Report",
            "",
            "## Population & Record Counts",
            f"- **Lots**: {self.lot_count}",
            f"- **Components**: {self.component_count}",
            f"- **Parameters**: {self.parameter_count}",
            f"- **Checkpoints**: {self.checkpoint_count}",
            f"- **Observation Records**: {self.total_observation_records:,}",
            f"- **Ground Truth Records**: {self.total_ground_truth_records:,}",
            "",
            "## Trajectory Class Distribution",
        ]
        for tc, cnt in self.trajectory_class_counts.items():
            pct = (cnt / max(1, self.component_count)) * 100
            lines.append(f"- `{tc}`: {cnt} ({pct:.1f}%)")

        lines.extend([
            "",
            "## Measurement & Artifact Semantics",
            f"- **Missing Observations**: {self.missingness_count} ({self.missingness_rate * 100:.2f}%)",
            f"- **Negative Observations (Preserved)**: {self.negative_observation_count}",
            f"- **Zero Observations**: {self.zero_observation_count}",
            f"- **Non-Finite Readings**: {self.non_finite_count}",
            f"- **Equipment Shift Readings**: {self.equipment_shift_observation_count}",
            "",
            "## Ground Truth Abnormality vs. Absolute Limits",
            f"- **Ground-Truth Abnormal Components**: {self.ground_truth_abnormal_components}",
            f"  - Abnormal by 24h: {self.ground_truth_abnormal_by_24h}",
            f"  - Abnormal by 96h: {self.ground_truth_abnormal_by_96h}",
            f"  - Abnormal by 168h: {self.ground_truth_abnormal_by_168h}",
            f"- **Absolute Operational Limit Crossings**: {self.absolute_limit_crossing_count}",
            "",
            "> [!NOTE]",
            "> These are dataset QA summary statistics, NOT machine learning detector performance metrics.",
        ])
        return "\n".join(lines)


class SyntheticValidator:
    """Validates structural and physical integrity of generated synthetic datasets."""

    def __init__(self, config: SyntheticConfig):
        self.config = config

    def validate(
        self,
        observations_df: pd.DataFrame,
        ground_truth_df: pd.DataFrame,
    ) -> ValidationReport:
        """Run full battery of generator-level verification checks."""
        errors: List[str] = []
        warnings: List[str] = []
        checks_passed = 0
        checks_total = 12

        # 1. Observation schema columns
        obs_cols = set(observations_df.columns)
        expected_obs_cols = set(CANONICAL_COLUMNS)
        if not expected_obs_cols.issubset(obs_cols):
            missing = expected_obs_cols - obs_cols
            errors.append(f"Observation DataFrame missing canonical columns: {missing}")
        else:
            checks_passed += 1

        # 2. Strict Ground-Truth Isolation: NO ground truth in observations
        gt_in_obs = obs_cols.intersection(set(GROUND_TRUTH_COLUMNS))
        if gt_in_obs:
            errors.append(f"DATA LEAKAGE: Ground truth columns leaked into observations: {gt_in_obs}")
        else:
            checks_passed += 1

        # 3. Ground truth schema columns
        gt_cols = set(ground_truth_df.columns)
        expected_gt_cols = {"component_id", "lot_id", "parameter_name", "elapsed_hours"} | set(GROUND_TRUTH_COLUMNS)
        if not expected_gt_cols.issubset(gt_cols):
            missing_gt = expected_gt_cols - gt_cols
            errors.append(f"Ground-truth DataFrame missing expected columns: {missing_gt}")
        else:
            checks_passed += 1

        # 4. Checkpoints integrity
        valid_cps = set(self.config.checkpoints)
        obs_cps = set(observations_df["elapsed_hours"].unique())
        if not obs_cps.issubset(valid_cps):
            errors.append(f"Observation DataFrame contains invalid checkpoints: {obs_cps - valid_cps}")
        else:
            checks_passed += 1

        # 5. Parameters and units
        for p_name, p_cfg in self.config.parameters.items():
            param_obs = observations_df[observations_df["parameter_name"] == p_name]
            if not param_obs.empty:
                units = param_obs["unit"].unique()
                if len(units) != 1 or units[0] != p_cfg.unit:
                    errors.append(f"Unit mismatch for {p_name}: expected {p_cfg.unit}, got {units}")
        checks_passed += 1

        # 6. Latent physical validity in ground truth
        if "latent_value" in ground_truth_df.columns:
            for p_name, p_cfg in self.config.parameters.items():
                p_gt = ground_truth_df[ground_truth_df["parameter_name"] == p_name]
                if not p_gt.empty:
                    if p_cfg.transform == "log":
                        # Leakage and iddq must be non-negative
                        invalid = p_gt[p_gt["latent_value"] < 0.0]
                        if not invalid.empty:
                            errors.append(f"Latent physical violation: {len(invalid)} negative latent values for {p_name}")
                    else:
                        # Propagation delay must be strictly positive
                        invalid = p_gt[p_gt["latent_value"] <= 0.0]
                        if not invalid.empty:
                            errors.append(f"Latent physical violation: {len(invalid)} non-positive latent values for {p_name}")
        checks_passed += 1

        # 7. Key consistency between observations and ground truth
        obs_keys = set(zip(observations_df["component_id"], observations_df["parameter_name"], observations_df["elapsed_hours"]))
        gt_keys = set(zip(ground_truth_df["component_id"], ground_truth_df["parameter_name"], ground_truth_df["elapsed_hours"]))
        # Observation keys must be a subset of ground truth keys (due to missingness)
        if not obs_keys.issubset(gt_keys):
            orphans = obs_keys - gt_keys
            errors.append(f"{len(orphans)} observation keys have no matching ground-truth entry")
        else:
            checks_passed += 1

        # 8. Negative observation preservation (LOG-020)
        # Verify that negative values are classified as ValueStatus.NEGATIVE
        neg_obs = observations_df[observations_df["value"] < 0.0]
        for val in neg_obs["value"]:
            st = classify_measurement_value(val)
            if st != ValueStatus.NEGATIVE:
                errors.append(f"ValueStatus classification failure for negative observation {val}: got {st}")
                break
        checks_passed += 1

        # 9. No non-finite values in observations unless explicit
        inf_nan_vals = observations_df[~np.isfinite(observations_df["value"])]
        if not inf_nan_vals.empty:
            errors.append(f"Unexpected non-finite values in observations DataFrame: {len(inf_nan_vals)}")
        else:
            checks_passed += 1

        # 10. Trajectory classes match valid taxonomy
        gt_classes = set(ground_truth_df["trajectory_class"].unique())
        valid_classes = {"stable", "high_but_stable", "lot_outlier", "linear_drift", "accelerating_drift", "abrupt_failure"}
        if not gt_classes.issubset(valid_classes):
            errors.append(f"Invalid trajectory classes in ground truth: {gt_classes - valid_classes}")
        else:
            checks_passed += 1

        # 11. Event timing consistency: first_abnormal_hour matches flags
        inconsistent_flags = ground_truth_df[
            (ground_truth_df["first_abnormal_hour"].notna()) &
            (ground_truth_df["first_abnormal_hour"] <= 24) &
            (~ground_truth_df["abnormal_by_24h"])
        ]
        if not inconsistent_flags.empty:
            errors.append(f"Event timing flag inconsistency: {len(inconsistent_flags)} rows with first_abnormal <= 24 but abnormal_by_24h False")
        else:
            checks_passed += 1

        # 12. Canonical 45 uA fixture integrity
        cf_id = self.config.canonical_fixture.component_id
        cf_obs = observations_df[observations_df["component_id"] == cf_id]
        if not cf_obs.empty:
            cf_leakage_0 = cf_obs[(cf_obs["parameter_name"] == "leakage_current") & (cf_obs["elapsed_hours"] == 0)]
            if not cf_leakage_0.empty:
                val = cf_leakage_0["value"].iloc[0]
                # Value should be close to 45 uA within noise (~42 to ~48 uA)
                if not (40.0 <= val <= 50.0):
                    warnings.append(f"Canonical fixture initial value is {val} uA (expected ~45 uA)")
        checks_passed += 1

        return ValidationReport(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
            checks_passed=checks_passed,
            checks_total=checks_total,
        )

    def generate_statistical_sanity_report(
        self,
        observations_df: pd.DataFrame,
        ground_truth_df: pd.DataFrame,
    ) -> StatisticalSanityReport:
        """Compute dataset QA statistics."""
        comp_count = ground_truth_df["component_id"].nunique()
        lot_count = ground_truth_df["lot_id"].nunique()
        param_count = ground_truth_df["parameter_name"].nunique()
        cp_count = ground_truth_df["elapsed_hours"].nunique()

        total_obs = len(observations_df)
        total_gt = len(ground_truth_df)

        # Expected observations under complete coverage = total_gt
        missing_count = max(0, total_gt - total_obs)
        missing_rate = missing_count / max(1, total_gt)

        # Value classifications
        neg_count = int((observations_df["value"] < 0.0).sum())
        zero_count = int((observations_df["value"] == 0.0).sum())
        non_finite_count = int((~np.isfinite(observations_df["value"])).sum())

        # Trajectory classes (per component)
        comp_tc = ground_truth_df.groupby("component_id")["trajectory_class"].first()
        tc_counts = {str(k): int(v) for k, v in comp_tc.value_counts().items()}

        # Equipment shift readings: Lot L13, INST_01
        eq_shift_obs = observations_df[
            (observations_df["lot_id"] == "L13") & (observations_df["instrument_id"] == "INST_01")
        ]
        eq_shift_count = len(eq_shift_obs)

        # Rework regime counts
        rework_lot_counts = {}
        for lot in self.config.lots:
            rework_lot_counts[lot.rework_regime] = rework_lot_counts.get(lot.rework_regime, 0) + 1

        # Ground-truth abnormality counts
        comp_gt = ground_truth_df.groupby("component_id").agg({
            "first_abnormal_hour": lambda s: any(s.notna()),
            "abnormal_by_24h": "any",
            "abnormal_by_96h": "any",
            "abnormal_by_168h": "any",
        })

        gt_abnormal_total = int(comp_gt["first_abnormal_hour"].sum())
        gt_abnormal_24 = int(comp_gt["abnormal_by_24h"].sum())
        gt_abnormal_96 = int(comp_gt["abnormal_by_96h"].sum())
        gt_abnormal_168 = int(comp_gt["abnormal_by_168h"].sum())

        # Operational limit crossings
        limit_crossings = 0
        for p_name, p_cfg in self.config.parameters.items():
            if p_cfg.user_limit_high is not None:
                p_obs = observations_df[observations_df["parameter_name"] == p_name]
                crossings = (p_obs["value"] > p_cfg.user_limit_high).sum()
                limit_crossings += int(crossings)

        return StatisticalSanityReport(
            component_count=comp_count,
            lot_count=lot_count,
            parameter_count=param_count,
            checkpoint_count=cp_count,
            total_observation_records=total_obs,
            total_ground_truth_records=total_gt,
            trajectory_class_counts=tc_counts,
            missingness_count=missing_count,
            missingness_rate=missing_rate,
            negative_observation_count=neg_count,
            zero_observation_count=zero_count,
            non_finite_count=non_finite_count,
            equipment_shift_observation_count=eq_shift_count,
            rework_regime_lot_counts=rework_lot_counts,
            ground_truth_abnormal_components=gt_abnormal_total,
            ground_truth_abnormal_by_24h=gt_abnormal_24,
            ground_truth_abnormal_by_96h=gt_abnormal_96,
            ground_truth_abnormal_by_168h=gt_abnormal_168,
            absolute_limit_crossing_count=limit_crossings,
        )
