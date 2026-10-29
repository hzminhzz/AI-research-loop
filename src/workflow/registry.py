"""Append-only strategy thesis registration; qualification belongs to Warden/ML4T."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.core.models import SAFE_ID


class StrategyThesis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thesis_id: str = Field(pattern=SAFE_ID, max_length=100)
    market: str = Field(min_length=1)
    mechanism: str = Field(min_length=10)
    universe: list[str] = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    decision_lag_bars: int = Field(ge=1)
    expected_holding_bars: int = Field(ge=1)
    cost_assumptions: str = Field(min_length=5)
    falsification_criteria: list[str] = Field(min_length=1)
    data_cutoff: str
    parent_forecast_ids: list[str] = Field(default_factory=list)


def register_thesis(thesis: StrategyThesis, root: str | Path) -> Path:
    folder = Path(root)
    folder.mkdir(parents=True, exist_ok=True)
    payload = thesis.model_dump_json(indent=2)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    # Exclusive write, never overwrite or reset an old attempt.
    path = folder / f"{digest}.json"
    try:
        with path.open("x", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
    except FileExistsError:
        raise FileExistsError("thesis already registered; prior attempt cannot be overwritten")
    return path
