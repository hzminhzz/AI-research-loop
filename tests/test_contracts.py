from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.core.models import AgentForecastArtifact, AgentState, Evidence, ReActAction

T = "2026-01-15T00:00:00Z"


def state():
    return AgentState(run_id="r1", question="Will the event resolve?", as_of_date=T, cutoff_date=T)


def test_dates_must_be_aware():
    with pytest.raises(ValidationError):
        AgentState(run_id="r1", question="Will the event resolve?",
                   as_of_date="2026-01-15T00:00:00", cutoff_date=T)


@pytest.mark.parametrize("p", [-0.01, 1.01, float("nan"), float("inf")])
def test_probability_rejected(p):
    with pytest.raises(ValidationError):
        AgentForecastArtifact(research_id="r1", probability_forecast=p,
                              confidence_score=0.5, primary_rationale="x",
                              evidence_citations=["x"], abstention_flag=False)


def test_abstention_semantics():
    with pytest.raises(ValidationError):
        AgentForecastArtifact(research_id="r1", probability_forecast=0.5,
                              confidence_score=0, primary_rationale="x",
                              abstention_flag=True, key_uncertainties=["missing"])


def test_action_contract():
    with pytest.raises(ValidationError):
        ReActAction.model_validate({"step_index": 0, "thought": "x",
                                    "action_type": "tool_call", "tool_name": "execute_order",
                                    "tool_args": {}, "unexpected": True})
