"""Public X/Substack strategy-post capture. No papers, mirrors or unverified snippets.

Substack: public RSS feed, with original post URL and RFC822 publication timestamp.
X: authenticated official v2 recent search only; no bearer => explicit source gap.
All content is untrusted DATA; current capture is not historical article-vintage proof.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from src.core.models import Evidence, EvidenceKind

# Curated original practitioner feeds; updates require code review, not model changes.
DEFAULT_FEEDS = (
    "https://delphicalpha.substack.com/feed",
    "https://empiricalab.substack.com/feed",
    "https://quantifiedstrategies.substack.com/feed",
    "https://backtest.substack.com/feed",
    "https://stoicresearch.substack.com/feed",
    "https://gurufinanceinsights.substack.com/feed",
)
X_SEARCH = (
    '(crypto OR bitcoin OR altcoin OR perpetual) '
    '("backtested" OR "trading strategy" OR "tested my") lang:en -is:retweet'
)
MAX_FEED_BYTES = 2_500_000
MAX_POST_CHARS = 2800
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"
STRATEGY_TERMS = (
    "backtest", "strategy", "trading rule", "momentum", "mean reversion",
    "reversal", "breakout", "trend following", "buy the dip", "funding",
    "RSI", "donchian", "signal", "tested", "short-term", "systematic",
)
PAPER_ONLY_TERMS = ("review of the paper", "new paper", "arxiv", "research paper summary")
NON_STRATEGY_TITLES = ("start here", "what is a trading strategy", "app store", "random signals",
                       "welcome", "about this newsletter", "my process")
RULE_TERMS = ("entry", "exit", "long", "short", "lookback", "threshold", "trades", "backtest",
              "risk", "return", "sharpe", "hold", "signal", "rsi", "hours", "bars", "moving average")
CRYPTO_TERMS = ("crypto", "bitcoin", "btc", "altcoin", "perpetual", "binance", "ethereum", "ethusd")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.ignore += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.ignore = max(0, self.ignore - 1)

    def handle_data(self, data):
        if not self.ignore:
            self.parts.append(data)


def html_to_text(raw: str) -> str:
    parser = _Text()
    parser.feed(raw[:35_000])
    return re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()


def _utc_pubdate(value: str) -> datetime:
    date = parsedate_to_datetime(value)
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError("RSS publication timestamp has no timezone")
    return date.astimezone(timezone.utc)


def eligible_post(title: str, body: str) -> bool:
    summary = (title + " " + body[:1600]).lower()
    title_lower = title.lower()
    if any(term in title_lower for term in PAPER_ONLY_TERMS + NON_STRATEGY_TITLES):
        return False
    # The pinned Warden contract contains only Binance crypto perpetuals.
    # Do not map an isolated equity/ETF rule onto crypto without any source support.
    if not any(term in (title_lower + " " + body[:900].lower()) for term in CRYPTO_TERMS):
        return False
    if not any(word.lower() in summary for word in STRATEGY_TERMS):
        return False
    return sum(t in summary for t in RULE_TERMS) >= 3 and len(body) >= 120


def _valid_substack_link(feed_url: str, link: str) -> bool:
    original = urlparse(feed_url)
    candidate = urlparse(link)
    return (
        candidate.scheme == "https"
        and candidate.hostname is not None
        and (
            candidate.hostname == original.hostname
            or candidate.hostname == "substack.com"
        )
        and (candidate.path.startswith("/p/") or "/note/" in candidate.path)
    )


def parse_substack_feed(xml_bytes: bytes, feed_url: str, captured_at: datetime) -> list[dict]:
    hostname = urlparse(feed_url).hostname
    if not hostname or not hostname.endswith(".substack.com"):
        raise ValueError("feed host not allowlisted")
    if len(xml_bytes) > MAX_FEED_BYTES:
        raise ValueError("Substack feed exceeded size cap")
    root = ET.fromstring(xml_bytes)
    records = []
    for item in root.findall("./channel/item"):
        link = (item.findtext("link") or "").strip().split("?")[0]
        if not _valid_substack_link(feed_url, link):
            continue
        title = (item.findtext("title") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        raw = item.findtext(f"{CONTENT_NS}encoded") or item.findtext("description") or ""
        try:
            published = _utc_pubdate(pub)
        except (ValueError, TypeError, OverflowError):
            continue
        if published > captured_at:
            continue
        content = html_to_text(raw)
        if not eligible_post(title, content):
            continue
        author = (item.findtext("{http://purl.org/dc/elements/1.1/}creator") or hostname)
        record = {
            "platform": "substack", "post_id": hashlib.sha256(link.encode()).hexdigest()[:24],
            "uri": link, "title": title[:250], "author": author[:100],
            "published_at": published.isoformat(), "captured_at": captured_at.isoformat(),
            "text": content[:MAX_POST_CHARS],
            "source_feed": feed_url,
        }
        records.append(record)
    return records


async def fetch_substack_feed(feed_url: str, client: httpx.AsyncClient) -> list[dict]:
    host = urlparse(feed_url)
    if host.scheme != "https" or not (host.hostname or "").endswith(".substack.com"):
        raise ValueError("Substack feed must be a curated HTTPS substack.com publication")
    if host.path != "/feed":
        raise ValueError("Substack URL must end in /feed")
    response = await client.get(
        feed_url, follow_redirects=False,
        headers={"User-Agent": "AI-quant-research-loop/0.3 (public strategy RSS research)"},
    )
    response.raise_for_status()
    if response.is_redirect:
        raise ValueError("Substack feed redirect not allowlisted")
    captured = datetime.now(timezone.utc)
    return parse_substack_feed(response.content, feed_url, captured)


async def fetch_x_posts(client: httpx.AsyncClient, bearer: str | None) -> list[dict]:
    if not bearer:
        return []
    response = await client.get(
        "https://api.x.com/2/tweets/search/recent",
        params={
            "query": X_SEARCH, "max_results": 20,
            "tweet.fields": "created_at,author_id,lang",
            "expansions": "author_id", "user.fields": "username,name",
        },
        headers={"Authorization": f"Bearer {bearer}"},
    )
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise ValueError("X returned partial errors; reject batch")
    users = {u["id"]: u for u in body.get("includes", {}).get("users", [])}
    captured = datetime.now(timezone.utc)
    rows = []
    for item in body.get("data", []):
        try:
            published = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
            account = users[item["author_id"]]["username"]
            post_id = item["id"]
            msg = item["text"].strip()
        except (KeyError, ValueError, TypeError):
            continue
        if published > captured or not eligible_post(msg[:110], msg):
            continue
        rows.append({
            "platform": "x", "post_id": str(post_id),
            "uri": f"https://x.com/{account}/status/{post_id}",
            "title": msg[:110], "author": account,
            "published_at": published.astimezone(timezone.utc).isoformat(),
            "captured_at": captured.isoformat(), "text": msg[:MAX_POST_CHARS],
            "source_feed": "official_x_recent_search",
        })
    return rows


def as_evidence(record: dict) -> Evidence:
    text_hash = hashlib.sha256(
        json.dumps(record, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return Evidence(
        source_id=f"social_{record['platform']}_{record['post_id']}",
        kind=EvidenceKind.HISTORICAL,
        uri=record["uri"],
        published_at=record["published_at"],
        available_at=record["captured_at"],
        archived_at=record["captured_at"],
        source_version=text_hash[:48],
        provider=f"{record['platform']}_current_public_capture",
        snippet=(
            f"UNTRUSTED SOCIAL POST, NOT A PEER-REVIEWED FACT. "
            f"AUTHOR: {record['author']}; TITLE: {record['title']}. "
            f"PUBLIC EXCERPT: {record['text'][:MAX_POST_CHARS]}"
        )[:3900],
        facts={
            "platform": record["platform"],
            "source_post_id": record["post_id"],
            "author": record["author"],
            "title": record["title"],
            "provenance": "captured at current time; original post may be edited later",
        },
    )


async def discover_social_sources(
    feeds: tuple[str, ...] = DEFAULT_FEEDS,
    x_bearer: str | None = None,
    limit: int = 40,
) -> tuple[list[Evidence], list[dict], list[str]]:
    if not 2 <= limit <= 60:
        raise ValueError("social discovery limit must be 2..60")
    gaps = []
    records = []
    async with httpx.AsyncClient(timeout=35) as client:
        for feed in feeds:
            try:
                records.extend(await fetch_substack_feed(feed, client))
            except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
                gaps.append(f"SUBSTACK_UNAVAILABLE:{urlparse(feed).hostname}:{type(exc).__name__}")
        if not x_bearer:
            gaps.append("X_AUTH_REQUIRED")
        else:
            try:
                records.extend(await fetch_x_posts(client, x_bearer))
            except (httpx.HTTPError, ValueError) as exc:
                gaps.append(f"X_UNAVAILABLE:{type(exc).__name__}")
    unique: dict[str, dict] = {}
    for record in records:
        unique.setdefault(record["uri"], record)
    # Stable preference for explicit strategy rules rather than vague promotional posts.
    def score(record: dict) -> tuple:
        body = (record["title"] + " " + record["text"]).lower()
        phrase_count = sum(token in body for token in (
            "backtest", "fee", "slippage", "profit factor", "drawdown",
            "out of sample", "entry", "exit", "hour", "breakout", "hold",
        ))
        title = record["title"].lower()
        direct_crypto = any(term in title for term in CRYPTO_TERMS)
        lead_crypto = any(term in record["text"][:360].lower() for term in CRYPTO_TERMS)
        return (-int(direct_crypto), -int(lead_crypto), -phrase_count,
                -len(record["text"]), record["uri"])
    ordered = sorted(unique.values(), key=score)[:limit]
    return [as_evidence(x) for x in ordered], ordered, gaps
