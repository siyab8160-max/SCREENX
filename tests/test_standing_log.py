"""Unit tests verifying Prototype Standing Log completeness and integrity."""

from pathlib import Path

REQUIRED_LOG_FIELDS = [
    "Log ID",
    "Date",
    "Phase",
    "Change",
    "Previous State",
    "New State",
    "Reason",
    "Source / Provenance",
    "Status",
    "Affected Area",
    "Impact",
]

VALID_STATUSES = {
    "VERIFIED",
    "SPECIFICATION",
    "ASSUMPTION",
    "DESIGN_DECISION",
    "USER_CONFIGURABLE",
    "NOT_YET_VERIFIED",
    "OPEN_QUESTION",
    "IMPLEMENTED",
    "TESTED",
    "DEFERRED",
    "REJECTED",
}


def test_prototype_standing_log_exists():
    """Verify docs/PROTOTYPE_STANDING_LOG.md exists."""
    log_path = Path("docs/PROTOTYPE_STANDING_LOG.md")
    if not log_path.exists():
        # Check relative to repo root
        log_path = Path(__file__).resolve().parent.parent / "docs" / "PROTOTYPE_STANDING_LOG.md"
    assert log_path.exists(), "docs/PROTOTYPE_STANDING_LOG.md must exist as a permanent project artifact."

    content = log_path.read_text(encoding="utf-8")
    assert "SIH26170 — Prototype Standing / Change Log" in content

    # Check that initial Phase 1 log entries LOG-001 through LOG-022 exist
    for i in range(1, 23):
        log_id = f"LOG-{i:03d}"
        assert log_id in content, f"Missing log entry {log_id} in PROTOTYPE_STANDING_LOG.md"

    # Check for presence of Phase 1 Engineering Audit section
    assert "## Phase 1 Engineering Audit" in content

    # Check for presence of required field headers
    for field_name in REQUIRED_LOG_FIELDS:
        assert f"**{field_name}**" in content or f"- **{field_name}**" in content, (
            f"Missing required field '{field_name}' in standing log."
        )
