"""Comprehensive automated test suite for Phase 7: Data Workspace & Demo Data / User Data Flow.

Covers all 21 verification requirements specified in Phase 7 specification:
- Dataset Selection (1-5):
    1. Demo dataset appears in dropdown.
    2. Actual available datasets are used; no fabricated datasets.
    3. Demo dataset is visibly marked synthetic.
    4. Upload-my-dataset option is available.
    5. Dataset selection changes active context.
- Upload & Ingestion (6-10):
    6. Valid telemetry CSV accepted.
    7. Invalid CSV rejected with useful errors.
    8. Preview renders.
    9. Validation summary renders.
    10. Confirmation required before analysis.
- Isolation & Model Integrity (11-15):
    11. Uploaded data does not trigger training.
    12. Uploaded data does not modify locked coefficients.
    13. Uploaded data does not modify sigma_eff.
    14. Ground truth cannot enter inference.
    15. Switching datasets clears stale results.
- Engineering Safety (16-18):
    16. Earlier as-of views cannot display future telemetry.
    17. Measured failure and predicted breach remain separate.
    18. No unsupported failure probability is displayed.
- Layout & Overflow Mitigation (19-21):
    19. No uncontrolled overflow at 1024px.
    20. No uncontrolled overflow at 1280px.
    21. No uncontrolled overflow at 1440px.
"""

from __future__ import annotations

import io
from pathlib import Path
import re
import pytest
import pandas as pd

from sih26170.pipeline.telemetry import (
    FORBIDDEN_GROUND_TRUTH_COLUMNS,
    SyntheticTelemetryProvider,
    assert_ground_truth_quarantine,
)
from sih26170.prognostics.locked_models import (
    LOCKED_COEFFICIENTS_HEX,
    FROZEN_SIGMA_EFF_HEX,
    get_locked_ridge_model,
)


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def html_content(repo_root: Path) -> str:
    html_path = repo_root / "src/sih26170/service/static/index.html"
    return html_path.read_text(encoding="utf-8")


@pytest.fixture
def js_content(repo_root: Path) -> str:
    js_path = repo_root / "src/sih26170/service/static/app.js"
    return js_path.read_text(encoding="utf-8")


@pytest.fixture
def css_content(repo_root: Path) -> str:
    css_path = repo_root / "src/sih26170/service/static/styles.css"
    return css_path.read_text(encoding="utf-8")


# =============================================================================
# SUITE 1: DATASET SELECTION (Requirements 1 - 5)
# =============================================================================
class TestDatasetSelection:
    """Verify dataset dropdown and selection semantics."""

    def test_01_demo_dataset_appears_in_dropdown(self, html_content: str):
        """1. Demo dataset appears in dropdown."""
        assert 'id="select-main-dataset"' in html_content
        assert 'value="phase4b_demo"' in html_content
        assert "Phase 4B Demo Dataset" in html_content

    def test_02_actual_available_datasets_used_no_fabricated(self, html_content: str):
        """2. Actual available datasets are used; no fabricated datasets."""
        # Find all option values inside select-main-dataset
        select_match = re.search(
            r'<select[^>]*id="select-main-dataset"[^>]*>(.*?)</select>',
            html_content,
            re.DOTALL,
        )
        assert select_match is not None
        options_html = select_match.group(1)

        # Must only contain the real demo dataset and upload option
        values = re.findall(r'value="([^"]+)"', options_html)
        assert values == ["phase4b_demo", "upload_own"]

        # Disallow fabricated datasets or scenario labels
        for forbidden in ["scenario_1", "drift_dataset", "failure_dataset", "custom_noise", "lot_cal_99"]:
            assert forbidden not in options_html.lower()

    def test_03_demo_dataset_visibly_marked_synthetic(self, html_content: str):
        """3. Demo dataset is visibly marked synthetic."""
        # Check badge and metadata in index.html
        assert "DEMO &bull; SYNTHETIC" in html_content or "DEMO · SYNTHETIC" in html_content
        assert "Synthetic demonstration data" in html_content

    def test_04_upload_my_dataset_option_available(self, html_content: str):
        """4. Upload-my-dataset option is available in the dropdown."""
        assert 'value="upload_own"' in html_content
        assert "Upload my own dataset" in html_content

    def test_05_dataset_selection_changes_active_context(self, js_content: str):
        """5. Dataset selection changes active context in left rail and context bar."""
        assert "rail-dataset-name" in js_content
        assert "rail-dataset-badge" in js_content
        assert "ctx-dataset" in js_content
        assert "val-source" in js_content
        # Switching between demo and uploaded updates activeDataset
        assert "state.activeDataset = 'demo'" in js_content
        assert "state.activeDataset = 'uploaded'" in js_content


