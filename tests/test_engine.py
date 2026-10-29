import json

import pytest

from src.core.audit import AuditTrail
from src.core.models import AgentState
from src.harness.engine import ReActEngine, EnginePolicy
from src.harness.model import DeterministicDemoModel
from src.tools.pit import PITGateway


def evidence():
    return dict(source_id="a", kind="historical", uri="https://example.org/a",
                published_at="2026-01-01T00:00:00Z",
                available_at="2026-01-02T00:00:00Z",
                snippet="historical base rate", provider="fixture")


@pytest.mark.asyncio
async def test_engine_finalizes_with_valid_evidence(tmp_path):
    async def source(request):
        assert request.cutoff_date.isoformat().startswith("2026-01-15")
        return [evidence()]
    state = AgentState(run_id="run-1", question="Will positive event happen?",
                       as_of_date="2026-01-15T00:00:00Z",
                       cutoff_date="2026-01-15T00:00:00Z")
    output = await ReActEngine(DeterministicDemoModel(),
                              PITGateway({"web_search": source}), tmp_path).run(state)
    assert not output.abstention_flag
    assert output.evidence_citations == ["a"]
    assert len(AuditTrail(tmp_path / "run-1" / "audit.jsonl", "run-1").read_verified()) == 2


@pytest.mark.asyncio
async def test_budget_abstains(tmp_path):
    async def source(request):
        return []
    state = AgentState(run_id="run-2", question="Will positive event happen?",
                       as_of_date="2026-01-15T00:00:00Z",
                       cutoff_date="2026-01-15T00:00:00Z", max_steps=1)
    output = await ReActEngine(DeterministicDemoModel(),
                              PITGateway({"web_search": source}), tmp_path).run(state)
    assert output.abstention_flag
