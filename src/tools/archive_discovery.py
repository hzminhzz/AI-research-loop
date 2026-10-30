"""Publisher-archive mining; preserves source evidence without Warden trials.

Only approved original hosts and immutable public code paths are read.
Source excerpts are NOT claims of a fully reproducible strategy or alpha.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "Quant-Archive-Scout/0.6 (public original sources, research only)"
MAX_HTML = 1_800_000
MAX_XML = 3_000_000
CAPS = {
    "breakout_academy": 35, "quantconnect_library": 29,
    "finetiq_ideas": 28, "cloudquant_backtrader": 10,
    "quantified_strategies": 16, "algomatic_trading": 14,
    "financial_hacker": 12,
}


@dataclass(frozen=True)
class Source:
    key: str
    host: str
    index: str
    kind: str
    prefix: str


SOURCES = (
    Source("breakout_academy", "breakouttradingacademy.com",
           "https://breakouttradingacademy.com/post-sitemap.xml", "sitemap", "/"),
    Source("quantconnect_library", "www.quantconnect.com",
           "https://www.quantconnect.com/learning/articles/investment-strategy-library",
           "html", "/learning/articles/investment-strategy-library/"),
    Source("finetiq_ideas", "ideas.finetiqsystems.com",
           "https://ideas.finetiqsystems.com/sitemap.xml", "sitemap", "/en/ideas/"),
    Source("cloudquant_backtrader", "api.github.com",
           "https://api.github.com/repos/cloudQuant/backtrader/commits/dev",
           "github", "/repos/cloudQuant/backtrader/"),
    Source("quantified_strategies", "www.quantifiedstrategies.com",
           "https://www.quantifiedstrategies.com/sitemap_index.xml", "sitemap", "/"),
    Source("algomatic_trading", "www.algomatictrading.com",
           "https://www.algomatictrading.com/blog-posts-sitemap.xml", "sitemap", "/"),
    Source("financial_hacker", "financial-hacker.com",
           "https://financial-hacker.com/wp-sitemap.xml", "sitemap", "/"),
)
PREFERRED_PATHS = {
    "breakout_academy": (
        "steal-this-monday-nasdaq-strategy",
        "how-to-build-a-short-opening-gap-strategy",
        "i-tested-225-opening-gap-strategies",
        "gold-breakout-strategy",
    ),
    "quantconnect_library": (
        "dual-thrust-trading-algorithm",
        "the-dynamic-breakout-ii-strategy",
        "combining-mean-reversion-and-momentum-in-forex-market",
        "intraday-dynamic-pairs-trading",
        "forex-momentum",
    ),
    "finetiq_ideas": ("adr-stop-gate", "avwap-ema-flush", "always-in-breakout"),
}
LOW_VALUE = ("podcast", "interview", "newsletter", "discount", "course",
             "subscription", "pricing", "broker review", "broker-review",
             "reasons why", "traders fail", "best trading indicator",
             "indicator comparison", "how to become", "common mistakes")
KEYWORDS = ("breakout", "reversion", "reversal", "momentum", "trend", "vwap",
            "bollinger", "opening", "gap", "mean", "intraday", "moving average",
            "rsi", "arbitrage", "pairs", "carry", "volatility", "channel",
            "seasonality", "pullback", "dual thrust", "keltner", "gold",
            "nasdaq", "forex", "futures", "donchian", "range", "regime",
            "rotation", "cointegration", "ftse", "index", "williams",
            "macd", "strategy", "system")
ENTRY = ("buy", "sell", "long", "short", "enter", "entry", "signal",
         "break above", "break below", "crosses", "crossed",
         "above the", "below the", "open a position")
EXIT = ("exit", "liquidate", "close when", "close the", "stop loss", "stop-loss",
        "take profit", "take-profit", "trailing stop", "hold for",
        "hold until", "rebalance", "sell when", "cover when", "flat at")
FAMILIES = (
    ("breakout", ("breakout", "opening range", "donchian", "dual thrust", "channel")),
    ("mean_reversion", ("mean reversion", "mean-reversion", "reversion", "reversal", "pullback")),
    ("momentum", ("momentum", "relative strength", "rotation", "cross-sectional")),
    ("trend_following", ("trend following", "trend-following", "trend", "moving average")),
    ("stat_arb", ("pairs", "arbitrage", "cointegration", "spread trading")),
    ("carry", ("funding", "carry", "term structure")),
    ("seasonality", ("seasonal", "calendar", "holiday", "overnight", "monday")),
    ("volatility", ("volatility", "vix", "atr", "squeeze", "compression")),
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def clean(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme, p.netloc.lower(), p.path or "/", "", "", ""))


def allowed(url: str, src: Source) -> bool:
    p = urlparse(url)
    return (p.scheme == "https" and p.hostname == src.host and
            p.port in (None, 443) and not p.username and not p.password and
            not p.query and not p.fragment and
            ".." not in p.path.split("/") and p.path.startswith(src.prefix))


def locs(xml: bytes) -> list[str]:
    root = ET.fromstring(xml)
    return [v.text.strip() for v in root.iter()
            if v.tag.rsplit("}", 1)[-1] == "loc" and v.text]


def interest(title: str, path: str) -> bool:
    low = (title + " " + path).lower().replace("-", " ")
    if any(part in path for part in ("/tag/", "/category/", "/wp-admin/", "/page/")):
        return False
    return not any(k in low for k in LOW_VALUE) and any(k in low for k in KEYWORDS)


def classify(title: str, path: str) -> tuple[str, str]:
    text = (title + " " + path).lower()
    if any(k in text for k in ("stocks", "equities", "qqq", "spy", "shares", "etf", "country equity indexes")):
        market = "equities_etf"
    elif any(k in text for k in ("forex", "currency", "eurusd", "usdjpy", "gbpusd", "eurjpy", "fx-")):
        market = "fx"
    elif any(k in text for k in ("gold", "xauusd", "silver", "xagusd")):
        market = "metals"
    elif any(k in text for k in ("bitcoin", "crypto", "btc", "ethusdt", "perpetual", "altcoin")):
        market = "crypto"
    elif any(k in text for k in ("nasdaq", "nq-", "s&p-500", "sp500", "ftse", "index trading", "equity index", "indices", "dax", "nifty", "shorting-the-index")):
        market = "indices"
    elif any(k in text for k in ("commodit", "crude", "wti", "brent")):
        market = "commodities"
    else:
        market = "unspecified"
    family = next((k for k, terms in FAMILIES if any(x in text for x in terms)), "other")
    return market, family


CONTRACTS = {
    "indices": ("INDICES_5M_V1", "MARKET_TIMEFRAME_REVIEW"),
    "fx": ("FX_MAJORS_5M_V1", "MARKET_TIMEFRAME_REVIEW"),
    "metals": ("METALS_1M_DATA_PRESENT", "NEW_CONTRACT_REVIEW"),
    "crypto": ("CRYPTO_PERPS_TOP100_1H_V1", "MARKET_TIMEFRAME_REVIEW"),
    "commodities": ("COMMODITIES_1M_DATA_PRESENT", "NEW_CONTRACT_REVIEW"),
    "equities_etf": ("NONE", "INSTRUMENT_MISMATCH"),
    "unspecified": ("UNKNOWN", "MARKET_UNRESOLVED"),
}


def extract(soup: BeautifulSoup) -> tuple[str, str, list[str]]:
    area = (soup.select_one("article .entry-content") or
            soup.select_one(".entry-content") or
            soup.select_one(".article-body") or
            soup.select_one("article") or
            soup.select_one("main") or soup.body)
    if area is None:
        return "", "", []
    for node in area.select("script,style,nav,footer,aside,noscript,iframe,form,svg,button"):
        node.decompose()
    head = soup.select_one("h1") or soup.select_one("title")
    title = " ".join(head.stripped_strings)[:240] if head else ""
    full = re.sub(r"\s+", " ", area.get_text(" ", strip=True))[:18000]
    segments = []
    for el in area.select("p,li,h2,h3"):
        if el.find_parent(["li", "p"]) is not None:
            continue
        value = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        if 25 <= len(value) <= 750 and value not in segments:
            segments.append(value)
    return title, full, segments


def quote_rule(parts: list[str], terms: tuple[str, ...]) -> str:
    matches = []
    for sentence in parts:
        low = sentence.lower()
        hits = sum(1 for token in terms if token in low)
        if hits:
            digits = int(bool(re.search(r"\b\d+(?:\.\d+)?\b", low)))
            matches.append((hits * 2 + digits, -len(sentence), sentence))
    return max(matches, default=(0, 0, ""))[2][:290]


def rules(title: str, segments: list[str]) -> dict:
    entry = quote_rule(segments, ENTRY)
    exit_text = quote_rule([x for x in segments if x != entry], EXIT)
    full = (title + " " + " ".join(segments[:35])[:1900]).lower()
    freq = None
    for name, pattern in (
        ("1m", r"\b(?:1-minute|1 minute|m1|1m)\b"),
        ("5m", r"\b(?:5-minute|5 minute|m5|5m)\b"),
        ("15m", r"\b(?:15-minute|15 minute|m15|15m)\b"),
        ("30m", r"\b(?:30-minute|30 minute|m30|30m)\b"),
        ("1h", r"\b(?:hourly|one.hour|1-hour|1 hour|h1|1h)\b"),
        ("4h", r"\b(?:4-hour|4 hour|h4|4h)\b"),
        ("1d", r"\b(?:daily|day bars|d1|1-day)\b"),
    ):
        if re.search(pattern, full):
            freq = name
            break
    exit_specific = bool(exit_text and re.search(
        r"\b\d+(?:\.\d+)?\s*(?:%|pips?|bars?|minutes?|hours?|days?|atr|r\b)"
        r"|\b(?:end of day|market close|next open|trailing stop|stop loss|stop-loss)\b",
        exit_text.lower()))
    state = ("RULES_VISIBLE_UNVERIFIED" if entry and exit_specific else
             "PARTIAL_RULES" if entry or exit_text else "TITLE_ONLY")
    return {"entry_excerpt": entry, "exit_excerpt": exit_text,
            "timeframe_hint": freq, "rule_state": state,
            "exact_source_equivalence_verified": False}


def published(soup: BeautifulSoup) -> str | None:
    for attrs in ({"property": "article:published_time"},
                  {"name": "datePublished"}, {"itemprop": "datePublished"}):
        el = soup.find("meta", attrs=attrs)
        if el and el.get("content"):
            return str(el["content"])[:60]
    el = soup.find("time", attrs={"datetime": True})
    return str(el["datetime"])[:60] if el else None


def rank(doc: dict) -> int:
    market = doc["market"]
    score = 35 if market in ("indices", "fx", "crypto", "metals") else 18 if market == "commodities" else 5
    score += 15 if doc["family"] not in ("other", "volatility") else 7
    score += {"RULES_VISIBLE_UNVERIFIED": 29, "PARTIAL_RULES": 13,
              "TITLE_ONLY": 0, "CODE_ONLY_UNREVIEWED": 2}[doc["rule_state"]]
    score += 7 if doc.get("timeframe_hint") else 0
    score += 3 if doc.get("published_at") else 0
    score += 5 if doc["source_key"] in ("breakout_academy", "quantconnect_library") else 0
    if any(slug in doc["url"] for slug in PREFERRED_PATHS.get(doc["source_key"], ())):
        score += 35  # research-fit priority only, NEVER predicted performance
    return score



class ArchiveScout:
    def __init__(self, *, limits: dict[str, int] | None = None, concurrency: int = 5,
                 seed_catalog: Path | None = None):
        self.limits = limits or CAPS
        self.sem = asyncio.Semaphore(concurrency)
        self.health: list[dict] = []
        self.indexes: dict[str, list[dict]] = {}
        self.robots: dict[str, RobotFileParser | bool] = {}
        self.seed_indexes: dict[str, list[dict]] = {}
        if seed_catalog is not None and seed_catalog.is_file():
            captured = json.loads(seed_catalog.read_text(encoding="utf-8"))
            if captured.get("schema_version") != "PRACTITIONER_ARCHIVE_V1":
                raise ValueError("Unrecognized source-index seed schema")
            self.seed_indexes = captured.get("source_indexes", {})

    async def get(self, client: httpx.AsyncClient, url: str, src: Source,
                  *, max_bytes: int = MAX_HTML) -> httpx.Response:
        if not allowed(url, src) and url != src.index:
            raise ValueError("External or unapproved source URL")
        async with self.sem:
            response = await client.get(url, follow_redirects=False)
        if response.is_redirect:
            # QuantConnect static library pages explicitly redirect to the
            # publisher's own public /research/{id}/{slug}/ article. This is
            # one strictly validated FIRST-PARTY hop, not arbitrary redirects.
            target = urljoin(url, response.headers.get("location", ""))
            p = urlparse(target)
            if (src.key != "quantconnect_library" or p.scheme != "https"
                    or p.hostname != src.host or p.query or p.fragment
                    or not re.fullmatch(r"/research/[0-9]+/[a-z0-9-]+/?", p.path)
                    or not self.robots[src.key].can_fetch(USER_AGENT, target)):
                raise ValueError("Unapproved redirect rejected")
            async with self.sem:
                response = await client.get(target, follow_redirects=False)
            if response.is_redirect:
                raise ValueError("Second publisher redirect rejected")
        response.raise_for_status()
        if response.url.host != src.host or len(response.content) > max_bytes:
            raise ValueError("Publisher host mismatch or oversized source")
        return response

    async def check_robots(self, client: httpx.AsyncClient, src: Source) -> None:
        if src.kind == "github":
            # Pinned public GitHub API metadata is not a spider of web pages.
            self.robots[src.key] = True
            return
        url = f"https://{src.host}/robots.txt"
        root = Source(src.key, src.host, url, src.kind, "/")
        for attempt in range(3):
            try:
                r = await self.get(client, url, root, max_bytes=250_000)
                mime = r.headers.get("content-type", "").lower()
                if not (("text/plain" in mime or "application/octet-stream" in mime)
                        and "user-agent:" in r.text.lower() and "<html" not in r.text[:300].lower()):
                    raise ValueError("robots policy is not a valid text rules document")
                rules = RobotFileParser()
                rules.parse(r.text.splitlines())
                self.robots[src.key] = rules
                return
            except (ValueError, httpx.HTTPError):
                if attempt < 2:
                    await asyncio.sleep((attempt + 1) * 0.5)
        # No verified robots policy after bounded retries -> do not crawl.
        self.robots[src.key] = False

    def can(self, src: Source, url: str) -> bool:
        if not allowed(url, src):
            return False
        policy = self.robots.get(src.key, False)
        if policy is True:
            return True
        if policy is False:
            return False
        return policy.can_fetch(USER_AGENT, url)

    async def sitemap(self, client: httpx.AsyncClient, src: Source) -> list[dict]:
        r = await self.get(client, src.index, src, max_bytes=MAX_XML)
        if "xml" not in r.headers.get("content-type", "").lower():
            raise ValueError("Publisher sitemap is unavailable or serves HTML")
        root = ET.fromstring(r.content)
        is_index = root.tag.rsplit("}", 1)[-1] == "sitemapindex"
        found = locs(r.content)
        direct = [] if is_index else [clean(u) for u in found if self.can(src, clean(u))
                                     and clean(u) != src.index]
        if is_index:
            children = [u for u in found if urlparse(u).hostname == src.host
                        and re.search(r"(?:/post-sitemap|/blog-posts-sitemap|/wp-sitemap-posts-post-)", urlparse(u).path)][:8]
            for child in children:
                # Sitemap index files can be outside the article path prefix.
                index_src = Source(src.key, src.host, child, src.kind, "/")
                try:
                    additional = await self.get(client, child, index_src, max_bytes=MAX_XML)
                    if "xml" in additional.headers.get("content-type", "").lower():
                        direct.extend(clean(u) for u in locs(additional.content)
                                      if self.can(src, clean(u)))
                except (ValueError, httpx.HTTPError, ET.ParseError):
                    continue
        return [{"url": url} for url in dict.fromkeys(direct)]

    async def html_index(self, client: httpx.AsyncClient, src: Source) -> list[dict]:
        r = await self.get(client, src.index, src)
        if "html" not in r.headers.get("content-type", "").lower():
            raise ValueError("Publisher index is not public HTML")
        soup = BeautifulSoup(r.content, "html.parser")
        rows = {}
        # QuantConnect library uses static div.article cards with onclick
        # location.href, not ordinary <a> tags. Parse only a literal same-host
        # path, NEVER evaluate the JavaScript or fetch embedded instructions.
        for card in soup.select(".article[onclick]"):
            action = card.get("onclick", "")
            match = re.search(r"location\.href\s*=\s*[\'\"]([^\'\"]+)[\'\"]", action)
            if not match:
                continue
            url = clean(urljoin(src.index, match.group(1)))
            if not self.can(src, url):
                continue
            title = re.sub(r"\s+", " ", (card.select_one("h3") or card).get_text(" ", strip=True))
            rows.setdefault(url, {"url": url, "index_title": title})
        for a in soup.select("a[href]"):
            url = clean(urljoin(src.index, a.get("href", "")))
            if url == clean(src.index) or not self.can(src, url):
                continue
            title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
            title = title or url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
            rows.setdefault(url, {"url": url, "index_title": title})
        return list(rows.values())

    async def substack_fallback(self, client: httpx.AsyncClient) -> list[dict]:
        """Publisher's own named Substack RSS, never a scraper mirror or WAF bypass."""
        from email.utils import parsedate_to_datetime

        url = "https://quantifiedstrategies.substack.com/feed"
        async with self.sem:
            response = await client.get(url, follow_redirects=False)
        if response.is_redirect or response.url.host != "quantifiedstrategies.substack.com":
            raise ValueError("Substack feed redirect or host mismatch")
        response.raise_for_status()
        if len(response.content) > MAX_XML or "xml" not in response.headers.get(
                "content-type", "").lower():
            raise ValueError("Publisher fallback is not a valid RSS response")
        root = ET.fromstring(response.content)
        results = []
        for item in root.findall("./channel/item"):
            link = clean((item.findtext("link") or "").strip())
            parsed = urlparse(link)
            if parsed.scheme != "https" or parsed.hostname != "quantifiedstrategies.substack.com":
                continue
            if not parsed.path.startswith("/p/"):
                continue
            title = (item.findtext("title") or "").strip()
            if not interest(title, parsed.path):
                continue
            raw = (item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
                   or item.findtext("description") or "")
            soup = BeautifulSoup(raw[:MAX_HTML], "html.parser")
            text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
            segments = [
                re.sub(r"\s+", " ", x.get_text(" ", strip=True))
                for x in soup.select("p,li")
            ]
            if len(text) < 160:
                continue
            dt = None
            try:
                dt = parsedate_to_datetime(item.findtext("pubDate") or "")
                if dt.tzinfo is None:
                    dt = None
            except (ValueError, TypeError):
                pass
            market, family = classify(title, parsed.path)
            contract, state = CONTRACTS[market]
            results.append({
                "id": sha(link)[:20], "source_key": "quantified_strategies",
                "url": link, "title": title,
                "published_at": dt.isoformat() if dt else None,
                "captured_at": now(), "content_sha256": sha(text),
                "source_revision": None,
                "source_kind": "ORIGINAL_PUBLISHER_SUBSTACK_RSS_CURRENT_CAPTURE",
                "market": market, "family": family,
                **rules(title, [x for x in segments if 25 <= len(x) <= 750]),
                "data_contract_hint": contract, "data_state": state,
                "experimental_disposition": "DISCOVERY_ONLY_NO_WARDEN_ATTEMPT",
                "review_notes": "Publisher's public RSS, not main website; rules need independent fidelity review.",
            })
        return results

    async def github(self, client: httpx.AsyncClient, src: Source) -> list[dict]:
        response = await self.get(client, src.index, src, max_bytes=500_000)
        commit = response.json().get("sha", "")
        if not re.fullmatch(r"[a-f0-9]{40}", commit):
            raise ValueError("Cannot pin public repo to a valid immutable commit")
        prefix = "tests/functional/strategies"
        root_url = f"https://api.github.com/repos/cloudQuant/backtrader/contents/{prefix}?ref={commit}"
        # Only source-identifying GitHub API query parameters are permitted.
        root_r = await self._github_api(client, root_url, src)
        folders = [x for x in root_r if x.get("type") == "dir"
                   and re.fullmatch(r"[a-f0-9]{40}", x.get("sha", ""))]
        if len(folders) > 32:
            raise ValueError("Unexpected public strategy root category count")
        out = []
        for directory in folders:
            tree_url = f"https://api.github.com/repos/cloudQuant/backtrader/git/trees/{directory['sha']}"
            tree = await self.get(client, tree_url, src, max_bytes=MAX_XML)
            data = tree.json()
            if data.get("sha") != directory["sha"] or data.get("truncated"):
                raise ValueError("Immutable GitHub subtree mismatch")
            for item in data.get("tree", []):
                name = item.get("path", "")
                blob = item.get("sha", "")
                if item.get("type") != "blob" or not name.startswith("test_") or not name.endswith(".py"):
                    continue
                if not re.fullmatch(r"[0-9a-f]{40}", blob):
                    continue
                path = f"{prefix}/{directory['name']}/{name}"
                title = re.sub(r"^test_\d+_", "", name.removesuffix(".py"))
                title = title.replace("_", " ").title()
                out.append({
                    "url": f"https://github.com/cloudQuant/backtrader/blob/{commit}/{quote(path, safe='/')}",
                    "index_title": title, "code_blob_sha": blob,
                    "commit_sha": commit, "code_path": path,
                })
        return out

    async def _github_api(self, client: httpx.AsyncClient, url: str, src: Source) -> list:
        p = urlparse(url)
        if p.hostname != src.host or p.scheme != "https" or not p.path.startswith(src.prefix):
            raise ValueError("Unapproved GitHub API path")
        if not re.fullmatch(r"ref=[0-9a-f]{40}", p.query):
            raise ValueError("Unpinned GitHub branch listing")
        async with self.sem:
            r = await client.get(url, follow_redirects=False)
        r.raise_for_status()
        if r.is_redirect or r.url.host != src.host or len(r.content) > MAX_XML:
            raise ValueError("Invalid GitHub response")
        if not isinstance(r.json(), list):
            raise ValueError("GitHub category listing malformed")
        return r.json()

    def prioritize(self, src: Source, docs: list[dict]) -> list[dict]:
        ranked = []
        for row in docs:
            u = row["url"]
            name = row.get("index_title") or urlparse(u).path.rsplit("/", 1)[-1].replace("-", " ")
            if src.kind == "github":
                eligible = interest(name, row.get("code_path", ""))
            else:
                eligible = self.can(src, u) and interest(name, urlparse(u).path)
            if not eligible:
                continue
            key = (name + " " + u).lower()
            preference = sum(word in key for word in (
                "nasdaq", "forex", "gold", "breakout", "opening", "mean",
                "vwap", "pairs", "momentum", "trend", "ftse", "index",
                "crypto", "dual", "arb", "eurusd",
            ))
            preferred = int(any(slug in u for slug in PREFERRED_PATHS.get(src.key, ())))
            ranked.append((-preferred, -preference, name.lower(), u, row))
        ranked.sort(key=lambda v: v[:4])
        return [x[4] for x in ranked]

    async def article(self, client: httpx.AsyncClient, src: Source,
                      row: dict) -> dict | None:
        if src.kind == "github":
            title = row["index_title"]
            market, family = classify(title, row["code_path"])
            contract, data_state = CONTRACTS[market]
            return {
                "id": sha(row["url"])[:20], "source_key": src.key,
                "url": row["url"], "title": title, "published_at": None,
                "captured_at": now(), "content_sha256": row["code_blob_sha"],
                "source_revision": row["commit_sha"], "source_kind": "PINNED_CODE_TEST",
                "market": market, "family": family, "timeframe_hint": None,
                "entry_excerpt": "", "exit_excerpt": "",
                "rule_state": "CODE_ONLY_UNREVIEWED",
                "exact_source_equivalence_verified": False,
                "data_contract_hint": contract, "data_state": data_state,
                "experimental_disposition": "DISCOVERY_ONLY_NO_WARDEN_ATTEMPT",
                "review_notes": "Source regression code is not proven alpha and is never executed by this collector.",
            }
        response = await self.get(client, row["url"], src)
        if "html" not in response.headers.get("content-type", "").lower():
            raise ValueError("Article did not return public HTML")
        soup = BeautifulSoup(response.content, "html.parser")
        heading, text, blocks = extract(soup)
        if len(text) < 180:
            return None
        title = (row.get("index_title") or heading or row["url"].split("/")[-2])[:230]
        if not interest(title, urlparse(row["url"]).path):
            return None
        market, family = classify(title, urlparse(row["url"]).path)
        contract, data_state = CONTRACTS[market]
        return {
            "id": sha(row["url"])[:20], "source_key": src.key,
            "url": row["url"], "title": title,
            "published_at": published(soup), "captured_at": now(),
            "content_sha256": sha(text), "source_revision": None,
            "source_kind": "ORIGINAL_PUBLISHER_CURRENT_CAPTURE",
            "market": market, "family": family,
            **rules(title, blocks), "data_contract_hint": contract,
            "data_state": data_state, "experimental_disposition": "DISCOVERY_ONLY_NO_WARDEN_ATTEMPT",
            "review_notes": "Excerpts are source substrings, not independently verified entry/exit timing or alpha.",
        }

    async def collect(self, target: int = 50) -> dict:
        if not 1 <= target <= 80:
            raise ValueError("Shortlist target outside 1..80")
        all_rows = []
        async with httpx.AsyncClient(timeout=24, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xml,application/json",
        }, limits=httpx.Limits(max_connections=8, max_keepalive_connections=5)) as client:
            for src in SOURCES:
                await self.check_robots(client, src)
                if self.robots.get(src.key) is False:
                    self.health.append({"source": src.key, "status": "ROBOTS_UNKNOWN",
                                        "discovered": 0, "fetched": 0})
                    continue
                try:
                    if src.kind == "github":
                        docs = await self.github(client, src)
                    elif src.kind == "html":
                        docs = await self.html_index(client, src)
                    else:
                        docs = await self.sitemap(client, src)
                except (ValueError, KeyError, TypeError, ET.ParseError, httpx.HTTPError) as e:
                    if src.key == "cloudquant_backtrader":
                        previous = self.seed_indexes.get(src.key, [])
                        valid = [x for x in previous if
                                 isinstance(x, dict) and
                                 re.fullmatch(r"[0-9a-f]{40}", x.get("code_blob_sha", "")) and
                                 re.fullmatch(r"[0-9a-f]{40}", x.get("commit_sha", "")) and
                                 x.get("code_path", "").startswith("tests/functional/strategies/") and
                                 x.get("url", "").startswith(
                                     "https://github.com/cloudQuant/backtrader/blob/"
                                     + x["commit_sha"] + "/")]
                        if valid and len(valid) == len(previous) and len(valid) <= 2000:
                            docs = valid
                            self.indexes[src.key] = docs
                            selected = self.prioritize(src, docs)[:self.limits.get(src.key, 10)]
                            records = [await self.article(client, src, row) for row in selected]
                            self.health.append({
                                "source": src.key, "status": "SHA_PINNED_PREVIOUS_CAPTURE",
                                "reason": "Public GitHub API unavailable; immutable prior SHA index reused",
                                "discovered": len(docs), "fetched": len(selected),
                                "accepted": len(records),
                            })
                            all_rows.extend(x for x in records if x)
                            continue
                    if src.key == "quantified_strategies":
                        try:
                            fallback = await self.substack_fallback(client)
                            self.health.append({
                                "source": src.key, "status": "ORIGINAL_PUBLISHER_SUBSTACK_FALLBACK",
                                "reason": "Main site sitemap unavailable; no anti-bot bypass",
                                "discovered": len(fallback), "fetched": len(fallback),
                                "accepted": len(fallback),
                            })
                            self.indexes[src.key] = [
                                {"url": item["url"], "index_title": item["title"]}
                                for item in fallback
                            ]
                            all_rows.extend(fallback)
                            continue
                        except (ValueError, httpx.HTTPError, ET.ParseError):
                            pass
                    self.health.append({"source": src.key, "status": "INDEX_UNAVAILABLE",
                                        "reason": f"{type(e).__name__}: {str(e)[:130]}",
                                        "discovered": 0, "fetched": 0})
                    continue
                self.indexes[src.key] = docs
                eligible = self.prioritize(src, docs)
                take = eligible[:self.limits.get(src.key, 10)]
                status = {
                    "source": src.key, "status": "INDEXED", "index_url": src.index,
                    "discovered": len(docs), "strategy_like_urls": len(eligible),
                    "fetched": len(take), "accepted": 0, "errors": 0,
                }
                async def retrieve(row: dict) -> dict | None:
                    try:
                        return await self.article(client, src, row)
                    except (httpx.HTTPError, ValueError, TypeError, KeyError):
                        status["errors"] += 1
                        return None
                values = await asyncio.gather(*[retrieve(row) for row in take])
                accepted = [x for x in values if x]
                status["accepted"] = len(accepted)
                status["status"] = "OK" if accepted else "NO_PUBLIC_ARTICLE_DETAILS"
                self.health.append(status)
                all_rows.extend(accepted)
        by_url = {record["url"]: record for record in all_rows}
        ranked = sorted(by_url.values(),
                        key=lambda x: (-rank(x), x["source_key"], x["url"]))
        unique: dict[str, dict] = {}
        duplicates = []
        for doc in ranked:
            title_words = re.findall(r"[a-z0-9]+", doc["title"].lower())
            filtered = [w for w in title_words if len(w) > 2 and w not in (
                "trading", "strategy", "system", "strategies", "backtesting",
                "the", "with", "for", "using", "and", "free",
            )]
            signature = doc["market"] + ":" + doc["family"] + ":" + "-".join(sorted(set(filtered))[:9])
            if signature in unique:
                duplicates.append({"url": doc["url"], "duplicate_of": unique[signature]["url"]})
            else:
                unique[signature] = doc
        unique_rows = list(unique.values())
        shortlist = []
        source_counts = Counter()
        family_counts = Counter()
        chosen = set()
        # A broad archive pilot should represent EVERY readable publisher,
        # not just the highest-scoring first three sources. A lead remains
        # explicitly incomplete when its article contains no full rule.
        for source in SOURCES:
            for record in [r for r in unique_rows if r["source_key"] == source.key][:2]:
                if len(shortlist) >= target:
                    break
                shortlist.append(record)
                chosen.add(record["url"])
                source_counts[record["source_key"]] += 1
                family_counts[record["family"]] += 1
        for record in unique_rows:
            if len(shortlist) >= target:
                break
            if record["url"] in chosen:
                continue
            if source_counts[record["source_key"]] >= 13 or family_counts[record["family"]] >= 16:
                continue
            shortlist.append(record)
            chosen.add(record["url"])
            source_counts[record["source_key"]] += 1
            family_counts[record["family"]] += 1
        if len(shortlist) < target:
            for doc in unique_rows:
                if len(shortlist) >= target:
                    break
                if doc["url"] not in chosen:
                    shortlist.append(doc)
                    chosen.add(doc["url"])
        shortlist.sort(key=lambda doc: (-rank(doc), doc["source_key"], doc["url"]))
        for doc in shortlist:
            doc["score"] = rank(doc)
        return {
            "schema_version": "PRACTITIONER_ARCHIVE_V1",
            "captured_at": now(),
            "warden_trials_consumed": 0,
            "fidelity_policy": "SOURCE_LEADS_NOT_READY_FOR_WARDEN",
            "source_health": self.health, "source_indexes": self.indexes,
            "reviewed_records": len(all_rows),
            "reviewed_leads": all_rows,
            "unique_strategy_titles": len(unique_rows),
            "duplicates": duplicates,
            "shortlist_count": len(shortlist), "shortlist": shortlist,
        }


