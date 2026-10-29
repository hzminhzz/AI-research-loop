"""Practitioner sources: original URLs, timestamps, no social-media auth."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest

from src.tools.social_sources import (
    _utc_pubdate, as_evidence, discover_social_sources,
    eligible_post, parse_substack_feed,
)

FEED = "https://example.substack.com/feed"
RULE_TEXT = (
    "We backtested this crypto strategy across multiple years. "
    "The entry is after a 12% drawdown from the previous seven-day high. "
    "Exit after four hours; the backtest includes transaction costs and "
    "slippage. We tested 120 trades and compare the net return, Sharpe ratio "
    "and maximum drawdown. These are not signals or a guaranteed profit."
)


def make_feed(title: str, body: str, url: str = "https://example.substack.com/p/a") -> bytes:
    return (
        '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">'
        "<channel><item>"
        f"<title>{title}</title><link>{url}</link>"
        "<pubDate>Mon, 05 Oct 2026 12:00:00 GMT</pubDate>"
        f"<content:encoded><![CDATA[{body}]]></content:encoded>"
        "</item></channel></rss>"
    ).encode()


def test_substack_rss_yields_timestamped_original_post():
    captured = datetime(2026, 10, 29, tzinfo=timezone.utc)
    docs = parse_substack_feed(
        make_feed("Bitcoin buy-the-dip backtest", f"<p>{RULE_TEXT}</p>"), FEED, captured
    )
    assert len(docs) == 1
    post = docs[0]
    assert post["uri"].startswith("https://example.substack.com/p/")
    evidence = as_evidence(post)
    assert evidence.published_at < evidence.available_at
    assert evidence.archived_at == evidence.available_at
    assert evidence.source_version and evidence.source_id.startswith("social_substack_")
    assert evidence.facts["platform"] == "substack"
    assert "12%" in evidence.snippet
    assert evidence.provider == "substack_current_public_capture"


def test_paper_summary_and_third_party_link_excluded():
    captured = datetime(2026, 10, 29, tzinfo=timezone.utc)
    assert parse_substack_feed(
        make_feed("New paper: Crypto momentum", RULE_TEXT), FEED, captured
    ) == []
    assert parse_substack_feed(
        make_feed("Bitcoin RSI strategy", RULE_TEXT, "http://internal/secret"), FEED, captured
    ) == []
    assert parse_substack_feed(
        make_feed("Bitcoin RSI strategy", RULE_TEXT, "https://other.com/p/stolen"), FEED, captured
    ) == []


def test_future_and_naive_pub_dates_rejected():
    assert parse_substack_feed(
        make_feed("Bitcoin strategy", RULE_TEXT).replace(
            b"05 Oct 2026", b"30 Nov 2026"
        ), FEED, datetime(2026, 10, 29, tzinfo=timezone.utc)
    ) == []
    with pytest.raises(ValueError):
        _utc_pubdate("2026-10-29T10:00:00")


@pytest.mark.asyncio
async def test_custom_substack_feed_discovery_without_other_providers(monkeypatch):
    import src.tools.social_sources as sources
    async def fake_feed(url, client):
        return parse_substack_feed(make_feed("Bitcoin strategy backtest", RULE_TEXT),
                                   FEED, datetime(2026, 10, 29, tzinfo=timezone.utc))
    monkeypatch.setattr(sources, "fetch_substack_feed", fake_feed)
    result = await discover_social_sources(feeds=(FEED,), limit=10)
    rows, metadata, gaps = result
    assert len(rows) == len(metadata) == 1
    assert gaps == []
    assert result.health[0]["status"] == "OK"
    assert result.deferred == []
