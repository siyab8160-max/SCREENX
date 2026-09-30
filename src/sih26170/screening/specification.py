"""Detector A: Absolute Specification and Screening Margin Detector (D_spec).

Compliant with docs/PHASE_3A_MODULE_A_SPEC.md Sections 4.1 & 5:
- Class A: Verified Device Specification (MIL-PRF-19500/703 Table I)
- Class C: Configured Screening Acceptance Criterion (PD-97217 room-temp margin)
- Explicitly maintains distinction: 65 mOhm = Class A spec; 60 mOhm = Class C margin.
- Never represents 60 mOhm as a universal MIL-PRF limit.
"""

from __future__ import annotations

from typing import Optional
from sih26170.screening.schema import (
    LimitClass,
    SpecificationEvidence,
    SpecificationStatus,
)

# MIL-PRF-19500/703 Table I verified specification boundaries (Class A)
SPEC_LIMITS_CLASS_A = {
    "IDSS": {"low": None, "high": 10.0, "unit": "uA", "provenance": "MIL-PRF-19500/703 Table I (<= 10.0 uA, VDS=80V)"},
    "VGS(th)": {"low": 2.0, "high": 4.0, "unit": "V", "provenance": "MIL-PRF-19500/703 Table I ([2.0, 4.0] V, ID=1mA)"},
    "IGSS": {"low": -100.0, "high": 100.0, "unit": "nA", "provenance": "MIL-PRF-19500/703 Table I ([-100.0, +100.0] nA, VGS=+/-20V)"},
    "RDS(on)": {"low": None, "high": 65.0, "unit": "mOhm", "provenance": "MIL-PRF-19500/703 Table I (<= 65.0 mOhm, ID=22A)"},
}

# Configured screening acceptance criteria (Class C)
SCREENING_MARGINS_CLASS_C = {
    "RDS(on)": {"low": None, "high": 60.0, "unit": "mOhm", "provenance": "Infineon PD-97217 Table 3 Screening Margin (<= 60.0 mOhm)"},
}


def evaluate_specification(
    parameter: str,
    value: float,
    custom_limit_low: Optional[float] = None,
    custom_limit_high: Optional[float] = None,
) -> SpecificationEvidence:
    """Evaluate observation against Class A specification and Class C screening margin.

    Args:
        parameter: Parameter name ('IDSS', 'VGS(th)', 'RDS(on)', 'IGSS')
        value: Observed measurement scalar
        custom_limit_low: Optional override lower limit from telemetry record
        custom_limit_high: Optional override upper limit from telemetry record

    Returns:
        SpecificationEvidence with full epistemic provenance and status.
    """
    f_val = float(value)
    spec_a = SPEC_LIMITS_CLASS_A.get(parameter)
    if spec_a is None:
        return SpecificationEvidence(
            parameter=parameter,
            observed_value=f_val,
            limit_low=custom_limit_low,
            limit_high=custom_limit_high,
            limit_class=LimitClass.CLASS_D,
            status=SpecificationStatus.NOT_EVALUATED,
            passed=True,
            reason_code="PARAMETER_NOT_IN_SLASH_SHEET",
            provenance="Unknown parameter",
        )

    # Use slash sheet limits as primary Class A ground truth; custom telemetry limits can also be recorded
    lim_low = custom_limit_low if custom_limit_low is not None else spec_a["low"]
    lim_high = custom_limit_high if custom_limit_high is not None else spec_a["high"]

    # Clean parameter tag for reason code
    clean_p = {
        "IDSS": "IDSS",
        "VGS(th)": "VGSTH",
        "RDS(on)": "RDSON",
        "IGSS": "IGSS",
    }.get(parameter, parameter.replace('(', '').replace(')', '').upper())

    # 1. Check Class A hard specification breach (safety veto)
    if lim_low is not None and f_val < lim_low:
        return SpecificationEvidence(
            parameter=parameter,
            observed_value=f_val,
            limit_low=lim_low,
            limit_high=lim_high,
            limit_class=LimitClass.CLASS_A,
            status=SpecificationStatus.SPEC_BREACH,
            passed=False,
            reason_code=f"ABSOLUTE_LIMIT_BREACH_{clean_p}_LOW",
            provenance=spec_a["provenance"],
        )

    if lim_high is not None and f_val > lim_high:
        return SpecificationEvidence(
            parameter=parameter,
            observed_value=f_val,
            limit_low=lim_low,
            limit_high=lim_high,
            limit_class=LimitClass.CLASS_A,
            status=SpecificationStatus.SPEC_BREACH,
            passed=False,
            reason_code=f"ABSOLUTE_LIMIT_BREACH_{clean_p}_HIGH",
            provenance=spec_a["provenance"],
        )

    # 2. Check Class C configured screening margin breach (tightened flight screening)
    margin_c = SCREENING_MARGINS_CLASS_C.get(parameter)
    if margin_c is not None:
        c_high = margin_c["high"]
        if c_high is not None and f_val > c_high:
            return SpecificationEvidence(
                parameter=parameter,
                observed_value=f_val,
                limit_low=lim_low,
                limit_high=c_high,
                limit_class=LimitClass.CLASS_C,
                status=SpecificationStatus.SCREENING_MARGIN_BREACH,
                passed=True,  # Complies with Class A, breaches Class C margin
                reason_code=f"SCREENING_MARGIN_BREACH_{clean_p}",
                provenance=margin_c["provenance"],
            )

    # 3. Fully compliant with both Class A and Class C
    return SpecificationEvidence(
        parameter=parameter,
        observed_value=f_val,
        limit_low=lim_low,
        limit_high=lim_high,
        limit_class=LimitClass.CLASS_A,
        status=SpecificationStatus.COMPLIANT,
        passed=True,
        reason_code="SPEC_COMPLIANT",
        provenance=spec_a["provenance"],
    )
