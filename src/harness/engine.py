"""Bounded, fail-closed ReAct research engine and immutable run identity."""
from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
from pydantic import ValidationError

from src.core.audit import AuditTrail, canonical
from src.core.checkpoints import checkpoint, load_checkpoint
from src.core.models import (
    ActionType, AgentForecastArtifact, AgentState, EvidenceKind,
    ReActAction, RunStatus,
)
from src.harness.gates import (
    GateRejected, abstain, parse_artifact, validate_state_evidence,
)
from src.harness.model import ResearchModel
from src.tools.pit import PITGateway


@dataclass(frozen=True)
class EnginePolicy:
    max_tool_calls: int = 8
    repair_attempts: int = 2
    tool_retries: int = 2
    max_consecutive_failures: int = 3


class RunConflict(ValueError):
    """A run ID is already attached to different inputs or unfinished work."""


class ReActEngine:
    def __init__(
        self, model: ResearchModel, gateway: PITGateway, root: str | Path,
        required: set[EvidenceKind] | None = None, policy: EnginePolicy | None = None,
    ):
        self.model = model
        self.gateway = gateway
        self.root = Path(root).resolve()
        self.required = required if required is not None else {EvidenceKind.HISTORICAL}
        self.policy = policy or EnginePolicy()

    def _identity(self, state: AgentState) -> str:
        # An ID represents one frozen research configuration. A new attempt needs a new ID.
        # Never record API keys, request authorization headers, or other secrets.
        details = {
            "initial_state": state.model_dump(mode="json"),
            "required": sorted(x.value for x in self.required),
            "policy": asdict(self.policy),
            "model": {
                "adapter": type(self.model).__qualname__,
                "name": getattr(self.model, "model", None),
                "temperature": getattr(self.model, "temperature", None),
            },
            "providers": sorted(self.gateway.providers),
            "require_archive": getattr(self.gateway, "require_archive", False),
            "source_digest": getattr(self.gateway, "source_digest", None),
        }
        return hashlib.sha256(canonical(details)).hexdigest()

    def _cached(self, run_dir: Path, fingerprint: str, state: AgentState) -> AgentForecastArtifact:
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.is_file():
            raise RunConflict(f"existing run has no identity manifest: {run_dir}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("fingerprint") != fingerprint:
            raise RunConflict(f"run ID already registered with different inputs: {state.run_id}")
        artifact_path = run_dir / "artifact.json"
        if not artifact_path.is_file():
            raise RunConflict(f"run exists but is unfinished; inspect its trace: {run_dir}")
        log = AuditTrail(run_dir / "audit.jsonl", state.run_id).read_verified()
        if not log:
            raise RunConflict("completed run has no verified audit events")
        artifact = AgentForecastArtifact.model_validate_json(
            artifact_path.read_text(encoding="utf-8")
        )
        if artifact.research_id != state.run_id:
            raise RunConflict("cached artifact uses a different research ID")
        if artifact.model_dump(mode="json") != log[-1].get("observation", {}).get("artifact"):
            raise RunConflict("cached artifact differs from the audited terminal result")
        terminal = sorted(
            list(run_dir.glob("state_*_COMPLETE.json")) +
            list(run_dir.glob("state_*_ABSTAINED.json"))
        )
        if not terminal:
            raise RunConflict("completed run has no terminal state checkpoint")
        saved = load_checkpoint(terminal[-1])
        if saved.run_id != state.run_id:
            raise RunConflict("cached state uses a different research ID")
        if saved.status == RunStatus.COMPLETE and artifact.abstention_flag:
            raise RunConflict("cached run has inconsistent completion status")
        if saved.status == RunStatus.ABSTAINED and not artifact.abstention_flag:
            raise RunConflict("cached run has inconsistent abstention status")
        state.step_index = saved.step_index
        state.accumulated_evidence = saved.accumulated_evidence
        state.tool_trace = saved.tool_trace
        state.quality_gate_results = saved.quality_gate_results
        state.status = saved.status
        return artifact

    async def _action(self, state: AgentState) -> tuple[ReActAction, list[dict]]:
        attempts: list[dict] = []
        feedback = None
        for _ in range(self.policy.repair_attempts + 1):
            raw = await self.model.action(state.model_copy(deep=True), feedback)
            attempts.append({"raw": raw, "feedback": feedback})
            try:
                action = ReActAction.model_validate_json(raw)
                if action.step_index != state.step_index:
                    raise ValueError("incorrect step_index")
                return action, attempts
            except (ValidationError, ValueError) as exc:
                feedback = f"Repair invalid JSON contract: {exc}"
        raise GateRejected(f"action repair exhausted: {feedback}")

    async def _forecast(
        self, state: AgentState, rationale: str
    ) -> tuple[AgentForecastArtifact, list[dict]]:
        attempts: list[dict] = []
        feedback = None
        for _ in range(self.policy.repair_attempts + 1):
            raw = await self.model.forecast(state.model_copy(deep=True), rationale, feedback)
            attempts.append({"raw": raw, "feedback": feedback})
            try:
                artifact = parse_artifact(raw, state, self.required)
                state.quality_gate_results["format_pass"] = True
                return artifact, attempts
            except GateRejected as exc:
                state.quality_gate_results["format_pass"] = False
                feedback = f"Repair forecast, verified citations and required coverage: {exc}"
        raise GateRejected(f"forecast repair exhausted: {feedback}")

    async def _call_tool(
        self, name: str, args: dict, cutoff
    ) -> list:
        for attempt in range(self.policy.tool_retries + 1):
            try:
                return await self.gateway.execute(name, args, cutoff)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in {429, 502, 503, 504}:
                    raise
                if attempt == self.policy.tool_retries:
                    raise
            except (TimeoutError, OSError, httpx.TransportError):
                if attempt == self.policy.tool_retries:
                    raise
            await asyncio.sleep(min(0.2 * 2 ** attempt, 1.0))
        raise AssertionError("unreachable tool retry state")

    async def run(self, state: AgentState) -> AgentForecastArtifact:
        if state.step_index != 0 or state.status != RunStatus.IN_PROGRESS:
            raise ValueError("run requires fresh state")
        validate_state_evidence(state)  # Never show unvalidated preloaded evidence to the LLM.

        run_dir = self.root / state.run_id
        if not run_dir.resolve().is_relative_to(self.root) or run_dir.is_symlink():
            raise ValueError("unsafe run destination")
        fingerprint = self._identity(state)
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            return self._cached(run_dir, fingerprint, state)

        with (run_dir / "manifest.json").open("x", encoding="utf-8") as stream:
            json.dump({"fingerprint": fingerprint, "run_id": state.run_id,
                       "required": sorted(x.value for x in self.required)}, stream)
        audit = AuditTrail(run_dir / "audit.jsonl", state.run_id)
        checkpoint(state, run_dir)

        seen: set[str] = set()
        tool_calls = 0
        failures = 0
        result: AgentForecastArtifact | None = None
        reason = "step budget exhausted"

        for index in range(state.max_steps):
            state.step_index = index
            action_record: dict = {}
            observation: dict = {}
            thought = "Failed to parse action"
            unexpected: Exception | None = None
            try:
                action, action_attempts = await self._action(state)
                action_record = action.model_dump(mode="json")
                action_record["model_attempts"] = action_attempts
                thought = action.thought
                if action.action_type == ActionType.FINALIZE:
                    result, forecast_attempts = await self._forecast(
                        state, action.rationale_summary or ""
                    )
                    observation = {
                        "status": "finalized",
                        "forecast_attempts": forecast_attempts,
                        "artifact": result.model_dump(mode="json"),
                    }
                    reason = ""
                else:
                    if tool_calls >= self.policy.max_tool_calls:
                        raise GateRejected("tool call budget exhausted")
                    key = json.dumps([action.tool_name, action.tool_args], sort_keys=True)
                    if key in seen:
                        raise GateRejected("duplicate tool query suppressed")
                    seen.add(key)
                    tool_calls += 1
                    rows = await self._call_tool(
                        action.tool_name or "", action.tool_args or {}, state.cutoff_date
                    )
                    # Validate the complete batch before mutating state.
                    previous = {x.source_id: x for x in state.accumulated_evidence}
                    for item in rows:
                        if item.source_id in previous and previous[item.source_id] != item:
                            raise GateRejected("source ID reused with different content")
                    for item in rows:
                        if item.source_id not in previous:
                            state.accumulated_evidence.append(item)
                    validate_state_evidence(state)
                    state.quality_gate_results["freshness_pass"] = True
                    observation = {
                        "status": "ok", "sources": [x.model_dump(mode="json") for x in rows],
                    }
                    state.tool_trace.append({
                        "step": index, "tool_name": action.tool_name,
                        "args": action.tool_args, "status": "ok",
                    })
                failures = 0
            except (GateRejected, ValidationError) as exc:
                reason = f"{type(exc).__name__}: {str(exc)[:500]}"
                observation = {"status": "rejected", "reason": reason}
                state.tool_trace.append({"step": index, "status": "rejected", "reason": reason})
                failures += 1
            except Exception as exc:
                # An infrastructure or programming failure is NOT a valid research abstention.
                reason = f"{type(exc).__name__}: {str(exc)[:500]}"
                observation = {"status": "failed", "reason": reason}
                state.tool_trace.append({"step": index, "status": "failed", "reason": reason})
                state.status = RunStatus.FAILED
                unexpected = exc
            finally:
                state.step_index = index + 1
                audit.append(index, thought, action_record, observation)
                if result is not None:
                    state.status = (
                        RunStatus.ABSTAINED if result.abstention_flag else RunStatus.COMPLETE
                    )
                checkpoint(state, run_dir)
            if unexpected is not None:
                raise unexpected
            if result is not None or failures >= self.policy.max_consecutive_failures:
                break

        if result is None:
            result = abstain(state, reason)
            state.status = RunStatus.ABSTAINED
            audit.append(
                state.step_index, "Budget/quality stop", {"action_type": "abstain"},
                {"artifact": result.model_dump(mode="json")},
            )
            checkpoint(state, run_dir)

        (run_dir / "artifact.json").write_text(
            result.model_dump_json(indent=2), encoding="utf-8"
        )
        return result
