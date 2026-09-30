"""Unit tests for Phase 4B Null-A calibration engine."""

import json
from pathlib import Path
import numpy as np
import pytest

from sih26170.screening.phase4b_calibration import (
    compute_critical_threshold,
    generate_null_a_trajectories,
    run_phase4b_calibration,
)


class TestPhase4BCalibration:
    """Test suite for Phase 4B calibration engine."""

    def test_generate_null_a_trajectories_small(self):
        seed = 194572359
        raw_u, excess_u = generate_null_a_trajectories(seed=seed, n_lots=5, lot_size=20)
        assert raw_u.shape == (5, 20, 4, 7)
        assert excess_u.shape == (100, 4, 7)
        assert np.all(np.isfinite(raw_u))
        assert np.all(np.isfinite(excess_u))

    def test_compute_critical_threshold(self):
        # Reference distribution with 10,000 samples from Standard Normal
        rng = np.random.default_rng(42)
        ref = rng.normal(0.0, 1.0, size=10000)

        # One-sided upper threshold for alpha = 0.05
        thresh_05 = compute_critical_threshold(ref, tail="upper", target_alpha=0.05)
        # Should be approximately 1.645
        assert 1.5 < thresh_05 < 1.8

        # Two-sided symmetric threshold for alpha = 0.05
        thresh_05_sym = compute_critical_threshold(ref, tail="two_sided", target_alpha=0.05)
        # Should be approximately 1.96
        assert 1.8 < thresh_05_sym < 2.1

    def test_run_phase4b_calibration_small(self, tmp_path: Path):
        output_dir = tmp_path / "calibration_test"
        res = run_phase4b_calibration(
            output_dir=output_dir,
            seed=194572359,
            n_lots=10,
            lot_size=20,
        )

        assert res["total_entries"] == 68
        assert Path(res["ref_table_path"]).exists()
        assert Path(res["dist_file_path"]).exists()
        assert Path(res["manifest_path"]).exists()

        ref_table = json.loads(Path(res["ref_table_path"]).read_text())
        assert len(ref_table["entries"]) == 68

        # Check metadata fields of an entry
        k_entry = ref_table["entries"]["kendall_tau__IDSS__T24h_K2"]
        assert k_entry["detector_family"] == "kendall_tau"
        assert k_entry["parameter"] == "IDSS"
        assert k_entry["T_as_of"] == 24
        assert k_entry["K"] == 2
        assert k_entry["tail_direction"] == "upper"
        assert k_entry["N_calibration"] == 200
        assert k_entry["p_value_method"] == "empirical_rank_davison_hinkley"
        assert k_entry["finite_sample_correction"] == "+1_rank_over_N_plus_1"
        assert "critical_value_threshold" in k_entry
        assert k_entry["calibration_seed"] == 194572359
        assert "artifact_hash" in k_entry
