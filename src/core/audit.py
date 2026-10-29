"""Append-only SHA256 chained JSONL audit; tamper-evident, not WORM storage."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ZERO_HASH = "0" * 64


def canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def validate_entries(entries: list[dict[str, Any]]) -> None:
    previous = ZERO_HASH
    for i, entry in enumerate(entries):
        if entry.get("seq") != i or entry.get("prev_hash") != previous:
            raise ValueError(f"audit chain broken at sequence {i}")
        body = {k: v for k, v in entry.items() if k != "entry_hash"}
        digest = hashlib.sha256(canonical(body)).hexdigest()
        if entry.get("entry_hash") != digest:
            raise ValueError(f"audit hash mismatch at sequence {i}")
        previous = digest


class AuditTrail:
    def __init__(self, path: str | Path, run_id: str):
        self.path = Path(path)
        self.run_id = run_id
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read_verified(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        # No symlinks: prevent following unexpected paths even when re-opening.
        fd = os.open(self.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            with os.fdopen(fd, "r", encoding="utf-8", closefd=False) as stream:
                entries = [json.loads(line) for line in stream if line.strip()]
            validate_entries(entries)
            if any(x.get("run_id") != self.run_id for x in entries):
                raise ValueError("mixed run IDs in audit log")
            return entries
        finally:
            os.close(fd)

    def append(
        self,
        step_index: int,
        thought: str,
        action: dict[str, Any],
        observation: dict[str, Any],
    ) -> dict[str, Any]:
        # Each event is one thought/action/observation triplet. The thought is
        # a concise decision summary, not private model chain-of-thought.
        fd = os.open(
            self.path, os.O_CREAT | os.O_RDWR | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            os.lseek(fd, 0, os.SEEK_SET)
            raw = bytearray()
            while part := os.read(fd, 1024 * 1024):
                raw.extend(part)
            entries = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
            validate_entries(entries)
            if any(x.get("run_id") != self.run_id for x in entries):
                raise ValueError("mixed run IDs in audit log")
            payload = {
                "seq": len(entries),
                "run_id": self.run_id,
                "step_index": step_index,
                "time_utc": datetime.now(timezone.utc).isoformat(),
                "thought": thought[:1000],
                "action": action,
                "observation": observation,
                "prev_hash": entries[-1]["entry_hash"] if entries else ZERO_HASH,
            }
            payload["entry_hash"] = hashlib.sha256(canonical(payload)).hexdigest()
            os.write(fd, canonical(payload) + b"\n")
            os.fsync(fd)
            return payload
        finally:
            os.close(fd)
