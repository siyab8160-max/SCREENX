"""SIH26170 Synthetic Generator Configuration Dataclasses and Loader.

Represents all configurable simulation parameters with explicit epistemic provenance.
Conforms to docs/PHASE_2_SYNTHETIC_DATA_SPEC.md.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from sih26170.config import ProvenanceCategory


@dataclass(frozen=True)
class ParameterSimConfig:
    """Simulation settings for a specific physical parameter."""
    name: str
    unit: str
    transform: str  # "log" or "linear"
    nominal_lot_baseline: float
    lot_dispersion: float
    comp_dispersion: float
    noise_floor: float  # synthetic numerical noise floor
    theta_abnormal: float  # dimensionless relative latent threshold
    user_limit_high: Optional[float] = None
    user_limit_low: Optional[float] = None
    provenance_category: ProvenanceCategory = ProvenanceCategory.SPECIFICATION


@dataclass(frozen=True)
class LotSimConfig:
    """Simulation configuration for a specific lot."""
    lot_id: str
    size: int
    partition: str  # "train", "validation", "test"
    scenario: str = "nominal"  # "nominal", "canonical_high_stable", "small_lot", etc.
    rework_regime: str = "R0"  # "R0", "R1", "R2"


@dataclass(frozen=True)
class EquipmentSimConfig:
    """Equipment test-bench configuration."""
    instruments: List[str]
    channels_per_instrument: int
    common_mode_gain_shift: float = 0.15
    channel_offset_shifts: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class MissingnessSimConfig:
    """Missingness simulation configuration."""
    random_dropout_rate: float = 0.03
    checkpoint_outage_rate: float = 0.0
    component_pull_rate: float = 0.01


@dataclass(frozen=True)
class CanonicalFixtureConfig:
    """Canonical 45 uA demonstration test case configuration."""
    component_id: str = "CANONICAL_C45"
    lot_id: str = "L11"
    parameter: str = "leakage_current"
    initial_value: float = 45.0
    lot_baseline: float = 10.0
    screening_limit: float = 50.0


@dataclass(frozen=True)
class SyntheticConfig:
    """Top-level configuration for synthetic burn-in generator."""
    generator_version: str
    master_seed: int
    burn_in_temperature_C: float
    test_condition: str
    checkpoints: List[int]
    parameters: Dict[str, ParameterSimConfig]
    noise_scale: float
    trajectory_probabilities: Dict[str, float]
    lots: List[LotSimConfig]
    equipment: EquipmentSimConfig
    missingness: MissingnessSimConfig
    canonical_fixture: CanonicalFixtureConfig
    raw_config: Dict[str, Any] = field(default_factory=dict, repr=False)

    def get_parameter(self, name: str) -> ParameterSimConfig:
        if name not in self.parameters:
            raise KeyError(f"Parameter '{name}' not found in synthetic configuration.")
        return self.parameters[name]

    def get_lot(self, lot_id: str) -> LotSimConfig:
        for lot in self.lots:
            if lot.lot_id == lot_id:
                return lot
        raise KeyError(f"Lot '{lot_id}' not found in synthetic configuration.")


def load_synthetic_config(config_path: str | Path = "configs/synthetic.yaml") -> SyntheticConfig:
    """Load and validate synthetic generator configuration from YAML."""
    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"Synthetic configuration file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Parse parameters
    params = {}
    for p_name, p_data in data["parameters"].items():
        prov_str = p_data.get("provenance_category", "SPECIFICATION")
        params[p_name] = ParameterSimConfig(
            name=p_data["name"],
            unit=p_data["unit"],
            transform=p_data["transform"],
            nominal_lot_baseline=float(p_data["nominal_lot_baseline"]),
            lot_dispersion=float(p_data["lot_dispersion"]),
            comp_dispersion=float(p_data["comp_dispersion"]),
            noise_floor=float(p_data["noise_floor"]),
            theta_abnormal=float(p_data["theta_abnormal"]),
            user_limit_high=float(p_data["user_limit_high"]) if p_data.get("user_limit_high") is not None else None,
            user_limit_low=float(p_data["user_limit_low"]) if p_data.get("user_limit_low") is not None else None,
            provenance_category=ProvenanceCategory(prov_str),
        )

    # Parse lots
    lots = []
    for l_data in data["lots"]:
        lots.append(
            LotSimConfig(
                lot_id=l_data["lot_id"],
                size=int(l_data["size"]),
                partition=l_data["partition"],
                scenario=l_data.get("scenario", "nominal"),
                rework_regime=l_data.get("rework_regime", "R0"),
            )
        )

    # Parse equipment
    eq_data = data["equipment"]
    equipment = EquipmentSimConfig(
        instruments=list(eq_data["instruments"]),
        channels_per_instrument=int(eq_data["channels_per_instrument"]),
        common_mode_gain_shift=float(eq_data.get("common_mode_gain_shift", 0.15)),
        channel_offset_shifts=eq_data.get("channel_offset_shifts", {}),
    )

    # Parse missingness
    m_data = data["missingness"]
    missingness = MissingnessSimConfig(
        random_dropout_rate=float(m_data.get("random_dropout_rate", 0.03)),
        checkpoint_outage_rate=float(m_data.get("checkpoint_outage_rate", 0.0)),
        component_pull_rate=float(m_data.get("component_pull_rate", 0.01)),
    )

    # Parse canonical fixture
    cf_data = data.get("canonical_fixture", {})
    canonical_fixture = CanonicalFixtureConfig(
        component_id=cf_data.get("component_id", "CANONICAL_C45"),
        lot_id=cf_data.get("lot_id", "L11"),
        parameter=cf_data.get("parameter", "leakage_current"),
        initial_value=float(cf_data.get("initial_value", 45.0)),
        lot_baseline=float(cf_data.get("lot_baseline", 10.0)),
        screening_limit=float(cf_data.get("screening_limit", 50.0)),
    )

    return SyntheticConfig(
        generator_version=data.get("generator_version", "2.0-prototype"),
        master_seed=int(data["master_seed"]),
        burn_in_temperature_C=float(data["burn_in_temperature_C"]),
        test_condition=data.get("test_condition", "STATIC_BURN_IN"),
        checkpoints=[int(cp) for cp in data["checkpoints"]],
        parameters=params,
        noise_scale=float(data["noise_scale"]),
        trajectory_probabilities={k: float(v) for k, v in data["trajectory_probabilities"].items()},
        lots=lots,
        equipment=equipment,
        missingness=missingness,
        canonical_fixture=canonical_fixture,
        raw_config=data,
    )
