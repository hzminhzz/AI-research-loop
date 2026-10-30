"""Continuous campaign records Stage1 successes and keeps reviewing distinct sources."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest

from src.core.models import Evidence, EvidenceKind
from src.social_campaign import CampaignStore, run_cycle


def make_evidence(index):
    return Evidence(
        source_id=f"social_substack_post_{index}",
        kind=EvidenceKind.HISTORICAL,
        uri=f"https://tested.substack.com/p/rule-{index}",
        published_at="2024-09-01T00:00:00Z",
        available_at="2026-10-29T00:00:00Z",
        archived_at="2026-10-29T00:00:00Z",
        source_version="v1",
        snippet=f"Verified original strategy rule {index}, with entry exit and costs.",
        provider="test_public_rss",
    )


def checkout(tmp_path):
    root = tmp_path / "quant-lab"
    (root / "registry").mkdir(parents=True)
    with sqlite3.connect(root / "registry/registry.db") as db:
        db.execute(
            "CREATE TABLE selection_attempts("
            "attempt_id TEXT, hypothesis_id TEXT, contract_id TEXT, stage TEXT, strategy_module TEXT, parameters_json TEXT)"
        )
    return root


@pytest.mark.asyncio
async def test_negative_then_pass_records_and_reuses_no_sources(tmp_path):
    store = CampaignStore(tmp_path / "state")
    lab = checkout(tmp_path)
    calls, selected = [], []
    async def discover(**kwargs):
        count = len(calls)
        indices = list(range(1, 7))
        # Already consumed posts are filtered by CampaignStore.
        docs = [{"post_id": str(n)} for n in indices]
        return [make_evidence(n) for n in indices], docs, []

    async def runner(*args, **kwargs):
        idx = len(calls)
        calls.append(kwargs["source_bundle"][0][0].source_id)
        return {
            "research_id": f"fake-{idx}",
            "disposition": "STAGE_1_PASS" if idx == 1 else "STAGE_1_REJECT",
            "template_id": "dip_7d" if idx else "donchian_trend",
            "model": "test-model",
            "stage1": {"passed": idx == 1},
        }

    first = await run_cycle(
        store, lab, model=object(), social_discovery=discover, research_runner=runner,
    )
    assert first["status"] == "RESEARCH_CYCLE_COMPLETE"
    assert first["total_screened"] == 1
    second = await run_cycle(
        store, lab, model=object(), social_discovery=discover, research_runner=runner,
    )
    # A single fresh independently authored strategy is sufficient; the
    # second cycle can proceed without recycling the consumed first post.
    assert second["status"] == "STAGE_1_PASS_RECORDED_CONTINUE"
    assert len(calls) == 2
    assert calls[0] != calls[1]
    assert second["total_screened"] == 2


@pytest.mark.asyncio
async def test_successful_stage1_does_not_halt_future_cycles(tmp_path):
    store = CampaignStore(tmp_path / "state")
    lab = checkout(tmp_path)
    events = []
    async def discover(**kwargs):
        events.append("discover")
        docs = [{"post_id": str(n)} for n in range(5)]
        return [make_evidence(n) for n in range(5)], docs, []
    attempts = []
    async def runner(*args, **kwargs):
        events.append("research")
        attempts.append(kwargs["source_bundle"][0][0].source_id)
        return {
            "research_id": f"fake-run-{len(attempts)}",
            "disposition": "STAGE_1_PASS" if len(attempts) == 1 else "STAGE_1_REJECT",
            "model": "frozen", "template_id": "donchian_trend",
        }
    first = await run_cycle(store, lab, model=object(),
                            social_discovery=discover, research_runner=runner)
    assert first["status"] == "STAGE_1_PASS_RECORDED_CONTINUE"
    assert store.has_stage1_pass_history()
    second = await run_cycle(store, lab, model=object(),
                             social_discovery=discover, research_runner=runner)
    assert second["status"] == "RESEARCH_CYCLE_COMPLETE"
    assert events == ["discover", "research", "discover", "research"]
    assert attempts[0] != attempts[1]
    assert second["total_screened"] == 2
    assert second["total_passed_stage1"] == 1


@pytest.mark.asyncio
async def test_manually_stopped_and_total_budget(tmp_path):
    store = CampaignStore(tmp_path / "state")
    lab = checkout(tmp_path)
    (store.root / "STOP").touch()
    result = await run_cycle(store, lab, model=object())
    assert result["status"] == "MANUALLY_STOPPED"
    (store.root / "STOP").unlink()
    store.record({"research_id": "old", "disposition": "STAGE_1_REJECT"}, ["old"], count_sources=True)
    result = await run_cycle(store, lab, model=object(), max_screened=1)
    assert result["status"] == "READONLY_RESEARCH_BUDGET_CAP"
    assert result["total_screened"] == 1


@pytest.mark.asyncio
async def test_direct_native_source_screens_count_toward_same_lifetime_cap(tmp_path):
    """A separate guarded Research Director cannot evade the source timer cap."""
    store = CampaignStore(tmp_path / "state")
    lab = checkout(tmp_path)
    with sqlite3.connect(lab / "registry/registry.db") as db:
        db.executemany(
            "INSERT INTO selection_attempts(attempt_id,hypothesis_id,stage) VALUES(?,?,?)",
            [(f"ATT-direct-{i}", f"HYP-SOC-DIRECT-{i}", "STAGE_1_SIGNAL")
             for i in range(3)],
        )
        # Non-campaign Warden hypotheses must not use the source-campaign cap.
        db.execute("INSERT INTO selection_attempts(attempt_id,hypothesis_id,stage) "
                   "VALUES('OTHER','HYP-OTHER-1','STAGE_1_SIGNAL')")
    result = await run_cycle(store, lab, model=object(), max_screened=3)
    assert result["status"] == "READONLY_RESEARCH_BUDGET_CAP"
    assert result["total_screened"] == 0
    assert result["effective_lifetime_screened"] == 3
    assert result["total_cycles"] == 0


@pytest.mark.asyncio
async def test_unavailable_model_does_not_consume_sources(tmp_path):
    store = CampaignStore(tmp_path / "state")
    lab = checkout(tmp_path)
    async def discover(**kwargs):
        return [make_evidence(n) for n in range(5)], [{} for _ in range(5)], []
    async def runner(*args, **kwargs):
        return {"research_id": "fail-once", "disposition": "BLOCKED_MODEL"}
    result = await run_cycle(store, lab, model=object(),
                             social_discovery=discover, research_runner=runner)
    assert result["total_cycles"] == 1
    assert not store.used_sources()



@pytest.mark.asyncio
async def test_campaign_persists_ranked_health_and_deferrals_without_spending_trial(tmp_path):
    from src.tools.social_sources import SourceDiscovery

    store = CampaignStore(tmp_path / "state")
    lab = checkout(tmp_path)
    entry = make_evidence(1)
    batch = SourceDiscovery(
        eligible=[entry],
        metadata=[{"source_key": "pedma", "authenticity": "ORIGINAL_PUBLISHER_RSS_CURRENT_CAPTURE"}],
        gaps=["SOURCE_LIMITED:quantconnect_community:INDEX_ONLY_JS_RENDERED_NO_VERIFIABLE_PUBLIC_STRATEGY"],
        deferred=[{
            "source": "breakout_trading_academy",
            "url": "https://breakouttradingacademy.com/how-to-build-a-short-opening-gap-strategy/",
            "title": "Nasdaq gap strategy", "reason": "NO_CRYPTO_MARKET_CONTRACT",
        }],
        health=[
            {"source": "pedma", "status": "OK", "usable_records": 1},
            {"source": "quantconnect_community",
             "status": "INDEX_ONLY_JS_RENDERED_NO_VERIFIABLE_PUBLIC_STRATEGY",
             "usable_records": 0},
        ],
    )

    async def discover(**kwargs):
        return batch

    async def fake_runner(*args, **kwargs):
        return {"research_id": "catalog-one", "disposition": "ABSTAINED_NO_STAGE_1"}
    result = await run_cycle(store, lab, model=object(), social_discovery=discover,
                             research_runner=fake_runner)
    assert result["status"] == "RESEARCH_CYCLE_COMPLETE"
    assert result["total_screened"] == 0
    assert result["eligible_post_count"] == 1
    assert result["deferred_post_count"] == 1
    assert result["source_health"][1]["source"] == "quantconnect_community"
    catalog = json.loads((store.root / "source_catalog.json").read_text())
    assert catalog["deferred_for_other_contracts"][0]["reason"] == "NO_CRYPTO_MARKET_CONTRACT"
    assert catalog["eligible_for_crypto_contract"][0]["url"] == entry.uri



@pytest.mark.asyncio
async def test_source_only_probe_never_calls_warden_or_model(tmp_path):
    from src.social_campaign import inspect_sources_only
    from src.tools.social_sources import SourceDiscovery

    store = CampaignStore(tmp_path / "state")
    async def discover(**kwargs):
        return SourceDiscovery(
            eligible=[make_evidence(1)],
            metadata=[{"source_key": "pedma"}],
            gaps=[], deferred=[],
            health=[{"source": "pedma", "status": "OK", "usable_records": 1}],
        )
    result = await inspect_sources_only(store, social_discovery=discover)
    assert result["status"] == "SOURCE_DISCOVERY_ONLY"
    assert result["eligible_crypto"] == 1
    assert result["warden_trials_consumed"] == 0
    assert store.status()["total_cycles"] == 0
    assert store.status()["total_screened"] == 0
