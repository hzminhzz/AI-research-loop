"""Trust boundary tests: model isolation, source identity and independent citation evidence."""
import asyncio
import json

import httpx
import pytest

from src.core.models import AgentForecastArtifact, AgentState, Evidence, SupervisorProposal
from src.harness.engine import ReActEngine, RunConflict
from src.harness.model import DeterministicDemoModel, OpenAICompatibleModel
from src.multi_agent.aggregate import aggregate
from src.multi_agent.supervisor import evaluate
from src.tools.pit import PITGateway

T = "2026-01-15T00:00:00Z"


def row(source, uri=None, publication="2026-01-01T00:00:00Z"):
    return dict(
        source_id=source, kind="historical", uri=uri or f"https://example.org/{source}",
        published_at=publication, available_at=publication,
        snippet="historical base rate", provider="source",
    )


def state(run_id):
    return AgentState(run_id=run_id, question="Will the event resolve positively?",
                      as_of_date=T, cutoff_date=T)


@pytest.mark.asyncio
async def test_untrusted_model_cannot_mutate_engine_evidence(tmp_path):
    class Mutator(DeterministicDemoModel):
        async def action(self, snapshot, feedback=None):
            if not snapshot.accumulated_evidence:
                snapshot.accumulated_evidence.append(
                    Evidence.model_validate(row("future", publication="2026-01-16T00:00:00Z"))
                )
                return json.dumps({
                    "step_index": snapshot.step_index, "thought": "Get historical data",
                    "action_type": "tool_call", "tool_name": "web_search",
                    "tool_args": {"query": "historical", "limit": 1},
                })
            return await super().action(snapshot, feedback)

    async def provider(_):
        return [row("clean")]
    s = state("isolated")
    result = await ReActEngine(
        Mutator(), PITGateway({"web_search": provider}), tmp_path
    ).run(s)
    assert result.probability_forecast == 0.5
    assert [x.source_id for x in s.accumulated_evidence] == ["clean"]


@pytest.mark.asyncio
async def test_changed_archive_digest_does_not_reuse_old_result(tmp_path):
    async def provider(_):
        return [row("clean")]
    first = ReActEngine(
        DeterministicDemoModel(),
        PITGateway({"web_search": provider}, source_digest="original"), tmp_path,
    )
    await first.run(state("digest"))
    changed = ReActEngine(
        DeterministicDemoModel(),
        PITGateway({"web_search": provider}, source_digest="changed"), tmp_path,
    )
    with pytest.raises(RunConflict, match="different inputs"):
        await changed.run(state("digest"))


def test_supervisor_distinct_ids_same_url_are_not_independent():
    forecast = lambda p: AgentForecastArtifact(
        research_id="x", probability_forecast=p, confidence_score=0.7,
        primary_rationale="test", evidence_citations=["one"], abstention_flag=False,
    )
    consensus = aggregate([forecast(0.1), forecast(0.9)], base_rate=0.5)
    srcs = [
        Evidence.model_validate(row("one", "https://example.org/shared")),
        Evidence.model_validate(row("two", "https://example.org/shared")),
    ]
    proposal = SupervisorProposal(
        probability_forecast=0.99, confidence_score=0.95, rationale="not independent",
        evidence_citations=["one", "two"],
    )
    decision = evaluate(consensus, proposal, srcs, srcs[0].available_at)
    assert not decision.overridden
    assert decision.probability == consensus.probability


@pytest.mark.asyncio
async def test_llm_transient_http_error_retries(monkeypatch):
    attempts = []

    class FakeHTTP:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, uri, json, headers):
            attempts.append(uri)
            if len(attempts) < 3:
                raise httpx.ReadTimeout("temporary timeout")
            return httpx.Response(
                200, request=httpx.Request("POST", uri),
                json={"choices": [{"message": {"content": '{"ok": true}'}}]},
            )

    import src.harness.model as module
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **_: FakeHTTP())
    model = OpenAICompatibleModel(model="test-model", api_key="fake-key")
    output = await model._request({"demo": True}, {}, None)
    assert output == '{"ok": true}'
    assert len(attempts) == 3
