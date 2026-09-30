"""Unit tests for Phase 4B Null-B stress test engine."""

import json
from pathlib import Path
import numpy as np
import pytest

from sih26170.screening.phase4b_calibration import run_phase4b_calibration
from sih26170.screening.phase4b_null_b import (
    generate_null_b_trajectories,
    run_null_b_stress_test,
)


class TestPhase4BNullB:
    """Test suite for Phase 4B Null-B stress test engine."""

    def test_generate_null_b_trajectories_shape_and_ar1(self):
        raw_u, excess_u, phi = generate_null_b_trajectories(
            seed=270315777,
            n_lots=5,
            lot_size=20,
        )
        assert raw_u.shape == (5, 20, 4, 7)
        assert excess_u.shape == (100, 4, 7)
        assert phi.shape == (100, 4)

        # Verify phi is in [0.20, 0.35]
        assert np.all(phi >= 0.20)
        assert np.all(phi <= 0.35)

        # Verify reproducibility with same seed
        raw_u2, excess_u2, phi2 = generate_null_b_trajectories(
            seed=270315777,
            n_lots=5,
            lot_size=20,
        )
        np.testing.assert_array_equal(raw_u, raw_u2)
        np.testing.assert_array_equal(excess_u, excess_u2)
        np.testing.assert_array_equal(phi, phi2)

    def test_run_null_b_stress_test_small(self, tmp_path: Path):
        # 1. First run a small calibration
        calib_dir = tmp_path / "calibration"
        run_phase4b_calibration(
            output_dir=calib_dir,
            seed=194572359,
            n_lots=5,
            lot_size=20,
        )

        # 2. Run small Null-B stress test
        stress_dir = tmp_path / "stress"
        res = run_null_b_stress_test(
            calibration_dir=calib_dir,
            output_dir=stress_dir,
            seed=270315777,
            n_lots=5,
            lot_size=20,
        )

        assert res["status"] == "NULL_B_STRESS_TEST_COMPLETED"
        assert Path(res["stress_file"]).exists()
        assert len(res["parameter_results"]) == 68
        assert len(res["fwer_results"]) == 17

        stress_json = json.loads(Path(res["stress_file"]).read_text())
        assert stress_json["stress_seed"] == 270315777
        assert stress_json["sample_accounting"]["n_components"] == 100
        assert "parameter_level_results" in stress_json
        assert "component_level_fwer_results" in stress_json
        assert "ar1_specification" in stress_json