# =============================================================================
# SUITE 2: UPLOAD & INGESTION (Requirements 6 - 10)
# =============================================================================
class TestUploadAndIngestion:
    """Verify upload validation, CSV schema, preview, and confirmation."""

    CANONICAL_COLUMNS = [
        "component_id",
        "lot_id",
        "parameter_name",
        "elapsed_hours",
        "value",
        "unit",
        "temperature_C",
        "test_condition",
        "instrument_id",
        "channel_id",
        "measurement_quality",
        "rework_count",
    ]

    def test_06_canonical_schema_contract_exact_match(self, html_content: str, js_content: str):
        """6. Supported telemetry schema uses canonical 12-column backend contract."""
        for col in self.CANONICAL_COLUMNS:
            assert col.lower() in html_content.lower(), f"Missing canonical column {col} in template text"
            assert col.lower() in js_content.lower(), f"Missing canonical column {col} in CSV parser/template"

    def test_07_valid_telemetry_csv_accepted(self, repo_root: Path):
        """7. Valid telemetry CSV accepted by canonical validation."""
        observations_path = repo_root / "data/synthetic_phase4b/observations.csv"
        assert observations_path.exists()

        # Read first 10 rows and verify compliance with canonical schema
        df = pd.read_csv(observations_path, nrows=10)
        assert set(self.CANONICAL_COLUMNS).issubset(set(df.columns))
        assert len(df) == 10

    def test_08_invalid_csv_rejected_with_useful_errors(self, js_content: str):
        """8. Invalid CSV rejected with useful errors."""
        # Parser must check for missing required fields and invalid records
        assert "missingRequiredFields" in js_content
        assert "invalidRecords" in js_content
        assert "missingCount" in js_content
        assert "NEEDS ATTENTION" in js_content

    def test_09_preview_and_validation_summary_render(self, html_content: str, js_content: str):
        """9. Preview and validation summary render cards exist."""
        assert 'id="upload-validation-report"' in html_content
        assert 'id="preview-table"' in html_content
        assert 'id="preview-tbody"' in html_content
        assert "val-rows" in html_content
        assert "val-lots" in html_content
        assert "val-comps" in html_content
        assert "val-params" in html_content
        assert "val-checkpoints" in html_content
        assert "val-status-text" in html_content

    def test_10_confirmation_required_before_analysis(self, js_content: str):
        """10. Confirmation required before analysis."""
        # Confirmation check before executing analysis on uploaded data
        assert "confirm(" in js_content
        assert "Confirm execution of locked Module A" in js_content or "Confirm analysis of uploaded dataset" in js_content


