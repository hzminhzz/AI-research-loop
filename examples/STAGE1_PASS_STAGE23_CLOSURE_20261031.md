# Stage 1 PASS → Stage 2 / Stage 3 closure — 2026-10-31 UTC

**Research-only outcome: eight scientifically admissible prior Stage-1 PASS candidates have a native Stage-3 trial either on their original contract or on an explicitly disclosed *different* contract. The ninth historical PASS is quarantined and remains disqualified. Three related AF30 risk-scaling mechanisms have existing Stage-3 candidate verdicts and now each has a complete 6/6 native audit; **all three also already have historical `REJECTED_ON_HOLDOUT` records**. Two earlier index mechanisms have historical `PROMOTED` records despite their Stage-3 `REVISE` verdicts and failed six-check audits. One new ES CFD Stage-3 trial is REVISE / audit REJECTED. No new Stage-1 screen, **holdout dataset read in this execution**, or real order.**

This is a reconciliation of **all** native `STAGE_1_SIGNAL/PASS` rows in the Warden append-only ledger, not only social-source hypotheses. The authoritative machine-readable, live-SQLite-read-only snapshot is [Stage1 PASS → Stage23 ledger](STAGE1_PASS_STAGE23_CLOSURE_20261031.json). Each row includes the Stage1 attempt ID, latest actual Stage3 run, native verdict/metrics, audit checks, direct-vs-rehomed contract, and quarantine history.

## Every recorded Stage-1 PASS

| Original Stage-1 hypothesis | Stage-1 contract | Stage-3 identity | Native Stage-3 net Sharpe / DSR | Audit | Final classification |
|---|---|---|---|---|---|
| `HYP-2026-065` | `INDICES_1H_V2` | `RUN-HYP065-003` (direct) | 1.257 / 0.560 | REJECTED | Pre-existing REVISE; full 3 trials already consumed |
| `HYP-2026-069` | `INDICES_1H_V2` | `RUN-HYP069-001` (direct) | 1.392 / 0.301 | REJECTED | Pre-existing REVISE; no outcome-based retry |
| `HYP-2026-095` — S01 | `MULTI_ASSET_1D_V1` | `RUN-HYP095-002` (direct) | 1.317 / 0.451 | REJECTED | Pre-existing REVISE; outlier/DSR sensitivity |
| `HYP-2026-096` — S02 | `MULTI_ASSET_1D_V1` | **`RUN-HYP112-003`** on `INDICES_1D_V1` | **1.224 / 0.976** | **6/6 APPROVED** | Related risk-scaling mechanism on re-homed 6-index book, not original 17-asset Stage3 |
| `HYP-2026-097` — S03 | `MULTI_ASSET_1D_V1` | **`RUN-HYP113-003`** on `INDICES_1D_V1` | **1.243 / 0.973** | **6/6 APPROVED** | Related variable-risk mechanism on re-homed 6-index book |
| `HYP-2026-098` — S04 | `MULTI_ASSET_1D_V1` | **`RUN-HYP114-003`** on `INDICES_1D_V1` | **1.247 / 0.973** | **6/6 APPROVED** | Related portfolio-scaling mechanism on re-homed 6-index book, max DD 33.7% |
| `HYP-2026-099` — S05 | `MULTI_ASSET_1D_V1` | `RUN-HYP099-001` (direct) | 0.879 / 0.314 | REJECTED | Pre-existing REVISE |
| `HYP-2026-128` | `CRYPTO_PERPS_TOP100_1H_V1` | `RUN-XSRR-002` (historical, contaminated) | −0.521 / 0.010 | REJECTED | **QUARANTINED**, not admissible; 159 unregistered diagnostics and horizon mismatch |
| `HYP-SOC-BTA-INDEXDOWN-20261031` | `INDICES_1D_V1` | **`RUN-SOC-BTA-INDEXDOWN-20261031`** (new native trial) | **1.035 / 0.844** | **4/6 REJECTED** | **Stage 3 REVISE; no promotion** |

**Selection caveats:** 096–098 and 112–114 are related implementations evaluated on different Warden contracts, not independent replications or unseen OOS. Legacy 065/069 have historical `PROMOTED` qualification records, but their **native Stage3 verdicts are `REVISE` and current six-check audits REJECTED**. The first status records a previously invoked human-override holdout rule; it cannot override a scientific failure. The quarantined residual reversal 128 remains immutable and untouched. The three AF30 6/6 Stage3 audit approvals have no new full trials in this invocation; they **already failed their historical consumed holdouts**, so **do not rerun the same holdout**. The last Stage3 trial has unmeasured default neighbor stability `1.0`, while earlier same-parameter versions measured 0.996 / 0.946 / 0.944. These are not independent fresh alpha approvals.

