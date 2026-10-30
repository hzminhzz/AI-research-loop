# Quant Thesis Factory — Batch 7 (2026-10-31 local, VPS 2026-10-30 23:40 UTC)

**Execution:** ChatGPT directly operated @VPS-cloudflare. Ten *distinct mechanisms* reviewed from current original public publisher pages or pinned source repositories. Exactly **one** was formally registered, causality-verified and screened by native Warden; it was **REJECTED**. The other **nine are blocked before scientific evaluation**, not nine Warden failures. No Stage3, protected holdout, live order or external coding agent.

[Complete machine ledger (all exact source URLs, SHA256s, rules, costs, clocks, risk, baselines and blockers)](THESIS_FACTORY_20261031_BATCH7.json). All captured publisher material is **untrusted**. Current response/body SHA256 or commit-pinned source is **not** proof of historical text availability; publisher's reported backtests are not independent OOS evidence.

## Verified native Stage1

| Hypothesis / research adaptation | Causal verify | PF | Bootstrap p | Time in market | Gross trade edge | Avg holding | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| `HYP-SOC-TV-BTC-2123-20261031`: Binance BTCUSDT USD-M perp, long 21:00–23:00 UTC | **PASS**, 21,888 rows | **0.825984** | **0.065** | **8.333%** | **5.304bps** | **2 × 1h** | **REJECT** |

