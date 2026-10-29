"""Supervisor: hard evidence and confidence gates precede any override."""
from __future__ import annotations

from dataclasses import dataclass

from src.core.models import Evidence, SupervisorProposal
from src.harness.gates import validate_evidence
from src.multi_agent.aggregate import Consensus


@dataclass(frozen=True)
class SupervisorDecision:
    probability: float | None
    overridden: bool
    divergent: bool
    explanation: str


def evaluate(consensus: Consensus, proposal: SupervisorProposal | None,
             evidence: list[Evidence], cutoff, divergence_threshold: float = 0.05,
             minimum_confidence: float = 0.85) -> SupervisorDecision:
    divergent = (consensus.variance is not None and
                 consensus.variance > divergence_threshold)
    if consensus.probability is None:
        return SupervisorDecision(None, False, divergent, "Insufficient non-abstaining workers")
    if not divergent:
        return SupervisorDecision(consensus.probability, False, False, "No divergence trigger")
    if proposal is None or proposal.confidence_score <= minimum_confidence:
        return SupervisorDecision(consensus.probability, False, True, "No qualified supervisor proposal")
    ledger = {x.source_id: x for x in evidence}
    if not all(key in ledger for key in proposal.evidence_citations):
        return SupervisorDecision(consensus.probability, False, True, "Unknown supervisor citation")
    facts: dict[str, str] = {}
    for key in proposal.evidence_citations:
        item = ledger[key]
        try:
            validate_evidence(item, cutoff)
        except ValueError:
            return SupervisorDecision(consensus.probability, False, True, "Post-cutoff supervisor citation")
        for fact_key, fact_value in item.facts.items():
            if fact_key in facts and facts[fact_key] != fact_value:
                return SupervisorDecision(consensus.probability, False, True, "Conflicting cited facts")
            facts[fact_key] = fact_value
    return SupervisorDecision(proposal.probability_forecast, True, True,
                              "Override supported by verified non-conflicting citations")
