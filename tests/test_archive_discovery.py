"""Regression tests for original-publisher discovery without Warden access."""
from __future__ import annotations

import asyncio
from urllib.robotparser import RobotFileParser

import httpx
import pytest

from src.tools.archive_discovery import (
    ArchiveScout, SOURCES, Source, allowed, classify, interest,
    locs, rules,
)


def test_only_exact_original_https_source_hosts_and_safe_paths():
    source = SOURCES[1]
    good = ("https://www.quantconnect.com/learning/articles/"
            "investment-strategy-library/dual-thrust-trading-algorithm")
    assert allowed(good, source)
    for url in (
        good.replace("https:", "http:"),
        good.replace("www.quantconnect.com", "www.quantconnect.com.attacker.test"),
        good.replace("https://", "https://evil@"),
        good + "?next=https://example.test",
        good.replace(".com/", ".com:8443/"),
        "https://www.quantconnect.com/research/15268/dual-thrust",
    ):
        assert not allowed(url, source)


def test_strategy_interest_filters_educational_filler_but_keeps_specific_rules():
    assert interest("Dual Thrust Trading Algorithm", "/dual-thrust-trading-algorithm/")
    assert interest("Steal This Monday Nasdaq Strategy", "/steal-this-monday-nasdaq-strategy/")
    assert not interest("3 Reasons Why 99% Forex Traders Fail", "/3-reasons-why/")
    assert not interest("Best Crypto Trading Indicator", "/best-crypto-trading-indicator/")


def test_sitemap_index_recurses_only_into_first_party_post_children():
    xml = b"""<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap><loc>https://financial-hacker.com/wp-sitemap-posts-post-1.xml</loc></sitemap>
    <sitemap><loc>https://evil.example/unsafe.xml</loc></sitemap></sitemapindex>"""
    article = b"""<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://financial-hacker.com/market-meanness-index/</loc></url>
    <url><loc>https://evil.example/attack/</loc></url></urlset>"""
    def serve(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("post-1.xml"):
            return httpx.Response(200, content=article, headers={"content-type": "application/xml"})
        return httpx.Response(200, content=xml, headers={"content-type": "application/xml"})
    scout = ArchiveScout()
    src = SOURCES[-1]
    p = RobotFileParser()
    p.parse(["User-agent: *", "Allow: /"])
    scout.robots[src.key] = p

    async def test():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            return await scout.sitemap(client, src)
    assert [x["url"] for x in asyncio.run(test())] == [
        "https://financial-hacker.com/market-meanness-index/"
    ]


def test_quantconnect_onclick_cards_and_explicit_first_party_redirect_only():
    src = SOURCES[1]
    root = src.index
    canonical = root + "/dual-thrust-trading-algorithm"
    article_url = "https://www.quantconnect.com/research/15268/dual-thrust-trading-algorithm/"
    index_html = f"""<html><main>
    <div class="article" onclick="location.href='/learning/articles/investment-strategy-library/dual-thrust-trading-algorithm';">
    <h3>Dual Thrust Trading Algorithm</h3></div>
    <div class="article" onclick="location.href='https://attacker.test/steal';">
    <h3>Unsafe Strategy</h3></div></main></html>"""
    article_html = """<html><main><h1>Dual Thrust Trading Algorithm</h1>
    <p>This strategy uses the range of the previous several completed bars for intraday breakouts.</p>
    <p>Enter a long position when close crosses the breakout trigger above the prior high.</p>
    <p>Close the position at the end of the trading day or use a trailing stop.</p></main></html>"""
    calls = []
    def serve(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        if str(req.url) == root:
            return httpx.Response(200, text=index_html, headers={"content-type": "text/html"})
        if str(req.url) == canonical:
            return httpx.Response(302, headers={"location": article_url})
        if str(req.url) == article_url:
            return httpx.Response(200, text=article_html, headers={"content-type": "text/html"})
        raise AssertionError("Unexpected network URL " + str(req.url))
    scout = ArchiveScout()
    p = RobotFileParser()
    p.parse(["User-agent: *", "Allow: /"])
    scout.robots[src.key] = p

    async def test():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            links = await scout.html_index(client, src)
            details = await scout.article(client, src, links[0])
            return links, details
    links, record = asyncio.run(test())
    assert len(links) == 1 and links[0]["url"] == canonical
    assert record["source_key"] == "quantconnect_library"
    assert record["source_kind"] == "ORIGINAL_PUBLISHER_CURRENT_CAPTURE"
    assert article_url in calls and "attacker.test" not in " ".join(calls)
    assert record["experimental_disposition"] == "DISCOVERY_ONLY_NO_WARDEN_ATTEMPT"


def test_evil_publisher_redirect_is_never_followed():
    src = SOURCES[1]
    url = src.index + "/dual-thrust-trading-algorithm"
    def serve(req):
        return httpx.Response(302, headers={"location": "https://attacker.test/exfiltrate"})
    scout = ArchiveScout()
    p = RobotFileParser()
    p.parse(["User-agent: *", "Allow: /"])
    scout.robots[src.key] = p
    async def test():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            with pytest.raises(ValueError, match="Unapproved redirect"):
                await scout.get(client, url, src)
    asyncio.run(test())


def test_finetiq_robots_uppercase_agent_is_accepted():
    scout = ArchiveScout()
    source = SOURCES[2]
    def serve(req):
        return httpx.Response(200, text="User-Agent: *\nAllow: /\n", headers={"content-type": "text/plain"})
    async def test():
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            await scout.check_robots(client, source)
    asyncio.run(test())
    assert scout.can(source, "https://ideas.finetiqsystems.com/en/ideas/adr-stop-gate/")


def test_quote_extraction_never_creates_executable_stated_rules():
    phrases = [
        "Entry: buy if the completed bar closes above the 20-bar high.",
        "Exit at the session close, or stop loss at 1.5 ATR below entry.",
    ]
    found = rules("NASDAQ Breakout", phrases)
    assert found["entry_excerpt"] in phrases
    assert found["exit_excerpt"] in phrases
    assert found["rule_state"] == "RULES_VISIBLE_UNVERIFIED"
    assert found["exact_source_equivalence_verified"] is False
    assert rules("Generic Momentum", [])["rule_state"] == "TITLE_ONLY"


def test_code_sources_keep_hashes_and_are_never_executed():
    src = SOURCES[3]
    record = {
        "url": ("https://github.com/cloudQuant/backtrader/blob/" +
                "a" * 40 + "/tests/functional/strategies/trend_following/"
                "test_0001_sma_trend_following.py"),
        "index_title": "SMA Trend Following",
        "code_blob_sha": "b" * 40,
        "commit_sha": "a" * 40,
        "code_path": "tests/functional/strategies/trend_following/test_0001_sma_trend_following.py",
    }
    value = asyncio.run(ArchiveScout().article(None, src, record))
    assert value["content_sha256"] == "b" * 40
    assert value["source_revision"] == "a" * 40
    assert value["rule_state"] == "CODE_ONLY_UNREVIEWED"
    assert not value["entry_excerpt"]
