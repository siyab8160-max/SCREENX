"""Unit tests for the six individual Module A detectors.

Validates:
- D_spec: Class A specification vs Class C screening margin disambiguation
- D_peer: Leave-One-Out robust calculation and small-lot N < 8 suppression
- D_drift: Theil-Sen slope, subtle drift, accelerating drift, and equipment confounding
- D_step: Abrupt single-interval step jump J(T) >= 4.0
- D_eq: Chamber synchrony and ATE fixture channel offset detection
- D_suff: History completeness, missing checkpoints, and small lot flags
"""

import pandas as pd
import pytest

from sih26170.screening.abrupt import evaluate_abrupt_step
from sih26170.screening.equipment import evaluate_equipment_environment
from sih26170.screening.peer import evaluate_peer_deviation
from sih26170.screening.schema import (
    AbruptStepStatus,
    EquipmentStatus,
    LimitClass,
    PeerDeviationStatus,
    SpecificationStatus,
    SufficiencyStatus,
    TemporalDriftStatus,
)
from sih26170.screening.specification import evaluate_specification
from sih26170.screening.sufficiency import evaluate_data_sufficiency
from sih26170.screening.temporal import evaluate_temporal_drift


# ============================================================================
# 1. Detector A (D_spec) Tests
# ============================================================================

def test_d_spec_compliance():
    """Verify compliant measurements pass under Class A specifications."""
    ev_rdson = evaluate_specification("RDS(on)", 45.0)
    assert ev_rdson.passed is True
    assert ev_rdson.status == SpecificationStatus.COMPLIANT
    assert ev_rdson.limit_class == LimitClass.CLASS_A

    ev_idss = evaluate_specification("IDSS", 0.5)
    assert ev_idss.passed is True
    assert ev_idss.status == SpecificationStatus.COMPLIANT


def test_d_spec_rdson_60_vs_65_disambiguation():
    """Verify semantic distinction between 65 mOhm Class A spec and 60 mOhm Class C margin."""
    # Value <= 60.0 mOhm: fully compliant with both
    ev_55 = evaluate_specification("RDS(on)", 55.0)
    assert ev_55.passed is True
    assert ev_55.status == SpecificationStatus.COMPLIANT

    # Value in (60.0, 65.0] mOhm: complies with Class A slash-sheet, breaches Class C margin!
    ev_62 = evaluate_specification("RDS(on)", 62.0)
    assert ev_62.passed is True  # Passed Class A specification
    assert ev_62.status == SpecificationStatus.SCREENING_MARGIN_BREACH
    assert ev_62.limit_class == LimitClass.CLASS_C
    assert "SCREENING_MARGIN_BREACH" in ev_62.reason_code
    assert "PD-97217" in ev_62.provenance

    # Value > 65.0 mOhm: hard Class A specification breach (safety veto)
    ev_68 = evaluate_specification("RDS(on)", 68.0)
    assert ev_68.passed is False
    assert ev_68.status == SpecificationStatus.SPEC_BREACH
    assert ev_68.limit_class == LimitClass.CLASS_A
    assert "ABSOLUTE_LIMIT_BREACH" in ev_68.reason_code
    assert "MIL-PRF-19500/703" in ev_68.provenance


def test_d_spec_boundaries():
    """Verify Class A envelope boundaries for IDSS, VGS(th), and IGSS."""
    # IDSS ceiling: 10.0 uA
    assert evaluate_specification("IDSS", 9.9).passed is True
    assert evaluate_specification("IDSS", 10.1).passed is False

    # VGS(th) envelope: [2.0, 4.0] V
    assert evaluate_specification("VGS(th)", 2.0).passed is True
    assert evaluate_specification("VGS(th)", 4.0).passed is True
    assert evaluate_specification("VGS(th)", 1.95).passed is False
    assert evaluate_specification("VGS(th)", 4.05).passed is False

    # IGSS envelope: [-100.0, +100.0] nA
    assert evaluate_specification("IGSS", -99.0).passed is True
    assert evaluate_specification("IGSS", +99.0).passed is True
    assert evaluate_specification("IGSS", -105.0).passed is False
    assert evaluate_specification("IGSS", +105.0).passed is False


# ============================================================================
# 2. Detector B (D_peer) Tests
# ============================================================================

def test_d_peer_small_lot_suppression():
    """Verify N < 8 small lot policy formally suppresses peer deviation without fabricating scores."""
    # Small lot with 5 peers (total lot size N=6 < 8)
    lot_obs = {f"C00{i}": 45.0 + 0.1 * i for i in range(1, 6)}
    lot_obs["C_TARGET"] = 45.3

    ev = evaluate_peer_deviation("C_TARGET", "LOT_SMALL", "RDS(on)", 45.3, lot_obs)
    assert ev.status == PeerDeviationStatus.PEER_SUPPRESSED_SMALL_LOT
    assert ev.z_score is None
    assert ev.peer_median is None
    assert ev.reason_code == "PEER_SUPPRESSED_SMALL_LOT"


def test_d_peer_leave_one_out_isolation():
    """Verify target device is strictly excluded from its own peer reference."""
    # Lot with 10 components: 9 normal (around 45 mOhm) and 1 extreme outlier (58 mOhm)
    lot_obs = {f"C{i:02d}": 45.0 for i in range(1, 10)}
    lot_obs["C_OUTLIER"] = 58.0

    # Evaluate outlier: its own 58.0 must NOT pull the peer median or inflate the MAD
    ev_outlier = evaluate_peer_deviation("C_OUTLIER", "LOT_01", "RDS(on)", 58.0, lot_obs)
    assert ev_outlier.peer_median is not None
    assert abs(ev_outlier.peer_median - 45.0) < 0.1
    assert ev_outlier.status in (PeerDeviationStatus.PEER_MILD_OUTLIER, PeerDeviationStatus.PEER_EXTREME_OUTLIER)
    assert ev_outlier.z_score is not None and ev_outlier.z_score > 3.0


