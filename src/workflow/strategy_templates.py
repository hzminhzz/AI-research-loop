"""Reviewed, immutable-rule strategy implementations for native Warden Stage 1.

No generated Python is executed. Parameters are exclusively a reviewed mode and
an ex-ante, observable source-date universe (when needed). Warden owns next-bar
execution, fees, funding, selection history and sealed holdouts.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from warden.contracts import EvaluationContract


ALLOWED_MODES = (
    "shock_reversal", "volume_breakout", "dip_7d",
    "rsi2_trend_pullback", "donchian_trend", "vol_compression_breakout",
    "cross_section_momentum_7d", "shock_reversal_5m",
    "donchian_trend_4h", "swing_breakout_1d", "index_intraday_breakout_5m",
)
EXPECTED_CONTRACTS = {
    "shock_reversal": "CRYPTO_PERPS_1H_V2",
    "volume_breakout": "CRYPTO_PERPS_1H_V2",
    "dip_7d": "CRYPTO_PERPS_1H_V2",
    "rsi2_trend_pullback": "CRYPTO_PERPS_1H_V2",
    "donchian_trend": "CRYPTO_PERPS_1H_V2",
    "vol_compression_breakout": "CRYPTO_PERPS_1H_V2",
    "cross_section_momentum_7d": "CRYPTO_PERPS_TOP100_1H_V1",
    "shock_reversal_5m": "CRYPTO_PERPS_5M_V1",
    "donchian_trend_4h": "CRYPTO_PERPS_4H_V1",
    "swing_breakout_1d": "CRYPTO_PERPS_1D_V1",
    "index_intraday_breakout_5m": "INDICES_5M_V1",
}


class FixedFeaturePipeline:
    def compute(self, bars_df: pl.DataFrame | pl.LazyFrame,
                contract: EvaluationContract) -> pl.DataFrame:
        _ = contract
        df = bars_df.collect() if isinstance(bars_df, pl.LazyFrame) else bars_df
        if "symbol" in df.columns and "asset" not in df.columns:
            df = df.rename({"symbol": "asset"})
        df = df.sort("asset", "timestamp")
        # shift(1) on rolling highs/volumes ensures these values are prior
        # observations only. Current closed-bar close is used for the signal;
        # Warden applies the NEXT_BAR execution lag.
        return (
            df.with_columns(
                ret_1=(pl.col("close") / pl.col("close").shift(1) - 1).over("asset"),
                ret_168=(pl.col("close") / pl.col("close").shift(168) - 1).over("asset"),
                vol168=pl.col("volume").rolling_mean(168).shift(1).over("asset"),
                hi12=pl.col("high").rolling_max(12).shift(1).over("asset"),
                lo12=pl.col("low").rolling_min(12).shift(1).over("asset"),
                hi20=pl.col("high").rolling_max(20).shift(1).over("asset"),
                lo20=pl.col("low").rolling_min(20).shift(1).over("asset"),
                hi24=pl.col("high").rolling_max(24).shift(1).over("asset"),
                lo24=pl.col("low").rolling_min(24).shift(1).over("asset"),
                hi60=pl.col("high").rolling_max(60).shift(1).over("asset"),
                lo60=pl.col("low").rolling_min(60).shift(1).over("asset"),
                hi72=pl.col("high").rolling_max(72).shift(1).over("asset"),
                lo72=pl.col("low").rolling_min(72).shift(1).over("asset"),
                hi168=pl.col("high").rolling_max(168).shift(1).over("asset"),
                hi240=pl.col("high").rolling_max(240).shift(1).over("asset"),
                lo240=pl.col("low").rolling_min(240).shift(1).over("asset"),
                ema48=pl.col("close").ewm_mean(span=48, adjust=False).over("asset"),
                ema200=pl.col("close").ewm_mean(span=200, adjust=False).over("asset"),
            ).with_columns(
                std168=pl.col("ret_1").rolling_std(168).shift(1).over("asset"),
                std24=pl.col("ret_1").rolling_std(24).shift(1).over("asset"),
                volume_ratio=pl.col("volume") / (pl.col("vol168") + 1e-9),
                gain=pl.col("ret_1").clip(lower_bound=0),
                loss=(-pl.col("ret_1")).clip(lower_bound=0),
            ).with_columns(
                rsi2=100 - 100 / (1 + pl.col("gain").rolling_mean(2).over("asset") /
                                  (pl.col("loss").rolling_mean(2).over("asset") + 1e-12))
            ).sort("timestamp", "asset")
        )


pipeline = FixedFeaturePipeline()


def _index_rth_mask(times) -> np.ndarray:
    """US indices only, regular New York hours with DST; stop before close."""
    tz = ZoneInfo("America/New_York")
    values = []
    for time in times:
        dt: datetime = time.astimezone(tz)
        # 10:30-14:30 ET: prior 12 bars cover current RTH, and no new position
        # can cross the 16:00 close with a <=12-bar holding interval.
        minute = dt.hour * 60 + dt.minute
        values.append(dt.weekday() < 5 and 10 * 60 + 30 <= minute <= 14 * 60 + 30)
    return np.asarray(values, dtype=bool)


def generate_positions(panel_df: pl.DataFrame, contract: EvaluationContract,
                       mode: str = "shock_reversal",
                       target_symbols: list[str] | None = None, **kwargs) -> dict:
    if kwargs:
        raise ValueError(f"Unapproved strategy parameters: {sorted(kwargs)}")
    if mode not in ALLOWED_MODES or contract.contract_id != EXPECTED_CONTRACTS.get(mode):
        raise ValueError("Mode not approved for this registered Warden contract")
    df = pipeline.compute(panel_df, contract)
    ts = sorted(df["timestamp"].unique().to_list())
    assets = sorted(df["asset"].unique().to_list())
    if target_symbols is not None and sorted(target_symbols) != assets:
        raise ValueError("Ex-ante target-symbol manifest does not match Warden-filtered universe")
    if mode == "cross_section_momentum_7d":
        if not 40 <= len(assets) <= 100:
            raise ValueError("Broad cross-sectional template needs >=40 ex-ante symbols")
    elif mode == "index_intraday_breakout_5m":
        if set(assets) - {"NQ", "ES"} or not assets:
            raise ValueError("Index template supports only US NQ/ES and RTH sessions")
    elif not (1 <= len(assets) <= 8):
        raise ValueError("This crypto template requires 1-8 source-declared instruments")
    if len(ts) < 300:
        raise ValueError("Insufficient causal signal warmup")

    def pivot(name: str) -> np.ndarray:
        panel = df.pivot(index="timestamp", on="asset", values=name).sort("timestamp")
        if panel.height != len(ts) or any(a not in panel.columns for a in assets):
            raise ValueError("Nonrectangular candidate matrix")
        return panel.select(assets).to_numpy()

    close = pivot("close")
    if not np.isfinite(close).all():
        raise ValueError("Missing close; never trade a sparse panel without Warden support")
    high, low = pivot("hi72"), pivot("lo72")
    ret, vol, vr = pivot("ret_1"), pivot("std168"), pivot("volume_ratio")
    signal = np.zeros_like(close, dtype=float)
    horizon = 12
    warmup = 242

    if mode in ("shock_reversal", "shock_reversal_5m"):
        signal = np.where(
            (np.abs(ret) >= 2.5 * vol) & (vol > 1e-10) & (vr >= 1.5),
            -np.sign(ret), 0.0)
        horizon = 4 if mode == "shock_reversal" else 12
    elif mode == "volume_breakout":
        signal = np.where((close > high) & (vr >= 1.5), 1.0,
                          np.where((close < low) & (vr >= 1.5), -1.0, 0.0))
        horizon = 12
    elif mode == "dip_7d":
        hi = pivot("hi168")
        signal = np.where((hi > 0) & (close <= 0.88 * hi), 1.0, 0.0)
        horizon = 4
    elif mode == "rsi2_trend_pullback":
        rsi, fast, slow = pivot("rsi2"), pivot("ema48"), pivot("ema200")
        signal = np.where((fast > slow) & (rsi < 10), 1.0,
                          np.where((fast < slow) & (rsi > 90), -1.0, 0.0))
        horizon = 12
    elif mode in ("donchian_trend", "donchian_trend_4h"):
        hi, lo = (
            (pivot("hi240"), pivot("lo240")) if mode == "donchian_trend"
            else (pivot("hi60"), pivot("lo60"))
        )
        signal = np.where(close > hi, 1.0, np.where(close < lo, -1.0, 0.0))
        horizon = 24 if mode == "donchian_trend" else 6
    elif mode == "vol_compression_breakout":
        squeeze = (vol > 1e-10) & (pivot("std24") < 0.55 * vol)
        hi, lo = pivot("hi24"), pivot("lo24")
        signal = np.where(squeeze & (close > hi), 1.0,
                          np.where(squeeze & (close < lo), -1.0, 0.0))
        horizon = 8
    elif mode == "swing_breakout_1d":
        hi, lo = pivot("hi20"), pivot("lo20")
        signal = np.where(close > hi, 1.0, np.where(close < lo, -1.0, 0.0))
        horizon, warmup = 5, 24
    elif mode == "index_intraday_breakout_5m":
        # Use previous 12 closed 5m bars, after the first RTH hour. Position
        # clock is bounded to same-day market hours (DST via zoneinfo).
        allowed = _index_rth_mask(ts)
        hi, lo = pivot("hi12"), pivot("lo12")
        signal = np.where(allowed[:, None] & (close > hi), 1.0,
                          np.where(allowed[:, None] & (close < lo), -1.0, 0.0))
        horizon, warmup = 12, 14
    elif mode == "cross_section_momentum_7d":
        returns = pivot("ret_168")
        positions = np.zeros_like(close)
        targets = np.zeros(len(assets), dtype=float)
        prior_day = None
        for idx, timestamp in enumerate(ts):
            # Rebalance every UTC day; no future universe selection.
            day = timestamp.date()
            if timestamp.hour == 0 and day != prior_day and idx >= 240:
                prior_day = day
                targets[:] = 0.0
                valid = np.flatnonzero(np.isfinite(returns[idx]))
                if len(valid) >= 40:
                    order = valid[np.argsort(returns[idx, valid], kind="stable")]
                    size = max(2, len(order) // 5)
                    targets[order[:size]] = -0.40 / size
                    targets[order[-size:]] = +0.40 / size
            positions[idx] = targets
        return {"positions": positions}
    else:
        raise AssertionError("Unrecognized rule")

    # One frozen time-exit per signal. No close-to-open leverage change or
    # parameter tuning; the one-bar execution lag is added only by Warden.
    positions = np.zeros_like(close, dtype=float)
    current = np.zeros(len(assets), dtype=float)
    end = np.zeros(len(assets), dtype=np.int64)
    for idx in range(len(ts)):
        for j in range(len(assets)):
            if idx >= end[j]:
                sig = signal[idx, j] if np.isfinite(signal[idx, j]) else 0.0
                if idx >= warmup and sig:
                    current[j], end[j] = 0.20 * sig, idx + horizon
                else:
                    current[j], end[j] = 0.0, idx
        gross = np.sum(np.abs(current))
        positions[idx] = current / max(1.0, float(gross))
    return {"positions": positions}
