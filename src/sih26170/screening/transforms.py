"""Parameter-specific mathematical representations for Module A.

Compliant with docs/PHASE_3A_MODULE_A_SPEC.md Section 3:
- IDSS: positive log-domain u = ln(y)
- RDS(on): positive log-domain u = ln(y)
- IGSS: signed inverse hyperbolic sine u = asinh(y / 1.0 nA), NEVER abs()
- VGS(th): bounded linear representation u = y
- Explicit noise floor scales to prevent division by zero in robust metrics
"""

from __future__ import annotations

from typing import Dict
import numpy as np

# Scale factor for signed IGSS transformation (1.0 nA electrometer noise floor)
IGSS_SCALE_NA: float = 1.0

# Parameter-specific physical noise floor in transformed space
NOISE_FLOORS: Dict[str, float] = {
    "IDSS": 0.05,     # log-domain floor (relative ~5% noise)
    "RDS(on)": 0.01,   # log-domain floor (relative ~1% noise)
    "IGSS": 0.1,       # asinh-domain floor (0.1 normalized unit ~0.1 nA)
    "VGS(th)": 0.01,   # linear-domain floor (10 mV ATE resolution)
}


def transform_parameter(param: str, value: float) -> float:
    """Transform physical measurement to its parameter-specific representation space.

    Args:
        param: Parameter name ('IDSS', 'VGS(th)', 'RDS(on)', 'IGSS')
        value: Measured value in canonical units (uA, V, mOhm, nA)

    Returns:
        Transformed coordinate u = phi(y)

    Raises:
        ValueError: If value violates physical domain (e.g. non-positive IDSS/RDS(on))
        KeyError: If parameter name is unrecognized
    """
    f_val = float(value)
    if not np.isfinite(f_val):
        raise ValueError(f"Measurement for {param} must be finite, got {f_val}")

    if param == "IDSS":
        if f_val <= 0.0:
            raise ValueError(
                f"IDSS measurement must be strictly positive (> 0) for log transform, got {f_val} uA"
            )
        return float(np.log(f_val))

    elif param == "RDS(on)":
        if f_val <= 0.0:
            raise ValueError(
                f"RDS(on) measurement must be strictly positive (> 0) for log transform, got {f_val} mOhm"
            )
        return float(np.log(f_val))

    elif param == "IGSS":
        # Strictly signed inverse hyperbolic sine: preserves polarity and exact zero.
        # NEVER apply abs() or artificial flooring.
        return float(np.arcsinh(f_val / IGSS_SCALE_NA))

    elif param == "VGS(th)":
        # Bounded linear representation: MOS additive charge trapping electrostatics
        return float(f_val)

    else:
        raise KeyError(f"Unknown parameter '{param}'. Expected one of {list(NOISE_FLOORS.keys())}")


def inverse_transform_parameter(param: str, u: float) -> float:
    """Map representation coordinate back to canonical engineering unit.

    Args:
        param: Parameter name
        u: Transformed coordinate

    Returns:
        Physical value in canonical units
    """
    f_u = float(u)
    if not np.isfinite(f_u):
        raise ValueError(f"Coordinate u for {param} must be finite, got {f_u}")

    if param == "IDSS":
        return float(np.exp(f_u))
    elif param == "RDS(on)":
        return float(np.exp(f_u))
    elif param == "IGSS":
        return float(np.sinh(f_u) * IGSS_SCALE_NA)
    elif param == "VGS(th)":
        return float(f_u)
    else:
        raise KeyError(f"Unknown parameter '{param}'.")


def get_noise_floor(param: str) -> float:
    """Retrieve minimum robust scale floor for parameter."""
    return NOISE_FLOORS.get(param, 0.01)
