import json

import pytest
from pydantic import ValidationError

from src.workflow.registry import StrategyThesis
from src.workflow.warden import WardenHandoff, export_warden_hypothesis


def thesis():
    return StrategyThesis(
        thesis_id="HYP-AI-001", market="Binance perps",
        mechanism="Momentum may persist because investors chase recent winners.",
        universe=["BTCUSDT", "ETHUSDT"], timeframe="1h",
        decision_lag_bars=1, expected_holding_bars=48,
        cost_assumptions="6 basis points round trip plus funding",
        falsification_criteria=["Reject if HAC t < 2", "Reject if net Sharpe < 0"],
        data_cutoff="2026-01-15", parent_forecast_ids=["forecast-001"],
    )


def mapping():
    return WardenHandoff(
        contract_id="CRYPTO_PERPS_TOP100_1H_V1",
        strategy_family="rules_ts",
        counterparty_or_friction="Momentum buyers pay spread, slippage and funding",
        source_provenance="Agent research data captured and timestamped at source",
        llm_model_id="research-model-v1",
    )


def test_handoff_exports_warden_native_fields_immutably(tmp_path):
    out = export_warden_hypothesis(thesis(), mapping(), tmp_path)
    text = out.read_text(encoding="utf-8")
    assert 'hypothesis_id: "HYP-AI-001"' in text
    assert '"rules_ts"' in text
    assert 'expected_holding_bars: 48' in text
    assert 'source_provenance' in text and 'forecast-001' in text
    assert 'economic_mechanism' in text and 'falsification_criteria' in text
    with pytest.raises(FileExistsError):
        export_warden_hypothesis(thesis(), mapping(), tmp_path)
    try:
        import yaml
    except ImportError:
        return
    payload = yaml.safe_load(text)
    assert payload["contract_id"] == "CRYPTO_PERPS_TOP100_1H_V1"
    assert payload["parent_hypothesis_id"] is None


def test_handoff_rejects_shallow_mechanisms(tmp_path):
    t = thesis().model_copy(update={"mechanism": "Too short"})
    with pytest.raises(ValueError, match="Warden requires"):
        export_warden_hypothesis(t, mapping(), tmp_path)
