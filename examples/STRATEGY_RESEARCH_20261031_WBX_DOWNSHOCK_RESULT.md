# Independent-mechanism research — 2026-10-31 B16 result

**Scientific result: one genuinely new, source-inspired economic hypothesis was preregistered, causally verified and screened natively under Warden. Stage1 `REJECT`. No newly qualified strategy, Stage3 backtest, protected holdout read or live order.**

## Source and frozen protocol

- [Frozen original B16 preregistration](STRATEGY_RESEARCH_20261031_WBX_DOWNSHOCK.md), committed **`1c8a95a` BEFORE validation**, plus [structured native evidence](STRATEGY_RESEARCH_20261031_WBX_DOWNSHOCK_RESULT.json).
- Original motivating study: Wen/Bouri/Xu/Zhao (2022), [Intraday return predictability in the cryptocurrency markets: Momentum, reversal, or both?](https://doi.org/10.1016/j.najef.2022.101733). Studied crypto hourly/intraday momentum/reversal around jumps and liquidity, 2013–2020 BTC history. We **did not replicate** its historical strategy: four-hour next-open long-only Binance perpetual trade, 72-hour lagged volatility/volume, 1.5× downside shock, 1.5× volume spike, close in bottom 35% of range are our fixed, previously untested **adaptation**.
- Immutable publisher-bibliography capture [RePEc](https://ideas.repec.org/a/eee/ecofin/v62y2022ics1062940822000833.html) HTML SHA256 `c3cf332fb56ee98889343524f3842e6e0d0e8a38fd1c225518ccd3acd0550076`, captured 2026-10-31 07:55 UTC, original DOI included.
- Frozen four symbols BTCUSDT, ETHUSDT, LTCUSDT, XRPUSDT (all Binance USD-M perps); 25% notional each, gross<=1, no shorts, no position stacking. Warden next-open lag+1, per-side cost 4.5bps taker+2bps estimated slippage, **13bps round-trip** plus funding at modeled settlement.
- 2022 primary author history of parameter variants is unknown; included as limitation, with native Warden's existing crypto family search debt. This source describes jump- and liquidity-conditional reversal; liquidation is a **proxy hypothesis**, never measured directly in OHLCV.

## Exact native Warden evidence

| Check | Observed | Meaning |
|---|---:|---|
| Registration | `HYP-SOC-WBX-DOWNSHOCK-20261031` | New registered mechanism, no parent reset |
| Prefix verification | **PASS**, 87,552 hourly rows | 4 ×21,888 bars with approved pinned exploratory SHA |
| Stage1 attempt | **`ATT-31fddf3942a229ee-001`** | One native screening receipt |
| Profit factor | **1.059065** | **REJECT**, requires ≥1.15 |
| Gross conditional active-bar edge | +2.7175bps | Positive descriptive mean not enough net of trading costs |
| Native bootstrap p-value | 0.010 | Tests active **gross** return; NOT net executable alpha |
| Time in market | 25.925% | Clears ≥5% |
| Warden trade-edge proxy | 21.009bps | Clears 9.75bps one-way multiple, but does not override PF |
| `avg_holding_bars` | 7.731 | **Warden turnover-derived, scale-dependent proxy**, NOT actual holding; original deterministic target hold is exactly 4 hourly bars |
| **Native Stage1 verdict** | **REJECT** | Freeze no retune/rebrand/sibling |
| Native Stage3 runs | **0** | Rejected Stage1 is ineligible |

Durable screening service **`warden-screen-5292c81134b7a0629d`** reported process exit status1 because scientific Stage1 rejected; this is **expected native rejection**, not technical failure. The append-only Warden registry contains exactly one `STAGE_1_SIGNAL/REJECT` record for the candidate. First engineering-only Warden verify failed because a `FeaturePipeline.compute` interface was missing, then second durable attempt blocked under exclusive writer lock. I corrected the interface without changing source signal thresholds; the third **direct guarded** native verify after the lock cleared PASSED. No failed verification was misrepresented as a scientific attempt. Original strategy SHA256 `7d02e44a0c8ea3d706e2496baba366bc001c824be520864d6e157def4387a54e`, spec SHA256 `8b3e998cda7590e9696c2dc0bc165864e16939d76ee50398a358946da70e0129`.

**True economics:** Stage1 net PF 1.059 after modeled fees, slippage and funding is weak. The apparently significant gross active-bar mean does NOT establish economic profitability or survive unrecorded published research selection. Warden's simulated returns and costs cannot by themselves authorize prop-firm follower PnL. No Stage3 attempt will be spent chasing this frozen rejection.

### Warden snapshot

| Item | Before | After |
|---|---:|---:|
| Hypotheses | 148 | **149** |
| Full trials | 72 | **72** |
| Selection attempts | 183 | **184** |
| Native source screens | 12/20 | **13/20** |
| Remaining source screens | 8 | **7** |
| New complete scientific Stage3 qualifications | 0 | **0** |

Guards `READY_FOR_DISTINCT_RESEARCH`, `uv run warden check-worktree` PASS; focused synthetic tests **3 passed**, targeted Ruff PASS. Strategy and tests are currently **VPS-local untracked files in the existing dirty quant-lab checkout** and are NOT claimed as committed/deployed on its GitHub remote; exact paths/digests are in [JSON receipt](STRATEGY_RESEARCH_20261031_WBX_DOWNSHOCK_RESULT.json). The immutable preregistration and result are separately committed in AI-research-loop. Do not reset or discard unrelated dirty changes.

## Next independent economics, not retuning this failure

- **EXPERIMENT (requires new data approval): Spot–perp basis convergence / crowding.** Cao et al. (2024) [Anatomy of cryptocurrency perpetual futures returns](https://www.research.ed.ac.uk/en/publications/anatomy-of-cryptocurrency-perpetual-futures-returns/) shows basis and price/volume related factors explain perp returns. Stronger directly attributable carry and convergence mechanics than a price oscillator, but existing Warden crypto hourly OHLCV contains perp OHLCV/funding only. **True PIT spot and perp prices, quote/latency calibration and a separately approved contract are needed**. Do not fake the basis using funding values.
- **EXPERIMENT (requires actual liquidation events): Direct liquidation shock and inventory recovery.** [Lim's October 2025 market cascade evidence](https://papers.ssrn.com/sol3/Delivery.cfm/6579278.pdf?abstractid=6579278&mirid=1&type=2) documents 22× futures volume and mark/spot divergence during a specific October2025 crash. This is a 2026 retrospective *case study*, not a robust trading entry rule; the Warden pinned OHLCV has NO direct liquidation prints, mark/spot divergence or L2. Source data and counterfactual matching are needed before preregistering an independent executable model.
- **IGNORE on existing perp-only panel: High disagreement / turnover overpricing with short-sale constraints.** Garfinkel et al. (2025), [Disagreement and returns: The case of cryptocurrencies](https://doi.org/10.1111/fima.12491), finds next-day high abnormal turnover underperformance specifically when **short-sale constraints are binding**; effect dissipates when margin shorting becomes available. Binance USD-M perps permit short exposure, so simply transplanting this source signal to perp data would **contradict its own identified mechanism**, not source-fidelity verification. Could merit spot-only testing under historical shortability/PIT supply data with a new contract; **do not consume source budget** on this inconsistent transfer.
- **DEFER under hourly-only Warden source contract: intraday first-half-hour BTC volume momentum.** Shen, Urquhart, and Wang (2022), [Bitcoin intraday time-series momentum](https://research.birmingham.ac.uk/en/publications/bitcoin-intraday-time-series-momentum/), studies volume-defined first versus final half-hour trading sessions. It is not the same as 1h arbitrary volume-bar continuation. Need matching 30m/1m causally constructed bars, original author session convention, and protected contract; no post-hoc 1h timer substitution.

**Next action:** Prioritize source-quality data for *independent* perp-basis convergence or direct liquidation-shock recovery. Register the precise economic trade only after PIT data existence and author selection are verified; at most 7 source screens remain. Autonomous hourly sourcing stays enabled, without recycling this new rejected lineage.
