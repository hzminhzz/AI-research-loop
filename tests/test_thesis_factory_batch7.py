"""Batch 7 frozen source-evidence and Warden disposition contract."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B7 = ROOT / "examples/THESIS_FACTORY_20261031_BATCH7.json"


def _load() -> dict:
    return json.loads(B7.read_text(encoding="utf-8"))


def test_batch7_research_counts_and_immutable_receipt():
    data = _load()
    s = data["results"]
    assert s == {
        "distinct_new_mechanism_cards": 10,
        "stage0_registered": 1,
        "causal_verified": 1,
        "native_stage1_screened": 1,
        "stage1_passes": 0,
        "stage1_rejections": 1,
        "blocked_before_screen": 9,
        "new_full_stage3_trials": 0,
    }
    attempts = [c for c in data["cards"] if c["native_stage1_screened"]]
    assert len(attempts) == 1
    assert attempts[0]["id"] == "HYP-SOC-TV-BTC-2123-20261031"
    assert attempts[0]["native_attempt_id"] == "ATT-5657f0c12d4653af-001"
    assert attempts[0]["status"] == "STAGE1_REJECT_FROZEN"
    assert attempts[0]["metrics"]["profit_factor"] < 1.15
    assert data["governance"]["effective_consumed"] == 11
    assert data["governance"]["remaining"] == 9
    assert data["governance"]["registry_after"]["selection_attempts"] == 182


def test_batch7_source_rules_are_explicit_and_originals_unique():
    cards = _load()["cards"]
    assert len(cards) == 10
    assert len({x["id"] for x in cards}) == 10
    assert len({x["source_url"] for x in cards}) == 10
    for card in cards:
        assert card["source_url"].startswith("https://")
        assert re.fullmatch(r"[0-9a-f]{64}", card["source_sha256"])
        for field in (
            "mechanism", "counterparty", "source_rules", "research_adaptation",
            "signal_clock", "costs", "baseline", "source_side_selection",
            "preflight", "status", "falsification", "next_action",
            "points_in_time", "source_capture_kind",
        ):
            assert card[field], f"{card['id']}: missing {field}"
        for key in ("entry", "exit", "size"):
            assert key in card["source_rules"]
            assert key in card["research_adaptation"]
        if card["status"].startswith("BLOCKED"):
            assert not card["stage0_registered"]
            assert not card["causal_verified"]
            assert not card["native_stage1_screened"]


def test_batch7_new_ids_and_source_code_leakage_are_disclosed():
    data = _load()
    earlier = set()
    for i in range(1, 7):
        batch = json.loads(
            (ROOT / f"examples/THESIS_FACTORY_20261031_BATCH{i}.json").read_text(
                encoding="utf-8",
            ),
        )
        earlier.update(x["id"] for x in batch.get("cards", batch.get("candidates", [])))
    assert not earlier.intersection(c["id"] for c in data["cards"])
    finding = data["quality_findings"][0]
    assert finding["severity"] == "HIGH"
    assert "i+49" in finding["finding"]
    assert "i+19" in finding["finding"]
    assert data["governance"]["no_holdout_reads"]
    assert data["governance"]["no_live_orders"]
