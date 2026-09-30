"""Unit tests for Phase 4B Independent Power Sweep Engine."""

import json
from pathlib import Path
import numpy as np
import pytest

from sih26170.screening.phase4b_calibration import (
    ALL_CHECKPOINTS,
    PARAM_SPECS,
    run_phase4b_calibration,
)
from sih26170.screening.phase4b_power_sweep import (
    ALL_MORPHOLOGIES,
    Morphology,
    SWEEP_DELTAS,
    evaluate_degradation_kinetics,
    generate_power_cell_trajectories,
    run_phase4b_power_sweep,
)


class TestPhase4BPowerSweep:
    """Test suite for Phase 4B power sweep engine."""

    def test_morphology_kinetics_evaluation(self):
        checkpoints = ALL_CHECKPOINTS
        sig_u = PARAM_SPECS["IDSS"]["sigma_u"]

        # Fixture A: Linear Drift
        g_t, s_t, cm_t = evaluate_degradation_kinetics(
            Morphology.FIXTURE_A_LINEAR_DRIFT, delta=2.0, param_name="IDSS", sign_p=1.0, checkpoints=checkpoints
        )
        assert g_t[0] == 0.0
        assert g_t[-1] == pytest.approx(2.0 * sig_u)
        assert cm_t.sum() == 0.0
        assert np.all(s_t == sig_u)

        # Fixture B: Accelerating Drift (exponent 2.1)
        g_t_b, _, _ = evaluate_degradation_kinetics(
            Morphology.FIXTURE_B_ACCELERATING_DRIFT, delta=2.0, param_name="IDSS", sign_p=1.0, checkpoints=checkpoints
        )
        assert g_t_b[0] == 0.0
        assert g_t_b[-1] == pytest.approx(2.0 * sig_u)
        # At midpoint (approx 72h or 96h), accelerating drift should be strictly less than linear drift
        assert g_t_b[3] < g_t[3]

        # Fixture C: Abrupt Step (step at 72h)
        g_t_c, _, _ = evaluate_degradation_kinetics(
            Morphology.FIXTURE_C_ABRUPT_STEP, delta=1.5, param_name="IDSS", sign_p=1.0, checkpoints=checkpoints
        )
        # Checkpoints: 0, 24, 48, 72, 96, 120, 168
        assert g_t_c[0] == 0.0
        assert g_t_c[1] == 0.0
        assert g_t_c[2] == 0.0
        assert g_t_c[3] == pytest.approx(1.5 * sig_u)  # 72h
        assert g_t_c[6] == pytest.approx(1.5 * sig_u)  # 168h

        # Fixture D: Confounded Drift (thermal shift at 72h, 96h)
        g_t_d, _, cm_t_d = evaluate_degradation_kinetics(
            Morphology.FIXTURE_D_CONFOUNDED_DRIFT, delta=1.5, param_name="IDSS", sign_p=1.0, checkpoints=checkpoints
        )
        assert g_t_d[-1] == pytest.approx(1.5 * sig_u)
        assert cm_t_d[0] == 0.0
        assert cm_t_d[1] == 0.0
        assert cm_t_d[2] == 0.0
        assert cm_t_d[3] > 0.0  # 72h thermal shift
        assert cm_t_d[4] > 0.0  # 96h thermal shift
        assert cm_t_d[5] == 0.0  # 120h recovered
        assert cm_t_d[6] == 0.0  # 168h recovered

        # Fixture E: Heteroscedastic Noise
        _, s_t_e, _ = evaluate_degradation_kinetics(
            Morphology.FIXTURE_E_HETEROSCEDASTIC_NOISE, delta=1.5, param_name="IDSS", sign_p=1.0, checkpoints=checkpoints
        )
        assert s_t_e[0] == pytest.approx(sig_u)
        assert s_t_e[-1] == pytest.approx(sig_u * 1.5)

        # Fixture F: Staggered Onset (onset at 48h)
        g_t_f, _, _ = evaluate_degradation_kinetics(
            Morphology.FIXTURE_F_STAGGERED_ONSET, delta=1.5, param_name="IDSS", sign_p=1.0, checkpoints=checkpoints
        )
        assert g_t_f[0] == 0.0
        assert g_t_f[1] == 0.0
        assert g_t_f[2] == 0.0  # 48h
        assert g_t_f[3] > 0.0  # 72h
        assert g_t_f[-1] == pytest.approx(1.5 * sig_u)

    def test_trajectory_generation_shapes_and_reproducibility(self):
        excess_u, raw_u = generate_power_cell_trajectories(
            morphology=Morphology.FIXTURE_A_LINEAR_DRIFT,
            delta=2.0,
            seed=15152878,
            n_components=20,
            lot_size=20,
        )
        assert excess_u.shape == (20, 4, 7)
        assert raw_u.shape == (20, 4, 7)

        # Reproducibility check
        excess_u2, raw_u2 = generate_power_cell_trajectories(
            morphology=Morphology.FIXTURE_A_LINEAR_DRIFT,
            delta=2.0,
            seed=15152878,
            n_components=20,
            lot_size=20,
        )
        np.testing.assert_array_equal(excess_u, excess_u2)
        np.testing.assert_array_equal(raw_u, raw_u2)

    def test_run_phase4b_power_sweep_small(self, tmp_path: Path):
        # 1. Run small calibration to establish reference table and distributions
        calib_dir = tmp_path / "calibration"
        run_phase4b_calibration(
            output_dir=calib_dir,
            seed=194572359,
            n_lots=5,
            lot_size=20,
        )

        # 2. Run small power sweep
        out_dir = tmp_path / "power_sweep"
        res = run_phase4b_power_sweep(
            calibration_dir=calib_dir,
            output_dir=out_dir,
            seed=15152878,
            n_per_cell=20,
            lot_size=20,
        )

        assert res["status"] == "POWER_SWEEP_COMPLETED"
        assert res["n_cells"] == 24
        assert res["total_components"] == 480  # 24 * 20
        assert Path(res["output_file"]).exists()

        data = json.loads(Path(res["output_file"]).read_text())
        assert data["power_seed"] == 15152878
        assert data["sample_accounting"]["total_cells"] == 24
        assert len(data["cell_power_results"]) == 24
