"""Unit tests for configuration system and 4-tier provenance verification."""

import pytest
from pathlib import Path
from sih26170.config import (
    ParameterConfig,
    PrototypeConfig,
    ProvenanceCategory,
    VerificationStatus,
    load_parameter_configs,
    load_prototype_config,
    verify_traceability,
)


def test_load_prototype_config_success():
    """Verify loading default prototype.yaml with correct types and values."""
    config = load_prototype_config()
    assert config.configuration_version == "prototype-v1"
    assert config.lot_size == 30
    assert config.checkpoint_hours == [0, 24, 96, 168]
    assert config.burn_in_temperature_C == 125.0
    assert config.noise_scale == 0.02
    assert config.defect_rate == 0.04
    assert config.missing_rate == 0.03
    assert config.equipment_shift_rate == 0.05
    assert config.alpha == 0.10
    assert config.rework_risk_enabled is True
    assert verify_traceability(config) is True


def test_prototype_config_provenance_tags():
    """Verify all 4 provenance categories are present in prototype config."""
    config = load_prototype_config()
    assert "lot_size" in config.provenance_tags
    category, assumption_id = config.provenance_tags["lot_size"]
    assert category == ProvenanceCategory.ASSUMPTION
    assert assumption_id == "A5"

    category, assumption_id = config.provenance_tags["burn_in_temperature_C"]
    assert category == ProvenanceCategory.ASSUMPTION
    assert assumption_id == "A2"

    category, assumption_id = config.provenance_tags["alpha"]
    assert category == ProvenanceCategory.SPECIFICATION
    assert assumption_id is None

    category, _ = config.provenance_tags["missing_rate"]
    assert category == ProvenanceCategory.DESIGN_DECISION


def test_load_parameter_configs_success():
    """Verify loading default parameters.yaml with separated reference specs and user limits."""
    configs = load_parameter_configs()
    assert "leakage_current" in configs
    assert "iddq" in configs
    assert "propagation_delay" in configs

    leakage = configs["leakage_current"]
    assert leakage.unit == "uA"
    assert leakage.transform == "log"
    assert leakage.user_limit_high == 50.0
    assert leakage.user_limit_low is None
    # Unverified reference value remains None and NOT_YET_VERIFIED
    assert leakage.reference_value is None
    assert leakage.reference_verification_status == VerificationStatus.NOT_YET_VERIFIED
    assert leakage.assumption_id == "A4"
    assert leakage.provenance_category == ProvenanceCategory.SPECIFICATION

    iddq = configs["iddq"]
    assert iddq.unit == "mA"
    assert iddq.user_limit_high is None
    assert iddq.user_limit_low is None
    assert iddq.reference_value is None
    assert iddq.provenance_category == ProvenanceCategory.USER_CONFIGURABLE

    prop = configs["propagation_delay"]
    assert prop.unit == "ns"
    assert prop.transform == "linear"
    assert prop.user_limit_high is None
    assert prop.user_limit_low is None
    assert prop.reference_value is None
    assert prop.provenance_category == ProvenanceCategory.USER_CONFIGURABLE


def test_parameter_config_invalid_user_limits():
    """Verify detection of invalid user screening limits (low > high)."""
    with pytest.raises(ValueError, match="user_limit_low .* > user_limit_high"):
        ParameterConfig(
            name="leakage_current",
            unit="uA",
            user_limit_low=60.0,
            user_limit_high=50.0,
        )


def test_parameter_config_reference_requires_provenance():
    """Verify that specifying a reference value without source raises error."""
    with pytest.raises(ValueError, match="missing reference_source"):
        ParameterConfig(
            name="leakage_current",
            unit="uA",
            reference_value=10.0,
            reference_source=None,  # Missing source
            reference_verification_status=VerificationStatus.VERIFIED,
        )


def test_parameter_config_invalid_assumption_id():
    """Verify that ASSUMPTION category requires a valid ID in A1-A18."""
    with pytest.raises(ValueError, match="valid assumption_id in A1-A18"):
        ParameterConfig(
            name="leakage_current",
            unit="uA",
            provenance_category=ProvenanceCategory.ASSUMPTION,
            assumption_id="A99",  # Invalid ID
        )


def test_prototype_config_invalid_values():
    """Verify invalid prototype simulation values are rejected."""
    with pytest.raises(ValueError, match="lot_size must be positive"):
        PrototypeConfig(lot_size=0)

    with pytest.raises(ValueError, match="checkpoint_hours must be monotonically increasing"):
        PrototypeConfig(checkpoint_hours=[0, 96, 24, 168])

    with pytest.raises(ValueError, match="alpha must be in"):
        PrototypeConfig(alpha=1.5)


def test_reference_value_type_enum():
    """Verify ReferenceValueType enumeration supports explicit engineering categories."""
    from sih26170.config import ReferenceValueType

    p = ParameterConfig(
        name="leakage_current",
        unit="uA",
        reference_value=10.0,
        reference_value_type=ReferenceValueType.TYPICAL,
        reference_source="QUAL_DOC_2026_01",
        reference_verification_status=VerificationStatus.VERIFIED,
    )
    assert p.reference_value_type == ReferenceValueType.TYPICAL

    # String coercion check
    p2 = ParameterConfig(
        name="leakage_current",
        unit="uA",
        reference_value=12.0,
        reference_value_type="DATASHEET_MAX",
        reference_source="QUAL_DOC_2026_02",
        reference_verification_status=VerificationStatus.VERIFIED,
    )
    assert p2.reference_value_type == ReferenceValueType.DATASHEET_MAX


def test_config_serialization():
    """Verify to_dict serialization for parameter and prototype configs."""
    from sih26170.config import ReferenceValueType

    p = ParameterConfig(
        name="leakage_current",
        unit="uA",
        reference_value=10.0,
        reference_value_type=ReferenceValueType.TYPICAL,
        reference_source="QUAL_DOC_2026_01",
        reference_verification_status=VerificationStatus.VERIFIED,
        user_limit_high=50.0,
    )
    d = p.to_dict()
    assert d["name"] == "leakage_current"
    assert d["reference_value"] == 10.0
    assert d["reference_value_type"] == "TYPICAL"
    assert d["user_limit_high"] == 50.0

    proto = PrototypeConfig()
    proto_d = proto.to_dict()
    assert proto_d["lot_size"] == 30
    assert proto_d["burn_in_temperature_C"] == 125.0
    assert proto_d["checkpoint_hours"] == [0, 24, 96, 168]
