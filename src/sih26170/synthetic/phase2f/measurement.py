"""SIH26170 Phase 2F Measurement Simulation & Common-Mode Engine.

Implements ATE measurement transductions, chamber common-mode temperature drifts,
channel socket calibration biases, and non-imputed missingness.
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np

from sih26170.schema import CanonicalMeasurement, ValueStatus
from sih26170.synthetic.phase2f.config import Phase2FConfig, Phase2FLotConfig, Phase2FParameterConfig
from sih26170.synthetic.phase2f.latent import Phase2FLatentState
from sih26170.synthetic.phase2f.scenarios import Phase2FComponentPlan


@dataclass(frozen=True)
class Phase2FMeasurementOutcome:
    """Result of an ATE measurement attempt."""
    measurement: Optional[CanonicalMeasurement]
    is_missing: bool
    common_mode_shift: float
    channel_bias: float
    noise_realization: float


class Phase2FMeasurementSimulator:
    """Simulates ATE readouts including instrumentation noise and common-mode artifacts."""

    def __init__(self, config: Phase2FConfig):
        self.config = config

    def simulate_readout(
        self,
        latent_state: Phase2FLatentState,
        plan: Phase2FComponentPlan,
        lot_cfg: Phase2FLotConfig,
        rng_meas: np.random.Generator,
    ) -> Phase2FMeasurementOutcome:
        """Simulate physical readout on ATE test bench."""
        p_name = latent_state.parameter_name
        t = latent_state.elapsed_hours
        p_cfg = self.config.parameters[p_name]

        # 1. Missingness check (non-imputed: missing observations are omitted)
        if p_name in plan.missing_checkpoints and t in plan.missing_checkpoints[p_name]:
            return Phase2FMeasurementOutcome(
                measurement=None,
                is_missing=True,
                common_mode_shift=0.0,
                channel_bias=0.0,
                noise_realization=0.0,
            )

        # 2. Chamber common-mode temperature drift (e.g. at 96h)
        common_mode_shift = 0.0
        if lot_cfg.has_chamber_drift and t == 96:
            delta_T = self.config.equipment.temp_drift_celsius
            if p_name == "IDSS":
                # Leakage increases with chamber temperature (~ 8%/°C)
                common_mode_shift = 0.08 * delta_T  # delta_ln = 0.40 (~49% increase)
            elif p_name == "RDS(on)":
                # Resistance increases slightly with temperature (~ 0.5%/°C)
                common_mode_shift = 0.005 * delta_T
            elif p_name == "VGS(th)":
                # Threshold voltage decreases with temperature (-4 mV/°C)
                common_mode_shift = -0.004 * delta_T  # delta_V = -0.020 V

        # 3. ATE channel/socket calibration bias
        channel_bias = 0.0
        if lot_cfg.has_channel_bias and lot_cfg.bias_channel_id and plan.channel_id == lot_cfg.bias_channel_id:
            if p_cfg.transform == "log":
                channel_bias = self.config.equipment.channel_bias_rel  # +20% offset in log-space
            else:
                channel_bias = 0.10  # +100 mV offset for linear VGS(th)

        # 4. Measurement noise
        noise = float(rng_meas.normal(0.0, p_cfg.noise_std))

        # 5. Combine into observed value
        x_true = latent_state.true_value
        if p_cfg.transform == "log":
            # Multiplicative in native units: y = x* * exp(delta_chamber + beta_channel + noise_log)
            # where noise_log ~ N(0, (noise_std / nominal)^2)
            noise_log = float(rng_meas.normal(0.0, p_cfg.noise_std / p_cfg.nominal_baseline))
            y_obs = x_true * np.exp(common_mode_shift + channel_bias + noise_log)
        elif p_cfg.transform == "asinh":
            # Signed asinh transform for IGSS: preserves sign, zero, and small magnitudes around 0 nA
            if plan.scenario_tag == "stationary_zero_igss" and p_name == "IGSS":
                y_obs = 0.0
            else:
                s = p_cfg.scale
                u_true = np.arcsinh(x_true / s)
                noise_u = float(rng_meas.normal(0.0, p_cfg.noise_std / s))
                u_obs = u_true + common_mode_shift + channel_bias + noise_u
                y_obs = s * np.sinh(u_obs)
        else:
            # Additive in linear units: y = x* + delta_chamber + beta_channel + noise
            y_obs = x_true + common_mode_shift + channel_bias + noise

        # Epoch timestamp calculation: base 2026-09-01T00:00:00Z + t hours
        base_epoch = 1788220800  # 2026-09-01 00:00:00 UTC
        meas_epoch = base_epoch + (t * 3600)

        temp_c = 150.0 if ("HTRB" in p_cfg.stress_regime or "HTGB" in p_cfg.stress_regime) else 125.0
        meas = CanonicalMeasurement(
            component_id=plan.component_id,
            lot_id=plan.lot_id,
            parameter_name=p_name,
            elapsed_hours=t,
            value=float(y_obs),
            unit=p_cfg.units,
            temperature_C=temp_c,
            test_condition=p_cfg.stress_regime,
            instrument_id=plan.instrument_id,
            channel_id=plan.channel_id,
            measurement_quality="VALID",
            rework_count=plan.rework_count,
            absolute_limit_low=p_cfg.absolute_min,
            absolute_limit_high=p_cfg.absolute_max,
            source_type="synthetic",
        )

        return Phase2FMeasurementOutcome(
            measurement=meas,
            is_missing=False,
            common_mode_shift=common_mode_shift,
            channel_bias=channel_bias,
            noise_realization=noise,
        )
