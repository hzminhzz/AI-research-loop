# AI Agent Research Loop for Quantitative Trading

**Status: research harness, not a validated profitable strategy or live trading engine.** Python 3.11+. This repository implements a read-only, point-in-time (PIT) forecasting and hypothesis research layer. Strategy validation and deployment remain under ML4T/quant-lab Warden control.

## Quickstart

```bash
git clone https://github.com/hzminhzz/AI-research-loop.git
cd AI-research-loop
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[test]"
python -m pytest -q
python -m src.cli --demo
python -m src.cli --demo          # identical input reuses verified run artifacts
python -m src.harness.replay \
  --source-run runs/v3/synthetic-event-001-w00 \
  --output runs/replay
```

The demo outputs **synthetic** probabilities, not market-derived forecasts. Original artifacts in the older `runs/<id>` layout are preserved. The new default is `runs/v3/` because legacy runs and earlier development runs do not have the same immutable input fingerprint.

## Architecture

| Module | Responsibility |
| --- | --- |
| `src/core/models.py` | Pydantic V2 state, actions, evidence, forecasts, run IDs, supervisor contracts |
| `src/core/audit.py` | Append-only, SHA-256 chained JSONL triplets; verifies integrity on reads |
| `src/core/checkpoints.py` | Exclusive state snapshots with explicit quality-gate outcomes |
| `src/harness/engine.py` | Bounded ReAct, repair prompts, duplicate suppression, retries, abstention and system-error separation, idempotent run identity |
| `src/harness/gates.py` | Validates **all** preloaded and fetched PIT evidence, coverage, and citations |
| `src/harness/replay.py` | Frozen successful-run replay without model or external provider access |
| `src/tools/pit.py` | Read-only tool allowlist and enforced cutoff injection |
| `src/tools/archive.py` | Pinned historical capture catalog with captured timestamps and source versions |
| `src/multi_agent/` | Parallel specialized workers, linear extremization, bounded supervisor research and policy override |
| `src/metrics.py` | Brier score and expected calibration error (ECE) for resolved, time-ordered events |
| `src/workflow/warden.py` | Native Warden hypothesis export **without** touching quant-lab or holdout data |

## Point-in-time evidence

Every observation requires `published_at` (publication), `available_at` (when a decision maker could know it), a source identifier, and source URL. Revised observations require a separate revision timestamp; those whose revisions came after the cutoff are rejected. If a starting `AgentState` contains future evidence, it is rejected **before** reaching any model, even if that evidence is uncited. The gate never counts future evidence toward a required source type.

In real archive mode, records additionally require:

```json
{
  "source_id": "original-release-2026-001",
  "kind": "historical",
  "uri": "https://example.org/original-release",
  "published_at": "2026-01-01T00:00:00Z",
  "available_at": "2026-01-01T00:00:00Z",
  "archived_at": "2026-01-01T09:00:00Z",
  "source_version": "original-release-v1",
  "snippet": "Original unrevised observation at decision time.",
  "provider": "institutional_archive",
  "facts": {"observation": "value-from-original-release"}
}
```

The record is eligible only when **all** timestamps, including archival capture, precede the research cutoff. A current vendor snapshot retrospectively labeled with an old date is NOT proof of PIT correctness. SHA-256 pins file bytes; it does not prove the vendor's asserted timestamps are truthful.

## Research using a pinned historical archive

Prepare a historically captured JSON array and a research-questions JSON file (format in `examples/questions.json`). Both must contain real, documented provenance. Set `LLM_API_KEY` in the environment and choose an OpenAI-compatible model:

```bash
python -m src.cli \
  --archive data/archived_evidence.json \
  --archive-sha256 "<verified-64-character-SHA256>" \
  --questions data/questions.json \
  --workers 3 --steps 10 --gamma 1.0 \
  --model "<compatible-model-id>" --output runs/research-001
```

No real archival dataset, API credentials, or calibration set is bundled. Live web search and vendor feeds are **not** integrated. Archive search is deterministic keyword matching, not a relevance-reranked commercial search API.

Gamma defaults to 1.0 (ordinary average). The formula `clip(base_rate + gamma * (mean - base_rate), 0, 1)` follows the requested linear extremization contract. Do **not** use gamma > 1 for decisions before evaluating it on independent resolved events.

## Deterministic research and supervisor policy

Run IDs are safe path components. A repeated identical invocation reuses verified completed artifacts. An altered request with the same ID, an unfinished run, or a tampered audit fails explicitly instead of turning into a fake abstention. Model and tool retries are bounded. Persistent model/provider errors are reported as failures, not profitable or qualified forecasts.

Workers may have distinct roles and model temperatures; temperature alone does not create independent data. A supervisor is invoked only when its probability-variance divergence threshold is exceeded. It may perform at most two targeted searches; overriding the aggregate requires >0.85 confidence and **two distinct valid, nonconflicting PIT citations**. This is a rule-based control, not proven forecast calibration.

Audit entries contain model responses, cited tool observations, and policy decisions. Replay verifies the hash chain and reproduces the forecast using frozen model and tool responses:

```bash
python -m src.harness.replay \
  --source-run runs/v3/synthetic-event-001-w00 --output runs/replay
```

Current replay supports successful model and tool steps, including repair attempts. It does not resume an interrupted run or independently certify that a rewritten entire audit log is original; external audit anchoring is needed for that guarantee.

