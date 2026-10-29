import hashlib
import json

import pytest
from pydantic import ValidationError

from src.core.models import AgentState
from src.harness.engine import ReActEngine
from src.harness.model import DeterministicDemoModel
from src.harness.replay import replay_run
from src.metrics import ResolvedForecast, score
from src.tools.archive import ArchivedCatalog
from src.tools.pit import PITGateway, PITRequest, PITViolation

CUTOFF = "2026-01-15T00:00:00Z"


def record(source_id, archived_at="2026-01-05T00:00:00Z"):
    return {
        "source_id": source_id, "kind": "historical",
        "uri": f"https://example.org/{source_id}",
        "published_at": "2026-01-01T00:00:00Z",
        "available_at": "2026-01-02T00:00:00Z",
        "archived_at": archived_at,
        "source_version": "release-v1",
        "snippet": f"historical base rate {source_id}",
        "provider": "verified_archive",
    }


def create_archive(path, rows):
    raw = json.dumps(rows).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.mark.asyncio
async def test_archive_filters_future_captures_and_pins_hash(tmp_path):
    path = tmp_path / "archive.json"
    sha = create_archive(path, [record("eligible"), record("future", "2026-01-16T00:00:00Z")])
    archive = ArchivedCatalog(path, sha)
    gateway = PITGateway(
        {"web_search": archive.query}, require_archive=True, source_digest=archive.sha256
    )
    from datetime import datetime
    rows = await gateway.execute(
        "web_search", {"query": "historical base rate"}, datetime.fromisoformat(CUTOFF.replace("Z", "+00:00"))
    )
    assert [x.source_id for x in rows] == ["eligible"]
    with pytest.raises(ValueError, match="SHA-256"):
        ArchivedCatalog(path, "0" * 64)


def test_archive_rejects_unversioned_records(tmp_path):
    path = tmp_path / "archive.json"
    item = record("broken")
    item.pop("source_version")
    digest = create_archive(path, [item])
    with pytest.raises(PITViolation):
        ArchivedCatalog(path, digest)


@pytest.mark.asyncio
async def test_frozen_replay_matches_original_without_external_access(tmp_path):
    async def provider(_):
        item = record("eligible")
        # Demo gateway accepts versioned sources as well.
        return [item]
    state = AgentState(
        run_id="replay-original", question="Will this event resolve positively?",
        as_of_date=CUTOFF, cutoff_date=CUTOFF,
    )
    original = await ReActEngine(
        DeterministicDemoModel(), PITGateway({"web_search": provider}),
        tmp_path / "originals",
    ).run(state)
    reproduced = await replay_run(
        tmp_path / "originals" / "replay-original", tmp_path / "replayed",
    )
    assert reproduced == original


@pytest.mark.asyncio
async def test_replay_rejects_tampered_trace(tmp_path):
    async def provider(_):
        return [record("eligible")]
    state = AgentState(
        run_id="replay-tampered", question="Will this event resolve positively?",
        as_of_date=CUTOFF, cutoff_date=CUTOFF,
    )
    await ReActEngine(
        DeterministicDemoModel(), PITGateway({"web_search": provider}),
        tmp_path / "originals",
    ).run(state)
    run_dir = tmp_path / "originals" / "replay-tampered"
    path = run_dir / "audit.jsonl"
    lines = path.read_text().splitlines()
    data = json.loads(lines[0])
    data["observation"]["status"] = "forged"
    lines[0] = json.dumps(data)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        await replay_run(run_dir, tmp_path / "replayed")


def outcome(research_id, probability, actual, method="consensus"):
    return ResolvedForecast(
        research_id=research_id, method=method,
        forecast_at="2025-01-01T00:00:00Z",
        resolved_at="2025-02-01T00:00:00Z",
        probability=probability, outcome=actual,
        resolution_source="https://example.org/resolution",
    )


def test_brier_and_calibration_score():
    report = score([outcome("a", 0.0, 0), outcome("b", 1.0, 1)])
    assert report["brier_score"] == 0.
    assert report["expected_calibration_error"] == 0.
    assert report["sample_size"] == 2


def test_outcome_time_and_duplicates_rejected():
    with pytest.raises(ValidationError):
        ResolvedForecast(
            research_id="bad", method="consensus", forecast_at="2025-02-01T00:00:00Z",
            resolved_at="2025-01-01T00:00:00Z", probability=0.2,
            outcome=1, resolution_source="https://example.org/resolution",
        )
    with pytest.raises(ValueError, match="duplicate"):
        score([outcome("a", 0.2, 0), outcome("a", 0.2, 0)])
