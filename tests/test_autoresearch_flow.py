"""Scientific negative paths: never consume selection attempts for bad models/duplicates."""
import hashlib
import json
import sqlite3

import pytest

from src.autoresearch import ResearchProposal, autonomous_run
from src.core.models import Evidence
from src.harness.openrouter import ModelAttempt, ModelReply, ModelUnavailable


def fake_sources():
    return [
        Evidence(
            source_id=f"alex_W{i}", kind="historical", uri=f"https://doi.org/example{i}",
            published_at="2022-01-01T23:59:59Z",
            available_at="2026-01-01T00:00:00Z",
            archived_at="2026-01-01T00:00:00Z",
            source_version=f"version{i}", provider="test_fixture",
            snippet="A synthetic but fully timestamped research abstract on cryptocurrency reversal."
        )
        for i in (1, 2)
    ]


def setup(monkeypatch, tmp_path):
    import src.autoresearch as app
    repo = tmp_path / "quant-lab"
    (repo / "src/warden").mkdir(parents=True)
    (repo / "src/warden/cli.py").write_text("test stub")
    (repo / "contracts").mkdir()
    (repo / "contracts/crypto_perps_1h_v2.yaml").write_text("test stub")
    (repo / "data/exploratory").mkdir(parents=True)
    (repo / "data/exploratory/crypto_perps_1h_v2.parquet").write_bytes(b"fixture")
    (repo / "registry").mkdir()
    with sqlite3.connect(repo / "registry/registry.db") as con:
        con.execute("CREATE TABLE selection_attempts (attempt_id TEXT, contract_id TEXT, stage TEXT, strategy_module TEXT, parameters_json TEXT)")
    async def discover(query):
        return fake_sources(), [{"source_id": e.source_id, "date": "2022"} for e in fake_sources()]
    calls = []
    def warden(checkout, *args, **kwargs):
        calls.append(args)
        if args != ("check-worktree",):
            raise AssertionError("Warden must not register or screen")
        return {"arguments": list(args), "exit_code": 0, "stdout": "pass", "stderr": ""}
    monkeypatch.setattr(app, "discover_sources", discover)
    monkeypatch.setattr(app, "_warden_call", warden)
    return repo, calls


@pytest.mark.asyncio
async def test_model_unavailable_is_audited_and_never_registers(monkeypatch, tmp_path):
    repo, calls = setup(monkeypatch, tmp_path)
    class Unavailable:
        async def generate(self, *_):
            raise ModelUnavailable("primary:429 fallback:ReadTimeout")
    result = await autonomous_run(repo, tmp_path / "runs", model=Unavailable())
    assert result["disposition"] == "BLOCKED_MODEL"
    run = (tmp_path / "runs" / result["research_id"])
    assert json.loads((run / "result.json").read_text())["disposition"] == "BLOCKED_MODEL"
    assert len((run / "audit.jsonl").read_text().splitlines()) == 2
    assert calls == [("check-worktree",)]


@pytest.mark.asyncio
async def test_duplicate_template_does_not_register(monkeypatch, tmp_path):
    import src.autoresearch as app
    repo, calls = setup(monkeypatch, tmp_path)
    template = (app.Path(app.__file__).parent / "workflow/strategy_templates.py")
    prior = repo / "strategies/candidates/air_template_older.py"
    prior.parent.mkdir(parents=True)
    prior.write_bytes(template.read_bytes())
    with sqlite3.connect(repo / "registry/registry.db") as con:
        con.execute("INSERT INTO selection_attempts VALUES (?,?,?,?,?)", (
            "ATT-PREVIOUS", "CRYPTO_PERPS_1H_V2", "STAGE_1_SIGNAL",
            "strategies/candidates/air_template_older.py",
            json.dumps({"mode": "shock_reversal"}),
        ))
    class DuplicateChoice:
        async def generate(self, *_):
            prop = ResearchProposal(
                template_id="shock_reversal",
                mechanism="Short-lived liquidity pressure is expected to reverse after exceptional one-hour moves.",
                counterparty_or_friction="Aggressive takers pay spreads while passive liquidity providers temporarily earn a premium.",
                rationale="Two historical studies motivate a test but do not guarantee future tradable returns.",
                cited_source_ids=["alex_W1", "alex_W2"],
                limitations=["Data is a synthetic fixture in this unit test."],
            )
            return ModelReply(prop, "unit-test-model", [ModelAttempt("unit-test-model","ok")])
    result = await autonomous_run(repo, tmp_path / "runs", model=DuplicateChoice())
    assert result["disposition"] == "SKIPPED_ALREADY_SCREENED_TEMPLATE"
    assert result["previous_attempt_id"] == "ATT-PREVIOUS"
    assert calls == [("check-worktree",)]
    assert not (repo / ".workspace").exists()
