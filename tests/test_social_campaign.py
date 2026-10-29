"""Continuous campaign stops on Stage 1 pass, never reuses consumed posts or trial budgets."""
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
            "attempt_id TEXT, contract_id TEXT, stage TEXT, strategy_module TEXT, parameters_json TEXT)"
        )
    return root


@pytest.mark.asyncio
async def test_negative_then_pass_stops_and_reuses_no_sources(tmp_path):
    store = CampaignStore(tmp_path / "state")
    lab = checkout(tmp_path)
    calls, selected = [], []
    async def discover(**kwargs):
        count = len(calls)
        indices = list(range(1, 7))
        # Already consumed posts are filtered by CampaignStore.
        docs = [{"post_id": str(n)} for n in indices]
        return [make_evidence(n) for n in indices], docs, ["X_AUTH_REQUIRED"]

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
    # Only one new source remains, so second cycle should wait instead of reusing posts.
    assert second["status"] == "WAITING_NEW_VERIFIED_POSTS"
    assert len(calls) == 1
    assert second["total_screened"] == 1


@pytest.mark.asyncio
async def test_successful_stage1_halts_future_cycles(tmp_path):
    store = CampaignStore(tmp_path / "state")
    lab = checkout(tmp_path)
    events = []
    async def discover(**kwargs):
        events.append("discover")
        docs = [{"post_id": str(n)} for n in range(5)]
        return [make_evidence(n) for n in range(5)], docs, []
    async def runner(*args, **kwargs):
        events.append("research")
        return {
            "research_id": "fake-winner", "disposition": "STAGE_1_PASS",
            "model": "frozen", "template_id": "donchian_trend",
        }
    first = await run_cycle(store, lab, model=object(),
                            social_discovery=discover, research_runner=runner)
    assert first["status"] == "STAGE_1_PASS_STOPPED"
    second = await run_cycle(store, lab, model=object(),
                             social_discovery=discover, research_runner=runner)
    assert second["status"] == "STAGE_1_PASS_STOPPED"
    assert events == ["discover", "research"]
    assert second["total_screened"] == 1


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
    assert result["status"] == "SCIENTIFIC_BUDGET_EXHAUSTED"


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
