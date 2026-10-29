# Research-contract factory v0.6 — live qualification evidence

**Status:** First source-specific contract provisioned, Warden verification passed, Stage 1 rejected. This is **not yet full end-to-end self-coding agent automation**.

## New contract produced under explicit delegated approval

- ID: `AUTO_CRYPTO_PERPS_TOP100_1H_V1_H24_E24_F45_S20_V1`
- Owner: `/home/quant/dev/quant-lab/contracts/`; activated locally, not pushed into the divergent/dirty quant-lab Git branch.
- Parent: `CRYPTO_PERPS_TOP100_1H_V1`, unchanged.
- Dataset: `data/exploratory/crypto_perps_top100_1h.parquet`, digest `a7e13ed71f8ac09a11f98bdb6d711d93f91a4021105141a2070fd79696af99bc`.
- Changes: label horizon 4 → 24 hourly bars; embargo 2 → 24 bars; taker 4 → 4.5 bps/side, slippage remains 2 bps/side.
- Data source, original exploratory/validation/holdout split, execution delay and funding series remain pinned.
- Existing protected manifest entries checked without modification; two new hashes appended. Warden `check-worktree` passed.
- Approval basis: principal explicitly granted creation of new research data contracts in this conversation. Manifest is labeled delegated, **without independent HMAC signature**. Live orders and holdout unsealing remain prohibited.
- Five previous selection attempts were already registered on the same underlying dataset, and must count against eventual multiple-testing review; a new contract ID does **not** erase this history.

## Reproduced native test

- Source: [Delphic Alpha funding-level carry](https://delphicalpha.substack.com/p/strategy-crypto-funding-carry-makes), published October 26, 2026.
- Original source: 32 coins listed on Binance AND Hyperliquid, long low funding / short high funding, inverse 30-day volatility, daily rebalance.
- This experiment is explicitly a **Binance-only 88-coin inception-universe adaptation**, not an exact reproduction. Liquidity filter uses 60 previous daily observations and $5m median daily dollar volume.
- Hypothesis: `HYP-AUTO-FUNDING7D-BINANCE-20261030`.
- Strategy: `strategies/candidates/auto_funding_level_carry_7d_1d.py`.
- Attempt: `ATT-abe185af756c1b98-001` (REJECT, immutable Warden registry).
- Causal verifier: PASS on 1,926,144 rows.
- Rule smoke test: exact prefix invariance and finite, dollar-neutral 88-asset weights.

| Warden metric | Observed | Native requirement |
|---|---:|---:|
| Net profit factor | **1.13036** | **≥1.150** |
| Conditional gross edge | 0.457 bps per active hour | Positive and economically sufficient |
| Warden block-bootstrap p | Reported 0.000 (finite draws) | <0.05 |
| Time in market | 100% | ≥5% |
| Exploratory net return, Jul 2024–Jun 2025 | +48.60% | Not an approval criterion |
| Exploratory max drawdown | −4.62% | Not an approval criterion |

High hourly annualized Sharpe (~4.10) and favorable block-bootstrap results require especially skeptical investigation. Funding settlement timestamps, cross-venue universe membership, execution impact, prior trials and the source's publication *after* the validation period prevent any OOS qualification claim.

**Disposition:** `STAGE_1_REJECT`; no rerun with tuned parameters, no Warden full backtest, no holdout opening.

## Automation boundary

The v0.6 contract factory can **propose and, with explicit bounded delegation, activate** genuinely new versioned contracts from pre-pinned market snapshots. It validates source URL/date/hash, existing manifest integrity, split/horizon compatibility, fee floors, data origin, and prior selection count.

**Still missing:** auto-generating verified strategy code for arbitrary publisher rules, automated acquisition and PIT qualification of truly new data providers, and automatic Stage 2/3 orchestration after a Stage 1 pass. The existing source-polling campaign continues, but it does **not** yet invoke this factory for every discovered idea. These are real outstanding engineering tasks, not completed functionality.
