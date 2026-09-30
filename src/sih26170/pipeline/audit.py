"""Deterministic hashing and forensic audit tracking for SIH26170 Engineering Prototype.

Complies strictly with post-Phase-5 engineering integration specifications:
- Strict Separation:
    * canonical_result_hash: Computed strictly over deterministic result payload.
      EXCLUDES run_id, created_at timestamp, wall-clock time, host/environment metadata.
    * PipelineAuditRecord: Holds forensic runtime metadata (run_id, created_at, software context)
      and references canonical_result_hash.
- Invariance: Repeated identical input/model/as-of executions produce bit-exact identical
  canonical_result_hash even when audit timestamps differ.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, Optional
import uuid
import pandas as pd

from sih26170.pipeline.schema import PipelineAuditRecord

LINEAGE_MANIFEST_HASH: str = "bde6989e24d195ab4b53f93c46c2156d1c336fe820baf149d76d32943e135667"
SOFTWARE_VERSION: str = "0.1.0-prototype"


def compute_telemetry_hash(df_rows: pd.DataFrame) -> str:
    """Compute deterministic SHA-256 digest of input telemetry rows.

    Sorts columns and rows deterministically to guarantee bit-exact repeatability.
    """
    if df_rows.empty:
        return hashlib.sha256(b"EMPTY_TELEMETRY").hexdigest()

    cols = sorted(df_rows.columns)
    sort_by = [c for c in ["elapsed_hours", "parameter_name", "component_id"] if c in cols]
    sorted_df = df_rows[cols].sort_values(by=sort_by) if sort_by else df_rows[cols]
    serialized = sorted_df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def compute_canonical_result_hash(canonical_dict: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 digest over canonical result payload.

    Enforces strict determinism:
    - Sorted dictionary keys
    - Standard JSON separator delimiters (',', ':')
    - Strictly no timestamps or random UUIDs in the serialized payload
    """
    serialized = json.dumps(
        canonical_dict,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def create_pipeline_audit_record(
    component_id: str,
    lot_id: str,
    as_of_hours: int,
    input_hash: str,
    canonical_result_hash: str,
    run_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> PipelineAuditRecord:
    """Generate forensic audit record containing runtime context."""
    if run_id is None:
        run_id = f"RUN-{uuid.uuid4().hex[:12]}"
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()

    software_context = {
        "pipeline_package": "sih26170.pipeline",
        "pipeline_version": SOFTWARE_VERSION,
        "lineage_manifest_hash": LINEAGE_MANIFEST_HASH,
        "model_lock": "LOCKED_IMMUTABLE",
        "safety_slope": "OPEN_EVIDENCE_GAP",
        "predictive_rejection": "NOT_AUTHORIZED",
        "scope": "ENGINEERING_PROTOTYPE",
    }

    return PipelineAuditRecord(
        run_id=run_id,
        created_at=created_at,
        component_id=component_id,
        lot_id=lot_id,
        as_of_hours=as_of_hours,
        input_hash=input_hash,
        canonical_result_hash=canonical_result_hash,
        model_lineage_hash=LINEAGE_MANIFEST_HASH,
        software_context=software_context,
    )