[Original EdgeTools TradingView publication](https://www.tradingview.com/script/IzFZxayj/) is dated 2024-10-30, default buy 21:00 UTC / exit 23:00 UTC. Live original HTML capture SHA256 `a4d4ee62841aaad48207547cd7e7a39ab14130197e4943f9a6bf75017eac0c0f`. Publisher's BTC venue is unspecified. This **is not a replication**: explicit transfer to Binance USD-M perpetual, approved contract `AUTO_CRYPTO_PERPS_TOP100_1H_V1_H24_E24_F45_S20_V1`, 1h NEXT_BAR, 6.5bps/side fee+slippage plus funding. Stage1 uses this contract's frozen validation split and does not read the protected holdout.

Profit factor <1.15, bootstrap p >=0.05 and 5.304bp trade edge <9.75bp 1.5× one-way-cost hurdle. Time in market >=5% is the only listed rule gate that passes. Do **not** tune/invert/retry. Selection/window lookback multiplicity is uncertain and prior B6 BTC overnight MAX(10) is related historical source selection.

- Native Warden verify job: `warden-verify-56018173e949e488d3` → structured `status=PASS`, prefix invariant, 21,888 source rows, verified-market data.
- Native Warden Stage1 job: `warden-screen-73ef2384c8a9be8056` → structured `passed=false` (process rc=1 is expected negative verdict).
- Immutable selection attempt: `ATT-5657f0c12d4653af-001` (`STAGE_1_SIGNAL`) confirmed via SQLite read-only.
- Native source local artifacts: `quant-lab/.workspace/hypotheses/HYP-SOC-TV-BTC-2123-20261031[_RESULT].md`; `experiments/active/tv_btc_2123_20261031.yaml`; `strategies/candidates/tv_btc_2123_20261031.py`. Synthetic-only unit tests: **3 passed**; focused Ruff PASS; native worktree integrity PASS. These are local in dirty `quant-lab`, not represented by committing this evidence repo.

## Independent source/mechanism inventory

**BLOCKED means not registered, not verified, and not screened.** See the JSON ledger for actual source snapshots, primary SHA values, original signal/exit, proposed venue, sizes, session clock, cost model, baselines and falsification.

| ID | Mechanism | Original source | Scientific status / prerequisite |
|---|---|---|---|
| `HYP-SOC-TV-BTC-2123-20261031` | BTC 21–23 UTC seasonal drift | [EdgeTools](https://www.tradingview.com/script/IzFZxayj/) | **Stage1 REJECT**, PF0.826; frozen |
| `TH-20261031-B7-FRANK-EMA2050` | 1h EMA(20/50) directional persistence, 12h hold | [Pinned FrankRKNL code](https://github.com/FrankRKNL/crypto-intraday-trader/blob/adc680e8ea3dc3143beef74d3152da4a8b4ac2f0/test-long.mjs) | **BLOCKED_SOURCE_LEAKAGE**, up to 49h lookahead |
| `TH-20261031-B7-TV-GRENEAGLE` | US BTC bullish bias following ATR compression | [TheSocialCryptoClub](https://www.tradingview.com/script/97ou6vBe-Hourly-Bias-on-BTC-in-Bullish-USA-Session-Green-Eagle/) | BLOCKED exact weekday/ATR/source timezone |
| `TH-20261031-B7-TV-EXLUX-WEEKDAY` | BTC Tuesday/Thursday timed drift + rising ATR | [exlux](https://www.tradingview.com/script/qQlE2in7-Time-Based-Crypto-DayTrade-Strategy/) | BLOCKED exact ATR filter/clock/author search |
| `TH-20261031-B7-FX-BBRSSI-M5` | EURUSD M5 BB(20/1.75) + RSI7 band-tail reversion | [sbrakni MQL5](https://github.com/sbrakni/mean-reversion-mql5/blob/c263c854dc6a26320c7001a4622c6cd25bdae90d/README.md) | BLOCKED intrabar stop and TP; 204 source search cells |
| `TH-20261031-B7-FX-WPR-EMA-M15` | EURUSD M15 band re-entry + Williams%R + EMA | [rishikabirverma EA](https://github.com/rishikabirverma/eurusd-mean-reversion-ea/blob/5491a9612520d618c6b4304801da0e6597d5a9ee/README.md) | BLOCKED M15 contract/quote-side/stop |
| `TH-20261031-B7-BTC-FUND-RSI5M` | Perpetual funding z-score and RSI extremes | [jiangkaili Binance bot](https://github.com/jiangkaili/binance-trader-bot/blob/39f7187ce21b021441fb4a55188b95831df7b5b1/README.md) | BLOCKED funding PIT + exchange stop/TP |
| `TH-20261031-B7-BTC-TOUCH-ML` | Barrier-touch likelihood and first-hit direction | [quocnv BTC pipeline](https://github.com/quocnv20214926/BTC_PIPELINE/blob/56e84e28c335b42539aa6624390834700878ac13/README.md) | BLOCKED missing PIT features, 5m exits, 30d horizon |
| `TH-20261031-B7-BTC-EXIT-HAZARD` | Time-dependent profit-target decay overlay | [ZeroJSL000](https://github.com/ZeroJSL000/time-dependent-trade-exits/blob/e648c2c9425e2cc642403c0bcb6213cd1784479d/README.md) | BLOCKED base strategy/overlay protocol |
| `TH-20261031-B7-BTC-PULLBACK-15M` | BTC 15m trend pullback into short EMA with 50/200h regime | [RipBacktest](https://ripbacktest.com/posts/intraday-trend-pullback-bitcoin/) | BLOCKED M15 native contract/intrabar risk exits; author already negative |

### High-severity source-level causal flaw

The [pinned FrankRKNL 1h EMA implementation](https://github.com/FrankRKNL/crypto-intraday-trader/blob/adc680e8ea3dc3143beef74d3152da4a8b4ac2f0/test-long.mjs) initializes the EMA array with the *first period's mean*, then indexes that shortened array at raw candle `i`. Therefore `ema50[i]` implicitly requires candle **i+49** and `ema20[i]` requires **i+19**. The source's signal at candle `i` reads future prices up to 49 hours ahead. It also fills at the very candle close used for the signal; its report describes an opposite-crossover exit that the pinned fixed-hold code does not implement. The source's reported profitability is **not causally valid** as written. Source code SHA256 `d61ae19917b1e70d1f6e4c4ec65d8c2232c03e399e27b40389d625a95f79248b`. No source-code execution or Warden screen was conducted for this flawed code.

### Warden budget and continuation

| State | Before | After |
|---|---:|---:|
| Native registered hypotheses | 146 | **147** |
| Full Stage3 trials | 71 | **71** |
| All selection attempts | 181 | **182** |
| Source-family Stage1 consumed | 10/20 | **11/20** |
| Remaining budget | 10 | **9** |

Campaign private source counter=3; authoritative Warden native HYP-SOC Stage1 count=11. Source archive remains 80/80 deferred with 107 review events and **0 active leads**. No source-cap expansion, protected contract/gate edits, Stage3, holdout or live trading. Prior quarantines and B1–B6 outcomes preserved.

**Next:** Favor a fully source-pinned, exact short-horizon 1h Binance-perpetual or FX M5 strategy that requires neither intrabar stops/ROI, unknown publisher inputs nor unapproved label contracts. Continue public-source inspection even if screening is blocked. If any candidate is viable, re-read native count and guard **immediately** before its single Warden registration/verify/screen. A preliminary Stage1 PASS, including the old ES down-day, is not qualified alpha.
