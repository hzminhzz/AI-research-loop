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

Or use the installed `quant-paper-research` compatibility command. Each invocation:

1. Validates Warden worktree integrity and the pinned real-data contract `CRYPTO_PERPS_1H_V2`.
2. Queries public OpenAlex academic metadata, independently cross-checks DOI publication dates against Crossref, rejects missing abstracts/retractions/post-2024 sources, and captures the current records in a SHA-256 pinned local archive.
3. Uses `poolside/laguna-s-2.1:free`, falling back to `cohere/north-mini-code:free` on provider errors. Neither supports enforced `response_format`; the fallback uses a **no-execution function-call output channel**, and Pydantic validates both. HTTP 401/403 fail closed.
4. Generates a structured thesis **only** from the seven reviewable, pre-frozen templates in `src/autoresearch.py`. The LLM cannot generate Python, select parameter grids, lower gates or execute orders. An evidence-insufficient proposal can abstain.
5. Checks Warden's prior selection-attempt registry to suppress a repeat of an already screened template/code/contract combination. Fresh proposals export Warden-native YAML; Warden registers the thesis, verifies prefix-invariance and executes **one** Stage 1 screen.
6. Stops on Stage 1 pass, reject, abstain, duplicate or any blocker. It never runs Stage 2+, reads holdouts, performs optimization, or changes Warden governance.

The source archive is **captured today**: the current OpenAlex abstract is not independently proven to be the exact version available in 2021. Crossref verifies publication dates, not historical text vintages. Current paper abstracts may be sent to OpenRouter's free model providers, which may retain or train on such inputs. **Do not submit private company data or protected trading records to these free endpoints.**

A completed real-data run is documented at `examples/autoresearch_live_20261029/`. The model selected a four-hour shock-reversal strategy; Warden Stage 1 rejected it, recording one real selection attempt. The original papers are hypotheses, **not a verified edge in Binance perpetuals**.

The default and opt-in GitHub Actions synthetic/archival forecasting workflows are unchanged. Autonomous Stage 1 is intentionally **VPS-local only**: an ephemeral GitHub runner does not have the pinned `quant-lab` dataset, append-only Warden registry, or the local `.env` key.

**Limits:** only seven frozen strategy templates; no calibrated forecasting, licensed historical-vintage web service, live API market-data ingestion, automatic strategy-family expansion, or validated holdout outcomes. Free models can be rate limited or retired at any time. Failed model requests and duplicate thesis selections do not consume Warden trials.

## Continuous contract-aware practitioner research (v0.5)

**This is the default automated research command. Academic papers are no longer
used by the continuous intake.** The former academic pipeline is an explicitly
separate `quant-paper-research` compatibility command and is NOT scheduled.

```bash
# One immediate cycle (source discovery -> model -> one Warden Stage 1 attempt).
python -m src.social_campaign --once

# Test and catalog all configured sources WITHOUT calling an LLM or Warden.
python -m src.social_campaign --sources-only

# Durable read-only status, source health and recent outcomes.
python -m src.social_campaign --status

# Interactive continuous loop, 30-minute polling and automatic exit after pass/budget.
python -m src.social_campaign --loop --interval-seconds 1800

# Emergency stop; status remains persisted and future timer cycles become no-ops.
python -m src.social_campaign --stop
python -m src.social_campaign --resume
```

**Ranked research sources:** All eight requested providers are explicitly configured
in `src/tools/source_registry.py`. The source collector retrieves only original
publisher/repository content and records whether each provider is readable.

