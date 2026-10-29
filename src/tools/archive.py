"""Pinned historical capture catalog; never reconstruct vintage data from today's snapshots."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.core.models import Evidence
from src.tools.pit import PITRequest, PITViolation


class ArchivedCatalog:
    """A versioned, locally captured evidence snapshot. This does not certify its provenance."""

    def __init__(self, path: str | Path, expected_sha256: str, max_bytes: int = 20_000_000):
        file = Path(path)
        blob = file.read_bytes()
        if len(blob) > max_bytes:
            raise ValueError("archive exceeds maximum size")
        sha256 = hashlib.sha256(blob).hexdigest()
        if len(expected_sha256) != 64 or sha256 != expected_sha256.lower():
            raise ValueError("archive SHA-256 does not match pinned source")
        data = json.loads(blob)
        if not isinstance(data, list):
            raise ValueError("archive must be a JSON array")
        entries: list[Evidence] = []
        seen: set[str] = set()
        for row in data:
            item = Evidence.model_validate(row)
            if item.archived_at is None or not item.source_version:
                raise PITViolation("archive record lacks captured timestamp/source version")
            if item.source_id in seen:
                raise PITViolation(f"duplicate archived source ID: {item.source_id}")
            seen.add(item.source_id)
            entries.append(item)
        self.entries = entries
        self.sha256 = sha256

    async def query(self, request: PITRequest) -> list[dict]:
        found = []
        search = (request.query or request.symbol or "").casefold().split()
        for item in self.entries:
            # Filter before returning. Never expose ineligible records to the model.
            times = [
                item.published_at, item.available_at, item.archived_at,
                item.revision_available_at,
            ]
            if any(ts is not None and ts > request.cutoff_date for ts in times):
                continue
            haystack = (item.snippet + " " + item.uri + " " + json.dumps(item.facts)).casefold()
            if all(token in haystack for token in search):
                found.append(item.model_dump(mode="json"))
            if len(found) >= request.limit:
                break
        return found
