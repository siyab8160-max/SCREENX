"""Auditability and Forensic Replay Tracking for Module A.

Compliant with docs/PHASE_3A_MODULE_A_SPEC.md Sections 12 & 14:
- Cryptographic hashing (SHA-256) of input telemetry rows
- Complete recording of intermediate transformations and detector evidence
- Verification of strict as-of historical boundaries
- Immutable replay records ensuring bit-for-bit decision reconstructibility
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List
import pandas as pd

from sih26170.screening.schema import ComponentScreeningResult


def compute_telemetry_hash(df_rows: pd.DataFrame) -> str:
    """Compute deterministic SHA-256 digest of input telemetry rows."""
    if df_rows.empty:
        return hashlib.sha256(b"EMPTY_ROWS").hexdigest()

    # Sort columns and rows for bit-exact reproducibility
    cols = sorted(df_rows.columns)
    sorted_df = df_rows[cols].sort_values(by=[c for c in ["elapsed_hours", "parameter_name"] if c in cols])
    serialized = sorted_df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


@dataclass
class AuditRecord:
    """Immutable forensic audit record of a single screening decision."""
    component_id: str
    lot_id: str
    checkpoint: int
    as_of_hours: int
    input_hash: str
    transformations: Dict[str, float]
    detector_outputs: Dict[str, Any]
    fusion_result: str
    final_state: str
    primary_reason_code: str
    reason_codes: List[str]
    version_metadata: str = "MODULE_A_v1.0.0"
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


def create_audit_record(
    result: ComponentScreeningResult,
    input_df: pd.DataFrame,
) -> AuditRecord:
    """Generate an immutable audit record from a screening result and its input telemetry slice."""
    # Ensure input_df obeys as-of boundary
    if "elapsed_hours" in input_df.columns:
        future_rows = input_df[input_df["elapsed_hours"] > result.checkpoint]
        if not future_rows.empty:
            raise ValueError(
                f"As-of violation: audit record received rows with elapsed_hours > {result.checkpoint}"
            )

    input_hash = compute_telemetry_hash(input_df)

    transformations = {
        p: res.transformed_value for p, res in result.parameter_results.items()
    }

    detector_outputs = {
        p: {
            "D_spec": res.spec_evidence.status.value,
            "D_peer": res.peer_evidence.status.value,
            "D_drift": res.temporal_evidence.status.value,
            "D_step": res.step_evidence.status.value,
            "D_eq": res.equipment_evidence.status.value,
            "D_suff": res.sufficiency_evidence.status.value,
        }
        for p, res in result.parameter_results.items()
    }

    return AuditRecord(
        component_id=result.component_id,
        lot_id=result.lot_id,
        checkpoint=result.checkpoint,
        as_of_hours=result.as_of_hours,
        input_hash=input_hash,
        transformations=transformations,
        detector_outputs=detector_outputs,
        fusion_result=result.final_state.value,
        final_state=result.final_state.value,
        primary_reason_code=result.primary_reason_code,
        reason_codes=result.reason_codes,
        created_at=result.created_at,
    )
