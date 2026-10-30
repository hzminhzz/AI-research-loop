# Quant Thesis Factory — 2026-10-31 Batch 4 (distinct-source preflight)

**Outcome: 10 distinct mechanism/source cards persisted, ZERO Warden registrations, ZERO causal verifications, ZERO native Stage 1 screens, ZERO scientific PASS/REJECT.** The 10 cards are blocked before registration; each is a falsifiable research direction, but NOT yet a complete source-faithful trading experiment. Do not report them as validated strategies or source-equivalent replications. The authoritative detail, original URLs, content hashes, rule gaps, counterparties, sizing, PIT/cost/horizon, comparators and next actions are in [Batch 4 JSON](THESIS_FACTORY_20261031_BATCH4.json).

## Live guard and screening budget (VPS checked)

- Warden `uv run warden check-worktree`: PASS. Governance `READY_FOR_DISTINCT_RESEARCH`. Registry 145 hypotheses / 71 full trials / 180 selection attempts, unchanged by this source-only batch.
- Shared lifetime count via `native_source_screen_count` vs campaign counter: native **9**, private **3**, effective **9/20**. At most **11** source-family screens remain, recheck live before each future write.
- Source timer and archive timer remain active. The 80-source approved shortlist is fully deferred after **107** review events: 0 actionable, 80 deferred. An attempted read-only discovery `--target 120` returned `ValueError: Shortlist target outside 1..80`; it did not refill or alter the archive. Do not silently raise this bound.
- Batches 1, 2, 3 were read before selection; 3 prior B1 attempts and 2 B2 attempts remain frozen. Their source/signal/contract families must not be recycled under different IDs. The old HYP-2026-128 quarantine remains intact.

## Source-backed thesis cards, not executed trials

