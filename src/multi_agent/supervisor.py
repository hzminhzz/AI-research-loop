"""Policy-bound supervisor; divergence investigation uses the same PIT tool gateway."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from pydantic import Field, field_validator

from src.core.audit import AuditTrail, canonical
from src.core.models import (
    AgentForecastArtifact, Evidence, ResearchQuestion, StrictModel, SupervisorProposal,
)
from src.harness.gates import GateRejected, validate_evidence
from src.multi_agent.aggregate import Consensus
from src.tools.pit import PITGateway


@dataclass(frozen=True)
class SupervisorDecision:
    probability: float | None
    overridden: bool
    divergent: bool
    explanation: str


class SupervisorQueries(StrictModel):
    queries: list[str] = Field(default_factory=list, max_length=2)

    @field_validator("queries")
    @classmethod
    def valid_queries(cls, value: list[str]) -> list[str]:
        if any(len(x) < 3 or len(x) > 200 for x in value):
            raise ValueError("supervisor query length must be 3..200")
        if len(set(x.casefold().strip() for x in value)) != len(value):
            raise ValueError("duplicate supervisor queries")
        return value


class SupervisorReview(StrictModel):
    proposal: SupervisorProposal | None = None


class SupervisorModel(Protocol):
    async def supervisor_queries(
        self, question: ResearchQuestion, consensus: Consensus,
        forecasts: list[AgentForecastArtifact], evidence: list[Evidence],
    ) -> str: ...

    async def supervisor_proposal(
        self, question: ResearchQuestion, consensus: Consensus,
        forecasts: list[AgentForecastArtifact], evidence: list[Evidence],
    ) -> str: ...


def evaluate(
    consensus: Consensus, proposal: SupervisorProposal | None,
    evidence: list[Evidence], cutoff: datetime,
    divergence_threshold: float = 0.05,
    minimum_confidence: float = 0.85,
) -> SupervisorDecision:
    divergent = (
        consensus.variance is not None and consensus.variance > divergence_threshold
    )
    if consensus.probability is None:
        return SupervisorDecision(None, False, divergent, "Insufficient worker forecasts")
    if not divergent:
        return SupervisorDecision(consensus.probability, False, False, "No divergence trigger")
    if proposal is None or proposal.confidence_score <= minimum_confidence:
        return SupervisorDecision(
            consensus.probability, False, True, "No qualified supervisor proposal"
        )
    if len(set(proposal.evidence_citations)) < 2:
        return SupervisorDecision(consensus.probability, False, True, "Too few distinct sources")
    ledger = {x.source_id: x for x in evidence}
    if not all(key in ledger for key in proposal.evidence_citations):
        return SupervisorDecision(consensus.probability, False, True, "Unknown supervisor citation")
    if len({ledger[key].uri for key in proposal.evidence_citations}) < 2:
        return SupervisorDecision(consensus.probability, False, True, "Only one independent source URI")
    facts: dict[str, str] = {}
    for key in proposal.evidence_citations:
        item = ledger[key]
        try:
            validate_evidence(item, cutoff)
        except ValueError:
            return SupervisorDecision(
                consensus.probability, False, True, "Post-cutoff supervisor citation"
            )
        for fact_key, fact_value in item.facts.items():
            if fact_key in facts and facts[fact_key] != fact_value:
                return SupervisorDecision(
                    consensus.probability, False, True, "Conflicting cited facts"
                )
            facts[fact_key] = fact_value
    return SupervisorDecision(
        proposal.probability_forecast, True, True,
        "Override supported by two distinct verified non-conflicting citations",
    )


class SupervisorAgent:
    """Run at most two clarifying searches; cannot call an unallowlisted tool."""

    def __init__(
        self, model: SupervisorModel, gateway: PITGateway, root: str | Path,
        divergence_threshold: float = 0.05,
    ):
        self.model = model
        self.gateway = gateway
        self.root = Path(root)
        self.divergence_threshold = divergence_threshold

    async def review(
        self, question: ResearchQuestion, forecasts: list[AgentForecastArtifact],
        consensus: Consensus, evidence: list[Evidence],
    ) -> SupervisorDecision:
        default = evaluate(
            consensus, None, evidence, question.cutoff_date,
            divergence_threshold=self.divergence_threshold,
        )
        if not default.divergent or consensus.probability is None:
            return default

        folder = self.root / f"{question.research_id}-supervisor"
        fingerprint = hashlib.sha256(canonical({
            "question": question.model_dump(mode="json"),
            "forecasts": [x.model_dump(mode="json") for x in forecasts],
            "consensus": consensus.__dict__,
            "evidence": [x.model_dump(mode="json") for x in evidence],
        })).hexdigest()
        if folder.exists():
            manifest = folder / "manifest.json"
            output = folder / "decision.json"
            if not manifest.is_file() or not output.is_file():
                raise ValueError(f"supervisor run incomplete: {folder}")
            if json.loads(manifest.read_text()) != {"fingerprint": fingerprint}:
                raise ValueError("supervisor run ID conflicts with a different forecast set")
            events = AuditTrail(folder / "audit.jsonl", question.research_id).read_verified()
            if not events:
                raise ValueError("supervisor decision lacks audited evidence")
            cached_decision = json.loads(output.read_text())
            if events[-1].get("observation", {}).get("decision") != cached_decision:
                raise ValueError("supervisor decision differs from audited result")
            return SupervisorDecision(**cached_decision)

        folder.mkdir(parents=True, exist_ok=False)
        (folder / "manifest.json").write_text(json.dumps({"fingerprint": fingerprint}))
        audit = AuditTrail(folder / "audit.jsonl", question.research_id)
        plan_raw = await self.model.supervisor_queries(question, consensus, forecasts, evidence)
        plan = SupervisorQueries.model_validate_json(plan_raw)
        audit.append(0, "Investigate disputed forecasts", {"model_raw": plan_raw},
                     {"validated_queries": plan.queries})

        unique: dict[str, Evidence] = {x.source_id: x for x in evidence}
        for number, query in enumerate(plan.queries, start=1):
            rows = await self.gateway.execute(
                "web_search", {"query": query, "limit": 5}, question.cutoff_date
            )
            for item in rows:
                if item.source_id in unique and unique[item.source_id] != item:
                    raise GateRejected("conflicting supervisor source ID")
                unique[item.source_id] = item
            audit.append(
                number, "Resolve disagreement with point-in-time evidence",
                {"tool_name": "web_search", "query": query},
                {"sources": [x.model_dump(mode="json") for x in rows]},
            )

        proposal_raw = await self.model.supervisor_proposal(
            question, consensus, forecasts, list(unique.values())
        )
        review = SupervisorReview.model_validate_json(proposal_raw)
        decision = evaluate(
            consensus, review.proposal, list(unique.values()), question.cutoff_date,
            divergence_threshold=self.divergence_threshold,
        )
        audit.append(
            len(plan.queries) + 1, "Apply hard supervisor policy",
            {"model_raw": proposal_raw},
            {"decision": decision.__dict__},
        )
        (folder / "decision.json").write_text(
            json.dumps(decision.__dict__, indent=2), encoding="utf-8"
        )
        return decision
