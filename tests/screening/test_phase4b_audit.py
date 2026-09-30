"""Unit tests for Phase 4B Independent Null-A audit engine."""

import json
from pathlib import Path
import numpy as np
import pytest

from sih26170.screening.phase4b_audit import (
    compute_wilson_ci,
    run_null_a_audit,
)
from sih26170.screening.phase4b_calibration import run_phase4b_calibration


class TestPhase4BAudit:
    """Test suite for Phase 4B audit engine."""

    def test_compute_wilson_ci_bounds(self):
        # k=0: lower must be 0, upper must be > 0
        low, high = compute_wilson_ci(0, 1000)
        assert low == 0.0
        assert high > 0.0

        # k=n: upper must be 1, lower must be < 1
        low, high = compute_wilson_ci(1000, 1000)
        assert high == 1.0
        assert low < 1.0

        # Intermediate: center around 0.5 for k=500
        low, high = compute_wilson_ci(500, 1000)
        assert 0.46 < low < 0.50
        assert 0.50 < high < 0.54

        # n=0 returns (0, 0)
        assert compute_wilson_ci(0, 0) == (0.0, 0.0)

    def test_run_null_a_audit_small(self, tmp_path: Path):
        # 1. First run a small calibration
        calib_dir = tmp_path / "calibration"
        run_phase4b_calibration(
            output_dir=calib_dir,
            seed=194572359,
            n_lots=5,
            lot_size=20,
        )

        # 2. Run small audit
        audit_dir = tmp_path / "audit"
        res = run_null_a_audit(
            calibration_dir=calib_dir,
            output_dir=audit_dir,
            seed=233837969,
            n_lots=5,
            lot_size=20,
        )

        assert res["status"] == "NULL_A_AUDIT_COMPLETED"
        assert Path(res["audit_file"]).exists()
        assert len(res["parameter_results"]) == 68
        assert len(res["fwer_results"]) == 17  # 6 (kendall) + 6 (theil-sen) + 5 (ols_t)

        audit_json = json.loads(Path(res["audit_file"]).read_text())
        assert audit_json["audit_seed"] == 233837969
        assert audit_json["sample_accounting"]["n_components"] == 100
        assert "parameter_level_results" in audit_json
        assert "component_level_fwer_results" in audit_json