| ID | Mechanism | Source / instrument | Outcome & required unblock |
| --- | --- | --- | --- |
| `TH-20261031-B4-X-ONEBAR-50` | 50-bar extreme, one-bar continuation | [Original X NQ post](https://x.com/onlybreakouts/status/2116230180008067336), futures 30m | **BLOCKED_EXECUTION**: intrabar stop entries and $1,000 futures stop not reproducible under CFD NEXT_BAR. |
| `TH-20261031-B4-X-CCI-CORRECTION` | Post-washout breakout conditioning | [Original X CCI filter](https://x.com/onlybreakouts/status/2114454472248230234), NQ | **BLOCKED_AUTHOR_RULES**: base breakout and exit absent; 16.5 million source-side filter tests. |
| `TH-20261031-B4-X-FAILED-BREAK` | Liquidity sweep and discounted retracement | [Original X liquidity note](https://x.com/RealMktEdge/status/2116039932456157221), market unspecified | **BLOCKED_AUTHOR_RULES**: no numeric sweep/entry/exit; proposed crypto application is a NEW conjecture. |
| `TH-20261031-B4-X-ORB-ACCEPT` | Post-open range acceptance vs snapback | [Original X opening-range note](https://x.com/HesssamK/status/2115844076671062264), NQ | **BLOCKED_AUTHOR_RULES**: qualitative observation only, no complete exit; related ORB lineage must be accounted for. |
| `TH-20261031-B4-FT-ADX-DI` | ADX/DI directional continuation | [Pinned Freqtrade ADXMomentum code](https://github.com/freqtrade/freqtrade-strategies/blob/f3340ce11f5bdf62f598522e64d1f5638eaa13f5/user_data/strategies/berlinguyinca/ADXMomentum.py), crypto 1h spot | **BLOCKED_EXECUTION**: Freqtrade +1% ROI/-25% stop and potentially unbounded exit vs native four-hour label. |
| `TH-20261031-B4-FT-SWING-CCI-RSI` | Oscillator oversold swing reversal | [Pinned Freqtrade SwingHighToSky code](https://github.com/freqtrade/freqtrade-strategies/blob/f3340ce11f5bdf62f598522e64d1f5638eaa13f5/user_data/strategies/SwingHighToSky.py), crypto spot 15m | **BLOCKED_DATA_AND_EXECUTION**: no 15m contract; multi-tier intrabar ROI and stoploss not native. |
| `TH-20261031-B4-FT-TRENDRIDER` | Trend pullback/re-entry ensemble | [Pinned Freqtrade TrendRider code](https://github.com/freqtrade/freqtrade-strategies/blob/f3340ce11f5bdf62f598522e64d1f5638eaa13f5/user_data/strategies/TrendRiderStrategy.py), crypto 1h | **BLOCKED_EXECUTION**: trailing stop, hyperoptimized ROI/entry choices, and 4h label mismatch. |
| `TH-20261031-B4-PEDMA-BINARY-ALLOC` | Binary signal expiry and top-k exposure loss | [Original pedma article](https://www.tradingresearchub.com/p/binary-signal-efficiency-when-scalable), crypto overlay | **BLOCKED_PROTOCOL**: allocator correctness question, not directional alpha; missing frozen base and native meta-overlay test. |
| `TH-20261031-B4-PEDMA-CARRY5` | Five-day funding persistence and beta-neutral price movement | [Original pedma carry part 3](https://www.tradingresearchub.com/p/dirty-crypto-carry-part-3-the-moneys), BTC/DOGE example | **BLOCKED_DATA_AND_HORIZON**: 120h forecast vs 4h or 24h approved 1h labels; need funding vintage and exact source entry/exit. Prior 7d funding rejection must not be reused. |
| `TH-20261031-B4-DELPHI-TREND-ATLAS` | Fold-local ML trend forecasts conditional on volatility | [Original Delphi Alpha model study](https://delphicalpha.substack.com/p/the-trend-atlas-a-recipe-for-ml-trend), cross-asset | **BLOCKED_AUTHOR_RULES_AND_SELECTION**: missing class-specific settings; published 2023–26 holdout is already public, not virgin confirmatory evidence. |

## Critical protocol distinction

The X posts and Freqtrade code include some numeric rules but are not necessarily executable with the approved contract. Freqtrade ROI, trailing-stop, and stoploss behavior requires trade-path/high-low execution; substituting next-bar signal exits creates a **new adaptation** that must be approved and frozen in advance. Source-specific selection searches must be counted, especially the 16.5 million-filter CCI claim and hyperoptimized Freqtrade configurations.

Approved contract inspection: `CRYPTO_PERPS_1H_V2` has a **4-bar** label, native 1-bar delay, and 4bps taker + 2bps slippage per side; `CRYPTO_PERPS_5M_V1` has a **48-bar** label (4h); `INDICES_30M_V1` has a 16-bar label and 0.5bps fee + 0.5bps slippage per side. These do **not** authorize fills for intrabar stop orders or five-day funding signals. The three source-only code examples were never imported/executed.

## Continuation queue

1. Prioritize a newly published or pinned **fully specified, short-horizon crypto-perpetual 1h / FX 5m rule** with explicit exit and original source timestamp. Do not claim a title/snippet/qualitative indicator is a Warden-ready hypothesis.
2. For source-specific stop/ROI strategies, first establish a compatible human-approved contract and execution engine, retaining the author's original instrument/timing. For funding carry, require complete 8h settlement history and at least 120h approved label.
3. Once a DISTINCT candidate clears source and contract preflight, use the shared native governance/durable-job writer, verify causality, then screen exactly once. Refresh the `max(native_source_screen_count, private_counter)` cap before each screen. A PASS is preliminary, not trading authorization.
4. The archive cap is 80; expanding beyond 80 would be a separate reviewed code/operational change. Until then mine new original source families outside the 80 or investigate blockers read-only.

**No Stage 3, holdout read, live order or Warden ledger mutation occurred.** This is a durable checkpoint; research continues on the existing hourly schedule.
