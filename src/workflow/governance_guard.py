"""Fail-closed Warden incident gate for the AI-research-loop director.

This reader distinguishes a historical, already-quarantined invalid trial from
a *current* global integrity violation. No registry or manifest is edited.
Actual Warden mutations must use the shared cross-agent flock held through the
full command, never infer exclusive ownership from git status or a timer check.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BANNED_HYPOTHESIS = "HYP-2026-128"
BANNED_RUNS = ("RUN-XSRR-001", "RUN-XSRR-002")
LOCK_NAME = "warden-writer.lock"
# Explicitly no qualify, unseal, manifest signing, arbitrary shell or direct code.
ALLOWED_WARDEN = frozenset({
    "register-hypothesis", "verify", "screen", "backtest",
    "verify-causality", "audit-check", "status", "check-worktree",
    "preflight",
})
AUTO_CONTRACT = re.compile(r"^contracts/(?:auto_[a-z0-9_]+\.yaml|datasets/AUTO_[A-Z0-9_]+\.json)$")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entries(raw: bytes) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        bits = line.split(maxsplit=1)
        if len(bits) != 2 or not re.fullmatch(r"[0-9a-f]{64}", bits[0]):
            raise ValueError("Malformed approved Warden manifest entry")
        digest, rel = bits
        if rel in entries:
            raise ValueError("Duplicate manifest path")
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError("Unsafe manifest path")
        entries[rel] = digest
    return entries


def manifest_reconciliation(root: Path) -> dict:
    """Diff exactly against the checkout's Git baseline, not its dirty count."""
    manifest = root / ".warden_manifest.sha256"
    metadata_path = root / ".warden_manifest.sha256.meta.json"
    if not manifest.is_file() or not metadata_path.is_file():
        raise ValueError("Missing Warden manifest or approval provenance")
    raw = manifest.read_bytes()
    meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict) or meta.get("manifest_sha256") != _digest(raw):
        raise ValueError("Manifest bytes disagree with approval metadata")
    baseline = subprocess.run(
        ["git", "show", "HEAD:.warden_manifest.sha256"],
        cwd=root, capture_output=True, check=True, timeout=12,
    ).stdout
    old = _entries(baseline)
    current = _entries(raw)
    for rel, expected in old.items():
        if current.get(rel) != expected:
            raise ValueError(f"An earlier approved Warden file was changed: {rel}")
    additions = sorted(set(current) - set(old))
    if additions:
        if meta.get("mode") not in (
            "delegated_principal_chat_approval_unsigned",
            "bounded_principal_delegation_unsigned",
        ):
            raise ValueError("Additional research contracts lack delegated approval provenance")
        if any(not AUTO_CONTRACT.fullmatch(path) for path in additions):
            raise ValueError("Manifest contains unexpected additional protected paths")
        names = {
            p.removeprefix("contracts/").removesuffix(".yaml").upper()
            for p in additions if p.startswith("contracts/auto_")
        }
        manifests = {
            p.removeprefix("contracts/datasets/").removesuffix(".json")
            for p in additions if p.startswith("contracts/datasets/")
        }
        if names != manifests:
            raise ValueError("Additional research contracts have no matching dataset manifests")
        if meta.get("mode") == "delegated_principal_chat_approval_unsigned" and len(additions) != 2:
            raise ValueError("The current delegated manifest documents exactly two additions")
        if meta.get("mode") == "bounded_principal_delegation_unsigned" and not set(meta.get("added_paths", [])) <= set(additions):
            raise ValueError("Last delegated activation not represented in manifest")
    # Validate *all* previous and added hashes, matching Warden's own check.
    for rel, expected in current.items():
        candidate = (root / rel).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise ValueError(f"Manifest file missing or escapes repository: {rel}")
        if _digest(candidate.read_bytes()) != expected:
            raise ValueError(f"Manifest hash mismatch: {rel}")
    return {
        "status": "VERIFIED_MANIFEST_ADDITIONS" if additions else "VERIFIED_BASELINE",
        "manifest_sha256": _digest(raw),
        "approval_mode": meta.get("mode"),
        "independent_signature": bool((root / ".warden_manifest.sha256.sig").is_file()),
        "unchanged_baseline_entries": len(old),
        "added_files": additions,
        "note": "Delegated unsigned approval is not independent cryptographic attestation",
    }


