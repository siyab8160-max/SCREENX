"""SIH26170 Phase 4B Candidate Degradation Detectors & Multiplicity Control.

Compliant with docs/PHASE_4B_DETECTOR_CALIBRATION_SPEC.md (v1.9.0):
- Detector Family 1: Kendall's tau rank correlation [PRIMARY CANDIDATE, K >= 2]
- Detector Family 2: Theil-Sen robust slope [AUXILIARY CANDIDATE, K >= 2]
- Detector Family 3: Parametric linear regression OLS t-statistic [BENCHMARK COMPARATOR, K >= 3]
  * Note: UNDEFINED at K=2 (df = 0)
- Detector Family 4: Module A endpoint drift [FROZEN NON-CALIBRATED COMPARATOR]
- Causal Leave-One-Out (LOO) lot median differencing
- Empirical p-value evaluation with Davison-Hinkley (+1) correction
- Component-level Holm-Bonferroni step-down multiplicity control (alpha = 0.001 across 4 parameters)
- Preserves signed IGSS throughout (NEVER abs() before transform or detector calculation)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


def compute_kendall_tau(y: np.ndarray) -> np.ndarray:
    """Compute Kendall's tau rank correlation statistic against monotonic time indices.

    For excess coordinates y across K checkpoints:
        S_tau = [2 / (K*(K-1))] * sum_{1 <= j < k <= K} sgn(y_k - y_j)

    Args:
        y: 1D array of shape (K,) or 2D array of shape (N, K)

    Returns:
        Scalar tau (for 1D input) or 1D array of shape (N,) (for 2D input)
    """
    arr = np.asarray(y, dtype=np.float64)
    is_1d = arr.ndim == 1
    if is_1d:
        arr = arr[np.newaxis, :]
    elif arr.ndim != 2:
        raise ValueError(f"y must be 1D or 2D array, got ndim={arr.ndim}")

    n, k = arr.shape
    if k < 2:
        raise ValueError(f"Kendall's tau requires at least K=2 points, got K={k}")

    pairs = [(j, k_idx) for j in range(k) for k_idx in range(j + 1, k)]
    pair_diffs = np.stack([arr[:, k_idx] - arr[:, j] for j, k_idx in pairs], axis=1)
    pair_signs = np.sign(pair_diffs)
    tau = np.mean(pair_signs, axis=1)

    return tau[0] if is_1d else tau


def compute_theil_sen(t: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Compute Theil-Sen robust slope estimator test statistic.

    For excess coordinates y at checkpoint times t across K checkpoints:
        S_TS = median_{1 <= j < k <= K} { (y_k - y_j) / (t_k - t_j) }

    Args:
        t: 1D array of checkpoint times of length K (strictly increasing)
        y: 1D array of shape (K,) or 2D array of shape (N, K)

    Returns:
        Scalar slope (for 1D input) or 1D array of shape (N,) (for 2D input)
    """
    t_arr = np.asarray(t, dtype=np.float64)
    arr = np.asarray(y, dtype=np.float64)
    is_1d = arr.ndim == 1
    if is_1d:
        arr = arr[np.newaxis, :]
    elif arr.ndim != 2:
        raise ValueError(f"y must be 1D or 2D array, got ndim={arr.ndim}")

    n, k = arr.shape
    if len(t_arr) != k:
        raise ValueError(f"Length of t ({len(t_arr)}) must match columns of y ({k})")
    if k < 2:
        raise ValueError(f"Theil-Sen requires at least K=2 points, got K={k}")

    pairs = [(j, k_idx) for j in range(k) for k_idx in range(j + 1, k)]
    pair_slopes = np.stack(
        [(arr[:, k_idx] - arr[:, j]) / (t_arr[k_idx] - t_arr[j]) for j, k_idx in pairs],
        axis=1,
    )
    slopes = np.median(pair_slopes, axis=1)

    return slopes[0] if is_1d else slopes


