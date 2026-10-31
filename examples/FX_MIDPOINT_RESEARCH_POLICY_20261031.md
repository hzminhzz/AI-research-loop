# FX midpoint / OHLCV proxy approval — 2026-10-31

**Decision from principal:** For low-/medium-frequency FX strategy discovery and Stage 0–1, historical bid/ask or tick data are **not mandatory**. Use observed OHLCV open/close as a **research price proxy** with delayed next-bar execution and an explicit estimated spread/slippage charge. Verify execution with venue-specific tick/quote/fill data before live authorization. This is approval of *methodology*, **not** an instruction to weaken Warden gates or self-sign protected contracts.

## Governed proposed research contract

- Draft: [FX_MAJORS_5M_MID_V1_PROPOSAL.yaml](FX_MAJORS_5M_MID_V1_PROPOSAL.yaml), [pinned dataset draft](FX_MAJORS_5M_MID_V1_DATASET_PROPOSAL.json).
- Parent: protected `FX_MAJORS_5M_V1` remains **QUOTE_SIDE** and unchanged. Its 8-asset exploratory snapshot SHA256 is `b364e18b03a2c52c4fc2bb8c54834ce992c7dc7ac63b5bef36258fb0f627558b`; the proposal preserves dataset bytes, val/holdout split, 48-bar label, 12-bar embargo and one-bar execution delay. No holdout data were read or written.
- Draft `FX_MAJORS_5M_MID_V1` uses `NEXT_BAR` with observed `open`, **not** fabricated `bid`/`ask`. This is *not* independently verified to be the actual quote midpoint; avoid describing fills as executable price-side observations.
- Preliminary cost per side: **3.0 bps total** = 0.2 bps commission + **1.3 bps assumed half-spread + 1.5 bps residual slippage** (the latter two carried in Warden's `slippage_bps=2.8` because the frozen schema has no separate spread field). Round trip **6.0 bps**; 2x stress **12.0 bps**; assumption is conservative but **not broker-measured**. Longer horizon/symbol-specific economics require separate calibration.
- Screen only a source-faithful, preregistered thesis with causal closed-bar signals, matching <=48-bar hold/label and actual spread-sensitive economics. The original `QUOTE_SIDE` contract must still fail on missing quotes; no silent fallback. Do not claim a Stage1 PASS proves follower PnL, executable returns or trading approval. Only test source-specific symbols actually cleared by the quality gate.

## Separate blocker: source price integrity

Read-only inspection of the pinned *exploratory* 5m panel found open vs previous close absolute jumps over 2%: AUDUSD **97**, GBPUSD **19**, USDCAD **12**, CADJPY **1**, GBPJPY **1**, USDCHF **1**, EURUSD **0**, USDJPY **0**. Some gaps/news events can be genuine, but values as large as 16.9%/12.9%/30.7% on AUDUSD/GBPUSD/USDCAD warrant forensic comparison to independent price history. EURUSD had **37** gaps above 0.5% even though none exceeded 2%; it is not certified clean.

Existing `quant-lab/.workspace/fx_stage3/decision_record.md` documents erroneous level-shift bars in LSE-derived FX minute history. Hence the *present 8-pair snapshot is not qualified for blanket midpoint Stage1 evaluation*. First quarantine or verify anomalies without hindsight selection, preferably rebuild from a qualified provider if needed. An independent data digest and governed contract are required if a rebuilt file changes bytes. Do not remove outliers just because they impair an intended strategy, and do not reinterpret market shocks as corruption without evidence.

## Activation and stage distinction

1. Record principal's research-only midpoint permission (this document). The draft is intentionally **not installed** in `quant-lab/contracts/` and not present in its protected manifest, because the Warden runbook reserves independent manifest signing/approval to the human boundary. The signed/approved contract and matching dataset manifest must be activated through the established governance procedure; don't self-certify.
2. Complete source-quality review for the specific target instruments and approve the corresponding immutable snapshot. Cross-check costs at 1x and 2x. Retain effective selection-attempt counts across parent and proposed sibling contract so the new ID cannot reset DSR/lineage/search penalties.
3. Once legitimately activated, run native preflight, causal prefix verification and Stage1 under the shared Warden writer lock. Missing bid/ask alone is **no longer an economic-policy objection** to midpoint research. Missing source rules, data quality, horizon or cost adequacy remain independent blockers.
4. At Stage3: test 1.5x and 2x assumed costs, +1-bar latency, subperiod and tail-event sensitivity; label results *midpoint-estimated*, not executable. Before forward deployment/capital authorization, use real venue quotes/ticks or broker fills to validate spread, stop/limit execution, latency, adverse selection and prop-firm restrictions. Strategies relying on intrabar stops cannot be faithfully screened from OHLCV alone.

**Scientific/budget state:** No Warden registration/screen executed as part of this decision; no campaign budget used, no holdout unsealing, and no live orders.
