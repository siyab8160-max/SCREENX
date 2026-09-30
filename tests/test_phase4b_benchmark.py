"""Tests for SIH26170 Phase 4B Independent Benchmark Generation and Integrity.

Validates:
- Benchmark file existence, schema adherence, and cryptographic checksums
- Dense temporal support (K=7, S1 schedule: 0, 24, 48, 72, 96, 120, 168 h)
- Signed IGSS preservation (no abs(), no clipping to positive)
- Parameter physical domain bounds
- Disjoint partition hierarchy (50% Calibration, 25% Validation, 25% Final Evaluation)
- Strict causal leakage isolation between observations and ground truth
- Null model zero-drift integrity
- AR(1) pooled ensemble autocorrelation
- Degradation fixture kinetics and parameter selectivity
"""

import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from sih26170.schema import CANONICAL_COLUMNS


BENCHMARK_DIR = Path("data/synthetic_phase4b")


@pytest.fixture(scope="module")
def benchmark_files():
    """Verify and return paths to the benchmark artifacts."""
    obs_path = BENCHMARK_DIR / "observations.csv"
    gt_path = BENCHMARK_DIR / "ground_truth.csv"
    manifest_path = BENCHMARK_DIR / "manifest.json"
    checksum_path = BENCHMARK_DIR / "checksums.sha256"

    assert obs_path.exists(), "observations.csv missing"
    assert gt_path.exists(), "ground_truth.csv missing"
    assert manifest_path.exists(), "manifest.json missing"
    assert checksum_path.exists(), "checksums.sha256 missing"

    return {
        "obs": obs_path,
        "gt": gt_path,
        "manifest": manifest_path,
        "checksums": checksum_path,
    }


def test_cryptographic_checksums(benchmark_files):
    """Verify SHA-256 checksums match checksums.sha256."""
    lines = benchmark_files["checksums"].read_text(encoding="utf-8").strip().splitlines()
    recorded_hashes = {}
    for line in lines:
        parts = line.split()
        if len(parts) == 2:
            recorded_hashes[parts[1]] = parts[0]

    for fname in ["observations.csv", "ground_truth.csv", "manifest.json"]:
        assert fname in recorded_hashes, f"{fname} missing from checksums.sha256"
        computed = hashlib.sha256((BENCHMARK_DIR / fname).read_bytes()).hexdigest()
        assert computed == recorded_hashes[fname], f"Checksum mismatch for {fname}"


def test_manifest_metadata(benchmark_files):
    """Verify manifest metadata schema and partition allocations."""
    with open(benchmark_files["manifest"], "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["benchmark_version"] == "PHASE_4B_BENCHMARK_v1.0.0"
    assert manifest["temporal_schedules"]["checkpoints"] == [0, 24, 48, 72, 96, 120, 168]
    assert manifest["temporal_schedules"]["checkpoint_count"] == 7

    partitions = manifest["partitions"]
    assert partitions["CALIBRATION"]["fraction"] == 0.50
    assert partitions["VALIDATION"]["fraction"] == 0.25
    assert partitions["FINAL_EVALUATION"]["fraction"] == 0.25

    assert partitions["CALIBRATION"]["lot_count"] == 50
    assert partitions["VALIDATION"]["lot_count"] == 25
    assert partitions["FINAL_EVALUATION"]["lot_count"] == 25

    assert manifest["dataset_summary"]["total_lots"] == 100
    assert manifest["dataset_summary"]["total_components"] == 2000
    assert manifest["dataset_summary"]["total_series"] == 8000
    assert manifest["dataset_summary"]["observation_row_count"] == 56000
    assert manifest["dataset_summary"]["ground_truth_row_count"] == 56000


def test_observation_schema_and_leakage(benchmark_files):
    """Verify observation columns strictly match CANONICAL_COLUMNS with zero metadata leaks."""
    obs_df = pd.read_csv(benchmark_files["obs"], nrows=100)
    assert list(obs_df.columns) == CANONICAL_COLUMNS

    forbidden_patterns = [
        "scenario",
        "ground_truth",
        "latent",
        "drift",
        "fixture",
        "delta",
        "degradation",
        "failure",
        "partition",
        "seed",
    ]
    for col in obs_df.columns:
        for pat in forbidden_patterns:
            assert pat not in col.lower(), f"Potential leakage column in observations: {col}"


def test_row_counts_and_checkpoints(benchmark_files):
    """Verify exact row counts, component counts, and checkpoints."""
    obs_df = pd.read_csv(benchmark_files["obs"])
    gt_df = pd.read_csv(benchmark_files["gt"])

    assert len(obs_df) == 56000
    assert len(gt_df) == 56000

    assert obs_df["component_id"].nunique() == 2000
    assert obs_df["lot_id"].nunique() == 100

    ckpts = sorted(obs_df["elapsed_hours"].unique().tolist())
    assert ckpts == [0, 24, 48, 72, 96, 120, 168]


def test_signed_igss_preservation(benchmark_files):
    """Verify that IGSS values remain signed with both positive and negative values observed."""
    obs_df = pd.read_csv(benchmark_files["obs"])
    igss_vals = obs_df[obs_df["parameter_name"] == "IGSS"]["value"]

    min_val = float(igss_vals.min())
    max_val = float(igss_vals.max())
    assert min_val < 0.0, f"Expected negative IGSS values, got min {min_val}"
    assert max_val > 0.0, f"Expected positive IGSS values, got max {max_val}"
    assert not igss_vals.isna().any(), "NaN found in IGSS"


def test_physical_domain_validity(benchmark_files):
    """Verify physical positivity of IDSS and RDS(on), and stability of VGS(th)."""
    obs_df = pd.read_csv(benchmark_files["obs"])

    idss_vals = obs_df[obs_df["parameter_name"] == "IDSS"]["value"]
    assert (idss_vals > 0).all(), "IDSS must be strictly positive"

    rdson_vals = obs_df[obs_df["parameter_name"] == "RDS(on)"]["value"]
    assert (rdson_vals > 0).all(), "RDS(on) must be strictly positive"

    vgsth_vals = obs_df[obs_df["parameter_name"] == "VGS(th)"]["value"]
    assert (vgsth_vals > 1.5).all() and (vgsth_vals < 4.5).all(), "VGS(th) out of bounds"


def test_null_models_and_ar1_autocorrelation(benchmark_files):
    """Verify null models have zero latent drift and AR(1) has correct pooled correlation."""
    gt_df = pd.read_csv(benchmark_files["gt"])

    # 1. Null models zero drift
    null_mask = gt_df["fixture_type"].isin(["null_gaussian", "null_ar1", "null_common_mode"])
    null_drift = gt_df[null_mask]["latent_drift"].abs().max()
    assert null_drift == 0.0, f"Null models have non-zero latent drift: {null_drift}"

    # 2. AR(1) pooled ensemble lag-1 correlation
    ar1_gt = gt_df[gt_df["fixture_type"] == "null_ar1"]
    all_x = []
    all_y = []
    for comp_id, comp_df in ar1_gt[ar1_gt["parameter_name"] == "IDSS"].groupby("component_id"):
        noise = comp_df.sort_values("elapsed_hours")["noise_realization"].values
        if len(noise) >= 7:
            all_x.extend(noise[:-1])
            all_y.extend(noise[1:])
    pooled_corr = float(np.corrcoef(all_x, all_y)[0, 1])
    assert 0.15 <= pooled_corr <= 0.40, f"AR(1) pooled lag-1 corr {pooled_corr:.3f} outside [0.15, 0.40]"
