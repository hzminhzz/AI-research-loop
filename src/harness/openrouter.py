"""OpenRouter-only research adapter: primary/fallback, no remote JSON-mode assumptions."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

PRIMARY = "poolside/laguna-s-2.1:free"
FALLBACK = "cohere/north-mini-code:free"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
T = TypeVar("T", bound=BaseModel)


def load_openrouter_key(path: str | Path = ".env") -> str:
    """Use the explicitly selected local secret file without exporting or printing it."""
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        from dotenv import dotenv_values
        key = str(dotenv_values(path).get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY missing from environment or local .env")
    return key


@dataclass(frozen=True)
class ModelAttempt:
    model: str
    status: str
    error_type: str = ""


@dataclass(frozen=True)
class ModelReply:
    parsed: BaseModel
    selected_model: str
    attempts: list[ModelAttempt]


def strict_json(content: str) -> dict[str, Any]:
    value = content.strip()
    fence = chr(96) * 3
    if value.startswith(fence):
        lines = value.splitlines()
        if lines and lines[0].lower() in (fence, fence + "json") and lines[-1] == fence:
            value = "\n".join(lines[1:-1]).strip()
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("model response must be a single JSON object")
    return parsed


class ModelUnavailable(RuntimeError):
    pass


class OpenRouterFallback:
    """One primary attempt, then fallback, then at most one schema repair on fallback.

    A 401/403 is fatal; fallback shares the credential. 429 does not retry.
    """

    def __init__(self, api_key: str, timeout: float = 105.0):
        self._key = api_key
        self.timeout = timeout

    async def _request(
        self, client: httpx.AsyncClient, model: str,
        system: str, task: dict[str, Any], schema: dict[str, Any],
        repair_feedback: str | None = None,
    ) -> str:
        prompt = {
            "task": task, "output_json_schema": schema,
            "repair_feedback": repair_feedback,
            "policy": "Output one JSON object. Do not use markdown code fences or prose.",
        }
        payload = {
            "model": model, "temperature": 0.2,
            "max_tokens": 2600 if model == FALLBACK else 1600,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
        }
        if model == FALLBACK:
            # This model supports tool calling but not response_format JSON mode.
            # The tool is an output channel ONLY: no application action executes.
            payload.update({
                "reasoning": {"enabled": False},
                "tools": [{"type": "function", "function": {
                    "name": "emit_json", "description": "Return the structured research proposal",
                    "parameters": schema,
                }}],
                "tool_choice": "required", "parallel_tool_calls": False,
            })
        response = await client.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
        message = body.get("choices", [{}])[0].get("message") or {}
        calls = message.get("tool_calls") or []
        if calls:
            if len(calls) != 1 or calls[0].get("function", {}).get("name") != "emit_json":
                raise ValueError("Unexpected or multiple model tool calls")
            arguments = calls[0]["function"].get("arguments")
            if not isinstance(arguments, str):
                raise ValueError("Model tool arguments are not JSON text")
            return arguments
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("OpenRouter returned empty model content")
        return content

    async def generate(self, schema_cls: type[T], task: dict, system: str) -> ModelReply:
        schema = schema_cls.model_json_schema()
        attempts: list[ModelAttempt] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for model in (PRIMARY, FALLBACK):
                feedback = None
                for schema_try in range(2 if model == FALLBACK else 1):
                    try:
                        raw = await self._request(client, model, system, task, schema, feedback)
                    except httpx.HTTPStatusError as exc:
                        status = exc.response.status_code
                        attempts.append(ModelAttempt(model, f"http_{status}", "HTTPStatusError"))
                        if status in {401, 403}:
                            raise PermissionError(f"OpenRouter authentication failed (HTTP {status})") from None
                        if status in {400, 404, 408, 409, 429, 500, 502, 503, 504}:
                            break
                        raise
                    except (httpx.TransportError, ValueError) as exc:
                        attempts.append(ModelAttempt(model, "unavailable", type(exc).__name__))
                        break
                    try:
                        parsed = schema_cls.model_validate(strict_json(raw))
                    except (ValueError, ValidationError) as exc:
                        attempts.append(ModelAttempt(model, "invalid_json", type(exc).__name__))
                        feedback = f"Previous output invalid: {str(exc)[:400]}. Return complete valid JSON."
                        continue
                    attempts.append(ModelAttempt(model, "ok"))
                    return ModelReply(parsed=parsed, selected_model=model, attempts=attempts)
        raise ModelUnavailable(
            "OpenRouter primary and fallback failed: " +
            ", ".join(f"{a.model}:{a.status}:{a.error_type}" for a in attempts)
        )
