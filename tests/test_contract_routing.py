"""Contract routing, data provenance, economics, and author-source fidelity gates."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from src.core.models import Evidence, EvidenceKind
from src.workflow.contract_router import (
    ROUTES, RouteBlocked, contract_preflight, require_observable_execution, route_template,
)
from src.workflow.source_fidelity import SourceRule, validate_source_rule


def candidate_rule(**change):
    values = {
        "source_market": "crypto_perps", "source_timeframe": "1h",
        "side": "long", "holding_bars": 4,
        "entry_quote": "Entry when 12% drawdown below the prior seven-day high",
        "exit_quote": "exit after four hours",
        "target_symbols": ["BTCUSDT"],
    }
    values.update(change)
    return SourceRule(**values)


def original_post():
    text = (
        "Original Bitcoin perpetuals research using 1h bars. "
        "Entry when 12% drawdown below the prior seven-day high; "
        "exit after four hours. Fee and slippage were considered."
    )
    record = {
        "platform": "substack", "post_id": "original",
        "source_key": "trusted_author", "uri": "https://original.substack.com/p/original",
        "title": "Bitcoin perpetuals buy the dip", "text": text,
        "authenticity": "ORIGINAL_PUBLISHER_RSS_CURRENT_CAPTURE",
    }
    evidence = Evidence(
        source_id="social_substack_original", kind=EvidenceKind.HISTORICAL,
        uri=record["uri"], published_at="2026-05-01T00:00:00Z",
        available_at="2026-10-29T00:00:00Z", archived_at="2026-10-29T00:00:00Z",
        source_version="original", snippet=text, provider="original_substack",
        facts={"source_authenticity": record["authenticity"]},
    )
    return record, evidence


def test_source_fidelity_accepts_exact_original_perp_rule():
    record, evidence = original_post()
    route = validate_source_rule("dip_7d", candidate_rule(), [evidence], [record])
    assert route.contract_id == "CRYPTO_PERPS_1H_V2"
    assert route.direction == "long"


@pytest.mark.parametrize("rule", [
    candidate_rule(source_timeframe="5m"),
    candidate_rule(source_market="indices"),
    candidate_rule(holding_bars=12),
    candidate_rule(side="both"),
    candidate_rule(entry_quote="Somewhere in this source there might be a dip"),
    candidate_rule(target_symbols=["SOLUSDT"]),
])
def test_source_fidelity_rejects_mismatched_rules(rule):
    record, evidence = original_post()
    with pytest.raises(RouteBlocked):
        validate_source_rule("dip_7d", rule, [evidence], [record])


def test_source_fidelity_rejects_21_day_source_cadence_and_spot_transfer():
    record, evidence = original_post()
    slow = candidate_rule(exit_quote="exit after four hours")
    record["text"] = record["text"].replace("exit after four hours", "rebalance every 21 days")
    with pytest.raises(RouteBlocked, match="single original source"):
        validate_source_rule("dip_7d", slow, [evidence], [record])
    record, evidence = original_post()
    record["text"] = record["text"].replace("perpetuals", "spot")
    record["title"] = record["title"].replace("perpetuals", "spot")
    with pytest.raises(RouteBlocked, match="perpetual"):
        validate_source_rule("dip_7d", candidate_rule(), [evidence], [record])


def test_incompatible_market_timeframe_or_hold_never_autocorrected():
    with pytest.raises(RouteBlocked, match="Source market"):
        route_template("dip_7d", source_market="indices", source_timeframe="1h", hold_bars=4)
    with pytest.raises(RouteBlocked, match="Source timeframe"):
        route_template("dip_7d", source_market="crypto_perps", source_timeframe="5m", hold_bars=4)
    with pytest.raises(RouteBlocked, match="Source hold"):
        route_template("dip_7d", source_market="crypto_perps", source_timeframe="1h", hold_bars=24)
    assert route_template("cross_section_momentum_7d", source_market="crypto_perps",
                          source_timeframe="1h", hold_bars=24,
                          rebalance_bars=24).contract_id == "CRYPTO_PERPS_TOP100_1H_V1"


def fixture_checkout(tmp_path, tamper_sha=False):
    repo = tmp_path / "quant-lab"
    (repo / "contracts/datasets").mkdir(parents=True)
    (repo / "data/exploratory").mkdir(parents=True)
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    dates = [start + timedelta(hours=i) for i in range(120)]
    assets = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "AVAXUSDT",
              "BNBUSDT", "DOGEUSDT", "SOLUSDT", "XRPUSDT"]
    rows = [(t, s) for t in dates for s in assets]
    frame = pa.table({
        "timestamp": pa.array([t for t, _ in rows], type=pa.timestamp("us", tz="UTC")),
        "asset": [s for _, s in rows], "open": [1.0] * len(rows),
        "high": [2.0] * len(rows), "low": [0.5] * len(rows),
        "close": [1.1] * len(rows), "volume": [100.0] * len(rows),
        "funding_rate": [0.001] * len(rows),
    })
    market = repo / "data/exploratory/crypto_perps_1h_v2.parquet"
    pq.write_table(frame, market)
    sha = hashlib.sha256(market.read_bytes()).hexdigest()
    contract = {
        "contract_id": "CRYPTO_PERPS_1H_V2", "asset_class": "crypto_perps",
        "frequency": "1h", "train_start": "2024-01-01T00:00:00Z",
        "val_start": "2024-01-03T00:00:00Z",
        "val_end": "2024-01-05T00:00:00Z",
        "holdout_start": "2024-01-06T00:00:00Z",
        "execution_mode": "NEXT_BAR", "execution_delay_bars": 1,
        "taker_fee_bps": 4.0, "slippage_bps": 2.0,
        "data_provenance": "verified_market", "data_snapshot_sha256": sha,
        "exploratory_data_path": "data/exploratory/crypto_perps_1h_v2.parquet",
        "holdout_data_path": "data/holdout/SEALED_MUST_NOT_READ.parquet",
    }
    (repo / "contracts/crypto_perps_1h_v2.yaml").write_text(yaml.safe_dump(contract))
    (repo / "contracts/datasets/CRYPTO_PERPS_1H_V2.json").write_text(json.dumps({
        "contract_id": contract["contract_id"], "sha256": sha if not tamper_sha else "0" * 64,
        "path": contract["exploratory_data_path"],
        "provenance": "verified_market",
    }))
    return repo


def test_preflight_checks_pinned_exploratory_only_and_economic_costs(tmp_path):
    root = fixture_checkout(tmp_path)
    assert not (root / "data/holdout").exists()
    audit = contract_preflight(root, ROUTES["dip_7d"])
    assert audit["assets"] == 8 and audit["observations"] == 960
    assert audit["one_way_modeled_cost_bps"] == 6.0
    assert audit["round_trip_modeled_cost_bps"] == 12.0
    assert audit["stress_cost_2x_bps"] == 24.0
    assert audit["protected_holdout_accessed"] is False
    assert audit["execution_qualification"] == "MODELED_COSTS_NOT_FILL_CALIBRATED"
    with pytest.raises(RouteBlocked, match="unavailable"):
        require_observable_execution("Required bid-ask and market making L2 data", ROUTES["dip_7d"], audit)


def test_preflight_never_falls_back_when_sha_or_origin_wrong(tmp_path):
    root = fixture_checkout(tmp_path, tamper_sha=True)
    with pytest.raises(RouteBlocked, match="SHA-256"):
        contract_preflight(root, ROUTES["dip_7d"])
    manifest = root / "contracts/datasets/CRYPTO_PERPS_1H_V2.json"
    doc = json.loads(manifest.read_text())
    doc["sha256"] = yaml.safe_load(
        (root / "contracts/crypto_perps_1h_v2.yaml").read_text()
    )["data_snapshot_sha256"]
    doc["provenance"] = "unknown"
    manifest.write_text(json.dumps(doc))
    with pytest.raises(RouteBlocked, match="origin"):
        contract_preflight(root, ROUTES["dip_7d"])



def test_exact_index_source_routes_to_real_five_minute_contract():
    article = (
        "Nasdaq NQ intraday system using 5m bars and regular US market hours. "
        "Buy breakout above the previous 12-bar high and sell breakout below "
        "the previous 12-bar low on Nasdaq NQ index; exit after 12 bars. "
        "Only enter after the first session hour, close before RTH end."
    )
    record = {
        "platform": "blog", "post_id": "nq12", "text": article,
        "title": "Nasdaq NQ index intraday breakout",
        "authenticity": "ORIGINAL_PUBLISHER_RSS_CURRENT_CAPTURE",
    }
    evidence = Evidence(
        source_id="social_blog_nq12", kind=EvidenceKind.HISTORICAL,
        uri="https://source.example/blog/nq12",
        published_at="2026-10-01T00:00:00Z",
        available_at="2026-10-29T00:00:00Z",
        archived_at="2026-10-29T00:00:00Z",
        source_version="nq", snippet=article,
        provider="author_blog",
        facts={"source_authenticity": record["authenticity"]},
    )
    rule = SourceRule(
        source_market="indices", source_timeframe="5m", side="both",
        holding_bars=12, target_symbols=["NQ"],
        entry_quote=(
            "Buy breakout above the previous 12-bar high and sell breakout "
            "below the previous 12-bar low on Nasdaq NQ index"
        ), exit_quote="exit after 12 bars",
    )
    route = validate_source_rule("index_intraday_breakout_5m", rule, [evidence], [record])
    assert route.contract_id == "INDICES_5M_V1"
    with pytest.raises(RouteBlocked, match="instrument"):
        validate_source_rule("index_intraday_breakout_5m",
                             rule.model_copy(update={"target_symbols": ["DAX"]}),
                             [evidence], [record])


def test_price_direction_must_be_explicit_in_source_quote():
    record, evidence = original_post()
    text = record["text"] + " Buy breakout above previous 72-bar high with 1.5x volume; exit after 12 hours."
    record["text"] = text
    quote = "Buy breakout above previous 72-bar high with 1.5x volume"
    bad = SourceRule(
        source_market="crypto_perps", source_timeframe="1h",
        side="both", holding_bars=12, target_symbols=["BTCUSDT"],
        entry_quote=quote, exit_quote="exit after 12 hours",
    )
    with pytest.raises(RouteBlocked, match="BOTH directions"):
        validate_source_rule("volume_breakout", bad, [evidence], [record])



def test_nasdaq_stocks_are_equities_not_index_futures():
    from src.workflow.source_fidelity import _source_market
    assert _source_market("Long Nasdaq stocks with a daily RSI filter",
                          "Nasdaq-100 Stocks RSI Strategy") == "equities"
    from src.tools.social_sources import index_relevant
    assert not index_relevant("Momentum Strategy for Nasdaq-100 Stocks", "backtest")
    assert not index_relevant("Opening Range Breakout on QQQ", "backtest")
    assert index_relevant("Nasdaq NQ Opening Range Breakout", "NQ index CFD strategy")
