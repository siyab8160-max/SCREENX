"""SIH26170 Synthetic Measurement Process Simulator.

Transforms uncorrupted latent physical states x* into observed sensor telemetry y:
    y = x* * (1 + E_mult + ε) + E_offset + η_floor

Where:
- E_mult is a dimensionless equipment common-mode gain shift
- ε ~ N(0, σ_rel^2) is dimensionless relative aleatory sensor noise
- E_offset is a channel/socket zero-offset in native parameter units
- η_floor ~ N(0, σ_floor^2) is the synthetic numerical noise floor in native units

Preserves raw negative observations without flooring or clipping (LOG-020).
Simulates realistic test-bench missingness (dropout, batch outage, component pull).
Conforms to docs/PHASE_2_SYNTHETIC_DATA_SPEC.md.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from sih26170.schema import CanonicalMeasurement, classify_measurement_value, ValueStatus
from sih26170.synthetic.config import ParameterSimConfig, SyntheticConfig
from sih26170.synthetic.latent import LatentState


@dataclass(frozen=True)
class EquipmentContext:
    """Holds test-bench equipment assignment and active calibration shifts."""
    instrument_id: str
    channel_id: str
    common_mode_gain_shift: float  # Dimensionless multiplicative factor
    channel_offset: float          # In native parameter units


@dataclass(frozen=True)
class MeasurementOutcome:
    """Represents the simulation outcome for a single sensor readout."""
    is_missing: bool
    missing_reason: Optional[str]
    measurement: Optional[CanonicalMeasurement]
    observed_value: Optional[float]
    value_status: Optional[ValueStatus]
    latent_value: float


class MeasurementSimulator:
    """Simulates physical sensor readouts and test-bench instrumentation."""

    def __init__(self, config: SyntheticConfig):
        self.config = config

    def simulate_readout(
        self,
        latent_state: LatentState,
        equipment: EquipmentContext,
        rework_count: int,
        noise_scale: float,
        rng: np.random.Generator,
        is_dropout: bool = False,
    ) -> MeasurementOutcome:
        """Simulate a single measurement readout from latent state."""
        param_config = self.config.get_parameter(latent_state.parameter_name)
        x_star = latent_state.latent_value

        if is_dropout:
            return MeasurementOutcome(
                is_missing=True,
                missing_reason="RANDOM_DROPOUT",
                measurement=None,
                observed_value=None,
                value_status=ValueStatus.MISSING,
                latent_value=x_star,
            )

        # 1. Aleatory relative sensor noise: ε ~ N(0, σ_rel^2)
        epsilon = float(rng.normal(0.0, noise_scale))

        # 2. Equipment multiplicative gain shift (dimensionless)
        e_mult = equipment.common_mode_gain_shift

        # 3. Channel offset in native parameter units
        e_offset = equipment.channel_offset

        # 4. Synthetic numerical noise floor in native parameter units
        sigma_floor = param_config.noise_floor
        eta_floor = float(rng.normal(0.0, sigma_floor))

        # 5. Calculate observed reading:
        # y = x* * (1 + E_mult + ε) + E_offset + η_floor
        y = x_star * (1.0 + e_mult + epsilon) + e_offset + eta_floor

        # For propagation delay, prevent physically impossible negative latency
        if param_config.transform == "linear" and y <= 0.0:
            y = max(0.01, abs(y))

        # Raw observation is preserved as-is (never floored to zero or log-clamped)
        val_status = classify_measurement_value(y)

        # Build canonical measurement (strictly observation layer)
        measurement = CanonicalMeasurement(
            component_id=latent_state.component_id,
            lot_id=latent_state.lot_id,
            parameter_name=latent_state.parameter_name,
            elapsed_hours=latent_state.elapsed_hours,
            value=float(y),
            unit=param_config.unit,
            temperature_C=self.config.burn_in_temperature_C,
            test_condition=self.config.test_condition,
            instrument_id=equipment.instrument_id,
            channel_id=equipment.channel_id,
            measurement_quality="VALID",
            rework_count=rework_count,
            absolute_limit_low=param_config.user_limit_low,
            absolute_limit_high=param_config.user_limit_high,
            source_type="synthetic",
        )

        return MeasurementOutcome(
            is_missing=False,
            missing_reason=None,
            measurement=measurement,
            observed_value=float(y),
            value_status=val_status,
            latent_value=x_star,
        )
