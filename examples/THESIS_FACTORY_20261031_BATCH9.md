# Quant Thesis Factory — Batch 9 | October 31, 2026 UTC

**State: batch checkpoint, recurring research continues.** This is an executed research batch, not an assertion of trading profitability or protected holdout qualification.

## Summary (native evidence only)

| Measure | Before | After / new batch |
| --- | ---: | ---: |
| Source-derived distinct mechanism cards | — | **10** |
| Native Warden registered | — | **1** |
| Native causal verify PASS | — | **1** (21,888 BTC 1h rows) |
| Native Stage 1 screens | — | **1** |
| Native Stage 1 PASS / REJECT | — | **0 / 1** |
| Source cards BLOCKED BEFORE screen | — | **9** |
| Registered hypotheses | 147 | **148** |
| Full Warden trials | 71 | **71** |
| Warden selection attempts | 182 | **183** |
| Native HYP-SOC Stage1 attempts | 11 | **12** |
| Conservative campaign lifetime screen budget | 11/20 | **12/20, <=8 remain** |
| Archive leads actionable / deferred | 0 / 80 | **0 / 80** |

Warden governance `READY_FOR_DISTINCT_RESEARCH`, protected worktree verification PASS, no protected registry/core edits, no holdout access or orders. All previous Batch1–8 results remain frozen. This batch's ten records are in `examples/THESIS_FACTORY_20261031_BATCH9.json`; each contains original commit-pinned source URL, first-party Git blob SHA1, instrument/timeframe, economic rationale, entry and exit, sizing, costs, PIT assumptions, baseline, source-side multiplicity, prerequisite and next action.

## Native screened candidate: H018 Stochastic K mean-reversion

**Native verdict: REJECT.** The primary-source H018 authored 2026-05-24 is already negative on Bybit BTCUSDT perp 1h (mean OOS Sharpe -0.12 over 45 CPCV paths). This is a controlled **Binance USD-M venue transfer**, not prospective independent alpha.

