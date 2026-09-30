"""Unit tests for Validation layer and 'as-of' temporal contract enforcement."""

import pytest
import pandas as pd
from sih26170.component_family import get_component_family
from sih26170.config import ParameterConfig, VerificationStatus
from sih26170.schema import CanonicalMeasurement, to_dataframe
from sih26170.validation import (
    enforce_as_of,
    validate_dataset,
    validate_reference_spec,
    validate_user_limits,
)


def create_sample_dataset() -> pd.DataFrame:
    """Helper to create a valid long-format test dataset."""
    measurements = []
    for comp_id in ["C001", "C002"]:
        for t in [0, 24, 96, 168]:
            measurements.append(
                CanonicalMeasurement(
                    component_id=comp_id,
                    lot_id="L01",
                    parameter_name="leakage_current",
                    elapsed_hours=t,
                    value=10.0 + (0.1 * t),
                    unit="uA",
                    temperature_C=125.0,
                    test_condition="STATIC_BURN_IN",
                    rework_count=0,
                    absolute_limit_low=None,
                    absolute_limit_high=50.0,
                    source_type="synthetic",
                )
            )
    return to_dataframe(measurements)


def test_validate_dataset_valid():
    """Verify clean dataset passes validation."""
    df = create_sample_dataset()
    family = get_component_family("DC_DC_CONVERTER")
    report = validate_dataset(df, family=family)
    assert report.is_valid is True
    assert len(report.errors) == 0
    assert report.total_records == 8
    assert len(report.duplicate_records) == 0


def test_validate_dataset_unit_mismatch():
    """Verify detection of unit mismatch (e.g. mA instead of uA for leakage_current)."""
    df = create_sample_dataset()
    # Introduce invalid unit
    df.loc[0, "unit"] = "mA"
    family = get_component_family("DC_DC_CONVERTER")
    report = validate_dataset(df, family=family)
    assert report.is_valid is False
    assert any("unit mismatch" in err for err in report.errors)


def test_validate_dataset_invalid_user_limits():
    """Verify detection of invalid user screening limits (low > high)."""
    df = create_sample_dataset()
    family = get_component_family("DC_DC_CONVERTER")
    # Screening limits with low > high
    invalid_limits = {"leakage_current": (60.0, 50.0)}
    report = validate_dataset(df, family=family, user_screening_limits=invalid_limits)
    assert report.is_valid is False
    assert any("user_limit_low (60.0) > user_limit_high (50.0)" in err for err in report.errors)


def test_validate_dataset_duplicate_detection():
    """Verify detection of duplicate (component_id, parameter_name, elapsed_hours)."""
    df = create_sample_dataset()
    # Duplicate the first row
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    family = get_component_family("DC_DC_CONVERTER")
    report = validate_dataset(df, family=family)
    assert report.is_valid is False
    assert len(report.duplicate_records) > 0
    assert any("duplicate measurement rows" in err for err in report.errors)


def test_validate_dataset_missingness_tracking():
    """Verify missingness tracking flags components missing required checkpoints."""
    df = create_sample_dataset()
    # Drop the 168h row for C001
    df = df[~((df["component_id"] == "C001") & (df["elapsed_hours"] == 168))]
    family = get_component_family("DC_DC_CONVERTER")
    report = validate_dataset(df, family=family)
    assert report.is_valid is True  # Missingness generates tracking report, not fatal schema failure
    missing_map = report.missingness["components_with_missing_checkpoints"]
    assert "C001::leakage_current" in missing_map
    assert 168 in missing_map["C001::leakage_current"]


def test_unverified_reference_spec_not_treated_as_screening_limit():
    """Verify CHANGE 4: unverified reference value is not treated as a rejection limit."""
    df = create_sample_dataset()
    # Measurement is 45 uA (below 50 uA user screening limit)
    df.loc[df["component_id"] == "C001", "value"] = 45.0
    family = get_component_family("DC_DC_CONVERTER")
    # Reference value is null / NOT_YET_VERIFIED
    report = validate_dataset(df, family=family)
    assert report.is_valid is True
    # Should not produce any user limit breaches since 45 <= 50.0
    assert len(report.user_limit_breaches) == 0


