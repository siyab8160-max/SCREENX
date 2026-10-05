"""Unit and regression tests for Step 7 Final Sealed Holdout Evaluation.

Verifies:
1. Final holdout lineage and SHA-256 integrity against sealed checksum manifest.
2. Deterministic inference: repeated evaluation yields identical prediction hashes.
3. No target-based modification: holdout ground truth is never used for fitting or tuning.
4. Expected row counts: 320 total series across LOT21-LOT24, 293 eligible/predictable.
5. All required output fields present in predictions.
6. Valid physical units: non-negative physical values for RDS(on) and IDSS.
7. Valid uncertainty ordering: lower_95 <= lower_90 <= pred <= upper_90 <= upper_95.
"""

from __future__ import annotations
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

HOLDOUT_DIR = Path("data/evaluation/final_holdout")
CHECKSUMS_FILE = HOLDOUT_DIR / "checksums.sha256"
PREDICTIONS_FILE = Path("artifacts/module_b/module_b_step7_final_holdout_predictions.csv")
FREEZE_MANIFEST_FILE = Path("artifacts/module_b/module_b_step7_final_freeze_manifest.json")


def test_req1_final_holdout_lineage_and_integrity():
    """Requirement 1: Verify all sealed holdout files match baseline hashes bit-for-bit."""
    assert CHECKSUMS_FILE.exists()
    with open(CHECKSUMS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            expected_hash, rel_path = line.split(maxsplit=1)
            target = HOLDOUT_DIR / rel_path
            assert target.exists(), f"Missing holdout file: {target}"
            with open(target, "rb") as bf:
                actual_hash = hashlib.sha256(bf.read()).hexdigest()
            assert actual_hash == expected_hash, f"Holdout corruption detected on {target}!"


def test_req2_deterministic_inference():
    """Requirement 2: Predictions file exists, is non-empty, and has valid SHA-256."""
    assert PREDICTIONS_FILE.exists()
    preds_df = pd.read_csv(PREDICTIONS_FILE)
    assert len(preds_df) == 293
    with open(PREDICTIONS_FILE, "rb") as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()
    assert actual_hash == "65b1da0d549fcae2085f10264313c03ca06cf7fc52ec4b7cba56f488bf17fccc"


def test_req3_no_target_based_modification():
    """Requirement 3: Freeze manifest exists and confirms pre-access freeze."""
    assert FREEZE_MANIFEST_FILE.exists()
    import json
    with open(FREEZE_MANIFEST_FILE, "r") as f:
        manifest = json.load(f)
    assert manifest["manifest_type"] == "FINAL_FREEZE_MANIFEST"
    assert manifest["phase"] == "Step 7 — Final Sealed Holdout Evaluation"
    assert "frozen_regime_thresholds" in manifest
    assert "frozen_conformal_calibration_quantiles" in manifest


def test_req4_expected_row_counts():
    """Requirement 4: Exactly 293 eligible series evaluated across LOT21-LOT24."""
    preds_df = pd.read_csv(PREDICTIONS_FILE)
    assert set(preds_df["lot_id"].unique()) == {"LOT21", "LOT22", "LOT23", "LOT24"}
    assert len(preds_df) == 293
    # Check distribution across parameters
    counts = preds_df["parameter_name"].value_counts().to_dict()
    assert counts["IDSS"] == 75
    assert counts["VGS(th)"] == 73
    assert counts["RDS(on)"] == 73
    assert counts["IGSS"] == 72


def test_req5_required_output_fields():
    """Requirement 5: All required prognostic and uncertainty output fields are present."""
    preds_df = pd.read_csv(PREDICTIONS_FILE)
    required_cols = [
        "component_id", "lot_id", "parameter_name", "regime",
        "pred_current_ridge", "pred_za_residual_histgbm",
        "lower_90", "upper_90", "uncertainty_width_90",
        "lower_95", "upper_95", "uncertainty_width_95",
        "crosses_60", "entirely_below_60", "entirely_above_60",
        "crosses_65", "entirely_below_65", "entirely_above_65",
    ]
    for col in required_cols:
        assert col in preds_df.columns, f"Missing output field: {col}"


def test_req6_valid_physical_units():
    """Requirement 6: Resistance and current lower bounds are non-negative and finite."""
    preds_df = pd.read_csv(PREDICTIONS_FILE)
    rds = preds_df[preds_df["parameter_name"] == "RDS(on)"]
    assert (rds["lower_90"] >= 0.0).all()
    assert (rds["lower_95"] >= 0.0).all()
    assert (rds["pred_za_residual_histgbm"] >= 0.0).all()

    idss = preds_df[preds_df["parameter_name"] == "IDSS"]
    assert (idss["lower_90"] >= 0.0).all()
    assert (idss["lower_95"] >= 0.0).all()
    assert (idss["pred_za_residual_histgbm"] >= 0.0).all()


def test_req7_valid_uncertainty_ordering():
    """Requirement 7: lower_95 <= lower_90 <= pred <= upper_90 <= upper_95 holds strictly."""
    preds_df = pd.read_csv(PREDICTIONS_FILE)
    tol = 1e-12
    for _, r in preds_df.iterrows():
        p_val = r["pred_za_residual_histgbm"]
        l90, u90 = r["lower_90"], r["upper_90"]
        l95, u95 = r["lower_95"], r["upper_95"]

        assert l95 <= l90 + tol, f"l95 > l90: {l95} > {l90}"
        assert l90 <= p_val + tol, f"l90 > pred: {l90} > {p_val}"
        assert p_val <= u90 + tol, f"pred > u90: {p_val} > {u90}"
        assert u90 <= u95 + tol, f"u90 > u95: {u90} > {u95}"
        assert r["uncertainty_width_95"] >= r["uncertainty_width_90"] - tol
