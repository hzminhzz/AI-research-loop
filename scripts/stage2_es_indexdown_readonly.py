"""Read-only Stage-2 session/cost preflight for the exact frozen ES Stage-1 PASS.

This uses the existing Warden evaluation functions on the *approved exploratory*
panel, but NEVER connects to the registry and NEVER resolves a holdout.
No strategy parameters, Warden controls or source variants are modified.
Outputs JSON on stdout. Run from /home/quant/dev/quant-lab with its uv env.
"""

from __future__ import annotations

import argparse
import bisect
import json
from pathlib import Path

import numpy as np
import polars as pl

from warden.contracts import load_contract
from warden.provenance import resolve_dataset
from warden.runner import (
    _aligned_matrix,
    _funding_settlement_mask,
    _run_strategy_isolated,
    calculate_metrics_from_returns,
    execution_returns,
    filter_target_symbols,
    simulate_positions,
)

CONTRACT_ID = "INDICES_1D_V1"
HYPOTHESIS_ID = "HYP-SOC-BTA-INDEXDOWN-20261031"
MODULE = "strategies/candidates/bta_index_down_es_cfd_1d_20261031.py"
DATASET = "data/exploratory/indices_1d.parquet"
SPEC = "experiments/active/bta_index_down_es_cfd_1d_20261031.yaml"
INDEX_SOURCE = "https://breakouttradingacademy.com/big-index-trading-secret-to-get-real-results/"


def sharpe(returns: np.ndarray, bars_per_year: float) -> float:
    r = np.asarray(returns, dtype=float)
    if len(r) < 3 or np.std(r, ddof=1) <= 0:
        return float("nan")
    return float(np.mean(r) / np.std(r, ddof=1) * np.sqrt(bars_per_year))


def rollup(values: np.ndarray) -> dict:
    v = np.asarray(values, dtype=float)
    return {
        "bars": int(v.size),
        "net_sum_return_fraction": float(np.sum(v)),
        "positive_bars": int((v > 0).sum()),
        "negative_bars": int((v < 0).sum()),
        "avg_return_bps": float(np.mean(v) * 1e4) if v.size else None,
    }


