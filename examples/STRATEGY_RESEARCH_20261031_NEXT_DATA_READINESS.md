# B16 next-mechanism data readiness — 2026-10-31 (READ-ONLY)

**Finding:** A stronger *observable* signal family is available in the authoritative `ml4t-data` canonical store, but NOT in the current approved Warden USD-M research contract. **No new Warden contract was activated and no Stage1 screen was attempted using these features.** This is source-data feasibility evidence, not a claim of alpha.

## Actual authority and records

Canonical repository: `/home/quant/dev/quant/ml4t-data`, [ML4T data repository authority](https://github.com/hzminhzz/ml4t-data). All observations below are read-only on the VPS, 2026-10-31. Existing dirty changes in that repo preserved.

| Dataset | Verified sample | Fields / state | Scientific value |
|---|---|---|---|
| `crypto_futures_ohlcv_1h_BINANCE_UM_PERP/symbol=BTCUSDT/year=2024/month=7/data.parquet` | **744 actual hourly rows**, 2024-07-01T00:00Z–2024-07-31T23:00Z; taker-buy nulls=0; taker-buy volume > total volume count=0 | `timestamp,symbol,open,high,low,close,volume,quote_volume,trade_count,taker_buy_base_volume,taker_buy_quote_volume` | **Actual past-bar aggressor-buy fraction** `taker_buy_base_volume/volume` at closed-hour decision, plus trade count/liquidity. 1-hour causal availability must still be validated and cost/slippage risk-matched |
| `crypto_futures_mark_price_1m_BINANCE_UM_PERP/symbol=BTCUSDT/year=2024/month=7/data.parquet` | **44,640 actual minute bars**, 2024-07-01T00:00Z–2024-07-31T23:59Z | `timestamp,symbol,open,high,low,close` mark-price OHLCV | Possible *last trade vs exchange **mark** price* dislocation signal. **Mark is NOT cash spot**; cannot claim verified spot–perp cash/futures arbitrage or cost-free convergence. Need causal sampling at completed hour plus observed venue price timestamps |
| `crypto_futures_open_interest_1m_HYPERLIQUID_BTC_PERP` | Directory includes **359 daily Parquet files**; docs describe OI event feed beginning **2025-09-29** | `timestamp,symbol,open_interest,updates`, from CHD worker; requires exact per-symbol dates and point-in-time close-asof | Not evidence on *Binance* OI. Post-2025-09 feed cannot be used inside the currently sealed 2024-07–2025-07 Warden validation without changing the approved market/horizon; and it overlaps the existing protected 2025–26 interval |
| Binance cash spot counterpart | **Not located** in a top-level-name search of canonical `.data/store` (search only; absence not proven across external providers) | No verified synchronized spot/last/mark basis pair | Direct spot-perp basis strategy remains **BLOCKED_DATA** until real PIT spot quotes/trades and synchronized perp prices are identified and qualified |

The existing Warden contract `AUTO_CRYPTO_PERPS_TOP100_1H_V1_H24_E24_F45_S20_V1` instead pins `quant-lab/data/exploratory/crypto_perps_top100_1h.parquet`. Its actual schema (previous native audits) contains `timestamp,asset,open,high,low,close,volume,funding_rate`, with **NO taker_buy volume, trade_count, quote_volume or mark_price**. It cannot be made capable by inventing columns, treating generic volume as signed trade pressure, changing the original sha, adding ad-hoc joins, or bypassing Warden's protected-contract approval.

## Specific genuinely independent next research thesis (proposal ONLY)

**Economic mechanism:** After an aggressive buy/sell imbalance when the traded Binance perp price deviates from the published Binance **mark price**, inventory-liquidity conditions may induce continued drift or a fast return toward the mark. The direction is an open hypothesis: do **not** fit sign, thresholds, windows or exits to reused Warden validation. This is **not** the rejected four-asset downside jump/volume rule; it uses two *new observed* inputs (signed taker flow fraction and mark-vs-last divergence) and must have a distinct economic estimand/counterparty.

**Original evidence to investigate:** Direct exchange kline field definitions from Binance official UM archived kline; original work on perp basis/volume (<https://www.research.ed.ac.uk/en/publications/anatomy-of-cryptocurrency-perpetual-futures-returns/>); distinct author selection history; potential conflicts with prior 2026-10-31 Gotodataru OOS post-selection taker-flow strategy. Third-party trading rules are untrusted; no new alpha assertion.

**Minimum activation gates:**
1. Inspect canonical `crypto_futures_ohlcv_1h_BINANCE_UM_PERP` and `crypto_futures_mark_price_1m_BINANCE_UM_PERP` provider/acceptance/catalog metadata, monthly continuity and quality for a **predeclared** instrument/period; validate market availability timestamp and bar close. These 2024-07 example summaries alone do not certify full multiyear history.
2. Define a **single source-faithful, bounded horizon** (<=24 hourly bars) with independently chosen rule parameters and sizing, specified before validation. Avoid source-side 108-cell/OOS selection from Gotodataru. Freeze universe using PIT listing and survivorship eligibility.
3. Prepare a **new, independently approved immutable Warden research contract and dataset manifest** with additional PIT columns, append-only search history and cost floors. Protect existing contract and historical rejection IDs. No fake "spot basis" field; mark price is mark price.
4. Use existing governance guard and exclusive writer, native verify/screen, and Stage3 only after legitimate Stage1 PASS. Warden crypto fees+slippage 6.5bps/side plus causal funding are an initial research floor, not proof of execution. Preserve remaining lifetime source budget **7/20** and all prior rejects.

**State:** `BLOCKED_PENDING_DATA_QUALITY_AND_CONTRACT_APPROVAL`. Only a data-readiness proposal; **0 new screens, 0 trials, 0 holdout reads** from this data review. The rejected B16 downside shock variant stays frozen.
