"""Frozen original-source research result has a real Warden receipt and no false alpha.

Source artifacts are research-only; no Warden or live registry access.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/STRATEGY_RESEARCH_20261031_WBX_DOWNSHOCK.md"
RESULT = ROOT / "examples/STRATEGY_RESEARCH_20261031_WBX_DOWNSHOCK_RESULT.json"
REPORT = ROOT / "examples/STRATEGY_RESEARCH_20261031_WBX_DOWNSHOCK_RESULT.md"


def test_source_rule_frozen_before_validation():
    source = SOURCE.read_text(encoding="utf-8")
    record = json.loads(RESULT.read_text(encoding="utf-8"))
    assert record["preregistration"]["git_sha"] == "1c8a95a"
    assert record["preregistration"]["is_original_source_trading_rule"] is False
    assert record["preregistration"]["html_capture_sha256"] in source
    for term in ("BTCUSDT", "ETHUSDT", "LTCUSDT", "XRPUSDT"):
        assert term in source
    assert "2022" in source
    assert "72" in source
    assert "13bps roundtrip" in source
    assert "independent author adaptation" in source
    assert "before reading any conditional return" in source


def test_one_native_screen_and_negative_frozen_outcome():
    d = json.loads(RESULT.read_text(encoding="utf-8"))
    w = d["warden"]
    m = w["screen_metrics"]
    assert d["status"] == "NATIVE_STAGE1_REJECT_FROZEN"
    assert w["source_screen_id"] == "ATT-31fddf3942a229ee-001"
    assert w["outcome"] == "REJECT"
    assert m["profit_factor"] < w["native_thresholds"]["profit_factor_min"]
    assert m["bootstrap_p_value"] < w["native_thresholds"]["bootstrap_p_max_exclusive"]
    assert m["time_in_market"] > w["native_thresholds"]["time_in_market_min"]
    assert w["full_trials_before"] == w["full_trials_after"] == 72
    assert w["selection_attempts_after"] == w["selection_attempts_before"] + 1
    assert (w["source_campaign_before"], w["source_campaign_after"]) == (
        "12/20", "13/20"
    )
    assert w["native_source_budget_remaining"] == 7
    assert w["stage3_run"] is w["holdout_read"] is w["orders"] is False
    assert d["files"]["quant_candidate_committed"] is False
    assert d["files"]["quant_candidate_deployed"] is False
    assert "NOT a reproduction" not in REPORT.read_text(encoding="utf-8")


def test_source_negative_provenance_and_leakage_caveats_present():
    d = json.loads(RESULT.read_text(encoding="utf-8"))
    assert d["warden"]["prefix_verification"]["result"] == "PASS"
    assert d["warden"]["prefix_verification"]["rows"] == 87552
    assert len(d["files"]["strategy_sha256"]) == 64
    assert len(d["files"]["experiment_sha256"]) == 64
    notes = " ".join(d["caveats"])
    for phrase in ("source", "gross", "multiple", "4h", "tick"):
        assert phrase.lower() in notes.lower()
