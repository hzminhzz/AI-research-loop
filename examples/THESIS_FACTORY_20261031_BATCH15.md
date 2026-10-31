# Quant Thesis Factory — Batch 15 (2026-10-31 UTC)

**Outcome:** 10 distinct primary-source code/economic mechanism cards from **three original publishers**. **0 native Warden registrations, causal verifies, Stage-1 screens, PASS, REJECT or Stage-3 trials.** All ten are BLOCKED *before scientific evaluation*. This is neither 10 failed alpha tests nor a reason to relax Warden rules. No holdout access or orders.

The complete machine-readable per-thesis evidence, original code URLs, immutable Git blob SHA1s, real captured Stratmill HTML digest, economic counterparties, exact original source signal vs proposed adaptation, original/pending time zone, lag/cost/sizing/holding/label details, PIT controls, source-side selection, baselines, falsification and next actions are in [Batch 15 JSON](THESIS_FACTORY_20261031_BATCH15.json). Source code is **untrusted evidence and was never executed**.

## Source-backed mechanism ledger

| ID | Original mechanism and market | Pinned primary source | Preflight status |
|---|---|---|---|
| `TH-20261031-B15-STRATMILL-BNB-BO` | Binance BNBUSDT USDT-M 1h 72-bar breakout confirmed by volume/CLV, 24h fixed hold | [Stratmill 24h BNB breakout](https://stratmill.com/research/en/strategies/254c86bd-eaa6-43e5-a4ad-02f2984d5f0b) | **BLOCKED_PUBLISHED_NEGATIVE_ECONOMICS_AND_SELECTION** |
| `TH-20261031-B15-CS-TSMOM-7D` | Hyperliquid 4h 7d directional trend with vol sizing | [CShear TSMOM](https://github.com/CShear/crack-the-nut/blob/72f293c19a61e01507f322595e3982da00f0932d/analog/strategies.py#L35-L63) | **BLOCKED_ORIGINAL_EXIT_AND_AUTHOR_SEARCH** |
| `TH-20261031-B15-CS-BB-RSI-TAIL` | Hyperliquid 4h Bollinger + RSI reversal | [CShear BB+RSI](https://github.com/CShear/crack-the-nut/blob/72f293c19a61e01507f322595e3982da00f0932d/analog/strategies.py#L409-L446) | **BLOCKED_EXIT_TIMEFRAME_AND_SELECTION** |
| `TH-20261031-B15-CS-BTCETH-RATIO` | Hyperliquid 4h BTC/ETH relative-price reversion, BTC-only signal | [CShear BTC/ETH ratio](https://github.com/CShear/crack-the-nut/blob/72f293c19a61e01507f322595e3982da00f0932d/analog/strategies.py#L485-L532) | **BLOCKED_MISSING_HEDGE_AND_EXIT** |
| `TH-20261031-B15-CS-BB-KELT-SQUEEZE` | Hyperliquid 4h BB inside Keltner → release direction | [CShear squeeze](https://github.com/CShear/crack-the-nut/blob/72f293c19a61e01507f322595e3982da00f0932d/analog/strategies.py#L577-L625) | **BLOCKED_UNFROZEN_EXIT_AND_CROSS_VENUE** |
| `TH-20261031-B15-CS-KAMA-ER-TREND` | Hyperliquid 4h Kaufman ER20 responsive trend | [CShear KAMA](https://github.com/CShear/crack-the-nut/blob/72f293c19a61e01507f322595e3982da00f0932d/analog/strategies.py#L704-L752) | **BLOCKED_UNFROZEN_EXIT_AND_AUTHOR_SELECTION** |
| `TH-20261031-B15-CS-SETTLEMENT-UNWIND` | Hyperliquid funding payer unwind 2–4h before settlement | [CShear settlement](https://github.com/CShear/crack-the-nut/blob/72f293c19a61e01507f322595e3982da00f0932d/analog/strategies.py#L953-L994) | **BLOCKED_PIT_SETTLEMENT_AND_PNL_ACCOUNTING** |
| `TH-20261031-B15-GTD-FUND-EMA-FLOW` | Binance 15m funding extreme + lagged EMA50 + taker buyer flow | [Gotodataru funding rules](https://github.com/Gotodataru/binance-futures-backtest/blob/5ed0d6e39d8a3e951bea40c66e2638c213012e1b/strategy_1_funding_mr/signals.py) | **BLOCKED_NO_TAKER_FLOW_AND_15M_CONTRACT** |
| `TH-20261031-B15-GTD-TAKER-PRESSURE` | Binance 5m persistent aggressive taker ratio + ATR continuation | [Gotodataru taker rules](https://github.com/Gotodataru/binance-futures-backtest/blob/5ed0d6e39d8a3e951bea40c66e2638c213012e1b/strategy_2_taker_momentum/signals.py) | **BLOCKED_MISSING_FLOW_OOS_SELECTION_AND_STOP_FIDELITY** |
| `TH-20261031-B15-GTD-OI-DIVERGENCE` | Binance 15m OI/price open-vs-close regime with taker flow | [Gotodataru OI rules](https://github.com/Gotodataru/binance-futures-backtest/blob/5ed0d6e39d8a3e951bea40c66e2638c213012e1b/strategy_3_oi_divergence/signals.py) | **BLOCKED_NO_PIT_OI_TAKER_AND_15M_CONTRACT** |

**Novelty constraint:** 6 CShear cards represent different defined signals but *one* shared 2026-04-03 Git blob (`2db11b6b32cd24909b8c3f76baa5c8a503a3be4b`) and the same author-side selection family. They are **not** six independent source studies. All six return `forward_return(ts,fwd_hours)`, where **the caller selects the outcome horizon**, rather than emitting complete entry/exit orders; no source-faithful native screen is authorized. Proposed 4h/8h exits in JSON are marked **new adaptations**, not source defaults. Hyperliquid source-to-Binance transfer changes market, fill and cost semantics.

## Two actionable evidence findings

**1. Source BNB breakout already rejected by its own publisher.** Stratmill's exact current HTML captured read-only on the VPS on 2026-10-31 at 06:59:08 UTC has SHA256 `6e58af4d1af3e4c92d8fd24078c3f732722b8ec873359e995d7138ab0c3874ab`. Original BNB 1h logic has fixed prior72 high / current CLV>0.70 / volume>1.5× prior168 median, enter next open, exit24h. Author reports **270 selection trials**, PF1.139, Sharpe0.540, max drawdown47.114%, 3/7 profitable years and an **ABANDON** outcome. Native preflight confirms BNBUSDT in the pinned 100-asset hourly USD-M panel (21,888 exploratory bars; 2023-01-01 to 2025-06-30, data hash verified), but it would be scientifically dishonest to treat the publisher's unsuccessful search as a new untouched alpha. **Not registered or screened.** Research contract costs remain 6.5bps per side and funding, not publisher's reported costs.

**2. A publisher selected on its reported out-of-sample Sharpe.** The [original Gotodataru taker momentum backtest](https://github.com/Gotodataru/binance-futures-backtest/blob/5ed0d6e39d8a3e951bea40c66e2638c213012e1b/strategy_2_taker_momentum/backtest.py#L72-L90) explicitly loops over stop/target pairs then retains the pair with the **highest measured OOS Sharpe**. The source's own declared full grid has **108 valid combinations** (36 signal/holding ×3 allowed bracket pairs). The presented best OOS result is therefore *post-selected* and must not be counted as an independent holdout. Warden's native 5m crypto panel also lacks taker-buy share and source stop/target ordering requires intrabar execution evidence. **Not registered or screened.**

Other Binance source obstacles: approved crypto panels have `timestamp,asset,open,high,low,close,volume,funding_rate` but **no `buy_ratio`, `open_interest`, `taker_ls_vol_ratio`**. The 15m crypto contract is unavailable. None of these features may be synthesized from simple OHLCV and then claimed as source reproduction.

## FX midpoint allowance: still gated by source integrity

The principal has approved *research* using open-price proxy, NEXT_BAR with **3bps per side** estimated costs, but `FX_MAJORS_5M_MID_V1` is only a draft: no Warden protected-contract activation/manifest signature. Existing `FX_MAJORS_5M_V1` stays QUOTE_SIDE. Verified source-data anomalies include USDCAD 2024-12-22 +30.7% open gap, AUDUSD 2022-10-09 +16.9%, GBPUSD 2022-10-04 +9.55%. Some gaps can be real; each must be compared to independent market prints before clearing, not deleted because of poor PnL. No FX native screen.

## Registry and governance, unchanged

| Metric | Before | After |
|---|---:|---:|
| Native hypotheses | 148 | **148** |
| Warden full trials | 71 | **71** |
| Selection attempts | 183 | **183** |
| Native source-backed Stage1 screens | 12 | **12** |
| Effective source screening budget | 12/20 | **12/20 (at most 8 remaining)** |
| New registrations/causal verifies/Stage1/PASS/REJECT/Stage3 | 0 | **0** |

Governance check `READY_FOR_DISTINCT_RESEARCH`, `uv run warden check-worktree` PASS. Quarantines, rejected candidates and 428 unrelated dirty/untracked quant-lab entries preserved. Approved 80-source archive: 0 actionable, 80 deferred, 120 review events. RSS had 0 unseen eligible posts. No holdout reads, protected file edits, broker orders, or Warden registry mutation.

## Queue cursor and next step

1. **Preserve source negative evidence**: never retry Stratmill's already-abandoned variant as fresh OOS or call Gotodataru's best-OOS stop parameter independent validation. Every source search is accounted for.
2. Investigate *new* truly complete Binance USD-M 1h original strategies with an explicitly bounded <=24h exit, causal next-open fills and economically adequate gross edge; avoid recycled B1–B14 mechanisms. Six CShear evaluator variants are retained as blocked research, not 6 candidate trials.
3. Run an independent FX5m data-quality/provider reconciliation and activate a separate human-governed next-bar midpoint contract only when source-specific data are sound. Keep original quote contract immutable.
4. Next hourly invocation must read **Batch15 JSON and this report**, prior B1–B14, live registry, archive and shared writer state; never reset source cursor or lifetime 20-screen cap.

**Scientific conclusion:** No new Stage1 performance evidence. Research remains ongoing; no alpha or trading authorization.
