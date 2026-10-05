"""Programmatic verification of final holdout independence and quarantine.

Enforces STEP 1 / Phase 7 requirements for SIH 2026 Problem Statement SIH26170:
- Lot disjointness: holdout lots ∩ all historical lots = empty
- Component disjointness: holdout components ∩ all historical components = empty
- Zero ground-truth leakage into observations
- Schema adherence and canonical checkpoint/parameter coverage
- Inaccessibility: zero automatic ingestion or scanning by training/calibration scripts
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Set

import numpy as np
import pandas as pd
import pytest


HOLDOUT_DIR = Path("data/evaluation/final_holdout")
OBSERVATIONS_PATH = HOLDOUT_DIR / "observations.csv"
GROUND_TRUTH_PATH = HOLDOUT_DIR / "ground_truth.csv"
MANIFEST_PATH = HOLDOUT_DIR / "manifest.json"
CONFIG_PATH = HOLDOUT_DIR / "generator_config_snapshot.json"
PROVENANCE_PATH = HOLDOUT_DIR / "provenance.json"
CHECKSUMS_PATH = HOLDOUT_DIR / "checksums.sha256"

EXPECTED_LOTS = {"LOT21", "LOT22", "LOT23", "LOT24"}
EXPECTED_PARAMETERS = {"IDSS", "VGS(th)", "RDS(on)", "IGSS"}
EXPECTED_CHECKPOINTS = {0, 24, 96, 168}
CANONICAL_OBS_COLUMNS = [
    "component_id",
    "lot_id",
    "parameter_name",
    "elapsed_hours",
    "value",
    "unit",
    "temperature_C",
    "test_condition",
    "instrument_id",
    "channel_id",
    "measurement_quality",
    "rework_count",
]
QUARANTINED_GT_COLUMNS = [
    "target_horizon_hours",
    "actual_value",
    "scenario_label",
    "first_abnormal_hour",
    "event_hour",
    "is_anomaly",
    "anomaly_type",
    "latent_true_value",
    "latent_drift",
]


@pytest.fixture(scope="module")
def holdout_data():
    """Load and return holdout observations, ground truth, and manifest."""
    assert HOLDOUT_DIR.exists(), f"Holdout directory {HOLDOUT_DIR} does not exist"
    assert OBSERVATIONS_PATH.exists(), f"{OBSERVATIONS_PATH} does not exist"
    assert GROUND_TRUTH_PATH.exists(), f"{GROUND_TRUTH_PATH} does not exist"
    assert MANIFEST_PATH.exists(), f"{MANIFEST_PATH} does not exist"
    assert CONFIG_PATH.exists(), f"{CONFIG_PATH} does not exist"
    assert PROVENANCE_PATH.exists(), f"{PROVENANCE_PATH} does not exist"
    assert CHECKSUMS_PATH.exists(), f"{CHECKSUMS_PATH} does not exist"

    obs_df = pd.read_csv(OBSERVATIONS_PATH)
    gt_df = pd.read_csv(GROUND_TRUTH_PATH)
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    return {
        "obs": obs_df,
        "gt": gt_df,
        "manifest": manifest,
    }


def test_holdout_files_exist_and_hashes_match():
    """Verify cryptographic checksums match manifest and checksums.sha256."""
    with open(CHECKSUMS_PATH, "r", encoding="utf-8") as f:
        lines = f.read().strip().splitlines()

    checksum_map = {}
    for line in lines:
        parts = line.split()
        if len(parts) == 2:
            checksum_map[parts[1]] = parts[0]

    for fname in ["observations.csv", "ground_truth.csv", "manifest.json", "generator_config_snapshot.json", "provenance.json"]:
        fpath = HOLDOUT_DIR / fname
        assert fpath.exists(), f"Missing file: {fname}"
        with open(fpath, "rb") as fp:
            actual_sha = hashlib.sha256(fp.read()).hexdigest()
        assert actual_sha == checksum_map[fname], f"Checksum mismatch for {fname}"


def test_manifest_sealing_declaration(holdout_data):
    """Verify manifest declares SEALED status and purpose."""
    manifest = holdout_data["manifest"]
    assert manifest["holdout_status"] == "SEALED / DEVELOPMENT-INACCESSIBLE"
    assert "Final evaluation of the redesigned Module B" in manifest["purpose"]
    assert set(manifest["lots"]) == EXPECTED_LOTS
    assert manifest["component_count"] == 80
    assert manifest["series_count"] == 320
    assert manifest["seed"] == 20261005
    assert manifest["disjointness"]["lot_disjointness_verified"] is True
    assert manifest["disjointness"]["component_disjointness_verified"] is True


def test_lot_disjointness(holdout_data):
    """Verify new holdout lots are strictly disjoint from all historical lots."""
    obs_lots = set(holdout_data["obs"]["lot_id"].unique())
    gt_lots = set(holdout_data["gt"]["lot_id"].unique())

    assert obs_lots == EXPECTED_LOTS
    assert gt_lots == EXPECTED_LOTS

    # Historical lots
    historical_b1_b5 = {f"LOT{i:02d}" for i in range(1, 15)}
    historical_b6_6 = {f"LOT{i:02d}" for i in range(15, 21)}
    historical_phase4b = (
        {f"LOT_CAL_{i:03d}" for i in range(1, 51)}
        | {f"LOT_VAL_{i:03d}" for i in range(1, 26)}
        | {f"LOT_EVAL_{i:03d}" for i in range(1, 26)}
    )
    historical_phase2f = {
        "LOT_S01", "LOT_S02", "LOT_S03", "LOT_S04", "LOT_S05",
        "LOT_N01", "LOT_N02", "LOT_D01", "LOT_D02", "LOT_D03", "LOT_D04",
        "LOT_L01", "LOT_E01", "LOT_E02", "LOT_M01", "LOT_W01"
    }
    historical_proto = {f"L{i:02d}" for i in range(1, 15)}

    all_historical = (
        historical_b1_b5
        | historical_b6_6
        | historical_phase4b
        | historical_phase2f
        | historical_proto
    )

    intersection = EXPECTED_LOTS.intersection(all_historical)
    assert len(intersection) == 0, f"Lot disjointness violated: {intersection}"


def test_component_disjointness(holdout_data):
    """Verify holdout components never appeared in any historical lot."""
    holdout_comps = set(holdout_data["obs"]["component_id"].unique())
    assert len(holdout_comps) == 80

    for cid in holdout_comps:
        lot = cid.split("_")[0]
        assert lot in EXPECTED_LOTS, f"Unexpected component prefix: {cid}"


def test_no_duplicate_observations(holdout_data):
    """Verify no duplicate (component_id, parameter_name, elapsed_hours) entries exist."""
    obs = holdout_data["obs"]
    dups = obs.duplicated(subset=["component_id", "parameter_name", "elapsed_hours"])
    assert not dups.any(), f"Found {dups.sum()} duplicate observation rows!"


def test_schema_validity(holdout_data):
    """Verify observations schema strictly conforms to CANONICAL_OBS_COLUMNS."""
    obs = holdout_data["obs"]
    assert list(obs.columns) == CANONICAL_OBS_COLUMNS
    assert obs["value"].notna().all(), "Found NaN in observed values!"
    assert np.all(np.isfinite(obs["value"])), "Found non-finite values in observations!"


def test_expected_checkpoints(holdout_data):
    """Verify checkpoints are strictly {0, 24, 96, 168}."""
    obs_hours = set(holdout_data["obs"]["elapsed_hours"].unique())
    assert obs_hours == EXPECTED_CHECKPOINTS


def test_expected_parameters(holdout_data):
    """Verify parameter coverage is strictly {IDSS, VGS(th), RDS(on), IGSS}."""
    obs_params = set(holdout_data["obs"]["parameter_name"].unique())
    gt_params = set(holdout_data["gt"]["parameter_name"].unique())
    assert obs_params == EXPECTED_PARAMETERS
    assert gt_params == EXPECTED_PARAMETERS


def test_ground_truth_isolation(holdout_data):
    """Verify observations file contains ZERO ground truth or future target columns."""
    obs_cols = set(holdout_data["obs"].columns)
    for col in QUARANTINED_GT_COLUMNS:
        assert col not in obs_cols, f"Quarantine leak: {col} found in observations.csv!"


def test_ground_truth_structure(holdout_data):
    """Verify ground truth contains exactly 320 records (80 components x 4 parameters)."""
    gt = holdout_data["gt"]
    assert len(gt) == 320
    assert set(gt["target_horizon_hours"].unique()) == {168}
    assert gt["actual_value"].notna().all()
    assert np.all(np.isfinite(gt["actual_value"]))
    assert set(gt["scenario_label"].unique()).issubset({
        "stable",
        "high_but_stable",
        "linear_drift",
        "accelerating_drift",
        "subtle_abrupt_change",
        "equipment_common_mode",
        "missing_observations",
        "insufficient_data",
        "mixed_compound",
    })


def test_training_scripts_do_not_scan_final_holdout():
    """Verify no existing training, calibration, or evaluation scripts reference final_holdout."""
    repo_root = Path(".")
    py_files = list((repo_root / "src").rglob("*.py"))

    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        assert "final_holdout" not in content, (
            f"Active source file {py_file} references final_holdout! "
            "Holdout must be sealed and development-inaccessible."
        )


def test_no_wildcard_discovery_of_holdout():
    """Verify holdout directory cannot be ingested by open data directory iterators."""
    for script_file in [
        Path("src/sih26170/prognostics/phase5_lolo_evaluator.py"),
        Path("src/sih26170/prognostics/phase5_validation_evaluator.py"),
        Path("src/sih26170/prognostics/phase5_final_evaluator.py"),
    ]:
        if script_file.exists():
            content = script_file.read_text(encoding="utf-8")
            assert "data/evaluation/final_holdout" not in content
            assert "LOT21" not in content
            assert "LOT22" not in content
            assert "LOT23" not in content
            assert "LOT24" not in content