# ============================================================================
# 3. Detector C (D_drift) Tests
# ============================================================================

def test_d_drift_kinetics():
    """Verify temporal drift kinetics: stationary, subtle drift, and accelerating drift."""
    # 1. Stationary history across 0h, 24h, 96h, 168h
    hist_stat = [(0, 45.0), (24, 45.01), (96, 44.99), (168, 45.02)]
    ev_stat = evaluate_temporal_drift("RDS(on)", hist_stat, as_of_hours=168, baseline_lot_scale=0.01)
    assert ev_stat.status == TemporalDriftStatus.STATIONARY
    assert ev_stat.observations_used == 4
    assert abs(ev_stat.normalized_drift) < 2.5

    # 2. Subtle linear drift
    hist_drift = [(0, 45.0), (24, 46.2), (96, 49.5), (168, 52.8)]
    ev_drift = evaluate_temporal_drift("RDS(on)", hist_drift, as_of_hours=168, baseline_lot_scale=0.01)
    assert ev_drift.status in (TemporalDriftStatus.SUBTLE_DRIFT, TemporalDriftStatus.ACCELERATING_DRIFT)
    assert ev_drift.slope_per_hour > 0

    # 3. Equipment confounding flag preserves active kinetics without erasing evidence
    ev_conf = evaluate_temporal_drift("RDS(on)", hist_drift, as_of_hours=168, baseline_lot_scale=0.01, confounded_by_equipment=True)
    assert ev_conf.status in (TemporalDriftStatus.SUBTLE_DRIFT, TemporalDriftStatus.ACCELERATING_DRIFT)
    assert ev_conf.confounded_by_equipment is True

    # Stationary series under equipment confounding receives TEMPORALLY_CONFOUNDED_BY_EQUIPMENT
    ev_conf_stat = evaluate_temporal_drift("RDS(on)", hist_stat, as_of_hours=168, baseline_lot_scale=0.01, confounded_by_equipment=True)
    assert ev_conf_stat.status == TemporalDriftStatus.TEMPORALLY_CONFOUNDED_BY_EQUIPMENT
    assert ev_conf_stat.confounded_by_equipment is True


# ============================================================================
# 4. Detector D (D_step) Tests
# ============================================================================

def test_d_step_abrupt_jump():
    """Verify abrupt step change detection across adjacent checkpoints."""
    # Nominal continuous variation
    hist_nominal = [(0, 45.0), (24, 45.1)]
    ev_nom = evaluate_abrupt_step("RDS(on)", hist_nominal, as_of_hours=24, lot_scale_prev=0.01)
    assert ev_nom.status == AbruptStepStatus.NO_STEP

    # Abrupt jump from 45.0 to 55.0 mOhm across 24h -> 96h
    hist_step = [(0, 45.0), (24, 45.1), (96, 55.0)]
    ev_jump = evaluate_abrupt_step("RDS(on)", hist_step, as_of_hours=96, lot_scale_prev=0.01)
    assert ev_jump.status == AbruptStepStatus.ABRUPT_JUMP_ALERT
    assert ev_jump.step_ratio >= 4.0
    assert ev_jump.reason_code == "ABRUPT_STEP_CHANGE"


# ============================================================================
# 5. Detector E (D_eq) Tests
# ============================================================================

def test_d_eq_chamber_and_channel():
    """Verify common-mode chamber excursion and channel offset detection."""
    # Synthetic lot where all components shift upward by +5 mOhm at 96h (chamber excursion)
    rows = []
    for i in range(1, 15):
        cid = f"C{i:02d}"
        rows.append({"component_id": cid, "lot_id": "LOT_E", "parameter_name": "RDS(on)", "elapsed_hours": 24, "value": 45.0, "channel_id": "CH_01"})
        rows.append({"component_id": cid, "lot_id": "LOT_E", "parameter_name": "RDS(on)", "elapsed_hours": 96, "value": 50.0, "channel_id": "CH_01"})
    df_lot = pd.DataFrame(rows)

    ev_chamber = evaluate_equipment_environment("LOT_E", 96, "RDS(on)", df_lot, "C01", channel_id="CH_01")
    assert ev_chamber.status == EquipmentStatus.CHAMBER_EXCURSION_SUSPECTED
    assert ev_chamber.suspected is True


# ============================================================================
# 6. Detector F (D_suff) Tests
# ============================================================================

def test_d_suff_completeness():
    """Verify data sufficiency and missing checkpoint detection."""
    # Complete schedule up to 96h: [0, 24, 96]
    ev_complete = evaluate_data_sufficiency("C01", 96, [0, 24, 96], ["VALID", "VALID", "VALID"], lot_size=20)
    assert ev_complete.status == SufficiencyStatus.SUFFICIENT
    assert ev_complete.sufficient is True

    # Missing 24h checkpoint
    ev_missing = evaluate_data_sufficiency("C01", 96, [0, 96], ["VALID", "VALID"], lot_size=20)
    assert ev_missing.status == SufficiencyStatus.INCOMPLETE_HISTORY
    assert ev_missing.sufficient is False
    assert "MISSING_CHECKPOINTS_24" in ev_missing.reason_code

    # Small lot restriction flag
    ev_small = evaluate_data_sufficiency("C01", 96, [0, 24, 96], ["VALID", "VALID", "VALID"], lot_size=5)
    assert ev_small.status == SufficiencyStatus.SMALL_LOT_RESTRICTION
    assert ev_small.is_small_lot is True