def registry_reconciliation(root: Path) -> dict:
    dbfile = root / "registry/registry.db"
    if not dbfile.is_file():
        raise ValueError("Warden registry absent")
    # No ResearchRegistry constructor: it may apply migrations and write data.
    database = sqlite3.connect(f"file:{dbfile}?mode=ro", uri=True, timeout=15)
    database.row_factory = sqlite3.Row
    try:
        n_h = database.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0]
        n_t = database.execute("SELECT COUNT(*) FROM trials").fetchone()[0]
        banned = {}
        for run_id in BANNED_RUNS:
            r = database.execute(
                "SELECT run_id,hypothesis_id,verdict,contract_id FROM trials WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if r is None:
                banned[run_id] = {"present": False, "quarantined": True}
                continue
            flags = [v[0] for v in database.execute(
                "SELECT disposition FROM trial_dispositions WHERE run_id=?",
                (run_id,),
            )]
            q = database.execute(
                "SELECT 1 FROM trial_quarantine WHERE run_id=?", (run_id,),
            ).fetchone()
            quarantined = "QUARANTINED" in flags or q is not None
            banned[run_id] = {
                "present": True, "quarantined": quarantined,
                "historical_verdict": r["verdict"],
                "hypothesis_id": r["hypothesis_id"],
                "dispositions": flags,
            }
        affected = database.execute(
            "SELECT COUNT(*) FROM selection_attempts WHERE hypothesis_id=?",
            (BANNED_HYPOTHESIS,),
        ).fetchone()[0]
        pending = database.execute(
            "SELECT COUNT(*) FROM trials WHERE hypothesis_id='HYP-2026-126'",
        ).fetchone()[0]
        attempted = database.execute(
            "SELECT COUNT(*) FROM selection_attempts WHERE hypothesis_id='HYP-2026-126'",
        ).fetchone()[0]
        # A previous timed-out verify has no durable job ID and no terminal
        # evidence. This blocks *that candidate*, never an unrelated lineage.
        return {
            "hypotheses_count": n_h,
            "full_trials_count": n_t,
            "quarantined_prior_runs": banned,
            "hyp128_stage1_attempts_retained": affected,
            "unregistered_hyp128_diagnostic_cells": 159,
            "hyp126": {
                "scope": "CANDIDATE_ONLY_UNRESOLVED_VERIFY",
                "full_trials": pending, "stage1_attempts": attempted,
                "action": "Do not replay HYP-2026-126 without a durable job ID and independent reconciliation",
            },
            "safe_for_unrelated_research": all(a["quarantined"] for a in banned.values()),
            "related_family_multiplicity_unresolved": True,
        }
    finally:
        database.close()


def inspect(root: Path) -> dict:
    root = root.resolve()
    checks: dict = {}
    errors = []
    for key, check in (
        ("manifest", manifest_reconciliation),
        ("registry", registry_reconciliation),
    ):
        try:
            checks[key] = check(root)
        except (OSError, ValueError, sqlite3.DatabaseError, subprocess.SubprocessError) as exc:
            errors.append(f"{key}: {type(exc).__name__}: {exc}")
    if checks.get("registry", {}).get("safe_for_unrelated_research") is False:
        errors.append("Historical XSRR trials have not been quarantined by an append-only disposition")
    return {
        "status": "READY_FOR_DISTINCT_RESEARCH" if not errors else "GOVERNANCE_BLOCKED",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "quant_lab": str(root),
        "checks": checks,
        "errors": errors,
        "writer_rule": (
            "All Warden registry mutators must hold exclusive "
            f"{root / 'registry' / LOCK_NAME};"
            " unrelated HYP-2026-126 verify remains quarantined without a durable job"
        ),
    }


def validate_warden_command(root: Path, command: list[str]) -> None:
    # The executable is a *literal* Warden CLI, never an arbitrary command.
    if (len(command) < 4 or command[:3] != ["uv", "run", "warden"]
            or command[3] not in ALLOWED_WARDEN):
        raise ValueError("Only approved Warden research CLI subcommands are permitted")
    # Independent quarantine: no choice of CLI subcommand may exercise a
    # known contaminated hypothesis or repeat an unresolved verify.
    blocked = ("HYP-2026-128", "hyp_2026_128", "RUN-XSRR-", "HYP-2026-126", "hyp_2026_126")
    text = " ".join(command[4:])
    if any(token in text for token in blocked):
        raise ValueError("Quarantined or unresolved hypothesis cannot be re-executed")
    root = root.resolve()
    for token in command[4:]:
        if not token.lower().endswith((".yaml", ".yml", ".json", ".md")):
            continue
        selected = (root / token).resolve()
        if not selected.is_relative_to(root):
            raise ValueError("Warden spec path escapes research checkout")
        if not selected.is_file() or selected.stat().st_size > 256_000:
            raise ValueError("Missing or oversized Warden spec file")
        if any(marker in selected.read_text(encoding="utf-8") for marker in blocked):
            raise ValueError("Warden spec contains a quarantined or unresolved lineage")


def run_warden(root: Path, command: list[str], timeout_seconds: int = 240) -> int:
    validate_warden_command(root, command)
    if not 1 <= timeout_seconds <= 1800:
        raise ValueError("Unbounded Warden subprocess runtime")
    root = root.resolve()
    lock_file = root / "registry" / LOCK_NAME
    lock = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("A concurrent Warden research writer holds the shared registry lock") from exc
        health = inspect(root)
        if health["status"] != "READY_FOR_DISTINCT_RESEARCH":
            raise ValueError("Warden research blocked by governance preflight: " + "; ".join(health["errors"]))
        # systemd user services do not inherit interactive shell PATH.
        executable = ["/home/quant/.local/bin/uv", *command[1:]]
        finished = subprocess.run(executable, cwd=root, timeout=timeout_seconds, check=False)
        return int(finished.returncode)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        os.close(lock)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile Warden governance, then execute only guarded research commands")
    parser.add_argument("--quant-lab", default="/home/quant/dev/quant-lab", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("action", choices=("check", "run"))
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.action == "check":
            result = inspect(args.quant_lab)
            print(json.dumps(result, indent=2))
            raise SystemExit(0 if result["status"] == "READY_FOR_DISTINCT_RESEARCH" else 2)
        command = args.command
        if command and command[0] == "--":
            command = command[1:]
        raise SystemExit(run_warden(args.quant_lab, command, args.timeout_seconds))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "GOVERNANCE_BLOCKED", "reason": str(exc)}), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
