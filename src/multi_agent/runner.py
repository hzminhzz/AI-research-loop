"""Bounded parallel worker runs; each worker owns an isolated state and trace."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.core.models import AgentForecastArtifact, AgentState, ResearchQuestion, Evidence
from src.harness.engine import ReActEngine
from src.harness.model import ResearchModel
from src.multi_agent.aggregate import Consensus, aggregate
from src.multi_agent.supervisor import SupervisorAgent, SupervisorDecision, evaluate
from src.tools.pit import PITGateway


@dataclass(frozen=True)
class EnsembleResult:
    forecasts: list[AgentForecastArtifact]
    consensus: Consensus
    supervisor: SupervisorDecision


class MultiAgentRunner:
    def __init__(self, model_factory: Callable[[int, str], ResearchModel], gateway: PITGateway,
                 root: str | Path, workers: int = 3, gamma: float = 1.,
                 roles: list[str] | None = None, max_steps: int = 10,
                 supervisor: SupervisorAgent | None = None):
        if not 1 <= workers <= 10:
            raise ValueError("workers must be in [1,10]")
        self.model_factory = model_factory
        self.gateway = gateway
        self.root = Path(root)
        self.workers = workers
        self.gamma = gamma
        self.roles = roles or ["historical", "macro", "cross_asset"]
        self.max_steps = max_steps
        self.supervisor = supervisor

    async def run(self, question: ResearchQuestion) -> EnsembleResult:
        async def one(index: int) -> tuple[AgentForecastArtifact, AgentState]:
            role = self.roles[index % len(self.roles)]
            state = AgentState(
                run_id=f"{question.research_id}-w{index:02d}",
                question=question.question,
                as_of_date=question.cutoff_date,
                cutoff_date=question.cutoff_date,
                max_steps=self.max_steps,
                open_subquestions=question.open_subquestions[:],
                role=role,
            )
            engine = ReActEngine(self.model_factory(index, role), self.gateway, self.root,
                                 required=set(question.required_kinds))
            artifact = await engine.run(state)
            return artifact, state

        outcomes = await asyncio.gather(*(one(i) for i in range(self.workers)))
        forecasts = [artifact for artifact, _ in outcomes]
        consensus = aggregate(
            forecasts, question.base_rate, 1.0 if self.workers == 1 else self.gamma,
            minimum_participants=1 if self.workers == 1 else 2,
        )
        ledger: dict[str, Evidence] = {}
        for _, state in outcomes:
            for item in state.accumulated_evidence:
                if item.source_id in ledger and ledger[item.source_id] != item:
                    raise ValueError(f"conflicting worker source ID: {item.source_id}")
                ledger[item.source_id] = item
        evidence = list(ledger.values())
        supervisor = (
            await self.supervisor.review(question, forecasts, consensus, evidence)
            if self.supervisor is not None
            else evaluate(consensus, None, evidence, question.cutoff_date)
        )
        return EnsembleResult(forecasts, consensus, supervisor)
