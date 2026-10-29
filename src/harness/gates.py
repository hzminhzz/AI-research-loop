"""Evidence freshness, coverage, format and citation gates: fail closed."""
from __future__ import annotations

from datetime import datetime

from pydantic import ValidationError

from src.core.models import AgentForecastArtifact, AgentState, Evidence, EvidenceKind


class GateRejected(ValueError):
    pass


def validate_evidence(item: Evidence, cutoff: datetime) -> None:
    dates = [item.published_at, item.available_at]
    if item.revision_available_at:
        dates.append(item.revision_available_at)
    if item.archived_at:
        dates.append(item.archived_at)
    if any(ts > cutoff for ts in dates):
        raise GateRejected(f"source {item.source_id}: post-cutoff evidence")
    if not item.uri.startswith(("https://", "file://")):
        raise GateRejected(f"source {item.source_id}: invalid source URI")


def validate_state_evidence(state: AgentState) -> None:
    """All evidence, cited or not, must be PIT compliant before model access."""
    seen: set[str] = set()
    for item in state.accumulated_evidence:
        validate_evidence(item, state.cutoff_date)
        if item.source_id in seen:
            raise GateRejected(f"duplicate evidence ID: {item.source_id}")
        seen.add(item.source_id)


def validate_coverage(state: AgentState, required: set[EvidenceKind]) -> None:
    validate_state_evidence(state)
    present = {x.kind for x in state.accumulated_evidence}
    missing = required - present
    if missing:
        raise GateRejected(f"missing required evidence types: {sorted(x.value for x in missing)}")


def parse_artifact(raw: str | dict, state: AgentState, required: set[EvidenceKind]) -> AgentForecastArtifact:
    try:
        artifact = (AgentForecastArtifact.model_validate_json(raw)
                    if isinstance(raw, str) else AgentForecastArtifact.model_validate(raw))
    except (ValidationError, ValueError) as exc:
        raise GateRejected(f"artifact schema: {exc}") from exc
    if artifact.research_id != state.run_id:
        raise GateRejected("artifact research_id mismatch")
    validate_state_evidence(state)
    if artifact.abstention_flag:
        return artifact
    validate_coverage(state, required)
    ids = {x.source_id for x in state.accumulated_evidence}
    unknown = set(artifact.evidence_citations) - ids
    if unknown:
        raise GateRejected(f"unknown citations: {sorted(unknown)}")
    state.quality_gate_results.update({
        "freshness_pass": True, "coverage_pass": True,
        "format_pass": True, "citations_pass": True,
    })
    return artifact


def abstain(state: AgentState, reason: str) -> AgentForecastArtifact:
    return AgentForecastArtifact(
        research_id=state.run_id,
        probability_forecast=None,
        confidence_score=0.0,
        primary_rationale="Insufficient verified point-in-time evidence to forecast.",
        evidence_citations=[],
        key_uncertainties=[reason[:1500]],
        abstention_flag=True,
    )
