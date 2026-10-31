from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mt5_batch17_has_ten_source_cards_and_no_fake_trials():
    record = json.loads(
        (ROOT / "examples/MT5_SOURCE_RESEARCH_20261031_BATCH17.json").read_text(
            encoding="utf-8"
        )
    )
    assert record["batch_id"] == "MT5-SOURCE-20261031-B17"
    assert len(record["source_cards"]) == 10
    warden = record["warden"]
    assert warden["new_registrations"] == 0
    assert warden["causal_verifies"] == 0
    assert warden["stage1_screens"] == 0
    assert warden["stage3_runs"] == 0
    assert warden["holdout_reads"] == 0
    assert warden["orders"] == 0
    assert record["preflight_results"]["btc_altcoin_leadlag"]["status"] == "BLOCKED_DIRECTION"
    assert record["preflight_results"]["weekend_gap_daily_index"]["validation_signals"] == 19


def test_mql5_batch17_report_separates_source_blockers_from_scientific_rejects():
    report = (ROOT / "examples/MT5_SOURCE_RESEARCH_20261031_BATCH17.md").read_text(
        encoding="utf-8"
    )
    assert "not ten Warden hypotheses" in report
    assert "BLOCKED_SOURCE" in report
    assert "not independent evidence" in report
    assert "do not invert" in report
    assert "daily US-equities data contract" in report