def test_reference_deviation_reporting():
    """Verify reporting when measurement deviates from verified reference while within user limit."""
    df = create_sample_dataset()
    # Set C001 value to 25.0 uA (under 50.0 uA screening limit)
    df.loc[df["component_id"] == "C001", "value"] = 25.0

    family = get_component_family("DC_DC_CONVERTER")
    # Configure a verified reference value for testing
    family.allowed_parameters["leakage_current"].reference_value = 10.0
    family.allowed_parameters["leakage_current"].reference_source = "TEST_STANDARD_001"
    family.allowed_parameters["leakage_current"].reference_verification_status = VerificationStatus.VERIFIED

    report = validate_dataset(df, family=family)
    assert report.is_valid is True
    assert len(report.user_limit_breaches) == 0
    # Reference deviation detected
    assert len(report.reference_deviations) > 0
    dev = report.reference_deviations[0]
    assert dev["measured_value"] == 25.0
    assert dev["reference_value"] == 10.0
    assert "deviates significantly from verified reference value" in dev["note"]


def test_as_of_temporal_contract():
    """Verify PRD NFR2 & Architecture Section 3.1 'as-of' contract enforcement.

    Statistics computed on as-of 24h data must strictly exclude 96h/168h observations.
    """
    df = create_sample_dataset()
    assert set(df["elapsed_hours"].unique()) == {0, 24, 96, 168}

    # Enforce as-of 24 hours
    as_of_24 = enforce_as_of(df, as_of_hours=24)
    assert (as_of_24["elapsed_hours"] <= 24).all()
    assert set(as_of_24["elapsed_hours"].unique()) == {0, 24}
    assert 96 not in as_of_24["elapsed_hours"].values
    assert 168 not in as_of_24["elapsed_hours"].values

    # Enforce as-of 0 hours
    as_of_0 = enforce_as_of(df, as_of_hours=0)
    assert (as_of_0["elapsed_hours"] == 0).all()

    # Invalid as-of hours
    with pytest.raises(ValueError, match="as_of_hours must be non-negative"):
        enforce_as_of(df, as_of_hours=-1)


def test_as_of_temporal_contract_deep_label_masking():
    """Verify Audit Section 7: Future ground-truth labels are masked in as-of temporal slices."""
    measurements = [
        CanonicalMeasurement(
            component_id="C001",
            lot_id="L01",
            parameter_name="leakage_current",
            elapsed_hours=0,
            value=10.0,
            unit="uA",
            temperature_C=125.0,
            test_condition="STATIC_BURN_IN",
            first_abnormal_hour=96,
            abnormal_by_24h=False,
            abnormal_by_96h=True,
            abnormal_by_168h=True,
        ),
        CanonicalMeasurement(
            component_id="C001",
            lot_id="L01",
            parameter_name="leakage_current",
            elapsed_hours=24,
            value=10.2,
            unit="uA",
            temperature_C=125.0,
            test_condition="STATIC_BURN_IN",
            first_abnormal_hour=96,
            abnormal_by_24h=False,
            abnormal_by_96h=True,
            abnormal_by_168h=True,
        ),
        CanonicalMeasurement(
            component_id="C001",
            lot_id="L01",
            parameter_name="leakage_current",
            elapsed_hours=96,
            value=35.0,
            unit="uA",
            temperature_C=125.0,
            test_condition="STATIC_BURN_IN",
            first_abnormal_hour=96,
            abnormal_by_24h=False,
            abnormal_by_96h=True,
            abnormal_by_168h=True,
        ),
    ]
    df = to_dataframe(measurements, include_ground_truth=True)

    # Slice as-of 24h
    as_of_24 = enforce_as_of(df, as_of_hours=24)
    assert len(as_of_24) == 2
    # 24h slice must preserve abnormal_by_24h (which is known by 24h)
    assert (as_of_24["abnormal_by_24h"] == False).all()
    # Future defect labels must be masked as None to prevent temporal label leakage
    assert as_of_24["abnormal_by_96h"].isna().all()
    assert as_of_24["abnormal_by_168h"].isna().all()
    # Event hour occurring at 96h must be masked as None as of 24h
    assert as_of_24["first_abnormal_hour"].isna().all()

    # Slice with strip_ground_truth=True
    as_of_clean = enforce_as_of(df, as_of_hours=24, strip_ground_truth=True)
    assert "abnormal_by_96h" not in as_of_clean.columns
    assert "first_abnormal_hour" not in as_of_clean.columns


def test_validate_dataset_unit_mismatch_without_family():
    """Verify unit mismatch is detected even when family=None via global config fallback."""
    df = create_sample_dataset()
    df.loc[0, "unit"] = "mA"  # leakage_current should be uA
    report = validate_dataset(df, family=None)
    assert report.is_valid is False
    assert any("unit mismatch" in err for err in report.errors)


