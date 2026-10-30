# Original-source Warden research batch — 30 October 2026

**Outcome: Two independent source-backed strategy adaptations implemented and Stage 1 screened; both REJECTED. Zero full backtests, zero protected holdout reads, zero orders.**

Conducted directly on VPS `/home/quant/dev/quant-lab` using the source pipeline at `/home/quant/dev/AI-research-loop`. The user explicitly authorized research and bounded new data-contract creation. The existing divergent/dirty quant-lab main, old trials and all unrelated source changes were preserved; no quant-lab Git push is implied by this report.

## Summary

| Experiment | Source idea | Market, cadence | Native causality | Stage 1 PF | Bootstrap p | In market | Final |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| `HYP-SOC-BTA-NQMON-20261030` | [Breakout Trading Academy: Monday NQ Bollinger + ATR](https://breakouttradingacademy.com/steal-this-monday-nasdaq-strategy-super-simple/) | NQ CFD, 1-hour, Monday | PASS, 55,766 rows | **1.1384176199** | 0.01 | 17.1% | **REJECT**: PF below 1.15 |
| `HYP-SOC-QC-TOM-ES-20261030` | [QuantConnect: SPY turn-of-month](https://www.quantconnect.com/research/15377/turn-of-the-month-in-equity-indexes/) | ES CFD, 1-day, 3 NYSE sessions | PASS, 3,111 rows | **0.9286388123** | 0.54 | 15.2% | **REJECT**: PF, p and negative edge |

Both are **adaptations of original publisher strategies**, not literal futures/ETF backtest replications. Both use existing human-owned Warden logic and immutable market snapshots. Both counts appear in Warden's append-only `selection_attempts` table. Neither was followed by post-rejection tuning, Stage 3, qualification, a protected holdout read or broker execution.

### 1. BTA Monday NQ Bollinger+ATR — near-miss, frozen rejection

- Original public post dated 2026-07-16. Current original article capture 2026-10-30 has text SHA256 `4b60f2ce4f0350e36016bf63f375fcc52bc8ca19649f1a5c9e03fa45944e15b4`.
- Publisher specifies E-mini NQ futures, 60-min bars, trigger based on lower Bollinger(10, 1 standard deviation) +0.8×ATR(5), Monday midnight–23:00 Chicago, stop-order entry if the next bar hits and 23:00 exit.
- Our CFD **adaptation** assumes a long-side stop (not expressly stated in the source table), computes the indicator from completed bars and enters only after a completed hourly high touches the previous bar's trigger; Warden fills **at the following hourly bar**. Exit target 0 at 22:00 Chicago; Warden next-bar exit at 23:00, including DST changes. One entry/Monday; NQ-only.
- Requested and ACTIVATED derived research contract `AUTO_INDICES_1H_V2_H24_E24_F5_S10_V1` using approved factory `src/workflow/contract_factory.py`. Original parent `INDICES_1H_V2` dataset SHA256 `03a9d948793542cba79f485d7a1fa39a3435252069bf9d131596303ec315ca55`; unchanged exploratory/validation/holdout splits, label and embargo 24 hourly bars, 0.5bps taker and 1.0bps slippage per side. Delegated **unsigned** approval, never independent HMAC attestation. The factory recorded **30 prior related selection attempts**; contract ID does not reset the family.
- Native Warden verify job `warden-verify-c1131e6f588571f4d2`: PASS, 55,766 rows, prefix_invariance=true, cached=true, verified_market. Five causal/DST/unit tests passed.
- Native Warden screen job `warden-screen-1a63932004c10bcaf6`: `passed=false`, stage1 `ATT-f6e9f68b4805e076-001`, **REJECT**. PF=1.1384176199 (minimum 1.15), bootstrap p=0.01, conditional edge 0.0001124372 (1.12bps per hour), trade edge 0.0021668938 (21.67bps), time-in-market 17.1065%, avg holding=19.272 hourly bars. Process exit1 is the Warden scientific rejection, not infrastructure damage.
- BTA publisher investigated approximately **1,800 Bollinger configurations**, then selected Monday. The publisher published only after the Warden 2023–2025 validation interval. Low bootstrap p from this test does **not** erase source-side or 30+ platform selection attempts or constitute independent OOS. No subsequent tuning permitted under the frozen protocol.
- Full immutable local report: `quant-lab/.workspace/hypotheses/HYP-SOC-BTA-NQMON-20261030_RESULT.md`. Implementation: `quant-lab/strategies/candidates/bta_monday_nq_bollinger_cfd_1h.py`. Spec: `quant-lab/experiments/active/bta_monday_nq_20261030.yaml`.

### 2. QuantConnect SPY turn-of-month — negative delayed ES CFD adaptation

- Original public QuantConnect post [Turn of the Month in Equity Indexes](https://www.quantconnect.com/research/15377/turn-of-the-month-in-equity-indexes/) accessed 2026-10-30. **Original publication date not independently established.** Publisher buys SPY about 1 minute after the last NYSE trading session opens, claiming to hold for three trading sessions. The published `OnData()` counter may be callback-based rather than actual sessions; do not fabricate fidelity.
- Our predeclared ES CFD adaptation observes the *close* of the final NYSE month session, emits +1 ES long; Warden fills next available daily ES CFD bar, potentially a partial **Sunday** session. Desired flat target at the end of third NYSE trading session of the next month, followed by Warden NEXT_BAR exit. This does **not** reproduce an SPY equity open order.
- Approved existing `INDICES_1D_V1` contract reused without change: verified data SHA256 `0e4677355587831849598a1217ab9987b991d9ed8ff0dc2f3369782fad36ba27`, 2015–2025 ES 3,111 daily rows, one-day NEXT_BAR execution, 5 daily-bar label, 0.5bps fee +0.5bps slippage each side. Ex-ante XNYS schedule found **125 complete monthly windows with 3–5 recorded CFD bars**; final June 2025 month-end not opened because its exit would be outside the exploratory sample.
- Eight schedule, Sunday, wrong-market and causal-prefix tests passed (13 combined across both source candidates).
- Native Warden verify job `warden-verify-82262b8969d1733afe`: PASS, 3,111 rows, prefix_invariance=true, cached=true, verified_market.
- Native Warden screen job `warden-screen-d89a9c73b033321b61`: `passed=false`, selection attempt `ATT-b56aee52fba281bc-001`, **REJECT**. PF=0.9286388123, bootstrap p=0.54, negative conditional edge −0.000171831 (−1.72bps), negative trade edge −0.0006758685 (−6.76bps), time in market 15.17%, avg holding 3.93 **daily** bars. The structured Warden notes abbreviate it as 'h' although the verified contract is daily; report units from the contract rather than the abbreviated string.
- The original SPY strategy is **not disproved** by this negative ES CFD adaptation. No parameter, session, instrument or direction optimization was done afterward.
- Full immutable local report: `quant-lab/.workspace/hypotheses/HYP-SOC-QC-TOM-ES-20261030_RESULT.md`. Implementation: `quant-lab/strategies/candidates/quantconnect_turn_month_es_cfd_1d.py`. Spec: `quant-lab/experiments/active/qc_turn_month_es_20261030.yaml`.

## Governance and accounting

- Shared Warden exclusive writer path `/home/quant/dev/quant-lab/registry/warden-writer.lock`.
- Only the typed guard and idempotent durable systemd `verify`/`screen` jobs performed protected Warden writes.
- Guard state before and after: `READY_FOR_DISTINCT_RESEARCH`, Warden `check-worktree` PASS, old XSRR001/002 quarantine preserved.
- Final authoritative registry after these runs: **139 hypotheses, 71 full trials, 174 selection attempts**. Start: 137/71. Two hypotheses and two Stage1 selection attempts added; **no new full trials**.
- One bounded, source-specific new **research contract** with inherited data hash and selection history; no other existing Warden YAML was modified. The parent repo has unrelated dirty files and is ahead/behind upstream; they remain untouched.
- Production holdouts remain sealed; zero broker orders or trading allocations.

## Next economically distinct source candidates / preflight dispositions

| Source | Mechanism / market | Current disposition and next research requirement |
| --- | --- | --- |
| [Empirica Lab — Bitcoin 50-day rule](https://empiricalab.substack.com/p/bitcoin-50-day-rule) | BTC spot 50-day trend filter, long/cash | **DATA/CONTRACT HOLD**: exact 50-day SMA rule is visible, but average trade ~22 days and some 60+ day trends exceed the existing `CRYPTO_PERPS_1D_V1` 5-bar label. The underlying is BTC spot while available contract executes a perpetual with funding; source acknowledges only 5/11 internal checks and reports PBO 62% over six lookback windows. Requires properly budgeted horizon/PIT dataset and review, not an ad hoc 5-bar proxy. |
| [Quantified Strategies — ES IBS Mean Reversion](https://quantifiedstrategies.substack.com/p/es-ibs-mean-reversion-strategy-futures) | ES intraday balance mean reversion | **RULES BLOCKED**: public publisher page exposes the title and heading but not complete entry and exit rules. No reverse-engineering from promotional performance. |
| [BTA — Short Opening Gap](https://breakouttradingacademy.com/how-to-build-a-short-opening-gap-strategy/) | NQ morning gap fade/continuation | **SOURCE_SELECTION/RULES HOLD**: source searched 225 gap/ATR combinations and then selected Thursday; article explicitly warns about overfitting and does not specify a complete executable stop/exit parameter set. Requires original exact rule and all selection multiplicity before native Warden. |
| [BTA — 1-hour ES short breakout](https://breakouttradingacademy.com/this-weird-e-mini-sp-500-strategy-is-simple-yet-very-profitable/) | ES one-hour short event | **EVENT_FREQUENCY REVIEW**: original intrabar stop fills do not match next-bar 1h CFD bar simulation; only a small fraction of hourly observations can be active, so the global Warden 5%-time-in-market screen may be structurally difficult. Prefer independently approved event-based minimum trade count/power criterion or faithful 1m execution contract, **not** silently relaxing thresholds on failed trials. |
| [Finetiq — AVWAP/EMA flush](https://ideas.finetiqsystems.com/en/ideas/avwap-ema-flush/) | Intraday anchored VWAP / EMA mean reversion | **SOURCE DATA REVIEW**: identify precise anchor and required legitimate volume data, exchange session boundaries, full stop/exit and market. Avoid importing author's incomplete idea as executable rule. |

**Highest-value improvement:** implement original-source-to-execution equivalence tests and explicit event-type market-data contracts (e.g., stop-trigger detection and next *minute* quote/fill), not more frozen-template reinterpretations. Inadequate execution fidelity can turn a viable original trading rule into an unrelated Warden test. This engineering direction is a proposal, not a claim that source strategies are profitable. Any new contract or evaluator semantics remain behind existing delegation and principal governance.

## Continuation checklist

- Mark the two above exact hypothesis and source-adaptation tuples as **already screened/rejected**. NEVER silently rerun them on the same Warden validation or relabel them as unseen. Do not backtest failed Stage1.
- Mine an *independent* source with explicit entry, exit, realistic executable asset and short enough label horizon, preferably a non-price feature available within the verified panel. Recheck latest source text and frozen parameters before starting.
- Every future candidate begins with source provenance and economic mechanism, then exact contract, prefix causal tests and guard check, then one immutable Stage1 selection attempt. Stage3 only on native pass; do not open protected holdout without user approval.

## Addendum — third independently screened source (2026-10-30 ~08:24Z)

The research loop continued after the initial two rejections. It used
[BTA's weird NQ genetic breakout](https://breakouttradingacademy.com/weird-nasdaq-algo-strategy/)
as a **new, distinct source-specific hypothesis** rather than revising either
previously failed model.

- Hypothesis: `HYP-SOC-BTA-WEIRDNQ-20261030`
- Source: BTA, May 22 2024, public source capture SHA256
  `6e919373c1d70ed055ff543d57d77beeb1629b7283012159ff268e01128d4326`.
  Author selected the complicated 35-open/typical-price breakout level
  from **thousands of genetic algorithm trials**, not a pre-declared rule.
- Frozen adaptation: NQ **CFD 30-minute bars**, long signal after a
  completed-bar high crosses the prior-bar high + abs(prior HLC3 minus
  highest open of 35 completed bars), 07:00–17:00 Eastern target,
  flat target 17:30 Eastern. Warden fills NEXT_BAR rather than the
  author's intrabar futures stop. The author's $1,000 E-mini stop
  **was not reproduced** and is an explicit severe execution-fidelity limit.
- New governed derived contract (principal delegated, independently unsigned)
  `AUTO_INDICES_30M_V1_H24_E24_F5_S10_V1`, original pinned source
  SHA256 `25f8c39dc245f0fe6070ce3fe3cd4063fd3093f7c951d9ed017f36367f23ff8f`,
  H24 label/E24 embargo, 0.5bps taker + 1.0bps slippage each side.
  Original exploration/validation/holdout timestamps unchanged.
- Nine formula/DST/prefix tests passed.
- Guarded Warden durable verify job `warden-verify-3bc96aea8bba1743d2`
  **PASS**, 109,100 NQ observations, prefix_invariance=true, verified_market.
- Guarded Warden durable screen job `warden-screen-8f681692bda9150bff`
  **STAGE_1_REJECT**, PF=1.047512403460569 vs threshold 1.15,
  bootstrap p=0.04 (not multiplicity-adjusted),
  conditional edge=0.00006091939629, trade edge=0.00082288046,
  time-in-market=21.3573%, average holding=13.5077 **30-minute bars**
  (not 13.5 hours). Immutable attempt `ATT-5baffc268b6d26ce-001`.
- No tuning, full Stage3 backtest, qualification, holdout read or live order.
  All prior quarantines and dirty quant-lab changes remain untouched.

**Authoritative after this batch:** Warden 140 hypotheses, 71 full trials,
175 source/trial selection attempts. The prior two source-specific rejections
are still frozen and a third rejection has been added. This is **not**
three statistically independent OOS tests: original publication timing and
source-side massive parameter search must be accounted for.

The live original-source archive and non-scientific review ledger are at
`runs/archive_discovery/shortlist.json` and
`runs/social_campaign/archive_progress.json`. Six reviewed source entries
are deferred with concrete data/execution/rule gaps, leaving 44 archive leads
to investigate. The hourly ChatGPT Research Director is enabled and does
not stop at either a rejection or a passing Stage1 signal.

**Next material experiment:** Algomatic
[3 Down, 3 Up on Nasdaq](https://www.algomatictrading.com/post/3-down-3-up-on-nasdaq)
publishes the precise CFD daily ProRealTime trading code: 3 bearish daily
bars, one body ≥70% of its candle's range, enter long; 3 bullish
daily bars, exit. Source backtest mean holding ≈10 days; existing governed
`INDICES_1D_V1` has label=5 daily bars. This is **BLOCKED_DATA**, not
a fabricated rejection: a properly authorized ≥20 daily-bar
label/embargo and CET-daily time contract is required, and the current
bounded research factory does not allow derivation from that daily parent.
Never silently shorten the holding period to five days to fit a gate.