| Priority | Source | Capture method | Research focus |
| --- | --- | --- | --- |
| 1 | [Trading Research Hub / pedma](https://www.tradingresearchub.com/) | Custom-domain Substack RSS | Crypto trend/carry/cross-sectional ideas |
| 2 | [Breakout Trading Academy](https://breakouttradingacademy.com/blog/) | Original WordPress RSS + permitted public article body | Index breakout ideas may route to approved NQ/ES 5m template only when rules match exactly |
| 3 | [Robot Wealth](https://robotwealth.com/blog/) | Original WordPress RSS + permitted public article body | Stat arb and economic mechanisms; deferred when non-crypto |
| 4 | [Quantitativo](https://www.quantitativo.com/) | Custom-domain Substack RSS | Factors and long-short research |
| 5 | [Quantified Strategies](https://www.quantifiedstrategies.com/) | Official [Substack publication feed](https://quantifiedstrategies.substack.com/) | Mean reversion, seasonality; the main-site RSS currently serves a challenge page |
| 6 | [Freqtrade Strategies](https://github.com/freqtrade/freqtrade-strategies) | GitHub public API, **commit and blob-pinned** Python text | **Deferred** as unmapped code examples; not screened, imported or executed |
| 7 | [QuantConnect Community Strategies](https://www.quantconnect.com/strategies/) | Official public strategy-directory probe | When the JS directory provides no verifiable public strategy rule, report `INDEX_ONLY_JS_RENDERED_NO_VERIFIABLE_PUBLIC_STRATEGY` and create no fabricated item |
| 8 | [Alvarez Quant Trading](https://alvarezquanttrading.com/blog/) | Original WordPress RSS + public article body | Equity/ETF mean reversion; deferred until appropriate data and contracts exist |

Existing independent feeds from Delphic Alpha, Empirica Lab, Trading Time
Machine, Stoic Research and others are retained without duplicating the
Quantified Strategies publication. **No X.com connector, token, or fallback is used.**

The campaign writes `runs/social_campaign/source_catalog.json` with a source-by-source
health report, eligible crypto **and index** strategy URLs, and deferred unsupported
markets/code. Freqtrade strategy files are also archived in this deferred catalog with
`CODE_ONLY_REQUIRES_FROZEN_RULE_MAPPING`; they cannot serve as Warden citations
until entry/exit logic, direction and timeframe are explicitly mapped to a
reviewed executable rule. The initial pre-mapping run is preserved in Warden
as a negative adaptation, not reported as a faithful code replication.
Run `--sources-only` for a safe refresh without creating another Warden trial.
Each cycle may discover rules from all eight original providers. Eligible entries
are automatically routed to **frozen, matching Warden market/timeframe contracts**;
unsupported market and source-rule mismatches are blocked before registry writes.

Each current capture logs the original URL, publication and observation timestamps,
source-text hash, code provenance, market classification,
prompt-injection boundary, model route, selected template, Warden attempt ID, and
terminal disposition. **These are current captures, not evidence of what an
original post said in 2024.** Posts from after the 2025 exploratory validation
window carry `post_publication_validation=true`; even a Stage 1 PASS remains
a hypothesis-selection result, not an independent OOS confirmation.

**Research policy:** Eleven immutable executable profiles cover crypto
5m/1h/4h/daily, broad crypto 1h and US NQ/ES 5m. Laguna S 2.1 is primary,
North Mini Code is fallback. A social-source proposal must give **verbatim
entry and exit quotes from one original post**, explicitly identified market,
bar timeframe, direction, holding bars, rebalance schedule and source assets.
The router checks exact quote containment, trigger constants, instrument fit,
execution-observable requirements and the authorized frozen contract. A generic
keyword match is insufficient. The LLM cannot write executable Python, tune
thresholds, alter Warden costs, access holdouts or place orders.

**Available routes:** `CRYPTO_PERPS_1H_V2` (1-8 explicitly sourced majors),
`CRYPTO_PERPS_TOP100_1H_V1` (88 instruments present on the original 2023-01-01
inception timestamp; no ex-post survivor selection),
`CRYPTO_PERPS_5M_V1`, `CRYPTO_PERPS_4H_V1`, `CRYPTO_PERPS_1D_V1`, and
`INDICES_5M_V1` (NQ/ES US regular trading hours, NY daylight-saving time).
Each route verifies the immutable SHA-256 against its manifest, expected
frequency, market, exploration/validation boundary, required columns, OHLC
integrity and Warden next-bar execution policy. The contract remains the sole
owner of actual costs and funding. Preflight reports 1x, 2x and 3x modeled
cost assumptions, explicitly marked **not calibrated to real bid/ask or fills**.
Sources requiring order-book, bid/ask, open-interest or maker-execution data
are blocked unless those observables exist. This is not a claim that any
strategy will be profitable. Existing retrospective sources remain labeled
`RETROSPECTIVE_DISCOVERY_NOT_INDEPENDENT_OOS` after routing.

A Warden `STAGE_1_PASS` **stops further research** and flags the candidate for
human scientific review and Stage 2. Scientific limits are 20 distinct Stage 1
screens per campaign and six source/model cycles per UTC day. Daily limits
reset, but total attempts remain recorded. If the fixed templates or fresh
strategy posts are exhausted, the campaign pauses and polls for new source
material. A single fully specified author post is sufficient; only genuinely
cited sources are consumed rather than discarding an entire five-post batch. It never generates infinite near-identical variants to force a pass.
Every negative Stage 1 screen is retained in Warden's selection-history ledger;
re-screening a previously used template/contract is blocked.

A user-level systemd timer template is in `deploy/` and schedules a cycle
30 minutes after the previous one completed:

```bash
systemctl --user link "$PWD/deploy/quant-social-research.service"
systemctl --user link "$PWD/deploy/quant-social-research.timer"
systemctl --user enable --now quant-social-research.timer
systemctl --user list-timers quant-social-research.timer
journalctl --user-unit quant-social-research.service -n 40 --no-pager
```

Unit files contain no credentials; the Python process reads the ignored `.env`
locally. Timer activation requires a running user systemd manager/lingering.
Use `systemctl --user disable --now quant-social-research.timer` to stop scheduling.

**Quantitative caveat:** Repeatedly screening strategies on the same validation
period inflates false-positive probability. Stop-at-first-pass is just a
discovery funnel; any passing candidate must be examined with Warden's
trial-history and deflated Sharpe / untouched OOS controls before making
economic claims. No guarantee of a passing or profitable strategy is made.

## GitHub Actions

`.github/workflows/ci.yml`: contract tests, regression tests, synthetic smoke and frozen replay.

`.github/workflows/batch_research.yml`: Monday 03:17 UTC. Default mode runs synthetic fixtures, with named synthetic artifacts. Real archive mode is opt-in: set Actions variable `RESEARCH_MODE=archive`, variable `PIT_ARCHIVE_SHA256`, secret `LLM_API_KEY`, and provide `data/archived_evidence.json` and `data/questions.json`. It fails closed if any required source or credential is absent.

## Limitations

No licensed historical-vintage PIT web/SEC/market connector, cryptographically attested data history, resolution oracle, external audit anchor, inference cost dashboard, load/chaos testing, or verified profitable trading strategy is bundled. The pipeline is a **research component**, not a trading execution system or an independent substitute for Warden.
