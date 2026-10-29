"""Supervisor is an actual bounded orchestration stage, not a dead helper."""
import json

import pytest

from src.core.models import ResearchQuestion, AgentForecastArtifact
from src.harness.model import DeterministicDemoModel
from src.multi_agent.runner import MultiAgentRunner
from src.multi_agent.supervisor import SupervisorAgent
from src.tools.pit import PITGateway

CUTOFF = "2026-01-15T00:00:00Z"


def record(source):
    return dict(
        source_id=source, kind="historical", uri=f"https://example.org/{source}",
        published_at="2026-01-01T00:00:00Z", available_at="2026-01-02T00:00:00Z",
        snippet="historical base rate / supporting evidence",
        provider="historical", facts={source: "observed"},
    )


class FixedWorker(DeterministicDemoModel):
    def __init__(self, value):
        self.value = value

    async def forecast(self, state, rationale, feedback=None):
        raw = json.loads(await super().forecast(state, rationale, feedback))
        raw["probability_forecast"] = self.value
        return json.dumps(raw)


class FakeSupervisor:
    def __init__(self):
        self.plans = 0
        self.proposals = 0

    async def supervisor_queries(self, *_):
        self.plans += 1
        return json.dumps({"queries": ["clarify bull", "clarify bear"]})

    async def supervisor_proposal(self, *args):
        self.proposals += 1
        return json.dumps({"proposal": {
            "probability_forecast": 0.8, "confidence_score": 0.9,
            "rationale": "Two independent sources", "evidence_citations": ["bull", "bear"],
        }})


@pytest.mark.asyncio
async def test_divergence_triggers_search_and_policy_bound_override(tmp_path):
    queries = []

    async def provider(request):
        queries.append(request.query)
        if request.query == "clarify bull":
            return [record("bull")]
        if request.query == "clarify bear":
            return [record("bear")]
        return [record("base")]

    gateway = PITGateway({"web_search": provider})
    model = FakeSupervisor()
    runner = MultiAgentRunner(
        lambda index, role: FixedWorker(0.1 if index == 0 else 0.9),
        gateway, tmp_path, workers=2,
        supervisor=SupervisorAgent(model, gateway, tmp_path),
    )
    question = ResearchQuestion(
        research_id="ensemble-one", question="Will the event resolve positively?",
        cutoff_date=CUTOFF, base_rate=0.5,
    )
    result = await runner.run(question)
    assert result.consensus.probability == pytest.approx(0.5)
    assert result.supervisor.overridden
    assert result.supervisor.probability == 0.8
    assert "clarify bull" in queries and "clarify bear" in queries
    assert model.plans == 1 and model.proposals == 1
    # An identical retry must reuse verified worker and supervisor results.
    again = await runner.run(question)
    assert again == result
    assert model.plans == 1 and model.proposals == 1


@pytest.mark.asyncio
async def test_absent_supervisor_never_overrides(tmp_path):
    async def provider(_):
        return [record("base")]
    runner = MultiAgentRunner(
        lambda i, _: FixedWorker(0.1 if i == 0 else 0.9),
        PITGateway({"web_search": provider}), tmp_path, workers=2,
    )
    question = ResearchQuestion(
        research_id="ensemble-baseline", question="Will the event resolve positively?",
        cutoff_date=CUTOFF, base_rate=0.5,
    )
    result = await runner.run(question)
    assert result.supervisor.divergent and not result.supervisor.overridden
    assert result.supervisor.probability == result.consensus.probability
