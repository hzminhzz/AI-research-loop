# OpenRouter autonomous research to Warden Stage 1 (29 October 2026)

**Verdict: E2E infrastructure passed; original fixed thesis rejected at Stage 1.**

The tool read the untracked local `.env` key without logging it; queried OpenAlex for historical crypto research abstracts and independently checked DOI publication dates using Crossref; pinned the current capture by SHA-256; called `poolside/laguna-s-2.1:free`; produced a Pydantic-validated `shock_reversal` thesis; registered it as `HYP-AIR-20261029-102247` in Warden; passed native causal verification on 105,024 pinned hourly market rows; and recorded exactly one Warden Stage 1 screen.

## Strategy and source provenance

Cited source titles and DOI links are in `result_summary.json` (abstract texts intentionally not mirrored to the public repository). The proposed strategy fades a >=2.5-sigma 1-hour return when volume is >=1.5x its 168-hour baseline, then targets a four-hour hold. The execution model is contract-owned: NEXT_BAR one-hour delay; taker 4bp + slippage 2bp per side, plus funding. The model did not write Python or choose thresholds.

The cited papers are evidence of research hypotheses, NOT proof of a transferable high-frequency reversal edge. OpenAlex was captured in October 2026; Crossref validates the publication date, not the historical source-text version. The 2025 validation window is exploratory, not an untouched production holdout.

## Warden result

| Gate | Actual | Required | Decision |
|---|---:|---:|---|
| Prefix-invariance | PASS | PASS | PASS |
| Profit factor | 0.7648 | >=1.15 | REJECT |
| Gross conditional edge per active hour | -3.91bp | Positive | REJECT |
| Bootstrap p | 0.975 | <0.05 | REJECT |
| Time in market | 23.78% | >=5% | PASS |

Warden registered `ATT-f331ab2845877aa0-001` (`STAGE_1_SIGNAL`, `REJECT`, verified_market). Full backtest trials: **0**. Protected holdout reads: **0**. No retuning or Stage 2+ execution was performed.

## Model routing and separate fallback verification

The actual Stage 1 run used **Laguna S 2.1** successfully (single primary-model attempt). The **North Mini Code** fallback was exercised separately against a real archived public-abstract task. Its ordinary text output repeatedly produced truncated JSON, so the adapter now requests a single structured `emit_json` function call (output only; no tool action executes). A live forced fallback probe then returned HTTP 200 and passed the full `ResearchProposal` Pydantic contract. Tests also cover a primary HTTP 429 activating fallback.

## Reproduction boundaries

The frozen original evidence lives only on the research VPS under `runs/autoresearch/AIR-OR-20261029-102247/`. The public repo contains source identifiers, DOI links, dates, hashes, model-authored thesis and Stage 1 metrics, but not the full potentially copyrighted abstracts or any API keys.

**Do not rerun Warden screen in the shared `quant-lab` registry merely to reproduce these values:** it would create a second scientific selection attempt. Use a fresh isolated registry/checkout for replay and preserve original dataset hash. The live run did not modify Warden governance or protected contracts; generated candidate/spec paths remain uncommitted in the already-dirty `quant-lab` checkout.

## Status

One-shot autonomous Stage 0 -> Stage 1 execution: **verified**. Neither a profitable strategy nor continuous large-scale multi-thesis discovery has been demonstrated. The current adapter has exactly two fixed template families; duplicate template attempts are now suppressed using Warden selection history.