## Previously consumed protected holdouts — registry metadata only

**Verified via read-only `qualifications` SQL, not by opening any protected dataset.** Five original Stage1 PASS lineages have prior holdout records. These are historic, fully consumed holdout evidence that cannot be presented as unseen/untouched or rerun:

| Earlier Stage3 run | Historical holdout net Sharpe | Validation-to-holdout Sharpe ratio | Recorded hypothesis status | Scientific interpretation |
|---|---:|---:|---|---|
| `RUN-HYP065-003` | 1.109 | 0.882 | `PROMOTED` | Stage3 `REVISE` and 6-check audit REJECTED; **promotion/audit conflict** |
| `RUN-HYP069-001` | 1.108 | 0.796 | `PROMOTED` | Stage3 `REVISE` and 6-check audit REJECTED; **promotion/audit conflict** |
| `RUN-HYP112-003` — S02 | 0.730 | 0.596 | `REJECTED_ON_HOLDOUT` | 6/6 Stage3 audit approval is **not** final qualification |
| `RUN-HYP113-003` — S03 | 0.582 | 0.468 | `REJECTED_ON_HOLDOUT` | 6/6 Stage3 audit approval is **not** final qualification |
| `RUN-HYP114-003` — S04 | 0.594 | 0.476 | `REJECTED_ON_HOLDOUT` | 6/6 Stage3 audit approval is **not** final qualification |

The native holdout rule for recorded promotions requires holdout Sharpe `>0.80` and holdout/validation Sharpe ratio `>=0.50`; all three AF30 indices siblings failed the absolute Sharpe requirement. The two older index runs were historically promoted using a human-authorized high-Sharpe `REVISE` exception, but they have not passed Warden's current scientific Stage3 audit. Existing promotion records are historical, not a basis to authorize live trading. **This execution performed zero new holdout reads, zero qualification actions, zero broker orders.**

## New ES down-day Stage 2: exact frozen code/contract, read-only native simulation

