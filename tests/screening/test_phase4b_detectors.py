"""Unit tests for Phase 4B candidate detectors, LOO differencing, and Holm-Bonferroni control."""

import numpy as np
import pytest

from sih26170.screening.phase4b_detectors import (
    apply_holm_bonferroni,
    compute_empirical_p_value,
    compute_kendall_tau,
    compute_loo_excess_coordinates,
    compute_module_a_drift,
    compute_ols_t,
    compute_theil_sen,
)


class TestPhase4BDetectors:
    """Test suite for Phase 4B detectors."""

    def test_kendall_tau_basic(self):
        # Strictly monotonic increasing
        y_inc = np.array([1.0, 2.0, 3.0, 4.0])
        assert np.isclose(compute_kendall_tau(y_inc), 1.0)

        # Strictly monotonic decreasing
        y_dec = np.array([4.0, 3.0, 2.0, 1.0])
        assert np.isclose(compute_kendall_tau(y_dec), -1.0)

        # Non-monotonic
        y_mid = np.array([1.0, 3.0, 2.0])
        # pairs: (1,3)+, (1,2)+, (3,2)- => (1 + 1 - 1)/3 = 1/3
        assert np.isclose(compute_kendall_tau(y_mid), 1.0 / 3.0)

        # Ties
        y_tie = np.array([1.0, 1.0, 1.0])
        assert np.isclose(compute_kendall_tau(y_tie), 0.0)

        # K=2 minimum horizon
        assert np.isclose(compute_kendall_tau(np.array([2.0, 5.0])), 1.0)
        assert np.isclose(compute_kendall_tau(np.array([5.0, 2.0])), -1.0)

        # K < 2 raises ValueError
        with pytest.raises(ValueError, match="at least K=2"):
            compute_kendall_tau(np.array([1.0]))

    def test_theil_sen_basic(self):
        t = np.array([0, 24, 48, 72], dtype=float)
        # Perfect linear slope 0.5
        y = 2.0 + 0.5 * t
        assert np.isclose(compute_theil_sen(t, y), 0.5)

        # K=2 algebraic identity: slope is (y1 - y0)/(t1 - t0)
        t_2 = np.array([0, 24], dtype=float)
        y_2 = np.array([1.0, 7.0])
        expected_slope = (7.0 - 1.0) / 24.0
        assert np.isclose(compute_theil_sen(t_2, y_2), expected_slope)

        # Outlier robustness at K=4: single point corrupted
        y_corrupt = y.copy()
        y_corrupt[1] = 999.0  # outlier
        # Outlier affects 3 pairs, but remaining 3 pairs have slope 0.5
        # Pair slopes: (0,24)->high, (0,48)->0.5, (0,72)->0.5, (24,48)->low, (24,72)->low, (48,72)->0.5
        # Median should still be 0.5!
        assert np.isclose(compute_theil_sen(t, y_corrupt), 0.5)

    def test_ols_t_basic_and_k2_exclusion(self):
        t = np.array([0, 24, 48, 72, 96], dtype=float)
        y = 1.0 + 0.1 * t + np.array([0.01, -0.01, 0.02, -0.02, 0.0])
        t_stat = compute_ols_t(t, y)
        assert t_stat > 0  # positive slope

        # K=2 must raise ValueError (df = 0, mathematically undefined)
        t_2 = np.array([0, 24], dtype=float)
        y_2 = np.array([1.0, 2.0])
        with pytest.raises(ValueError, match="UNDEFINED at K=2"):
            compute_ols_t(t_2, y_2)

    def test_module_a_drift(self):
        y = np.array([1.0, 1.2, 1.4, 2.0])
        noise_scale = 0.08
        drift = compute_module_a_drift(y, noise_scale)
        assert np.isclose(drift, (2.0 - 1.0) / 0.08)

    def test_loo_excess_coordinates(self):
        np.random.seed(42)
        # Lot of L=20 components, 4 parameters, 7 checkpoints
        lot_data = np.random.randn(20, 4, 7)
        excess = compute_loo_excess_coordinates(lot_data)
        assert excess.shape == (20, 4, 7)

        # Verify strict self-exclusion for every component
        for i in range(20):
            for p in range(4):
                for k in range(7):
                    others = np.delete(lot_data[:, p, k], i)
                    expected_loo_med = np.median(others)
                    expected_excess = lot_data[i, p, k] - expected_loo_med
                    assert np.isclose(excess[i, p, k], expected_excess)

    def test_empirical_p_value(self):
        # Reference distribution of N=1000 items
        ref = np.linspace(-3.0, 3.0, 1000)

        # One-sided upper: value larger than all reference items
        p_extreme = compute_empirical_p_value(10.0, ref, tail="upper")
        assert np.isclose(p_extreme, 1.0 / (1000 + 1))  # exactly 1 / (N+1)

        # One-sided upper: value smaller than all reference items
        p_low = compute_empirical_p_value(-10.0, ref, tail="upper")
        assert np.isclose(p_low, (1.0 + 1000) / (1000 + 1))  # exactly 1.0

        # Two-sided symmetric: for s=10.0 larger than all |ref|, count is 0, so p = (1 + 0) / (1000 + 1)
        p_sym_extreme = compute_empirical_p_value(10.0, ref, tail="two_sided")
        assert np.isclose(p_sym_extreme, 1.0 / (1000 + 1))

    def test_holm_bonferroni(self):
        # Case 1: All p-values above threshold -> accept all
        p_vals_null = {
            "IDSS": 0.05,
            "VGS(th)": 0.10,
            "RDS(on)": 0.20,
            "IGSS": 0.50,
        }
        res = apply_holm_bonferroni(p_vals_null, alpha=0.001)
        assert not res["component_rejected"]
        assert len(res["rejected_parameters"]) == 0
        assert res["step_reached"] == 1

        # Case 2: IDSS rejects at step 1 (p <= 0.00025)
        p_vals_rej1 = {
            "IDSS": 0.0001,  # step 1: 0.0001 <= 0.00025 -> REJECT
            "VGS(th)": 0.05,
            "RDS(on)": 0.10,
            "IGSS": 0.50,
        }
        res = apply_holm_bonferroni(p_vals_rej1, alpha=0.001)
        assert res["component_rejected"]
        assert res["rejected_parameters"] == ["IDSS"]
        assert res["step_reached"] == 2

        # Case 3: Multiple rejections
        p_vals_rej_multi = {
            "IDSS": 0.0001,    # step 1: <= 0.00025 -> REJECT
            "RDS(on)": 0.0003,  # step 2: <= 0.000333 -> REJECT
            "VGS(th)": 0.0004,  # step 3: <= 0.00050 -> REJECT
            "IGSS": 0.05,      # step 4: > 0.001 -> ACCEPT
        }
        res = apply_holm_bonferroni(p_vals_rej_multi, alpha=0.001)
        assert res["component_rejected"]
        assert set(res["rejected_parameters"]) == {"IDSS", "RDS(on)", "VGS(th)"}
        assert res["step_reached"] == 4
