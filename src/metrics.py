"""Outcome scoring after event resolution. Proper scores do not imply calibration validity."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from statistics import mean
from typing import Literal

from pydantic import Field, field_validator, model_validator

from src.core.models import SAFE_ID, StrictModel, utc


class ResolvedForecast(StrictModel):
    research_id: str = Field(pattern=SAFE_ID, max_length=100)
    method: Literal["worker", "consensus", "supervisor"]
    forecast_at: datetime
    resolved_at: datetime
    probability: float = Field(strict=True, ge=0, le=1)
    outcome: Literal[0, 1]
    resolution_source: str = Field(min_length=5)

    @field_validator("forecast_at", "resolved_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        return utc(value)

    @model_validator(mode="after")
    def resolved_after_prediction(self) -> "ResolvedForecast":
        if self.resolved_at <= self.forecast_at:
            raise ValueError("event must resolve strictly after prediction")
        if self.resolved_at > datetime.now(timezone.utc):
            raise ValueError("future event outcome cannot be scored")
        if not self.resolution_source.startswith("https://"):
            raise ValueError("outcome requires HTTPS resolution source")
        return self


def score(records: list[ResolvedForecast], bins: int = 10) -> dict:
    if not records or not 2 <= bins <= 100:
        raise ValueError("nonempty records and 2..100 bins required")
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record.research_id, record.method)
        if key in seen:
            raise ValueError(f"duplicate forecast outcome: {key}")
        seen.add(key)
    brier = mean((r.probability - r.outcome) ** 2 for r in records)
    ece = 0.0
    for index in range(bins):
        group = [
            r for r in records if min(bins - 1, int(r.probability * bins)) == index
        ]
        if group:
            ece += (len(group) / len(records)) * abs(
                mean(x.probability for x in group) - mean(x.outcome for x in group)
            )
    return {
        "sample_size": len(records),
        "brier_score": brier,
        "expected_calibration_error": ece,
        "bins": bins,
        "small_sample_warning": len(records) < 100,
        "method": records[0].method if len({r.method for r in records}) == 1 else "mixed",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Score resolved forecasting outcomes; no model training"
    )
    parser.add_argument("--resolutions", required=True, help="JSON array of ResolvedForecast")
    parser.add_argument("--bins", type=int, default=10)
    args = parser.parse_args()
    from pathlib import Path
    rows = [ResolvedForecast.model_validate(x) for x in
            json.loads(Path(args.resolutions).read_text(encoding="utf-8"))]
    result = {
        method: score([r for r in rows if r.method == method], args.bins)
        for method in sorted({r.method for r in rows})
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
