"""Incident regression: quarantined XSRR trials must not block unrelated research."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sqlite3
import subprocess

import pytest

from src.workflow.governance_guard import (
    inspect, manifest_reconciliation, registry_reconciliation, run_warden,
)


def _file_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def lab(tmp_path):
    root = tmp_path / "quant-lab"
    (root / "contracts/datasets").mkdir(parents=True)
    (root / "registry").mkdir()
    (root / "scripts").mkdir()
    original = root / "scripts/worktree-integrity.py"
    original.write_text("protected source\n")
    baseline = _file_hash(original.read_bytes()) + "  scripts/worktree-integrity.py\n"
    manifest = root / ".warden_manifest.sha256"
    manifest.write_text(baseline)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.com",
                    "add", ".warden_manifest.sha256"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.com",
                    "commit", "-q", "-m", "baseline"], cwd=root, check=True)
    new_yaml = root / "contracts/auto_crypto_perps_top100_1h_v1_h24_e24_f45_s20_v1.yaml"
    new_json = root / "contracts/datasets/AUTO_CRYPTO_PERPS_TOP100_1H_V1_H24_E24_F45_S20_V1.json"
    new_yaml.write_text("contract_id: AUTO_CRYPTO_PERPS_TOP100_1H_V1_H24_E24_F45_S20_V1\n")
    new_json.write_text("{}\n")
    manifest.write_text(baseline + "".join(
        f"{_file_hash(path.read_bytes())}  {path.relative_to(root)}\n"
        for path in (new_yaml, new_json)
    ))
    (root / ".warden_manifest.sha256.meta.json").write_text(json.dumps({
        "mode": "delegated_principal_chat_approval_unsigned",
        "manifest_sha256": _file_hash(manifest.read_bytes()),
    }))
    with sqlite3.connect(root / "registry/registry.db") as db:
        db.executescript("""
            CREATE TABLE hypotheses(hypothesis_id TEXT PRIMARY KEY);
            CREATE TABLE trials(run_id TEXT PRIMARY KEY, hypothesis_id TEXT,
                                verdict TEXT, contract_id TEXT);
            CREATE TABLE trial_dispositions(run_id TEXT, disposition TEXT);
            CREATE TABLE trial_quarantine(run_id TEXT, reason TEXT);
            CREATE TABLE selection_attempts(hypothesis_id TEXT);
        """)
        db.executemany(
            "INSERT INTO trials(run_id,hypothesis_id,verdict,contract_id) VALUES(?,?,?,?)",
            [(run, "HYP-2026-128", "REVISE", "CRYPTO_PERPS_TOP100_1H_V1")
             for run in ("RUN-XSRR-001", "RUN-XSRR-002")],
        )
        db.executemany(
            "INSERT INTO trial_dispositions(run_id,disposition) VALUES(?,?)",
            [(run, "QUARANTINED") for run in ("RUN-XSRR-001", "RUN-XSRR-002")],
        )
        db.execute(
            "INSERT INTO selection_attempts(hypothesis_id) VALUES(?)",
            ("HYP-2026-128",),
        )
    return root


def test_reconciled_governance_ready_without_changing_dirty_worktree(lab):
    (lab / "random-untracked-branch-work.txt").write_text("unrelated agent work")
    status = inspect(lab)
    assert status["status"] == "READY_FOR_DISTINCT_RESEARCH"
    assert status["checks"]["manifest"]["unchanged_baseline_entries"] == 1
    assert len(status["checks"]["manifest"]["added_files"]) == 2
    assert status["checks"]["registry"]["hyp128_stage1_attempts_retained"] == 1
    assert status["checks"]["registry"]["unregistered_hyp128_diagnostic_cells"] == 159
    assert status["checks"]["registry"]["hyp126"]["scope"] == "CANDIDATE_ONLY_UNRESOLVED_VERIFY"
    assert (lab / "random-untracked-branch-work.txt").read_text() == "unrelated agent work"


def test_unquarantined_prior_run_blocks_new_warden_writes(lab):
    with sqlite3.connect(lab / "registry/registry.db") as db:
        db.execute("DELETE FROM trial_dispositions WHERE run_id='RUN-XSRR-002'")
    status = inspect(lab)
    assert status["status"] == "GOVERNANCE_BLOCKED"
    assert not status["checks"]["registry"]["safe_for_unrelated_research"]


def test_manifest_drift_or_unapproved_paths_blocks_even_with_quarantines(lab):
    (lab / "scripts/worktree-integrity.py").write_text("secret modified core")
    assert "Manifest hash mismatch" in " ".join(inspect(lab)["errors"])
    (lab / "scripts/worktree-integrity.py").write_text("protected source\n")
    manifest = lab / ".warden_manifest.sha256"
    unknown = lab / "contracts/unreviewed.yaml"
    unknown.write_text("not authorised\n")
    manifest.write_text(manifest.read_text()
                        + f"{_file_hash(unknown.read_bytes())}  contracts/unreviewed.yaml\n")
    meta = lab / ".warden_manifest.sha256.meta.json"
    meta.write_text(json.dumps({
        "mode": "delegated_principal_chat_approval_unsigned",
        "manifest_sha256": _file_hash(manifest.read_bytes()),
    }))
    assert "unexpected additional protected paths" in " ".join(inspect(lab)["errors"])


def test_modified_manifest_without_matching_approval_is_blocked(lab):
    meta = lab / ".warden_manifest.sha256.meta.json"
    meta.write_text(json.dumps({"manifest_sha256": "0" * 64}))
    assert "approval metadata" in " ".join(inspect(lab)["errors"])


@pytest.mark.parametrize("command", [
    ["uv", "run", "warden", "qualify", "--run-id", "RUN-XSRR-002"],
    ["bash", "-c", "uv run warden screen some.yaml"],
    ["uv", "run", "warden", "verify", "experiments/active/hyp_2026_126_screen.yaml"],
    ["uv", "run", "warden", "backtest", "experiments/active/hyp_2026_128_t2.yaml"],
    ["uv", "run", "warden", "audit-check", "--run-id", "RUN-XSRR-001"],
])
def test_guard_rejects_unsafe_warden_commands_before_subprocess(lab, command):
    with pytest.raises(ValueError):
        run_warden(lab, command)


def test_exclusive_writer_lock_detects_existing_writer(lab):
    lock_path = lab / "registry/warden-writer.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="concurrent Warden"):
            run_warden(lab, ["uv", "run", "warden", "status"])
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)



def test_renamed_spec_cannot_sneak_quarantined_lineage_into_research(lab):
    (lab / "experiments").mkdir()
    renamed = lab / "experiments/new-name.yaml"
    renamed.write_text(
        "contract_id: CRYPTO_PERPS_TOP100_1H_V1\n"
        "hypothesis_id: HYP-2026-128\n"
    )
    with pytest.raises(ValueError, match="quarantined or unresolved lineage"):
        run_warden(lab, ["uv", "run", "warden", "screen", "experiments/new-name.yaml"])
