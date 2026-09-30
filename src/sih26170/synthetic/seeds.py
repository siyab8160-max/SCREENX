"""SIH26170 Synthetic Generator Deterministic Seed Hierarchy.

Implements a deterministic, bitwise-reproducible seed derivation hierarchy
using SHA-256 hashing to ensure stability across Python processes,
avoiding Python's randomized built-in hash().
"""

import hashlib
import numpy as np


def derive_seed(parent_seed: int, *keys: str | int) -> int:
    """Derive a deterministic 32-bit integer seed from a parent seed and key tokens.
    
    Uses SHA-256 to ensure consistent bitwise derivation across different OS platforms
    and Python runtimes.
    """
    token = f"{parent_seed}:" + ":".join(str(k) for k in keys)
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    # Extract 32-bit unsigned integer (0 to 2^32 - 1)
    seed_32 = int.from_bytes(digest[:4], byteorder="big", signed=False)
    return seed_32


class SeedHierarchy:
    """Manages hierarchical seed derivation for synthetic generation."""

    def __init__(self, master_seed: int):
        self.master_seed = master_seed

    def get_lot_seed(self, lot_id: str) -> int:
        """Derive seed for a specific lot."""
        return derive_seed(self.master_seed, "lot", lot_id)

    def get_component_seed(self, lot_id: str, component_id: str) -> int:
        """Derive seed for a specific component within a lot."""
        lot_seed = self.get_lot_seed(lot_id)
        return derive_seed(lot_seed, "component", component_id)

    def get_parameter_seed(self, lot_id: str, component_id: str, parameter_name: str) -> int:
        """Derive seed for a specific parameter trajectory of a component."""
        comp_seed = self.get_component_seed(lot_id, component_id)
        return derive_seed(comp_seed, "parameter", parameter_name)

    def get_measurement_seed(
        self, lot_id: str, component_id: str, parameter_name: str, elapsed_hours: int
    ) -> int:
        """Derive seed for a specific checkpoint measurement readout."""
        param_seed = self.get_parameter_seed(lot_id, component_id, parameter_name)
        return derive_seed(param_seed, "measurement", elapsed_hours)

    def get_rng(self, *keys: str | int) -> np.random.Generator:
        """Convenience helper to get a NumPy random Generator for any key path."""
        derived = derive_seed(self.master_seed, *keys)
        return np.random.default_rng(derived)
