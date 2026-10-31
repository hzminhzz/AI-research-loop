# MQL5 / MT5 source expansion — Batch 17 (2026-10-31)

**This batch reviews new source families and tests source-specific feasibility. It is not ten Warden hypotheses.** Ten distinct source mechanisms were audited; only one simple train-only lead/lag preflight was calculated, and it failed the prespecified direction. **0 new registrations, 0 native causal verifies, 0 native Stage1 screens, 0 Stage3 trials.** No source-screen budget was consumed. Existing Warden evidence and quarantines remain untouched.

## Why the earlier funnel produced so few useful candidates

There are **nine historical native Stage1 PASS receipts** in the prior ledger; that does not mean nine strategies qualified. The subsequent Stage2/3/holdout reconciliation found zero strategies that survive complete scientific qualification. New source batches repeatedly hit one of four problems:

1. Many retail sources provide a title or indicator, not a full entry/exit/position-sizing rule.
2. Many EAs depend on intrabar stop/TP, pending/limit orders, or hedging semantics not represented by the currently approved `NEXT_BAR` Warden contracts.
3. Author performance is selected from hundreds of parameter grids, short samples, or periods that overlap our validation/holdout.
4. Gross signals frequently fail after costs. Example: B16's new shock/volume reversal had gross active-bar bootstrap p=.01 but native net PF1.059 <1.15 and was frozen REJECT.

This is not a reason to relax Warden gates. It is a reason to source better mechanisms and stop registering incomplete variants.

## MQL5 / MT5 sources reviewed

