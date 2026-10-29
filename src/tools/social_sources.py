"""Curated practitioner strategy intake from original blogs, Substack and GitHub.

No X.com ingestion, external search mirrors, paywall bypass or code execution.
All records are untrusted current captures; market-fit and authenticity labels
are preserved through evidence/strategy selection.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from src.core.models import Evidence, EvidenceKind
from src.tools.source_registry import (
    LEGACY_SUBSTACK_FEEDS, MAX_FEED_BYTES, MAX_SOURCE_TEXT,
    RANKED_SOURCES, collect_registry_sources, make_record,
)

DEFAULT_FEEDS = LEGACY_SUBSTACK_FEEDS
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"
STRATEGY_TERMS = (
    "backtest", "strategy", "trading rule", "momentum", "mean reversion",
    "reversal", "breakout", "trend following", "buy the dip", "funding",
    "rsi", "donchian", "signal", "tested", "short-term", "systematic",
)
PAPER_ONLY_TERMS = ("review of the paper", "new paper", "arxiv", "research paper summary")
NON_STRATEGY_TITLES = (
    "start here", "what is a trading strategy", "app store", "random signals",
    "welcome", "about this newsletter", "my process",
    "i sold", "i am ending", "performance update", "my portfolio update",
)
RULE_TERMS = (
    "entry", "exit", "long", "short", "lookback", "threshold", "trades",
    "backtest", "risk", "return", "sharpe", "hold", "signal", "rsi",
    "hours", "bars", "moving average", "buy", "sell",
)
CRYPTO_TERMS = (
    "crypto", "bitcoin", "btc", "altcoin", "perpetual", "binance",
    "ethereum", "ethusd", "hyperliquid", "solana",
)


@dataclass(frozen=True)
class SourceDiscovery:
    eligible: list[Evidence]
    metadata: list[dict]
    gaps: list[str]
    deferred: list[dict]
    health: list[dict]

    def __iter__(self):
        """Compatibility with previous three-element source discovery results."""
        yield self.eligible
        yield self.metadata
        yield self.gaps


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


def generally_relevant(title: str, body: str) -> bool:
    summary = (title + " " + body[:1600]).lower()
    title_lower = title.lower()
    if any(x in title_lower for x in PAPER_ONLY_TERMS + NON_STRATEGY_TITLES):
        return False
    if not any(x in summary for x in STRATEGY_TERMS):
        return False
    has_rule_focus = any(term in title_lower for term in (
        "strategy", "backtest", "rule", "research", "momentum", "reversal",
        "breakout", "trend", "rsi", "alpha", "carry", "signal", "trading",
        "stat arb", "factor", "arbitrage", "edge", "quant", "systematic",
    )) or (all(term in summary for term in ("entry", "exit")))
    return (has_rule_focus and sum(term in summary for term in RULE_TERMS) >= 3
            and len(body) >= 120)


def crypto_relevant(title: str, body: str) -> bool:
    # An index or ETF strategy is deferred even when it discusses crypto in a
    # disclaimer or market comparison. Require positive crypto subject evidence.
    title_lower = title.lower()
    if any(term in title_lower for term in CRYPTO_TERMS):
        return True
    noncrypto_title = (
        "nasdaq", "s&p 500", "spy", "qqq", "apple", "equity",
        "etf", "vix", "e-mini", "nifty", "gold", "ustec", "indices",
    )
    if any(term in title_lower for term in noncrypto_title):
        return False
    lead = body[:650].lower()
    if re.search(r"\b(?:not|no|without)\s+(?:an?\s+)?crypto\b", lead):
        return False
    return any(term in lead for term in CRYPTO_TERMS)


def index_relevant(title: str, body: str) -> bool:
    title_l = title.lower()
    keys = ("nasdaq", "nq", "s&p 500", "sp500", "s&p500", "dax",
            "nikkei", "hk33", "index breakout", "opening range", "index futures")
    # A stock universe / leveraged ETF is not the index CFD itself.
    if any(k in title_l for k in ("stocks", "shares", "qqq", "spy", "etf", "etfs")):
        return False
    lead = body[:550].lower()
    if "leverage switch" in title_l and any(k in lead for k in ("etf", "qqq", "tqqq")):
        return False
    return any(k in title_l for k in keys)


def eligible_post(title: str, body: str) -> bool:
    return generally_relevant(title, body) and (
        crypto_relevant(title, body) or index_relevant(title, body)
    )


def _valid_substack_link(feed_url: str, link: str) -> bool:
    original = urlparse(feed_url)
    candidate = urlparse(link)
    return (
        candidate.scheme == "https"
        and candidate.hostname is not None
        and (candidate.hostname == original.hostname
             or candidate.hostname == "substack.com")
        and (candidate.path.startswith("/p/") or "/note/" in candidate.path)
    )


def parse_substack_feed(xml_bytes: bytes, feed_url: str, captured_at: datetime) -> list[dict]:
    """Compatibility adapter for the pre-existing direct Substack RSS contract."""
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
        creator = item.findtext("{http://purl.org/dc/elements/1.1/}creator") or hostname
        records.append(make_record(
            platform="substack", source_key=hostname, rank=100,
            link=link, title=title, author=creator,
            published=published, captured=captured_at, text=content,
            source_feed=feed_url,
            authenticity="ORIGINAL_PUBLISHER_RSS_CURRENT_CAPTURE",
        ))
    return records


async def fetch_substack_feed(feed_url: str, client: httpx.AsyncClient) -> list[dict]:
    host = urlparse(feed_url)
    if host.scheme != "https" or not (host.hostname or "").endswith(".substack.com"):
        raise ValueError("Substack feed must be a curated HTTPS publication")
    if host.path != "/feed":
        raise ValueError("Substack URL must end in /feed")
    response = await client.get(
        feed_url, follow_redirects=False,
        headers={"User-Agent": "AI-quant-research-loop/0.4 (public practitioner RSS)"},
    )
    response.raise_for_status()
    if response.is_redirect:
        raise ValueError("Substack feed redirect not allowlisted")
    return parse_substack_feed(response.content, feed_url, datetime.now(timezone.utc))


def as_evidence(record: dict) -> Evidence:
    source_hash = hashlib.sha256(
        json.dumps({
            "uri": record["uri"], "text": record["text"],
            "published_at": record["published_at"],
            "revision": record.get("source_revision", ""),
        }, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    authenticity = record.get("authenticity", "ORIGINAL_PUBLIC_POST_CURRENT_CAPTURE")
    return Evidence(
        source_id=f"social_{record['platform']}_{record['post_id']}",
        kind=EvidenceKind.HISTORICAL,
        uri=record["uri"],
        published_at=record["published_at"],
        available_at=record["captured_at"],
        archived_at=record["captured_at"],
        source_version=source_hash[:48],
        provider=f"{record['platform']}_current_public_capture",
        snippet=(
            f"UNTRUSTED PRACTITIONER CONTENT, NOT VERIFIED ALPHA. "
            f"AUTHOR: {record['author']}; TITLE: {record['title']}. "
            f"SOURCE_TYPE: {authenticity}. "
            f"PUBLIC EXCERPT: {record['text'][:MAX_SOURCE_TEXT]}"
        )[:3900],
        facts={
            "platform": record["platform"],
            "source_key": record.get("source_key", "unknown"),
            "source_post_id": record["post_id"],
            "source_priority": str(record.get("source_priority", 100)),
            "author": record["author"], "title": record["title"],
            "source_authenticity": authenticity,
            "revision": record.get("source_revision", ""),
            "provenance": "Current public capture, historical text vintage unverified",
        },
    )


def focused_rule_excerpt(original: str, max_chars: int = 1900) -> str:
    """Preserve exact author sentences about entry/exit before filler intros.

    Input is a captured public post, never a command or instruction. Keeping
    original substrings allows deterministic quote verification downstream.
    """
    sentences = re.split(r"(?<=[.!?])\s+", original.strip())
    if not sentences:
        return ""
    phrases = ("entry", "exit", "buy", "sell", "hold", "rebalance",
               "breakout", "lookback", "stop", "long", "short",
               "rsi", "donchian", "momentum", "volume", "timeframe")
    ranked = sorted(enumerate(sentences), key=lambda row: (
        -sum(term in row[1].lower() for term in phrases), row[0]
    ))
    selected, consumed = [], 0
    for index, sentence in ranked:
        if not sentence or len(sentence) > max_chars:
            continue
        if consumed + len(sentence) + 2 > max_chars:
            continue
        selected.append((index, sentence))
        consumed += len(sentence) + 2
    return " ".join(sentence for _, sentence in sorted(selected))


def _rank_key(record: dict) -> tuple:
    body = (record["title"] + " " + record["text"]).lower()
    detail = sum(x in body for x in (
        "backtest", "fee", "slippage", "profit factor", "drawdown",
        "out of sample", "entry", "exit", "hour", "breakout", "hold",
    ))
    return (record.get("source_priority", 100), -detail, -len(record["text"]), record["uri"])


async def discover_social_sources(
    feeds: tuple[str, ...] = DEFAULT_FEEDS,
    limit: int = 40,
) -> SourceDiscovery:
    """Collect original practitioner rules for contract-aware Warden routing.

    Crypto and explicitly index-focused posts are eligible for source-rule
    extraction. Unsupported equities, FX, and code-only ideas are deferred.
    """
    if not 2 <= limit <= 60:
        raise ValueError("source limit must be 2..60")
    records, health, gaps = [], [], []
    async with httpx.AsyncClient(timeout=35, headers={
        "User-Agent": "AI-quant-research-loop/0.4 (public academic and practitioner research)",
        "Accept": "application/rss+xml, application/xml, application/json, text/html;q=0.9",
    }) as client:
        # Custom feeds in tests/one-off probes do not fetch eight other sites.
        if feeds == DEFAULT_FEEDS:
            ranked, source_health, ranked_gaps = await collect_registry_sources(
                client, html_to_text, generally_relevant, RANKED_SOURCES,
            )
            records.extend(ranked)
            health.extend(source_health)
            gaps.extend(ranked_gaps)
        for feed in feeds:
            try:
                posts = await fetch_substack_feed(feed, client)
                records.extend(posts)
                health.append({
                    "source": urlparse(feed).hostname, "priority": 100,
                    "kind": "rss", "status": "OK" if posts else "NO_USABLE_PUBLIC_CRYPTO",
                    "usable_records": len(posts), "feed": feed,
                })
            except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
                gaps.append(
                    f"SOURCE_UNAVAILABLE:{urlparse(feed).hostname}:{type(exc).__name__}"
                )
                health.append({
                    "source": urlparse(feed).hostname, "priority": 100,
                    "kind": "rss", "status": f"ERROR_{type(exc).__name__}",
                    "usable_records": 0, "feed": feed,
                })
    unique = {}
    for record in records:
        unique.setdefault(record["uri"], record)
    ordered = sorted(unique.values(), key=_rank_key)
    eligible = [
        r for r in ordered
        if r.get("platform") != "github"
        and (crypto_relevant(r["title"], r["text"])
             or index_relevant(r["title"], r["text"]))
    ]
    eligible_urls = {item["uri"] for item in eligible}
    deferred = [
        {"source": r.get("source_key"), "source_priority": r.get("source_priority"),
         "url": r["uri"], "title": r["title"],
         "reason": (
             "CODE_ONLY_REQUIRES_FROZEN_RULE_MAPPING" if r.get("platform") == "github"
             else "NO_MATCHING_REVIEWED_MARKET_CONTRACT"
         ),
         "published_at": r["published_at"],
         "code_revision": r.get("source_revision", ""),
         "code_preview": r["text"][:900] if r.get("platform") == "github" else "",
        }
        for r in ordered if r["uri"] not in eligible_urls
    ]
    # Ranked research is preferred over the previously existing feed basket.
    selected = eligible[:limit]
    return SourceDiscovery(
        eligible=[as_evidence(item) for item in selected],
        metadata=selected,
        gaps=gaps,
        deferred=deferred[:150],
        health=health,
    )
