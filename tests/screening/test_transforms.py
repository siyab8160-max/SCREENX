"""Unit tests for Module A parameter representations and mathematical transforms.

Validates:
- IDSS positive log transform (fails on non-positive)
- RDS(on) positive log transform (fails on non-positive)
- IGSS signed inverse hyperbolic sine transform:
  - Preserves signed polarity (positive and negative)
  - Preserves exact zero (asinh(0) == 0.0)
  - Never applies abs()
  - Exact round-trip inversion
- VGS(th) bounded linear representation
- Noise floor scale retrieval
"""

import numpy as np
import pytest

from sih26170.screening.transforms import (
    NOISE_FLOORS,
    get_noise_floor,
    inverse_transform_parameter,
    transform_parameter,
)


def test_idss_log_transform():
    """Verify IDSS strictly positive log-domain transformation."""
    # Nominal positive leakage
    u = transform_parameter("IDSS", 0.50)
    assert np.isclose(u, np.log(0.50))
    # Round-trip inversion
    y_back = inverse_transform_parameter("IDSS", u)
    assert np.isclose(y_back, 0.50)

    # Rejection of non-positive readings
    with pytest.raises(ValueError, match="strictly positive"):
        transform_parameter("IDSS", 0.0)

    with pytest.raises(ValueError, match="strictly positive"):
        transform_parameter("IDSS", -1.5)


def test_rdson_log_transform():
    """Verify RDS(on) strictly positive log-domain transformation."""
    u = transform_parameter("RDS(on)", 45.0)
    assert np.isclose(u, np.log(45.0))
    y_back = inverse_transform_parameter("RDS(on)", u)
    assert np.isclose(y_back, 45.0)

    with pytest.raises(ValueError, match="strictly positive"):
        transform_parameter("RDS(on)", 0.0)

    with pytest.raises(ValueError, match="strictly positive"):
        transform_parameter("RDS(on)", -5.0)


def test_igss_signed_asinh_transform():
    """Verify IGSS signed asinh transformation preserves polarity, zero, and never applies abs()."""
    # 1. Zero preservation
    u_zero = transform_parameter("IGSS", 0.0)
    assert u_zero == 0.0
    y_zero = inverse_transform_parameter("IGSS", 0.0)
    assert y_zero == 0.0

    # 2. Positive leakage
    u_pos = transform_parameter("IGSS", 15.0)
    assert u_pos > 0.0
    assert np.isclose(u_pos, np.arcsinh(15.0 / 1.0))
    y_pos = inverse_transform_parameter("IGSS", u_pos)
    assert np.isclose(y_pos, 15.0)

    # 3. Negative leakage (polarity must be strictly preserved!)
    u_neg = transform_parameter("IGSS", -15.0)
    assert u_neg < 0.0
    assert np.isclose(u_neg, -u_pos)  # Odd function symmetry: asinh(-x) == -asinh(x)
    y_neg = inverse_transform_parameter("IGSS", u_neg)
    assert np.isclose(y_neg, -15.0)

    # 4. Prove abs() is NEVER applied: u(-15) != u(+15)
    assert u_neg != u_pos

    # 5. Near-zero linear behavior (|y| << 1.0 nA -> asinh(y) ~ y)
    u_small = transform_parameter("IGSS", 0.05)
    assert np.isclose(u_small, 0.05, rtol=1e-3)


def test_vgsth_bounded_linear_representation():
    """Verify VGS(th) bounded linear representation preserves exact physical potential."""
    u = transform_parameter("VGS(th)", 2.85)
    assert u == 2.85
    y_back = inverse_transform_parameter("VGS(th)", u)
    assert y_back == 2.85


def test_noise_floors():
    """Verify parameter-specific noise floors are non-zero and properly mapped."""
    for param in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]:
        floor = get_noise_floor(param)
        assert floor > 0.0
        assert floor == NOISE_FLOORS[param]

    # Default fallback
    assert get_noise_floor("UNKNOWN_PARAM") == 0.01