- **Original:** [H018.md](https://github.com/SeifBoukerdenna/hl/blob/88151f9f9845f20636b43fd3f70d133243d60382/docs/hypotheses/H018.md), pinned blob `622bc86b73f5e97ec6c4db018a867ab0e51242da`. Long when prior K14<20 and current K14>=20. Exit K>80 or 24 hourly bars. 50%-equity target.
- **Frozen Warden adaptation:** same K14 / 20 / 80 / 24-bar rules, BTCUSDT Binance USD-M 1h instead of Bybit, NEXT_BAR fills one bar after completed candle, no stop, 4.5bps taker +2.0bps slippage per side plus source-available funding. Validation calendar overlaps author's work; no OOS claim.
- **Paths:** `/home/quant/dev/quant-lab/.workspace/hypotheses/HYP-SOC-HL-STOCHK-BTC-20261031.md`, `strategies/candidates/soc_hl_stochk_btc_1h_20261031.py`, `experiments/active/soc_hl_stochk_btc_1h_20261031.yaml`, `.workspace/hypotheses/HYP-SOC-HL-STOCHK-BTC-20261031_RESULT.md`.
- **Native verify:** PASS, prefix-invariant, verified-market 21,888 rows; durable unit `warden-verify-f506fae96cfb901b9c`.
- **Native Stage1 screen:** `ATT-5d71f73e9c96ca2f-001`, durable unit `warden-screen-8dd5ab878f62536618`, scientifically **REJECT**. Exit code 1 is Warden's normal rejection, not a failed executable run.

| Warden metric | Value | Gate |
| --- | ---: | --- |
| Profit factor | **0.987509** | >=1.15 **FAIL** |
| Block-bootstrap p-value | **0.135** | <0.05 **FAIL** |
| Time in market | 38.607% | >=5% PASS |
| Conditional gross edge / active bar | 0.409bps | informational |
| Derived trade edge | 10.868bps | >9.75bps PASS |
| Warden turnover-derived avg hold | **26.578 hourly bars** | **not realized duration** |
| Native Stage1 | **REJECT** | immutable |

The `avg_holding_bars` value **is not a realized position-holding duration**. Current protected Warden Stage1 estimates it as `2*n_active / sum(abs(diff(position)))`; with the source's 0.5 target it is scale-sensitive and can exceed a 24-bar hard position state cap. This is a methodological caveat in the native report, not evidence the source rules had a >24-bar stop. Do not adjust the evaluator, the source strategy, or re-screen to repair the cosmetic estimator. This is one frozen negative trial.

## Nine additional independently sourced mechanisms — blocked before Warden

| Card | Original source | Mechanism / exact rule nucleus | Blocker (not scientific REJECT) |
| --- | --- | --- | --- |
| B9-FOLG-EMA20-TIMED | [folg-code BTC futures dry-run](https://github.com/folg-code/research-trading-framework/blob/d05b7291a9d32bb247d4dd55d34a6a63de6b51d5/src/trading_framework/strategy/btc_futures_demo.py) | BTCUSDT USD-M long on close>EMA20 **true-edge**, 10 closed bars, fixed 0.001 BTC; unvalidated demonstration | Source operates **1m**, Warden authorized crypto panel **1h**; 10m to 10h is a 60x holding change. |
| B9-PANJ-BTC-FLAG | [pa-pattern-quant BTCUSDT 1h flag detector](https://github.com/panjinhe/pa-pattern-quant/blob/43c24fcb735ac186ffa8f9585a9fc3c6e91a84dd/%E4%BA%A7%E5%87%BA/TechnicalAnalysisAutomation%20%E6%97%97%E5%BD%A2%E6%97%97%E5%B9%A1%20BTCUSDT%201h/detect_flags_pennants.py) | Causally delayed pole and flag trendline break, fixed hold = flag width. | No proven maximum <=24h, source same-confirmation-close fills and overlapping trades. Source reported PF1.134 (not a Warden result). |
| B9-SEIF-HILBERT-128 | [Seif H026](https://github.com/SeifBoukerdenna/hl/blob/88151f9f9845f20636b43fd3f70d133243d60382/docs/hypotheses/H026.md) | Detrended 128-bar Hilbert phase crossing: enter 0, exit pi/2 or 48h. | Native label 24h vs source max48h; source's own prior reports Sharpe -2.14, DD -58.24%. |
| B9-CHEN-RSI-EMA-HYBRID | [chencore source `train_quant.py`](https://github.com/chencore/autoresearch-crypto/blob/ec86e44a6f0b4063e79f33253e00fefb4249ec88/train_quant.py) | 5m RSI14 <25 oversold within EMA20>EMA40 trend, ATR trailing/EMA reverse, 24x5m cap. | No approved matching 5m crypto execution/venue contract, intrabar stops. |
| B9-ELVIS-USD-M-BREAKDOWN | [ElvisTV BTCUSDT short scalper](https://github.com/ElvisTV/backtestingbots_s1/blob/043c8c499bd47b33ca0d0fd2eb021fe992a2cfa4/btcusdt_usdm_scalping_backtester.py) | 5m/1m BTCUSDT short EMA21<55<200, ADX>=16, prior-low breakdown, 18-bar cap with 1.2ATR stop and 1.45ATR TP. | Original intrabar stop/TP/trail/breakeven not reproducible by Warden hourly NEXT_BAR. |
| B9-WEDGE-BASIS-Z | [BTCUSDT USDT-M basis mean-reversion decision](https://github.com/toobigtofailbot-maker/crypto-perp-wedge/blob/1731d6bd75f403d5a40c4cc9c9ff7eb4cc0e3602/research/decisions/DEC-0010.md) | 90x4h basis z-score +/-2 with premium consistency, exit abs(z)<0.5 or 18x4h bars. | Needs PIT mark/index/premium and 72h horizon; source itself NO-GO (DD84.97%, broken IS/OOS split). |
| B9-MAID-SHADOW-SHORT | [trading-maid shadow example](https://github.com/86maid/trading-maid/blob/93967a423630875c9829b8e719521960259c25f0/examples/simple.rs) | Hourly BTC short bearish upper wick >=2x body and body >=$300; bracket TP/SL by wick size. | Uses 1m intrabar matching and **unbounded** time until brackets fill. |
| B9-MAID-DONCHIAN-VOL | [trading-maid volume breakout](https://github.com/86maid/trading-maid/blob/93967a423630875c9829b8e719521960259c25f0/examples/volume_breakout.rs) | BTC 4h Donchian20 includes **current** high/low, volume >1.3x, 20-RMA trend; bracket TP4ATR/SL0.5ATR. | 4h timeframe, intrabar OCO/stop and missing bounded holding; do not rewrite as prior-only Donchian breakout. |
| B9-MNEMOX-SESSION-DRAIN | [mnemox Strategy C primary code](https://github.com/mnemox-ai/tradememory-protocol/blob/cb599bd3614560435670a7afaee44d1bb62ec507/scripts/research/run_real_baseline.py) | Binance BTC 1h short at 16:00 UTC if prior 12h trend negative; ATR1 stop, ATR2 TP, max6 bars. | Intrabar ATR brackets; source feed spot/perp not proven; author's script compared against 1,000 random strategy draws. |

These are nine **preflight-blocked research cards**, not nine native Warden rejections. All original Git blob pins, research-specific costs, source-vs-adaptation provenance, baselines, falsification tests, and suggested next actions are saved in Batch9 JSON.

## Additional public X intake

The live, bounded original public-post scan returned no new verified numeric strategy. Two individually fetched posts were reviewed without following external short links: one [RyanWebb breakout/retest narrative](https://x.com/RyanWebb_KY/status/2116262650359541975) lacks entry/exit numbers; one [finance GitHub-repository list](https://x.com/gusik4ever/status/2114001885413716163) is not a trading strategy. They were excluded from the ten mechanisms instead of fabricating source rules.

## Verification / scope

- Guarded native source count before 11, after 12, private campaign counter 3; conservative effective **12/20**, at most **8** further source screens remain, conditional on live recount and authorized contracts.
- Native Warden hypotheses 147 -> 148, full trials 71 -> 71, selection attempts 182 -> 183.
- Candidate synthetic causal regression: **2 passed**, Ruff: **PASS**, native Warden verify: **PASS**, native Stage1: **REJECT**. Full AI-research-loop suite should be rerun on this evidence commit before merge.
- Exact Warden source adaptation/report and receipt are in VPS-local dirty `quant-lab`; no protected code, OOS holdout, trading API, or real orders touched.
- Prior source archive remains frozen at its **approved cap 80**, all 80 deferred. No attempt to bypass the cap. Earlier Batch1's ES down-day preliminary Stage1 PASS still awaits separate Stage3 economics and session reconciliation.

**Next:** Search genuinely executable first-party Binance USD-M 1h entry+exit with max <=24h, not merely more models with ATR OCO stops. If none is present, continue source-only investigation and preserve the native budget. Research program continues hourly.
