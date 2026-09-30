"""SIH26170 Phase 4B Configuration Schema and Defaults.

Implements the implementation-ready benchmark specification defined by LOG-076.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class Phase4BPartition(str, Enum):
    """Quarantined partition hierarchy."""
    CALIBRATION = "CALIBRATION"
    VALIDATION = "VALIDATION"
    FINAL_EVALUATION = "FINAL_EVALUATION"


class Phase4BFixtureType(str, Enum):
    """Phase 4B statistical fixture taxonomy per LOG-076."""
    NULL_GAUSSIAN = "null_gaussian"
    NULL_AR1 = "null_ar1"
    NULL_COMMON_MODE = "null_common_mode"
    FIXTURE_A_LINEAR_DRIFT = "fixture_a_linear_drift"
    FIXTURE_B_ACCELERATING_DRIFT = "fixture_b_accelerating_drift"
    FIXTURE_C_ABRUPT_STEP = "fixture_c_abrupt_step"
    FIXTURE_D_CONFOUNDED_DRIFT = "fixture_d_confounded_drift"
    FIXTURE_E_HETEROSCEDASTIC_NOISE = "fixture_e_heteroscedastic_noise"
    FIXTURE_F_STAGGERED_ONSET = "fixture_f_staggered_onset"


@dataclass(frozen=True)
class Phase4BParameterConfig:
    """Configuration for an individual physical parameter under transformed coordinate space."""
    name: str
    units: str
    transform: str  # "log", "linear", or "asinh"
    scale: float = 1.0  # Scale parameter for asinh transform: asinh(x / scale)
    nominal_baseline: float = 0.0
    lot_dispersion: float = 0.1
    device_dispersion: float = 0.1
    noise_scale: float = 0.05  # Transformed instrumentation noise std sigma_{u,p}
    absolute_limit_low: Optional[float] = None
    absolute_limit_high: Optional[float] = None
    test_condition: str = ""
    nominal_temp: float = 150.0
    cm_temp_coeff: float = 0.0  # Transformed coordinate shift delta u per degree Celsius


@dataclass(frozen=True)
class Phase4BLotConfig:
    """Configuration for a single manufacturing lot in Phase 4B."""
    lot_id: str
    partition: Phase4BPartition
    fixture_type: Phase4BFixtureType
    size: int = 20  # Minimum lot size >= 10 for leave-one-out reference stability
    signal_delta: Optional[float] = None  # Signal strength in units of sigma_{u,p} (1.0, 1.5, 2.0, 2.5)
    target_parameter: Optional[str] = None  # "ALL", "IDSS", "VGS(th)", "RDS(on)", "IGSS"
    step_hour: Optional[int] = None  # Checkpoint hour for abrupt step (48, 72, 96)
    onset_hour: Optional[int] = None  # Checkpoint hour for staggered onset (48, 72)
    phi_range: Tuple[float, float] = (0.20, 0.35)  # Synthetic AR(1) stress parameter range
    has_chamber_drift: bool = False  # Synchronous chamber excursion (+5C at 72h, 96h)
    notes: str = ""


@dataclass
class Phase4BConfig:
    """Complete benchmark specification for Phase 4B synthetic generator."""
    benchmark_version: str = "PHASE_4B_BENCHMARK_v1.0.0"
    master_seed: int = 261704
    component_anchor: str = "IRHNJ57130 / JANSR2N7481U3"
    checkpoints: List[int] = field(default_factory=lambda: [0, 24, 48, 72, 96, 120, 168])
    parameters: Dict[str, Phase4BParameterConfig] = field(default_factory=dict)
    lots: List[Phase4BLotConfig] = field(default_factory=list)


def get_default_phase4b_config() -> Phase4BConfig:
    """Construct canonical default Phase 4B benchmark configuration matching LOG-076."""
    parameters = {
        "IDSS": Phase4BParameterConfig(
            name="IDSS",
            units="uA",
            transform="log",
            nominal_baseline=0.50,
            lot_dispersion=0.15,
            device_dispersion=0.20,
            noise_scale=0.08,
            absolute_limit_low=None,
            absolute_limit_high=10.0,
            test_condition="HTRB (150°C, 80V)",
            nominal_temp=150.0,
            cm_temp_coeff=0.04,  # +0.20 in u for +5C
        ),
        "VGS(th)": Phase4BParameterConfig(
            name="VGS(th)",
            units="V",
            transform="linear",
            nominal_baseline=3.00,
            lot_dispersion=0.08,
            device_dispersion=0.10,
            noise_scale=0.02,
            absolute_limit_low=2.0,
            absolute_limit_high=4.0,
            test_condition="HTGB (150°C, 20V)",
            nominal_temp=150.0,
            cm_temp_coeff=-0.005,  # -0.025 V for +5C
        ),
        "RDS(on)": Phase4BParameterConfig(
            name="RDS(on)",
            units="mOhm",
            transform="log",
            nominal_baseline=48.0,
            lot_dispersion=0.06,
            device_dispersion=0.08,
            noise_scale=0.0125,
            absolute_limit_low=None,
            absolute_limit_high=60.0,
            test_condition="Operating Life / Power Conduction (TJ=125-150°C)",
            nominal_temp=125.0,
            cm_temp_coeff=0.005,  # +0.025 in u for +5C
        ),
        "IGSS": Phase4BParameterConfig(
            name="IGSS",
            units="nA",
            transform="asinh",
            scale=1.0,
            nominal_baseline=2.00,
            lot_dispersion=0.20,
            device_dispersion=0.25,
            noise_scale=0.25,
            absolute_limit_low=-100.0,
            absolute_limit_high=100.0,
            test_condition="HTGB (150°C, ±20V)",
            nominal_temp=150.0,
            cm_temp_coeff=0.02,  # +0.10 in u for +5C
        ),
    }

    lots: List[Phase4BLotConfig] = []

    # =========================================================================
    # PARTITION 1: CALIBRATION (50 lots = 1,000 components = 50%)
    # =========================================================================
    # Null Models (25 lots = 500 components)
    for i in range(1, 11):
        lots.append(Phase4BLotConfig(
            lot_id=f"LOT_CAL_{i:03d}",
            partition=Phase4BPartition.CALIBRATION,
            fixture_type=Phase4BFixtureType.NULL_GAUSSIAN,
            notes="Calibration: Ideal i.i.d. Gaussian Null A",
        ))
    for i in range(11, 21):
        lots.append(Phase4BLotConfig(
            lot_id=f"LOT_CAL_{i:03d}",
            partition=Phase4BPartition.CALIBRATION,
            fixture_type=Phase4BFixtureType.NULL_AR1,
            notes="Calibration: AR(1) Correlated Session-Drift Null B",
        ))
    for i in range(21, 26):
        lots.append(Phase4BLotConfig(
            lot_id=f"LOT_CAL_{i:03d}",
            partition=Phase4BPartition.CALIBRATION,
            fixture_type=Phase4BFixtureType.NULL_COMMON_MODE,
            has_chamber_drift=True,
            notes="Calibration: Synchronous Chamber Thermal Excursion Null C",
        ))

    # Degradation Fixtures (25 lots = 500 components)
    # Fixture A: Linear Drift (5 lots)
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_026", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_A_LINEAR_DRIFT, signal_delta=1.0, target_parameter="ALL", notes="Linear drift delta=1.0 on all params"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_027", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_A_LINEAR_DRIFT, signal_delta=1.5, target_parameter="IDSS", notes="Linear drift delta=1.5 on IDSS only"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_028", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_A_LINEAR_DRIFT, signal_delta=2.0, target_parameter="VGS(th)", notes="Linear drift delta=2.0 on VGS(th) only"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_029", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_A_LINEAR_DRIFT, signal_delta=2.5, target_parameter="RDS(on)", notes="Linear drift delta=2.5 on RDS(on) only"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_030", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_A_LINEAR_DRIFT, signal_delta=1.5, target_parameter="IGSS", notes="Linear drift delta=1.5 on IGSS only"))

    # Fixture B: Accelerating Drift (5 lots)
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_031", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_B_ACCELERATING_DRIFT, signal_delta=1.0, target_parameter="ALL", notes="Accelerating drift delta=1.0 on all params"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_032", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_B_ACCELERATING_DRIFT, signal_delta=1.5, target_parameter="ALL", notes="Accelerating drift delta=1.5 on all params"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_033", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_B_ACCELERATING_DRIFT, signal_delta=2.0, target_parameter="IDSS", notes="Accelerating drift delta=2.0 on IDSS only"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_034", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_B_ACCELERATING_DRIFT, signal_delta=2.5, target_parameter="VGS(th)", notes="Accelerating drift delta=2.5 on VGS(th) only"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_035", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_B_ACCELERATING_DRIFT, signal_delta=2.0, target_parameter="RDS(on)", notes="Accelerating drift delta=2.0 on RDS(on) only"))

    # Fixture C: Abrupt Step (5 lots)
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_036", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_C_ABRUPT_STEP, signal_delta=1.5, step_hour=48, target_parameter="ALL", notes="Abrupt step delta=1.5 at 48h"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_037", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_C_ABRUPT_STEP, signal_delta=2.0, step_hour=72, target_parameter="IDSS", notes="Abrupt step delta=2.0 at 72h on IDSS"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_038", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_C_ABRUPT_STEP, signal_delta=2.5, step_hour=72, target_parameter="VGS(th)", notes="Abrupt step delta=2.5 at 72h on VGS(th)"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_039", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_C_ABRUPT_STEP, signal_delta=1.5, step_hour=96, target_parameter="RDS(on)", notes="Abrupt step delta=1.5 at 96h on RDS(on)"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_040", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_C_ABRUPT_STEP, signal_delta=2.0, step_hour=96, target_parameter="IGSS", notes="Abrupt step delta=2.0 at 96h on IGSS"))

    # Fixture D: Confounded Drift (3 lots)
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_041", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_D_CONFOUNDED_DRIFT, signal_delta=1.5, target_parameter="ALL", has_chamber_drift=True, notes="Confounded drift delta=1.5 on all params under +5C excursion"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_042", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_D_CONFOUNDED_DRIFT, signal_delta=1.5, target_parameter="IDSS", has_chamber_drift=True, notes="Confounded drift delta=1.5 on IDSS under +5C excursion"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_043", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_D_CONFOUNDED_DRIFT, signal_delta=2.0, target_parameter="RDS(on)", has_chamber_drift=True, notes="Confounded drift delta=2.0 on RDS(on) under +5C excursion"))

    # Fixture E: Heteroscedastic Noise Drift (3 lots)
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_044", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_E_HETEROSCEDASTIC_NOISE, signal_delta=1.5, target_parameter="ALL", notes="Heteroscedastic noise drift delta=1.5 on all params"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_045", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_E_HETEROSCEDASTIC_NOISE, signal_delta=2.0, target_parameter="IDSS", notes="Heteroscedastic noise drift delta=2.0 on IDSS"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_046", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_E_HETEROSCEDASTIC_NOISE, signal_delta=2.5, target_parameter="VGS(th)", notes="Heteroscedastic noise drift delta=2.5 on VGS(th)"))

    # Fixture F: Staggered Onset Drift (4 lots)
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_047", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_F_STAGGERED_ONSET, signal_delta=1.5, onset_hour=48, target_parameter="ALL", notes="Staggered onset at 48h, delta=1.5 on all params"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_048", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_F_STAGGERED_ONSET, signal_delta=2.0, onset_hour=48, target_parameter="IDSS", notes="Staggered onset at 48h, delta=2.0 on IDSS"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_049", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_F_STAGGERED_ONSET, signal_delta=1.5, onset_hour=72, target_parameter="VGS(th)", notes="Staggered onset at 72h, delta=1.5 on VGS(th)"))
    lots.append(Phase4BLotConfig(lot_id="LOT_CAL_050", partition=Phase4BPartition.CALIBRATION, fixture_type=Phase4BFixtureType.FIXTURE_F_STAGGERED_ONSET, signal_delta=2.5, onset_hour=72, target_parameter="RDS(on)", notes="Staggered onset at 72h, delta=2.5 on RDS(on)"))

    # =========================================================================
    # PARTITION 2: VALIDATION (25 lots = 500 components = 25%)
    # =========================================================================
    for i in range(1, 6):
        lots.append(Phase4BLotConfig(lot_id=f"LOT_VAL_{i:03d}", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.NULL_GAUSSIAN, notes="Validation: Null A"))
    for i in range(6, 11):
        lots.append(Phase4BLotConfig(lot_id=f"LOT_VAL_{i:03d}", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.NULL_AR1, notes="Validation: Null B"))
    for i in range(11, 13):
        lots.append(Phase4BLotConfig(lot_id=f"LOT_VAL_{i:03d}", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.NULL_COMMON_MODE, has_chamber_drift=True, notes="Validation: Null C"))

    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_013", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_A_LINEAR_DRIFT, signal_delta=1.0, target_parameter="ALL"))
    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_014", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_A_LINEAR_DRIFT, signal_delta=1.5, target_parameter="IDSS"))
    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_015", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_A_LINEAR_DRIFT, signal_delta=2.0, target_parameter="VGS(th)"))
    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_016", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_B_ACCELERATING_DRIFT, signal_delta=1.5, target_parameter="ALL"))
    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_017", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_B_ACCELERATING_DRIFT, signal_delta=2.0, target_parameter="RDS(on)"))
    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_018", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_B_ACCELERATING_DRIFT, signal_delta=2.5, target_parameter="IGSS"))
    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_019", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_C_ABRUPT_STEP, signal_delta=1.5, step_hour=48, target_parameter="ALL"))
    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_020", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_C_ABRUPT_STEP, signal_delta=2.0, step_hour=72, target_parameter="IDSS"))
    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_021", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_C_ABRUPT_STEP, signal_delta=2.5, step_hour=96, target_parameter="VGS(th)"))
    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_022", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_D_CONFOUNDED_DRIFT, signal_delta=1.5, target_parameter="ALL", has_chamber_drift=True))
    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_023", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_E_HETEROSCEDASTIC_NOISE, signal_delta=1.5, target_parameter="ALL"))
    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_024", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_F_STAGGERED_ONSET, signal_delta=1.5, onset_hour=48, target_parameter="ALL"))
    lots.append(Phase4BLotConfig(lot_id="LOT_VAL_025", partition=Phase4BPartition.VALIDATION, fixture_type=Phase4BFixtureType.FIXTURE_F_STAGGERED_ONSET, signal_delta=2.0, onset_hour=72, target_parameter="IDSS"))

    # =========================================================================
    # PARTITION 3: FINAL EVALUATION (25 lots = 500 components = 25%)
    # =========================================================================
    for i in range(1, 6):
        lots.append(Phase4BLotConfig(lot_id=f"LOT_EVAL_{i:03d}", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.NULL_GAUSSIAN, notes="Final Evaluation: Null A"))
    for i in range(6, 11):
        lots.append(Phase4BLotConfig(lot_id=f"LOT_EVAL_{i:03d}", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.NULL_AR1, notes="Final Evaluation: Null B"))
    for i in range(11, 13):
        lots.append(Phase4BLotConfig(lot_id=f"LOT_EVAL_{i:03d}", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.NULL_COMMON_MODE, has_chamber_drift=True, notes="Final Evaluation: Null C"))

    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_013", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_A_LINEAR_DRIFT, signal_delta=1.0, target_parameter="ALL"))
    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_014", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_A_LINEAR_DRIFT, signal_delta=1.5, target_parameter="IDSS"))
    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_015", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_A_LINEAR_DRIFT, signal_delta=2.0, target_parameter="VGS(th)"))
    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_016", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_B_ACCELERATING_DRIFT, signal_delta=1.5, target_parameter="ALL"))
    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_017", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_B_ACCELERATING_DRIFT, signal_delta=2.0, target_parameter="RDS(on)"))
    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_018", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_B_ACCELERATING_DRIFT, signal_delta=2.5, target_parameter="IGSS"))
    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_019", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_C_ABRUPT_STEP, signal_delta=1.5, step_hour=48, target_parameter="ALL"))
    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_020", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_C_ABRUPT_STEP, signal_delta=2.0, step_hour=72, target_parameter="IDSS"))
    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_021", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_C_ABRUPT_STEP, signal_delta=2.5, step_hour=96, target_parameter="VGS(th)"))
    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_022", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_D_CONFOUNDED_DRIFT, signal_delta=1.5, target_parameter="ALL", has_chamber_drift=True))
    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_023", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_E_HETEROSCEDASTIC_NOISE, signal_delta=1.5, target_parameter="ALL"))
    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_024", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_F_STAGGERED_ONSET, signal_delta=1.5, onset_hour=48, target_parameter="ALL"))
    lots.append(Phase4BLotConfig(lot_id="LOT_EVAL_025", partition=Phase4BPartition.FINAL_EVALUATION, fixture_type=Phase4BFixtureType.FIXTURE_F_STAGGERED_ONSET, signal_delta=2.0, onset_hour=72, target_parameter="IDSS"))

    return Phase4BConfig(
        parameters=parameters,
        lots=lots,
    )
