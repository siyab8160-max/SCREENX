"""Demo scenario loader for SIH26170 Engineering Prototype.

Complies strictly with post-Phase-5 engineering integration specifications:
- Dynamic execution over frozen synthetic benchmark: Zero hardcoded mock responses.
- Executes real underlying pipeline (orchestrator + locked Ridge + Module A).
- Provides convenience interface to select lot, component, and as-of checkpoint.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from sih26170.pipeline.orchestrator import run_component_pipeline
from sih26170.pipeline.schema import ComponentPipelineResult
from sih26170.pipeline.telemetry import BaseTelemetryProvider, SyntheticTelemetryProvider


class DemoScenarioLoader:
    """Demonstration scenario loader for interactive and test execution."""

    def __init__(self, provider: Optional[BaseTelemetryProvider] = None) -> None:
        if provider is None:
            provider = SyntheticTelemetryProvider()
        self.provider = provider

    def list_lots(self) -> List[str]:
        """Return available lots in the benchmark."""
        return self.provider.get_lot_ids()

    def list_components(self, lot_id: str) -> List[str]:
        """Return components available for a given lot."""
        return self.provider.get_component_ids(lot_id)

    def get_component_info(self, component_id: str) -> Dict[str, Any]:
        """Return bare metadata for component (no inference)."""
        return self.provider.get_component_metadata(component_id)

    def run_scenario(
        self,
        component_id: str,
        as_of_hours: int,
    ) -> ComponentPipelineResult:
        """Execute real end-to-end pipeline for the selected component at as_of_hours."""
        meta = self.get_component_info(component_id)
        lot_id = meta["lot_id"]

        comp_telemetry = self.provider.get_component_telemetry(component_id, as_of_hours)
        lot_telemetry = self.provider.get_lot_telemetry(lot_id, as_of_hours)

        return run_component_pipeline(
            telemetry=comp_telemetry,
            component_id=component_id,
            as_of_hours=as_of_hours,
            lot_telemetry=lot_telemetry,
        )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SIH26170 Prototype Demo Loader")
    parser.add_argument("--component-id", default="LOT_CAL_001_C001", help="Target component ID")
    parser.add_argument("--as-of", type=int, default=24, help="As-of evaluation hours")
    args = parser.parse_args()

    loader = DemoScenarioLoader()
    res = loader.run_scenario(args.component_id, args.as_of)
    print(res.explainability.ascii_summary)
    print(f"\nCanonical Result Hash: {res.canonical_result_hash}")
    print(f"Audit Created At:     {res.audit_record.created_at}")
