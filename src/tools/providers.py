"""Development fixtures and safe local timestamped evidence catalog."""
from __future__ import annotations

import json
from pathlib import Path

from src.tools.pit import PITRequest


def fixture_provider(path: str | Path):
    """Fixture records must contain all PIT metadata. Never use unversioned vendor snapshots."""
    source = Path(path)

    async def query(request: PITRequest) -> list[dict]:
        rows = json.loads(source.read_text(encoding="utf-8"))
        records = []
        for record in rows:
            snippet = record.get("snippet", "")
            identifier = record.get("uri", "")
            if request.query and request.query.casefold() not in (snippet + " " + identifier).casefold():
                continue
            if request.symbol and request.symbol.casefold() not in (snippet + " " + identifier).casefold():
                continue
            records.append(record)
        # Gateway rejects missing/unsafe dates; never use provider-side filtering alone.
        return records[:request.limit]
    return query
