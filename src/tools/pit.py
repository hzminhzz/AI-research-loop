"""PIT tool boundary. Providers MUST supply release/knowledge timestamps, not current snapshots."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.models import Evidence
from src.harness.gates import GateRejected, validate_evidence


class PITViolation(GateRejected):
    pass


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=3, max_length=200)
    limit: int = Field(default=5, ge=1, le=20)


class LookupArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=32)
    limit: int = Field(default=10, ge=1, le=50)


class PITRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cutoff_date: datetime
    query: str | None = None
    symbol: str | None = None
    limit: int = Field(ge=1, le=50)

    @model_validator(mode="after")
    def nonempty(self) -> "PITRequest":
        if (self.query is None) == (self.symbol is None):
            raise ValueError("exactly one query or symbol required")
        return self


Provider = Callable[[PITRequest], Awaitable[list[dict[str, Any]]]]


class PITGateway:
    """Registered read-only providers; the LLM cannot set/relax its cutoff."""
    def __init__(self, providers: dict[str, Provider], timeout: float = 15.0):
        self.providers = dict(providers)
        self.timeout = timeout

    async def execute(self, name: str, args: dict[str, Any], cutoff: datetime) -> list[Evidence]:
        schema: type[BaseModel]
        if name == "web_search":
            schema = SearchArgs
        elif name == "market_lookup":
            schema = LookupArgs
        else:
            raise PITViolation(f"tool not allowlisted: {name}")
        if name not in self.providers:
            raise PITViolation(f"provider not configured: {name}")
        parsed = schema.model_validate(args)
        request = PITRequest(cutoff_date=cutoff, **parsed.model_dump(exclude_none=True))
        rows = await asyncio.wait_for(self.providers[name](request), timeout=self.timeout)
        if len(rows) > request.limit:
            raise PITViolation("provider returned more than request limit")
        # Reject whole batch rather than silently truncating/falsely claiming clean coverage.
        items: list[Evidence] = []
        for row in rows:
            try:
                evidence = Evidence.model_validate(row)
                validate_evidence(evidence, cutoff)
            except (ValueError, GateRejected) as exc:
                raise PITViolation(str(exc)) from exc
            items.append(evidence)
        if len({x.source_id for x in items}) != len(items):
            raise PITViolation("duplicate source IDs")
        return items
