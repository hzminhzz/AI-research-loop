# Quant Thesis Factory — Batch 8 (2026-10-31 UTC)

**Result: 10 new, genuinely distinct primary-code-backed mechanism cards. ZERO native Warden Stage 1 screens.** All 10 were classified as preflight-blocked; these are **not** scientific rejections or failed alpha tests. No native registration, verify, Stage3, protected holdout or live order. Work performed directly through the connected VPS and primary public-source inspection, without coding agents.

All exact source URLs, immutable Git revisions and blob SHA1s, original entry/exit rules, venue, timeframe, sizing, costs, selection risks, PIT requirements, falsification and resolution steps are in [the machine-readable Batch 8 ledger](THESIS_FACTORY_20261031_BATCH8.json). Git blob pins certify the retrieved source bytes, not historical timestamp correctness or predictive profitability.

## New source-backed mechanisms

| ID | Original thesis mechanism | Source clock/instrument | Status and binding blocker |
|---|---|---|---|
| `B8-FW-FX-SESSION12` | London/NY prior-12-bar FX range breakout, hold 60min | EURUSD 5m | **BLOCKED_EXECUTION_DATA:** Warden QUOTE_SIDE FX5m missing bid/ask; source macro/kill-switch state also required |
| `B8-FW-FX-MAGAP6` | 50-bar z-score of MA gap mean-reversion, hold 30min | EURUSD 5m | **BLOCKED_EXECUTION_AND_PIT:** FX bid/ask absent, original feature/macro vintages unavailable |
| `B8-ZIN-BTC-RSI-TREND` | BTC RSI14<35 conditional on SMA200 uptrend, exit RSI>60 | BTCUSDT spot 1h | **BLOCKED_HORIZON_AND_VENUE:** unbounded RSI exit, source ~50h average vs Warden 24h; spot versus perp |
| `B8-ZIN-DOGE-DUALMA` | DOGE 24/168h MA directional momentum | DOGEUSDT spot 1h | **BLOCKED_HORIZON_AND_VENUE:** source ~111h average/unbounded hold, venue difference |
| `B8-PGUP-TURNAROUND-EMA` | Three-candle reversal inside EMA200 trend and 1% EMA20 pullback | Binance spot crypto 15m | **BLOCKED_HORIZON_AND_EXECUTION:** no approved original 15m contract, source exit mode / setup stop |
| `B8-PGUP-PERP-STATE` | Funding/flow/regime state machine sizes perp risk | Binance perps 4h | **BLOCKED_PIT_FUNDING_AND_COMPLEXITY:** 480-bar state, PIT crowding and R0–R9 selection controls |
| `B8-CDR-CFD-Z20` | 20-bar z-score CFD mean-reversion to midline | CFD 1m | **BLOCKED_EXECUTION_AND_HORIZON:** original dealer spread/quotes and unbounded exit |
| `B8-CDR-CFD-SESSION-ATR` | Session-open ATR-band first close breakout with Chandelier trail | Index CFD 15m | **BLOCKED_ORIGINAL_RULES_AND_EXECUTION:** session fill, trail and author parameter provenance |
| `B8-FT-CMCWINNER` | CCI+MFI+CMO triple oscillator exhaustion | Crypto spot 15m | **BLOCKED_15M_STOP_AND_VENUE:** native frequency and intrabar ROI/stop incompatible |
| `B8-FT-HLHB` | RSI50 and EMA5/10 synchronous cross filtered by ADX>25 | Crypto strategy 4h | **BLOCKED_LONG_HORIZON_AND_STOP:** ROI/trailing stops and original instrument unresolved |

**Author-metric correction:** ZinanSong's reported ~50h / ~111h "average holds" come from total dataset bars divided by the number of position changes, not durations of closed trades. We retain the source figures only as approximate author claims. The stronger contractual blocker is that the original RSI/MA exit is unbounded, regardless of these estimates.

For exact immutable citations see the `source_url`, `source_revision`, and `source_blob_sha1` fields for each card.

## Verified native Warden preflight, not an inferred data limitation

`uv run python scripts/preflight_thesis.py --contract FX_MAJORS_5M_V1 --hypothesis HYP-SOC-FREEWILLY-SB-20261031 --json` showed: 8 verified FX assets, dataset digest matching, full validation coverage, label 48 × 5m, **execution_mode=QUOTE_SIDE** and `execution_columns_ok=false`. Native error: `ExecutionDataError: QUOTE_SIDE contract FX_MAJORS_5M_V1 requires ['bid', 'ask']; a close-price fallback is not a valid execution basis`. Thus the available 5m OHLCV **cannot** legitimately support a net-executable FX Stage1 without resolving the quote source.

`uv run python scripts/preflight_thesis.py --contract AUTO_CRYPTO_PERPS_TOP100_1H_V1_H24_E24_F45_S20_V1 --hypothesis HYP-SOC-PGUP-TURNAROUND-20261031 --json` showed 100 verified Binance perpetual assets, 24 × 1h label, 6.5bps/side native costs, dataset digest match and execution columns **available**. The discovered sources still fail source-faithful original exit horizon / venue / stop or history gates; this is a **source-fit blocker, not a dataset outage**.

## Registry and budget

| Metric | Start | End |
|---|---:|---:|
| Native hypotheses | 147 | **147** |
| Full trials | 71 | **71** |
| Selection attempts | 182 | **182** |
| Native HYP-SOC Stage1 attempts | 11 | **11** |
| Effective campaign consumption | 11/20 | **11/20** |
| Remaining lifetime source screens | 9 | **9** |
| Archive actionable / deferred | 0/80 | **0/80** |

`uv run warden check-worktree`: PASS. Governance guard: `READY_FOR_DISTINCT_RESEARCH`. The existing dirty `quant-lab` checkout was preserved with no protected files or registry writes. No tests or code changes to `quant-lab` were attempted in this source-only batch.

## Next research frontier

1. For **FX 5m**, obtain verified historical bid/ask price-side data and a human-approved matching research contract. Do not relabel midpoint OHLCV as executable bid/ask.
2. For **crypto 1h**, find an original **Binance perpetual** strategy with complete, bounded <=24h closed-bar entry/exit and no intrabar-only orders, all author-searches disclosed. Only then preregister and run guarded native verify and Stage1.
3. Preserve Batch1–8 source/rule dedupe, failed Warden experiments and all source-selection penalties. Continue read-only research after campaign cap; never auto-enlarge the 80-source archive cap, protected label horizon or 20-screen limit.

**Scientific conclusion:** no new Stage1 statistical evidence, and no trade authorization. Research continues on the existing hourly schedule.
