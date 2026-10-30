"""Batch 5 is source evidence only, not an executable Warden campaign."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "examples/THESIS_FACTORY_20261031_BATCH5.json"


def test_batch5_pinned_distinct_not_scientific_results():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    cards = report["cards"]
    assert len(cards) == report["results"]["new_source_mechanism_cards"] == 10
    ids = [card["id"] for card in cards]
    urls = [card["source_url"] for card in cards]
    sha = [card["source_blob_sha1"] for card in cards]
    assert len(set(ids)) == len(set(urls)) == len(set(sha)) == 10
    assert all(re.fullmatch(r"[0-9a-f]{40}", value) for value in sha)
    assert all(card["source_revision"] == "f3340ce11f5bdf62f598522e64d1f5638eaa13f5" for card in cards)
    assert all(card["source_url"].startswith("https://github.com/freqtrade/freqtrade-strategies/blob/") for card in cards)
    assert all(card["expected_holding_bars"] is None for card in cards)
    assert all(card["status"] == "BLOCKED_PREFLIGHT_NOT_REGISTERED_NOT_SCREENED" for card in cards)
    assert all(not card["warden_registration"] and not card["causal_verified"] and not card["stage1_screened"] for card in cards)
    for key in ("registered", "verified", "native_stage1_screened", "passed", "rejected", "full_trials", "holdout_reads", "live_orders"):
        assert report["results"][key] == 0
    assert report["results"]["blocked_before_screen"] == 10


def test_batch5_distinct_from_prior_batches_and_budget_accounted():
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    prior = "\n".join((ROOT / f"examples/THESIS_FACTORY_20261031_BATCH{i}.json").read_text(encoding="utf-8")
                      for i in range(1, 5))
    for card in report["cards"]:
        assert card["source_url"] not in prior
        assert card["native_contract_for_eligibility_check"] in {
            "CRYPTO_PERPS_1H_V2",
            "CRYPTO_PERPS_5M_V1",
            "AUTO_CRYPTO_PERPS_TOP100_1H_V1_H24_E24_F45_S20_V1",
        }
    gov = report["governance"]
    assert gov["effective_lifetime_consumed"] == max(gov["native_source_screens"], gov["private_campaign_source_screens"])
    assert gov["remaining_max"] == gov["lifetime_cap"] - gov["effective_lifetime_consumed"]
    assert gov["registry_hypotheses_before"] == gov["registry_hypotheses_after"]
    assert gov["registry_full_trials_before"] == gov["registry_full_trials_after"]
    assert gov["registry_selection_attempts_before"] == gov["registry_selection_attempts_after"]
