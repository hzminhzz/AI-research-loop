"""Frozen replay of completed successful runs without model or data-provider calls."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from src.core.audit import AuditTrail
from src.core.checkpoints import load_checkpoint
from src.core.models import AgentForecastArtifact, EvidenceKind
from src.harness.engine import ReActEngine
from src.tools.pit import PITGateway


class FrozenModel:
    def __init__(self, events: list[dict]):
        self.events = {x["step_index"]: x for x in events if
                       x["action"].get("action_type") in {"tool_call", "finalize"}}
        self.action_counts: dict[int, int] = {}
        self.forecast_counts: dict[int, int] = {}

    def _next(self, state, key: str, counts: dict[int, int], feedback):
        event = self.events.get(state.step_index)
        if event is None:
            raise ValueError("missing frozen model event")
        attempts = event["action"].get(key) if key == "model_attempts" else (
            event["observation"].get(key)
        )
        if not attempts:
            raise ValueError("missing frozen raw model responses")
        index = counts.get(state.step_index, 0)
        if index >= len(attempts):
            raise ValueError("unexpected extra model request in replay")
        counts[state.step_index] = index + 1
        attempt = attempts[index]
        if attempt["feedback"] != feedback:
            raise ValueError("replay contract repair feedback diverged")
        return attempt["raw"]

    async def action(self, state, feedback=None):
        return self._next(state, "model_attempts", self.action_counts, feedback)

    async def forecast(self, state, rationale, feedback=None):
        return self._next(state, "forecast_attempts", self.forecast_counts, feedback)


class FrozenGateway:
    def __init__(self, events: list[dict]):
        self.events = [x for x in events if
                       x["action"].get("action_type") == "tool_call"]
        self.cursor = 0

    def provider(self, name: str):
        async def query(request):
            if self.cursor >= len(self.events):
                raise ValueError("replay called an unrecorded tool")
            event = self.events[self.cursor]
            self.cursor += 1
            action = event["action"]
            if action.get("tool_name") != name:
                raise ValueError("frozen tool name mismatch")
            args = action.get("tool_args") or {}
            if args.get("query") != request.query or args.get("symbol") != request.symbol:
                raise ValueError("frozen tool query mismatch")
            if event["observation"].get("status") != "ok":
                raise ValueError("non-successful tool calls need an extended replay format")
            return event["observation"]["sources"]
        return query


async def replay_run(source_dir: str | Path, output_root: str | Path):
    src = Path(source_dir)
    run_id = src.name
    events = AuditTrail(src / "audit.jsonl", run_id).read_verified()
    if not events or not any(
        x.get("observation", {}).get("artifact") for x in events
    ):
        raise ValueError("source run has no audited final artifact")
    for event in events:
        if event["observation"].get("status") in {"failed", "rejected"}:
            raise ValueError("frozen replay currently requires successful tool/model steps")

    state = load_checkpoint(src / "state_000_IN_PROGRESS.json")
    manifest_path = src / "manifest.json"
    import json
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {EvidenceKind(x) for x in manifest["required"]}

    frozen = FrozenGateway(events)
    gateway = PITGateway({
        "web_search": frozen.provider("web_search"),
        "market_lookup": frozen.provider("market_lookup"),
    })
    outcome = await ReActEngine(
        FrozenModel(events), gateway, output_root, required=required
    ).run(state)
    expected = AgentForecastArtifact.model_validate_json(
        (src / "artifact.json").read_text(encoding="utf-8")
    )
    if outcome != expected:
        raise ValueError("replay forecast differs from original")
    return outcome


def main():
    parser = argparse.ArgumentParser(description="Verify frozen replay without external APIs")
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = asyncio.run(replay_run(args.source_run, args.output))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
