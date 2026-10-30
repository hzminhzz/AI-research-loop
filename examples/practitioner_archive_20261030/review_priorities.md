# Practitioner source review priorities — 30 October 2026

**Status:** 50 distinct source-backed *research leads*, not 50 preregistered or proven trading hypotheses. This list prioritizes practical compatibility with existing CFD and perpetual data. The original website is the authority for exact rules. All historical articles were captured today: current capture does NOT establish their text vintage in the 2024–2025 Warden validation interval.

| Order | Original source | Economic idea / proposed first experiment | Data and route | Main blocker |
| --- | --- | --- | --- | --- |
| 1 | [BTA — My Secret Gold Breakout Strategy](https://breakouttradingacademy.com/my-secret-gold-breakout-strategy/) | Long-only Monday and Thursday gold aftermarket, breakout above an ATR-based threshold. Investigate session-conditioned returns *before* adding the author's selected ATR settings. | Gold CFD, existing minute observations; require Chicago DST session conversion and an explicitly approved gold contract | The author reports selecting session/day/ATR parameters after exploration; source's 25-minute gold futures bars vs CFD minute resampling and spread need reconciliation |
| 2 | [BTA — Monday NASDAQ](https://breakouttradingacademy.com/steal-this-monday-nasdaq-strategy-super-simple/) | Monday-only short intraday breakout / Bollinger-ATR logic; extract full exact original rule and time-zone definitions first | Existing NQ/US100 index CFD minute data, new or reviewed session contract | Source-rule excerpt is **partial**; cannot register or fill parameter gaps from memory |
| 3 | [BTA — NASDAQ & S&P ratio breakout](https://breakouttradingacademy.com/nasdaq-sp-ratio-breakout-strategy-money-machine/) | Inter-market relative strength conditions breakouts on US100 vs US500 rather than using price levels alone | Joint index minute/5m observations with strictly synchronized times | Requires both underlying prices, consistent CFD scaling, time zone and source exit specifics |
| 4 | [QuantConnect — Dual Thrust](https://www.quantconnect.com/learning/articles/investment-strategy-library/dual-thrust-trading-algorithm) | Dynamic prior-range breakout keyed off session open, as a *new CFD adaptation* | US100 / US500 minute bars; session clock and next-bar execution | Original QuantConnect demonstration tests SPY equity, not a CFD; adaptation must be explicit and must not reuse claimed source performance |
| 5 | [Algomatic — Gold Stochastic Extremes](https://www.algomatictrading.com/post/a-mean-reversion-gold-system-using-stochastic-extremes) | Trend-filtered stochastic exhaustion, long/short, 2h bars with ATR sizing and trailing exits | XAUUSD minute → 2h causally resampled bars, gold contract | Full author code/parameters may be subscriber-only; claims PF 1.65 are not an independently verified alpha finding |
| 6 | [Finetiq — AVWAP/EMA flush](https://ideas.finetiqsystems.com/en/ideas/avwap-ema-flush/) | Anchored VWAP / EMA demand reaction and low-of-day invalidation | Intraday OHLCV with point-in-time anchor rules and volume validation | Source concept does not establish traded instrument/timeframe or exact anchor by itself |
| 7 | [BTA — Short opening-gap](https://breakouttradingacademy.com/how-to-build-a-short-opening-gap-strategy/) | Test whether opening overnight-gap direction predicts same-session returns | Index minute bars, next bar open and market-close alignment | Original instrument, gap reference and exit must be checked; multiple tested gap configurations inflate selection count |
| 8 | [Financial Hacker — Market Meanness Index](https://financial-hacker.com/the-market-meanness-index/) | Regime indicator as a filter, *not* a standalone tradable strategy | Broad price-history feature research, causal prefix checks | No independent entry/exit; do NOT register as alpha just because it has an index name |
| 9 | [cloudQuant Backtrader — EURUSD Breakout](https://github.com/cloudQuant/backtrader/blob/884ea41d5fb0079cd7744525f835f3fc3c2986b1/tests/functional/strategies/trend_following/test_0044_0575_eurusd_breakout.py) | Read regression-test source as a possible code-to-rule translation | FX majors minute/5m data | Test passing proves software consistency, not profitability. Never import publisher code directly |
| 10 | [Quantified Strategies](https://quantifiedstrategies.substack.com/) | Compare short-term gold/indices swing strategies and documented negative tests | Gold and indices where compatible | Its main site protected sitemap is unavailable; publisher's own feed is only a partial archive |

## Pilot evidence summary

- BTA original post sitemap: 521 indexed URLs, of which 137 match a broad keyword filter; 34 original articles sampled and successfully read.
- QuantConnect static library: 83 strategy cards, 29 article details reviewed. Cards contain first-party redirects to /research/... pages, which the collector validates and follows **one hop only**.
- Finetiq: 75 English /en/ideas/ URLs, 28 article details reviewed. The concept library includes incomplete/untested trading ideas; a cited concept is not a backtest.
- cloudQuant: 1,154 immutable test-file paths cataloged in a GitHub commit-pinned public tree; 10 metadata references reviewed. No third-party code executed.
- Quantified: 15 accessible original-publication Substack entries; protected main-site sitemap not bypassed.
- Algomatic: 59 blog sitemap URLs, 14 details reviewed.
- Financial Hacker: 64 actual **posts**, 12 reviewed. Earlier broad sitemap crawl incorrectly counted tags/taxonomy pages; these were removed from the index selection.
- **142 total article/code records reviewed, 50 deduplicated and curated leads, zero Warden trials consumed.**

## Scientific routing rules

The agent must obtain the original full article or pinned source text again before coding. Its proposal must include source URL and capture SHA, exact author-stated entry/exit, market and direction, session/timeframe, missing parameters, risk controls, and source parameter-search history. A source published after the validation interval does not confer independent out-of-sample evidence. Unsupported equity ETFs cannot be silently recast as index CFDs. Causal resampling, instrument contracts, realistic cost bounds, and native Warden preregistration precede any Stage 1 testing.

The public shortlist is a source-intake artifact. It does not override Warden's existing quarantines, scientific trial budgets, or sealed holdout controls.
