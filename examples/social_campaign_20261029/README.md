# First continuous social-source campaign run — 2026-10-29

**Disposition: Warden Stage 1 REJECT.** One genuine market-data screen with causal feature verification. This is not a qualifying/profitable strategy.

The campaign sourced current public Substack RSS posts, routed to the primary `poolside/laguna-s-2.1:free` (invalid JSON) and then `cohere/north-mini-code:free` (valid structured proposal). The selected source was **Stoic Research & Technology**, [1.4 Cross-Sectional Momentum](https://stoicresearch.substack.com/p/14-cross-sectional-momentum), originally published 2026-06-16.

The model chose a pre-reviewed 7-day rank strategy on eight Binance perpetuals. Warden successfully ran causality verification on **105,024** real rows, then rejected the Stage 1 screen: **PF 0.9633; bootstrap p=0.72; conditional gross edge about −0.19 bp per active hour; time in market 100%**. Warden recorded one selection attempt (`ATT-7a57f17da1b3e44b-001`), zero full trials, zero holdout reads.

## Provenance and cadence limitation

**The tested adaptation was not a faithful replication of the author's rule.** The cited Stoic post specifies a roughly **21-day rebalance** on a 20-coin book; our fixed template ranked eight coins over 168 hours and rebalanced **daily**. This was a different experiment, not independent validation of Stoic's performance. The pipeline was subsequently tightened to reject such explicit source cadence mismatches before Stage 0 registration. The existing result/selection attempt was retained, not erased or reclassified as a valid source replication.

The post itself was written after the 2025 exploratory validation interval, so this is retrospective discovery, not prospective point-in-time validation. Do not infer that a passing social-sourced candidate is independently confirmed on untouched data.

The original full post excerpts and provider results remain under the locally ignored `runs/social_campaign/research/AIR-OR-20261029-111618/`, not republished in this repository. No API tokens or private input are included here.

## Campaign safeguards

Seven pre-reviewed strategy families, at most six model/source cycles per UTC day, 20 **distinct** Stage 1 screens per campaign, Warden's append-only selection history and protected holdout gate unchanged. Continues polling for new eligible social posts; stops on a Stage 1 pass or exhausted scientific budget. X first-party retrieval requires `X_BEARER_TOKEN`; this initial run was Substack-only, with `X_AUTH_REQUIRED` recorded.
