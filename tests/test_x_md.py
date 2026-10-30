"""Public X strategy sources via mdfromx, with hostile provider boundaries."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import parse_qs

import httpx
import pytest

from src.tools.source_registry import RANKED_SOURCES, collect_registry_sources
from src.tools.social_sources import as_evidence, crypto_relevant, generally_relevant
from src.tools.x_md import (
    MAX_SEARCH_RESULTS, MAX_VERIFIED_POSTS_PER_SCAN, POSTS_ENDPOINT,
    SEARCH_ENDPOINT, SOURCE_KEY, SEARCH_QUERIES, collect_x_posts,
    fetch_x_post, original_url, parse_permalink, parse_verified_post,
)

POST_ID = "2115820000000000000"
POST_URL = f"https://x.com/rulequant/status/{POST_ID}"
STRATEGY = (
    "Bitcoin perpetual breakout strategy backtest: enter long when BTC closes "
    "above the prior 24-hour high, exit after 12 hours or stop at 1.5 ATR "
    "below entry. Rebalance once a day and report fees, slippage, Sharpe, "
    "drawdown, and live execution limitations."
)
CAPTURED = datetime(2026, 10, 30, tzinfo=timezone.utc)


def x_post(*, text=STRATEGY, author="rulequant", post_id=POST_ID,
           url=POST_URL, date="Thu Oct 29 14:30:33 +0000 2026"):
    return {
        "id": post_id, "url": url, "text": text,
        "created_at": date,
        "author": {"screen_name": author},
        "created_timestamp": 1793284233,
    }


def envelope(*, post=None, url=POST_URL, warnings=None):
    return {
        "format": "json", "url": url, "posts": [post or x_post()],
        "warnings": [] if warnings is None else warnings,
        "source": "fxtwitter", "markdown": "",
    }


def test_exact_public_status_url_only():
    assert parse_permalink(POST_URL) == ("rulequant", POST_ID)
    assert parse_permalink(f"https://twitter.com/rulequant/status/{POST_ID}") == (
        "rulequant", POST_ID)
    for url in (
        f"http://x.com/rulequant/status/{POST_ID}",
        f"https://x.com.evil.invalid/rulequant/status/{POST_ID}",
        f"https://x.com:8443/rulequant/status/{POST_ID}",
        f"https://evil@x.com/rulequant/status/{POST_ID}",
        f"https://x.com/rulequant/status/{POST_ID}?next=evil",
        f"https://x.com/rulequant/status/{POST_ID}/photo/1",
        "https://x.com/rulequant",
        "https://x.com/rulequant/status/abc",
        f"https://mdfromx.com/rulequant/status/{POST_ID}",
        f"https://x.com/rulequant/status/{POST_ID}#context",
    ):
        with pytest.raises(ValueError):
            parse_permalink(url)


def test_verified_post_provenance_and_current_capture_not_historical_pit():
    row = parse_verified_post(envelope(), POST_URL, CAPTURED,
                              eligible_general=generally_relevant)
    assert row["uri"] == POST_URL
    assert row["published_at"] == "2026-10-29T14:30:33+00:00"
    assert row["captured_at"] == CAPTURED.isoformat()
    assert row["author"] == "@rulequant"
    assert row["platform"] == "x_md"
    assert row["source_key"] == SOURCE_KEY
    assert row["authenticity"] == "PUBLIC_X_POST_THIRD_PARTY_CURRENT_CAPTURE"
    assert row["source_feed"] == POSTS_ENDPOINT
    assert row["source_revision"] == POST_ID
    assert row["x_rule_candidate"] is True
    assert "exit after 12 hours" in row["text"]
    assert crypto_relevant(row["title"], row["text"])
    evidence = as_evidence(row)
    assert evidence.uri == POST_URL
    assert evidence.available_at == CAPTURED
    assert evidence.facts["source_authenticity"] == row["authenticity"]
    assert "historical text vintage unverified" in evidence.facts["provenance"].lower()


@pytest.mark.parametrize("bad", [
    {"warnings": ["upstream incomplete"]},
    {"post": x_post(author="other")},
    {"post": x_post(post_id="2115820000000000001")},
    {"post": x_post(url="https://x.com/rulequant/status/2115820000000000002")},
    {"url": "https://x.com/rulequant/status/2115820000000000002"},
    {"post": x_post(date="Fri Nov 27 14:30:33 +0000 2026")},
    {"post": {**x_post(), "created_timestamp": 42}},
])
def test_inconsistent_or_warned_provider_data_fails_closed(bad):
    data = envelope()
    if "post" in bad:
        data["posts"] = [bad["post"]]
    data.update({k: v for k, v in bad.items() if k != "post"})
    with pytest.raises(ValueError):
        parse_verified_post(data, POST_URL, CAPTURED)


def test_missing_text_or_promotional_only_post_not_accepted():
    with pytest.raises(ValueError):
        parse_verified_post(envelope(post=x_post(text="Trade with my app")), POST_URL, CAPTURED)
    with pytest.raises(ValueError):
        parse_verified_post(
            envelope(post=x_post(text="Join my awesome tool, sell more courses now "
                                         "and never learn how to trade by rules or backtest.")),
            POST_URL, CAPTURED, eligible_general=generally_relevant,
        )


@pytest.mark.asyncio
async def test_post_reader_only_calls_documented_fixed_api_and_blocks_redirects():
    requests = []

    def serve(req: httpx.Request):
        requests.append((str(req.url), dict(req.url.params)))
        if req.url.path == "/api/v1/posts":
            assert set(req.url.params) == {
                "handle", "id", "thread", "replies", "full", "format",
            }
            assert req.url.params["handle"] == "rulequant"
            assert req.url.params["id"] == POST_ID
            assert req.url.params["thread"] == "off"
            assert req.url.params["replies"] == "off"
            return httpx.Response(
                200, json=envelope(), headers={"content-type": "application/json"})
        raise AssertionError("Attempt to follow an untrusted URL")

    async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
        row = await fetch_x_post(POST_URL, client, eligible_general=generally_relevant)
    assert row["uri"] == POST_URL
    assert len(requests) == 1
    assert requests[0][0].startswith(POSTS_ENDPOINT + "?")

    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(
            302, headers={"location": "https://attacker.invalid"}))) as client:
        with pytest.raises((httpx.HTTPError, ValueError)):
            await fetch_x_post(POST_URL, client)


@pytest.mark.asyncio
async def test_search_is_two_queries_and_verifies_exact_eligible_post_once():
    queried = []
    post_calls = []

    def serve(req: httpx.Request):
        if req.url.path.endswith("/search"):
            queried.append(dict(req.url.params))
            assert req.url.params["limit"] == str(MAX_SEARCH_RESULTS)
            assert req.url.params["feed"] == "top"
            # Same status appears twice: must be deduped before post reads.
            return httpx.Response(200, json={
                "resource": "search", "query": req.url.params["q"],
                "posts": [
                    x_post(),
                    x_post(post_id="2115820000000000001",
                           url="https://x.com/rulequant/status/2115820000000000001",
                           text="Use my trading bot now!"),
                ],
            }, headers={"content-type": "application/json"})
        if req.url.path.endswith("/posts"):
            post_calls.append(dict(req.url.params))
            return httpx.Response(200, json=envelope(),
                                  headers={"content-type": "application/json"})
        raise AssertionError("Unexpected request " + str(req.url))

    async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
        records, status = await collect_x_posts(client, generally_relevant)
    assert len(queried) == len(SEARCH_QUERIES) == 2
    assert len(post_calls) == 1 <= MAX_VERIFIED_POSTS_PER_SCAN
    assert len(records) == 1 and records[0]["uri"] == POST_URL
    assert status == "OK_PUBLIC_X_POST_LEADS_UNVERIFIED"


@pytest.mark.asyncio
async def test_degraded_search_and_rate_limit_dont_fabricate_ideas():
    async def probe(resp: httpx.Response):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: resp)) as c:
            return await collect_registry_sources(
                c, lambda s: s, generally_relevant, specs=(RANKED_SOURCES[-1],),
            )
    _, health, gaps = await probe(httpx.Response(
        200, json={"posts": [x_post()]},
        headers={"content-type": "application/json", "X-Search-Degraded": "true"}))
    assert health[0]["status"] == "ERROR_ValueError"
    assert gaps == ["SOURCE_UNAVAILABLE:x_public_posts:ValueError"]

    _, health, gaps = await probe(httpx.Response(
        429, json={"error": "rate_limited"},
        headers={"content-type": "application/json"}))
    assert health[0]["status"] == "ERROR_HTTPStatusError"
    assert "HTTPStatusError" in gaps[0]


@pytest.mark.asyncio
async def test_index_source_yields_health_even_with_no_verified_rule_posts():
    calls = 0
    def serve(req: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"posts": [], "source": "xsearch"},
                              headers={"content-type": "application/json"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
        rows, health, gaps = await collect_registry_sources(
            client, lambda s: s, generally_relevant, specs=(RANKED_SOURCES[-1],),
        )
    assert calls == 2
    assert rows == []
    assert health[0]["source"] == "x_public_posts"
    assert health[0]["status"] == "NO_VERIFIED_X_RULE_POSTS"
    assert gaps[0].startswith("SOURCE_LIMITED:x_public_posts:")


@pytest.mark.asyncio
async def test_x_posts_enter_warden_source_queue_only_with_complete_rules(monkeypatch):
    import src.tools.social_sources as social

    partial = parse_verified_post(envelope(post=x_post(text=(
        "I analyzed the NASDAQ opening range breakout across five years "
        "and tested thousands of CCI filters. The range is 9:30 to 9:45 "
        "Eastern time; here is a detailed discussion of the results "
        "and why selection bias can be a problem for quantitative traders."
    ))), POST_URL, CAPTURED)
    assert partial["x_rule_candidate"] is False
    complete = parse_verified_post(
        envelope(post=x_post(
            author="rulequant2", post_id="2115820000000000001",
            url="https://x.com/rulequant2/status/2115820000000000001",
        ), url="https://x.com/rulequant2/status/2115820000000000001"),
        "https://x.com/rulequant2/status/2115820000000000001",
        CAPTURED, eligible_general=generally_relevant,
    )
    assert complete["x_rule_candidate"] is True

    async def fake_registry(client, html_to_text, eligible_general, specs):
        return [partial, complete], [
            {"source": "x_public_posts", "status": "OK_PUBLIC_X_POST_LEADS_UNVERIFIED",
             "usable_records": 2}
        ], []

    async def fake_feed(feed, client):
        return []

    monkeypatch.setattr(social, "collect_registry_sources", fake_registry)
    monkeypatch.setattr(social, "fetch_substack_feed", fake_feed)
    batch = await social.discover_social_sources(limit=10)
    assert [record.uri for record in batch.eligible] == [
        "https://x.com/rulequant2/status/2115820000000000001"
    ]
    assert batch.eligible[0].facts["rule_support_candidate"] == "True"
    assert batch.eligible[0].facts["source_authenticity"].startswith(
        "PUBLIC_X_POST_THIRD_PARTY")
    assert any(x["url"] == POST_URL and
               x["reason"] == "X_POST_NEEDS_SOURCE_RULE_FIDELITY_REVIEW"
               for x in batch.deferred)
