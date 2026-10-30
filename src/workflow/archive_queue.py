"""Durable discovery backlog for autonomous source-first quant research.

This is a REVIEW queue, NOT an experiment registry, a rule verifier, or
permission to run Warden. Every source is third-party untrusted evidence.
Only the native Warden SQLite ledger can establish screened/PASS results.
Source-level review does not spend or replenish a hypothesis's trial budget.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

CURRENT_ARCHIVE = Path("runs/archive_discovery/shortlist.json")
BUNDLED_ARCHIVE = Path("examples/practitioner_archive_20261030/shortlist.json")
CHECKPOINT = Path("examples/research_batch_20261030/candidate_state.json")
VALID_REVIEW_STATES = frozenset({
    "BLOCKED_AUTHOR_RULES", "BLOCKED_DATA", "BLOCKED_EXECUTION",
    "REVIEWED_NOT_ACTIONABLE", "RULES_REVIEWED_READY_FOR_PREFLIGHT",
    "REVIEW_IN_PROGRESS",
})
DEFERRED = frozenset({
    "BLOCKED_AUTHOR_RULES", "BLOCKED_DATA", "BLOCKED_EXECUTION",
    "REVIEWED_NOT_ACTIONABLE",
})


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _original_https(url: str) -> bool:
    parsed = urlparse(url)
    return bool(
        parsed.scheme == "https" and parsed.netloc and not parsed.username
        and not parsed.password and not parsed.fragment and not parsed.query
    )


def _archive_rows(project: Path) -> tuple[list[dict], str]:
    for candidate in (project / CURRENT_ARCHIVE, project / BUNDLED_ARCHIVE):
        if not candidate.is_file():
            continue
        try:
            rows = _read_json(candidate, [])
        except (json.JSONDecodeError, UnicodeError):
            # A partial archive update must not crash the recurring source
            # campaign; use the last complete retained snapshot instead.
            continue
        if not isinstance(rows, list):
            continue
        validated: list[dict] = []
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            key, url, sha = (row.get("id"), row.get("url"),
                             row.get("content_sha256"))
            pinned_code = (
                row.get("source_kind") == "PINNED_CODE_TEST"
                and isinstance(url, str)
                and url.startswith("https://github.com/")
                and isinstance(row.get("source_revision"), str)
                and bool(re.fullmatch(r"[0-9a-f]{40}", row["source_revision"]))
                and isinstance(sha, str)
                and bool(re.fullmatch(r"[0-9a-f]{40}", sha))
            )
            if (not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{20}", key)
                    or not isinstance(url, str) or not _original_https(url)
                    or not isinstance(sha, str)
                    or not (re.fullmatch(r"[0-9a-f]{64}", sha) or pinned_code)):
                continue
            if key in seen_ids or url in seen_urls:
                continue
            seen_ids.add(key)
            seen_urls.add(url)
            validated.append(row)
        return validated, str(candidate.relative_to(project))
    return [], "MISSING_ARCHIVE_CATALOG"


def _finished_variant_urls(project: Path) -> set[str]:
    # This historical report is informative only; it never turns a
    # rejected adaptation into a claim that ALL ideas at that URL fail.
    info = _read_json(project / CHECKPOINT, {})
    if not isinstance(info, dict):
        return set()
    done = info.get("completed", [])
    return {x["source"] for x in done
            if isinstance(x, dict) and isinstance(x.get("source"), str)
            and x.get("verdict") == "STAGE_1_REJECT"}


def _progress(root: Path) -> dict:
    data = _read_json(root / "archive_progress.json", {"version": 1, "events": []})
    if (not isinstance(data, dict) or data.get("version") != 1
            or not isinstance(data.get("events"), list)):
        raise ValueError("Archive review progress is not a supported append-only event ledger")
    return data


def _current_review(events: list) -> dict[str, dict]:
    state = {}
    for event in events:
        if isinstance(event, dict) and event.get("status") in VALID_REVIEW_STATES:
            state[event.get("source_id")] = event
    return state


def _diverse(leads: list[dict], n: int) -> list[dict]:
    """First pass: one from each publisher; second: original shortlist order."""
    chosen = []
    seen = set()
    for lead in leads:
        source = lead["source_key"]
        if source not in seen:
            seen.add(source)
            chosen.append(lead)
        if len(chosen) >= n:
            return chosen
    for lead in leads:
        if lead["id"] not in {row["id"] for row in chosen}:
            chosen.append(lead)
        if len(chosen) >= n:
            return chosen
    return chosen


def backlog(project: Path, state_dir: Path, limit: int = 8) -> dict:
    """Read-only status with transparent current source capture and review state."""
    if not 1 <= limit <= 30:
        raise ValueError("Backlog preview must contain 1..30 sources")
    rows, source_path = _archive_rows(project)
    events = _progress(state_dir).get("events", [])
    review = _current_review(events)
    already_screened = _finished_variant_urls(project)
    available = []
    blocked = []
    for row in rows:
        event = review.get(row["id"])
        # New source content hash means a new source version. Do not transfer
        # its prior author-rule conclusions onto materially revised text.
        status = ("UNREVIEWED" if not event or
                  event.get("source_fingerprint") != row["content_sha256"]
                  else event["status"])
        item = {
            "id": row["id"], "title": str(row.get("title", ""))[:140],
            "url": row["url"], "source_key": row.get("source_key", "unknown"),
            "market": row.get("market", "unspecified"),
            "family": row.get("family", "unknown"),
            "rule_state": row.get("rule_state", "UNKNOWN"),
            "data_state": row.get("data_state", "UNKNOWN"),
            "source_fingerprint": row["content_sha256"],
            "source_fingerprint_kind": ("GIT_BLOB_SHA1" if len(row["content_sha256"]) == 40
                                        else "SHA256"),
            "review_state": status,
            "already_screened_variant": row["url"] in already_screened,
            "evidence": str(event.get("evidence", ""))[:300] if event else "",
        }
        if status in DEFERRED:
            blocked.append(item)
        else:
            available.append(item)
    # Prefer unseen, distinct sources. A source with a rejected Warden
    # adaptation may still contain additional ideas, but should not be
    # re-screened with that same frozen parameterization.
    available.sort(key=lambda r: (
        r["already_screened_variant"],
        r["review_state"] == "REVIEW_IN_PROGRESS",
        r["review_state"] == "RULES_REVIEWED_READY_FOR_PREFLIGHT",
    ))
    next_leads = _diverse(available, limit)
    return {
        "status": ("ARCHIVE_BACKLOG_READY" if next_leads else
                   "ARCHIVE_BACKLOG_BLOCKED_OR_EMPTY"),
        "catalog_path": source_path,
        "total_source_leads": len(rows),
        "actionable_review_leads": len(available),
        "deferred_leads": len(blocked),
        "existing_source_variant_rejections": len(already_screened),
        "next_leads": next_leads,
        "deferred_preview": blocked[:min(limit, 4)],
        "progress_events": len(events),
        "scope": "DISCOVERY_ONLY; WARDEN_REGISTRY_AUTHORITATIVE",
    }


def mark_review(project: Path, state_dir: Path, *, source_id: str,
                status: str, evidence: str) -> dict:
    """Append a review-only observation; never set experimental pass/fail here."""
    if status not in VALID_REVIEW_STATES:
        raise ValueError("Only non-scientific source review states are accepted")
    if not isinstance(evidence, str) or not 10 <= len(evidence) <= 500:
        raise ValueError("Record a specific 10..500-character review evidence note")
    rows, _ = _archive_rows(project)
    matched = next((row for row in rows if row["id"] == source_id), None)
    if matched is None:
        raise ValueError("Unknown or outdated source ID; refresh archive first")
    state_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(state_dir / "archive_progress.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        record = _progress(state_dir)
        event = {
            "source_id": source_id, "url": matched["url"],
            "source_fingerprint": matched["content_sha256"],
            "status": status, "evidence": evidence,
            "updated_at": _utc(),
        }
        # Skip duplicate identical status/evidence rather than fabricating
        # additional investigation events.
        previous = next((e for e in reversed(record["events"])
                         if isinstance(e, dict) and e.get("source_id") == source_id),
                        None)
        if previous and all(previous.get(k) == event[k] for k in (
                "source_id", "url", "source_fingerprint", "status", "evidence")):
            return {"status": "UNCHANGED_REVIEW", "source_id": source_id}
        record["events"].append(event)
        path = state_dir / "archive_progress.json"
        tmp = state_dir / f".archive_progress_{os.getpid()}.tmp"
        tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        os.replace(tmp, path)
        return {"status": "REVIEW_CHECKPOINT_RECORDED", **event}
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only archive queue and review checkpoints")
    parser.add_argument("--project", type=Path, default=Path("."))
    parser.add_argument("--state", type=Path, default=Path("runs/social_campaign"))
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--mark", help="Exact source ID from shortlist; optional")
    parser.add_argument("--review-state", choices=sorted(VALID_REVIEW_STATES))
    parser.add_argument("--evidence", help="Review evidence note, never a Warden verdict")
    args = parser.parse_args()
    if args.mark:
        if not args.review_state or not args.evidence:
            parser.error("--mark requires --review-state and --evidence")
        response = mark_review(args.project, args.state, source_id=args.mark,
                               status=args.review_state, evidence=args.evidence)
    else:
        response = backlog(args.project, args.state, limit=args.limit)
    print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