def test_validate_dataset_strict_checkpoints():
    """Verify Audit Section 9: Arbitrary timestamps (e.g. 37h) fail under strict checkpoints."""
    df = create_sample_dataset()
    df.loc[0, "elapsed_hours"] = 37
    report = validate_dataset(df, strict_checkpoints=True)
    assert report.is_valid is False
    assert any("elapsed_hours 37 not in allowed checkpoints" in err for err in report.errors)


def test_validate_dataset_missing_identity():
    """Verify Audit Section 9: Missing component_id, lot_id, or parameter_name fails validation."""
    df = create_sample_dataset()
    df.loc[0, "lot_id"] = ""
    df.loc[1, "parameter_name"] = "  "
    report = validate_dataset(df)
    assert report.is_valid is False
    assert any("lot_id is missing or empty" in err for err in report.errors)
    assert any("parameter_name is missing or empty" in err for err in report.errors)


def test_validate_dataset_non_finite_values():
    """Verify Audit Section 10: NaN, Inf, -Inf are rejected as errors."""
    import numpy as np
    df = create_sample_dataset()
    df.loc[0, "value"] = np.nan
    df.loc[1, "value"] = np.inf
    report = validate_dataset(df)
    assert report.is_valid is False
    assert any("value must be a finite number" in err for err in report.errors)


def test_validate_dataset_log_transform_non_positive_warning():
    """Verify Audit Section 10 & Issue A: Zero or negative values for log-transformed parameters generate warnings."""
    df = create_sample_dataset()
    df.loc[0, "value"] = 0.0  # Zero leakage current
    report = validate_dataset(df)
    assert report.is_valid is True  # Warning, not fatal error
    assert any("physically zero measurement (0.0) for log-transformed parameter" in w for w in report.warnings)


def test_validate_dataset_duplicate_measurements_conflicting():
    """Verify Audit Section 9: Duplicate rows with conflicting values are strictly rejected."""
    df = create_sample_dataset()
    conflict_row = df.iloc[[0]].copy()
    conflict_row["value"] = 999.0  # Conflicting value for same (C001, leakage_current, 0h)
    df = pd.concat([df, conflict_row], ignore_index=True)
    report = validate_dataset(df)
    assert report.is_valid is False
    assert any("duplicate measurement rows" in err for err in report.errors)


def test_raw_measurement_immutability_and_value_status_records():
    """Verify Issue A & Invariant 3: Original measurements remain intact and unfloored.

    Structured ValueStatus records are populated, distinguishing negative vs zero.
    """
    df = create_sample_dataset()
    # Introduce negative and zero values
    df.loc[0, "value"] = -0.25  # Negative sensor offset
    df.loc[1, "value"] = 0.0    # Physically zero

    report = validate_dataset(df)

    # 1. Invariant: raw values in df must NOT be altered or floored to scale_floor (0.05)
    assert df.loc[0, "value"] == -0.25
    assert df.loc[1, "value"] == 0.0

    # 2. Structured status records distinguish negative from zero
    stat_map = {f"{r['component_id']}@{r['elapsed_hours']}h": r for r in report.numerical_status_records}

    rec_neg = stat_map["C001@0h"]
    assert rec_neg["raw_value"] == -0.25
    assert rec_neg["status"] == "NEGATIVE"
    assert rec_neg["log_transform_eligible"] is False

    rec_zero = stat_map["C001@24h"]
    assert rec_zero["raw_value"] == 0.0
    assert rec_zero["status"] == "ZERO"
    assert rec_zero["log_transform_eligible"] is False


def test_assess_peer_sample_size_without_arbitrary_cutoffs():
    """Verify Issue B: assess_peer_sample_size reports counts without imposing arbitrary minimums."""
    from sih26170.validation import assess_peer_sample_size

    df = create_sample_dataset()
    # 1. When min_peer_count is None: reports peer counts as engineering observation
    result = assess_peer_sample_size(df, min_peer_count=None)
    assert result["peer_counts"]["L01@0h"] == 2
    assert result["peer_counts"]["L01@24h"] == 2
    assert result["is_peer_sufficient"] is None  # No arbitrary cutoff imposed

    # 2. When an explicit threshold is passed for study
    res_thresh = assess_peer_sample_size(df, min_peer_count=5)
    assert res_thresh["is_peer_sufficient"] is False
    assert res_thresh["min_peer_threshold"] == 5


