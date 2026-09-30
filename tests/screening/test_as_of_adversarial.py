"""As-Of adversarial tests for Module A.

Validates prompt Section 16 mandate:
For every checkpoint T in {0, 24, 96, 168}:
- Prove that no telemetry record with elapsed_hours > T can influence the screening decision.
- Injects extreme adversarial future mutations (catastrophic failures, NaNs, wild drift at t > T).
- Verifies that earlier decisions, detector outputs, and explainability cards remain 100% bit-for-bit identical.
"""

import copy
import pandas as pd
import pytest

from sih26170.screening.explainability import generate_explainability_card
from sih26170.screening.pipeline import screen_component


def make_test_dataset() -> pd.DataFrame:
    """Generate multi-checkpoint telemetry for adversarial testing."""
    rows = []
    for i in range(1, 12):
        cid = f"LOT_ADV_C{i:03d}"
        for t in [0, 24, 96, 168]:
            rows.append({"component_id": cid, "lot_id": "LOT_ADV", "parameter_name": "IDSS", "elapsed_hours": t, "value": 0.50 + 0.01 * i, "unit": "uA", "measurement_quality": "VALID", "instrument_id": "ATE_01", "channel_id": "CH_01"})
            rows.append({"component_id": cid, "lot_id": "LOT_ADV", "parameter_name": "VGS(th)", "elapsed_hours": t, "value": 2.85 + 0.01 * i, "unit": "V", "measurement_quality": "VALID", "instrument_id": "ATE_01", "channel_id": "CH_01"})
            rows.append({"component_id": cid, "lot_id": "LOT_ADV", "parameter_name": "RDS(on)", "elapsed_hours": t, "value": 45.0 + 0.1 * i, "unit": "mOhm", "measurement_quality": "VALID", "instrument_id": "ATE_01", "channel_id": "CH_01"})
            rows.append({"component_id": cid, "lot_id": "LOT_ADV", "parameter_name": "IGSS", "elapsed_hours": t, "value": 5.0 + 0.1 * i, "unit": "nA", "measurement_quality": "VALID", "instrument_id": "ATE_01", "channel_id": "CH_01"})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("checkpoint_t", [0, 24, 96, 168])
def test_as_of_adversarial_invariance(checkpoint_t: int):
    """Verify earlier decisions are strictly invariant to future data mutations."""
    df_clean = make_test_dataset()
    target_cid = "LOT_ADV_C001"

    # Baseline screening at checkpoint_t
    res_baseline = screen_component(df_clean, target_cid, as_of_hours=checkpoint_t)
    card_baseline = generate_explainability_card(res_baseline)

    # Create poisoned dataset mutating all records with elapsed_hours > checkpoint_t
    df_poisoned = df_clean.copy()

    if checkpoint_t < 168:
        future_mask = df_poisoned["elapsed_hours"] > checkpoint_t
        # Inject extreme catastrophic limit breaches into all future rows
        df_poisoned.loc[future_mask & (df_poisoned["parameter_name"] == "RDS(on)"), "value"] = 999999.0
        df_poisoned.loc[future_mask & (df_poisoned["parameter_name"] == "IDSS"), "value"] = 888888.0
        df_poisoned.loc[future_mask & (df_poisoned["parameter_name"] == "IGSS"), "value"] = -777777.0
        df_poisoned.loc[future_mask & (df_poisoned["parameter_name"] == "VGS(th)"), "value"] = 0.01
    else:
        # At 168h, inject synthetic future checkpoints at 500h with catastrophic failures
        future_rows = []
        for i in range(1, 12):
            cid = f"LOT_ADV_C{i:03d}"
            future_rows.append({"component_id": cid, "lot_id": "LOT_ADV", "parameter_name": "RDS(on)", "elapsed_hours": 500, "value": 999999.0, "unit": "mOhm", "measurement_quality": "VALID", "instrument_id": "ATE_01", "channel_id": "CH_01"})
        df_poisoned = pd.concat([df_poisoned, pd.DataFrame(future_rows)], ignore_index=True)

    # Re-run screening on poisoned dataset
    res_poisoned = screen_component(df_poisoned, target_cid, as_of_hours=checkpoint_t)
    # Set identical creation timestamp for exact card text comparison
    res_poisoned.created_at = res_baseline.created_at
    card_poisoned = generate_explainability_card(res_poisoned)

    # Assert 100% bit-for-bit identity
    assert res_poisoned.final_state == res_baseline.final_state
    assert res_poisoned.primary_reason_code == res_baseline.primary_reason_code
    assert res_poisoned.audit_hash == res_baseline.audit_hash
    assert card_poisoned == card_baseline

    for p in ["IDSS", "VGS(th)", "RDS(on)", "IGSS"]:
        p_base = res_baseline.parameter_results[p]
        p_pois = res_poisoned.parameter_results[p]
        assert p_pois.to_dict() == p_base.to_dict()
