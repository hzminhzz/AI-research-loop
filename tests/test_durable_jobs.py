"""Durable Warden launch: no duplicate job after lost tool response or timeout."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.workflow.durable_jobs as jobs


@pytest.fixture
def testroot(tmp_path):
    lab = tmp_path / "quant-lab"
    loop = tmp_path / "AI-research-loop"
    (lab / "experiments/active").mkdir(parents=True)
    (lab / "strategies/candidates").mkdir(parents=True)
    (lab / "registry").mkdir()
    loop.mkdir()
    (lab / ".warden_manifest.sha256").write_text("frozen-manifest\n")
    (lab / "strategies/candidates/new.py").write_text("def generate_positions(): pass\n")
    (lab / "experiments/active/new.yaml").write_text(
        "hypothesis_id: HYP-NEW-20261030\n"
        "contract_id: CRYPTO_PERPS_1H_V2\n"
        "strategy_module: strategies/candidates/new.py\n"
    )
    return lab, loop


def _command():
    return ["uv", "run", "warden", "verify", "experiments/active/new.yaml", "--json"]


def test_job_id_pins_spec_strategy_code_and_manifest(testroot):
    lab, loop = testroot
    first = jobs.make_identity(lab, _command())
    assert first["unit"].startswith("warden-verify-")
    (lab / "strategies/candidates/new.py").write_text("def generate_positions(): return 1\n")
    changed = jobs.make_identity(lab, _command())
    assert first["unit"] != changed["unit"]


def test_idempotent_submit_and_poll_terminal_receipt(monkeypatch, testroot):
    lab, loop = testroot
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[0] == "systemd-run":
            assert "--no-block" in argv
            assert "--remain-after-exit" in argv
            assert "src.workflow.governance_guard" in argv
            return SimpleNamespace(returncode=0, stdout="Running transient service...", stderr="")
        if argv[0] == "systemctl":
            return SimpleNamespace(returncode=0, stdout=(
                "LoadState=loaded\nActiveState=active\nSubState=exited\n"
                "Result=success\nExecMainStatus=0\n"
            ), stderr="")
        if argv[0] == "journalctl":
            return SimpleNamespace(
                returncode=0, stdout='{"status":"PASS","prefix_invariance":true}\n',
                stderr="",
            )
        raise AssertionError(argv)

    monkeypatch.setattr(jobs, "inspect", lambda root: {"status": "READY_FOR_DISTINCT_RESEARCH"})
    monkeypatch.setattr(jobs.subprocess, "run", fake_run)
    a = jobs.submit(lab, loop, _command())
    assert a["status"] == "SUBMITTED"
    b = jobs.submit(lab, loop, _command())
    assert b["status"] == "SUBMITTING" or b["status"] == "ALREADY_RECORDED_NO_REPLAY"
    assert sum(call[0] == "systemd-run" for call in calls) == 1
    result = jobs.poll(loop, a["unit"])
    assert result["status"] == "TERMINAL_RECORDED"
    assert result["terminal_result"] == "PROCESS_OK"
    assert result["qualified"] is False
    again = jobs.poll(loop, a["unit"])
    assert again["status"] == "TERMINAL_RECORDED"
    assert len([x for x in calls if x[0] == "systemctl"]) == 1
    assert (loop / "runs/warden_jobs" / (a["unit"] + ".terminal.json")).exists()


def test_systemd_missing_after_submit_is_unknown_not_relaunched(monkeypatch, testroot):
    lab, loop = testroot
    monkeypatch.setattr(jobs, "inspect", lambda root: {"status": "READY_FOR_DISTINCT_RESEARCH"})

    def fake_run(argv, **kwargs):
        if argv[0] == "systemd-run":
            return SimpleNamespace(returncode=0, stdout="queued", stderr="")
        return SimpleNamespace(
            returncode=0, stdout="LoadState=not-found\nActiveState=inactive\n", stderr="",
        )

    monkeypatch.setattr(jobs.subprocess, "run", fake_run)
    saved = jobs.submit(lab, loop, _command())
    status = jobs.poll(loop, saved["unit"])
    assert status["status"] == "UNKNOWN_TERMINAL_DO_NOT_RESUBMIT"


@pytest.mark.parametrize("command", [
    ["uv", "run", "warden", "qualify", "experiments/active/new.yaml"],
    ["uv", "run", "warden", "backtest", "experiments/active/hyp_2026_128_t2.yaml"],
    ["uv", "run", "warden", "verify", "experiments/active/hyp_2026_126_screen.yaml"],
])
def test_durable_job_rejects_unsafe_commands(testroot, command):
    lab, loop = testroot
    with pytest.raises(ValueError):
        jobs.make_identity(lab, command)


def test_submit_fails_governance_before_creating_job(monkeypatch, testroot):
    lab, loop = testroot
    monkeypatch.setattr(jobs, "inspect", lambda root: {"status": "GOVERNANCE_BLOCKED"})
    with pytest.raises(ValueError, match="Governance preflight"):
        jobs.submit(lab, loop, _command())
    assert not list((loop / "runs/warden_jobs").glob("warden-*.json"))
