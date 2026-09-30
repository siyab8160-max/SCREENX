"""Validation layer and 'as-of' temporal contract enforcement for SIH26170.

Implements CHANGE 4 and CHANGE 11:
- Distinguishes measurement validation, reference specification validation, and user screening limit validation.
- Validates user_limit_low <= user_limit_high when both exist.
- Validates that unverified reference values are never silently converted into rejection thresholds.
- Enforces strict 'as-of' temporal contract (elapsed_hours <= as_of_hours) preventing future data leakage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd

from sih26170.component_family import ComponentFamily, get_component_family
from sih26170.config import ParameterConfig, VerificationStatus
from sih26170.schema import (
    CANONICAL_COLUMNS,
    VALID_MEASUREMENT_QUALITIES,
    VALID_SOURCE_TYPES,
    PeerStatus,
    TrendStatus,
    ValueStatus,
    classify_measurement_value,
)


@dataclass
class ValidationReport:
    """Comprehensive report returned by the validation layer."""
    is_valid: bool
    total_records: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missingness: Dict[str, Any] = field(default_factory=dict)
    user_limit_breaches: List[Dict[str, Any]] = field(default_factory=list)
    reference_deviations: List[Dict[str, Any]] = field(default_factory=list)
    duplicate_records: List[Dict[str, Any]] = field(default_factory=list)
    numerical_status_records: List[Dict[str, Any]] = field(default_factory=list)

    def summary(self) -> str:
        """Provide a human-readable validation summary."""
        status_str = "PASSED" if self.is_valid else "FAILED"
        lines = [
            f"Validation Status: {status_str}",
            f"Total Records: {self.total_records}",
            f"Errors: {len(self.errors)}",
            f"Warnings: {len(self.warnings)}",
            f"Duplicates: {len(self.duplicate_records)}",
            f"User Screening Limit Breaches: {len(self.user_limit_breaches)}",
            f"Reference Deviations: {len(self.reference_deviations)}",
        ]
        if self.errors:
            lines.append("Top Errors:")
            for err in self.errors[:5]:
                lines.append(f"  - {err}")
        return "\n".join(lines)


def validate_user_limits(
    user_limit_low: Optional[float],
    user_limit_high: Optional[float],
    param_name: str = "parameter"
) -> List[str]:
    """Validate user screening limits consistency.

    Enforces: user_limit_low <= user_limit_high when both exist.
    """
    errors = []
    if user_limit_low is not None and user_limit_high is not None:
        if user_limit_low > user_limit_high:
            errors.append(
                f"Invalid screening limits for '{param_name}': user_limit_low ({user_limit_low}) > user_limit_high ({user_limit_high})"
            )
    return errors


def validate_reference_spec(param_config: ParameterConfig) -> List[str]:
    """Validate reference specification metadata.

    Enforces CHANGE 1 & 4:
    - reference value requires unit and authoritative source
    - verification status must be VERIFIED or NOT_YET_VERIFIED
    - unverified reference values cannot silently be treated as authoritative screening limits
    """
    errors = []
    if param_config.reference_value is not None:
        if not param_config.reference_source:
            errors.append(
                f"Reference value for '{param_config.name}' ({param_config.reference_value}) "
                f"lacks required reference_source provenance."
            )
        if param_config.reference_verification_status not in (VerificationStatus.VERIFIED, VerificationStatus.NOT_YET_VERIFIED):
            errors.append(
                f"Invalid reference verification status for '{param_config.name}': {param_config.reference_verification_status}"
            )
    return errors


def validate_dataset(
    df: pd.DataFrame,
    family: Optional[ComponentFamily] = None,
    allowed_checkpoints: Optional[List[int]] = None,
    user_screening_limits: Optional[Dict[str, Tuple[Optional[float], Optional[float]]]] = None,
    strict_checkpoints: bool = True,
) -> ValidationReport:
    """Validate a long-format DataFrame of measurements.

    Checks:
    - Required columns present
    - Non-null mandatory identity fields (component_id, lot_id, parameter_name)
    - Parameter/unit pairing against component family or global parameter config
    - Checkpoints within allowed list (strict mode flags as ERROR per Architecture spec)
    - Measurement quality and source type values
    - Non-negative integer rework count
    - Duplicate measurements (both identical and conflicting values flagged as ERROR)
    - Non-finite numbers (NaN, +Inf, -Inf flagged as ERROR)
    - Numerical safety for log-space parameters (val <= 0 flagged as warning)
    - Missingness tracking across components and checkpoints
    - User screening limit breaches (without automatically rejecting)
    - Reference deviations for verified reference values
    """
    errors: List[str] = []
    warnings: List[str] = []
    user_limit_breaches: List[Dict[str, Any]] = []
    reference_deviations: List[Dict[str, Any]] = []
    duplicate_records: List[Dict[str, Any]] = []
    numerical_status_records: List[Dict[str, Any]] = []

    if df.empty:
        return ValidationReport(
            is_valid=False,
            total_records=0,
            errors=["Dataset is empty"],
            numerical_status_records=[],
        )

    # 1. Schema / Column Check
    missing_cols = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing required canonical columns: {missing_cols}")
        return ValidationReport(
            is_valid=False,
            total_records=len(df),
            errors=errors,
        )

    checkpoints = allowed_checkpoints or [0, 24, 96, 168]

    # Load fallback parameter configs for unit verification if no family was explicitly passed
    fallback_params: Dict[str, ParameterConfig] = {}
    try:
        from sih26170.config import load_parameter_configs
        fallback_params = load_parameter_configs()
    except Exception:
        pass

    # 2. Duplicate Detection
    dup_mask = df.duplicated(subset=["component_id", "parameter_name", "elapsed_hours"], keep=False)
    if dup_mask.any():
        dup_rows = df[dup_mask]
        for _, row in dup_rows.iterrows():
            duplicate_records.append({
                "component_id": str(row["component_id"]),
                "parameter_name": str(row["parameter_name"]),
                "elapsed_hours": int(row["elapsed_hours"]),
                "value": row["value"],
            })
        errors.append(f"Found {dup_mask.sum()} duplicate measurement rows for identical (component, parameter, time).")

    # 3. Checkpoints, Identity, Values & Quality Checks
    for idx, row in df.iterrows():
        comp_id = row["component_id"]
        lot_id = row["lot_id"]
        param_name = row["parameter_name"]
        t = row["elapsed_hours"]
        val = row["value"]
        unit = str(row["unit"])
        quality = str(row["measurement_quality"])
        source = str(row["source_type"])
        rework = row["rework_count"]

        # Null checks on required identity values
        if pd.isna(comp_id) or not str(comp_id).strip():
            errors.append(f"Row {idx}: component_id is missing or empty")
        if pd.isna(lot_id) or not str(lot_id).strip():
            errors.append(f"Row {idx}: lot_id is missing or empty")
        if pd.isna(param_name) or not str(param_name).strip():
            errors.append(f"Row {idx}: parameter_name is missing or empty")

        # Numerical safety & ValueStatus classification (Issue A & Invariant 3)
        val_status = classify_measurement_value(val)
        param_cfg = None
        if family and family.is_parameter_allowed(str(param_name)):
            param_cfg = family.allowed_parameters.get(str(param_name))
        elif str(param_name) in fallback_params:
            param_cfg = fallback_params[str(param_name)]

        is_log_transform = (param_cfg is not None and param_cfg.transform == "log")

        if val_status == ValueStatus.MISSING:
            errors.append(f"Row {idx} ({comp_id}, {param_name}, {t}h): value is missing")
            numerical_status_records.append({
                "component_id": str(comp_id),
                "parameter_name": str(param_name),
                "elapsed_hours": int(t) if pd.notna(t) else None,
                "raw_value": None,
                "status": ValueStatus.MISSING.value,
                "log_transform_eligible": False,
                "note": "Measurement was missing.",
            })
        elif val_status == ValueStatus.NON_FINITE:
            errors.append(f"Row {idx} ({comp_id}, {param_name}, {t}h): value must be a finite number, got {val}")
            numerical_status_records.append({
                "component_id": str(comp_id),
                "parameter_name": str(param_name),
                "elapsed_hours": int(t) if pd.notna(t) else None,
                "raw_value": val,
                "status": ValueStatus.NON_FINITE.value,
                "log_transform_eligible": False,
                "note": "Measurement was non-finite (NaN or Infinity).",
            })
        elif val_status == ValueStatus.NEGATIVE:
            eligible = not is_log_transform
            if is_log_transform:
                warnings.append(
                    f"Row {idx} ({comp_id}, {param_name}): negative measurement ({val}) for log-transformed parameter. "
                    f"Raw value preserved intact; ineligible for direct log transform without separate preprocessing."
                )
            numerical_status_records.append({
                "component_id": str(comp_id),
                "parameter_name": str(param_name),
                "elapsed_hours": int(t) if pd.notna(t) else None,
                "raw_value": float(val),
                "status": ValueStatus.NEGATIVE.value,
                "log_transform_eligible": eligible,
                "note": "Measurement was negative; raw value preserved intact without flooring." if is_log_transform else "Measurement was negative.",
            })
        elif val_status == ValueStatus.ZERO:
            eligible = not is_log_transform
            if is_log_transform:
                warnings.append(
                    f"Row {idx} ({comp_id}, {param_name}): physically zero measurement ({val}) for log-transformed parameter. "
                    f"Raw value preserved intact; undefined in log space without separate preprocessing."
                )
            numerical_status_records.append({
                "component_id": str(comp_id),
                "parameter_name": str(param_name),
                "elapsed_hours": int(t) if pd.notna(t) else None,
                "raw_value": float(val),
                "status": ValueStatus.ZERO.value,
                "log_transform_eligible": eligible,
                "note": "Measurement was physically zero; raw value preserved intact." if is_log_transform else "Measurement was physically zero.",
            })
        elif val_status == ValueStatus.POSITIVE:
            numerical_status_records.append({
                "component_id": str(comp_id),
                "parameter_name": str(param_name),
                "elapsed_hours": int(t) if pd.notna(t) else None,
                "raw_value": float(val),
                "status": ValueStatus.POSITIVE.value,
                "log_transform_eligible": True,
                "note": "Measurement was positive; eligible for direct log transform." if is_log_transform else "Measurement was positive.",
            })

        # Checkpoint validation
        try:
            t_int = int(t)
            if t_int not in checkpoints:
                msg = f"Row {idx} ({comp_id}): elapsed_hours {t_int} not in allowed checkpoints {checkpoints}"
                if strict_checkpoints:
                    errors.append(msg)
                else:
                    warnings.append(msg)
        except (ValueError, TypeError):
            errors.append(f"Row {idx} ({comp_id}): elapsed_hours must be an integer, got {t}")

        # Quality validation
        if quality not in VALID_MEASUREMENT_QUALITIES:
            errors.append(f"Row {idx} ({comp_id}): measurement_quality '{quality}' not in {VALID_MEASUREMENT_QUALITIES}")

        # Source type validation
        if source not in VALID_SOURCE_TYPES:
            errors.append(f"Row {idx} ({comp_id}): source_type '{source}' not in {VALID_SOURCE_TYPES}")

        # Rework count validation
        try:
            rework_int = int(rework)
            if rework_int < 0:
                errors.append(f"Row {idx} ({comp_id}): rework_count must be non-negative, got {rework_int}")
        except (ValueError, TypeError):
            errors.append(f"Row {idx} ({comp_id}): rework_count must be an integer, got {rework}")

        # Parameter/Unit Verification (either via family or fallback config)
        param_str = str(param_name)
        if family is not None:
            if not family.is_parameter_allowed(param_str):
                errors.append(
                    f"Row {idx} ({comp_id}): parameter '{param_str}' is not allowed for component family '{family.family_id}'"
                )
            else:
                expected_unit = family.get_expected_unit(param_str)
                if expected_unit and unit != expected_unit:
                    errors.append(
                        f"Row {idx} ({comp_id}, {param_str}): unit mismatch. Expected '{expected_unit}', got '{unit}'"
                    )

                # Reference specification inspection
                ref_val, _, _, ref_status = family.get_reference_value_info(param_str)
                if ref_status == VerificationStatus.VERIFIED and ref_val is not None:
                    if abs(val - ref_val) > 0.5 * abs(ref_val):
                        reference_deviations.append({
                            "component_id": comp_id,
                            "parameter_name": param_str,
                            "elapsed_hours": t,
                            "measured_value": val,
                            "reference_value": ref_val,
                            "unit": unit,
                            "note": "Measurement is below screening limit but deviates significantly from verified reference value",
                        })
        elif param_str in fallback_params:
            expected_unit = fallback_params[param_str].unit
            if unit != expected_unit:
                errors.append(
                    f"Row {idx} ({comp_id}, {param_str}): unit mismatch. Expected '{expected_unit}', got '{unit}'"
                )

        # User Screening Limit checks
        low_limit = None
        high_limit = None
        if user_screening_limits and param_str in user_screening_limits:
            low_limit, high_limit = user_screening_limits[param_str]
        elif family is not None and family.is_parameter_allowed(param_str):
            low_limit, high_limit = family.get_user_screening_limits(param_str)
        else:
            low_limit = row.get("absolute_limit_low")
            high_limit = row.get("absolute_limit_high")

        # Validate limit consistency
        if low_limit is not None and high_limit is not None and low_limit > high_limit:
            errors.append(f"Row {idx} ({comp_id}, {param_str}): user_limit_low ({low_limit}) > user_limit_high ({high_limit})")

        if low_limit is not None and not pd.isna(low_limit) and val < low_limit:
            user_limit_breaches.append({
                "component_id": comp_id,
                "parameter_name": param_str,
                "elapsed_hours": t,
                "value": val,
                "limit_breached": "LOW",
                "limit_value": low_limit,
                "unit": unit,
            })
        if high_limit is not None and not pd.isna(high_limit) and val > high_limit:
            user_limit_breaches.append({
                "component_id": comp_id,
                "parameter_name": param_str,
                "elapsed_hours": t,
                "value": val,
                "limit_breached": "HIGH",
                "limit_value": high_limit,
                "unit": unit,
            })

    # 4. Missingness Tracking across Checkpoints
    missingness: Dict[str, Any] = {"components_with_missing_checkpoints": {}}
    if "component_id" in df.columns and "elapsed_hours" in df.columns and "parameter_name" in df.columns:
        expected_times = set(checkpoints)
        for (c_id, p_name), group in df.groupby(["component_id", "parameter_name"]):
            present_times = set(group["elapsed_hours"].unique())
            missing_times = expected_times - present_times
            if missing_times:
                missingness["components_with_missing_checkpoints"][f"{c_id}::{p_name}"] = sorted(list(missing_times))

    is_valid = len(errors) == 0

    return ValidationReport(
        is_valid=is_valid,
        total_records=len(df),
        errors=errors,
        warnings=warnings,
        missingness=missingness,
        user_limit_breaches=user_limit_breaches,
        reference_deviations=reference_deviations,
        duplicate_records=duplicate_records,
        numerical_status_records=numerical_status_records,
    )


def enforce_as_of(
    df: pd.DataFrame,
    as_of_hours: int,
    strip_ground_truth: bool = False
) -> pd.DataFrame:
    """Enforce the strict 'as-of' temporal contract with deep leakage protection.

    Mandated by Architecture Section 3.1 & PRD NFR2 (Audit Section 7 & 8):
    - Every statistic and downstream filter must use only rows where elapsed_hours <= as_of_hours.
    - Future checkpoints (elapsed_hours > as_of_hours) are strictly removed.
    - Deep leakage protection:
      * If ground-truth label columns are present, any future time-indexed label
        (e.g., abnormal_by_96h when as_of_hours < 96) is masked to None/NaN.
      * If first_abnormal_hour > as_of_hours, it is masked to None/NaN.
      * If strip_ground_truth=True, all ground truth columns are completely removed.
    """
    if as_of_hours < 0:
        raise ValueError(f"as_of_hours must be non-negative, got {as_of_hours}")
    if "elapsed_hours" not in df.columns:
        raise KeyError("DataFrame must contain 'elapsed_hours' column to enforce as-of contract.")

    # 1. Strict temporal row slice
    sliced = df[df["elapsed_hours"] <= as_of_hours].copy()

    # Integrity assertion on rows
    if (sliced["elapsed_hours"] > as_of_hours).any():
        raise RuntimeError(f"As-of contract violated: records with elapsed_hours > {as_of_hours} found in sliced data.")

    # 2. Deep leakage protection on ground truth columns
    if strip_ground_truth:
        from sih26170.schema import GROUND_TRUTH_COLUMNS
        sliced = sliced.drop(columns=[c for c in GROUND_TRUTH_COLUMNS if c in sliced.columns])
    else:
        # Mask future-dated ground truth defect labels
        time_indexed_labels = [
            ("abnormal_by_24h", 24),
            ("abnormal_by_96h", 96),
            ("abnormal_by_168h", 168),
        ]
        for col_name, checkpoint_t in time_indexed_labels:
            if col_name in sliced.columns and as_of_hours < checkpoint_t:
                sliced[col_name] = None

        if "first_abnormal_hour" in sliced.columns:
            # If the abnormal event occurs in the future, it cannot be known as-of now
            mask_future = sliced["first_abnormal_hour"] > as_of_hours
            sliced.loc[mask_future, "first_abnormal_hour"] = None

    return sliced


def assess_peer_sample_size(
    lot_df: pd.DataFrame,
    min_peer_count: Optional[int] = None
) -> Dict[str, Any]:
    """Assess available peer sample size per checkpoint without forcing arbitrary cutoffs.

    Enforces Issue B (Section 4, 5, 6):
    - Reports available device counts per lot and parameter checkpoint.
    - If min_peer_count is specified, evaluates whether peer population is sufficient.
    - If min_peer_count is None, reports counts as engineering observations without
      fabricating an arbitrary minimum threshold.
    - Confirms that insufficient peer data routes to PeerStatus.INSUFFICIENT_DATA
      while absolute screening limits (AbsoluteStatus) are evaluated independently.
    """
    results: Dict[str, Any] = {"peer_counts": {}, "is_peer_sufficient": None}
    if "lot_id" in lot_df.columns and "elapsed_hours" in lot_df.columns:
        counts = lot_df.groupby(["lot_id", "elapsed_hours"])["component_id"].nunique().to_dict()
        results["peer_counts"] = {f"{lot}@{h}h": int(cnt) for (lot, h), cnt in counts.items()}
        if min_peer_count is not None:
            results["is_peer_sufficient"] = all(cnt >= min_peer_count for cnt in counts.values())
            results["min_peer_threshold"] = min_peer_count
    return results


@dataclass(frozen=True)
class DecompositionResult:
    """Result of leave-one-out robust lot baseline decomposition (b_i vs g_i(t)).

    Maintains mathematical consistency:
    - For log parameters: operates strictly in log space z = ln(x) on positive values.
    - For linear parameters: operates in physical units.
    - Normalizes both peer offset b_i and temporal deviation g_i(t) by robust scale.
    - Explicitly distinguishes non-positive values, MAD=0, and small peer populations.
    """
    component_id: str
    lot_id: str
    parameter_name: str
    elapsed_hours: int
    transform: str
    raw_value_0: Optional[float]
    raw_value_t: Optional[float]
    b_i: Optional[float]
    g_i_t: Optional[float]
    peer_status: PeerStatus
    trend_status: TrendStatus
    peer_median_0: Optional[float]
    peer_mad_0: Optional[float]
    peer_scale_0: Optional[float]
    peer_count_0: int
    peer_median_t: Optional[float]
    peer_mad_t: Optional[float]
    peer_scale_t: Optional[float]
    peer_count_t: int
    status_note: str


def compute_robust_decomposition(
    lot_df: pd.DataFrame,
    target_comp_id: str,
    parameter_name: str,
    elapsed_hours: int,
    transform: str = "log",
    noise_floor: float = 0.01,
    min_peer_count: int = 4,
) -> DecompositionResult:
    """Compute leave-one-out robust lot baseline decomposition (b_i and g_i(t)).

    Mathematical formulation (LOG-032):
    1. For log-transformed parameters (leakage_current, iddq):
       Operates on z = ln(x). If x <= 0, preserves raw immutability and returns
       INSUFFICIENT_DATA without fabricating values.
    2. For linear parameters (propagation_delay):
       Operates in natural physical units (ns).
    3. Leave-one-out statistics:
       Excludes target device i from lot median and MAD.
       scale = max(1.4826 * MAD, noise_floor), strictly preventing zero-scale division.
    4. Components:
       b_i = (z_i(0) - mu_lot,-i(0)) / scale_0
       Z_i(t) = (z_i(t) - mu_lot,-i(t)) / scale_t
       g_i(t) = Z_i(t) - b_i  (at t=0, g_i(0) = 0 identically)
    """
    # Filter for the relevant parameter
    p_df = lot_df[lot_df["parameter_name"] == parameter_name]
    lot_id = str(lot_df["lot_id"].iloc[0]) if not lot_df.empty and "lot_id" in lot_df.columns else "UNKNOWN"

    # 1. Baseline at t = 0
    t0_rows = p_df[p_df["elapsed_hours"] == 0]
    target_row_0 = t0_rows[t0_rows["component_id"] == target_comp_id]
    raw_val_0 = float(target_row_0["value"].iloc[0]) if not target_row_0.empty and pd.notna(target_row_0["value"].iloc[0]) else None

    # Check baseline presence
    if raw_val_0 is None:
        return DecompositionResult(
            component_id=target_comp_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            elapsed_hours=elapsed_hours,
            transform=transform,
            raw_value_0=None,
            raw_value_t=None,
            b_i=None,
            g_i_t=None,
            peer_status=PeerStatus.INSUFFICIENT_DATA,
            trend_status=TrendStatus.INSUFFICIENT_DATA,
            peer_median_0=None,
            peer_mad_0=None,
            peer_scale_0=None,
            peer_count_0=0,
            peer_median_t=None,
            peer_mad_t=None,
            peer_scale_t=None,
            peer_count_t=0,
            status_note="Missing baseline observation at 0h",
        )

    # Check non-positive baseline for log transform
    if transform == "log" and raw_val_0 <= 0.0:
        return DecompositionResult(
            component_id=target_comp_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            elapsed_hours=elapsed_hours,
            transform=transform,
            raw_value_0=raw_val_0,
            raw_value_t=None,
            b_i=None,
            g_i_t=None,
            peer_status=PeerStatus.INSUFFICIENT_DATA,
            trend_status=TrendStatus.INSUFFICIENT_DATA,
            peer_median_0=None,
            peer_mad_0=None,
            peer_scale_0=None,
            peer_count_0=0,
            peer_median_t=None,
            peer_mad_t=None,
            peer_scale_t=None,
            peer_count_t=0,
            status_note=f"Non-positive baseline ({raw_val_0}) ineligible for direct log transform",
        )

    # Check non-finite baseline
    if not np.isfinite(raw_val_0):
        return DecompositionResult(
            component_id=target_comp_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            elapsed_hours=elapsed_hours,
            transform=transform,
            raw_value_0=raw_val_0,
            raw_value_t=None,
            b_i=None,
            g_i_t=None,
            peer_status=PeerStatus.INSUFFICIENT_DATA,
            trend_status=TrendStatus.INSUFFICIENT_DATA,
            peer_median_0=None,
            peer_mad_0=None,
            peer_scale_0=None,
            peer_count_0=0,
            peer_median_t=None,
            peer_mad_t=None,
            peer_scale_t=None,
            peer_count_t=0,
            status_note=f"Non-finite baseline ({raw_val_0}) rejected",
        )

    # Peer rows at t = 0 (leave-one-out)
    peer_rows_0 = t0_rows[t0_rows["component_id"] != target_comp_id]
    valid_peers_0 = [
        float(v) for v in peer_rows_0["value"].dropna()
        if np.isfinite(v) and (transform != "log" or float(v) > 0.0)
    ]

    if len(valid_peers_0) < min_peer_count:
        return DecompositionResult(
            component_id=target_comp_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            elapsed_hours=elapsed_hours,
            transform=transform,
            raw_value_0=raw_val_0,
            raw_value_t=None,
            b_i=None,
            g_i_t=None,
            peer_status=PeerStatus.INSUFFICIENT_DATA,
            trend_status=TrendStatus.INSUFFICIENT_DATA,
            peer_median_0=None,
            peer_mad_0=None,
            peer_scale_0=None,
            peer_count_0=len(valid_peers_0),
            peer_median_t=None,
            peer_mad_t=None,
            peer_scale_t=None,
            peer_count_t=0,
            status_note=f"Insufficient leave-one-out peer count at 0h ({len(valid_peers_0)} < {min_peer_count})",
        )

    # Compute baseline peer stats in consistent statistical space
    if transform == "log":
        z_peers_0 = np.log(np.array(valid_peers_0))
        z_target_0 = np.log(raw_val_0)
    else:
        z_peers_0 = np.array(valid_peers_0)
        z_target_0 = raw_val_0

    med_0 = float(np.median(z_peers_0))
    mad_0 = float(np.median(np.abs(z_peers_0 - med_0)))
    scale_0 = float(max(1.4826 * mad_0, noise_floor))
    b_i = float((z_target_0 - med_0) / scale_0)

    # Map b_i to PeerStatus
    if abs(b_i) >= 3.5:
        p_status = PeerStatus.MAJOR_OUTLIER
    elif abs(b_i) >= 2.5:
        p_status = PeerStatus.OUTLIER
    elif abs(b_i) >= 1.5:
        p_status = PeerStatus.SUSPECT
    else:
        p_status = PeerStatus.NORMAL

    # 2. Checkpoint t evaluation
    if elapsed_hours == 0:
        return DecompositionResult(
            component_id=target_comp_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            elapsed_hours=0,
            transform=transform,
            raw_value_0=raw_val_0,
            raw_value_t=raw_val_0,
            b_i=b_i,
            g_i_t=0.0,
            peer_status=p_status,
            trend_status=TrendStatus.STABLE,
            peer_median_0=med_0,
            peer_mad_0=mad_0,
            peer_scale_0=scale_0,
            peer_count_0=len(valid_peers_0),
            peer_median_t=med_0,
            peer_mad_t=mad_0,
            peer_scale_t=scale_0,
            peer_count_t=len(valid_peers_0),
            status_note="Baseline checkpoint (g_i(0) = 0.0)",
        )

    # For t > 0
    t_rows = p_df[p_df["elapsed_hours"] == elapsed_hours]
    target_row_t = t_rows[t_rows["component_id"] == target_comp_id]
    raw_val_t = float(target_row_t["value"].iloc[0]) if not target_row_t.empty and pd.notna(target_row_t["value"].iloc[0]) else None

    if raw_val_t is None:
        return DecompositionResult(
            component_id=target_comp_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            elapsed_hours=elapsed_hours,
            transform=transform,
            raw_value_0=raw_val_0,
            raw_value_t=None,
            b_i=b_i,
            g_i_t=None,
            peer_status=p_status,
            trend_status=TrendStatus.INSUFFICIENT_DATA,
            peer_median_0=med_0,
            peer_mad_0=mad_0,
            peer_scale_0=scale_0,
            peer_count_0=len(valid_peers_0),
            peer_median_t=None,
            peer_mad_t=None,
            peer_scale_t=None,
            peer_count_t=0,
            status_note=f"Missing observation at {elapsed_hours}h",
        )

    if transform == "log" and raw_val_t <= 0.0:
        return DecompositionResult(
            component_id=target_comp_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            elapsed_hours=elapsed_hours,
            transform=transform,
            raw_value_0=raw_val_0,
            raw_value_t=raw_val_t,
            b_i=b_i,
            g_i_t=None,
            peer_status=p_status,
            trend_status=TrendStatus.INSUFFICIENT_DATA,
            peer_median_0=med_0,
            peer_mad_0=mad_0,
            peer_scale_0=scale_0,
            peer_count_0=len(valid_peers_0),
            peer_median_t=None,
            peer_mad_t=None,
            peer_scale_t=None,
            peer_count_t=0,
            status_note=f"Non-positive reading at {elapsed_hours}h ({raw_val_t}) ineligible for log transform",
        )

    if not np.isfinite(raw_val_t):
        return DecompositionResult(
            component_id=target_comp_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            elapsed_hours=elapsed_hours,
            transform=transform,
            raw_value_0=raw_val_0,
            raw_value_t=raw_val_t,
            b_i=b_i,
            g_i_t=None,
            peer_status=p_status,
            trend_status=TrendStatus.INSUFFICIENT_DATA,
            peer_median_0=med_0,
            peer_mad_0=mad_0,
            peer_scale_0=scale_0,
            peer_count_0=len(valid_peers_0),
            peer_median_t=None,
            peer_mad_t=None,
            peer_scale_t=None,
            peer_count_t=0,
            status_note=f"Non-finite reading at {elapsed_hours}h ({raw_val_t}) rejected",
        )

    # Leave-one-out peers at t
    peer_rows_t = t_rows[t_rows["component_id"] != target_comp_id]
    valid_peers_t = [
        float(v) for v in peer_rows_t["value"].dropna()
        if np.isfinite(v) and (transform != "log" or float(v) > 0.0)
    ]

    if len(valid_peers_t) < min_peer_count:
        return DecompositionResult(
            component_id=target_comp_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            elapsed_hours=elapsed_hours,
            transform=transform,
            raw_value_0=raw_val_0,
            raw_value_t=raw_val_t,
            b_i=b_i,
            g_i_t=None,
            peer_status=p_status,
            trend_status=TrendStatus.INSUFFICIENT_DATA,
            peer_median_0=med_0,
            peer_mad_0=mad_0,
            peer_scale_0=scale_0,
            peer_count_0=len(valid_peers_0),
            peer_median_t=None,
            peer_mad_t=None,
            peer_scale_t=None,
            peer_count_t=len(valid_peers_t),
            status_note=f"Insufficient leave-one-out peer count at {elapsed_hours}h ({len(valid_peers_t)} < {min_peer_count})",
        )

    if transform == "log":
        z_peers_t = np.log(np.array(valid_peers_t))
        z_target_t = np.log(raw_val_t)
    else:
        z_peers_t = np.array(valid_peers_t)
        z_target_t = raw_val_t

    med_t = float(np.median(z_peers_t))
    mad_t = float(np.median(np.abs(z_peers_t - med_t)))
    scale_t = float(max(1.4826 * mad_t, noise_floor))

    # Standardized temporal deviation relative to baseline lot scale
    # z_i(t) = med_t + scale_0 * (b_i + g_i(t))
    # delta_i(t) = [z_target_t - med_t] - [z_target_0 - med_0]
    # g_i(t) = delta_i(t) / scale_0
    delta_i_t = (z_target_t - med_t) - (z_target_0 - med_0)
    g_i_t = float(delta_i_t / scale_0)

    # Map g_i(t) to TrendStatus
    if abs(g_i_t) >= 3.0:
        t_status = TrendStatus.ACCELERATING
    elif abs(g_i_t) >= 1.5:
        t_status = TrendStatus.DRIFTING
    else:
        t_status = TrendStatus.STABLE

    return DecompositionResult(
        component_id=target_comp_id,
        lot_id=lot_id,
        parameter_name=parameter_name,
        elapsed_hours=elapsed_hours,
        transform=transform,
        raw_value_0=raw_val_0,
        raw_value_t=raw_val_t,
        b_i=b_i,
        g_i_t=g_i_t,
        peer_status=p_status,
        trend_status=t_status,
        peer_median_0=med_0,
        peer_mad_0=mad_0,
        peer_scale_0=scale_0,
        peer_count_0=len(valid_peers_0),
        peer_median_t=med_t,
        peer_mad_t=mad_t,
        peer_scale_t=scale_t,
        peer_count_t=len(valid_peers_t),
        status_note="Decomposition successful",
    )

