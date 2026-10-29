"""Source-to-executable fidelity gate.

An LLM must quote the original entry and exit, identify the source market,
timeframe and exact holding/rebalance rule. Literal quotes are mechanically
checked against the captured publisher text, then compared with an immutable,
reviewed strategy route. A keyword match alone is never enough.

This gate deliberately abstains on ambiguous, incomplete or long-horizon
sources. It does not "adapt" a strategy into a different timeframe or market.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from src.core.models import StrictModel
from src.workflow.contract_router import ROUTES, RouteBlocked, TemplateRoute, route_template


class SourceRule(StrictModel):
    source_market: Literal["crypto_perps", "indices", "equities", "fx", "unknown"]
    source_timeframe: Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d", "unknown"]
    side: Literal["long", "short", "both", "unknown"]
    holding_bars: int = Field(ge=1, le=3000)
    rebalance_bars: int | None = Field(default=None, ge=1, le=3000)
    entry_quote: str = Field(min_length=18, max_length=280)
    exit_quote: str = Field(min_length=13, max_length=280)
    source_limitations: list[str] = Field(default_factory=list, max_length=4)
    target_symbols: list[str] = Field(default_factory=list, max_length=20)


# These are the strategy logic primitives actually implemented; weak keyword
# overlap is rejected, including "trend" alone for a Donchian breakout.
REQUIRED_ENTRY_SEMANTICS = {
    "shock_reversal": (("reversal", "fade", "opposite"), ("volume",), ("volatility", "sigma", "std")),
    "shock_reversal_5m": (("reversal", "fade", "opposite"), ("volume",), ("volatility", "sigma", "std")),
    "volume_breakout": (("breakout", "break above", "break below"), ("volume",)),
    "dip_7d": (("dip", "drawdown", "drop"), ("seven day", "seven-day", "7-day", "7 day", "week")),
    "rsi2_trend_pullback": (("rsi",), ("moving average", "ema", "trend")),
    "donchian_trend": (("donchian", "channel breakout", "high breakout", "prior high"),),
    "donchian_trend_4h": (("donchian", "channel breakout", "high breakout", "prior high"),),
    "vol_compression_breakout": (("compression", "squeeze", "low volatility"), ("breakout",)),
    "cross_section_momentum_7d": (("cross sectional", "cross-sectional", "ranking", "rank"),
                                  ("momentum", "relative strength")),
    "swing_breakout_1d": (("breakout", "break above", "break below"), ("20 day", "20-day", "20 trading day")),
    "index_intraday_breakout_5m": (("breakout", "break above", "break below"), ("index", "nasdaq", "nq", "s&p", "es", "dax", "nikkei", "opening")),
}
REQUIRED_EXIT = ("hold", "exit", "close", "rebalance", "liquidat", "sell", "cover", "bars", "hours", "days")
# Numbers are fixed by the reviewed executable, not optimizer choices.
FIXED_ENTRY_TERMS = {
    "shock_reversal": ("2.5", "1.5"),
    "shock_reversal_5m": ("2.5", "1.5"),
    "volume_breakout": ("72", "1.5"),
    "dip_7d": ("12%",),
    "rsi2_trend_pullback": ("rsi(2)", "10", "90"),
    "donchian_trend": ("240",),
    "donchian_trend_4h": ("60",),
    "vol_compression_breakout": ("0.55",),
    "cross_section_momentum_7d": ("7-day",),
    "swing_breakout_1d": ("20",),
    "index_intraday_breakout_5m": ("12",),
}
INDEX_ALIASES = {
    "NQ": ("nasdaq", "nq", "us100"),
    "ES": ("s&p 500", "sp500", "s&p500", "es", "us500"),
}
SYMBOL_ALIASES = {
    "BTCUSDT": ("bitcoin", "btcusdt", "btc"),
    "ETHUSDT": ("ethereum", "ethusdt", "eth"),
    "SOLUSDT": ("solana", "solusdt", "sol"),
    "ADAUSDT": ("cardano", "adausdt", "ada"),
    "BNBUSDT": ("binance coin", "bnbusdt", "bnb"),
    "DOGEUSDT": ("dogecoin", "dogeusdt", "doge"),
    "XRPUSDT": ("xrp", "xrpusdt"),
    "AVAXUSDT": ("avalanche", "avaxusdt", "avax"),
}



def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _quote_in_source(quote: str, original_text: str) -> bool:
    return _norm(quote) in _norm(original_text)


def _source_market(original_text: str, title: str) -> str:
    heading = title.casefold()
    crypto_terms = ("crypto", "bitcoin", "btc", "ethereum", "ethusdt", "altcoin", "perpetual", "binance")
    index_terms = ("nasdaq", "s&p 500", "sp500", "nq", "es futures", "dax", "nikkei", "hk33", "indices", "index")
    equity_terms = ("equity", "etf", "stock", "spy", "qqq")
    if any(term in heading for term in ("stocks", "shares", "etf", "qqq", "spy", "equity")):
        return "equities"
    if any(term in heading for term in crypto_terms):
        return "crypto_perps"
    if any(term in heading for term in index_terms):
        return "indices"
    if any(term in heading for term in equity_terms):
        return "equities"
    # No guessing from a throwaway crypto example in the footer.
    lead = original_text[:550].casefold()
    if any(term in lead for term in crypto_terms):
        return "crypto_perps"
    if any(term in lead for term in index_terms):
        return "indices"
    if any(term in lead for term in equity_terms):
        return "equities"
    return "unknown"


def _source_timeframe(text: str) -> str | None:
    # This is the signal bar timeframe, not the holding period. A single
    # source can discuss multiple bar periods; ambiguity must block.
    patterns = {
        "5m": (r"\b5[- ]?min(?:ute)?(?:s|ute)?\s*(?:bars?|candles?|chart|data|timeframe)", r"\b5m\s*(?:bars?|candles?|chart|timeframe)"),
        "1h": (r"\b1[- ]?h(?:our)?\s*(?:bars?|candles?|chart|data|timeframe)", r"\bhourly\s*(?:bars?|candles?|chart|data|timeframe)"),
        "4h": (r"\b4[- ]?h(?:our)?\s*(?:bars?|candles?|chart|data|timeframe)",),
        "1d": (r"\bdaily\s*(?:bars?|candles?|chart|data|timeframe)", r"\b1[- ]?day\s*(?:bars?|candles?|chart|timeframe)"),
        "30m": (r"\b30[- ]?min(?:ute)?(?:s)?\s*(?:bars?|candles?|chart|data|timeframe)",),
        "15m": (r"\b15[- ]?min(?:ute)?(?:s)?\s*(?:bars?|candles?|chart|data|timeframe)",),
        "1m": (r"\b1[- ]?min(?:ute)?(?:s)?\s*(?:bars?|candles?|chart|data|timeframe)",),
    }
    found = {timeframe for timeframe, regexes in patterns.items()
             if any(re.search(pattern, text.casefold()) for pattern in regexes)}
    return next(iter(found)) if len(found) == 1 else None


def _claimed_horizon(text: str, timeframe: str) -> int | None:
    """Return number of source bar intervals; ambiguous or unexpressed -> None."""
    repl = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
            "six": "6", "seven": "7", "eight": "8", "twelve": "12"}
    words = r"one|two|three|four|five|six|seven|eight|twelve"
    unit = r"minutes?|mins?|hours?|hrs?|days?|weeks?|bars?|candles?"
    expr = (
        r"(?:hold(?:s|ing)?(?:\s+for)?|exit\s+after|close\s+after|"
        r"rebalance(?:s|d)?\s+every|rebalanced\s+every|after)\s+"
        r"(" + r"\d{1,3}|" + words + r")\s*(" + unit + r")"
    )
    matches = re.findall(expr, text.casefold())
    resolutions = []
    bar_minutes = {"1m": 1, "5m": 5, "15m": 15, "30m": 30,
                   "1h": 60, "4h": 240, "1d": 1440}
    for raw, u in matches:
        count = int(repl.get(raw, raw))
        minutes = (count if u.startswith(("min", "bar", "candle")) and not u.startswith(("bar", "candle"))
                   else count * (60 if u.startswith(("hour", "hr")) else
                                 1440 if u.startswith("day") else
                                 10080 if u.startswith("week") else
                                 bar_minutes[timeframe]))
        if minutes % bar_minutes[timeframe] != 0:
            return None
        resolutions.append(minutes // bar_minutes[timeframe])
    return resolutions[0] if len(set(resolutions)) == 1 and resolutions else None


def validate_source_rule(template_id: str, rule: SourceRule, evidence, raw_records: list[dict]
                         ) -> TemplateRoute:
    """Fail closed if model-provided quoted facts or contract choice are unsupported."""
    if template_id not in ROUTES:
        raise RouteBlocked("Unknown frozen template")
    sources = {s.source_id: s for s in evidence}
    records = {
        "social_" + item["platform"] + "_" + item["post_id"]: item
        for item in raw_records
        if isinstance(item, dict) and "platform" in item and "post_id" in item
    }
    # A single source must substantiate BOTH entry AND exit. Combining one
    # publisher's entry with another's exit is a newly invented strategy.
    matching = []
    for sid, source in sources.items():
        if sid not in records:
            continue
        record = records[sid]
        original = record.get("text", "")
        if not _quote_in_source(rule.entry_quote, original) or not _quote_in_source(rule.exit_quote, original):
            continue
        if str(record.get("authenticity", "")).startswith("CODE_ONLY_"):
            raise RouteBlocked("Unmapped executable code requires a separate reviewed strategy")
        market = _source_market(original, record.get("title", ""))
        if market == "unknown" or market != rule.source_market:
            raise RouteBlocked("Market not supported by the original source")
        source_tf = _source_timeframe(original)
        if source_tf is None or source_tf != rule.source_timeframe:
            raise RouteBlocked("Source bar timeframe ambiguous or unsupported")
        quoted_entry = _norm(rule.entry_quote)
        if any(value not in quoted_entry for value in FIXED_ENTRY_TERMS[template_id]):
            raise RouteBlocked("Source entry omits a predeclared numeric trigger; cannot infer it")
        if any(not any(word in quoted_entry for word in group)
               for group in REQUIRED_ENTRY_SEMANTICS[template_id]):
            raise RouteBlocked("Quoted source entry does not match the executable rule family")
        if rule.side != ROUTES[template_id].direction:
            raise RouteBlocked("Source position direction differs from reviewed executable rule")
        quote = _norm(rule.entry_quote)
        if rule.side == "both" and not (
            ("long" in quote and "short" in quote)
            or ("buy" in quote and "sell" in quote)
            or ("high" in quote and "low" in quote)
        ):
            raise RouteBlocked("Reviewed long/short implementation requires BOTH directions in entry quote")
        if rule.side == "long" and not any(t in quote for t in ("buy", "long", "entry")):
            raise RouteBlocked("Source does not specify long entry")
        if rule.source_market == "indices":
            text_for_assets = _norm(record.get("title", "") + " " + original[:1100])
            if not rule.target_symbols or any(s not in INDEX_ALIASES for s in rule.target_symbols):
                raise RouteBlocked("Index source requires an explicit NQ/ES instrument list")
            if len(set(rule.target_symbols)) != len(rule.target_symbols):
                raise RouteBlocked("Repeated index target instrument")
            for symbol in rule.target_symbols:
                if not any(re.search(r"\b" + re.escape(alias) + r"\b", text_for_assets)
                           for alias in INDEX_ALIASES[symbol]):
                    raise RouteBlocked("Cited index source does not name target instrument")
        if rule.source_market == "crypto_perps":
            # A spot-only source cannot be relabeled a perpetual execution test.
            head = _norm(record.get("title", "") + " " + original[:1100])
            if not any(token in head for token in ("perpetual", "perps", "futures", "usd-m", "funding rate")):
                raise RouteBlocked("Spot/unspecified crypto rule is not a sourced perpetual strategy")
            selected = rule.target_symbols
            if selected:
                if len(selected) != len(set(selected)) or any(s not in SYMBOL_ALIASES for s in selected):
                    raise RouteBlocked("Unsupported, duplicate or unspecified crypto asset selection")
                for s in selected:
                    if not any(re.search(r"\b" + re.escape(alias) + r"\b", head)
                               for alias in SYMBOL_ALIASES[s]):
                        raise RouteBlocked("Source does not specify chosen target instrument")
            elif route_template(template_id, source_market=rule.source_market,
                                source_timeframe=rule.source_timeframe,
                                hold_bars=rule.holding_bars,
                                rebalance_bars=rule.rebalance_bars).universe == "crypto_eight":
                if not any(x in head for x in ("eight coins", "8 coins", "eight major", "8 major")):
                    raise RouteBlocked("No original multi-asset universe; cannot trade eight majors")
        if any(k in _norm(rule.exit_quote) for k in ("stop loss", "stop-loss", "take profit", "take-profit", "trailing stop")):
            raise RouteBlocked("Source includes an exit mechanism absent from the reviewed time-exit template")
        if not any(k in _norm(rule.exit_quote) for k in REQUIRED_EXIT):
            raise RouteBlocked("No documented author exit/holding rule")
        explicit_horizon = _claimed_horizon(rule.exit_quote, rule.source_timeframe)
        if explicit_horizon is None:
            raise RouteBlocked("Holding or rebalance duration not explicit in author's exit quote")
        if explicit_horizon != rule.holding_bars:
            raise RouteBlocked("Model holding bars contradict the cited source")
        matching.append(source)
    if not matching:
        raise RouteBlocked("No single original source contains both exact entry and exit quotes")
    route = route_template(
        template_id, source_market=rule.source_market,
        source_timeframe=rule.source_timeframe, hold_bars=rule.holding_bars,
        rebalance_bars=rule.rebalance_bars,
    )
    return route