def compute_ols_t(t: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Compute parametric ordinary linear regression OLS t-statistic.

    For excess coordinates y at checkpoint times t across K checkpoints:
        S_t = beta_1 / SE(beta_1), df = K - 2

    Note:
        At K=2, df = 0, so the OLS t-statistic is mathematically UNDEFINED.
        Calling this function with K=2 raises ValueError.

    Args:
        t: 1D array of checkpoint times of length K (strictly increasing)
        y: 1D array of shape (K,) or 2D array of shape (N, K)

    Returns:
        Scalar t-stat (for 1D input) or 1D array of shape (N,) (for 2D input)
    """
    t_arr = np.asarray(t, dtype=np.float64)
    arr = np.asarray(y, dtype=np.float64)
    is_1d = arr.ndim == 1
    if is_1d:
        arr = arr[np.newaxis, :]
    elif arr.ndim != 2:
        raise ValueError(f"y must be 1D or 2D array, got ndim={arr.ndim}")

    n, k = arr.shape
    if len(t_arr) != k:
        raise ValueError(f"Length of t ({len(t_arr)}) must match columns of y ({k})")
    if k < 3:
        raise ValueError(
            f"OLS t-statistic is mathematically UNDEFINED at K={k} (df = K - 2 = {k - 2} <= 0)."
        )

    t_bar = np.mean(t_arr)
    t_dev = t_arr - t_bar
    s_tt = np.sum(t_dev**2)
    if s_tt <= 0.0:
        raise ValueError("Degenerate time checkpoints: zero sum of squared deviations.")

    y_bar = np.mean(arr, axis=1, keepdims=True)
    y_dev = arr - y_bar
    beta1 = np.sum(y_dev * t_dev, axis=1) / s_tt
    beta0 = y_bar[:, 0] - beta1 * t_bar
    residuals = arr - (beta0[:, np.newaxis] + np.outer(beta1, t_arr))
    sse = np.sum(residuals**2, axis=1)
    df = k - 2
    s_e = np.sqrt(sse / df)
    se_beta1 = s_e / np.sqrt(s_tt)

    t_stat = np.where(se_beta1 > 0.0, beta1 / se_beta1, 0.0)

    return t_stat[0] if is_1d else t_stat


def compute_module_a_drift(y: np.ndarray, noise_scale: float) -> np.ndarray:
    """Compute Module A endpoint drift comparator statistic.

    g_p(T_as_of) = [u_p(T_as_of) - u_p(0)] / sigma_{u,p}

    Args:
        y: 1D array of shape (K,) or 2D array of shape (N, K)
        noise_scale: sigma_{u,p} transformed noise scale

    Returns:
        Scalar drift (for 1D input) or 1D array of shape (N,) (for 2D input)
    """
    arr = np.asarray(y, dtype=np.float64)
    is_1d = arr.ndim == 1
    if is_1d:
        arr = arr[np.newaxis, :]
    elif arr.ndim != 2:
        raise ValueError(f"y must be 1D or 2D array, got ndim={arr.ndim}")

    if noise_scale <= 0.0:
        raise ValueError(f"noise_scale must be positive, got {noise_scale}")

    drift = (arr[:, -1] - arr[:, 0]) / float(noise_scale)
    return drift[0] if is_1d else drift


def compute_loo_excess_coordinates(
    lot_measurements: np.ndarray,
) -> np.ndarray:
    """Compute leave-one-out (LOO) lot-median excess coordinates.

    For each component i in lot of size L:
        u_{i,p}^{excess}(t) = u_{i,p}(t) - median_{j in L \\ {i}} { u_{j,p}(t) }

    Args:
        lot_measurements: Array of shape (L, ...) where axis 0 indexes components in the lot.
                         For single lot: shape (L, n_params, K)
                         For multiple lots: shape (n_lots, L, n_params, K)

    Returns:
        Excess coordinates of identical shape with component i strictly excluded from its own reference.
    """
    arr = np.asarray(lot_measurements, dtype=np.float64)

    if arr.ndim == 3:
        l_size = arr.shape[0]
        if l_size < 3:
            raise ValueError(f"LOO median requires lot size >= 3, got {l_size}")

        sorted_arr = np.sort(arr, axis=0)
        k_target = (l_size - 1) // 2
        low_med = sorted_arr[k_target : k_target + 1]
        high_med = sorted_arr[k_target + 1 : k_target + 2]
        loo_med = np.where(arr < high_med, high_med, low_med)
        return arr - loo_med

    elif arr.ndim == 4:
        n_lots, l_size, n_params, k_len = arr.shape
        if l_size < 3:
            raise ValueError(f"LOO median requires lot size >= 3, got {l_size}")

        sorted_arr = np.sort(arr, axis=1)
        k_target = (l_size - 1) // 2
        low_med = sorted_arr[:, k_target : k_target + 1, :, :]
        high_med = sorted_arr[:, k_target + 1 : k_target + 2, :, :]
        loo_med = np.where(arr < high_med, high_med, low_med)
        return arr - loo_med

    else:
        raise ValueError(f"lot_measurements must be 3D or 4D array, got ndim={arr.ndim}")


def compute_empirical_p_value(
    statistic: Union[float, np.ndarray],
    reference_distribution: np.ndarray,
    tail: str = "upper",
) -> Union[float, np.ndarray]:
    """Compute empirical p-value with Davison-Hinkley (+1) finite-sample correction.

    One-sided upper tail:
        p = (1 + sum I(S_ref >= S_obs)) / (N + 1)
    Two-sided symmetric tail:
        p = min(1.0, 2 * (1 + sum I(|S_ref| >= |S_obs|)) / (N + 1))

    Args:
        statistic: Observed test statistic (scalar or array)
        reference_distribution: 1D array of calibration null statistics (sorted or unsorted)
        tail: "upper" (one-sided) or "two_sided" (symmetric)

    Returns:
        Empirical p-value(s) in (0, 1]
    """
    ref = np.asarray(reference_distribution, dtype=np.float64)
    if ref.ndim != 1:
        raise ValueError("reference_distribution must be 1D array")
    n_cal = len(ref)
    if n_cal < 1:
        raise ValueError("reference_distribution must not be empty")

    s = np.asarray(statistic, dtype=np.float64)
    is_scalar = s.ndim == 0
    if is_scalar:
        s = s[np.newaxis]

    ref_sorted = np.sort(ref)

    if tail == "upper":
        idx = np.searchsorted(ref_sorted, s, side="left")
        counts = n_cal - idx
        p_vals = (1.0 + counts) / (n_cal + 1.0)
    elif tail == "two_sided":
        ref_abs_sorted = np.sort(np.abs(ref))
        s_abs = np.abs(s)
        idx = np.searchsorted(ref_abs_sorted, s_abs, side="left")
        counts = n_cal - idx
        p_vals = (1.0 + counts) / (n_cal + 1.0)
    else:
        raise ValueError(f"Unknown tail '{tail}'. Expected 'upper' or 'two_sided'.")

    return float(p_vals[0]) if is_scalar else p_vals


def apply_holm_bonferroni(
    p_values: Dict[str, float],
    alpha: float = 0.001,
) -> Dict[str, Any]:
    """Execute step-down Holm-Bonferroni procedure across physical parameter p-values.

    Sequential thresholds for M=4:
        Step 1: alpha / 4 = 0.00025
        Step 2: alpha / 3 ~= 0.0003333
        Step 3: alpha / 2 = 0.00050
        Step 4: alpha / 1 = 0.00100

    Args:
        p_values: Dictionary of parameter_name -> p_value (e.g. 4 parameters)
        alpha: Component-level target FWER (default 0.001)

    Returns:
        Dictionary with step-down decisions:
        {
            "rejected_parameters": List[str],
            "component_rejected": bool,
            "sorted_p_values": List[Tuple[str, float, float, bool]], # (param, p_val, threshold, rejected)
            "step_reached": int,
        }
    """
    m = len(p_values)
    if m == 0:
        return {
            "rejected_parameters": [],
            "component_rejected": False,
            "sorted_p_values": [],
            "step_reached": 0,
        }

    sorted_items = sorted(p_values.items(), key=lambda item: item[1])

    rejected_params: List[str] = []
    audit_trail: List[Tuple[str, float, float, bool]] = []
    step_reached = 0

    for rank_idx, (p_name, p_val) in enumerate(sorted_items):
        step_reached = rank_idx + 1
        threshold = alpha / float(m - rank_idx)
        if p_val <= threshold:
            rejected_params.append(p_name)
            audit_trail.append((p_name, float(p_val), float(threshold), True))
        else:
            audit_trail.append((p_name, float(p_val), float(threshold), False))
            for rem_rank in range(rank_idx + 1, m):
                rem_name, rem_p = sorted_items[rem_rank]
                rem_thresh = alpha / float(m - rem_rank)
                audit_trail.append((rem_name, float(rem_p), float(rem_thresh), False))
            break

    component_rejected = len(rejected_params) > 0

    return {
        "rejected_parameters": rejected_params,
        "component_rejected": component_rejected,
        "sorted_p_values": audit_trail,
        "step_reached": step_reached,
    }