def main(root: Path) -> dict:
    import yaml

    root = root.resolve()
    cfg = yaml.safe_load((root / SPEC).read_text(encoding="utf-8"))
    if cfg["hypothesis_id"] != HYPOTHESIS_ID or cfg["contract_id"] != CONTRACT_ID:
        raise ValueError("Frozen Stage1 experiment identity mismatch; STOP")
    if cfg["parameters"] != {"target_symbols": ["ES"]} or cfg.get("param_grid"):
        raise ValueError("Source parameterization changed or nonempty grid; STOP")
    if cfg["strategy_module"] != MODULE:
        raise ValueError("Strategy module changed; STOP")
    contract = load_contract(root / "contracts/indices_1d_v1.yaml")
    if contract.contract_id != CONTRACT_ID or contract.execution_mode != "NEXT_BAR":
        raise ValueError("Non-approved native contract semantics; STOP")
    if contract.execution_delay_bars != 1:
        raise ValueError("Native next-bar lag changed; STOP")
    resolved = resolve_dataset(contract, root)
    if str(resolved.path) != DATASET or resolved.provenance != "verified_market":
        raise ValueError("Dataset contract mismatch; STOP")
    if not resolved.eligible_market:
        raise ValueError("Exploratory data no longer qualified verified-market; STOP")
    path = root / resolved.path
    panel = pl.read_parquet(path)
    if "symbol" in panel.columns and "asset" not in panel.columns:
        panel = panel.rename({"symbol": "asset"})
    panel = filter_target_symbols(panel, {"target_symbols": ["ES"]}, str(resolved.path)).sort(
        "timestamp", "asset"
    )
    ts = sorted(panel["timestamp"].unique().to_list())
    if any(t.tzinfo is None or t.hour != 0 or t.minute != 0 for t in ts):
        raise ValueError("Unexpected ES timestamp clock; STOP")
    if len(ts) != panel.height:
        raise ValueError("Duplicate or missing ES timestamp records; STOP")
    lo = bisect.bisect_left(ts, contract.val_start)
    hi = bisect.bisect_left(ts, contract.val_end)
    if hi <= lo or (hi - lo) < 100:
        raise ValueError("No sufficient validation window; STOP")
    window = slice(lo, hi)
    result = _run_strategy_isolated(root / MODULE, panel, contract, cfg["parameters"])
    pos = np.asarray(result["positions"], dtype=float)
    if pos.shape != (len(ts), 1):
        raise ValueError("Original Warden frozen signal no longer has ES-only shape")
    assets = sorted(panel["asset"].unique().to_list())
    ret = execution_returns(panel, contract, assets)
    funding = (
        _aligned_matrix(panel, "funding_rate", assets)
        if "funding_rate" in panel.columns
        else None
    )
    mask = _funding_settlement_mask(ts, contract)
    sim = {
        "1x": simulate_positions(
            pos, ret["long"], funding, contract, window,
            cost_multiplier=1.0, funding_mask=mask, quote_returns=ret
        ),
        "1p5x": simulate_positions(
            pos, ret["long"], funding, contract, window,
            cost_multiplier=1.5, funding_mask=mask, quote_returns=ret
        ),
        "2x": simulate_positions(
            pos, ret["long"], funding, contract, window,
            cost_multiplier=2.0, funding_mask=mask, quote_returns=ret
        ),
        "lag_plus1": simulate_positions(
            pos, ret["long"], funding, contract, window,
            cost_multiplier=1.0, delay_offset=1,
            funding_mask=mask, quote_returns=ret
        ),
    }
    net = sim["1x"]["net_returns"]
    tval = ts[lo:hi]
    weekdays = np.array([t.weekday() for t in tval], dtype=int)
    red_signal = (panel["close"].to_numpy() < panel["open"].to_numpy())[lo:hi]
    buckets = {}
    for wday in range(7):
        ix = weekdays == wday
        if ix.any():
            buckets[str(wday)] = {
                **rollup(net[ix]),
                "exposed_bars": int(np.count_nonzero(sim["1x"]["positions"][ix])),
                "red_signal_bars": int(np.count_nonzero(red_signal[ix])),
                "gross_sum_return_fraction": float(np.sum(sim["1x"]["gross_returns"][ix])),
            }
    sunday = weekdays == 6
    monday = weekdays == 0
    cash_unsupported_bars = sunday | monday
    pos_val = sim["1x"]["positions"].ravel()
    pos_before = pos[lo - 1:hi - 1, 0] if lo > 0 else pos[lo:hi, 0]
    if len(pos_before) != len(net) or not np.array_equal(pos_val, pos_before):
        raise ValueError("Native execution lag verification failed")
    prev_day = np.array([ts[max(lo + k - 1, 0)].weekday() for k in range(len(net))])
    after_sunday_signal = monday & (prev_day == 6) & (pos_val > 0)
    top5_count = max(1, int(np.ceil(0.05 * len(net))))
    top5_idx = np.argsort(net)[-top5_count:]
    removed_top5 = net.copy()
    removed_top5[top5_idx] = 0
    selected = {
        "non_sunday": ~sunday,
        "sunday": sunday,
        "monday": monday,
        "sunday_or_monday": cash_unsupported_bars,
        "monday_after_sunday_signal": after_sunday_signal,
    }
    date_start = tval[0].isoformat()
    date_end = tval[-1].isoformat()
    return {
        "identity": {
            "hypothesis_id": HYPOTHESIS_ID,
            "experiment": SPEC,
            "module": MODULE,
            "source_original": INDEX_SOURCE,
            "source_type": "published cash-market tendency; independent CFD daily research adaptation",
            "contract": CONTRACT_ID,
            "dataset_path": str(resolved.path),
            "dataset_sha256": resolved.sha256,
            "data_provenance": resolved.provenance,
            "validation_start": date_start,
            "validation_last_bar": date_end,
            "never_read_holdout": True,
            "registry_connection_created": False,
        },
        "native_read_only_execution": {
            label: {
                "metrics": calculate_metrics_from_returns(
                    s["gross_returns"], s["net_returns"], s["turnover"],
                    contract.bars_per_year
                ),
                "bar_count": len(s["net_returns"]),
                "exposure_fraction": float(np.count_nonzero(s["positions"]) / len(s["positions"])),
            }
            for label, s in sim.items()
        },
        "cash_clock_reconciliation": {
            "weekday_map": "0=Monday, 1=Tuesday, ..., 4=Friday, 6=Sunday (Python UTC weekday)",
            "source_nyse_core_session": "Monday-Friday 09:30-16:00 Eastern (NYSE official)",
            "source_cme_globex": "Sunday 18:00 ET-Friday 17:00 ET with daily break (CME official)",
            "native_bars_all_timestamped_utc_midnight": True,
            "native_daily_bars_with_sunday": int(sunday.sum()),
            "weekdays_by_return_interval_start": buckets,
            "cash_session_unsupported_return_bars": rollup(net[cash_unsupported_bars]),
            "non_sunday_open_to_open_bars": rollup(net[~sunday]),
            "monday_after_sunday_signal_bars": rollup(net[after_sunday_signal]),
            "original_run_full_net_sum": float(np.sum(net)),
            "return_contributions_by_group": {
                label: rollup(net[idx]) for label, idx in selected.items()
            },
            "interpretation": "Attribution ONLY on the original frozen Warden executed positions. Removing a weekday posthoc is NOT a new tradable strategy or Warden Stage1 result.",
        },
        "outlier_sensitivity": {
            "top5pct_n_bars": top5_count,
            "net_sharpe_after_zeroing_best5pct": sharpe(
                removed_top5, contract.bars_per_year
            ),
            "fraction_sum_reliant_on_top5pct": (
                float(np.sum(net[top5_idx]) / np.sum(net))
                if abs(float(np.sum(net))) > 1e-12 else None
            ),
        },
        "limitation": {
            "publisher_prior_tendencies": "Six stated; actual author search count UNKNOWN and not included in native Warden selection history",
            "author_vintage": "Captured in 2026; 2022 publication claim not independently authenticated",
            "original_cash_day_reproduction": "NOT supported: 390 of 3111 pinned ES CFD exploratory bars carry Sunday UTC labels; verified_market provenance does not establish NYSE cash-session alignment.",
            "session_eligibility_for_source_replication": "BLOCKED: CFD Sunday and UTC-midnight bar definitions not equivalent to NYSE cash close",
            "full_stage3_scientific_qualification": "Requires Warden native trial and audit with explicit source-selection debt; Stage2 diagnostics alone cannot qualify.",
            "broker_fills_and_spread": "Unknown; 1bps/side fixed native cost is NOT measured CFD execution",
        },
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--quant-lab", default="/home/quant/dev/quant-lab")
    args = p.parse_args()
    print(json.dumps(main(Path(args.quant_lab)), sort_keys=True, indent=2))