## Objective probability evaluation

For resolved binary events, create a JSON array of `ResolvedForecast` records: `research_id`, `method` (`worker`, `consensus`, `supervisor`), `forecast_at`, `resolved_at`, `probability`, `outcome`, `resolution_source`. Outcomes must resolve after forecasts and not in the future.

```bash
python -m src.metrics --resolutions path/to/resolved-events.json
```

This reports Brier, binned ECE, and sample-size warnings by method. The repo does not fabricate ground truth or imply predictive accuracy from its synthetic demos. Formal calibration, resolution verification, and OOS extremization calibration require actual resolved event datasets.

## Native quant-lab/Warden Stage-0 handoff

Hypothesis authoring is distinct from strategy validation. The source repo `quant-lab` remains untouched. The exporter produces Warden's native `HypothesisSpec` YAML, with explicit contract ID, strategy family, mechanism, costs/counterparty, holding period, and falsification criteria.

```bash
python -m src.workflow.warden \
  --thesis path/to/thesis.json \
  --handoff path/to/warden-mapping.json \
  --output runs/warden-handoff
```

The thesis file conforms to `src/workflow/registry.py:StrategyThesis`; the mapping conforms to `src/workflow/warden.py:WardenHandoff`. The manual exporter itself does not register or run experiments. The separate opt-in autonomous command below **can register and screen Stage 1** under Warden, but cannot backtest, unseal a holdout, or trade. Stage 2–4 causal screening, costs, trial budgets, DSR and holdout integrity remain Warden-owned.

## Autonomous OpenRouter -> Warden Stage 1 (opt-in, on the VPS)

This is a **separate, bounded one-thesis research intake**, not the generic forecasting ensemble.
The OpenRouter key is read from the local, untracked `.env` file (or `OPENROUTER_API_KEY` in the process environment). Never commit or print the key.

```bash
python -m pip install -e ".[test]"
python -m src.autoresearch \
  --env-file .env \
  --quant-lab /home/quant/dev/quant-lab \
  --output runs/autoresearch
```

Or use the installed `quant-autoresearch` command. Each invocation:

1. Validates Warden worktree integrity and the pinned real-data contract `CRYPTO_PERPS_1H_V2`.
2. Queries public OpenAlex academic metadata, independently cross-checks DOI publication dates against Crossref, rejects missing abstracts/retractions/post-2024 sources, and captures the current records in a SHA-256 pinned local archive.
3. Uses `poolside/laguna-s-2.1:free`, falling back to `cohere/north-mini-code:free` on provider errors. Neither supports enforced `response_format`; the fallback uses a **no-execution function-call output channel**, and Pydantic validates both. HTTP 401/403 fail closed.
4. Generates a structured thesis **only** from two reviewable, pre-frozen executable templates: `shock_reversal` or `volume_breakout`. The LLM cannot generate Python, select parameter grids, lower gates or execute orders. An evidence-insufficient proposal can abstain.
5. Checks Warden's prior selection-attempt registry to suppress a repeat of an already screened template/code/contract combination. Fresh proposals export Warden-native YAML; Warden registers the thesis, verifies prefix-invariance and executes **one** Stage 1 screen.
6. Stops on Stage 1 pass, reject, abstain, duplicate or any blocker. It never runs Stage 2+, reads holdouts, performs optimization, or changes Warden governance.

The source archive is **captured today**: the current OpenAlex abstract is not independently proven to be the exact version available in 2021. Crossref verifies publication dates, not historical text vintages. Current paper abstracts may be sent to OpenRouter's free model providers, which may retain or train on such inputs. **Do not submit private company data or protected trading records to these free endpoints.**

A completed real-data run is documented at `examples/autoresearch_live_20261029/`. The model selected a four-hour shock-reversal strategy; Warden Stage 1 rejected it, recording one real selection attempt. The original papers are hypotheses, **not a verified edge in Binance perpetuals**.

The default and opt-in GitHub Actions synthetic/archival forecasting workflows are unchanged. Autonomous Stage 1 is intentionally **VPS-local only**: an ephemeral GitHub runner does not have the pinned `quant-lab` dataset, append-only Warden registry, or the local `.env` key.

**Limits:** only two frozen strategy templates; no calibrated forecasting, licensed historical-vintage web service, live API market-data ingestion, automatic strategy-family expansion, or validated holdout outcomes. Free models can be rate limited or retired at any time. Failed model requests and duplicate thesis selections do not consume Warden trials.

## GitHub Actions

`.github/workflows/ci.yml`: contract tests, regression tests, synthetic smoke and frozen replay.

`.github/workflows/batch_research.yml`: Monday 03:17 UTC. Default mode runs synthetic fixtures, with named synthetic artifacts. Real archive mode is opt-in: set Actions variable `RESEARCH_MODE=archive`, variable `PIT_ARCHIVE_SHA256`, secret `LLM_API_KEY`, and provide `data/archived_evidence.json` and `data/questions.json`. It fails closed if any required source or credential is absent.

## Limitations

No licensed historical-vintage PIT web/SEC/market connector, cryptographically attested data history, resolution oracle, external audit anchor, inference cost dashboard, load/chaos testing, or verified profitable trading strategy is bundled. The pipeline is a **research component**, not a trading execution system or an independent substitute for Warden.