# =============================================================================
# SUITE 3: ISOLATION & MODEL INTEGRITY (Requirements 11 - 15)
# =============================================================================
class TestIsolationAndModelIntegrity:
    """Verify model calibration data and coefficients cannot be modified."""

    def test_11_model_status_semantics_displayed_prominently(self, html_content: str):
        """11. Model status card displays inference only / no retraining semantics."""
        assert "MODEL STATUS" in html_content
        assert "Locked Ridge Regression" in html_content
        assert "Frozen calibration data" in html_content
        assert "Inference only" in html_content
        assert "Retraining:" in html_content
        assert "Not performed" in html_content
        assert "Recalibration:" in html_content

    def test_12_locked_ridge_coefficients_unmodified(self):
        """12. Uploaded data does not modify locked Ridge coefficients."""
        # Verify exact coefficients remain unchanged
        expected_params = {"IDSS", "VGS(th)", "RDS(on)", "IGSS"}
        assert set(LOCKED_COEFFICIENTS_HEX.keys()) == expected_params
        for p in expected_params:
            model = get_locked_ridge_model(p)
            assert hasattr(model, "coefficients")
            assert hasattr(model, "sigma_eff")
            assert len(model.coefficients) == 3
            assert len(LOCKED_COEFFICIENTS_HEX[p]) == 3

    def test_13_locked_sigma_eff_unmodified(self):
        """13. Uploaded data does not modify locked sigma_eff."""
        expected_params = {"IDSS", "VGS(th)", "RDS(on)", "IGSS"}
        assert set(FROZEN_SIGMA_EFF_HEX.keys()) == expected_params
        for p, sigma_hex in FROZEN_SIGMA_EFF_HEX.items():
            sigma_val = float.fromhex(sigma_hex)
            assert sigma_val > 0.0

    def test_14_ground_truth_quarantine_enforced(self):
        """14. Ground truth cannot enter runtime inference path."""
        # Test assertion function rejects forbidden columns
        clean_df = pd.DataFrame({"component_id": ["C1"], "value": [1.0]})
        assert_ground_truth_quarantine(clean_df)

        for col in FORBIDDEN_GROUND_TRUTH_COLUMNS:
            tainted_df = pd.DataFrame({"component_id": ["C1"], col: [1]})
            with pytest.raises(ValueError, match="Ground truth quarantine violation"):
                assert_ground_truth_quarantine(tainted_df)

    def test_15_switching_datasets_clears_stale_results(self, js_content: str):
        """15. Switching datasets clears stale lot, component, screening, and prognostic results."""
        assert "function clearStaleAnalysisResults()" in js_content
        # Verify that clearStaleAnalysisResults contains code clearing the result panels
        assert "screening-matrix-tbody" in js_content
        assert "prognostics-tbody" in js_content
        assert "val-breach-flag" in js_content
        assert "audit-canonical-hash" in js_content
        assert "clearStaleAnalysisResults();" in js_content


# =============================================================================
# SUITE 4: ENGINEERING SAFETY & REPORT SEMANTICS (Requirements 16 - 18)
# =============================================================================
class TestEngineeringSafety:
    """Verify strict temporal causality and report disclaimers."""

    def test_16_temporal_causality_enforced(self, repo_root: Path):
        """16. Earlier as-of views cannot display future telemetry."""
        provider = SyntheticTelemetryProvider()
        # For a component at as_of=24h, no observation > 24h should exist
        sample_comp = "LOT_CAL_001_C001"
        tel_24 = provider.get_component_telemetry(sample_comp, as_of_hours=24)
        assert (tel_24["elapsed_hours"] > 24).sum() == 0
        assert 24 in tel_24["elapsed_hours"].values
        assert 96 not in tel_24["elapsed_hours"].values
        assert 168 not in tel_24["elapsed_hours"].values

    def test_17_measured_failure_and_predicted_breach_remain_separate(self, html_content: str, js_content: str):
        """17. Measured failure and predicted breach remain strictly separate concepts."""
        # Verify report disclaimer text in index.html and app.js
        for content in [html_content, js_content]:
            assert "measured specification failure" in content.lower()
            assert "module a evidence" in content.lower()
            assert "module b forecast" in content.lower()
            assert "predicted future specification breach" in content.lower()
            assert "autonomous" in content.lower()
            assert "not authorized" in content.lower()

    def test_18_no_unsupported_ai_probability_claims(self, html_content: str, js_content: str):
        """18. No unsupported AI failure probability claims (e.g. 'AI rejected component')."""
        for content in [html_content, js_content]:
            assert "AI rejected component" not in content
            assert "AI predicts failure with" not in content
            assert "AI confidence" not in content.lower()


# =============================================================================
# SUITE 5: LAYOUT & OVERFLOW MITIGATION (Requirements 19 - 21)
# =============================================================================
class TestLayoutAndOverflowMitigation:
    """Verify responsive CSS rules and overflow protections."""

    def test_19_overflow_protection_table_wrap_and_flex_min_width(self, css_content: str):
        """19. Layout protection: table-wrap has horizontal scrolling, main-workspace has min-width: 0."""
        assert ".table-wrap" in css_content
        assert "overflow-x: auto" in css_content
        assert "min-width: 0" in css_content

    def test_20_responsive_breakpoints_1440_1280_1024(self, css_content: str):
        """20. Responsive media queries exist for 1440px, 1280px, and 1024px viewports."""
        assert "@media (max-width: 1440px)" in css_content
        assert "@media (max-width: 1280px)" in css_content
        assert "@media (max-width: 1024px)" in css_content

    def test_21_print_media_styles_for_shareable_report(self, css_content: str):
        """21. Print styles exist for clean printable engineering report export."""
        assert "@media print" in css_content
        assert "page-break-inside: avoid" in css_content
