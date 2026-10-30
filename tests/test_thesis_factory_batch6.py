"""Scientific checkpoint contract: source-only leads are not native screens."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "examples" / "THESIS_FACTORY_20261031_BATCH6.json"


def test_batch6_persists_only_one_genuine_screen():
    batch = json.loads(REPORT.read_text(encoding="utf-8"))
    metrics = batch["results"]
    assert metrics == {
        "mechanism_cards": 10, "preregistered": 1, "verified": 1,
        "native_stage1_screened": 1, "stage1_pass": 0, "stage1_reject": 1,
        "source_only_blocked": 9, "stage3_trials": 0,
        "holdout_reads": 0, "live_orders": 0,
    }
    assert len(batch["cards"]) == 10
    assert len({card["id"] for card in batch["cards"]}) == 10
    assert all(len(card["source_http_body_sha256"]) == 64 for card in batch["cards"])
    screened = [card for card in batch["cards"] if card["native_stage1_screened"]]
    assert len(screened) == 1
    assert screened[0]["attempt_id"] == "ATT-40545e258d2c604a-001"
    assert screened[0]["status"] == "STAGE1_REJECT_FROZEN"
    for card in batch["cards"]:
        assert card["source_url"].startswith("https://")
        assert card["original_entry"] and card["original_exit"]
        assert card["mechanism"] and card["falsification"]
        if card is not screened[0]:
            assert card["status"] == "BLOCKED_SOURCE_ONLY_NOT_REGISTERED"
            assert card["attempt_id"] is None
            assert not card["preregistered"] and not card["verified"]
    before = batch["governance"]["registry_before"]
    after = batch["governance"]["registry_after"]
    assert after["hypotheses"] == before["hypotheses"] + 1
    assert after["selection_attempts"] == before["selection_attempts"] + 1
    assert after["full_trials"] == before["full_trials"]
    assert after["source_screens"] == before["source_screens"] + 1
    assert batch["governance"]["remaining_max"] == 10


def test_prior_checkpoints_retained():
    batch = json.loads(REPORT.read_text(encoding="utf-8"))
    for path in batch["prerequisite_checkpoints"]:
        assert (ROOT / path).is_file()
