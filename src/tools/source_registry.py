"""Curated practitioner research sources with explicit provenance boundaries.

Eight original ranked publishers plus newly user-approved public X posts
read through the third-party mdfromx.com versioned read-only API. No X
credentials, private posts, bypassing controls or publisher code execution.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import quote, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

MAX_FEED_BYTES = 2_500_000
MAX_SOURCE_TEXT = 6500
MAX_HTML_BYTES = 1_000_000
MAX_CODE_BYTES = 28_000


@dataclass(frozen=True)
class SourceSpec:
    key: str
    rank: int
    kind: str
    url: str
    homepage: str
    platform: str


# The first 8 entries represent every requested original publisher/repository.
# QuantifiedStrategies.com serves a protection page to unattended requests.
# Its own named Substack publication is used as the documented public fallback.
RANKED_SOURCES = (
    SourceSpec("pedma", 1, "rss", "https://www.tradingresearchub.com/feed",
               "https://www.tradingresearchub.com/", "substack"),
    SourceSpec("breakout_trading_academy", 2, "rss",
               "https://breakouttradingacademy.com/feed/",
               "https://breakouttradingacademy.com/blog/", "blog"),
    SourceSpec("robot_wealth", 3, "rss", "https://robotwealth.com/feed/",
               "https://robotwealth.com/blog/", "blog"),
    SourceSpec("quantitativo", 4, "rss", "https://www.quantitativo.com/feed",
               "https://www.quantitativo.com/", "substack"),
    SourceSpec("quantified_strategies", 5, "rss",
               "https://quantifiedstrategies.substack.com/feed",
               "https://www.quantifiedstrategies.com/", "substack"),
    SourceSpec("freqtrade_strategies", 6, "github",
               "https://api.github.com/repos/freqtrade/freqtrade-strategies/git/trees/main?recursive=1",
               "https://github.com/freqtrade/freqtrade-strategies", "github"),
    SourceSpec("quantconnect_community", 7, "strategy_index",
               "https://www.quantconnect.com/strategies/",
               "https://www.quantconnect.com/strategies/", "quantconnect"),
    SourceSpec("alvarez_quant_trading", 8, "rss",
               "https://alvarezquanttrading.com/feed/",
               "https://alvarezquanttrading.com/blog/", "blog"),
    SourceSpec("x_public_posts", 9, "x_md",
               "https://mdfromx.com/api/v1/search",
               "https://mdfromx.com/docs/posts", "x_md"),
)

RANKED_SOURCE_KEYS = tuple(s.key for s in RANKED_SOURCES)

LEGACY_SUBSTACK_FEEDS = (
    "https://delphicalpha.substack.com/feed",
    "https://empiricalab.substack.com/feed",
    "https://backtest.substack.com/feed",
    "https://stoicresearch.substack.com/feed",
    "https://gurufinanceinsights.substack.com/feed",
)

# Anchored accepted hosts. Never open links supplied by a source unless first
# verified against this fixed registry (the reader consumes RSS content only).
GITHUB_REPO = "freqtrade/freqtrade-strategies"
GITHUB_TREE_PATH = "user_data/strategies/"
CODE_MARKERS = ("populate_entry_trend", "populate_buy_trend", "populate_indicators",
                "populate_sell_trend", "populate_exit_trend")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def host_of(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.lower().removeprefix("www.")


def same_site(expected_url: str, candidate_url: str) -> bool:
    parsed = urlparse(candidate_url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    if parsed.port not in (None, 443):
        return False
    return host_of(expected_url) == host_of(candidate_url)


def canonical_url(url: str) -> str:
    parts = urlparse(url)
    return urlunparse((parts.scheme, parts.netloc.lower(), parts.path or "/",
                       "", "", ""))


def make_record(*, platform: str, source_key: str, rank: int, link: str,
                title: str, author: str, published: datetime, captured: datetime,
                text: str, source_feed: str, authenticity: str,
                revision: str = "", tags: tuple[str, ...] = ()) -> dict:
    # Blog records are keyed by original permalink, not the publication's RSS
    # last-access timestamp. GitHub revisions use immutable SHA URLs.
    return {
        "platform": platform, "source_key": source_key, "source_priority": rank,
        "post_id": hashlib.sha256(canonical_url(link).encode()).hexdigest()[:24],
        "uri": canonical_url(link), "title": title.strip()[:250],
        "author": author.strip()[:100],
        "published_at": published.isoformat(), "captured_at": captured.isoformat(),
        "text": text.strip()[:MAX_SOURCE_TEXT], "source_feed": source_feed,
        "authenticity": authenticity, "source_revision": revision,
        "tags": list(tags),
    }


def parse_rss_items(xml_bytes: bytes, spec: SourceSpec, captured: datetime,
                    html_to_text, eligible_general) -> list[dict]:
    """Parse source-author original RSS records. Never infer missing pub dates."""
    if len(xml_bytes) > MAX_FEED_BYTES:
        raise ValueError("RSS feed exceeds size cap")
    root = ET.fromstring(xml_bytes)
    posts = []
    for item in root.findall("./channel/item"):
        link = (item.findtext("link") or "").strip()
        if not same_site(spec.url, link):
            continue
        title = html.unescape(item.findtext("title") or "").strip()
        pubdate = (item.findtext("pubDate") or "").strip()
        description = (
            item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
            or item.findtext("description") or ""
        )
        try:
            from email.utils import parsedate_to_datetime
            published = parsedate_to_datetime(pubdate)
            if published.tzinfo is None:
                continue
            published = published.astimezone(timezone.utc)
        except (ValueError, TypeError, OverflowError, IndexError):
            continue
        if not (published <= captured and title):
            continue
        body = html_to_text(description)
        # Blog RSS feeds often contain short summaries. The full original
        # article is retrieved and validated below, never from other hosts.
        if spec.platform == "substack" and not eligible_general(title, body):
            continue
        creator = item.findtext("{http://purl.org/dc/elements/1.1/}creator") or host_of(spec.url)
        posts.append(make_record(
            platform=spec.platform, source_key=spec.key, rank=spec.rank,
            link=link, title=title, author=creator, published=published,
            captured=captured, text=body, source_feed=spec.url,
            authenticity="ORIGINAL_PUBLISHER_RSS_CURRENT_CAPTURE",
        ))
    return posts


async def fetch_original_article(
    record: dict, spec: SourceSpec, client: httpx.AsyncClient
) -> str | None:
    """Extract public author text; no remote subresources or paywall bypass."""
    url = record["uri"]
    if not same_site(spec.url, url):
        raise ValueError("Original article domain mismatch")
    response = await client.get(url, follow_redirects=False)
    response.raise_for_status()
    if response.is_redirect or len(response.content) > MAX_HTML_BYTES:
        raise ValueError("Article redirected or exceeded HTML size budget")
    if "html" not in response.headers.get("content-type", "").lower():
        raise ValueError("Article did not serve HTML")
    soup = BeautifulSoup(response.content, "html.parser")
    body = (
        soup.select_one("article .entry-content")
        or soup.select_one("article .post-content")
        or soup.select_one("article")
        or soup.select_one("main")
    )
    if body is None:
        return None
    for node in body.select("script,style,nav,footer,aside,form,noscript,svg"):
        node.decompose()
    return re.sub(r"\s+", " ", body.get_text(" ", strip=True))[:MAX_SOURCE_TEXT]


async def get_rss(spec: SourceSpec, client: httpx.AsyncClient,
                  html_to_text, eligible_general) -> tuple[list[dict], str]:
    response = await client.get(spec.url, follow_redirects=True)
    response.raise_for_status()
    if not same_site(spec.url, str(response.url)):
        raise ValueError("RSS redirected to an unapproved hostname")
    if len(response.content) > MAX_FEED_BYTES:
        raise ValueError("RSS source response exceeds byte limit")
    if not response.text.lstrip().startswith("<?xml") and "<rss" not in response.text[:1000]:
        raise ValueError("RSS endpoint returned non-XML content or anti-bot page")
    posts = parse_rss_items(response.content, spec, utc_now(), html_to_text, eligible_general)
    if spec.platform == "blog":
        qualified = []
        for post in posts[:8]:
            if len(post["text"]) < 950:
                try:
                    expanded = await fetch_original_article(post, spec, client)
                    if expanded and len(expanded) > len(post["text"]):
                        post["text"] = expanded
                except (httpx.HTTPError, ValueError, TypeError):
                    # Keep a useful original feed excerpt when an article is protected.
                    pass
            if eligible_general(post["title"], post["text"]):
                qualified.append(post)
        posts = qualified
    return posts, "OK" if posts else "NO_USABLE_PUBLIC_STRATEGY_POSTS"


async def get_github(spec: SourceSpec, client: httpx.AsyncClient) -> tuple[list[dict], str]:
    """Read immutable strategy examples; do not import, eval, or run source code."""
    commit_response = await client.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/commits/main"
    )
    commit_response.raise_for_status()
    branch_commit = commit_response.json()
    commit_sha = branch_commit.get("sha")
    if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise ValueError("GitHub branch commit has invalid SHA")
    tree_sha = branch_commit.get("commit", {}).get("tree", {}).get("sha")
    if not isinstance(tree_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", tree_sha):
        raise ValueError("GitHub branch tree SHA invalid")
    tree_response = await client.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/git/trees/{tree_sha}",
        params={"recursive": 1},
    )
    tree_response.raise_for_status()
    data = tree_response.json()
    if data.get("sha") != tree_sha:
        raise ValueError("GitHub immutable tree content mismatch")
    items = data.get("tree")
    if not isinstance(items, list) or data.get("truncated", False):
        raise ValueError("GitHub tree missing or truncated")
    permitted = []
    for entry in items:
        path = entry.get("path", "")
        blob = entry.get("sha", "")
        if (entry.get("type") == "blob"
                and path.startswith(GITHUB_TREE_PATH)
                and path.endswith(".py")
                and ".." not in PurePosixPath(path).parts
                and re.fullmatch(r"[0-9a-f]{40}", blob or "")):
            permitted.append((path, blob))
    # Limit GitHub rate usage. Prefer real named strategy classes over examples
    # but preserve stable ordering so a rerun is deterministic.
    preferred = ("trend", "rsi", "momentum", "ema", "supertrend", "band", "swing", "macd")
    permitted.sort(key=lambda x: (-int(any(k in x[0].lower() for k in preferred)), x[0]))
    selected = permitted[:6]
    records = []
    for path, sha in selected:
        endpoint = f"https://api.github.com/repos/{GITHUB_REPO}/git/blobs/{sha}"
        try:
            r = await client.get(endpoint)
            r.raise_for_status()
            blob = r.json()
            if blob.get("encoding") != "base64":
                continue
            encoded = blob.get("content", "")
            if not isinstance(encoded, str) or len(encoded) > MAX_CODE_BYTES * 2:
                continue
            code = base64.b64decode(encoded, validate=False).decode("utf-8", errors="replace")
            if len(code.encode("utf-8")) > MAX_CODE_BYTES:
                continue
            if not ("class " in code and any(marker in code for marker in CODE_MARKERS)):
                continue
            # Code source is pinned to its actual blob SHA; date is the
            # current capture, not a fabricated publication date.
            captured = utc_now()
            url = f"https://github.com/{GITHUB_REPO}/blob/{commit_sha}/{quote(path, safe='/')}"
            records.append(make_record(
                platform="github", source_key=spec.key, rank=spec.rank,
                link=url, title=PurePosixPath(path).stem,
                author=GITHUB_REPO, published=captured, captured=captured,
                text=code[:MAX_SOURCE_TEXT], source_feed=spec.url,
                authenticity="CODE_ONLY_UNVALIDATED_NO_EXECUTION",
                revision=sha, tags=("crypto", "code_unvalidated"),
            ))
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            continue
    return records, "OK_CODE_EXAMPLES_UNVALIDATED" if records else "NO_VALID_CODE_EXAMPLES"


class StrategyLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href") or ""
            if href:
                self.links.append(href)


async def get_quantconnect(spec: SourceSpec, client: httpx.AsyncClient) -> tuple[list[dict], str]:
    """Inspect only first-party, explicit strategy detail links.

    The public overview page currently loads its strategy table dynamically.
    We intentionally do NOT invent a private, undocumented JSON endpoint.
    """
    response = await client.get(spec.url, follow_redirects=True)
    response.raise_for_status()
    if not same_site(spec.url, str(response.url)) or len(response.content) > MAX_HTML_BYTES:
        raise ValueError("invalid QuantConnect page or redirect")
    parser = StrategyLinkParser()
    parser.feed(response.text)
    qualified = []
    for link in parser.links:
        if link.startswith("/strategies/"):
            link = "https://www.quantconnect.com" + link
        parsed = urlparse(link)
        if (same_site(spec.url, link)
                and re.fullmatch(r"/strategies/[A-Za-z0-9_-]{5,}", parsed.path)):
            qualified.append(link)
    if not qualified:
        return [], "INDEX_ONLY_JS_RENDERED_NO_VERIFIABLE_PUBLIC_STRATEGY"
    # A link alone has no strategy rule or independently dated publication.
    # Do not synthesize a trading idea from its URL or the marketing page.
    return [], f"INDEX_LINKS_PRESENT_WITHOUT_PUBLIC_RULES:{len(set(qualified))}"


async def collect_registry_sources(client: httpx.AsyncClient, html_to_text,
                                   eligible_general, specs=RANKED_SOURCES
                                   ) -> tuple[list[dict], list[dict], list[str]]:
    """Retrieve every configured source; fail one source independently."""
    all_records, health, gaps = [], [], []
    for spec in specs:
        try:
            if spec.kind == "rss":
                records, result = await get_rss(spec, client, html_to_text, eligible_general)
            elif spec.kind == "github":
                records, result = await get_github(spec, client)
            elif spec.kind == "strategy_index":
                records, result = await get_quantconnect(spec, client)
            elif spec.kind == "x_md":
                from src.tools.x_md import collect_x_posts
                records, result = await collect_x_posts(client, eligible_general)
            else:
                raise ValueError("unknown configured source type")
            health.append({"source": spec.key, "priority": spec.rank, "kind": spec.kind,
                           "status": result, "usable_records": len(records),
                           "homepage": spec.homepage, "feed": spec.url})
            if result.startswith("INDEX_") or result.startswith("NO_"):
                gaps.append(f"SOURCE_LIMITED:{spec.key}:{result}")
            all_records.extend(records)
        except (httpx.HTTPError, ValueError, ET.ParseError, json.JSONDecodeError,
                UnicodeDecodeError, TypeError) as exc:
            status = f"ERROR_{type(exc).__name__}"
            health.append({"source": spec.key, "priority": spec.rank, "kind": spec.kind,
                           "status": status, "usable_records": 0,
                           "homepage": spec.homepage, "feed": spec.url})
            gaps.append(f"SOURCE_UNAVAILABLE:{spec.key}:{type(exc).__name__}")
    return all_records, health, gaps