Source: [Breakout Trading Academy index down-day tendency](https://breakouttradingacademy.com/big-index-trading-secret-to-get-real-results/) (2022 publication claim, captured 2026; author has six tendencies, unknown further selection). Our independent ES daily CFD **red `close < open` candle → long at next open, flat after nonred candle** is not source replication. Native contract `INDICES_1D_V1` pins exploratory ES data SHA256 `0e4677355587831849598a1217ab9987b991d9ed8ff0dc2f3369782fad36ba27`, NEXT_BAR execution, and 0.5bps taker+0.5bps slippage per side, no financing. 3111 source bars for ES (2015–2025), validation 778 bars Jan 2023–Jun 2025. Source is verified-market CFD, *not* NYSE cash-index daily bars.

The read-only script [stage2_es_indexdown_readonly.py](../scripts/stage2_es_indexdown_readonly.py) invoked actual Warden `resolve_dataset`, `execution_returns` and `simulate_positions` with the exact existing frozen Warden strategy (no parameter edits, no Stage1 budget use, no registry constructor). [Exact Stage2 JSON](STAGE2_ES_INDEXDOWN_20261031.json).

| Diagnostic | Net Sharpe |
|---|---:|
| Native cost (1bp per side) | 1.034708 |
| 1.5× native costs | 0.974710 |
| 2× native costs | 0.914685 |
| Additional **one bar** of entry/exit lag | **−0.269278** |
| Setting best 5% validation bars' returns to zero | **−1.741000** |

Attribution on original positions only: 129/778 validation bars are **Sunday-labeled**; 260 Sunday-or-Monday intervals contribute `0.16959` of `0.34757` summed native net-return fractions (**48.8%**). 57 Monday intervals after a Sunday red signal contribute `0.14543` (overlapping the prior category; DO NOT add these two buckets). Top 5% best bars contribute 211.6% of original summed net results, so tail dependence is severe. This is explanatory **attribution**, not a retuned weekdays strategy. Original BTA cash-index open/close and ES CFD Sunday/UTC-midnight pricing are not interchangeable.

## New ES Stage 3 — official native Warden receipt

- **Frozen experiment:** `experiments/active/bta_index_down_es_cfd_1d_20261031.yaml`; zero `param_grid` and no modified signal thresholds.
- **Job:** `warden-backtest-0d82835a48987553fd`, submitted/polled by the existing durable-jobs CLI under the governance-guard and exclusive Warden writer lock, transcript in `runs/warden_jobs/`. Process logged **`WARDEN_RUN_COMPLETE`** and the structured `REVISE` verdict.
- **New Warden trial:** `RUN-SOC-BTA-INDEXDOWN-20261031` (first lifetime trial), net Sharpe **1.034708**, PF **1.359836**, max drawdown **12.73%**, annual turnover **162.53**, breakeven **9.60bps per unit turnover**, native DSR probability **0.843550** against a Stage3 gate of **0.90**. Additional one-bar lag Sharpe **−0.269278** fails the native latency gate; 2× cost Sharpe **0.914685** clears the stand-alone 0.5 hurdle, but is insufficient. Official benchmark Sharpe 1.217 is zero-cost equal-weight buy-and-hold at different exposure; **not risk-matched** to the red-bar strategy. Relative reported annualized return −6.57pp is likewise not an equal-exposure alpha test.
- Warden `verify-causality --run-id RUN-SOC-BTA-INDEXDOWN-20261031` **PASS** for 5 truncation cutpoints (code closure/dataset/config bound; not a mathematical proof of every causal edge).
- Native `audit-check` **REJECTED** checks **2 outlier sensitivity** and **5 cost + latency survival**; checks 1,3,4,6 pass. An initial pre-causality audit showed check3 false; rerunning **only the deterministic audit**, after legitimate strategy-bound causal proof, yielded the correct **4/6**. The trial was not rerun.
- Native timing circular-shift diagnostic `p=0.1343` is **not a formal gate**; evidence is weak vs shift null. Original publisher-side search beyond six published tendencies is UNKNOWN and not included in Warden effective rank. The reported DSR is therefore not a fully source-selection-adjusted inference.

No second attempt, no rule inversion, no Sunday filtering for performance selection, no new contract, no holdout access, no orders.

## Existing AF30 Stage3: direct audits without new backtests

`RUN-HYP112-003`, `RUN-HYP113-003` and `RUN-HYP114-003` already had full Warden Stage3 receipts (net Sharpe 1.224/1.243/1.247; DSR0.976/0.973/0.973). We ran **native `warden verify-causality`** on each exactly recorded strategy module/import closure, parameter config, and dataset digest. All passed 5 prefix cuts. We then ran native `warden audit-check` for each; **6/6 APPROVED** and appending the code-bound evidence. This repairs the previously missing native audit check3 **without consuming any full trial or touching evaluator code**.

No new Stage4 qualification was attempted. **The three index Stage3 audit-approved runs already consumed their protected holdouts and were `REJECTED_ON_HOLDOUT`**, with historical holdout Sharpe 0.730/0.582/0.594 (see read-only records above). S04's 33.7% validation drawdown is another prop-firm suitability concern. Six-check `APPROVED` means *validation audit passed*, not trading authorization; it does not erase historical negative holdout evidence.

## Full-ledger counters & governance

| Counter | At start | At end |
|---|---:|---:|
| Registered Warden hypotheses | 148 | **148** |
| Warden full trials | 71 | **72** |
| Selection attempts | 183 | **183** |
| New Stage1 source screens | 0 | **0** |
| Source-family Stage1 use | 12/20 | **12/20** |
| Native audited candidate validation approvals | prior incomplete evidence | **3 complete, 6/6 (all historically holdout-REJECTED)** |
| Prior holdout records (read-only metadata) | 5 | **5 (2 PROMOTED, 3 REJECTED_ON_HOLDOUT)** |
| New protected holdout reads or orders | 0 | **0** |

`uv run warden check-worktree` PASS. Cross-workspace `governance_guard` READY. Existing `HYP-2026-126`, `HYP-2026-128`, `RUN-XSRR-001/002`, rejected sources and 428 unrelated dirty quant-lab files remain untouched. Work was read-only or guarded by the shared lock; no raw SQL writes.

**Disposition:** All nine original Stage1 PASS attempts are accounted for. **Three rehomed AF30 siblings are NATIVE_STAGE3_AUDIT_APPROVED_BUT_HISTORICALLY_HOLDOUT_REJECTED.** Two older indexes carry historical `PROMOTED` holdout records but current Stage3 `REVISE` and rejected audits (**conflicting scientific evidence, not approved trading alpha**). Two other older hypotheses are Stage3 REVISE/audit REJECTED; the new ES hypothesis is Stage3 REVISE/audit REJECTED; one residual-reversal lineage remains quarantined. No live trading authorization, no untouched holdouts for those five historical read lineages, no retries on closed experiments.
