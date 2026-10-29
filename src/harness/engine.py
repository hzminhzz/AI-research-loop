"""Bounded ReAct state machine with explicit schema-repair and abstention."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from src.core.audit import AuditTrail
from src.core.checkpoints import checkpoint
from src.core.models import ActionType, AgentForecastArtifact, AgentState, EvidenceKind, ReActAction, RunStatus
from src.harness.gates import GateRejected, abstain, parse_artifact
from src.harness.model import ResearchModel
from src.tools.pit import PITGateway


@dataclass(frozen=True)
class EnginePolicy:
    max_tool_calls: int = 8
    repair_attempts: int = 2
    tool_retries: int = 2
    max_consecutive_failures: int = 3


class ReActEngine:
    def __init__(self, model: ResearchModel, gateway: PITGateway, root: str | Path,
                 required: set[EvidenceKind] | None = None, policy: EnginePolicy | None = None):
        self.model = model
        self.gateway = gateway
        self.root = Path(root)
        self.required = required if required is not None else {EvidenceKind.HISTORICAL}
        self.policy = policy or EnginePolicy()

    async def _action(self, state: AgentState) -> ReActAction:
        feedback = None
        for attempt in range(self.policy.repair_attempts + 1):
            try:
                raw = await self.model.action(state, feedback)
                action = ReActAction.model_validate_json(raw)
                if action.step_index != state.step_index:
                    raise ValueError("incorrect step_index")
                return action
            except (ValidationError, ValueError) as exc:
                feedback = f"Repair invalid JSON contract: {exc}"
        raise GateRejected(f"action repair exhausted: {feedback}")

    async def _forecast(self, state: AgentState, rationale: str) -> AgentForecastArtifact:
        feedback = None
        for attempt in range(self.policy.repair_attempts + 1):
            try:
                raw = await self.model.forecast(state, rationale, feedback)
                return parse_artifact(raw, state, self.required)
            except GateRejected as exc:
                feedback = f"Repair forecast, verified citations and required coverage: {exc}"
        raise GateRejected(f"forecast repair exhausted: {feedback}")

    async def run(self, state: AgentState) -> AgentForecastArtifact:
        if state.step_index != 0 or state.status != RunStatus.IN_PROGRESS:
            raise ValueError("run requires fresh state")
        run_dir = self.root / state.run_id
        if run_dir.exists():
            raise FileExistsError(f"run already exists: {run_dir}")
        run_dir.mkdir(parents=True, exist_ok=False)
        audit = AuditTrail(run_dir / "audit.jsonl", state.run_id)
        checkpoint(state, run_dir)
        seen: set[str] = set()
        tool_calls = 0
        failures = 0
        result: AgentForecastArtifact | None = None
        reason = "step budget exhausted"
        for index in range(state.max_steps):
            state.step_index = index
            action_json: dict = {}
            observation: dict = {}
            thought = "Failed to parse action"
            try:
                action = await self._action(state)
                action_json = action.model_dump(mode="json")
                thought = action.thought
                if action.action_type == ActionType.FINALIZE:
                    result = await self._forecast(state, action.rationale_summary or "")
                    observation = {"status": "finalized", "artifact": result.model_dump(mode="json")}
                    reason = ""
                else:
                    if tool_calls >= self.policy.max_tool_calls:
                        raise GateRejected("tool call budget exhausted")
                    key = json.dumps([action.tool_name, action.tool_args], sort_keys=True)
                    if key in seen:
                        raise GateRejected("duplicate tool query suppressed")
                    seen.add(key)
                    tool_calls += 1
                    last_error: Exception | None = None
                    for retry in range(self.policy.tool_retries + 1):
                        try:
                            rows = await self.gateway.execute(
                                action.tool_name or "", action.tool_args or {}, state.cutoff_date
                            )
                            break
                        except (TimeoutError, ConnectionError, OSError) as exc:
                            last_error = exc
                            if retry == self.policy.tool_retries:
                                raise
                            await asyncio.sleep(min(0.2 * (2 ** retry), 1.0))
                    for item in rows:
                        existing = next((x for x in state.accumulated_evidence if
                                         x.source_id == item.source_id), None)
                        if existing and existing != item:
                            raise GateRejected("source ID reused with different content")
                        if not existing:
                            state.accumulated_evidence.append(item)
                    observation = {"status": "ok", "sources": [x.model_dump(mode="json") for x in rows]}
                    state.tool_trace.append({"step": index, "tool_name": action.tool_name,
                                             "args": action.tool_args, "status": "ok"})
                failures = 0
            except Exception as exc:
                reason = f"{type(exc).__name__}: {str(exc)[:500]}"
                observation = {"status": "rejected", "reason": reason}
                state.tool_trace.append({"step": index, "status": "rejected", "reason": reason})
                failures += 1
            finally:
                state.step_index = index + 1
                audit.append(index, thought, action_json, observation)
                if result is not None:
                    state.status = RunStatus.ABSTAINED if result.abstention_flag else RunStatus.COMPLETE
                checkpoint(state, run_dir)
            if result is not None or failures >= self.policy.max_consecutive_failures:
                break
        if result is None:
            result = abstain(state, reason)
            state.status = RunStatus.ABSTAINED
            audit.append(state.step_index, "Budget/quality stop", {"action_type": "abstain"},
                         {"artifact": result.model_dump(mode="json")})
            checkpoint(state, run_dir)
        (run_dir / "artifact.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result
