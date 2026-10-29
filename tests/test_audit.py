import json

import pytest

from src.core.audit import AuditTrail


def test_hash_chain_detects_tamper(tmp_path):
    trail = AuditTrail(tmp_path / "audit.jsonl", "run-x")
    trail.append(0, "brief", {"action_type": "tool_call"}, {"status": "ok"})
    trail.append(1, "brief", {"action_type": "finalize"}, {"status": "complete"})
    assert len(trail.read_verified()) == 2
    path = tmp_path / "audit.jsonl"
    lines = path.read_text().splitlines()
    entry = json.loads(lines[0])
    entry["observation"]["status"] = "tampered"
    lines[0] = json.dumps(entry)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError):
        trail.read_verified()


def test_run_isolation(tmp_path):
    trail = AuditTrail(tmp_path / "audit.jsonl", "run-x")
    trail.append(0, "x", {}, {})
    with pytest.raises(ValueError):
        AuditTrail(tmp_path / "audit.jsonl", "another-run").append(0, "x", {}, {})
