"""Bounded parallel worker runs; each worker owns an isolated state and trace."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from src.core.models import AgentForecastArtifact, AgentState, ResearchQuestion, EvidenceKind
from src.harness.engine import ReActEngine
from src.harness.gates import abstain
from src.harness.model import ResearchModel
from src.multi_agent.aggregate import Consensus, aggregate
from src.tools.pit import PITGateway


@dataclass(frozen=True)
class EnsembleResult:
    forecasts: list[AgentForecastArtifact]
    consensus: Consensus


class MultiAgentRunner:
    def __init__(self, model_factory: Callable[[int, str], ResearchModel], gateway: PITGateway,
                 root: str | Path, workers: int = 3, gamma: float = 1.,
                 roles: list[str] | None = None, max_steps: int = 10):
        if not 1 <= workers <= 10:
            raise ValueError("workers must be in [1,10]")
        self.model_factory = model_factory
        self.gateway = gateway
        self.root = Path(root)
        self.workers = workers
        self.gamma = gamma
        self.roles = roles or ["historical", "macro", "cross_asset"]
        self.max_steps = max_steps

    async def run(self, question: ResearchQuestion) -> EnsembleResult:
        async def one(index: int) -> AgentForecastArtifact:
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
            try:
                return await engine.run(state)
            except Exception as exc:
                return abstain(state, f"worker failure: {type(exc).__name__}: {exc}")
        forecasts = list(await asyncio.gather(*(one(i) for i in range(self.workers))))
        return EnsembleResult(forecasts, aggregate(forecasts, question.base_rate,
                                                  self.gamma, minimum_participants=2))
