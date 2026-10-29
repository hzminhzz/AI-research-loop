import pytest

from src.core.models import AgentForecastArtifact
from src.multi_agent.aggregate import aggregate
from src.multi_agent.supervisor import evaluate


def forecast(p):
    return AgentForecastArtifact(research_id="x", probability_forecast=p,
                                 confidence_score=0.5, primary_rationale="test",
                                 evidence_citations=["a"], abstention_flag=False)


def test_extremization():
    result = aggregate([forecast(0.6), forecast(0.8)], base_rate=0.5, gamma=1.5)
    assert result.probability == pytest.approx(0.8)


def test_insufficient_participants():
    assert aggregate([forecast(0.7)], base_rate=0.5).probability is None


def test_no_unguarded_override():
    consensus = aggregate([forecast(0.1), forecast(0.9)], base_rate=0.5)
    decision = evaluate(consensus, None, [], None)
    assert not decision.overridden
    assert decision.probability == 0.5
