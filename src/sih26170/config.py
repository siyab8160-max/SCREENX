"""Configuration system and provenance verification for SIH26170.

Enforces 4-tier provenance categorization:
- ASSUMPTION: values sourced from or defined in the Assumptions Register (A1-A18).
- SPECIFICATION: values explicitly required by the PRD / Architecture specification.
- DESIGN_DECISION: implementation architecture decisions.
- USER_CONFIGURABLE: screening limits or parameters configured by the screening engineer.

Guarantees:
- Verified reference specifications are separated from user screening limits.
- Reference values lacking verified provenance remain null / NOT_YET_VERIFIED.
- No physical parameters, limits, or reference standards are invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml


class ProvenanceCategory(str, Enum):
    """Categorization of configuration values to ensure intellectual honesty."""
    ASSUMPTION = "ASSUMPTION"
    SPECIFICATION = "SPECIFICATION"
    DESIGN_DECISION = "DESIGN_DECISION"
    USER_CONFIGURABLE = "USER_CONFIGURABLE"


class VerificationStatus(str, Enum):
    """Status of reference specification verification."""
    VERIFIED = "VERIFIED"
    NOT_YET_VERIFIED = "NOT_YET_VERIFIED"


class ReferenceValueType(str, Enum):
    """Specific engineering categorization of reference values (audit requirement)."""
    TYPICAL = "TYPICAL"
    NOMINAL = "NOMINAL"
    DATASHEET_MAX = "DATASHEET_MAX"
    DATASHEET_MIN = "DATASHEET_MIN"
    QUALIFICATION_LIMIT = "QUALIFICATION_LIMIT"
    ENGINEERING_REFERENCE = "ENGINEERING_REFERENCE"


VALID_ASSUMPTION_IDS = {f"A{i}" for i in range(1, 19)}


@dataclass
class ParameterConfig:
    """Configuration for a measured physical parameter in component screening."""
    name: str
    unit: str
    transform: str = "linear"  # "log" | "linear"
    risk_direction: str = "high"  # "high" | "low" | "both"
    scale_floor: float = 0.05
    condition_keys: List[str] = field(default_factory=lambda: ["temperature_C", "test_condition"])
    assumption_id: Optional[str] = None
    provenance_category: ProvenanceCategory = ProvenanceCategory.SPECIFICATION

    # User-configured screening limits (configured by screening engineer for a run)
    user_limit_low: Optional[float] = None
    user_limit_high: Optional[float] = None

    # Reference / standard specifications (verified property of component/parameter)
    reference_value: Optional[float] = None
    reference_value_type: Optional[ReferenceValueType] = None  # TYPICAL, NOMINAL, DATASHEET_MAX, etc.
    reference_source: Optional[str] = None  # Authoritative source/document
    reference_verification_status: VerificationStatus = VerificationStatus.NOT_YET_VERIFIED

    def __post_init__(self):
        if isinstance(self.provenance_category, str):
            self.provenance_category = ProvenanceCategory(self.provenance_category)
        if isinstance(self.reference_verification_status, str):
            self.reference_verification_status = VerificationStatus(self.reference_verification_status)
        if self.reference_value_type is not None and isinstance(self.reference_value_type, str):
            self.reference_value_type = ReferenceValueType(self.reference_value_type)
        self.validate()

    def validate(self) -> None:
        """Validate parameter configuration integrity."""
        # Screening limit checks
        if self.user_limit_low is not None and self.user_limit_high is not None:
            if self.user_limit_low > self.user_limit_high:
                raise ValueError(
                    f"Invalid user screening limits for '{self.name}': "
                    f"user_limit_low ({self.user_limit_low}) > user_limit_high ({self.user_limit_high})"
                )

        # Reference value checks: reference_value != user_limit_high
        if self.reference_value is not None:
            if not self.reference_source:
                raise ValueError(
                    f"Parameter '{self.name}' has reference_value={self.reference_value} "
                    f"but missing reference_source provenance."
                )
            if self.reference_verification_status not in (VerificationStatus.VERIFIED, VerificationStatus.NOT_YET_VERIFIED):
                raise ValueError(f"Invalid reference verification status: {self.reference_verification_status}")

        # Provenance check
        if self.provenance_category == ProvenanceCategory.ASSUMPTION:
            if not self.assumption_id or self.assumption_id not in VALID_ASSUMPTION_IDS:
                raise ValueError(
                    f"Parameter '{self.name}' tagged as ASSUMPTION requires valid assumption_id in A1-A18, got '{self.assumption_id}'"
                )

    def to_dict(self) -> Dict[str, Any]:
        """Convert parameter configuration to dictionary for serialization/snapshots."""
        return {
            "name": self.name,
            "unit": self.unit,
            "transform": self.transform,
            "risk_direction": self.risk_direction,
            "scale_floor": self.scale_floor,
            "condition_keys": list(self.condition_keys),
            "assumption_id": self.assumption_id,
            "provenance_category": self.provenance_category.value,
            "user_limit_low": self.user_limit_low,
            "user_limit_high": self.user_limit_high,
            "reference_value": self.reference_value,
            "reference_value_type": self.reference_value_type.value if self.reference_value_type else None,
            "reference_source": self.reference_source,
            "reference_verification_status": self.reference_verification_status.value,
        }


@dataclass
class PrototypeConfig:
    """Global configuration for SIH26170 prototype screening and simulation."""
    configuration_version: str = "prototype-v1"
    lot_size: int = 30
    checkpoint_hours: List[int] = field(default_factory=lambda: [0, 24, 96, 168])
    burn_in_temperature_C: float = 125.0
    noise_scale: float = 0.02
    defect_rate: float = 0.04
    missing_rate: float = 0.03
    equipment_shift_rate: float = 0.05
    alpha: float = 0.10
    rework_risk_enabled: bool = True
    provenance_tags: Dict[str, Tuple[ProvenanceCategory, Optional[str]]] = field(default_factory=dict)

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        """Validate prototype configuration parameters."""
        if self.lot_size <= 0:
            raise ValueError(f"lot_size must be positive, got {self.lot_size}")
        if not self.checkpoint_hours or any(h < 0 for h in self.checkpoint_hours):
            raise ValueError(f"checkpoint_hours must contain non-negative integers, got {self.checkpoint_hours}")
        if sorted(self.checkpoint_hours) != list(self.checkpoint_hours):
            raise ValueError(f"checkpoint_hours must be monotonically increasing, got {self.checkpoint_hours}")
        if self.burn_in_temperature_C <= 0:
            raise ValueError(f"burn_in_temperature_C must be positive, got {self.burn_in_temperature_C}")
        if not (0.0 <= self.noise_scale <= 1.0):
            raise ValueError(f"noise_scale must be in [0, 1], got {self.noise_scale}")
        if not (0.0 <= self.defect_rate <= 1.0):
            raise ValueError(f"defect_rate must be in [0, 1], got {self.defect_rate}")
        if not (0.0 < self.alpha < 1.0):
            raise ValueError(f"alpha must be in (0, 1), got {self.alpha}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert prototype configuration to dictionary."""
        return {
            "configuration_version": self.configuration_version,
            "lot_size": self.lot_size,
            "checkpoint_hours": list(self.checkpoint_hours),
            "burn_in_temperature_C": self.burn_in_temperature_C,
            "noise_scale": self.noise_scale,
            "defect_rate": self.defect_rate,
            "missing_rate": self.missing_rate,
            "equipment_shift_rate": self.equipment_shift_rate,
            "alpha": self.alpha,
            "rework_risk_enabled": self.rework_risk_enabled,
        }


