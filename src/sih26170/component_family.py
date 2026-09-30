"""Component-family abstraction for SIH26170.

Implements CHANGE 1 and CHANGE 3:
- Represents: Component Family -> Allowed Parameters -> Expected Units -> Verified Reference Specifications (where available).
- Does NOT contain invented "default physical operating limits".
- Separates verified reference values from engineer-configured user screening limits.
- Supports primary framing: Board-Level High-Reliability Electronic Assembly (DC-DC Converter,
  Power Supply Unit, Electronic Control Board) and secondary framing: Packaged MMIC.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sih26170.config import (
    ParameterConfig,
    ProvenanceCategory,
    VerificationStatus,
    load_parameter_configs,
)


@dataclass
class ComponentFamily:
    """Component Family representation.

    Maps component family framing to allowed physical parameters, expected physical units,
    and verified reference specifications where available.
    """
    family_id: str
    name: str
    description: str
    framing: str  # "BOARD_LEVEL_ASSEMBLY" or "PACKAGED_MMIC"
    allowed_parameters: Dict[str, ParameterConfig] = field(default_factory=dict)

    def is_parameter_allowed(self, param_name: str) -> bool:
        """Check if parameter is valid and applicable for this component family."""
        return param_name in self.allowed_parameters

    def get_expected_unit(self, param_name: str) -> Optional[str]:
        """Return the expected physical measurement unit for a parameter."""
        cfg = self.allowed_parameters.get(param_name)
        return cfg.unit if cfg else None

    def get_reference_spec(self, param_name: str) -> Optional[ParameterConfig]:
        """Return reference specification for a parameter if present."""
        return self.allowed_parameters.get(param_name)

    def get_reference_value_info(self, param_name: str) -> Tuple[Optional[float], Optional[str], Optional[str], VerificationStatus]:
        """Return verified reference value tuple: (value, type, source, verification_status)."""
        cfg = self.allowed_parameters.get(param_name)
        if not cfg:
            return (None, None, None, VerificationStatus.NOT_YET_VERIFIED)
        return (
            cfg.reference_value,
            cfg.reference_value_type,
            cfg.reference_source,
            cfg.reference_verification_status,
        )

    def get_user_screening_limits(self, param_name: str) -> Tuple[Optional[float], Optional[float]]:
        """Return engineer-configured screening limits (user_limit_low, user_limit_high)."""
        cfg = self.allowed_parameters.get(param_name)
        if not cfg:
            return (None, None)
        return (cfg.user_limit_low, cfg.user_limit_high)

    def set_user_screening_limits(
        self,
        param_name: str,
        user_limit_low: Optional[float],
        user_limit_high: Optional[float]
    ) -> None:
        """Configure user screening limits for a screening run without modifying reference values.

        Enforces CHANGE 1 & 11: Changing user limit does not modify the reference value.
        """
        if param_name not in self.allowed_parameters:
            raise KeyError(f"Parameter '{param_name}' not allowed in family '{self.family_id}'")

        if user_limit_low is not None and user_limit_high is not None and user_limit_low > user_limit_high:
            raise ValueError(
                f"Invalid user limits for '{param_name}': user_limit_low ({user_limit_low}) > user_limit_high ({user_limit_high})"
            )

        cfg = self.allowed_parameters[param_name]
        cfg.user_limit_low = user_limit_low
        cfg.user_limit_high = user_limit_high

    def add_allowed_parameter(self, param_config: ParameterConfig) -> None:
        """Add or configure an allowed parameter for this family."""
        self.allowed_parameters[param_config.name] = deepcopy(param_config)

    def remove_allowed_parameter(self, param_name: str) -> None:
        """Remove a parameter from this family's allowed scope."""
        if param_name in self.allowed_parameters:
            del self.allowed_parameters[param_name]


# In-memory registry of initialized component families
_COMPONENT_FAMILY_REGISTRY: Dict[str, ComponentFamily] = {}


def register_component_family(family: ComponentFamily) -> None:
    """Register a component family in the global registry."""
    _COMPONENT_FAMILY_REGISTRY[family.family_id.upper()] = family


