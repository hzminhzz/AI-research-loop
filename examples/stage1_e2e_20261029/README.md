# E2E research → Warden Stage 1: 29 October 2026

**Verdict: Stage 0 + causal verification completed; Stage 1 REJECT.** This is a real-market negative result for one frozen hypothesis. It is not a profitable trading strategy.

## Trace

1. **Research inputs.** Source-grounded review of [Caporale & Plastun (2020)](https://link.springer.com/article/10.1007/s11408-020-00357-1) and [Wen et al. (2022)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4080253). Both are older empirical studies; neither validates the adaptation used here.
2. **Research engine.** Point-in-time archive validated under SHA-256 `99806347...`. The AI-research-loop evidence gateway processed two source records and wrote an auditable artifact. Because no model API key was present, a **ChatGPT-authored, frozen decision adapter** was used; the forecast correctly **abstained** from claiming a calibrated probability. No autonomous API model call occurred.
3. **Stage 0.** Thesis `HYP-AIR-20261029-001` was written through `StrategyThesis` and exported using `WardenHandoff`; Warden registered the hypothesis without bypassing policy.
4. **Causality.** `uv run warden verify` passed three-point prefix invariance on **105,024** rows, 8 assets, contract `CRYPTO_PERPS_1H_V2`, provenance `verified_market`.
5. **Stage 1.** `uv run warden screen` ran once on the predeclared rule. It returned `passed: false`; Warden recorded selection attempt `ATT-f0f2cb2a9facbf51-001` with `REJECT`. **No Warden backtest, Stage 2+, or protected holdout access.**

## Frozen hypothesis

Daily post-shock momentum: at **00:00 UTC**, take the sign of the completed trailing 24h close return when its absolute standardized value exceeds **2.0**, normalized by the trailing 720-hour volatility of overlapping 24h returns, estimated using only observations through the previous hour. Hold direction until the next UTC boundary. Gross exposure capped at 1.0, per-asset weight capped at 0.25. Warden enforces a 1-hour NEXT_BAR execution delay, 4 bp taker fee + 2 bp modeled slippage per side, and funding from the contract.

Universe frozen to BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, ADAUSDT, DOGEUSDT, XRPUSDT and AVAXUSDT. Training begins 2024-01-01; Stage 1 validation window is 2025-01-01 to 2025-07-01; later protected periods were not accessed. This rule is **an original test adaptation, not a faithful replication of the source studies**. No parameter search was performed.

## Warden Stage 1 metrics

| Metric | Measured | Warden requirement | Result |
|---|---:|---:|---|
| Profit factor | **0.8797** | ≥1.15 | FAIL |
| Conditional gross edge per active hour | **−3.31 bp** | Positive net trade-edge condition | FAIL |
| Trade-edge proxy | **−0.01296** | >0.0009 | FAIL |
| Block-bootstrap p-value | **0.80** | <0.05 | FAIL |
| Time in market | **17.68%** | ≥5% | PASS |
| Approximate holding bars (Warden turnover proxy) | **39.13** | Descriptive | — |

The performance evidence does **not** support continuing this rule. A low profit factor and negative conditional edge remain negative results, not reasons to optimize the same frozen attempt.

## Evidence hashes and provenance

- Source archive SHA-256: `998063473330ee2e756b08b4a8025349e0f5441a13a0c9389da6de559621ee2f`
- Dataset SHA-256: `7d8751eb44c8177fee2828fb354a650f29fe4741d1e993f06ae1afdb025b13e2`
- Native hypothesis YAML SHA-256: `2babbebed8531d05e52e188cb67d6fc912d9cd021b5bf7ebd34716460d8fb5ad`
- Candidate strategy SHA-256: `213567e4c126f4ed88eafd49b173cd9b393d816ed24ee501b837bd28681e4a83`
- Warden experiment SHA-256: `46440f85720b9fa22b6b54581641bb510501508e6081ae44836bb4668bb0b803`
- Warden hypothesis trial count after screen: **0**; selection attempts: **1**.

See adjacent files for the archived source records, Stage 0 thesis, Warden-native hypothesis, frozen experiment YAML, strategy code, audit events and forecast artifact.

**Reproducibility warning:** Do not rerun `warden screen` against the same shared registry to check these numbers: Warden records another selection attempt each time. Use an isolated throwaway registry / checkout and the exact pinned dataset to reproduce without inflating the project's trial-selection history.

## Qualification boundary

**Research-to-Stage1 handoff: verified. Fully autonomous model-driven research: not verified.** The production LLM API was not configured, and the papers were summarized in a human-assisted archive rather than fetched automatically by the tool. Live market-data ingestion, independent publisher snapshot attestation and calibrated forecasting remain open integration requirements. No changes to Warden protected contracts or human-gated qualification logic were made.
