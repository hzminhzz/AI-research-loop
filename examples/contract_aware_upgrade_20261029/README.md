# Research loop v0.5 — contract-aware, source-faithful routing

**Date:** 2026-10-29
**Scope:** `hzminhzz/AI-research-loop` only. The protected `hzminhzz/quant-lab` contracts, Warden core, statistical gates and historical research registry are unchanged.

## Bottlenecks corrected

1. **Source fidelity gate.** Each new practitioner proposal must contain one original publisher's verbatim entry and exit quotes and typed market, bar timeframe, long/short policy, holding/rebalance bars, and source-named instruments. Missing or contradictory fields yield `BLOCKED_RULE_FIDELITY` and **no Warden selection attempt**. The fixed template's numeric triggers and direction must match the cited quote. Single-symbol Bitcoin rules no longer silently become eight-symbol portfolios. US index sources are not conflated with Nasdaq stocks or QQQ ETFs.
2. **Contract routing.** Eleven reviewed executable profiles route to pinned `CRYPTO_PERPS_1H_V2`, `CRYPTO_PERPS_TOP100_1H_V1`, `CRYPTO_PERPS_5M_V1`, `CRYPTO_PERPS_4H_V1`, `CRYPTO_PERPS_1D_V1`, or `INDICES_5M_V1`. Unsupported markets/timeframes/stop-loss logic are deferred or blocked, not transformed to another regime. The broad contract uses the 88 instruments observed at its **first timestamp** (2023-01-01), not the 100-asset list conditioned on survival in 2025; the late-listed subset needs a sparse-instrument execution contract before inclusion.
3. **Data integrity.** The preflight checks full exploratory Parquet SHA-256 against the frozen Warden YAML and manifest; historical start, validation end, holdout boundary, dataset frequency and class, OHLC validity, timestamp/asset uniqueness, funding presence, non-finite prices, and ex-ante cohort fit. It only opens exploratory data, never a holdout file. Unverified/unknown data or broken snapshots fail closed.
4. **Execution-cost provenance.** Warden's existing NEXT_BAR lag, fee/slippage floor and funding remain authoritative. The preflight reports modeled round-trip cost and illustrative 2x/3x sensitivity rates without pretending to have observed spreads or trades. Sources demanding maker fills, order-book, historical bid/ask or open-interest data fail closed. No rates or Stage 1 thresholds were lowered.
5. **Throughput & audit.** One independently authored source is sufficient to propose a thesis; the campaign no longer needs two unrelated posts. Only cited sources are marked used after a deterministic disposition; blocked proposals and model route are archived. Existing selection attempts cannot be erased by deleting a strategy module. The loop still stops on a native Warden Stage 1 pass or its 20-screen/6-cycles-per-day budgets.

## Evidence (read-only / isolated)

| Check | Result |
|---|---|
| Local automated tests | 89 passed |
| Pinned eight-asset 1h contract preflight | 105,024 rows, 8 assets; 6bps one way modeled |
| Broad 1h contract preflight | 2,174,396 rows, 100 present, 88 inception-available; 6bps one way modeled |
| Index 5m contract preflight | 3,485,714 rows, 6 present; eligible US RTH subset ES+NQ; 1bps one way modeled |
| Actual broad reviewed signal smoke | 21,888 timestamps x 88, all finite, max gross 0.8 |
| Actual US-index RTH signal smoke | 645,888 timestamps x 2, all finite, max gross 0.4 |
| New nested OpenRouter schema | Laguna S 2.1 valid contract; separate synthetic (non-trading) probe |
| New live practitioner cycle | `AIR-OR-20261029-165052`: `BLOCKED_RULE_FIDELITY`, no Warden trial |
| Fresh source-only scan | 12 eligible crypto/index posts; 38 deferred; 0 Warden trials |

Previously logged rejected Stage 1 screening attempts remain recorded. The first real v0.5 live cycle attempted to map a Nasdaq-stock idea onto an index template. The fidelity gate properly rejected the source-market mismatch before Warden registration. The source classifier was subsequently strengthened to defer Nasdaq stocks/QQQ ETFs as equity ideas.

## Qualification boundary

- **Implemented:** faithful-source and contract metadata gates, read-only dataset/fee provenance checks, broad and index executables, dedicated tests, and bounded campaign wiring.
- **Not claimed:** true historical text vintages for today's captured posts, independent forward confirmation, measured spreads/fills/market impact, live order execution, or profitability.
- **Not automatically permitted:** Warden Stage 2–4, protected holdout use, contract/evaluator modification, and changes to scientific thresholds.
- **Intentionally deferred:** arbitrary author strategy code, unreviewed stop-loss/time-exits, open interest/level-2-based models, later-listed sparse crypto coins, and equities/FX without a reviewed matching executable rule.

A new Stage 1 pass remains a **candidate**, never a confirmed tradable edge. The selection ledger continues to account for multiple tests on the same exploratory period. All changes are confined to the research-loop repository and generated, ignored campaign outputs.
