"""Unit tests for Phase 4B Null-C common-mode stress test engine."""

import json
from pathlib import Path
import numpy as np
import pytest

from sih26170.screening.phase4b_calibration import run_phase4b_calibration
from sih26170.screening.phase4b_null_c import (
    generate_null_c_trajectories,
    run_null_c_stress_test,
    CM_TEMP_COEFF,
    DELTA_T_CELSIUS,
)


class TestPhase4BNullC:
    """Test suite for Phase 4B Null-C common-mode stress test engine."""

    def test_generate_null_c_trajectories_shape_and_cancellation(self):
        raw_u, excess_u, cm_shift, raw_flat = generate_null_c_trajectories(
            seed=622638004,
            n_lots=5,
            lot_size=20,
        )
        assert raw_u.shape == (5, 20, 4, 7)
        assert excess_u.shape == (100, 4, 7)
        assert cm_shift.shape == (4, 7)
        assert raw_flat.shape == (100, 4, 7)

        # Verify common-mode shift values
        # Checkpoints: [0, 24, 48, 72, 96, 120, 168] -> indices 3 and 4 are 72h and 96h
        for p_idx, p_name in enumerate(["IDSS", "VGS(th)", "RDS(on)", "IGSS"]):
            expected_shift = CM_TEMP_COEFF[p_name] * DELTA_T_CELSIUS
            assert cm_shift[p_idx, 3] == pytest.approx(expected_shift)
            assert cm_shift[p_idx, 4] == pytest.approx(expected_shift)
            assert cm_shift[p_idx, 0] == 0.0
            assert cm_shift[p_idx, 1] == 0.0
            assert cm_shift[p_idx, 2] == 0.0
            assert cm_shift[p_idx, 5] == 0.0
            assert cm_shift[p_idx, 6] == 0.0

        # Verify reproducibility with same seed
        raw_u2, excess_u2, cm_shift2, raw_flat2 = generate_null_c_trajectories(
            seed=622638004,
            n_lots=5,
            lot_size=20,
        )
        np.testing.assert_array_equal(raw_u, raw_u2)
        np.testing.assert_array_equal(excess_u, excess_u2)
        np.testing.assert_array_equal(cm_shift, cm_shift2)
        np.testing.assert_array_equal(raw_flat, raw_flat2)

    def test_run_null_c_stress_test_small(self, tmp_path: Path):
        # 1. First run a small calibration
        calib_dir = tmp_path / "calibration"
        run_phase4b_calibration(
            output_dir=calib_dir,
            seed=194572359,
            n_lots=5,
            lot_size=20,
        )

        # 2. Run small Null-C stress test
        stress_dir = tmp_path / "stress"
        res = run_null_c_stress_test(
            calibration_dir=calib_dir,
            output_dir=stress_dir,
            seed=622638004,
            n_lots=5,
            lot_size=20,
        )

        assert res["status"] == "NULL_C_STRESS_TEST_COMPLETED"
        assert Path(res["stress_file"]).exists()
        assert len(res["parameter_results"]) == 68
        assert len(res["fwer_results"]) == 17
        assert len(res["module_a_excess_results"]) == 6
        assert len(res["module_a_raw_results"]) == 6

        stress_json = json.loads(Path(res["stress_file"]).read_text())
        assert stress_json["stress_seed"] == 622638004
        assert stress_json["sample_accounting"]["n_components"] == 100
        assert "parameter_level_results" in stress_json
        assert "component_level_fwer_results" in stress_json
        assert "common_mode_specification" in stress_json
        assert "comparator_module_a_excess_results" in stress_json
        assert "comparator_module_a_raw_results" in stress_json
