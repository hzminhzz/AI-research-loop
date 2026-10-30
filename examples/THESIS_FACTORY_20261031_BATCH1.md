# Quant Thesis Factory — source-first batch 2026-10-31

**Scientific boundary:** Three genuinely distinct Warden-native Stage1 screens completed; remaining eight source-backed mechanisms are **blocked BEFORE Stage1**. No strategy is financially qualified or authorized for trading.

## Native Stage1 results

| Hypothesis | Instrument / frequency | Warden verify | Native PF | Bootstrap p | TiM | Avg holding | Verdict |
|---|---|---|---:|---:|---:|---:|---|
| `HYP-SOC-BTA-ADXNQ-20261031` | NQ_CFD 30m | PASS | 1.0084 | 0.095 | 20.0% | 10.56 30m | **REJECT** |
| `HYP-SOC-BTA-INDEXDOWN-20261031` | ES_CFD 1d | PASS | 1.3598 | 0.000 | 45.6% | 1.76 1d | **PASS** |
| `HYP-SOC-BTA-TIMENQ-20261031` | NQ_CFD 1h | PASS | 1.0983 | 0.025 | 9.3% | 10.46 1h | **REJECT** |

Native Warden gates: PF >=1.15, bootstrap p<0.05, time-in-market>=5%, trade edge >1.5× one-way costs. The reported bootstrap p=0.000 is a finite numerical estimate, not proof that chance is impossible. Published selected strategies have unquantified source-level multiplicity. Exact receipts are stored in VPS durable systemd jobs and append-only Warden registry.

**One preliminary PASS:** `HYP-SOC-BTA-INDEXDOWN-20261031` was tested as a new ES CFD conjecture, NOT as a replication of the BTA index cash tendency. Warden Stage3 requires cash-market/CFD session reconciliation, source-side selection accounting, deflated Sharpe, fee and latency robustness, and no protected holdout access.

## Distinct unscreened research theses

| ID | Mechanism | Source | Precise blocking prerequisite |
|---|---|---|---|
| `TH-20261031-THURSDAY-NQ-SHORT` | end-of-week downside order-flow acceleration | [Original/source](https://breakouttradingacademy.com/this-nasdaq-short-strategy-works/) | Do not register merely to consume a guaranteed failing TiM screen; resolve exact rules or choose a different intrinsically higher-exposure hypothesis |
| `TH-20261031-ALG-XAU-STOCH-EXTREMES` | stochastic exhaustion mean reversion with trend filter | [Original/source](https://www.algomatictrading.com/post/a-mean-reversion-gold-system-using-stochastic-extremes) | Obtain exact original full code and allow 2h XAU research contract; no unpaid author rules invented as source fidelity |
| `TH-20261031-FINETIQ-ES-KAMA` | adaptive trend persistence / price smoothing | [Original/source](https://ideas.finetiqsystems.com/en/ideas/kama-trend/) | Verify CME 360m bar alignment and create a human-authorized research contract; do not map to 4h or 1d |
| `TH-20261031-FINETIQ-HH100-MA10` | long-horizon structural price discovery breakouts | [Original/source](https://ideas.finetiqsystems.com/en/ideas/new-high-breakout-ma10-exit/) | Request separately governed >MA10-exit daily-index contract and genuine broker financing |
| `TH-20261031-FH-QQQ-GAPM` | overnight opening-gap composition momentum | [Original/source](https://financial-hacker.com/the-gap-momentum-system/) | Obtain verified QQQ data and author-vintage code; not screenable under current CFD-only validated registry |
| `TH-20261031-FINETIQ-DONCHIAN70` | always-in breakout / crisis convexity replica | [Original/source](https://ideas.finetiqsystems.com/en/ideas/always-in-breakout/) | Long horizon contract plus source stop interpretation/fill integrity before Warden |
| `TH-20261031-ALG-3D3U` | three-candle exhaustion / multi-day index reversal | [Original/source](https://www.algomatictrading.com/post/3-down-3-up-on-nasdaq) | Preflight research-only extended daily indices contract and CET source-fill consistency, no fabricated 5-day exit |
| `TH-20261031-QC-FX-CARRY` | cross-currency interest rate differential carry | [Original/source](https://www.quantconnect.com/learning/articles/investment-strategy-library/forex-carry-trade) | Acquire historical rate vintages and original nine forex series, extend label contract by authorized process; no seven-major shortcut |

## Cross-market hypothesis ledger

The [machine-readable batch record](./THESIS_FACTORY_20261031_BATCH1.json) contains original URL, SHA256 capture, publisher-versus-researcher rule provenance, economic mechanism/counterparty, entry/exit, sizing, expected horizon, timezone/session, fees/spread/financing assumptions, PIT controls, baseline, falsification, selection debt and next actions for all 11 items. Source-derived excerpts and third-party pages are untrusted research evidence, never executable instructions.

## Immutable accounting

- Initial registry: 140 hypotheses / 71 full trials / 175 selection attempts.
- Final registry: 143 hypotheses / 71 full trials / 178 selection attempts.
- This batch: 3 new hypotheses registered, 3 causality/prefix-verifies PASS, 3 native Stage1 screens, **1 pass and 2 rejects**, 8 source blockers, 0 full Stage3 trials, 0 protected holdouts, 0 orders.
- Lifetime source campaign screen cap is 20. Read-only authoritative registry query found **7 distinct `HYP-SOC-*` native Stage1 attempts**, including four prior source attempts (one older Stoic XSMOM19 result beyond the three immediately cited) and three from this run: **at most 13 slots remain**. Source-campaign private counter is 3 and overlaps the native ledger; the driver now enforces `max(private_count, native_HYP_SOC_count)` before any new screen. Future direct executors must also honor this shared cap.

## Archived local artifacts

All candidate modules and Warden hypotheses live in `/home/quant/dev/quant-lab`; full Warden-native source experiment files and result narratives are currently **VPS-local and uncommitted**, because the existing quant-lab working tree is dirty/divergent. Protected files were not altered. This GitHub evidence artifact is not proof that quant-lab candidate code is pushed or reproducibly packaged outside the VPS.

Native receipts:

- `HYP-SOC-BTA-ADXNQ-20261031`: attempt `ATT-0135377556327165-001`, durable `warden-screen-9b59ceb71f65eb4259`, hypothesis/result `.workspace/hypotheses/HYP-SOC-BTA-ADXNQ-20261031[_RESULT].md`.
- `HYP-SOC-BTA-INDEXDOWN-20261031`: attempt `ATT-4f8505fedde82ba2-001`, durable `warden-screen-bf18f8984c89556595`, hypothesis/result `.workspace/hypotheses/HYP-SOC-BTA-INDEXDOWN-20261031[_RESULT].md`.
- `HYP-SOC-BTA-TIMENQ-20261031`: attempt `ATT-df6d30871f03b245-001`, durable `warden-screen-01c5116050c30d8277`, hypothesis/result `.workspace/hypotheses/HYP-SOC-BTA-TIMENQ-20261031[_RESULT].md`.

## Continuation

Resume from the persisted archive source queue and this batch, prioritizing genuinely new short-horizon crypto 1h and index/FX 5m strategies. Do not repeat these three results or convert source blockers into backtests. The independent hourly Research Director may inspect the single Stage1 PASS handoff, but no Stage3 can be claimed without its own Warden receipt and selection-risk reconciliation.
