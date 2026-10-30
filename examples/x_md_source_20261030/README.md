# Public X strategy source via x.md — live verification

**Date:** 2026-10-30 UTC. **Scope:** user-approved return of public X posts after a previous request to remove direct X integration. Read-only research intake, no broker/trading authority.

## API methods

- [x.md posts documentation](https://mdfromx.com/docs/posts): `GET https://mdfromx.com/api/v1/posts?handle=...&id=...&thread=off&replies=off&full=true&format=json`.
- [x.md search documentation](https://mdfromx.com/docs/search): `GET https://mdfromx.com/api/v1/search?q=...&feed=top&limit=8&format=json`.
- No direct X API key or X login. This is a third-party public-data reader, NOT the official X API, not a guaranteed full historical feed.
- Search bounded at two predefined queries per scan and eight preview rows each; at most four follow-up verified public status reads. Zero pagination or rate-limit bypass.
- Validates every original x.com status URL, original author handle, status ID, claimed publication timestamp and source envelope; rejects warnings, redirects and degraded search snippets. Never fetches embedded external links or runs publisher code.

## Live source smoke

`python -m src.tools.x_md --url https://x.com/trq212/status/2052809885763747935`
successfully extracted a public, long-form article with author, original URL, source timestamp and 6,500 characters of capped text.

`python -m src.tools.x_md --scan` returned `OK_PUBLIC_X_POST_LEADS_UNVERIFIED` with one source-attributed research lead:

- Original post: https://x.com/QuantAlphaXXX/status/2109422015572545729
- Account: `@QuantAlphaXXX`
- Published: `2026-10-11T23:12:54+00:00`
- Topic: NASDAQ 15-minute opening-range breakout with long/short threshold conditions; describes retrospective research over 5.5 years. Exact original fill timing, exit and session filters must still be reviewed. This is NOT a Warden Stage 1 screen and does NOT establish alpha.

## Distinct scientific tiers

1. A public X source can be captured from a strictly validated status permalink without claiming it specifies a complete strategy.
2. Incomplete X posts are **deferred** as `X_POST_NEEDS_SOURCE_RULE_FIDELITY_REVIEW`.
3. Only original posts containing independently attributed, numerical entry AND exit rules can become *eligible for further source matching*. The existing Warden source-rule equivalence gate, market contracts and selection-history accounting still decide whether an experiment is possible.
4. X article/posts observed in October 2026 are retrospective discovery against any 2024–2025 evaluation window: their current text cannot be treated as point-in-time vintage evidence.
5. Source retrieval never registers a Warden hypothesis, screens a signal, touches holdouts or places an order.

## End-to-end collector smoke

The complete read-only `python -m src.social_campaign --sources-only` run returned
`SOURCE_DISCOVERY_ONLY`, including source #9 `x_public_posts` with status
`OK_PUBLIC_X_POST_LEADS_UNVERIFIED` and **four verified public X posts**.
The catalog places **one** post in the market-compatible preliminary source
queue and **three** posts in `X_POST_NEEDS_SOURCE_RULE_FIDELITY_REVIEW`;
zero Warden screens or full backtests were submitted. This is not a source-rule
fidelity pass or statistical validation.

The unrelated Freqtrade GitHub API experienced a transient
`ERROR_HTTPStatusError` and QuantConnect's older JS-only community index
remained unavailable; neither prevented the new public X source from being
captured. Other RSS/blog sources remained reachable.

## Integration

`x_public_posts` is source #9, after the original eight ranked practitioner sources. The original X bearer-token adapter remains removed. The existing 30-minute source campaign scans x.md automatically; its `--sources-only` command is the safe full-health test and the hourly Research Director also receives this source.

Production limitations: x.md is a free best-effort upstream aggregation service; public search can be stale, incomplete, degraded or rate limited. Logs and source health must preserve failure rather than fabricate posts or circumvent public access controls.
