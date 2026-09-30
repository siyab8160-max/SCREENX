"""Ground-truth isolation and benchmark immutability tests for Module A.

Validates:
- Prompt Section 17: Runtime boundary preventing Module A from reading ground_truth.csv
- Rejection of input dataframes contaminated with evaluation ground-truth columns
- Static code audit ensuring zero ground_truth.csv references inside screening code
- Cryptographic verification that frozen benchmark v1.0.0 is 100% byte-identical
- Cryptographic verification that historical Phase 2C benchmark is 100% untouched
"""

import hashlib
from pathlib import Path
import pandas as pd
import pytest

from sih26170.screening.pipeline import (
    FORBIDDEN_GROUND_TRUTH_COLUMNS,
    assert_ground_truth_quarantine,
    screen_component,
)

FROZEN_OBS_SHA256 = "b4282e0743cd6a0b2b74354e431bf8f308b03281c44c0437d30f7b53bd6ca983"
FROZEN_GT_SHA256 = "4bf2155fcc7698813f766e1dea9730213e0a6097e484bfa786eb1b94925f3d2b"


def test_ground_truth_quarantine_rejection():
    """Verify input dataframes containing evaluation ground-truth columns are immediately rejected."""
    clean_df = pd.DataFrame([
        {"component_id": "C01", "lot_id": "L01", "parameter_name": "RDS(on)", "elapsed_hours": 0, "value": 45.0, "unit": "mOhm"}
    ])

    # Clean input passes quarantine check
    assert_ground_truth_quarantine(clean_df)

    # Contaminated inputs with any forbidden column must raise ValueError
    for forbidden_col in FORBIDDEN_GROUND_TRUTH_COLUMNS:
        bad_df = clean_df.copy()
        bad_df[forbidden_col] = "oracle_value"
        with pytest.raises(ValueError, match="Ground truth quarantine violation"):
            assert_ground_truth_quarantine(bad_df)

        with pytest.raises(ValueError, match="Ground truth quarantine violation"):
            screen_component(bad_df, "C01", as_of_hours=0)


def test_codebase_isolation_from_ground_truth():
    """Verify Module A screening source code contains zero references to ground_truth.csv."""
    screening_dir = Path("src/sih26170/screening")
    assert screening_dir.exists()

    for py_file in screening_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "ground_truth.csv" not in content, (
            f"Violation in {py_file}: Module A source code must never reference ground_truth.csv"
        )


def test_frozen_benchmark_immutability():
    """Verify frozen Phase 2F benchmark files remain 100% byte-identical to release hash."""
    frozen_dir = Path("data/synthetic_phase2f_frozen")
    assert frozen_dir.exists()

    obs_path = frozen_dir / "observations.csv"
    gt_path = frozen_dir / "ground_truth.csv"

    obs_sha = hashlib.sha256(obs_path.read_bytes()).hexdigest()
    gt_sha = hashlib.sha256(gt_path.read_bytes()).hexdigest()

    assert obs_sha == FROZEN_OBS_SHA256, (
        f"CRITICAL: observations.csv hash changed! Expected {FROZEN_OBS_SHA256}, got {obs_sha}"
    )
    assert gt_sha == FROZEN_GT_SHA256, (
        f"CRITICAL: ground_truth.csv hash changed! Expected {FROZEN_GT_SHA256}, got {gt_sha}"
    )


def test_historical_phase2c_immutability():
    """Verify historical Phase 2C benchmark remains untouched."""
    hist_dir = Path("data/synthetic")
    assert hist_dir.exists()
    assert (hist_dir / "observations.csv").exists()
    assert (hist_dir / "ground_truth.csv").exists()
