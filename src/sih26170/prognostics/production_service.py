"""Module B Production Service & Release Integration Engine.

Implements STEP 8 requirements for SIH 2026 Problem Statement SIH26170:
- Production-facing Module B output contract (ModuleBOutput)
- Frozen Zero-Anchored Residual HistGBM forecaster with regime-conditioned conformal intervals
- Full data / edge-case hardening (refusal on insufficient data, zero NaN/Inf leakage, unit preservation)
- Decoupled Module A / Module B interface with bidirectional evidence preservation
- Decision-support safety-slope integration (early measurement -> point forecast -> interval -> threshold -> safety slope -> QA advisory)
- Rigorous physical QA explainability object (no vague "AI" terminology)
- Informational decision support only — NO AUTONOMOUS REJECTION / SCRAP CONTROLLER
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import pandas as pd

from sih26170.screening.transforms import (
    get_noise_floor,
    inverse_transform_parameter,
    transform_parameter,
)
from sih26170.prognostics.lot_context import (
    ResidualHistGBMModel,
    ZeroAnchoredHybridPrognosticModel,
    extract_loo_lot_context_features,
)
from sih26170.synthetic.burnin_generator import SyntheticBurnInGenerator
from sih26170.prognostics.safety import (
    SafetyConfig,
    SafetyDecision,
    SafetySlopeEvaluator,
    IntervalSafetyStatus,
)
from sih26170.screening.schema import ComponentScreeningResult


# ============================================================
# Canonical Constants & Frozen Release Specifications
# ============================================================

CANONICAL_PARAMETERS = ("IDSS", "VGS(th)", "RDS(on)", "IGSS")

CANONICAL_UNITS: Dict[str, str] = {
    "IDSS": "uA",
    "VGS(th)": "V",
    "RDS(on)": "mOhm",
    "IGSS": "nA",
}

# Frozen regime decision thresholds from Step 6 & 7 Freeze Manifest
FROZEN_REGIME_THRESHOLDS: Dict[str, float] = {
    "IDSS": 0.0648496515277103,
    "VGS(th)": 0.021568977823908864,
    "RDS(on)": 0.013243167732299863,
    "IGSS": 0.18743324021279184,
}

# Frozen regime-conditioned conformal calibration quantiles from Step 6 & 7 Freeze Manifest
FROZEN_CONFORMAL_QUANTILES: Dict[str, Dict[str, Dict[str, float]]] = {
    "IDSS": {
        "ZERO_ANCHORED": {
            "q90": 1.7310065961056587,
            "q95": 1.775533162799307,
        },
        "DRIFT_MODEL": {
            "q90": 1.426713739798579,
            "q95": 1.5214188730997327,
        },
    },
    "VGS(th)": {
        "ZERO_ANCHORED": {
            "q90": 0.6755717616111105,
            "q95": 0.7519662828698007,
        },
        "DRIFT_MODEL": {
            "q90": 0.44986358170275814,
            "q95": 0.5394605929653896,
        },
    },
    "RDS(on)": {
        "ZERO_ANCHORED": {
            "q90": 0.4717169476722369,
            "q95": 0.5697359556101429,
        },
        "DRIFT_MODEL": {
            "q90": 0.36643807212470775,
            "q95": 0.37849102434517173,
        },
    },
    "IGSS": {
        "ZERO_ANCHORED": {
            "q90": 3.173402778732049,
            "q95": 3.996544929849206,
        },
        "DRIFT_MODEL": {
            "q90": 1.938428807802817,
            "q95": 2.180031899120612,
        },
    },
}

FEATURE_COLUMNS: List[str] = [
    "u24",
    "component_drift",
    "lot_drift",
    "excess_drift",
]


# ============================================================
# Enums
# ============================================================

class ModuleBAdvisoryStatus(str, Enum):
    """Production QA decision-support advisory status.
    
    CRITICAL: This is an advisory recommendation for QA engineering review.
    It does NOT grant autonomous machine control or automated scrap authority.
    """
    CONTINUE = "CONTINUE"
    EARLY_WARNING = "EARLY_WARNING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ModuleBRegime(str, Enum):
    """Dual-regime forecasting partition."""
    ZERO_ANCHORED = "ZERO_ANCHORED"
    DRIFT_MODEL = "DRIFT_MODEL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


# ============================================================
# Output Contracts
# ============================================================

@dataclass(frozen=True)
class ModuleBExplanation:
    """Rigorous physical explainability evidence object.
    
    Contains exact mathematical and physical reasons for the regime choice,
    forecast trajectory, uncertainty band, and QA advisory status.
    Prohibits generic or uninformative buzzwords (e.g. 'AI detected anomaly').
    """
    early_drift_signal: Optional[float]
    excess_drift: Optional[float]
    selected_regime: str
    predicted_168h_value: Optional[float]
    uncertainty_interval_90: Optional[Tuple[float, float]]
    uncertainty_interval_95: Optional[Tuple[float, float]]
    threshold_proximity: Dict[str, float]
    reason_for_advisory_status: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModuleBOutput:
    """Production-facing Module B Output Contract.
    
    Contains point forecast, regime-conditioned conformal prediction intervals,
    parameter-specific threshold checks (including 60 mOhm screening margin and
    65 mOhm specification ceiling for RDS(on)), safety-slope decision support,
    and a structured explainability object.
    """
    component_id: str
    lot_id: str
    parameter_name: str
    predicted_value: float
    lower_90: float
    upper_90: float
    lower_95: float
    upper_95: float
    regime: str
    uncertainty_width_90: float
    uncertainty_width_95: float

    # RDS(on) specific screening fields
    crosses_60: bool
    entirely_below_60: bool
    entirely_above_60: bool
    crosses_65: bool
    entirely_below_65: bool
    entirely_above_65: bool

    # Advisory status (Decision support only; never autonomous scrap controller)
    advisory_status: ModuleBAdvisoryStatus
    explanation: ModuleBExplanation

    # Additional metadata
    unit: str = ""
    is_valid: bool = True
    refusal_reason: Optional[str] = None
    predicted_drift_rate: Optional[float] = None
    safety_slope: Optional[float] = None
    safety_threshold: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["advisory_status"] = self.advisory_status.value
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass(frozen=True)
class UnifiedPipelineEvidence:
    """Unified container integrating Module A screening and Module B prognostics.
    
    Enforces bidirectional evidence preservation:
    - Module A screening disposition is never overwritten by Module B.
    - Module B prognostic forecast and intervals are never overwritten by Module A.
    - Equipment and common-mode evidence from Module A co-exists transparently.
    """
    component_id: str
    lot_id: str
    as_of_hours: int
    module_a_screening: Optional[Dict[str, Any]]
    module_b_prognostics: Dict[str, Dict[str, Any]]
    unified_advisory: str
    preservation_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# Model Registry & Deterministic Factory
# ============================================================

_FROZEN_MODELS: Optional[Dict[str, ZeroAnchoredHybridPrognosticModel]] = None


def get_frozen_production_models() -> Dict[str, ZeroAnchoredHybridPrognosticModel]:
    """Retrieve or fit cached frozen Zero-Anchored Residual HistGBM models.
    
    Models are trained strictly on development lots LOT01-LOT08 using
    locked seed 20260918, exactly replicating the Step 7 frozen release candidate.
    """
    global _FROZEN_MODELS
    if _FROZEN_MODELS is not None:
        return _FROZEN_MODELS

    # Fit forecaster strictly on Development Training Cohort (LOT01-LOT08)
    gen = SyntheticBurnInGenerator(seed=20260918)
    train_obs, train_gt, _ = gen.generate(
        lots=[f"LOT{i:02d}" for i in range(1, 9)],
        mode="stress",
    )
    train_feat = extract_loo_lot_context_features(train_obs)

    gt_168 = (
        train_gt[train_gt["target_horizon_hours"] == 168]
        .copy()
        .rename(columns={"actual_value": "y_168"})
    )
    gt_168["u_168"] = [
        transform_parameter(p, val)
        for p, val in zip(gt_168["parameter_name"], gt_168["y_168"])
    ]

    merged = pd.merge(
        train_feat,
        gt_168[["component_id", "lot_id", "parameter_name", "u_168", "y_168"]],
        on=["component_id", "lot_id", "parameter_name"],
    )
    merged["delta_u"] = merged["u_168"] - merged["u24"]

    models: Dict[str, ZeroAnchoredHybridPrognosticModel] = {}
    for p in CANONICAL_PARAMETERS:
        sub_p = merged[merged["parameter_name"] == p]
        gm = ResidualHistGBMModel(
            parameter_name=p,
            feature_columns=FEATURE_COLUMNS,
            max_depth=3,
            max_iter=50,
            learning_rate=0.05,
            min_samples_leaf=10,
            l2_regularization=1.0,
            random_state=20260918,
        )
        gm.fit(sub_p[FEATURE_COLUMNS].values, sub_p["delta_u"].values)
        za = ZeroAnchoredHybridPrognosticModel(
            parameter_name=p,
            base_model=gm,
            threshold=FROZEN_REGIME_THRESHOLDS[p],
            feature_columns=FEATURE_COLUMNS,
        )
        models[p] = za

    _FROZEN_MODELS = models
    return _FROZEN_MODELS


# ============================================================
# Production Module B Inference Engine
# ============================================================

def create_insufficient_data_output(
    component_id: str,
    lot_id: str,
    parameter_name: str,
    reason: str,
    unit: Optional[str] = None,
) -> ModuleBOutput:
    """Produce deterministic refusal output when input data are insufficient or corrupt."""
    p_unit = unit or CANONICAL_UNITS.get(parameter_name, "")
    explanation = ModuleBExplanation(
        early_drift_signal=None,
        excess_drift=None,
        selected_regime=ModuleBRegime.INSUFFICIENT_DATA.value,
        predicted_168h_value=None,
        uncertainty_interval_90=None,
        uncertainty_interval_95=None,
        threshold_proximity={},
        reason_for_advisory_status=(
            f"INSUFFICIENT_DATA: {reason}. Prognostic extrapolation safely refused."
        ),
        details={"refusal_reason": reason},
    )
    return ModuleBOutput(
        component_id=component_id,
        lot_id=lot_id,
        parameter_name=parameter_name,
        predicted_value=float("nan"),
        lower_90=float("nan"),
        upper_90=float("nan"),
        lower_95=float("nan"),
        upper_95=float("nan"),
        regime=ModuleBRegime.INSUFFICIENT_DATA.value,
        uncertainty_width_90=float("nan"),
        uncertainty_width_95=float("nan"),
        crosses_60=False,
        entirely_below_60=False,
        entirely_above_60=False,
        crosses_65=False,
        entirely_below_65=False,
        entirely_above_65=False,
        advisory_status=ModuleBAdvisoryStatus.INSUFFICIENT_DATA,
        explanation=explanation,
        unit=p_unit,
        is_valid=False,
        refusal_reason=reason,
    )


def predict_module_b_series(
    component_id: str,
    lot_id: str,
    parameter_name: str,
    v0: Optional[float],
    v24: Optional[float],
    peer_v0: Optional[Sequence[float]] = None,
    peer_v24: Optional[Sequence[float]] = None,
    safety_config: Optional[SafetyConfig] = None,
) -> ModuleBOutput:
    """Evaluate frozen Module B forecaster on a single parameter time series.
    
    Hardened for all corrupt/missing/boundary edge cases:
    - Missing 0h, 24h, or both
    - Non-finite (NaN, Inf) values
    - Unknown or mismatched parameters
    - Extreme finite values (divergence policy)
    - Exact regime threshold equality
    - Zero, positive, and negative drift
    """
    unit = CANONICAL_UNITS.get(parameter_name, "")

    # 1. Parameter validation
    if parameter_name not in CANONICAL_PARAMETERS:
        return create_insufficient_data_output(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            reason=f"Unknown electrical parameter '{parameter_name}'. Must be one of {list(CANONICAL_PARAMETERS)}.",
            unit=unit,
        )

    # 2. Check measurement presence
    if v0 is None and v24 is None:
        return create_insufficient_data_output(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            reason="Missing both 0h baseline and 24h intermediate observations",
            unit=unit,
        )
    if v0 is None:
        return create_insufficient_data_output(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            reason="Missing 0h baseline observation required for drift reference",
            unit=unit,
        )
    if v24 is None:
        return create_insufficient_data_output(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            reason="Missing 24h intermediate observation required for prognostics",
            unit=unit,
        )

    # 3. Check finiteness
    try:
        v0_f = float(v0)
        v24_f = float(v24)
    except (ValueError, TypeError) as e:
        return create_insufficient_data_output(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            reason=f"Malformed measurement value: {e}",
            unit=unit,
        )

    if not math.isfinite(v0_f) or not math.isfinite(v24_f):
        return create_insufficient_data_output(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            reason="Measurement contains non-finite value (NaN or Inf)",
            unit=unit,
        )

    # 4. Physical boundary check (Resistance and IDSS must be strictly positive)
    if parameter_name in ("RDS(on)", "IDSS") and (v0_f <= 0.0 or v24_f <= 0.0):
        return create_insufficient_data_output(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            reason=f"Physical parameter {parameter_name} requires positive readings (v0={v0_f}, v24={v24_f})",
            unit=unit,
        )

    # 5. Transform to canonical representation space
    try:
        u0 = transform_parameter(parameter_name, v0_f)
        u24 = transform_parameter(parameter_name, v24_f)
    except Exception as e:
        return create_insufficient_data_output(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            reason=f"Transform error: {e}",
            unit=unit,
        )

    # Divergence guard on early representations
    if abs(u0) > 10.0 or abs(u24) > 10.0:
        return create_insufficient_data_output(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=parameter_name,
            reason="Extreme representation magnitude (|u| > 10.0) violates numerical bounds",
            unit=unit,
        )

    # 6. Extract component & lot drift features
    comp_drift = u24 - u0
    floor = get_noise_floor(parameter_name)

    # Compute LOO peer context
    if peer_v0 is not None and peer_v24 is not None and len(peer_v0) > 0 and len(peer_v0) == len(peer_v24):
        valid_peer_u0 = []
        valid_peer_u24 = []
        for pv0, pv24 in zip(peer_v0, peer_v24):
            if pv0 is not None and pv24 is not None and math.isfinite(pv0) and math.isfinite(pv24):
                if parameter_name in ("RDS(on)", "IDSS") and (pv0 <= 0 or pv24 <= 0):
                    continue
                try:
                    pu0 = transform_parameter(parameter_name, float(pv0))
                    pu24 = transform_parameter(parameter_name, float(pv24))
                    if math.isfinite(pu0) and math.isfinite(pu24) and abs(pu0) <= 10.0 and abs(pu24) <= 10.0:
                        valid_peer_u0.append(pu0)
                        valid_peer_u24.append(pu24)
                except Exception:
                    continue

        if len(valid_peer_u0) >= 1:
            loo_med_0h = float(np.median(valid_peer_u0))
            loo_med_24h = float(np.median(valid_peer_u24))
            lot_drift = loo_med_24h - loo_med_0h
            excess_drift = comp_drift - lot_drift
        else:
            loo_med_0h = u0
            loo_med_24h = u24
            lot_drift = 0.0
            excess_drift = comp_drift
    else:
        loo_med_0h = u0
        loo_med_24h = u24
        lot_drift = 0.0
        excess_drift = comp_drift

    # 7. Model evaluation
    models = get_frozen_production_models()
    model = models[parameter_name]

    features_dict = {
        "u24": u24,
        "v24": v24_f,
        "component_drift": comp_drift,
        "lot_drift": lot_drift,
        "excess_drift": excess_drift,
    }

    res_za = model.predict_single(features_dict)
    regime = res_za["regime"]
    pred_phys = float(res_za["predicted_physical"])
    u168_pred = float(res_za["predicted_u168"])
    delta_pred = float(res_za["predicted_delta"])
    is_divergent = bool(res_za["is_divergent"])

    # 8. Apply regime-conditioned conformal calibration quantiles
    quantiles = FROZEN_CONFORMAL_QUANTILES[parameter_name][regime]
    q90 = quantiles["q90"]
    q95 = quantiles["q95"]

    low_u_90 = u168_pred - q90
    high_u_90 = u168_pred + q90
    low_u_95 = u168_pred - q95
    high_u_95 = u168_pred + q95

    # Inverse transform intervals to physical units
    try:
        low_phys_90 = inverse_transform_parameter(parameter_name, low_u_90)
        high_phys_90 = inverse_transform_parameter(parameter_name, high_u_90)
        low_phys_95 = inverse_transform_parameter(parameter_name, low_u_95)
        high_phys_95 = inverse_transform_parameter(parameter_name, high_u_95)
    except Exception:
        # Fallback to v24 bounds on transform failure
        low_phys_90 = v24_f
        high_phys_90 = v24_f
        low_phys_95 = v24_f
        high_phys_95 = v24_f

    # Physical clamping: IDSS and RDS(on) can never be negative
    if parameter_name in ("RDS(on)", "IDSS"):
        low_phys_90 = max(0.0, low_phys_90)
        high_phys_90 = max(0.0, high_phys_90)
        low_phys_95 = max(0.0, low_phys_95)
        high_phys_95 = max(0.0, high_phys_95)
        pred_phys = max(0.0, pred_phys)

    # Uncertainty widths
    w90 = float(high_phys_90 - low_phys_90)
    w95 = float(high_phys_95 - low_phys_95)

    # 9. Threshold comparisons (including 60 mOhm & 65 mOhm for RDS(on))
    crosses_60, below_60, above_60 = False, False, False
    crosses_65, below_65, above_65 = False, False, False
    threshold_proximity: Dict[str, float] = {}

    if parameter_name == "RDS(on)":
        if high_phys_90 < 60.0:
            below_60 = True
        elif low_phys_90 > 60.0:
            above_60 = True
        else:
            crosses_60 = True

        if high_phys_90 < 65.0:
            below_65 = True
        elif low_phys_90 > 65.0:
            above_65 = True
        else:
            crosses_65 = True

        threshold_proximity["margin_to_60mOhm"] = float(60.0 - pred_phys)
        threshold_proximity["margin_to_65mOhm"] = float(65.0 - pred_phys)
        threshold_proximity["upper_90_margin_to_60mOhm"] = float(60.0 - high_phys_90)
        threshold_proximity["upper_90_margin_to_65mOhm"] = float(65.0 - high_phys_95)

    # 10. Safety-slope decision-support integration
    if safety_config is None:
        safety_config = SafetyConfig.default()
    safety_evaluator = SafetySlopeEvaluator(config=safety_config)
    safety_res = safety_evaluator.evaluate_single(
        component_id=component_id,
        parameter_name=parameter_name,
        value_24h=v24_f,
        predicted_value_168h=pred_phys,
        model_id=f"ZA_RESIDUAL_HISTGBM_{parameter_name}",
        upstream_disposition="PREDICTED",
        lower_bound=low_phys_90,
        upper_bound=high_phys_90,
    )

    safety_slope = safety_res.safety_slope
    safety_drift_rate = safety_res.predicted_drift_rate
    safety_threshold = safety_res.safety_threshold

    # 11. Determine QA advisory status
    # Rules:
    # 1. Crossing or exceeding threshold produces EARLY_WARNING.
    # 2. Entirely below threshold can produce CONTINUE where safety slope is satisfied.
    # 3. Insufficient data handled upstream (never reaches here as CONTINUE).
    advisory_status = ModuleBAdvisoryStatus.CONTINUE
    advisory_reasons = []

    if parameter_name == "RDS(on)":
        if crosses_60:
            advisory_status = ModuleBAdvisoryStatus.EARLY_WARNING
            advisory_reasons.append("90% prediction interval crosses the 60.0 mOhm screening margin.")
        elif above_60:
            advisory_status = ModuleBAdvisoryStatus.EARLY_WARNING
            advisory_reasons.append("Predicted trajectory is entirely above the 60.0 mOhm screening margin.")

        if crosses_65:
            advisory_status = ModuleBAdvisoryStatus.EARLY_WARNING
            advisory_reasons.append("90% prediction interval crosses the 65.0 mOhm specification ceiling.")
        elif above_65:
            advisory_status = ModuleBAdvisoryStatus.EARLY_WARNING
            advisory_reasons.append("Predicted trajectory is entirely above the 65.0 mOhm specification ceiling.")

    if safety_res.decision == SafetyDecision.EARLY_REJECT:
        advisory_status = ModuleBAdvisoryStatus.EARLY_WARNING
        advisory_reasons.append(
            f"Predicted drift rate ({safety_drift_rate:+.6f} {unit}/h) breaches calculated safety slope "
            f"({safety_slope:+.6f} {unit}/h) toward {safety_res.evaluated_direction} threshold ({safety_threshold:.2f} {unit})."
        )
    elif safety_res.interval_status == IntervalSafetyStatus.BOUNDARY_CROSSED:
        advisory_status = ModuleBAdvisoryStatus.EARLY_WARNING
        advisory_reasons.append(
            f"90% prediction interval [{low_phys_90:.3f}, {high_phys_90:.3f}] {unit} crosses safety boundary ({safety_threshold:.2f} {unit})."
        )

    if not advisory_reasons:
        advisory_reasons.append(
            f"Predicted 168h trajectory ({pred_phys:.3f} {unit}) and 90% interval [{low_phys_90:.3f}, {high_phys_90:.3f}] {unit} "
            f"remain within nominal margins (margin to safety threshold: {safety_res.margin_to_safety_threshold:.3f} {unit})."
        )

    # 12. Build structured QA explainability object
    thresh_p = FROZEN_REGIME_THRESHOLDS[parameter_name]
    if regime == "ZERO_ANCHORED":
        regime_exp = (
            f"ZERO_ANCHORED regime selected because absolute 24h excess drift "
            f"({abs(excess_drift):.6f}) is within training-derived threshold tau_p ({thresh_p:.6f})."
        )
    else:
        regime_exp = (
            f"DRIFT_MODEL regime selected because absolute 24h excess drift "
            f"({abs(excess_drift):.6f}) exceeded training-derived threshold tau_p ({thresh_p:.6f})."
        )

    explanation = ModuleBExplanation(
        early_drift_signal=comp_drift,
        excess_drift=excess_drift,
        selected_regime=regime,
        predicted_168h_value=pred_phys,
        uncertainty_interval_90=(low_phys_90, high_phys_90),
        uncertainty_interval_95=(low_phys_95, high_phys_95),
        threshold_proximity=threshold_proximity,
        reason_for_advisory_status=f"{regime_exp} Advisory status: {advisory_status.value}. {' '.join(advisory_reasons)}",
        details={
            "delta_transformed": delta_pred,
            "u168_transformed": u168_pred,
            "q90_conformal": q90,
            "q95_conformal": q95,
            "is_divergent": is_divergent,
            "safety_res": safety_res.to_dict(),
        },
    )

    return ModuleBOutput(
        component_id=component_id,
        lot_id=lot_id,
        parameter_name=parameter_name,
        predicted_value=pred_phys,
        lower_90=low_phys_90,
        upper_90=high_phys_90,
        lower_95=low_phys_95,
        upper_95=high_phys_95,
        regime=regime,
        uncertainty_width_90=w90,
        uncertainty_width_95=w95,
        crosses_60=crosses_60,
        entirely_below_60=below_60,
        entirely_above_60=above_60,
        crosses_65=crosses_65,
        entirely_below_65=below_65,
        entirely_above_65=above_65,
        advisory_status=advisory_status,
        explanation=explanation,
        unit=unit,
        is_valid=True,
        refusal_reason=None,
        predicted_drift_rate=safety_drift_rate,
        safety_slope=safety_slope,
        safety_threshold=safety_threshold,
    )


# ============================================================
# Telemetry Batch & Component Evaluators
# ============================================================

def evaluate_module_b_component(
    telemetry: pd.DataFrame,
    component_id: str,
    lot_telemetry: Optional[pd.DataFrame] = None,
    as_of_hours: int = 24,
    safety_config: Optional[SafetyConfig] = None,
) -> Dict[str, ModuleBOutput]:
    """Evaluate Module B outputs across all 4 parameters for a component from telemetry DataFrame."""
    as_of_df = telemetry[telemetry["elapsed_hours"] <= as_of_hours].copy()
    comp_df = as_of_df[as_of_df["component_id"] == component_id]

    if comp_df.empty:
        return {
            p: create_insufficient_data_output(
                component_id=component_id,
                lot_id="UNKNOWN",
                parameter_name=p,
                reason=f"No telemetry observations found for component '{component_id}' at or before {as_of_hours}h.",
            )
            for p in CANONICAL_PARAMETERS
        }

    lot_id = str(comp_df["lot_id"].iloc[0])

    # Lot context assembly
    if lot_telemetry is not None:
        lot_as_of = lot_telemetry[lot_telemetry["elapsed_hours"] <= as_of_hours].copy()
        lot_df = pd.concat([as_of_df, lot_as_of], ignore_index=True)
    else:
        lot_df = as_of_df.copy()

    # Deduplicate observations
    comp_df = comp_df.drop_duplicates(subset=["parameter_name", "elapsed_hours"], keep="last")
    lot_df = lot_df.drop_duplicates(subset=["component_id", "parameter_name", "elapsed_hours"], keep="last")

    results: Dict[str, ModuleBOutput] = {}

    for param in CANONICAL_PARAMETERS:
        p_comp = comp_df[comp_df["parameter_name"] == param]
        t0_row = p_comp[p_comp["elapsed_hours"] == 0]
        t24_row = p_comp[p_comp["elapsed_hours"] == 24]

        v0 = float(t0_row["value"].iloc[-1]) if not t0_row.empty else None
        v24 = float(t24_row["value"].iloc[-1]) if not t24_row.empty else None

        # Gather peers (excluding current component)
        peer_df = lot_df[(lot_df["parameter_name"] == param) & (lot_df["component_id"] != component_id)]
        p0 = peer_df[peer_df["elapsed_hours"] == 0].groupby("component_id")["value"].last()
        p24 = peer_df[peer_df["elapsed_hours"] == 24].groupby("component_id")["value"].last()
        common_peers = p0.index.intersection(p24.index)

        peer_v0 = p0.loc[common_peers].tolist() if len(common_peers) > 0 else None
        peer_v24 = p24.loc[common_peers].tolist() if len(common_peers) > 0 else None

        res = predict_module_b_series(
            component_id=component_id,
            lot_id=lot_id,
            parameter_name=param,
            v0=v0,
            v24=v24,
            peer_v0=peer_v0,
            peer_v24=peer_v24,
            safety_config=safety_config,
        )
        results[param] = res

    return results


# ============================================================
# Module A & Module B Interface (PART D)
# ============================================================

def integrate_module_a_and_module_b(
    screening_result: Optional[ComponentScreeningResult],
    module_b_outputs: Dict[str, ModuleBOutput],
    component_id: str,
    lot_id: str,
    as_of_hours: int = 24,
) -> UnifiedPipelineEvidence:
    """Interface between Module A and Module B preserving evidence from both.
    
    CRITICAL ARCHITECTURAL CONTRACT:
    1. Module A screening state (PASS, ALERT, FAIL, EQUIPMENT_SUSPECTED, INSUFFICIENT_DATA)
       is fully preserved and NEVER overwritten by Module B forecasts.
    2. Module B forecasts, conformal intervals, and QA advisory statuses are fully
       preserved and NEVER overwritten by Module A screening disposition.
    3. If Module A reports equipment / chamber excursions, Module B prognostic
       evidence remains accessible while flagging equipment confounding in the unified record.
    4. Neither module grants autonomous scrapping authority; all dispositions are
       governed decision support for human engineering review.
    """
    preservation_notes: List[str] = []

    # 1. Inspect Module A Evidence
    scr_dict: Optional[Dict[str, Any]] = None
    if screening_result is not None:
        scr_dict = screening_result.to_dict()
        scr_state = screening_result.final_state.value
        preservation_notes.append(
            f"Module A screening disposition preserved: {scr_state} "
            f"(qualifier: {screening_result.disposition_qualifier.value}, "
            f"reason_code: {screening_result.primary_reason_code})."
        )
        if scr_state == "EQUIPMENT_SUSPECTED":
            preservation_notes.append(
                "Module A detected equipment/chamber excursion. Module B prognostics are calculated "
                "for engineering context but marked as potentially confounded by chamber state."
            )
    else:
        preservation_notes.append("Module A screening evidence absent. Module B evaluated independently.")

    # 2. Inspect Module B Evidence
    mb_dict = {p: out.to_dict() for p, out in module_b_outputs.items()}
    any_warning = any(out.advisory_status == ModuleBAdvisoryStatus.EARLY_WARNING for out in module_b_outputs.values())
    any_insufficient = any(out.advisory_status == ModuleBAdvisoryStatus.INSUFFICIENT_DATA for out in module_b_outputs.values())

    if any_warning:
        preservation_notes.append("Module B emitted EARLY_WARNING advisory on one or more parameters.")
    elif any_insufficient:
        preservation_notes.append("Module B flagged INSUFFICIENT_DATA on one or more parameters.")
    else:
        preservation_notes.append("Module B emitted CONTINUE advisory across all evaluated parameters.")

    # 3. Derive unified QA advisory
    # Transparent synthesis for human engineering review
    if screening_result is not None and screening_result.final_state.value in ("FAIL", "ALERT"):
        unified_advisory = f"SCREENING_{screening_result.final_state.value}_WITH_PROGNOSTIC_CONTEXT"
    elif screening_result is not None and screening_result.final_state.value == "EQUIPMENT_SUSPECTED":
        unified_advisory = "EQUIPMENT_INVESTIGATION_REQUIRED"
    elif any_warning:
        unified_advisory = "PROGNOSTIC_EARLY_WARNING"
    elif any_insufficient:
        unified_advisory = "INSUFFICIENT_TELEMETRY"
    else:
        unified_advisory = "NOMINAL_CONTINUE"

    return UnifiedPipelineEvidence(
        component_id=component_id,
        lot_id=lot_id,
        as_of_hours=as_of_hours,
        module_a_screening=scr_dict,
        module_b_prognostics=mb_dict,
        unified_advisory=unified_advisory,
        preservation_notes=preservation_notes,
    )
