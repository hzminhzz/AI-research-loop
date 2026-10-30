"""Frozen Batch 4 source-preflight evidence, not an executable trading test."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "examples/THESIS_FACTORY_20261031_BATCH4.json"


def test_batch4_records_ten_unique_unregistered_mechanisms():
    data = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    cards = data["cards"]
    assert data["schema"] == "THESIS_FACTORY_SOURCE_PREFLIGHT_V2"
    assert len(cards) == data["results"]["mechanism_cards"] == 10
    assert len({c["id"] for c in cards}) == len(cards)
    assert len({c["source"]["url"] for c in cards}) == len(cards)
    assert all(c["blocker"].startswith("BLOCKED") for c in cards)
    assert all(c["scientific_status"] == "BLOCKED_SOURCE_ONLY_NOT_A_WARDEN_VERDICT" for c in cards)
    assert all(not c["stage0_registered"] and not c["causal_verified"]
               and not c["native_stage1_screened"] for c in cards)
    assert data["results"]["native_stage1_screened"] == 0
    assert data["results"]["stage1_rejections"] == 0
    assert data["results"]["stage1_passes"] == 0
    assert data["results"]["blocked_before_screen"] == 10


def test_batch4_sources_have_captured_fingerprints_and_no_prior_card_reuse():
    data = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    prior = "\n".join(
        (ROOT / f"examples/THESIS_FACTORY_20261031_BATCH{i}.json")
        .read_text(encoding="utf-8")
        for i in (1, 2, 3)
    )
    for card in data["cards"]:
        src = card["source"]
        expected = 40 if src["fingerprint_algorithm"] == "GIT_BLOB_SHA1" else 64
        assert re.fullmatch(r"[0-9a-f]{" + str(expected) + r"}", src["fingerprint"])
        assert src["url"].startswith("https://")
        assert src["url"] not in prior
        assert datetime.fromisoformat(src["published_at"].replace("Z", "+00:00")) <= (
            datetime.fromisoformat(src["captured_at"].replace("Z", "+00:00")))
        assert not src["historical_text_vintage_verified"]
        assert card["original_entry"] and card["original_exit"]
        assert card["costs"] and card["causality"] and card["next_action"]


def test_batch4_budget_is_static_checkpoint_not_new_spending():
    data = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    guard = data["live_governance"]
    assert guard["effective_consumed"] == max(
        guard["source_family_native_count"], guard["private_campaign_count"])
    assert guard["remaining"] == guard["lifetime_cap"] - guard["effective_consumed"]
    assert guard["lifetime_cap"] == 20
    assert data["results"]["protected_holdout_reads"] == 0
    assert data["results"]["broker_orders"] == 0