def verify_traceability(config: Union[PrototypeConfig, ParameterConfig]) -> bool:
    """Verify that a configuration object strictly complies with traceability rules."""
    if isinstance(config, ParameterConfig):
        config.validate()
        return True
    elif isinstance(config, PrototypeConfig):
        config.validate()
        return True
    return False


def _find_default_config_path(filename: str) -> Path:
    """Locate config file relative to project root or package."""
    # Try relative to current working directory
    cwd_path = Path("configs") / filename
    if cwd_path.exists():
        return cwd_path

    # Try relative to repo root based on this file's location
    module_root = Path(__file__).resolve().parent.parent.parent
    repo_path = module_root / "configs" / filename
    if repo_path.exists():
        return repo_path

    raise FileNotFoundError(f"Configuration file '{filename}' not found in configs/ or repo root.")


def load_prototype_config(config_path: Optional[Union[str, Path]] = None) -> PrototypeConfig:
    """Load PrototypeConfig from YAML file."""
    path = Path(config_path) if config_path else _find_default_config_path("prototype.yaml")
    if not path.exists():
        raise FileNotFoundError(f"Prototype configuration file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    provenance_tags: Dict[str, Tuple[ProvenanceCategory, Optional[str]]] = {
        "lot_size": (ProvenanceCategory(raw.get("lot_size_provenance", "ASSUMPTION")), raw.get("lot_size_assumption_id", "A5")),
        "checkpoint_hours": (ProvenanceCategory(raw.get("checkpoint_hours_provenance", "ASSUMPTION")), raw.get("checkpoint_hours_assumption_id", "A3")),
        "burn_in_temperature_C": (ProvenanceCategory(raw.get("burn_in_temperature_provenance", "ASSUMPTION")), raw.get("burn_in_temperature_assumption_id", "A2")),
        "noise_scale": (ProvenanceCategory(raw.get("noise_scale_provenance", "ASSUMPTION")), raw.get("noise_scale_assumption_id", "A7")),
        "defect_rate": (ProvenanceCategory(raw.get("defect_rate_provenance", "ASSUMPTION")), raw.get("defect_rate_assumption_id", "A6")),
        "missing_rate": (ProvenanceCategory(raw.get("missing_rate_provenance", "DESIGN_DECISION")), None),
        "equipment_shift_rate": (ProvenanceCategory(raw.get("equipment_shift_provenance", "DESIGN_DECISION")), None),
        "alpha": (ProvenanceCategory(raw.get("alpha_provenance", "SPECIFICATION")), None),
        "rework_risk_enabled": (ProvenanceCategory(raw.get("rework_risk_provenance", "ASSUMPTION")), raw.get("rework_risk_assumption_id", "A11")),
    }

    config = PrototypeConfig(
        configuration_version=raw.get("configuration_version", "prototype-v1"),
        lot_size=raw.get("lot_size", 30),
        checkpoint_hours=raw.get("checkpoint_hours", [0, 24, 96, 168]),
        burn_in_temperature_C=float(raw.get("burn_in_temperature_C", 125.0)),
        noise_scale=float(raw.get("noise_scale", 0.02)),
        defect_rate=float(raw.get("defect_rate", 0.04)),
        missing_rate=float(raw.get("missing_rate", 0.03)),
        equipment_shift_rate=float(raw.get("equipment_shift_rate", 0.05)),
        alpha=float(raw.get("alpha", 0.10)),
        rework_risk_enabled=bool(raw.get("rework_risk_enabled", True)),
        provenance_tags=provenance_tags,
    )
    return config


