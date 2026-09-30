"""Unit tests for Component Family abstraction and reference specification separation."""

import pytest
from sih26170.component_family import (
    ComponentFamily,
    get_component_family,
    list_component_families,
    register_component_family,
)
from sih26170.config import ParameterConfig, VerificationStatus, ProvenanceCategory


def test_list_component_families():
    """Verify all 4 required framing families are registered."""
    families = list_component_families()
    assert "DC_DC_CONVERTER" in families
    assert "POWER_SUPPLY_UNIT" in families
    assert "ELECTRONIC_CONTROL_BOARD" in families
    assert "PACKAGED_MMIC" in families


def test_board_level_framing_parameters():
    """Verify parameters allowed per board-level assembly and MMIC framing."""
    dcdc = get_component_family("DC_DC_CONVERTER")
    assert dcdc.framing == "BOARD_LEVEL_ASSEMBLY"
    assert dcdc.is_parameter_allowed("leakage_current") is True
    assert dcdc.is_parameter_allowed("iddq") is True
    # Propagation delay is a timing parameter on digital control boards, not DC-DC converter
    assert dcdc.is_parameter_allowed("propagation_delay") is False
    assert dcdc.get_expected_unit("leakage_current") == "uA"
    assert dcdc.get_expected_unit("iddq") == "mA"

    ecb = get_component_family("ELECTRONIC_CONTROL_BOARD")
    assert ecb.is_parameter_allowed("leakage_current") is True
    assert ecb.is_parameter_allowed("iddq") is True
    assert ecb.is_parameter_allowed("propagation_delay") is True
    assert ecb.get_expected_unit("propagation_delay") == "ns"

    mmic = get_component_family("PACKAGED_MMIC")
    assert mmic.framing == "PACKAGED_MMIC"
    assert mmic.is_parameter_allowed("leakage_current") is True
    assert mmic.is_parameter_allowed("iddq") is False


def test_reference_vs_user_limit_separation():
    """Verify CHANGE 1 & 11: reference_value is separated from user_limit_high.

    Changing user screening limit must NOT modify the reference value.
    """
    dcdc = get_component_family("DC_DC_CONVERTER")
    ref_val, ref_type, ref_src, ref_status = dcdc.get_reference_value_info("leakage_current")
    low_limit, high_limit = dcdc.get_user_screening_limits("leakage_current")

    # Initial state: reference_value is None, user screening limit is 50.0 uA
    assert ref_val is None
    assert ref_status == VerificationStatus.NOT_YET_VERIFIED
    assert high_limit == 50.0

    # Engineer updates user screening limit to 45.0 uA
    dcdc.set_user_screening_limits("leakage_current", user_limit_low=None, user_limit_high=45.0)
    new_low, new_high = dcdc.get_user_screening_limits("leakage_current")
    assert new_high == 45.0

    # Reference value must remain untouched (still None and NOT_YET_VERIFIED)
    ref_val_after, _, _, ref_status_after = dcdc.get_reference_value_info("leakage_current")
    assert ref_val_after is None
    assert ref_status_after == VerificationStatus.NOT_YET_VERIFIED


def test_missing_reference_value_handling():
    """Verify CHANGE 1 & 11: reference_value = null and NOT_YET_VERIFIED is valid

    and does not trigger invented defaults.
    """
    ecb = get_component_family("ELECTRONIC_CONTROL_BOARD")
    ref_val, _, _, status = ecb.get_reference_value_info("iddq")
    assert ref_val is None
    assert status == VerificationStatus.NOT_YET_VERIFIED


def test_user_limit_validation_in_family():
    """Verify set_user_screening_limits enforces low <= high."""
    dcdc = get_component_family("DC_DC_CONVERTER")
    with pytest.raises(ValueError, match="user_limit_low .* > user_limit_high"):
        dcdc.set_user_screening_limits("leakage_current", user_limit_low=75.0, user_limit_high=50.0)


def test_registry_deepcopy_isolation():
    """Verify modifying a retrieved family does not mutate default global registry."""
    dcdc_instance = get_component_family("DC_DC_CONVERTER")
    dcdc_instance.set_user_screening_limits("leakage_current", user_limit_low=1.0, user_limit_high=35.0)

    # Fresh retrieval from registry must retain original default limit (50.0 uA)
    dcdc_fresh = get_component_family("DC_DC_CONVERTER")
    assert dcdc_fresh.get_user_screening_limits("leakage_current") == (None, 50.0)


def test_component_family_parameter_applicability_configurable():
    """Verify Audit Section 5: Registry does not imply universal parameter applicability.

    Parameters can be added or removed explicitly per component family.
    """
    mmic = get_component_family("PACKAGED_MMIC")
    assert mmic.is_parameter_allowed("iddq") is False

    # Configure a custom parameter for an active screening study
    custom_param = ParameterConfig(
        name="custom_leakage_drain",
        unit="uA",
        transform="log",
        provenance_category=ProvenanceCategory.USER_CONFIGURABLE,
    )
    mmic.add_allowed_parameter(custom_param)
    assert mmic.is_parameter_allowed("custom_leakage_drain") is True
    assert mmic.get_expected_unit("custom_leakage_drain") == "uA"

    # Remove parameter
    mmic.remove_allowed_parameter("custom_leakage_drain")
    assert mmic.is_parameter_allowed("custom_leakage_drain") is False

