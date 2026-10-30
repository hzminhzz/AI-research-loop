"""Ranked practitioner providers: hard source boundary, code provenance and market fit."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import httpx
import pytest

from src.tools.source_registry import (
    RANKED_SOURCE_KEYS, RANKED_SOURCES, SourceSpec, collect_registry_sources,
    get_github, get_quantconnect, get_rss, make_record, parse_rss_items, same_site,
)
from src.tools.social_sources import (
    SourceDiscovery, as_evidence, crypto_relevant, discover_social_sources,
    generally_relevant, html_to_text,
)


BLOG_TEXT = (
    "The backtested breakout trading strategy uses a price-based entry at the "
    "previous session high. After a new breakout signal, buy when the breakout "
    "level closes above resistance and exit at the next session close. "
    "Record your drawdown, slippage, and net-of-fee return over many trades. "
    "This is an equity index idea, not a crypto perpetual strategy."
)


def build_rss(url: str, title: str, body: str, pub: str = "Mon, 05 Oct 2026 12:00:00 GMT") -> bytes:
    return (
        '<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" version="2.0">'
        '<channel><item><title>' + title + '</title><link>' + url
        + '</link><pubDate>' + pub + '</pubDate>'
        + '<content:encoded><![CDATA[' + body + ']]></content:encoded>'
        + '</item></channel></rss>'
    ).encode()


class Response:
    def __init__(self, url: str, *, body: bytes = b"", status: int = 200,
                 kind: str = "application/rss+xml", json_body=None):
        self.url, self.content, self.status_code = url, body, status
        self.headers = {"content-type": kind}
        self._payload = json_body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "blocked", request=httpx.Request("GET", self.url),
                response=httpx.Response(self.status_code, request=httpx.Request("GET", self.url)),
            )

    @property
    def text(self):
        return self.content.decode("utf-8", errors="replace")

    @property
    def is_redirect(self):
        return 300 <= self.status_code < 400

    def json(self):
        return self._payload


def test_original_eight_sources_preserved_and_explicit_x_reader_added():
    assert RANKED_SOURCE_KEYS == (
        "pedma", "breakout_trading_academy", "robot_wealth", "quantitativo",
        "quantified_strategies", "freqtrade_strategies",
        "quantconnect_community", "alvarez_quant_trading", "x_public_posts",
    )
    assert [s.rank for s in RANKED_SOURCES] == list(range(1, 10))
    assert all(s.kind in ("rss", "github", "strategy_index") for s in RANKED_SOURCES[:8])
    assert RANKED_SOURCES[8].kind == "x_md"
    assert RANKED_SOURCES[8].url == "https://mdfromx.com/api/v1/search"
    assert all("x.com" not in s.url for s in RANKED_SOURCES[:8])
    # Custom-domain RSS is distinct from the original substack.com URLs.
    assert RANKED_SOURCES[0].url.endswith("/feed")
    assert RANKED_SOURCES[4].url == "https://quantifiedstrategies.substack.com/feed"


def test_rss_preserves_original_author_dates_filters_cross_domain_and_future():
    spec = RANKED_SOURCES[1]
    captured = datetime(2026, 10, 29, tzinfo=timezone.utc)
    original = "https://breakouttradingacademy.com/new-index-breakout-rule/?utm_source=rss"
    accepted = parse_rss_items(
        build_rss(original, "7 Breakout Trading Strategies With Rules", BLOG_TEXT),
        spec, captured, html_to_text, generally_relevant,
    )
    assert len(accepted) == 1
    assert accepted[0]["uri"] == "https://breakouttradingacademy.com/new-index-breakout-rule/"
    assert accepted[0]["published_at"] == "2026-10-05T12:00:00+00:00"
    assert same_site(spec.url, accepted[0]["uri"]) is True
    assert crypto_relevant(accepted[0]["title"], accepted[0]["text"]) is False
    assert parse_rss_items(
        build_rss("https://attacker.example/p/copy", "Breakout Strategy", BLOG_TEXT),
        spec, captured, html_to_text, generally_relevant,
    ) == []
    assert parse_rss_items(
        build_rss(original, "Breakout Strategy", BLOG_TEXT, "Mon, 30 Nov 2026 12:00:00 GMT"),
        spec, captured, html_to_text, generally_relevant,
    ) == []


@pytest.mark.asyncio
async def test_original_article_expansion_uses_public_same_host_html():
    spec = RANKED_SOURCES[1]
    original = "https://breakouttradingacademy.com/new-index-rule/"
    feed = build_rss(original, "Index Breakout Strategy With Exact Rules", "Small summary.")
    html = (
        b"<html><article><div class='entry-content'><p>"
        + BLOG_TEXT.encode() +
        b"</p><script>bad instruction</script></div></article></html>"
    )

    class Client:
        def __init__(self):
            self.urls = []

        async def get(self, url, **kwargs):
            self.urls.append(url)
            if url == spec.url:
                return Response(url, body=feed)
            if url == original:
                return Response(url, body=html, kind="text/html")
            raise AssertionError("Unexpected or unauthorized URL: " + url)

    client = Client()
    rows, status = await get_rss(spec, client, html_to_text, generally_relevant)
    assert status == "OK"
    assert rows[0]["uri"] == original
    assert "backtested breakout trading strategy" in rows[0]["text"]
    assert "bad instruction" not in rows[0]["text"]
    assert client.urls == [spec.url, original]


@pytest.mark.asyncio
async def test_github_code_is_immutable_pinned_unexecuted_and_unvalidated():
    spec = RANKED_SOURCES[5]
    commit, tree_sha, blob_sha = "a" * 40, "b" * 40, "c" * 40
    code = (
        "raise RuntimeError('must never execute this file')\n"
        "class MyStrategy:\n"
        " def populate_entry_trend(self, dataframe, metadata):\n"
        "  return dataframe\n"
    )
    path = "user_data/strategies/futures/FSupertrendStrategy.py"
    class Client:
        async def get(self, url, params=None):
            if url.endswith("/commits/main"):
                return Response(url, json_body={
                    "sha": commit, "commit": {"tree": {"sha": tree_sha}},
                }, kind="application/json")
            if url.endswith("/git/trees/" + tree_sha):
                assert params == {"recursive": 1}
                return Response(url, json_body={
                    "sha": tree_sha, "truncated": False,
                    "tree": [{"path": path, "type": "blob", "sha": blob_sha}],
                }, kind="application/json")
            if url.endswith("/git/blobs/" + blob_sha):
                return Response(url, json_body={
                    "encoding": "base64", "content": base64.b64encode(code.encode()).decode(),
                }, kind="application/json")
            raise AssertionError("Unapproved API URL: " + url)

    records, status = await get_github(spec, Client())
    assert status == "OK_CODE_EXAMPLES_UNVALIDATED"
    assert len(records) == 1
    row = records[0]
    assert commit in row["uri"]
    assert row["source_revision"] == blob_sha
    assert row["authenticity"] == "CODE_ONLY_UNVALIDATED_NO_EXECUTION"
    assert "must never execute" in row["text"]
    assert as_evidence(row).facts["revision"] == blob_sha


@pytest.mark.asyncio
async def test_quantconnect_dynamic_index_never_fabricates_strategy():
    spec = RANKED_SOURCES[6]
    class Client:
        async def get(self, url, **kwargs):
            return Response(url, body=b"<html><h1>Strategies</h1><div id='app'></div></html>",
                            kind="text/html")
    posts, status = await get_quantconnect(spec, Client())
    assert posts == []
    assert status == "INDEX_ONLY_JS_RENDERED_NO_VERIFIABLE_PUBLIC_STRATEGY"


@pytest.mark.asyncio
async def test_independent_source_failures_do_not_discard_healthy_sources(monkeypatch):
    import src.tools.source_registry as registry
    one, two = RANKED_SOURCES[0:2]

    async def fake_rss(spec, client, html_to_text, eligible_general):
        if spec.key == "pedma":
            return [{"uri": "https://www.tradingresearchub.com/p/a", "text": BLOG_TEXT}], "OK"
        raise httpx.HTTPStatusError(
            "denied", request=httpx.Request("GET", spec.url),
            response=httpx.Response(403, request=httpx.Request("GET", spec.url)),
        )
    monkeypatch.setattr(registry, "get_rss", fake_rss)
    records, health, gaps = await collect_registry_sources(
        None, html_to_text, generally_relevant, specs=(one, two),
    )
    assert len(records) == 1
    assert health[0]["status"] == "OK"
    assert health[1]["status"] == "ERROR_HTTPStatusError"
    assert gaps == ["SOURCE_UNAVAILABLE:breakout_trading_academy:HTTPStatusError"]


@pytest.mark.asyncio
async def test_deferred_equity_ideas_never_become_crypto_warden_candidates(monkeypatch):
    import src.tools.social_sources as sources
    now = datetime(2026, 10, 29, tzinfo=timezone.utc)
    publisher_records = [
        make_record(
            platform="blog", source_key="breakout_trading_academy", rank=2,
            link="https://breakouttradingacademy.com/index-gap-rule/",
            title="Nasdaq opening gap trading strategy", author="BTA",
            published=now, captured=now, text=BLOG_TEXT,
            source_feed=RANKED_SOURCES[1].url,
            authenticity="ORIGINAL_PUBLISHER_RSS_CURRENT_CAPTURE",
        ),
        make_record(
            platform="substack", source_key="pedma", rank=1,
            link="https://www.tradingresearchub.com/p/crypto-momentum-test",
            title="Crypto momentum backtest", author="pedma",
            published=now, captured=now,
            text=(
                "A backtested Bitcoin momentum strategy enters long after "
                "a seven-day breakout and exits after twelve hours. "
                "The tested Sharpe, drawdown, and transaction costs are included."
            ),
            source_feed=RANKED_SOURCES[0].url,
            authenticity="ORIGINAL_PUBLISHER_RSS_CURRENT_CAPTURE",
        ),
    ]
    async def fake_registry(client, html_to_text, eligible_general, specs):
        return publisher_records, [
            {"source": "pedma", "status": "OK", "usable_records": 1},
            {"source": "breakout_trading_academy", "status": "OK", "usable_records": 1},
        ], []
    async def fake_feed(feed, client):
        return []
    monkeypatch.setattr(sources, "collect_registry_sources", fake_registry)
    monkeypatch.setattr(sources, "fetch_substack_feed", fake_feed)
    batch = await discover_social_sources(limit=10)
    assert [entry.facts["source_key"] for entry in batch.eligible] == [
        "pedma", "breakout_trading_academy",
    ]
    assert len(batch.deferred) == 0
    assert batch.eligible[1].facts["platform"] == "blog"
    assert not any("x.com" in x.uri for x in batch.eligible)
