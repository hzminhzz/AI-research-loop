"""Adversarial regressions for the approved Ponytail review."""
import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from src.core.models import (
    AgentState, ResearchQuestion, Evidence, EvidenceKind, SupervisorProposal,
)
from src.harness.engine import ReActEngine, EnginePolicy
from src.harness.gates import GateRejected, parse_artifact
from src.harness.model import DeterministicDemoModel
from src.multi_agent.aggregate import aggregate
from src.multi_agent.runner import MultiAgentRunner
from src.multi_agent.supervisor import evaluate
from src.tools.pit import PITGateway


CUTOFF = "2026-01-15T00:00:00Z"


def row(source="a", **kwargs):
    result = dict(source_id=source, kind="historical", uri=f"https://example.org/{source}",
                  published_at="2026-01-01T00:00:00Z",
                  available_at="2026-01-02T00:00:00Z",
                  snippet="historical base rate", provider="archival")
    result.update(kwargs)
    return result


def initial(run_id="test-one", question="Will the event resolve positively?", **kwargs):
    return AgentState(run_id=run_id, question=question, as_of_date=CUTOFF,
                      cutoff_date=CUTOFF, **kwargs)


async def one_source(_):
    return [row()]


@pytest.mark.parametrize("model", ["state", "question"])
def test_path_traversal_rejected(model):
    with pytest.raises(ValidationError):
        if model == "state":
            initial("../../escape")
        else:
            ResearchQuestion(research_id="../../escape", question="Event positive?",
                             cutoff_date=CUTOFF, base_rate=0.5)


def test_future_preloaded_evidence_cannot_satisfy_coverage():
    future = Evidence.model_validate(row("future", available_at="2026-01-16T00:00:00Z",
                                         published_at="2026-01-16T00:00:00Z"))
    news = Evidence.model_validate(row("news", kind="news"))
    state = initial(accumulated_evidence=[future, news])
    artifact = {"research_id": state.run_id, "probability_forecast": 0.7, "confidence_score": 0.6,
                "primary_rationale": "Cites old news", "evidence_citations": ["news"],
                "key_uncertainties": [], "abstention_flag": False}
    with pytest.raises(GateRejected):
        parse_artifact(artifact, state, {EvidenceKind.HISTORICAL})


@pytest.mark.asyncio
async def test_future_preloaded_source_denied_before_model(tmp_path):
    class ShouldNotRun:
        async def action(self, *_):
            raise AssertionError("the model must not see post-cutoff records")

        async def forecast(self, *_):
            raise AssertionError("the model must not see post-cutoff records")
    state = initial(accumulated_evidence=[
        Evidence.model_validate(row("future", published_at="2026-01-16T00:00:00Z",
                                    available_at="2026-01-16T00:00:00Z"))
    ])
    with pytest.raises(GateRejected):
        await ReActEngine(ShouldNotRun(), PITGateway({}), tmp_path).run(state)


def test_supervisor_requires_distinct_citations():
    with pytest.raises(ValidationError):
        SupervisorProposal(probability_forecast=0.99, confidence_score=0.99,
                           rationale="Override", evidence_citations=["a", "a"])


@pytest.mark.asyncio
async def test_repeat_same_run_is_idempotent_and_mismatch_fails(tmp_path):
    engine = ReActEngine(DeterministicDemoModel(), PITGateway({"web_search": one_source}), tmp_path)
    first = await engine.run(initial("repeat-one"))
    again = await engine.run(initial("repeat-one"))
    assert first == again
    assert first.probability_forecast == 0.5
    with pytest.raises((ValueError, FileExistsError)):
        await engine.run(initial("repeat-one", question="A changed research question?"))


@pytest.mark.asyncio
async def test_httpx_timeout_retries_then_succeeds(tmp_path):
    attempts = 0

    async def flaky(_):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ReadTimeout("Temporary gateway outage")
        return [row()]
    engine = ReActEngine(DeterministicDemoModel(), PITGateway({"web_search": flaky}),
                         tmp_path, policy=EnginePolicy(tool_retries=2))
    result = await engine.run(initial("retry-one"))
    assert attempts == 3
    assert not result.abstention_flag


@pytest.mark.asyncio
async def test_unexpected_provider_failure_is_not_synthetic_abstention(tmp_path):
    async def broken(_):
        raise RuntimeError("misconfigured provider")
    engine = ReActEngine(DeterministicDemoModel(), PITGateway({"web_search": broken}), tmp_path)
    with pytest.raises(RuntimeError, match="misconfigured provider"):
        await engine.run(initial("provider-bad"))


@pytest.mark.asyncio
async def test_single_worker_returns_baseline_probability(tmp_path):
    question = ResearchQuestion(research_id="one-agent", question="Event positive?",
                                cutoff_date=CUTOFF, base_rate=0.5)
    runner = MultiAgentRunner(lambda *_: DeterministicDemoModel(),
                              PITGateway({"web_search": one_source}), tmp_path, workers=1)
    result = await runner.run(question)
    assert not result.forecasts[0].abstention_flag
    assert result.consensus.probability == 0.5


@pytest.mark.asyncio
async def test_successful_run_records_explicit_gates(tmp_path):
    state = initial("gates-good")
    await ReActEngine(DeterministicDemoModel(), PITGateway({"web_search": one_source}),
                       tmp_path).run(state)
    assert state.quality_gate_results == {
        "freshness_pass": True, "coverage_pass": True,
        "format_pass": True, "citations_pass": True,
    }
