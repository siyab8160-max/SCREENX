"""SIH26170 Phase 2F Synthetic Configuration Schema.

Defines the mathematical and statistical parameters for the Phase 2E-compliant
physics-informed generator targeting IRHNJ57130 / JANSR2N7481U3 under MIL-PRF-19500/703.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


@dataclass(frozen=True)
class Phase2FParameterConfig:
    """Configuration for an individual physical parameter."""
    name: str
    units: str
    transform: str  # "log", "linear", or "asinh"
    scale: float = 1.0  # Scale parameter for asinh transform: asinh(x / scale)
    absolute_min: Optional[float] = None
    absolute_max: Optional[float] = None
    nominal_baseline: float = 0.0
    lot_dispersion: float = 0.1
    device_dispersion: float = 0.1
    noise_std: float = 0.05
    stress_regime: str = ""
    epistemic_layer: str = "Layer B (Verified Standard Fact)"


@dataclass(frozen=True)
class Phase2FLotConfig:
    """Configuration for a single manufacturing lot."""
    lot_id: str
    size: int
    scenario_profile: str  # primary role of the lot
    chamber_id: str = "CHAMBER_A"
    rework_count: int = 0
    has_chamber_drift: bool = False
    has_channel_bias: bool = False
    bias_channel_id: Optional[str] = None
    target_snr: Optional[float] = None
    notes: str = ""


@dataclass(frozen=True)
class Phase2FEquipmentConfig:
    """ATE test-bench equipment configuration."""
    chambers: List[str] = field(default_factory=lambda: ["CHAMBER_A", "CHAMBER_B"])
    instruments: List[str] = field(default_factory=lambda: ["ATE_BENCH_01", "ATE_BENCH_02"])
    channels_per_instrument: int = 16
    temp_drift_celsius: float = 5.0
    channel_bias_rel: float = 0.20  # relative offset on biased channel


@dataclass(frozen=True)
class Phase2FMissingnessConfig:
    """Missingness simulation configuration without imputation."""
    random_dropout_rate: float = 0.025
    allow_missing_initial: bool = False  # t=0 readouts preserved for baseline integrity


@dataclass
class Phase2FConfig:
    """Complete configuration specification for Phase 2F synthetic generator."""
    generator_version: str = "2.0.0-phase2f-dev"
    master_seed: int = 26170
    component_anchor: str = "IRHNJ57130 / JANSR2N7481U3"
    governing_specification: str = "MIL-PRF-19500/703"
    package_type: str = "SMD-0.5 (TO-276AA)"
    checkpoints: List[int] = field(default_factory=lambda: [0, 24, 96, 168])
    small_lot_threshold_policy: int = 8  # Configurable prototype policy
    subtle_snr_min: float = 1.5
    subtle_snr_max: float = 2.5
    parameters: Dict[str, Phase2FParameterConfig] = field(default_factory=dict)
    lots: List[Phase2FLotConfig] = field(default_factory=list)
    equipment: Phase2FEquipmentConfig = field(default_factory=Phase2FEquipmentConfig)
    missingness: Phase2FMissingnessConfig = field(default_factory=Phase2FMissingnessConfig)
    raw_config: Dict[str, Any] = field(default_factory=dict)


def get_default_phase2f_config() -> Phase2FConfig:
    """Construct canonical default Phase 2F configuration for IRHNJ57130."""
    parameters = {
        "IDSS": Phase2FParameterConfig(
            name="IDSS",
            units="uA",
            transform="log",
            absolute_min=None,
            absolute_max=10.0,
            nominal_baseline=0.50,
            lot_dispersion=0.15,
            device_dispersion=0.20,
            noise_std=0.04,
            stress_regime="HTRB (150°C, 80V)",
            epistemic_layer="Layer B (MIL-PRF-19500/703 Table I)",
        ),
        "VGS(th)": Phase2FParameterConfig(
            name="VGS(th)",
            units="V",
            transform="linear",
            absolute_min=2.0,
            absolute_max=4.0,
            nominal_baseline=3.00,
            lot_dispersion=0.08,
            device_dispersion=0.10,
            noise_std=0.02,
            stress_regime="HTGB (150°C, 20V)",
            epistemic_layer="Layer B (MIL-PRF-19500/703 Table I)",
        ),
        "RDS(on)": Phase2FParameterConfig(
            name="RDS(on)",
            units="mOhm",
            transform="log",
            absolute_min=None,
            absolute_max=60.0,
            nominal_baseline=48.0,
            lot_dispersion=0.06,
            device_dispersion=0.08,
            noise_std=0.6,
            stress_regime="Operating Life / Power Conduction (TJ=125-150°C)",
            epistemic_layer="Layer A (Infineon Datasheet PD-97217)",
        ),
        "IGSS": Phase2FParameterConfig(
            name="IGSS",
            units="nA",
            transform="asinh",
            scale=1.0,
            absolute_min=-100.0,
            absolute_max=100.0,
            nominal_baseline=2.0,
            lot_dispersion=0.20,
            device_dispersion=0.25,
            noise_std=0.25,
            stress_regime="HTGB (150°C, ±20V)",
            epistemic_layer="Layer B (MIL-PRF-19500/703 Table I)",
        ),
    }

    # 16 planned lots covering nominal, small-lots, specific degradation mechanisms, and common-mode
    lots = [
        # Small lots testing sensitivity sizes: N = 3, 5, 8, 12, 20
        Phase2FLotConfig(lot_id="LOT_S01", size=3, scenario_profile="small_lot_insufficient_data", notes="Sensitivity test size N=3"),
        Phase2FLotConfig(lot_id="LOT_S02", size=5, scenario_profile="small_lot_insufficient_data", notes="Sensitivity test size N=5"),
        Phase2FLotConfig(lot_id="LOT_S03", size=8, scenario_profile="small_lot_boundary", notes="Sensitivity boundary size N=8"),
        Phase2FLotConfig(lot_id="LOT_S04", size=12, scenario_profile="small_lot_intermediate", notes="Sensitivity test size N=12"),
        Phase2FLotConfig(lot_id="LOT_S05", size=20, scenario_profile="nominal_small", notes="Sensitivity test size N=20"),
        
        # Nominal healthy lots
        Phase2FLotConfig(lot_id="LOT_N01", size=30, scenario_profile="nominal_healthy", notes="Standard production flight lot"),
        Phase2FLotConfig(lot_id="LOT_N02", size=30, scenario_profile="nominal_healthy", chamber_id="CHAMBER_B", notes="Standard production flight lot Chamber B"),

        # Parameter-selective single-mechanism drift lots
        Phase2FLotConfig(lot_id="LOT_D01", size=30, scenario_profile="htrb_leakage_drift", notes="HTRB mobile ion drift predominantly on IDSS"),
        Phase2FLotConfig(lot_id="LOT_D02", size=30, scenario_profile="htgb_threshold_drift", notes="HTGB interface trap shift predominantly on VGS(th)"),
        Phase2FLotConfig(lot_id="LOT_D03", size=30, scenario_profile="thermal_power_drift", notes="Thermal packaging fatigue on RDS(on)"),
        
        # Subtle failure lot (SNR 1.5 - 2.5)
        Phase2FLotConfig(lot_id="LOT_D04", size=30, scenario_profile="subtle_failure_drift", target_snr=2.0, notes="Subtle progressive failure near noise floor"),

        # Static limit breaches (temporally stationary at t=0, non-compliant)
        Phase2FLotConfig(lot_id="LOT_L01", size=30, scenario_profile="static_limit_breach_lot", notes="Static tail outliers exceeding limits at t=0 without drift"),

        # Equipment / Common-mode anomaly lots
        Phase2FLotConfig(lot_id="LOT_E01", size=30, scenario_profile="chamber_common_mode", has_chamber_drift=True, notes="Chamber A temp drift at 96h"),
        Phase2FLotConfig(lot_id="LOT_E02", size=30, scenario_profile="channel_calibration_bias", has_channel_bias=True, bias_channel_id="CH_02", notes="ATE Card #2 channel bias"),

        # Mixed compound anomaly lot
        Phase2FLotConfig(lot_id="LOT_M01", size=30, scenario_profile="mixed_compound_anomaly", notes="Complex multi-stress compound anomalies"),

        # Large wafer lot for sensitivity evaluation (N=50)
        Phase2FLotConfig(lot_id="LOT_W01", size=50, scenario_profile="wafer_sensitivity_large", notes="Sensitivity test size N=50"),
    ]

    return Phase2FConfig(
        parameters=parameters,
        lots=lots,
        equipment=Phase2FEquipmentConfig(),
        missingness=Phase2FMissingnessConfig(),
    )


def load_phase2f_config(path: Optional[str | Path] = None) -> Phase2FConfig:
    """Load configuration from YAML or return default canonical configuration."""
    if path is None:
        return get_default_phase2f_config()
    
    p = Path(path)
    if not p.exists():
        return get_default_phase2f_config()

    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    cfg = get_default_phase2f_config()
    cfg.raw_config = data
    if "master_seed" in data:
        cfg.master_seed = int(data["master_seed"])
    if "small_lot_threshold_policy" in data:
        cfg.small_lot_threshold_policy = int(data["small_lot_threshold_policy"])
    return cfg
