"""Read-only public X strategy intake via the documented x.md v1 API.

x.md is a best-effort third-party reader, NOT an authenticated X timeline or
a historically versioned dataset. Query two bounded public searches, then
verify candidate status posts individually before handing their *original X*
permalink and text to the existing source-fidelity checks. Never execute,
follow external links, import private content, or consume a Warden trial here.

Docs: https://mdfromx.com/docs/posts
      https://mdfromx.com/docs/search
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx

from src.tools.source_registry import MAX_SOURCE_TEXT, make_record

API_HOST = "mdfromx.com"
POSTS_ENDPOINT = "https://mdfromx.com/api/v1/posts"
SEARCH_ENDPOINT = "https://mdfromx.com/api/v1/search"
SOURCE_KEY = "x_public_posts"
# Fixed, small queries; no unbounded firehose or ephemeral user-provided searches.
SEARCH_QUERIES = (
    "nasdaq opening range breakout strategy",
    "crypto breakout strategy backtest",
)
MAX_SEARCH_RESULTS = 8
MAX_VERIFIED_POSTS_PER_SCAN = 4
MAX_RESPONSE_BYTES = 450_000
MAX_TEXT_BYTES = 80_000
POST_PATH = re.compile(r"^/([A-Za-z0-9_]{1,15})/status/([0-9]{14,22})/?$")
RULE_HINTS = ("entry", "exit", "buy", "sell", "long", "short", "breakout",
              "rsi", "atr", "backtest", "stop", "hold", "rebalance", "momentum",
              "mean reversion", "funding", "strategy", "signal")


def parse_permalink(link: str) -> tuple[str, str]:
    """Accept only an exact public X status permalink; no query or media hops."""
    url = urlparse(link)
    if (url.scheme != "https" or url.hostname not in ("x.com", "www.x.com",
         "twitter.com", "www.twitter.com") or url.username or url.password
            or url.port not in (None, 443) or url.query or url.fragment):
        raise ValueError("Only direct public X/twitter status permalinks are permitted")
    match = POST_PATH.fullmatch(url.path)
    if match is None:
        raise ValueError("Missing or malformed X public status path")
    return match.group(1), match.group(2)


def original_url(handle: str, post_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        raise ValueError("Invalid X author handle")
    if not re.fullmatch(r"[0-9]{14,22}", post_id):
        raise ValueError("Invalid X post identifier")
    return f"https://x.com/{handle}/status/{post_id}"


def _published(post: dict, captured: datetime) -> datetime:
    raw = post.get("created_at")
    stamp = post.get("created_timestamp")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Post lacks an original publication timestamp")
    value = parsedate_to_datetime(raw)
    if value.tzinfo is None:
        raise ValueError("Post timestamp must have a timezone")
    value = value.astimezone(timezone.utc)
    if value > captured or value.year < 2006:
        raise ValueError("Future or impossible original publication date")
    if isinstance(stamp, (float, int)) and abs(value.timestamp() - stamp) > 120:
        raise ValueError("Inconsistent provider post timestamps")
    return value


def _rule_candidate(text: str, eligible_general=None) -> bool:
    """Only this tier can feed the frozen Warden matching stage."""
    low = text.lower()
    has_entry = bool(re.search(r"\b(?:entry|enter|buy|sell|long|short)\b", low))
    has_exit = bool(re.search(r"\b(?:exit|close|stop.loss|take.profit|hold for)\b", low))
    has_value = bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:hours?|days?|minutes?|bars?|atr|%|pips?)\b", low))
    return (has_entry and has_exit and has_value and
            (eligible_general is None or eligible_general(text[:165], text)))


def _read_content(post: dict, response: dict) -> tuple[str, bool]:
    text = post.get("text")
    if not isinstance(text, str):
        text = ""
    # X Articles can provide empty post.text while the author content appears
    # in response.markdown. This only applies when a single verified post was
    # requested with thread/replies disabled; never attach reply text.
    is_article = False
    if len(text.strip()) < 30 and post.get("article"):
        markdown = response.get("markdown", "")
        if isinstance(markdown, str) and markdown:
            text = markdown
            is_article = True
    text = re.sub(r"\s+", " ", text).strip()
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError("X post/article exceeds bounded text allowance")
    if len(text) < 45:
        raise ValueError("Public post does not contain sufficient verified text")
    return text[:MAX_SOURCE_TEXT], is_article


def parse_verified_post(payload: dict, requested: str, captured: datetime,
                        *, eligible_general=None) -> dict:
    """Validate a single-post x.md response and retain original X provenance."""
    handle, post_id = parse_permalink(requested)
    if not isinstance(payload, dict) or not isinstance(payload.get("posts"), list):
        raise ValueError("x.md returned no structured post list")
    if payload.get("warnings"):
        raise ValueError("x.md warned that post or context may be incomplete")
    posts = payload["posts"]
    if len(posts) != 1 or not isinstance(posts[0], dict):
        raise ValueError("Single status read returned an ambiguous thread")
    post = posts[0]
    author = post.get("author")
    if not isinstance(author, dict):
        raise ValueError("x.md post has no attributable author")
    if str(author.get("screen_name", "")).lower() != handle.lower():
        raise ValueError("x.md author does not match requested status URL")
    if str(post.get("id", "")) != post_id:
        raise ValueError("x.md post ID does not match requested status URL")
    post_handle, echoed_id = parse_permalink(post.get("url", ""))
    if post_handle.lower() != handle.lower() or echoed_id != post_id:
        raise ValueError("x.md response returned a different original status")
    root_handle, root_id = parse_permalink(payload.get("url", ""))
    if root_handle.lower() != handle.lower() or root_id != post_id:
        raise ValueError("x.md response envelope cites a different post")
    published = _published(post, captured)
    body, is_article = _read_content(post, payload)
    title = re.sub(r"\s+", " ", body).strip()[:165]
    if eligible_general is not None and not eligible_general(title, body):
        raise ValueError("Post is not a documented, rule-focused trading idea")
    # The literal original link is stable when the provider's handle has the
    # same case; API reader/capture timestamp is NOT historical X text vintage.
    original = original_url(handle, post_id)
    record = make_record(
        platform="x_md", source_key=SOURCE_KEY, rank=9,
        link=original, title=title,
        author="@" + handle, published=published, captured=captured,
        text=body, source_feed=POSTS_ENDPOINT,
        authenticity=("PUBLIC_X_ARTICLE_THIRD_PARTY_CURRENT_CAPTURE"
                      if is_article else "PUBLIC_X_POST_THIRD_PARTY_CURRENT_CAPTURE"),
        revision=str(post_id),
        tags=("third_party_reader", "retrospective", "x_public", "rule_unverified"),
    )
    record["x_rule_candidate"] = _rule_candidate(body, eligible_general)
    return record


async def _get(client: httpx.AsyncClient, endpoint: str, params: dict) -> dict:
    if endpoint not in (POSTS_ENDPOINT, SEARCH_ENDPOINT):
        raise ValueError("Unapproved x.md API endpoint")
    response = await client.get(endpoint, params=params, follow_redirects=False)
    response.raise_for_status()
    p = urlparse(str(response.url))
    if response.is_redirect or p.scheme != "https" or p.hostname != API_HOST:
        raise ValueError("x.md response was redirected or changed host")
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ValueError("x.md returned an oversized response")
    if "json" not in response.headers.get("content-type", "").lower():
        raise ValueError("x.md response not JSON; API or quota failure")
    if response.headers.get("X-Search-Degraded", "").lower() in ("true", "1", "yes"):
        raise ValueError("x.md degraded search snippets are not verified posts")
    value = response.json()
    if not isinstance(value, dict) or value.get("error"):
        raise ValueError("x.md returned a malformed or error payload")
    return value


async def fetch_x_post(url: str, client: httpx.AsyncClient,
                       *, eligible_general=None) -> dict:
    """Direct public permalink read. Does not search or invoke Warden."""
    handle, post_id = parse_permalink(url)
    data = await _get(client, POSTS_ENDPOINT, {
        "handle": handle, "id": post_id, "thread": "off",
        "replies": "off", "full": "true", "format": "json",
    })
    return parse_verified_post(
        data, original_url(handle, post_id), datetime.now(timezone.utc),
        eligible_general=eligible_general,
    )


async def collect_x_posts(client: httpx.AsyncClient, eligible_general
                          ) -> tuple[list[dict], str]:
    """Two bounded searches, max four independently fetched public posts.

    Source errors are contained by the outer ranked-source registry. A keyword
    search never manufactures a source quote, date, strategy rule, or gain.
    """
    urls: list[str] = []
    total_searches = 0
    for query in SEARCH_QUERIES:
        result = await _get(client, SEARCH_ENDPOINT, {
            "q": query, "feed": "top", "limit": MAX_SEARCH_RESULTS,
            "format": "json",
        })
        total_searches += 1
        posts = result.get("posts")
        if not isinstance(posts, list):
            raise ValueError("x.md search returned no structured posts")
        # Search results are only untrusted leads; the post endpoint is the
        # actual source verification path.
        for post in posts:
            if not isinstance(post, dict):
                continue
            try:
                handle, post_id = parse_permalink(post.get("url", ""))
                text = post.get("text", "")
                if not isinstance(text, str):
                    continue
                low = text.lower()
                if (len(text) < 140
                        or sum(term in low for term in RULE_HINTS) < 2
                        or not any(topic in low for topic in (
                            "breakout", "momentum", "mean reversion", "vwap",
                            "atr", "backtest", "trading strategy", "range"))):
                    continue
                source = original_url(handle, post_id)
                if source not in urls:
                    urls.append(source)
            except ValueError:
                continue
        # Do not page, bypass rate limits or search automatically again.
    records: list[dict] = []
    for link in urls[:MAX_VERIFIED_POSTS_PER_SCAN]:
        try:
            row = await fetch_x_post(link, client)
            # Discovery can keep source-attributed partial ideas, but they
            # must remain deferred until their original rules are complete.
            row["x_rule_candidate"] = _rule_candidate(row["text"], eligible_general)
            records.append(row)
        except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError):
            continue
    status = ("OK_PUBLIC_X_POST_LEADS_UNVERIFIED" if records else
              "NO_VERIFIED_X_RULE_POSTS")
    return records, status


async def _cli(url: str | None) -> None:
    async with httpx.AsyncClient(timeout=28, headers={
        "User-Agent": "AI-quant-research-loop/0.7 (public X research)",
        "Accept": "application/json",
    }) as client:
        if url is None:
            from src.tools.social_sources import generally_relevant
            rows, status = await collect_x_posts(client, generally_relevant)
            print(json.dumps({
                "status": status, "public_strategy_post_count": len(rows),
                "source_urls": [record["uri"] for record in rows],
                "warden_trials_consumed": 0,
            }, indent=2))
            return
        record = await fetch_x_post(url, client)
    print(json.dumps({
        "status": "PUBLIC_POST_CAPTURED_NO_WARDEN",
        "source": record["uri"], "author": record["author"],
        "published_at": record["published_at"], "captured_at": record["captured_at"],
        "authenticity": record["authenticity"], "text": record["text"],
    }, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Read public X via versioned x.md API")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--url", help="Exact original https://x.com/handle/status/id")
    mode.add_argument("--scan", action="store_true", help="Two bounded public strategy searches")
    args = parser.parse_args()
    asyncio.run(_cli(args.url))


if __name__ == "__main__":
    main()
