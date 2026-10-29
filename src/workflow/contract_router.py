"""Deterministic, contract-bound routing and data/execution feasibility checks.

The principal owns Warden contract files. This module ONLY reads existing pinned
exploratory data and contracts; it never loads a protected holdout or adjusts
statistical thresholds. Unavailable execution observables are explicit blockers
for strategies that require them, never synthesized as zero-cost quotes.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pyarrow.compute as pc
import pyarrow.parquet as pq
import yaml


class RouteBlocked(ValueError):
    """The published strategy cannot be evaluated on a compatible Warden contract."""


@dataclass(frozen=True)
class TemplateRoute:
    mode: str
    contract_id: str
    market: Literal["crypto_perps", "indices"]
    timeframe: Literal["5m", "1h", "4h", "1d"]
    hold_bars: int
    rebalance_bars: int | None
    required_columns: tuple[str, ...]
    universe: Literal["crypto_eight", "crypto_broad", "indices"]
    fidelity_family: str
    direction: Literal["long", "short", "both"] = "both"


# Exact, reviewed templates. A route does not imply that a source faithfully
# describes this implementation; source-rule verification is mandatory first.
ROUTES = {
    "shock_reversal": TemplateRoute("shock_reversal", "CRYPTO_PERPS_1H_V2",
        "crypto_perps", "1h", 4, None, ("close", "volume"), "crypto_eight", "shock_reversal"),
    "volume_breakout": TemplateRoute("volume_breakout", "CRYPTO_PERPS_1H_V2",
        "crypto_perps", "1h", 12, None, ("high", "low", "close", "volume"), "crypto_eight", "volume_breakout"),
    "dip_7d": TemplateRoute("dip_7d", "CRYPTO_PERPS_1H_V2",
        "crypto_perps", "1h", 4, None, ("high", "close"), "crypto_eight", "dip_7d", "long"),
    "rsi2_trend_pullback": TemplateRoute("rsi2_trend_pullback", "CRYPTO_PERPS_1H_V2",
        "crypto_perps", "1h", 12, None, ("close",), "crypto_eight", "rsi2_trend_pullback"),
    "donchian_trend": TemplateRoute("donchian_trend", "CRYPTO_PERPS_1H_V2",
        "crypto_perps", "1h", 24, None, ("high", "low", "close"), "crypto_eight", "donchian_trend"),
    "vol_compression_breakout": TemplateRoute("vol_compression_breakout", "CRYPTO_PERPS_1H_V2",
        "crypto_perps", "1h", 8, None, ("high", "low", "close"), "crypto_eight", "vol_compression_breakout"),
    # Broad 100-perp contract, explicitly not the old eight-asset simulation.
    "cross_section_momentum_7d": TemplateRoute("cross_section_momentum_7d", "CRYPTO_PERPS_TOP100_1H_V1",
        "crypto_perps", "1h", 24, 24, ("close", "volume"), "crypto_broad", "cross_section_momentum_7d"),
    "shock_reversal_5m": TemplateRoute("shock_reversal_5m", "CRYPTO_PERPS_5M_V1",
        "crypto_perps", "5m", 12, None, ("close", "volume"), "crypto_eight", "shock_reversal"),
    "donchian_trend_4h": TemplateRoute("donchian_trend_4h", "CRYPTO_PERPS_4H_V1",
        "crypto_perps", "4h", 6, None, ("high", "low", "close"), "crypto_eight", "donchian_trend"),
    "swing_breakout_1d": TemplateRoute("swing_breakout_1d", "CRYPTO_PERPS_1D_V1",
        "crypto_perps", "1d", 5, None, ("high", "low", "close"), "crypto_eight", "swing_breakout"),
    # Index signals must be intraday, not disguised crypto perpetual tests.
    "index_intraday_breakout_5m": TemplateRoute("index_intraday_breakout_5m", "INDICES_5M_V1",
        "indices", "5m", 12, None, ("high", "low", "close"), "indices", "intraday_breakout"),
}
ALLOWED_CONTRACT_IDS = frozenset(r.contract_id for r in ROUTES.values())
CORE_COLUMNS = ("timestamp", "asset", "open", "high", "low", "close", "volume")


def route_template(mode: str, *, source_market: str, source_timeframe: str,
                   hold_bars: int, rebalance_bars: int | None = None) -> TemplateRoute:
    if mode not in ROUTES:
        raise RouteBlocked("Unapproved strategy template")
    route = ROUTES[mode]
    if source_market != route.market:
        raise RouteBlocked(f"Source market {source_market!r} does not match {route.market!r}")
    if source_timeframe != route.timeframe:
        raise RouteBlocked(f"Source timeframe {source_timeframe!r} does not match {route.timeframe!r}")
    if hold_bars != route.hold_bars:
        raise RouteBlocked(f"Source hold {hold_bars} bars differs from reviewed {route.hold_bars} bars")
    if route.rebalance_bars is not None and rebalance_bars != route.rebalance_bars:
        raise RouteBlocked("Source rebalance cadence does not match reviewed strategy")
    if route.rebalance_bars is None and rebalance_bars not in (None, 0):
        raise RouteBlocked("Source rebalances explicitly but fixed strategy does not")
    return route


def _read_manifest(path: Path) -> dict:
    if not path.is_file():
        raise RouteBlocked(f"Required manifest unavailable: {path.name}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RouteBlocked("Malformed dataset manifest")
    return raw


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def contract_preflight(checkout: Path, route: TemplateRoute) -> dict:
    """Audit the exact registered snapshot, read-only, without any holdout reads.

    Large Parquet files are scanned via selected columns; the whole file hash is
    computed to enforce the immutable contract before Warden registration.
    """
    checkout = checkout.resolve()
    if route.contract_id not in ALLOWED_CONTRACT_IDS:
        raise RouteBlocked("Unapproved Warden contract ID")
    contract_path = checkout / "contracts" / (route.contract_id.lower() + ".yaml")
    manifest_path = checkout / "contracts/datasets" / (route.contract_id + ".json")
    if not contract_path.is_file():
        raise RouteBlocked("Warden contract missing; cannot fall back to another market")
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    manifest = _read_manifest(manifest_path)
    if not isinstance(contract, dict):
        raise RouteBlocked("Malformed Warden contract")
    if contract.get("contract_id") != route.contract_id or manifest.get("contract_id") != route.contract_id:
        raise RouteBlocked("Contract-to-manifest identity mismatch")
    if contract.get("asset_class") != route.market or contract.get("frequency") != route.timeframe:
        raise RouteBlocked("Market/frequency mismatch in protected contract")
    if contract.get("data_provenance") != "verified_market" or manifest.get("provenance") != "verified_market":
        raise RouteBlocked("Data origin not marked verified_market")
    expected = contract.get("data_snapshot_sha256")
    if not isinstance(expected, str) or len(expected) != 64 or manifest.get("sha256") != expected:
        raise RouteBlocked("Contract and manifest SHA-256 mismatch")
    if manifest.get("path") != contract.get("exploratory_data_path"):
        raise RouteBlocked("Manifest exploratory path mismatch")
    rel = Path(str(manifest["path"]))
    if rel.is_absolute() or ".." in rel.parts or not str(rel).startswith("data/exploratory/"):
        raise RouteBlocked("Unsafe dataset path")
    file = (checkout / rel).resolve()
    if not file.is_relative_to(checkout) or not file.is_file():
        raise RouteBlocked("Pinned exploratory dataset missing")
    if _hash_file(file) != expected:
        raise RouteBlocked("Exploratory data digest drift")
    if contract.get("execution_mode") not in ("NEXT_BAR", "QUOTE_SIDE"):
        raise RouteBlocked("Unsupported execution mode")
    if int(contract.get("execution_delay_bars", 0)) < 1:
        raise RouteBlocked("Warden NEXT_BAR latency gate missing")

    table = pq.read_table(
        file, columns=list(CORE_COLUMNS) + (["funding_rate"] if route.market == "crypto_perps" else []),
        memory_map=True,
    )
    missing = set(CORE_COLUMNS + route.required_columns) - set(table.column_names)
    if missing:
        raise RouteBlocked(f"Required dataset fields missing: {sorted(missing)}")
    if table.num_rows == 0:
        raise RouteBlocked("Empty exploratory market dataset")
    nulls = {name: table[name].null_count for name in table.column_names}
    if any(nulls[col] > 0 for col in ("timestamp", "asset", "open", "high", "low", "close")):
        raise RouteBlocked("Missing timestamp, asset or OHLC observation")
    assets = pc.count_distinct(table["asset"]).as_py()
    if route.universe == "crypto_eight" and assets != 8:
        raise RouteBlocked(f"Eight-symbol profile expected eight instruments, found {assets}")
    if route.universe == "crypto_broad" and assets < 40:
        raise RouteBlocked("Broad strategy requires >=40 observed assets")
    if route.universe == "indices" and assets < 2:
        raise RouteBlocked("Indices strategy requires multiple observed instruments")
    # Only pinned exploratory data is inspected; never open holdout paths.
    times = table["timestamp"].to_pylist()
    symbols = table["asset"].to_pylist()
    if len(set(zip(times, symbols))) != len(times):
        raise RouteBlocked("Duplicate (timestamp, asset) market bars")
    high, low, opn, close = (table[k].to_numpy(zero_copy_only=False) for k in ("high", "low", "open", "close"))
    import numpy as np
    if (not np.isfinite(high).all() or not np.isfinite(low).all()
            or not np.isfinite(opn).all() or not np.isfinite(close).all()):
        raise RouteBlocked("Nonfinite price observations")
    if np.any(low > high) or np.any(opn < low) or np.any(opn > high) or np.any(close < low) or np.any(close > high):
        raise RouteBlocked("Invalid OHLC bar relationships")
    timestamps = sorted(set(times))
    cohort = None
    if route.universe == "crypto_broad":
        # This is a point-in-time inception cohort, NOT assets selected for
        # surviving until the end of the validation sample.
        initial = timestamps[0]
        available_then = sorted({symbol for ts, symbol in zip(times, symbols) if ts == initial})
        if len(available_then) < 40:
            raise RouteBlocked("Fewer than 40 ex-ante broad-universe instruments")
        count_by_asset = Counter(symbols)
        if any(count_by_asset[s] != len(timestamps) for s in available_then):
            raise RouteBlocked("Inception universe has data gaps: sparse execution unsupported")
        cohort = available_then
    elif route.universe == "indices":
        # RTH template only supports NQ and ES on the US time/calendar.
        cohort = sorted({"NQ", "ES"} & set(symbols))
        if not cohort:
            raise RouteBlocked("No supported NQ/ES indices in pinned market file")
    start = datetime.fromisoformat(str(contract["train_start"]).replace("Z", "+00:00"))
    val_start = datetime.fromisoformat(str(contract["val_start"]).replace("Z", "+00:00"))
    val_end = datetime.fromisoformat(str(contract["val_end"]).replace("Z", "+00:00"))
    holdout_start = datetime.fromisoformat(str(contract["holdout_start"]).replace("Z", "+00:00"))
    if not (start < val_start < val_end <= holdout_start):
        raise RouteBlocked("Invalid time splits")
    if min(timestamps) > start or max(timestamps) >= holdout_start:
        raise RouteBlocked("Exploratory data touches holdout or does not reach training start")
    if max(timestamps) < val_end - __import__("datetime").timedelta(days=1):
        raise RouteBlocked("Dataset misses final validation interval")
    per_side_cost_bps = float(contract["taker_fee_bps"]) + float(contract["slippage_bps"])
    if not math.isfinite(per_side_cost_bps) or per_side_cost_bps <= 0:
        raise RouteBlocked("Missing conservative Warden execution-cost floor")
    if route.market == "crypto_perps" and "funding_rate" not in table.column_names:
        raise RouteBlocked("Perpetual funding data missing")
    if route.market == "crypto_perps" and nulls.get("funding_rate", 0):
        raise RouteBlocked("Incomplete perpetual funding series")
    return {
        "contract_id": route.contract_id, "data_sha256": expected,
        "data_path": str(rel), "provenance": "verified_market",
        "observations": table.num_rows, "assets": assets,
        "available_symbols": sorted(set(symbols)), "ex_ante_symbols": cohort,
        "first_timestamp": min(timestamps).isoformat(),
        "last_timestamp": max(timestamps).isoformat(),
        "nulls": nulls,
        "execution_mode": contract["execution_mode"],
        "next_bar_delay": int(contract["execution_delay_bars"]),
        "one_way_modeled_cost_bps": per_side_cost_bps,
        "round_trip_modeled_cost_bps": 2 * per_side_cost_bps,
        "stress_cost_2x_bps": 4 * per_side_cost_bps,
        "stress_cost_3x_bps": 6 * per_side_cost_bps,
        "quote_observations": False,
        "execution_qualification": "MODELED_COSTS_NOT_FILL_CALIBRATED",
        "train_start": start.isoformat(),
        "validation_start": val_start.isoformat(),
        "validation_end": val_end.isoformat(),
        "protected_holdout_accessed": False,
    }


def require_observable_execution(source_text: str, route: TemplateRoute, audit: dict) -> None:
    """Fail closed on requirements not represented by this OHLCV/funding dataset."""
    low = source_text.lower()
    orderbook_terms = (
        "order book", "orderbook", "level 2", "l2 data",
        "bid-ask", "bid ask", "queue position", "order flow imbalance",
        "maker rebates", "market making", "markout",
    )
    if any(term in low for term in orderbook_terms):
        raise RouteBlocked("Source requires unavailable quote/order-book or maker execution fields")
    if route.market == "crypto_perps" and ("open interest" in low or "liquidation data" in low):
        raise RouteBlocked("Source requires unprovided historical open-interest/liquidations")
    if audit["execution_qualification"] != "MODELED_COSTS_NOT_FILL_CALIBRATED":
        raise RouteBlocked("Unrecognized execution evidence state")
