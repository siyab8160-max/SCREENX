"""Detector E: Common-Mode / Equipment Artifact Detector (D_eq).

Compliant with docs/PHASE_3A_MODULE_A_SPEC.md & Phase 3C Pre-Implementation Amendments:
- Evaluates lot-wide chamber thermal excursions via synchronous population shifts
- Evaluates ATE fixture channel offsets via standardized robust residuals (Z_channel)
- Suppresses channel bias inference when N_k < 4 because for very small N_k,
  the finite-sample distribution of the median is poorly approximated by the
  asymptotic normal standard-error formula, making tail-based channel-bias inference unreliable.
- Retains raw telemetry without in-place mutation or imputation.
- Classifies critical threshold |Z| >= 3.42 as a Layer F Benchmark/Design Parameter
  (Bonferroni-corrected alpha_FWER approx 0.01 across K=16 channels under Gaussian null).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from sih26170.screening.schema import (
    AteEvidence,
    ChamberEvidence,
    EquipmentEvidence,
    EquipmentStatus,
)
from sih26170.screening.transforms import (
    get_noise_floor,
    transform_parameter,
)

# Minimum proportion of lot shifting synchronously to suspect chamber excursion (Class D heuristic)
CHAMBER_SYNCHRONY_PROPORTION: float = 0.75
# Scale multiplier for chamber shift threshold (Class D heuristic)
CHAMBER_SHIFT_SCALE_MULTIPLIER: float = 3.0

# Minimum channel subgroup size for statistical inference
# For N_k < 4, finite-sample median distribution is poorly approximated by asymptotic SE formula
MIN_CHANNEL_SAMPLE_SIZE: int = 4

# Asymptotic normal median SE scale constant: sqrt(pi / 2) approx 1.253314
MEDIAN_SE_CONSTANT: float = 1.2533141373155001

# Normal MAD consistency factor for standard deviation
NORMAL_MAD_SCALE: float = 1.482602218505602

# Standardized residual critical threshold (Layer F Benchmark/Design Parameter)
# Corresponds to two-tailed Bonferroni alpha = 0.01 / 16 = 0.000625 under asymptotic standard normal
CHANNEL_BIAS_Z_THRESHOLD: float = 3.42


def evaluate_chamber_excursion(
    parameter: str,
    lot_df_as_of: pd.DataFrame,
    checkpoint: int,
) -> ChamberEvidence:
    """Evaluate synchronous lot-wide chamber excursion across adjacent checkpoints.

    Args:
        parameter: Parameter name ('IDSS', 'VGS(th)', 'RDS(on)', 'IGSS')
        lot_df_as_of: Telemetry dataframe for this lot strictly with elapsed_hours <= checkpoint
        checkpoint: Current as-of evaluation checkpoint T

    Returns:
        ChamberEvidence detailing median shift, fraction shifting, and suspicion status.
    """
    floor = get_noise_floor(parameter)
    p_df = lot_df_as_of[lot_df_as_of["parameter_name"] == parameter].copy()

    chamber_suspected = False
    lot_median_shift: Optional[float] = None
    frac_shifting: Optional[float] = None
    reason_code = "NOMINAL_CHAMBER_ENVIRONMENT"

    available_times = sorted(p_df["elapsed_hours"].unique())
    if checkpoint > 0 and len(available_times) >= 2 and checkpoint in available_times:
        prior_times = [t for t in available_times if t < checkpoint]
        if prior_times:
            t_prev = prior_times[-1]

            # Find components with valid measurements at both t_prev and checkpoint
            df_prev = p_df[p_df["elapsed_hours"] == t_prev].set_index("component_id")["value"]
            df_curr = p_df[p_df["elapsed_hours"] == checkpoint].set_index("component_id")["value"]
            common_components = df_prev.index.intersection(df_curr.index)

            if len(common_components) >= 4:
                shifts: List[float] = []
                for cid in common_components:
                    try:
                        u_p = transform_parameter(parameter, df_prev.loc[cid])
                        u_c = transform_parameter(parameter, df_curr.loc[cid])
                        shifts.append(u_c - u_p)
                    except ValueError:
                        continue

                if len(shifts) >= 4:
                    shifts_arr = np.array(shifts, dtype=np.float64)
                    lot_median_shift = float(np.median(shifts_arr))
                    if abs(lot_median_shift) > 1e-6:
                        s_sign = np.sign(lot_median_shift)
                        same_dir_count = int(np.sum(np.sign(shifts_arr) == s_sign))
                        frac_shifting = float(same_dir_count / len(shifts_arr))

                        # Synchronous chamber excursion: significant shift + high fraction of lot
                        if (
                            abs(lot_median_shift) >= (CHAMBER_SHIFT_SCALE_MULTIPLIER * floor)
                            and frac_shifting >= CHAMBER_SYNCHRONY_PROPORTION
                        ):
                            chamber_suspected = True
                            reason_code = "CHAMBER_SYNCHRONOUS_EXCURSION"

    return ChamberEvidence(
        lot_median_shift=lot_median_shift,
        fraction_shifting=frac_shifting,
        suspected=chamber_suspected,
        reason_code=reason_code,
    )


def evaluate_fixture_channel_bias(
    parameter: str,
    curr_checkpoint_df: pd.DataFrame,
    channel_id: Optional[str],
) -> AteEvidence:
    """Evaluate ATE fixture channel offset using robust standardized residuals.

    Args:
        parameter: Parameter name ('IDSS', 'VGS(th)', 'RDS(on)', 'IGSS')
        curr_checkpoint_df: Telemetry dataframe for the lot at checkpoint T
        channel_id: Channel / socket identifier under evaluation

    Returns:
        AteEvidence detailing channel offset, sample sizes, Z-score, and suspicion status.
    """
    if channel_id is None or "channel_id" not in curr_checkpoint_df.columns:
        return AteEvidence(
            channel_id=channel_id,
            n_channel=0,
            n_lot_other=0,
            channel_offset=None,
            z_score=None,
            suppressed=True,
            suspected=False,
            reason_code="NO_CHANNEL_ID_METADATA",
        )

    floor = get_noise_floor(parameter)
    p_df = curr_checkpoint_df[curr_checkpoint_df["parameter_name"] == parameter]

    channel_vals = p_df[p_df["channel_id"] == channel_id]["value"].dropna()
    other_vals = p_df[p_df["channel_id"] != channel_id]["value"].dropna()
    lot_vals = p_df["value"].dropna()

    u_chan: List[float] = []
    for v in channel_vals:
        try:
            u_chan.append(transform_parameter(parameter, v))
        except ValueError:
            continue

    u_other: List[float] = []
    for v in other_vals:
        try:
            u_other.append(transform_parameter(parameter, v))
        except ValueError:
            continue

    u_lot: List[float] = []
    for v in lot_vals:
        try:
            u_lot.append(transform_parameter(parameter, v))
        except ValueError:
            continue

    n_k = len(u_chan)
    n_other = len(u_other)

    # Small sample suppression:
    # For very small N_k (N_k < 4), the finite-sample distribution of the median
    # is poorly approximated by the asymptotic normal standard-error formula,
    # making tail-based channel-bias inference unreliable.
    if n_k < MIN_CHANNEL_SAMPLE_SIZE:
        chan_med = float(np.median(u_chan)) if n_k > 0 else None
        lot_med = float(np.median(u_lot)) if len(u_lot) > 0 else None
        offset = float(chan_med - lot_med) if (chan_med is not None and lot_med is not None) else None
        return AteEvidence(
            channel_id=channel_id,
            n_channel=n_k,
            n_lot_other=n_other,
            channel_offset=offset,
            z_score=None,
            suppressed=True,
            suspected=False,
            reason_code="CHANNEL_BIAS_SUPPRESSED_SMALL_SAMPLE",
        )

    if n_other < 4:
        return AteEvidence(
            channel_id=channel_id,
            n_channel=n_k,
            n_lot_other=n_other,
            channel_offset=None,
            z_score=None,
            suppressed=True,
            suspected=False,
            reason_code="INSUFFICIENT_REFERENCE_POPULATION",
        )

    med_k = float(np.median(u_chan))
    med_other = float(np.median(u_other))
    channel_offset = med_k - med_other

    # Robust scale from entire lot
    u_lot_arr = np.array(u_lot, dtype=np.float64)
    med_lot = float(np.median(u_lot_arr))
    mad_lot = float(np.median(np.abs(u_lot_arr - med_lot)))
    sigma_eff = max(NORMAL_MAD_SCALE * mad_lot, floor)

    # Asymptotic standard error of median difference under Gaussian null
    se = MEDIAN_SE_CONSTANT * sigma_eff * np.sqrt(1.0 / n_k + 1.0 / n_other)
    z_score = channel_offset / se if se > 0 else 0.0

    suspected = bool(abs(z_score) >= CHANNEL_BIAS_Z_THRESHOLD)
    reason_code = "ATE_CHANNEL_FIXTURE_BIAS" if suspected else "NOMINAL_ATE_CHANNEL"

    return AteEvidence(
        channel_id=channel_id,
        n_channel=n_k,
        n_lot_other=n_other,
        channel_offset=float(channel_offset),
        z_score=float(z_score),
        suppressed=False,
        suspected=suspected,
        reason_code=reason_code,
    )


def evaluate_equipment_environment(
    lot_id: str,
    checkpoint: int,
    parameter: str,
    lot_df_as_of: pd.DataFrame,
    target_component_id: Optional[str] = None,
    instrument_id: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> EquipmentEvidence:
    """Evaluate common-mode equipment and chamber signals on the as-of telemetry slice.

    Args:
        lot_id: Manufacturing/screening lot identifier
        checkpoint: Current as-of evaluation checkpoint T
        parameter: Parameter name ('IDSS', 'VGS(th)', 'RDS(on)', 'IGSS')
        lot_df_as_of: Telemetry dataframe for this lot strictly with elapsed_hours <= checkpoint
        target_component_id: Optional target component ID
        instrument_id: Optional ATE bench identifier
        channel_id: Optional fixture socket / channel identifier

    Returns:
        EquipmentEvidence containing chamber shift, channel offset, and suspected status.
    """
    # 1. Chamber excursion evaluation across adjacent checkpoints
    chamber_ev = evaluate_chamber_excursion(
        parameter=parameter,
        lot_df_as_of=lot_df_as_of,
        checkpoint=checkpoint,
    )

    # 2. ATE Fixture Channel Offset evaluation at checkpoint
    curr_checkpoint_df = lot_df_as_of[lot_df_as_of["elapsed_hours"] == checkpoint]
    ate_ev = evaluate_fixture_channel_bias(
        parameter=parameter,
        curr_checkpoint_df=curr_checkpoint_df,
        channel_id=channel_id,
    )

    # 3. Synthesize equipment status
    if chamber_ev.suspected:
        status = EquipmentStatus.CHAMBER_EXCURSION_SUSPECTED
        suspected = True
        reason_code = chamber_ev.reason_code
    elif ate_ev.suspected:
        status = EquipmentStatus.CHANNEL_BIAS_SUSPECTED
        suspected = True
        reason_code = ate_ev.reason_code
    elif ate_ev.suppressed:
        status = EquipmentStatus.CHANNEL_BIAS_SUPPRESSED_SMALL_SAMPLE
        suspected = False
        reason_code = ate_ev.reason_code
    else:
        status = EquipmentStatus.NOMINAL_EQUIPMENT
        suspected = False
        reason_code = "NOMINAL_EQUIPMENT_ENVIRONMENT"

    return EquipmentEvidence(
        lot_id=lot_id,
        checkpoint=checkpoint,
        instrument_id=instrument_id,
        channel_id=channel_id,
        lot_median_shift=chamber_ev.lot_median_shift,
        fraction_shifting=chamber_ev.fraction_shifting,
        channel_offset=ate_ev.channel_offset,
        status=status,
        suspected=suspected,
        reason_code=reason_code,
        chamber_evidence=chamber_ev,
        ate_evidence=ate_ev,
    )
