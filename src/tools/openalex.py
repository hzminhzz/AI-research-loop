"""Automatically capture real public abstracts from OpenAlex with as-known provenance.

This is a current-time research source, NOT a historical-vintage API.
No claim that today's OpenAlex record was available on its publication date.
"""
from __future__ import annotations

import calendar
import hashlib
import json
from datetime import datetime, time, timezone
from urllib.parse import quote
from pathlib import Path

import httpx

from src.core.models import Evidence

OPENALEX = "https://api.openalex.org/works"
CROSSREF = "https://api.crossref.org/works/"


def _abstract(words: dict[str, list[int]] | None) -> str:
    if not isinstance(words, dict) or not words:
        return ""
    max_pos = max((max(indexes) for indexes in words.values() if indexes), default=-1)
    if max_pos < 25 or max_pos > 12000:
        return ""
    result = [""] * (max_pos + 1)
    for token, indexes in words.items():
        for i in indexes:
            if result[i]:
                raise ValueError("OpenAlex abstract has overlapping token indices")
            result[i] = token
    return " ".join(result)


def _publication_date(raw: str) -> datetime:
    # Day precision does not imply a release time. Use 23:59:59 UTC conservatively.
    day = datetime.strptime(raw, "%Y-%m-%d").date()
    return datetime.combine(day, time(23, 59, 59), tzinfo=timezone.utc)


def _crossref_published(payload: dict) -> datetime:
    """Conservative latest possible day for date-only Crossref published fields."""
    dates = []
    for field in ("published", "published-online", "published-print"):
        values = payload.get(field, {}).get("date-parts", [])
        if not values or not values[0]:
            continue
        parts = values[0]
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 12
        day = int(parts[2]) if len(parts) > 2 else calendar.monthrange(year, month)[1]
        dates.append(datetime(year, month, day, 23, 59, 59, tzinfo=timezone.utc))
    if not dates:
        raise ValueError("Crossref publication date unavailable")
    return max(dates)


async def discover_sources(
    query: str, max_sources: int = 4, search_limit: int = 15,
) -> tuple[list[Evidence], list[dict]]:
    """Collect publication-eligible original records and raw HTTP evidence.

    Only studies published no later than 2024-12-31 enter the 2025 exploratory
    validation experiment. This limits post-outcome literature selection.
    """
    if not (1 <= max_sources <= 8 and max_sources <= search_limit <= 25):
        raise ValueError("invalid public research source budget")
    params = {
        "search": query, "per-page": search_limit,
        "filter": "from_publication_date:2018-01-01,to_publication_date:2024-12-31",
    }
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.get(
            OPENALEX, params=params,
            headers={"User-Agent": "AI-quant-research-loop/0.2 (public academic research)"},
        )
        response.raise_for_status()
        rows = response.json().get("results")
    if not isinstance(rows, list):
        raise ValueError("OpenAlex response missing results")
    selected: list[Evidence] = []
    raw_records: list[dict] = []
    seen_dois: set[str] = set()
    for item in rows:
        if len(selected) >= max_sources:
            break
        doi, title, day = item.get("doi"), item.get("title"), item.get("publication_date")
        if not isinstance(doi, str) or not doi.startswith("https://doi.org/"):
            continue
        if not isinstance(title, str) or not isinstance(day, str):
            continue
        if "retracted" in title.casefold() or item.get("is_retracted", False):
            continue
        if not any(key in title.casefold() for key in ("cryptocurr", "bitcoin", "cryptoasset")):
            continue
        abstract = _abstract(item.get("abstract_inverted_index"))
        if len(abstract) < 130:
            continue
        published = _publication_date(day)
        # Cross-check the DOI's original publisher metadata. OpenAlex can
        # assign a historical date to a 2025 journal DOI: never trust it alone.
        try:
            doi_path = doi.removeprefix("https://doi.org/")
            async with httpx.AsyncClient(timeout=16) as crossref:
                verified = await crossref.get(
                    CROSSREF + quote(doi_path, safe="/"),
                    headers={"User-Agent": "AI-quant-research-loop/0.2 (PIT verification)"},
                )
                verified.raise_for_status()
                crossref_record = verified.json()["message"]
            crossref_published = _crossref_published(crossref_record)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            continue
        published = max(published, crossref_published)
        if published >= datetime(2025, 1, 1, tzinfo=timezone.utc):
            continue
        captured_at = datetime.now(timezone.utc)  # after BOTH remote metadata reads
        if doi.casefold() in seen_dois:
            continue
        seen_dois.add(doi.casefold())
        source = f"alex_{item['id'].split('/')[-1]}"
        excerpt = f"TITLE: {title}\nABSTRACT (untrusted publication text): {abstract[:2900]}"
        raw_records.append({
            "openalex_id": item["id"], "doi": doi,
            "openalex_published_date": day,
            "crossref_published_at": crossref_published.isoformat(),
            "publisher_title": (crossref_record.get("title") or [""])[0],
            "title": title, "abstract": abstract,
            "retrieved_at": captured_at.isoformat(),
        })
        digest = hashlib.sha256(
            json.dumps(raw_records[-1], sort_keys=True).encode()
        ).hexdigest()
        selected.append(Evidence(
            source_id=source,
            kind="historical",
            uri=doi,
            published_at=published,
            available_at=captured_at,
            archived_at=captured_at,
            source_version=digest[:48],
            snippet=excerpt[:3900],
            provider="openalex_current_capture_abstract",
            facts={
                "research_title": title,
                "doi": doi,
                "provenance_note": "OpenAlex + Crossref date-checked at today's capture; historical text vintage unverified",
            },
        ))
    if len(selected) < 2:
        raise ValueError("Insufficient independent, dated, nonretracted source abstracts")
    return selected, raw_records


def persist_capture(folder: Path, sources: list[Evidence], raw: list[dict]) -> dict:
    folder.mkdir(parents=True, exist_ok=False)
    archive = folder / "evidence.json"
    captured = folder / "source_metadata.json"
    data = json.dumps([x.model_dump(mode="json") for x in sources], indent=2) + "\n"
    metadata = json.dumps(raw, indent=2) + "\n"
    with archive.open("x", encoding="utf-8") as fd:
        fd.write(data)
    with captured.open("x", encoding="utf-8") as fd:
        fd.write(metadata)
    return {
        "evidence_path": str(archive),
        "evidence_sha256": hashlib.sha256(data.encode()).hexdigest(),
        "source_metadata_sha256": hashlib.sha256(metadata.encode()).hexdigest(),
        "source_count": len(sources),
    }
