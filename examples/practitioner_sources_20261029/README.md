# Ranked practitioner strategy source registry — 29 October 2026

**Status:** All eight user-requested sources are configured; seven expose accessible original public posts or code from the current VPS environment. QuantConnect's public strategy listing is JS-populated and supplied no verifiable individual strategy rules to a normal read-only HTTP request; its source health is reported rather than fabricated.

| Priority | Original source | Public records | Pipeline |
| --- | --- | ---: | --- |
| 1 | Trading Research Hub / pedma | 3 | Custom-domain RSS → crypto research |
| 2 | Breakout Trading Academy | 3 | WordPress RSS + original article content → deferred index ideas |
| 3 | Robot Wealth | 2 | WordPress RSS + original article content → strategy inbox |
| 4 | Quantitativo | 6 | Custom-domain RSS → relevant ideas retained |
| 5 | Quantified Strategies | 17 | Official Substack RSS fallback; main-site automated RSS blocked |
| 6 | Freqtrade Strategies GitHub | 6 | SHA-pinned code, no execution → deferred until exact rule mapping |
| 7 | QuantConnect Community Strategies | 0 | Official public page monitored; no machine-readable individual strategy details |
| 8 | Alvarez Quant Trading | 4 | WordPress RSS + public article content → deferred equity/ETF ideas |

Additional previously configured independent Substack feeds remain enabled. Source-only scan: **9 eligible crypto posts, 39 deferred**, no Warden screens or LLM calls. Each source reports a separate fetch status and reason. The current source catalog lives at `runs/social_campaign/source_catalog.json` on the VPS.

**X.com removed from active ingestion**: the pipeline no longer requests its API, reads an X credential, or records an X auth-required gap. Historical 2026-10-29 experiment records mentioning the old source policy are kept immutable.

## One live E2E and scientific correction

Run `AIR-OR-20261029-114744` selected the reviewed `donchian_trend` template after referencing the public Freqtrade `TrendRiderStrategy` code. Warden's causal verification passed and Stage 1 rejected the rule (profit factor 1.0130, bootstrap p-value 0.36). The Warden selection attempt remains in the registry, with **zero full backtest trials and no protected holdout access**.

Review showed the original cited Freqtrade example uses a spot-safe, long-only mixture of pullback/EMA/RSI/BB/MACD entries, **not** a long-short 240-hour Donchian breakout. This was a scientific source-to-rule mismatch, not a faithful code replication. The negative trial is preserved. The corrected collector now classifies code-only examples as `CODE_ONLY_REQUIRES_FROZEN_RULE_MAPPING` and prohibits Warden Stage 1 registration from an unmapped code citation. The code is available as an idea source but cannot automatically authorize an unrelated template.

## Constraints

The active Warden contract covers eight Binance USDT perpetuals on 1h data. Index, equity, ETF, and unsupported data/timeframe articles are archived in the deferred source catalog and require separately registered dataset and strategy contracts. No direct trading, parameter tuning, holdout unseal or unsupported third-party mirror crawling is introduced.

The documented publication date is **not proof of historical text vintage**; current captures and code revisions are hashed. Source-author backtest metrics are unverified claims until independently reproduced. A Stage 1 pass stops discovery but does not equal independently validated or deployable alpha.