| # | Source / mechanism | Original evidence and useful details | Decision |
|---:|---|---|---|
| 1 | [Low-Frequency Quantitative Strategies Part 2 — lead/lag and cointegration](https://www.mql5.com/en/articles/21811) | Cross-market price discovery; distinguishes mean-reversion for cointegrated pairs from momentum for non-cointegrated leader/follower pairs. Author example XAUUSD→GDX uses lagged prices, a spread/z-score and a 2-week optimized test; the article itself warns about pair/lag multiple testing and session alignment. | **EXPERIMENT, but not with publisher EA unchanged.** Its EA uses bar-index CopyClose arrays/current bar semantics instead of the exact timestamp join emphasized by the SQL analysis. Rebuild with closed bars, UTC timestamp joins, train-only pair classification, and native costs. |
| 2 | BTC→altcoin 1h lead/lag transfer | Fixed, non-optimized preflight on BTC leader and ETH/BNB/SOL/XRP/LTC followers, train-only 2023-01-01–2024-06-30. Contemporaneous correlations were positive, but the prespecified one-hour BTC-leads-altcoin return correlations were negative across all five followers. This does not support the proposed positive momentum-diffusion branch. | **BLOCKED at source-specific preflight.** No Warden registration/screen. Do not reverse the sign or flip leader after seeing results; that would be a new selected hypothesis. |
| 3 | Low-Frequency Quantitative Strategies Part 3 — regime-adaptive mean-reversion swing | 200-day hysteresis regime, Value Chart, DVO and SVAPO/volume confirmation; daily swing holding. Author reports a five-year study on six liquid Nasdaq stocks and says symbol selection, not parameter optimization, was the principal selection. This is much more interesting than another RSI/EMA crossover. | **TOP NEXT EXPERIMENT, blocked by contract/data.** Existing Warden `MULTI_ASSET_1D_V1` has only 17 FX/index/metals instruments and a 5-day label, not the US equity universe or longer holding horizon. Needs a verified US-equities daily OHLCV+real-volume contract, 20–60 day label/embargo, and explicit limit-fill proxy. |
| 4 | Low-Frequency Quantitative Strategies Part 4 — volatility-adjusted intraday momentum / ORB | Opening-range breakout with relative-volume and volatility filters; short holding period and multiple stock selection. | **IGNORE for now.** Same broad ORB family already heavily researched; adding another asset/window is not independent. |
| 5 | Low-Frequency Quantitative Strategies Part 5 — formulaic alphas | Cross-sectional alpha research and IC-first methodology. Its example Alpha #1 reports Rank IC≈0.0219 but t≈1.86 on 498 days, below the article's stronger multiple-testing significance guidance; reported decay after mid-2025. It warns against screening thousands of formulas without correction. | **ADOPT methodology; do not adopt weak example alpha.** Add IC/HAC, source-trial count and decay checks before costly backtests. |
| 6 | [First Fractal Breakout, DAX M5](https://www.mql5.com/en/articles/23575) | Confirmed 5-bar fractals, D1 ATR stop at 15% ATR, TP 10R, 1% risk, one trade per direction/session. Article reports 420 parameter configurations and 440 trades on its selected DAX sample; its later selected sample overlaps our protected period. | **BLOCKED before Warden.** Source session is 9h45 while current M5 contract label is 96 bars/8h; source expects hedging and permits one long plus one short per session, while Warden positions are netted. The 420-config author search must be disclosed and included in any later DSR. |
| 7 | [Inverse Fair Value Gap, Nasdaq M3](https://www.mql5.com/en/articles/16659) | 400-period MA filter, 3-candle FVG, rejection-wick filter, inverse break, fixed TP/SL, one position at a time. Source period 2020–2024; M3 is too short for the user's preferred frequency, so DAX M5 would be a cross-market/timeframe adaptation. | **BLOCKED / source red-team.** Pinned code computes bullish gap size with `abs(previousLow-currentHigh)` instead of `currentLow-previousHigh`; its mutable `LastGapIndex` can re-identify the same gap as the index shifts. Do not trust reported results until corrected and frozen. |
| 8 | [Weekend Gap Multi-Signal indicator](https://www.mql5.com/en/articles/22993) plus [gap-fill event study](https://www.mql5.com/en/articles/23609) | Gap ≥48h, retest/close back across gap boundary, target opposite boundary, stop at weekly extreme, gap validity up to 168h. Separate FX study reports 211 gaps and 78.7% fill rate, but it is an event-fill statistic, not strategy PnL, and its 2024-12–2026-07 sample overlaps part of our validation/holdout. A daily-index adaptation produced only **19 validation signals** under the fixed minimum-gap rule. | **BLOCKED sample / no screen.** Daily resolution is too sparse; M5 weekly horizon needs a new longer-horizon contract. Do not treat gap-fill probability as PF or executable edge. |
| 9 | MQL5 forum EUR/GBP RSI hedge / custom Spreader | Relative-strength hedge idea, but formula depends on an unpinned custom indicator; cited forum test is only 32 days and uses 5% risk without a defined stop. | **BLOCKED source fidelity and risk.** Could be reconsidered only with full indicator formula and proper FX relative-value contract. |
| 10 | MQL5 forum Big Ben / London range breakout and related carry/heatmap ideas | OCO range breakout posts omit exact range boundaries/exit semantics; carry requires historical swap; liquidity heatmaps estimate liquidation levels rather than observe actual liquidation prints. | **BLOCKED / IGNORE.** No Warden trial. Need exact range rules, PIT swap history, or actual liquidation/mark data. |

### What this changes

- Source discovery must include **MQL5 Articles, MQL5 Forum, MQL5 CodeBase, ForexFactory, TradingView source-code posts, QuantConnect/Lean, practitioner Substack/blogs, GitHub-pinned code, and X via mdfromx**. RSS is only one intake channel.
- Prefer **low-frequency** strategies: 5m/15m, 1h, daily swing, multi-day. Skip scalpers and sub-second execution ideas.
- Search economic mechanisms, not indicator names: information diffusion/lead-lag, relative-value convergence, carry/roll yield, volatility risk premium, session/holiday liquidity, market closure gaps, dealer inventory and actual aggressor-flow imbalance.
- Every MQL5 EA gets source-code red-team before testing: timestamp alignment, series indexing, bar 0 vs closed bar, indicator buffer shifts, duplicate signals, stop/target ordering, hedging/netting, pending-order semantics, session timezone and broker point-size assumptions.
- Pin original article HTML and source-code attachments by SHA256 or Git commit/blob before claiming source fidelity. If not pinned, keep it blocked before Warden registration.
- Record author-side optimization counts and sample/period. A selected backtest that overlaps our validation or protected holdout is not independent evidence.
- Never lower Stage1/Stage3 gates, reset the 20-screen lifetime cap, or retune/rebrand a rejected candidate.

## Next priority

**Build the missing daily US-equities data contract for the MQL5 Part 3 regime-adaptive swing candidate.** Verify the user's SPY/QQQ/NVDA (and any other available liquid US equity) canonical Parquet, actual volume quality, PIT history and exact hashes from `ml4t-data`. Propose (do not self-sign) a new Warden contract with daily bars, 20–60 day label/embargo, next-bar open proxy and conservative estimated costs. The MQL5 Part 3 rules then get transcribed and preregistered before validation. At Stage3, verify limit-order fills and slippage with 1m/tick data.

A second research branch is a clean timestamp-aligned **NQ→ES or other fixed index-pair lead/lag** test on the existing 1h index contract; the BTC→altcoin 1h lead hypothesis failed its train-only direction preflight and is closed without a Warden attempt.

## Warden / campaign state

- Warden at last authoritative read: **149 hypotheses / 72 full trials / 184 selection attempts**.
- Native source-family screens: **13/20**, at most **7 remain**; always re-read live count and exclusive writer lock before every screen.
- This Batch 17: **0 registrations, 0 causal verifies, 0 Stage1 screens, 0 Stage3 runs, 0 holdout reads, 0 orders**.
- B16 rejection stays frozen. No old candidate was retried, inverted or rebranded.
- Existing hourly research automations remain enabled; their source instructions are being expanded to cover MT5 forums and original code repositories.
