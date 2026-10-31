"""Batch15 source evidence schema and scientific-claim guardrails.

No protected data, Warden CLI, registry or network reads.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "examples/THESIS_FACTORY_20261031_BATCH15.json"


def test_batch15_cards_are_distinct_source_backed_and_preflight_blocked():
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    cards = document["cards"]
    assert len(cards) == 10
    assert len({card["id"] for card in cards}) == len(cards)
    assert len({card["independent_mechanism"] for card in cards}) == len(cards)
    assert document["source_accounting"]["source_repository_count"] == 3
    for card in cards:
        assert card["source"]["kind"]
        assert card["source"].get("original_url", "").startswith("https://")
        assert card["economic_rationale"]
        assert card["counterparty"]
        assert card["original_source_rules"]["closed_bar_signal"]
        assert card["original_source_rules"]["entry"]
        assert card["original_source_rules"]["exit"]
        assert card["original_source_rules"]["sizing"]
        assert card["original_source_rules"]["holding_label"]
        assert card["proposed_adaptation"]["difference_from_source"]
        assert card["cost_model"]
        assert card["baseline"]
        assert card["falsification"]
        assert card["source_selection_history"]
        assert card["pit_controls"]
        assert card["preflight"]["status"].startswith("BLOCKED_")
        assert card["registered"] is False
        assert card["causal_verified"] is False
        assert card["native_stage1_screened"] is False
        assert card["warden_verdict"] is None


def test_batch15_immutable_capture_provenance_and_rejection_invariants():
    document = json.loads(REPORT.read_text(encoding="utf-8"))
    card_sources = [card["source"] for card in document["cards"]]
    for source in card_sources:
        assert source["captured_at_utc"]
        if source["kind"] == "ORIGINAL_PUBLISHER_HTML_SHA256":
            assert len(source["content_sha256"]) == 64
        else:
            git_sha = source.get("commit") or source.get("git_commit_sha")
            blob_sha = source.get("blob_sha1") or source.get("code_blob_sha1")
            assert len(git_sha or "") == 40
            assert len(blob_sha or "") == 40
    end = document["warden_end"]
    assert end["registrations"] == end["verifies"] == end["native_stage1_screens"] == 0
    assert end["passes"] == end["rejections"] == end["stage3"] == 0
    assert end["holdout_reads"] == end["orders"] == 0
    assert end["hypotheses"] == document["warden_start"]["hypotheses"]
    assert end["full_trials"] == document["warden_start"]["full_trials"]
    assert end["selection_attempts"] == document["warden_start"]["selection_attempts"]
    assert end["source_budget_remaining_at_most"] <= 8
    assert document["fx_midpoint_policy"]["active_native_contract"] is False
    assert document["fx_midpoint_policy"]["principal_approved"] is True
