"""Durable systemd Warden jobs with idempotent request IDs and terminal receipts.

Designed for MCP tool requests with shorter lifetimes than expensive Warden
prefix checks. The submitted service runs the guarded Warden command under the
shared exclusive registry lock. The caller gets a stable job ID immediately and
can poll across chat/agent sessions without silently replaying the same screen.
No holdout qualification or orders are supported.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.workflow.governance_guard import inspect, validate_warden_command

ALLOWED_DURABLE = {"verify", "screen", "backtest"}
MAX_JOBS = 100
MAX_SECONDS = 1700


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_identity(repo: Path, command: list[str]) -> dict:
    repo = repo.resolve()
    validate_warden_command(repo, command)
    if command[3] not in ALLOWED_DURABLE:
        raise ValueError("Durable jobs allow only verify, screen, or backtest")
    spec_tokens = [arg for arg in command[4:] if arg.endswith((".yaml", ".yml", ".json"))]
    if len(spec_tokens) != 1:
        raise ValueError("Durable jobs require exactly one source experiment spec")
    spec_path = (repo / spec_tokens[0]).resolve()
    if not spec_path.is_relative_to(repo) or not spec_path.is_file():
        raise ValueError("Experiment specification missing or outside quant-lab")
    # The strategy source is separately pinned, so changes cannot invisibly
    # reuse the old job identifier.
    import yaml
    info = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(info, dict) or "strategy_module" not in info:
        raise ValueError("Not a Warden experiment specification")
    module = (repo / str(info["strategy_module"])).resolve()
    if not module.is_relative_to(repo) or not module.is_file():
        raise ValueError("Registered strategy module unavailable or unsafe")
    manifest = repo / ".warden_manifest.sha256"
    digest = hashlib.sha256(json.dumps({
        "argv": command,
        "spec_sha256": _hash(spec_path),
        "strategy_sha256": _hash(module),
        "manifest_sha256": _hash(manifest),
    }, sort_keys=True).encode()).hexdigest()
    unit = f"warden-{command[3]}-{digest[:18]}"
    return {
        "unit": unit, "command": command, "config_digest": digest,
        "spec_sha256": _hash(spec_path),
        "strategy_sha256": _hash(module),
        "manifest_sha256": _hash(manifest),
    }


def submit(repo: Path, project: Path, command: list[str]) -> dict:
    repo, project = repo.resolve(), project.resolve()
    identity = make_identity(repo, command)
    root = project / "runs/warden_jobs"
    root.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(root / "submit.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        path = root / f"{identity['unit']}.json"
        if path.exists():
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved.get("config_digest") != identity["config_digest"]:
                raise ValueError("Unexpected job ID collision")
            return {**saved, "status": "ALREADY_RECORDED_NO_REPLAY"}
        if len(list(root.glob("warden-*.json"))) >= MAX_JOBS:
            raise ValueError("Durable job ledger full, cannot silently replenish")
        health = inspect(repo)
        if health["status"] != "READY_FOR_DISTINCT_RESEARCH":
            raise ValueError("Governance preflight blocked this durable job")
        record = {
            **identity,
            "status": "SUBMITTING",
            "submitted_at": _now(),
            "quant_lab": str(repo),
            "project": str(project),
            "terminal_receipt_required": True,
        }
        with path.open("x", encoding="utf-8") as out:
            out.write(json.dumps(record, indent=2) + "\n")
        # Service state is durable even if the original MCP request times out.
        launch = [
            "systemd-run", "--user", "--no-block", "--remain-after-exit",
            f"--unit={identity['unit']}",
            f"--working-directory={project}",
            "--property=Type=oneshot",
            "--property=RuntimeMaxSec=1800",
            "--property=MemoryMax=18G",
            "--property=NoNewPrivileges=yes",
            "/home/quant/anaconda3/bin/python", "-m",
            "src.workflow.governance_guard", "--quant-lab", str(repo),
            "--timeout-seconds", str(MAX_SECONDS), "run", "--",
            *command,
        ]
        launched = subprocess.run(launch, cwd=project, capture_output=True, text=True,
                                  timeout=25, check=False)
        receipt = {
            "unit": identity["unit"], "launched_at": _now(),
            "exit_code": launched.returncode,
            "stdout": launched.stdout[-1400:],
            "stderr": launched.stderr[-1400:],
        }
        (root / f"{identity['unit']}.launch.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8",
        )
        return {
            **record,
            "status": "SUBMITTED" if launched.returncode == 0 else "LAUNCH_FAILED_NEVER_AUTORETRY",
            "launcher": receipt,
        }
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def poll(project: Path, unit: str) -> dict:
    if not unit.startswith("warden-") or not all(c.islower() or c.isdigit() or c == "-" for c in unit):
        raise ValueError("Invalid durable Warden unit name")
    root = project.resolve() / "runs/warden_jobs"
    record_path = root / f"{unit}.json"
    if not record_path.is_file():
        raise ValueError("Unknown job ID; do not invent or retry missing jobs")
    request = json.loads(record_path.read_text(encoding="utf-8"))
    terminal = root / f"{unit}.terminal.json"
    if terminal.is_file():
        saved = json.loads(terminal.read_text(encoding="utf-8"))
        return {"status": "TERMINAL_RECORDED", **saved}
    proc = subprocess.run(
        ["systemctl", "--user", "show", f"{unit}.service",
         "-p", "LoadState", "-p", "ActiveState", "-p", "SubState",
         "-p", "Result", "-p", "ExecMainStatus"],
        capture_output=True, text=True, check=False, timeout=15,
    )
    if proc.returncode != 0:
        return {"status": "UNRESOLVED_SYSTEMD_STATUS", "unit": unit, "error": proc.stderr[-500:]}
    props = dict(line.split("=", 1) for line in proc.stdout.splitlines() if "=" in line)
    if props.get("LoadState") == "not-found":
        return {"status": "UNKNOWN_TERMINAL_DO_NOT_RESUBMIT", "unit": unit, "properties": props}
    if props.get("SubState") not in ("exited", "failed", "dead") and props.get("ActiveState") != "failed":
        return {"status": "RUNNING", "unit": unit, "properties": props}
    logs = subprocess.run(
        ["journalctl", "--user", "-u", f"{unit}.service", "--no-pager", "-n", "65"],
        capture_output=True, text=True, check=False, timeout=15,
    )
    evidence = {
        "unit": unit, "completed_observed_at": _now(),
        "command": request["command"], "config_digest": request["config_digest"],
        "properties": props,
        "journal_excerpt": logs.stdout[-7800:],
        "terminal_result": "PROCESS_OK" if (
            props.get("Result") == "success" and props.get("ExecMainStatus") == "0"
        ) else "PROCESS_NONZERO",
        "qualified": False,
        "evidence_note": (
            "Process exit status only: Warden screen REJECT and verify FAIL require "
            "reading the original structured stdout. Never infer Stage1 PASS from process exit alone."
        ),
    }
    with terminal.open("x", encoding="utf-8") as out:
        out.write(json.dumps(evidence, indent=2) + "\n")
    return {"status": "TERMINAL_RECORDED", **evidence}


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit/poll idempotent Warden systemd jobs")
    parser.add_argument("--quant-lab", type=Path, default=Path("/home/quant/dev/quant-lab"))
    parser.add_argument("--project", type=Path, default=Path("/home/quant/dev/AI-research-loop"))
    actions = parser.add_subparsers(dest="action", required=True)
    s = actions.add_parser("submit")
    s.add_argument("command", nargs=argparse.REMAINDER)
    p = actions.add_parser("poll")
    p.add_argument("--job-id", required=True)
    args = parser.parse_args()
    try:
        if args.action == "submit":
            command = args.command[1:] if args.command and args.command[0] == "--" else args.command
            result = submit(args.quant_lab, args.project, command)
        else:
            result = poll(args.project, args.job_id)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