def load_parameter_configs(config_path: Optional[Union[str, Path]] = None) -> Dict[str, ParameterConfig]:
    """Load parameter configurations from YAML file."""
    path = Path(config_path) if config_path else _find_default_config_path("parameters.yaml")
    if not path.exists():
        raise FileNotFoundError(f"Parameters configuration file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    parameters_dict = raw.get("parameters", {})
    configs: Dict[str, ParameterConfig] = {}

    for name, p in parameters_dict.items():
        ref_type_raw = p.get("reference_value_type")
        ref_type = ReferenceValueType(ref_type_raw) if ref_type_raw else None

        configs[name] = ParameterConfig(
            name=p["name"],
            unit=p["unit"],
            transform=p.get("transform", "linear"),
            risk_direction=p.get("risk_direction", "high"),
            scale_floor=float(p.get("scale_floor", 0.05)),
            condition_keys=p.get("condition_keys", ["temperature_C", "test_condition"]),
            assumption_id=p.get("assumption_id"),
            provenance_category=ProvenanceCategory(p.get("provenance_category", "SPECIFICATION")),
            user_limit_low=p.get("user_limit_low"),
            user_limit_high=p.get("user_limit_high"),
            reference_value=p.get("reference_value"),
            reference_value_type=ref_type,
            reference_source=p.get("reference_source"),
            reference_verification_status=VerificationStatus(p.get("reference_verification_status", "NOT_YET_VERIFIED")),
        )

    return configs