def get_component_family(family_id: str) -> ComponentFamily:
    """Retrieve a component family by ID."""
    fam = _COMPONENT_FAMILY_REGISTRY.get(family_id.upper())
    if not fam:
        raise KeyError(
            f"Component family '{family_id}' not found in registry. "
            f"Available families: {list(_COMPONENT_FAMILY_REGISTRY.keys())}"
        )
    # Return a deep copy so runtime limit modifications do not mutate global defaults
    return deepcopy(fam)


def list_component_families() -> List[str]:
    """List all registered component family IDs."""
    return list(_COMPONENT_FAMILY_REGISTRY.keys())


def initialize_default_component_families() -> None:
    """Initialize component families from parameters configuration and specs."""
    try:
        base_params = load_parameter_configs()
    except Exception:
        # Fallback minimal definitions if YAML not found during standalone import
        base_params = {
            "leakage_current": ParameterConfig(
                name="leakage_current",
                unit="uA",
                transform="log",
                user_limit_high=50.0,
                reference_verification_status=VerificationStatus.NOT_YET_VERIFIED,
                provenance_category=ProvenanceCategory.SPECIFICATION,
            ),
            "iddq": ParameterConfig(
                name="iddq",
                unit="mA",
                transform="log",
                reference_verification_status=VerificationStatus.NOT_YET_VERIFIED,
                provenance_category=ProvenanceCategory.USER_CONFIGURABLE,
            ),
            "propagation_delay": ParameterConfig(
                name="propagation_delay",
                unit="ns",
                transform="linear",
                reference_verification_status=VerificationStatus.NOT_YET_VERIFIED,
                provenance_category=ProvenanceCategory.USER_CONFIGURABLE,
            ),
        }

    # 1. DC-DC Converter (Board-level assembly: power stage + control electronics)
    # Parameters: leakage_current (uA), iddq (mA)
    dcdc_params = {
        "leakage_current": deepcopy(base_params["leakage_current"]),
        "iddq": deepcopy(base_params["iddq"]),
    }
    register_component_family(
        ComponentFamily(
            family_id="DC_DC_CONVERTER",
            name="DC-DC Power Converter Assembly",
            description="High-reliability spacecraft power supply module combining switched power stage and control loop.",
            framing="BOARD_LEVEL_ASSEMBLY",
            allowed_parameters=dcdc_params,
        )
    )

    # 2. Power Supply Unit (Board-level assembly)
    # Parameters: leakage_current (uA), iddq (mA)
    psu_params = {
        "leakage_current": deepcopy(base_params["leakage_current"]),
        "iddq": deepcopy(base_params["iddq"]),
    }
    register_component_family(
        ComponentFamily(
            family_id="POWER_SUPPLY_UNIT",
            name="Power Supply Unit (PSU)",
            description="Avionics power regulation board with multiple rails and isolation stages.",
            framing="BOARD_LEVEL_ASSEMBLY",
            allowed_parameters=psu_params,
        )
    )

    # 3. Electronic Control Board (Board-level assembly)
    # Parameters: leakage_current (uA), iddq (mA), propagation_delay (ns)
    ecb_params = {
        "leakage_current": deepcopy(base_params["leakage_current"]),
        "iddq": deepcopy(base_params["iddq"]),
        "propagation_delay": deepcopy(base_params["propagation_delay"]),
    }
    register_component_family(
        ComponentFamily(
            family_id="ELECTRONIC_CONTROL_BOARD",
            name="Electronic Control Board (ECB)",
            description="Spacecraft digital avionics board containing digital controller, sequencing logic, and timing paths.",
            framing="BOARD_LEVEL_ASSEMBLY",
            allowed_parameters=ecb_params,
        )
    )

    # 4. Packaged MMIC (Monolithic Microwave Integrated Circuit)
    # Secondary framing per A1/A14: RF/microwave component
    # Parameter: leakage_current (uA)
    mmic_params = {
        "leakage_current": deepcopy(base_params["leakage_current"]),
    }
    register_component_family(
        ComponentFamily(
            family_id="PACKAGED_MMIC",
            name="Packaged MMIC Module",
            description="High-frequency microwave amplifier/attenuator packaged module.",
            framing="PACKAGED_MMIC",
            allowed_parameters=mmic_params,
        )
    )


# Automatically initialize default registry upon module import
initialize_default_component_families()
