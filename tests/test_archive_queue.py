"""Durable archive queue is review-only; scientific outcomes live in Warden."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.workflow.archive_queue import (
    backlog, mark_review, _archive_rows, VALID_REVIEW_STATES,
)


def row(number: int, provider: str, *, kind: str = "ARTICLE", sha=None) -> dict:
    identifier = format(number, "020x")
    return {
        "id": identifier,
        "title": f"Test Source {number}",
        "source_key": provider,
        "url": f"https://publisher.example/p/{number}",
        "content_sha256": sha or format(number, "064x"),
        "market": "fx" if number % 2 else "indices",
        "family": "mean_reversion",
        "rule_state": "PARTIAL_RULES",
        "data_state": "MARKET_TIMEFRAME_REVIEW",
        "source_kind": kind,
    }


def project(tmp_path: Path):
    repo = tmp_path / "project"
    (repo / "runs/archive_discovery").mkdir(parents=True)
    (repo / "examples/research_batch_20261030").mkdir(parents=True)
    (repo / "examples/practitioner_archive_20261030").mkdir(parents=True)
    archive = [row(1, "alpha"), row(2, "alpha"), row(3, "bravo"),
               row(4, "charlie"), row(5, "bravo")]
    (repo / "runs/archive_discovery/shortlist.json").write_text(json.dumps(archive))
    (repo / "examples/research_batch_20261030/candidate_state.json").write_text(
        json.dumps({"completed": [{
            "source": archive[1]["url"], "verdict": "STAGE_1_REJECT",
        }]}))
    return repo, archive


def test_diverse_backlog_and_historical_screened_variants_not_replayed(tmp_path):
    repo, rows = project(tmp_path)
    state = tmp_path / "state"
    first = backlog(repo, state, limit=4)
    assert first["total_source_leads"] == 5
    assert first["actionable_review_leads"] == 5
    assert [x["source_key"] for x in first["next_leads"][:3]] == [
        "alpha", "bravo", "charlie",
    ]
    assert len(first["next_leads"]) == 4
    assert first["next_leads"][-1]["id"] != rows[1]["id"]
    assert first["existing_source_variant_rejections"] == 1
    assert first["scope"] == "DISCOVERY_ONLY; WARDEN_REGISTRY_AUTHORITATIVE"


def test_append_only_review_state_and_duplicate_idempotency(tmp_path):
    repo, rows = project(tmp_path)
    state = tmp_path / "state"
    key = rows[0]["id"]
    evidence = "Original author uses ETF fill at close; no CFD fill adapter verified"
    out = mark_review(repo, state, source_id=key,
                      status="BLOCKED_EXECUTION", evidence=evidence)
    assert out["status"] == "BLOCKED_EXECUTION"
    again = mark_review(repo, state, source_id=key,
                        status="BLOCKED_EXECUTION", evidence=evidence)
    assert again["status"] == "UNCHANGED_REVIEW"
    record = backlog(repo, state)
    assert record["progress_events"] == 1
    assert record["deferred_leads"] == 1
    assert record["deferred_preview"][0]["id"] == key

    mark_review(repo, state, source_id=key, status="REVIEW_IN_PROGRESS",
                evidence="New source rule excerpt captured and checked against original article")
    record = backlog(repo, state)
    assert record["progress_events"] == 2
    assert record["deferred_leads"] == 0
    assert [event["status"] for event in json.loads(
        (state / "archive_progress.json").read_text())["events"]] == [
            "BLOCKED_EXECUTION", "REVIEW_IN_PROGRESS",
        ]


@pytest.mark.parametrize("status", [
    "STAGE_1_PASS", "STAGE_1_REJECT", "APPROVED_FOR_TRADING",
    "REPLENISH_BUDGET",
])
def test_review_queue_never_claims_warden_verdict_or_replenishes(status, tmp_path):
    repo, rows = project(tmp_path)
    with pytest.raises(ValueError, match="non-scientific"):
        mark_review(repo, tmp_path / "state", source_id=rows[0]["id"],
                    status=status, evidence="Paper author text verified")


def test_unknown_source_and_missing_evidence_refused(tmp_path):
    repo, rows = project(tmp_path)
    with pytest.raises(ValueError, match="Unknown"):
        mark_review(repo, tmp_path / "state", source_id="0" * 20,
                    status="BLOCKED_DATA", evidence="Need historical FX swap series")
    with pytest.raises(ValueError, match="evidence"):
        mark_review(repo, tmp_path / "state", source_id=rows[0]["id"],
                    status="BLOCKED_DATA", evidence="small")


def test_new_source_capture_reopens_review_without_erasing_history(tmp_path):
    repo, rows = project(tmp_path)
    mark_review(repo, tmp_path / "state", source_id=rows[0]["id"],
                status="BLOCKED_AUTHOR_RULES",
                evidence="The original source did not describe any exit")
    archive = json.loads((repo / "runs/archive_discovery/shortlist.json").read_text())
    archive[0]["content_sha256"] = "a" * 64
    (repo / "runs/archive_discovery/shortlist.json").write_text(json.dumps(archive))
    latest = backlog(repo, tmp_path / "state")
    assert latest["progress_events"] == 1
    assert latest["deferred_leads"] == 0
    assert any(x["id"] == rows[0]["id"] and x["review_state"] == "UNREVIEWED"
               for x in latest["next_leads"])


def test_corrupt_current_archive_falls_back_to_complete_snapshot(tmp_path):
    repo, rows = project(tmp_path)
    (repo / "runs/archive_discovery/shortlist.json").write_text(
        "[\n{'truncated': yes}\n[Showing lines 1-500...]")
    (repo / "examples/practitioner_archive_20261030/shortlist.json").write_text(
        json.dumps(rows))
    state = backlog(repo, tmp_path / "state")
    assert state["total_source_leads"] == 5
    assert state["catalog_path"].startswith("examples/")


def test_pinned_code_sha1_is_not_misrepresented_as_sha256(tmp_path):
    repo, rows = project(tmp_path)
    pinned = row(6, "cloudquant_backtrader", kind="PINNED_CODE_TEST", sha="b" * 40)
    pinned["url"] = ("https://github.com/cloudQuant/backtrader/blob/" +
                     "a" * 40 + "/tests/test_strategy.py")
    pinned["source_revision"] = "a" * 40
    rows.append(pinned)
    (repo / "runs/archive_discovery/shortlist.json").write_text(json.dumps(rows))
    result = backlog(repo, tmp_path / "state", limit=10)
    selected = next(x for x in result["next_leads"] if x["id"] == pinned["id"])
    assert selected["source_fingerprint_kind"] == "GIT_BLOB_SHA1"
    assert len(selected["source_fingerprint"]) == 40
    assert result["total_source_leads"] == 6


def test_actual_retained_snapshot_has_50_parseable_sources():
    repo = Path(__file__).resolve().parents[1]
    rows, path = _archive_rows(repo)
    assert path.endswith("shortlist.json")
    assert len(rows) == 50


@pytest.mark.asyncio
async def test_empty_feed_triggers_archive_review_not_global_termination(tmp_path):
    from src.social_campaign import CampaignStore, run_cycle

    repo, rows = project(tmp_path)
    lab = tmp_path / "quant-lab"
    (lab / "registry").mkdir(parents=True)
    import sqlite3
    with sqlite3.connect(lab / "registry/registry.db") as db:
        db.execute("CREATE TABLE selection_attempts("
                   "attempt_id TEXT, contract_id TEXT, stage TEXT, "
                   "strategy_module TEXT, parameters_json TEXT)")

    async def no_new_posts(**kwargs):
        return [], [], ["UPSTREAM_FEED_EMPTY"]

    # Explicitly isolate archive project for a synthetic data fixture.
    # The production campaign resolves the installed repo and sees its
    # saved bundle; fallback need not execute a fake Warden runner.
    state = await run_cycle(CampaignStore(tmp_path / "state"), lab, model=object(),
                            social_discovery=no_new_posts)
    assert state["status"] in ("ARCHIVE_REVIEW_REQUIRED", "PAUSED_DAILY_QUOTA")
    assert "archive_backlog" in state
    assert "warden_trials_consumed" not in state


@pytest.mark.asyncio
async def test_continuous_polling_only_ends_for_explicit_stop(monkeypatch, tmp_path):
    import src.social_campaign as campaign

    snapshots = [
        {"status": "STAGE_1_PASS_RECORDED_CONTINUE"},
        {"status": "RESEARCH_CYCLE_COMPLETE"},
        {"status": "MANUALLY_STOPPED"},
    ]
    calls = []
    async def fake_run_cycle(*args, **kwargs):
        calls.append(1)
        return snapshots[len(calls)-1]
    async def fast_sleep(seconds):
        assert seconds >= 300

    monkeypatch.setattr(campaign, "run_cycle", fake_run_cycle)
    monkeypatch.setattr(campaign.asyncio, "sleep", fast_sleep)
    await campaign.run_continuously(
        object(), Path("/tmp/test-checkout"), interval_seconds=300)
    assert len(calls) == 3
