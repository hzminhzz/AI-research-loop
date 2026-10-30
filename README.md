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

**Ranked research sources:** The eight original practitioner sources and a newly
approved ninth public X-post reader are configured in `src/tools/source_registry.py`.
The collector records origin, third-party capture provenance, and source health.

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
| 9 | [Public X strategy posts via mdfromx](https://mdfromx.com/docs/posts) | Versioned v1 read-only search + verified public status post, no X API key | Bounded search, source-faithful excerpts, incomplete rules deferred |

Existing independent feeds from Delphic Alpha, Empirica Lab, Trading Time
Machine, Stoic Research and others are retained without duplicating the
Quantified Strategies publication. Public X posts are now user-approved via
`mdfromx.com`; the old direct X bearer-token integration remains removed.

The campaign writes `runs/social_campaign/source_catalog.json` with a source-by-source
health report, eligible crypto **and index** strategy URLs, and deferred unsupported
markets/code. Freqtrade strategy files are also archived in this deferred catalog with
`CODE_ONLY_REQUIRES_FROZEN_RULE_MAPPING`; they cannot serve as Warden citations
until entry/exit logic, direction and timeframe are explicitly mapped to a
reviewed executable rule. The initial pre-mapping run is preserved in Warden
as a negative adaptation, not reported as a faithful code replication.
Run `--sources-only` for a safe refresh without creating another Warden trial.
Each cycle may discover rules from all eight original providers plus the public
X reader. Eligible entries
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

### Public X-post source via x.md (user-approved, 2026-10-30)

The ninth ranked source, `x_public_posts`, uses the documented
[x.md / mdfromx v1 post API](https://mdfromx.com/docs/posts)
and [v1 search API](https://mdfromx.com/docs/search). Public X content
is retrieved by the fixed HTTPS host `mdfromx.com`, while evidence retains
the **original x.com status URL**, author, publication timestamp and separate
current capture date. No X login, X API bearer token, private account access
or paywall bypass is used. The hosted third-party service is best-effort and
rate-limited; it is NOT a guaranteed complete X historical feed.

```bash
# Verify one exact public permalink; no model, Warden or order execution.
python -m src.tools.x_md --url \
  https://x.com/QuantAlphaXXX/status/2109422015572545729

# At most 2 bounded top-feed searches, 8 results each, 4 verified post reads.
python -m src.tools.x_md --scan

# Include X alongside the original practitioner feeds in source health.
python -m src.social_campaign --sources-only
```

The source adapter validates post IDs, handles, dates, API hostname, content
type, upstream warnings, and origin links. It does not follow arbitrary
links embedded in tweets, fetch protected posts, or use degraded web-indexed
snippets as verified results. Invalid or rate-limited responses fail that
source independently; they do not abort the other eight.

Results are **current third-party captures**, not evidence that the exact
post text was available before an older backtest period. A post without a
recognizable numeric entry AND exit rule stays
`X_POST_NEEDS_SOURCE_RULE_FIDELITY_REVIEW` in the deferred catalog; it is
never automatically matched to an unrelated Warden template. All ideas still
require verification against the original post, actual historical market
data, transaction costs, execution timing, and multiple-testing history.
No Warden trial is consumed by ingestion alone.

The original archived source set and daily archive scan are unchanged; this
source runs on the existing bounded practitioner campaign. It is deliberately
not a general X firehose or a bulk import of user timelines.

## Autonomous contract creation (v0.6)

`src/workflow/contract_factory.py` supplies a deterministic contract compiler
for research-agent use. The model may **request** a source-specific horizon or
market, but it cannot edit Warden YAML, lower a trading cost, invent source
snapshots, move a validation split, or access protected holdouts. The compiler
derives a versioned contract from the immutable **parent market dataset** and
pins the identical SHA-256 with its original data provenance.

```bash
# Dry-run only: creates NO contracts and consumes NO trials.
python -m src.workflow.contract_factory \
  --quant-lab /home/quant/dev/quant-lab \
  --request-json examples/contract_factory/funding_level_24h_request.json

# One-time delegated research contract activation, for a source whose
# derived contract ID does not already exist (uses an explicit operator grant).
RESEARCH_CONTRACT_DELEGATION=principal-approved-2026-10-30-research-contracts \
python -m src.workflow.contract_factory \
  --quant-lab /home/quant/dev/quant-lab \
  --request-json path/to/new_reviewed_source_request.json \
  --activate
```

Activation is fail-closed: approved parent contracts only, exact pinned market
bytes, no unknown provenance, no missing mandatory columns, compatible
label/embargo versus validation fold width, conservative fee/slippage floors,
unmodified prior Warden manifest entries, exclusive new-file creation and a
hard maximum of eight derived research contracts. It records a cross-contract
**selection group** and the existing underlying-dataset selection-attempt count;
a new contract ID is never evidence of an independent OOS test.

This operator delegation is **not** a human-held HMAC signing key. If the Warden
manifest has an independent digital signature, automated activation is refused.
Each research-only addition is explicitly labeled as delegated and unsigned.
Full evaluation still follows Warden, and production holdout unsealing, broker
orders and capital allocation are not delegated.

The first live use created
`AUTO_CRYPTO_PERPS_TOP100_1H_V1_H24_E24_F45_S20_V1` from the existing
Binance top-100 1h snapshot. The data digest and split were unchanged; the
evaluation horizon/embargo were raised to 24 hours and taker fee floor to 4.5
bps/side. Warden verified a Binance-only adaptation of a publicly published
funding-level strategy (1,926,144 bars), then **rejected Stage 1** at profit
factor 1.130, against a required minimum 1.150. This is a counted negative
attempt, **not** approval for a live strategy. Details remain in quant-lab
`.workspace/hypotheses/HYP-AUTO-FUNDING7D-BINANCE-20261030_RESULT.md`.

**Remaining work for full hands-free strategy research:** The current
`social_campaign` still picks from reviewed frozen templates and has a
bounded daily cycle quota. The contract factory is independently callable, but
it is not a general unrestricted AI-to-Python compiler or a self-attesting
data-vendor connector. Arbitrary source-specific code generation, fresh data
provider integration and full stage 2/3 retry orchestration require a separate
sandboxed agent executor and validation before deployment. Do not claim those
features already run automatically.

## Incident-safe Warden research (2026-10-30)

The actual VPS host (`vmi2637217`, user `quant`) owns the user-level `quant-social-research.timer`.
A ChatGPT/cloud-local `systemctl` error is **not** evidence this VPS timer is absent.
Run all host checks through the connected VPS-cloudflare service.

Residual reversal hypothesis `HYP-2026-128` has 159 previously unregistered
diagnostic cells and a holding/label-horizon mismatch. Full trials
`RUN-XSRR-001` and `RUN-XSRR-002` have immutable rejected audits and now
append-only `QUARANTINED` dispositions. They remain counted but are **ineligible**
for promotion. Missing historical multiplicity has **not** been repaired.

The previous manifest diff consists of exactly two research-only additions for
`AUTO_CRYPTO_PERPS_TOP100_1H_V1_H24_E24_F45_S20_V1` and its dataset manifest,
under delegated **unsigned** principal approval. All 84 original protected entries
match their Git baseline and hashes. This is not independent HMAC attestation.

The timed-out `HYP-2026-126` verify has **no terminal job receipt**. That
candidate remains individually blocked, not a global research stop. It has
two historical rejected Stage 1 screens and zero full Warden trials.

Read-only reconciliation:

```bash
cd /home/quant/dev/AI-research-loop
python -m src.workflow.governance_guard --quant-lab /home/quant/dev/quant-lab check
```

The timer uses the same preflight and holds an exclusive cross-agent `flock` on
`/home/quant/dev/quant-lab/registry/warden-writer.lock` during its run.
All hourly agent Warden writes must use the typed guard wrapper:

```bash
python -m src.workflow.governance_guard --quant-lab /home/quant/dev/quant-lab run -- uv run warden status --json
# For a distinct, preregistered strategy with a new experiment spec:
python -m src.workflow.governance_guard --quant-lab /home/quant/dev/quant-lab run -- uv run warden screen experiments/active/independent_candidate.yaml --json
```

The wrapper fails closed for known contaminated or unresolved lineages, unsafe
spec paths, concurrent lock holders, and mismatched manifest provenance.
Other independently implemented agents can still bypass this cooperative lock;
the research director must not do so. For future long verifications, require
a durable job ID and terminal receipt rather than retrying an unknown timeout.
Protected holdouts and live orders remain outside this research authority.
### Durable long-running Warden jobs

Submitting a long verification directly through a short-lived MCP shell can
lose its exit status. Use an idempotent systemd user job instead:

```bash
cd /home/quant/dev/AI-research-loop
python -m src.workflow.durable_jobs submit -- \
  uv run warden verify experiments/active/new_distinct_candidate.yaml --json

# Submit returns a job ID such as warden-verify-<18hex>.
python -m src.workflow.durable_jobs poll --job-id warden-verify-<18hex>
```

The job ID hashes the exact experiment spec, strategy code, approved manifest
and Warden CLI arguments. A repeated submit returns the prior job without
re-running it, even if its initial tool response was lost. The service executes
the governance guard and shared writer lock; a bounded runtime, memory limit
and terminal receipt are retained in `runs/warden_jobs/`. `UNKNOWN_TERMINAL`
is a blocker for that ID, never permission to submit a duplicate.

Historically timed-out HYP-2026-126 cannot be retroactively assigned a valid
job ID. It remains scoped as unresolved until independently reconciled.
## Practitioner archive discovery (2026-10-30)

The former live source feed saw only three Breakout Trading Academy items.
The separate archive scout `src/tools/archive_discovery.py` now indexes public
publisher sitemaps, QuantConnect's 83-card investment-strategy library,
Finetiq's English idea URLs, and the SHA-pinned Backtrader regression-test
tree. Quantified Strategies uses its own Substack feed when the main
WordPress sitemap is unavailable; it does not bypass protection or paywalls.

```bash
# Safe source-only scan: no Warden or protected holdout use.
python -m src.tools.archive_discovery --output runs/archive_discovery \
  --target 50 --seed-catalog runs/archive_discovery/catalog.json

# Compact outputs, sorted by reviewed research fit:
ls runs/archive_discovery/
# catalog.json (all URL metadata and 142 briefly extracted leads),
# shortlist.json (50 diverse source-backed leads), report.md
```

The validated 2026-10-30 run indexed BTA 521 URLs (137 keyword matches),
QuantConnect 83 strategy articles, Finetiq 75 English ideas, Backtrader
1,154 strategy test files, Quantified Strategies 15 public Substack posts,
Algomatic 59 blog URLs, and Financial Hacker 64 original posts.
The pilot reviewed 142 public original pages/code identifiers and produced
50 deduplicated, source-diverse research *leads*. Detailed evidence and
review priorities are checked in under
`examples/practitioner_archive_20261030/`.

Safety: only exact allowlisted HTTPS publisher hosts, robots-policy checks,
strict one-hop first-party QuantConnect article redirects, bounded HTTP
requests and size limits, no untrusted code execution, no accounts/paywall
bypass, SHA-pinned GitHub code references and small quoted excerpts rather
than scraped full-article redistribution. Re-using a previous GitHub index
is allowed only when its item-level immutable commit and blob SHAs verify.
Publisher pages are untrusted evidence, never shell or model instructions.

All leads are tagged `DISCOVERY_ONLY_NO_WARDEN_ATTEMPT` and include original
URL, current capture timestamp, text hash, market/family hints, source rule
excerpts (or explicit incomplete state), probable data contract and risk
notes. The classification is intentionally conservative: a source's title
or regression test is NOT a replicable trading strategy; author claims of
performance are NOT independent validation. Equity ETF ideas are not
silently transformed into index CFDs, and source publication dates do not
prove text availability before 2025 validation.

A separate daily VPS user timer refreshes the discovery queue without
touching Warden:

```bash
systemctl --user link "$PWD/deploy/quant-archive-discovery.service"
systemctl --user link "$PWD/deploy/quant-archive-discovery.timer"
systemctl --user enable --now quant-archive-discovery.timer
systemctl --user list-timers --all quant-archive-discovery.timer
```

The schedule is 02:20 UTC daily with up to 20min randomized jitter,
with no catch-up burst on installation. The existing 30-minute Warden
source-screening timer is unchanged. Hourly agent-led research should
start with `runs/archive_discovery/shortlist.json`, inspect the original
article for full entry/exit/source-vintage, and then preregister Warden
experiments only when the source rule and market data are truly sufficient.
## GitHub Actions

`.github/workflows/ci.yml`: contract tests, regression tests, synthetic smoke and frozen replay.

`.github/workflows/batch_research.yml`: Monday 03:17 UTC. Default mode runs synthetic fixtures, with named synthetic artifacts. Real archive mode is opt-in: set Actions variable `RESEARCH_MODE=archive`, variable `PIT_ARCHIVE_SHA256`, secret `LLM_API_KEY`, and provide `data/archived_evidence.json` and `data/questions.json`. It fails closed if any required source or credential is absent.

## Limitations

No licensed historical-vintage PIT web/SEC/market connector, cryptographically attested data history, resolution oracle, external audit anchor, inference cost dashboard, load/chaos testing, or verified profitable trading strategy is bundled. The pipeline is a **research component**, not a trading execution system or an independent substitute for Warden.