def markdown(result: dict) -> str:
    lines = [
        "# Original practitioner archive — strategy research intake",
        "",
        f"Capture: {result['captured_at']}. No Warden trials consumed.",
        "",
        f"Reviewed {result['reviewed_records']} original articles/code identifiers, "
        f"shortlisted {result['shortlist_count']}, "
        f"identified {len(result['duplicates'])} near-duplicate titles.",
        "",
        "## Source inventory",
        "",
        "| Source | Index links | Reviewed | Kept | Status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for h in result["source_health"]:
        lines.append(f"| {h['source']} | {h.get('discovered', 0)} | "
                     f"{h.get('fetched', 0)} | {h.get('accepted', 0)} | {h['status']} |")
    lines += [
        "",
        "## Ranked candidate leads (source-backed, not executable qualifications)",
        "",
        "| Rank | Original URL and title | Market | Family | Rule evidence |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for i, r in enumerate(result["shortlist"], 1):
        title = r["title"].replace("|", " ").replace("\n", " ")
        lines.append(f"| {i} | [{title[:60]}]({r['url']}) | "
                     f"{r['market']} | {r['family']} | {r['rule_state']} |")
    lines += [
        "", "## Scientific boundaries", "",
        "These are DISCOVERY leads. Source-rule excerpts are not verified economic hypotheses.",
        "Current captures do not establish historical source-vintage availability.",
        "Instrument conversion from equity ETFs or futures to CFD/perpetual execution requires an explicit adaptation.",
        "Code-test examples are not validated trading algorithms and are never executed by this miner.",
        "Any future Warden hypothesis requires a frozen mechanism, source-faithful entries/exits,",
        "timeframe, data provenance, transaction costs and multiplicity controls before a trial.", "",
    ]
    return "\n".join(lines).rstrip() + "\n"


async def run(output: Path, *, target: int = 50,
              per_source: int | None = None,
              seed_catalog: Path | None = None) -> dict:
    limits = {k: min(cap, per_source) for k, cap in CAPS.items()} if per_source else None
    result = await ArchiveScout(limits=limits, seed_catalog=seed_catalog).collect(target=target)
    output.mkdir(parents=True, exist_ok=True)
    (output / "catalog.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    (output / "shortlist.json").write_text(json.dumps(result["shortlist"], indent=2, ensure_ascii=False) + "\n")
    (output / "report.md").write_text(markdown(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Original strategy archives, read-only Warden")
    parser.add_argument("--output", type=Path, default=Path("runs/archive_discovery"))
    parser.add_argument("--target", type=int, default=50)
    parser.add_argument("--per-source", type=int, default=None)
    parser.add_argument("--seed-catalog", type=Path, default=None,
                        help="Re-use previous immutable SHA GitHub index if API rate limited")
    args = parser.parse_args()
    result = asyncio.run(run(args.output, target=args.target,
                             per_source=args.per_source, seed_catalog=args.seed_catalog))
    print(json.dumps({
        "status": "SOURCE_DISCOVERY_COMPLETED",
        "shortlist": result["shortlist_count"],
        "records_reviewed": result["reviewed_records"],
        "source_health": result["source_health"],
        "warden_trials_consumed": 0,
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
