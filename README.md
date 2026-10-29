# AI Agent Research Loop for Quantitative Trading

A Python 3.11+ **read-only forecasting and hypothesis research** package. The deterministic harness enforces typed contracts, bounded ReAct steps, point-in-time (PIT) evidence checks, citations, repair loops, append-only tamper-evident traces, and a parallel forecasting ensemble.

**Status:** a runnable, testable research foundation, not a production-qualified forecasting system. It does not execute strategies, ingest authenticated market datasets, or deploy trading systems. `--demo` uses synthetic fixtures, not market evidence.

## Quickstart

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
pytest -q
python -m src.cli --demo
```

Outputs: `runs/<research-id>-wXX/{audit.jsonl,artifact.json,state_*.json}` and `runs/batch.json`.

## Architecture

- `src/core/models.py`: Pydantic V2 strict state/action/evidence/artifact contracts, UTC timestamps.
- `src/core/audit.py`: SHA-256 chained JSONL triplets; OS append+fsync, tamper-evident not hardware WORM.
- `src/core/checkpoints.py`: exclusive state snapshots; replay investigation starting points.
- `src/harness/engine.py`: max-step and tool-call budgets, schema correction, duplicate suppression, bounded retries, abstention.
- `src/harness/gates.py`: PIT, coverage, artifact schema, citation consistency gates.
- `src/tools/pit.py`: read-only allowlist and provider-level cutoff injection; rejects post-cutoff results and unversioned evidence.
- `src/tools/providers.py`: synthetic offline fixture provider for deterministic CI.
- `src/harness/model.py`: minimal OpenAI-compatible chat-completions JSON model adapter (not enabled through CLI without a real PIT provider).
- `src/multi_agent/`: concurrent isolated workers, linear base-rate extremization, policy-bound supervisor decision.
- `src/workflow/registry.py`: append-only strategy-thesis contracts for handoff into ML4T/Warden.

## Point-in-time correctness

`published_at` and `available_at` are mandatory for every source; revised data requires `revision_available_at`. All must be <= the requested cutoff. Publication time is not the same as the event or economic observation date. The harness rejects a mixed batch rather than silently dropping future observations. A provider claiming false timestamps remains a provenance risk: only trust verified historical revisions, snapshots and archival source logs.

## Quant strategy workflow

The forecasting ensemble is **stage-zero research support**, not validation evidence. Strategy thesis registration requires mechanism, universe, timeframe, execution lag, costs and predeclared falsification. Actual Stage 1+ feature testing, purged CV, frictions, DSR, protected holdouts, and deployments must run through the separate governed ML4T/quant-lab pipeline. No broker/order APIs are provided.

## Aggregation and supervisor

Non-abstaining probability mean is extremized as `clip(base_rate + gamma*(p_mean-base_rate), 0, 1)`. `gamma` defaults to 1.0 and MUST be estimated on an appropriate historical calibration set before using values >1 in decision-making. Fewer than two forecasts yields no consensus. Supervisor overrides need variance above threshold, confidence >0.85, and two verified non-conflicting cited observations; no LLM-generated self-confidence is accepted as calibrated accuracy.

## Scheduled workflow

`.github/workflows/batch_research.yml` runs Mondays at 03:17 UTC **in synthetic fixture mode only**; it uploads evidence, logs, and artifact for inspection. To schedule real research, integrate a licensed source that supports historical as-known timestamps and a model provider, add secrets securely, and replace the demo command. Do not trust web search snippets for historical financial facts without archive-availability proof.

## Production-hardening gaps

- No licensed live PIT web/SEC/market connector yet; fixture mode only.
- Model request adapter is present, but not wired to live scheduled runs.
- Supervisor decision is a separate callable policy and not yet orchestrated with targeted clarification searches.
- JSONL hash chain is tamper-evident but not externally anchored or WORM.
- Checkpoints support inspection, not fully deterministic end-to-end replay of all stochastic model responses.
- No outcome-resolution, calibration training, Brier/ECE monitoring or measured forecast quality.
- No native ML4T/Warden execution integration; stage 1–4 advancement is deliberately excluded.
- For reliable unattended operation, add provider SLAs, external audit anchors, durable retries, alerts, alert ownership, and failure-injection tests.

Do not present synthetic forecasts or uncalibrated probabilities as trade signals.
