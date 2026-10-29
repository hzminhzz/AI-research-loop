"""Strict model and evidence contracts. All operational timestamps are UTC aware."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp requires an explicit UTC offset")
    return value.astimezone(timezone.utc)


SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)


class EvidenceKind(StrEnum):
    HISTORICAL = "historical"
    MARKET = "market"
    NEWS = "news"
    FILING = "filing"
    MACRO = "macro"
    CALCULATION = "calculation"


class Evidence(StrictModel):
    source_id: str = Field(min_length=1, max_length=120)
    kind: EvidenceKind
    uri: str = Field(min_length=5, max_length=2048)
    published_at: datetime
    available_at: datetime  # first version accessible to a real decision maker
    revision_available_at: datetime | None = None
    archived_at: datetime | None = None  # first archived capture, if available
    source_version: str | None = Field(default=None, max_length=120)
    snippet: str = Field(min_length=1, max_length=4000)
    provider: str = Field(min_length=1, max_length=120)
    # Structured factual assertions; used to detect conflicting supervisor citations.
    facts: dict[str, str] = Field(default_factory=dict)

    @field_validator("published_at", "available_at", "revision_available_at", "archived_at")
    @classmethod
    def utc_datetime(cls, value: datetime | None) -> datetime | None:
        return utc(value) if value is not None else None

    @model_validator(mode="after")
    def availability_is_consistent(self) -> "Evidence":
        if self.available_at < self.published_at:
            raise ValueError("available_at cannot precede published_at")
        if self.revision_available_at and self.revision_available_at < self.available_at:
            raise ValueError("revision_available_at cannot precede available_at")
        if self.archived_at and self.archived_at < self.available_at:
            raise ValueError("archived_at cannot precede available_at")
        return self


class ActionType(StrEnum):
    TOOL_CALL = "tool_call"
    FINALIZE = "finalize"


class ReActAction(StrictModel):
    step_index: int = Field(ge=0)
    # Concise decision summary, NEVER hidden chain-of-thought.
    thought: str = Field(min_length=1, max_length=1000)
    action_type: ActionType
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    rationale_summary: str | None = None

    @model_validator(mode="after")
    def conditional_fields(self) -> "ReActAction":
        if self.action_type == ActionType.TOOL_CALL:
            if not self.tool_name or self.tool_args is None or self.rationale_summary is not None:
                raise ValueError("tool_call requires tool_name/tool_args and forbids rationale_summary")
        else:
            if not self.rationale_summary or self.tool_name is not None or self.tool_args is not None:
                raise ValueError("finalize requires rationale_summary and no tool fields")
        return self


class AgentForecastArtifact(StrictModel):
    research_id: str = Field(min_length=1, max_length=160)
    probability_forecast: float | None = Field(default=None, ge=0.0, le=1.0, strict=True)
    confidence_score: float = Field(ge=0.0, le=1.0, strict=True)
    primary_rationale: str = Field(min_length=1, max_length=5000)
    evidence_citations: list[str] = Field(default_factory=list)
    key_uncertainties: list[str] = Field(default_factory=list)
    abstention_flag: bool

    @model_validator(mode="after")
    def valid_abstention(self) -> "AgentForecastArtifact":
        if self.abstention_flag:
            if self.probability_forecast is not None or self.confidence_score != 0.0:
                raise ValueError("abstention requires null probability and zero confidence")
            if not self.key_uncertainties:
                raise ValueError("abstention must include a reason in key_uncertainties")
        elif self.probability_forecast is None or not self.evidence_citations:
            raise ValueError("forecast requires probability and citations")
        if len(set(self.evidence_citations)) != len(self.evidence_citations):
            raise ValueError("duplicate citation IDs")
        return self


class RunStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    ABSTAINED = "ABSTAINED"
    FAILED = "FAILED"


class AgentState(StrictModel):
    run_id: str = Field(pattern=SAFE_ID, max_length=100)
    question: str = Field(min_length=5, max_length=2000)
    as_of_date: datetime
    cutoff_date: datetime
    step_index: int = Field(default=0, ge=0)
    max_steps: int = Field(default=10, ge=1, le=50)
    accumulated_evidence: list[Evidence] = Field(default_factory=list)
    open_subquestions: list[str] = Field(default_factory=list)
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)
    quality_gate_results: dict[str, bool] = Field(default_factory=dict)
    status: RunStatus = RunStatus.IN_PROGRESS
    role: str = "generalist"

    @field_validator("as_of_date", "cutoff_date")
    @classmethod
    def validate_time(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def validate_window(self) -> "AgentState":
        if self.cutoff_date > self.as_of_date:
            raise ValueError("cutoff_date cannot be after as_of_date")
        if self.step_index > self.max_steps:
            raise ValueError("step_index exceeds max_steps")
        return self


class SupervisorProposal(StrictModel):
    probability_forecast: float = Field(ge=0.0, le=1.0, strict=True)
    confidence_score: float = Field(ge=0.0, le=1.0, strict=True)
    rationale: str = Field(min_length=1, max_length=3000)
    evidence_citations: list[str] = Field(min_length=2)

    @field_validator("evidence_citations")
    @classmethod
    def distinct_sources(cls, value: list[str]) -> list[str]:
        if len(set(value)) < 2:
            raise ValueError("supervisor override requires two distinct source IDs")
        return value


class ResearchQuestion(StrictModel):
    research_id: str = Field(pattern=SAFE_ID, max_length=88)
    question: str = Field(min_length=5)
    cutoff_date: datetime
    base_rate: float = Field(ge=0, le=1, strict=True)
    required_kinds: list[EvidenceKind] = Field(default_factory=lambda: [EvidenceKind.HISTORICAL])
    open_subquestions: list[str] = Field(default_factory=list)

    @field_validator("cutoff_date")
    @classmethod
    def validate_cutoff(cls, value: datetime) -> datetime:
        return utc(value)
