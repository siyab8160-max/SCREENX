"""Telemetry provider abstractions for SIH26170 Engineering Prototype.

Complies strictly with post-Phase-5 engineering integration specifications:
- Decoupled provider interface: The core screening/prognostic logic depends on the
  telemetry-provider interface, allowing a future real-data provider to be substituted
  without changes to core model/screening logic, subject to real-data schema and validation integration.
- Strict Ground Truth Quarantine: SyntheticTelemetryProvider consumes observations.csv ONLY.
  Evaluation ground-truth files MUST NOT be imported, loaded, joined, or referenced by the runtime inference path.
- Strict As-Of Causality: All telemetry queries strictly enforce:
    elapsed_hours <= as_of_hours
  Future checkpoints (e.g. 96h and 168h when as_of_hours=24) are completely inaccessible.
- Clear provenance tagging: source_type = 'SYNTHETIC_PHASE4B'.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import pandas as pd

# Quarantined ground-truth columns that must NEVER enter runtime telemetry
FORBIDDEN_GROUND_TRUTH_COLUMNS: Set[str] = {
    "trajectory_class",
    "first_abnormal_hour",
    "abnormal_by_24h",
    "abnormal_by_96h",
    "abnormal_by_168h",
    "is_temporally_degraded",
    "is_spec_compliant",
    "is_abnormal",
    "parameter_scenario",
    "achieved_snr",
    "dominant_mechanism",
    "scenario_class",
}


def assert_ground_truth_quarantine(df: pd.DataFrame) -> None:
    """Verify that runtime input telemetry is free of evaluation ground-truth labels."""
    forbidden_found = FORBIDDEN_GROUND_TRUTH_COLUMNS.intersection(set(df.columns))
    if forbidden_found:
        raise ValueError(
            f"Ground truth quarantine violation: input dataframe contains forbidden evaluation columns: {sorted(forbidden_found)}. "
            "Evaluation ground truth must NEVER enter runtime screening or prognostics."
        )


class BaseTelemetryProvider(ABC):
    """Abstract telemetry provider interface for component burn-in data."""

    @abstractmethod
    def get_lot_ids(self) -> List[str]:
        """Return list of unique lot identifiers available in the repository."""
        pass

    @abstractmethod
    def get_component_ids(self, lot_id: str) -> List[str]:
        """Return list of unique component identifiers for a lot."""
        pass

    @abstractmethod
    def get_component_telemetry(self, component_id: str, as_of_hours: int) -> pd.DataFrame:
        """Return strictly filtered historical telemetry for a component: elapsed_hours <= as_of_hours."""
        pass

    @abstractmethod
    def get_lot_telemetry(self, lot_id: str, as_of_hours: int) -> pd.DataFrame:
        """Return strictly filtered historical telemetry for an entire lot cohort: elapsed_hours <= as_of_hours."""
        pass

    @abstractmethod
    def get_component_metadata(self, component_id: str) -> Dict[str, Any]:
        """Return bare metadata for component (e.g. lot_id, part_number) without executing inference."""
        pass


class SyntheticTelemetryProvider(BaseTelemetryProvider):
    """Synthetic Phase 4B benchmark telemetry provider for prototype demonstration."""

    def __init__(self, observations_path: Optional[Path] = None) -> None:
        if observations_path is None:
            # Locate relative to project repository root
            observations_path = (
                Path(__file__).resolve().parents[3]
                / "data/synthetic_phase4b/observations.csv"
            )

        if not observations_path.exists():
            raise FileNotFoundError(
                f"Synthetic observations file not found at: {observations_path}"
            )

        self.observations_path = Path(observations_path)
        self._df: Optional[pd.DataFrame] = None

    def _get_raw_df(self) -> pd.DataFrame:
        """Load and cache observations.csv under strict ground-truth quarantine."""
        if self._df is None:
            df = pd.read_csv(self.observations_path)
            assert_ground_truth_quarantine(df)
            df["source_type"] = "SYNTHETIC_PHASE4B"
            self._df = df
        return self._df

    def get_lot_ids(self) -> List[str]:
        """Return sorted list of all unique lots in the benchmark."""
        df = self._get_raw_df()
        return sorted(df["lot_id"].unique().tolist())

    def get_component_ids(self, lot_id: str) -> List[str]:
        """Return sorted list of component IDs for a given lot."""
        df = self._get_raw_df()
        lot_df = df[df["lot_id"] == lot_id]
        if lot_df.empty:
            raise KeyError(f"Lot '{lot_id}' not found in telemetry store.")
        return sorted(lot_df["component_id"].unique().tolist())

    def get_component_telemetry(self, component_id: str, as_of_hours: int) -> pd.DataFrame:
        """Return component telemetry strictly filtered by elapsed_hours <= as_of_hours."""
        df = self._get_raw_df()
        comp_df = df[df["component_id"] == component_id]
        if comp_df.empty:
            raise KeyError(f"Component '{component_id}' not found in telemetry store.")

        # STRICT AS-OF FILTERING
        as_of_slice = comp_df[comp_df["elapsed_hours"] <= as_of_hours].copy()
        assert_ground_truth_quarantine(as_of_slice)
        return as_of_slice.sort_values(by=["elapsed_hours", "parameter_name"]).reset_index(drop=True)

    def get_lot_telemetry(self, lot_id: str, as_of_hours: int) -> pd.DataFrame:
        """Return entire lot telemetry strictly filtered by elapsed_hours <= as_of_hours."""
        df = self._get_raw_df()
        lot_df = df[df["lot_id"] == lot_id]
        if lot_df.empty:
            raise KeyError(f"Lot '{lot_id}' not found in telemetry store.")

        # STRICT AS-OF FILTERING
        as_of_slice = lot_df[lot_df["elapsed_hours"] <= as_of_hours].copy()
        assert_ground_truth_quarantine(as_of_slice)
        return as_of_slice.sort_values(by=["elapsed_hours", "component_id", "parameter_name"]).reset_index(drop=True)

    def get_component_metadata(self, component_id: str) -> Dict[str, Any]:
        """Return bare metadata for component without evaluating screening or inference."""
        df = self._get_raw_df()
        comp_df = df[df["component_id"] == component_id]
        if comp_df.empty:
            raise KeyError(f"Component '{component_id}' not found in telemetry store.")

        first_row = comp_df.iloc[0]
        checkpoints = sorted(comp_df["elapsed_hours"].unique().tolist())
        parameters = sorted(comp_df["parameter_name"].unique().tolist())

        return {
            "component_id": str(component_id),
            "lot_id": str(first_row["lot_id"]),
            "part_number": "IRHNJ57130",
            "slash_sheet": "MIL-PRF-19500/703",
            "package": "SMD-0.5",
            "source_type": "SYNTHETIC_PHASE4B",
            "available_checkpoints": checkpoints,
            "monitored_parameters": parameters,
        }
