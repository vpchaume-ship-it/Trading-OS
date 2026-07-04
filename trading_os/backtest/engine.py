"""IFVG backtest engine — event-driven, bar by bar, no lookahead.

Fill model (documented assumptions):
* Entry = limit order at the inverted-zone edge, filled when a later bar's
  range crosses it (the order is placed at inversion time, before the retest).
* Stop = market order; slippage applied against us (config).
* If a bar could hit both stop and target, the STOP is counted (conservative).
* On the entry bar itself the stop can be hit (conservative same-bar handling).
* One position at a time; forced flat at eod_flat_time (NY).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from trading_os.core.fvg import FVG, FVGStatus, FVGTracker, InversionEvent, Direction
from trading_os.core.rating import InversionRating, rate_inversion
from trading_os.core.swings import find_swings, nearest_liquidity_target
from trading_os.core.timeutils import Killzones, parse_hhmm


@dataclass
class PendingSetup:
    fvg: FVG
    direction: Direction   # trade direction (IFVG polarity)
    entry: float
    stop: float
    target: float
    risk_ticks: float
    rating: InversionRating | None = None


@dataclass
class Position:
    setup: PendingSetup
    entry_time: pd.Timestamp
    entry_idx: int
    killzone: str | None
    in_ntz: bool


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    params: dict
    n_bars: int
    start: pd.Timestamp
    end: pd.Timestamp
    skipped_low_rr: int = 0
    skipped_ntz: int = 0
    skipped_position_busy: int = 0
    skipped_low_rating: int = 0


def _load_ntz_intervals(path: str, before_min: int, after_min: int) -> list[tuple]:
    """No-trade-zone intervals from the accumulated news history CSV."""
    import os
    if not path or not os.path.exists(path):
        return []
    hist = pd.read_csv(path)
    if hist.empty:
        return []
    times = pd.to_datetime(hist["datetime_ny"])
    if times.dt.tz is None:
        times = times.dt.tz_localize("America/New_York")
    return [(t - pd.Timedelta(minutes=before_min), t + pd.Timedelta(minutes=after_min))
            for t in times]


def _in_ntz(ts: pd.Timestamp, intervals: list[tuple]) -> bool:
    return any(a <= ts <= b for a, b in intervals)


def run_backtest(df: pd.DataFrame, cfg: dict, instrument: str) -> BacktestResult:
    """df: 1m (or resampled) OHLCV indexed by NY-tz timestamps."""
    icfg = cfg["ifvg"]
    bcfg = cfg["backtest"]
    spec = cfg["instruments"][instrument]
    tick = spec["tick_size"]
    contract = bcfg.get("contract", "mini")
    tick_value = spec["tick_value"] if contract == "mini" else spec["micro_tick_value"]

    costs = bcfg["costs"]
    commission_rt = 2 * costs["commission_per_side"][contract]
    slip_stop = costs["slippage_ticks_stop"] * tick
    slip_entry = costs["slippage_ticks_entry"] * tick

    kz = Killzones(cfg["killzones"])
    allowed_kz = icfg["allowed_killzones"]
    eod_flat = parse_hhmm(bcfg["eod_flat_time"])

    ncfg = cfg["news"]["no_trade_zone"]
    ntz = _load_ntz_intervals(bcfg.get("news_history_csv", ""),
                              ncfg["minutes_before"], ncfg["minutes_after"])
    respect_ntz = bcfg.get("respect_no_trade_zones", True)

    target_cfg = icfg["target"]
    use_liquidity = target_cfg["mode"] == "liquidity"
    swing_strength = target_cfg["swing_strength"]
    # Full swing list precomputed; lookahead is avoided at use time via the
    # confirmation lag inside nearest_liquidity_target().
    swings = find_swings(df, swing_strength) if use_liquidity else []

    tracker = FVGTracker(
        tick_size=tick,
        min_gap_ticks=icfg["min_gap_ticks"],
        invalidation_mode=icfg["invalidation_mode"],
        wick_fill_kills=icfg["wick_fill_kills"],
        fvg_max_age_bars=icfg["fvg_max_age_bars"],
        ifvg_max_age_bars=icfg["ifvg_max_age_bars"],
        max_retests=icfg["max_retests_per_zone"],
    )
    stop_buffer = icfg["stop_buffer_ticks"] * tick
    entry_mode = icfg["retest_entry"]
    min_rating = icfg.get("min_rating", 0)

    setups: list[PendingSetup] = []
    position: Position | None = None
    rows: list[dict] = []
    result = BacktestResult(trades=pd.DataFrame(), params={}, n_bars=len(df),
                            start=df.index[0], end=df.index[-1])

    o_arr = df["open"].to_numpy(); h_arr = df["high"].to_numpy()
    l_arr = df["low"].to_numpy(); c_arr = df["close"].to_numpy()
    times = df.index

    def make_setup(f: FVG, idx: int,
                   rating: InversionRating | None = None) -> PendingSetup | None:
        if rating is not None and rating.total < min_rating:
            result.skipped_low_rating += 1
            return None
        if f.ifvg_direction == Direction.BEARISH:
            edges = {"proximal": f.bottom, "midpoint": (f.top + f.bottom) / 2, "distal": f.top}
            entry = edges[entry_mode]
            stop = f.top + stop_buffer
            risk = stop - entry
            if use_liquidity:
                tgt = nearest_liquidity_target(swings, idx, swing_strength, entry, "bearish")
                if tgt is None or (entry - tgt) / risk < target_cfg["liquidity_min_rr"]:
                    result.skipped_low_rr += 1
                    return None
            else:
                tgt = entry - target_cfg["fixed_rr"] * risk
        else:
            edges = {"proximal": f.top, "midpoint": (f.top + f.bottom) / 2, "distal": f.bottom}
            entry = edges[entry_mode]
            stop = f.bottom - stop_buffer
            risk = entry - stop
            if use_liquidity:
                tgt = nearest_liquidity_target(swings, idx, swing_strength, entry, "bullish")
                if tgt is None or (tgt - entry) / risk < target_cfg["liquidity_min_rr"]:
                    result.skipped_low_rr += 1
                    return None
            else:
                tgt = entry + target_cfg["fixed_rr"] * risk
        return PendingSetup(f, f.ifvg_direction, entry, stop, tgt, risk / tick, rating)

    def close_position(pos: Position, ts, exit_price: float, reason: str):
        s = pos.setup
        sign = 1 if s.direction == Direction.BULLISH else -1
        gained_ticks = sign * (exit_price - s.entry) / tick
        pnl = gained_ticks * tick_value - commission_rt
        risk_usd = s.risk_ticks * tick_value
        rows.append({
            "entry_time": pos.entry_time, "exit_time": ts,
            "direction": s.direction.value, "entry": s.entry, "stop": s.stop,
            "target": s.target, "exit_price": exit_price, "exit_reason": reason,
            "risk_ticks": s.risk_ticks,
            "gross_r": gained_ticks / s.risk_ticks,
            "net_r": pnl / risk_usd,
            "pnl_usd": round(pnl, 2),
            "killzone": pos.killzone or "hors_killzone",
            "weekday": pos.entry_time.strftime("%A"),
            "in_ntz": pos.in_ntz,
            "fvg_direction": s.fvg.direction.value,
            "fvg_created": s.fvg.created_time,
            "inverted_time": s.fvg.inverted_time,
            "rating": s.rating.total if s.rating else None,
            "grade": s.rating.grade if s.rating else None,
        })

    for i in range(len(df)):
        ts = times[i]
        o, h, l, c = o_arr[i], h_arr[i], l_arr[i], c_arr[i]

        # ---- 1) manage open position (exits before anything else) -------
        if position is not None:
            s = position.setup
            if s.direction == Direction.BULLISH:
                if l <= s.stop:
                    close_position(position, ts, s.stop - slip_stop, "stop"); position = None
                elif h >= s.target:
                    close_position(position, ts, s.target, "target"); position = None
            else:
                if h >= s.stop:
                    close_position(position, ts, s.stop + slip_stop, "stop"); position = None
                elif l <= s.target:
                    close_position(position, ts, s.target, "target"); position = None
            if position is not None and ts.time() >= eod_flat:
                close_position(position, ts, c, "eod_flat"); position = None

        # ---- 2) update FVG state machine on this completed bar ----------
        events = list(tracker.update(i, ts, o, h, l, c))
        retested_now: set[int] = set()
        for ev in events:
            if isinstance(ev, InversionEvent):
                stp = make_setup(ev.fvg, i, rate_inversion(ev.fvg, o, h, l, c))
                if stp is not None:
                    setups.append(stp)
            else:  # RetestEvent — the tracker may flag the zone CONSUMED on the
                retested_now.add(id(ev.fvg))  # very bar our limit order fills

        # ---- 3) try to fill pending limit orders on this bar ------------
        still: list[PendingSetup] = []
        for stp in setups:
            if stp.fvg.inverted_idx == i:
                # order placed at the close of THIS bar — it cannot fill on the
                # inversion bar itself (no lookahead)
                still.append(stp)
                continue
            if stp.fvg.status != FVGStatus.INVERTED and id(stp.fvg) not in retested_now:
                continue  # zone reclaimed or expired -> cancel the pending order
            touched = (h >= stp.entry) if stp.direction == Direction.BEARISH else (l <= stp.entry)
            if not touched:
                still.append(stp)
                continue
            # Entry conditions at fill time
            if ts.time() >= eod_flat or not kz.in_any(ts, allowed_kz):
                continue  # setup consumed by the touch, entry filtered out
            in_zone_news = _in_ntz(ts, ntz)
            if respect_ntz and in_zone_news:
                result.skipped_ntz += 1
                continue
            if position is not None:
                result.skipped_position_busy += 1
                continue
            entry_px = stp.entry + (slip_entry if stp.direction == Direction.BULLISH else -slip_entry)
            stp.entry = entry_px
            position = Position(stp, ts, i, kz.label(ts), in_zone_news)
            # conservative same-bar stop check
            if stp.direction == Direction.BULLISH and l <= stp.stop:
                close_position(position, ts, stp.stop - slip_stop, "stop"); position = None
            elif stp.direction == Direction.BEARISH and h >= stp.stop:
                close_position(position, ts, stp.stop + slip_stop, "stop"); position = None
        setups = still

    if position is not None:
        close_position(position, times[-1], c_arr[-1], "end_of_data")

    result.trades = pd.DataFrame(rows)
    result.params = {
        "instrument": instrument, "contract": contract, "timeframe": icfg["timeframe"],
        "min_gap_ticks": icfg["min_gap_ticks"], "invalidation_mode": icfg["invalidation_mode"],
        "retest_entry": entry_mode, "stop_buffer_ticks": icfg["stop_buffer_ticks"],
        "target": dict(target_cfg), "allowed_killzones": list(allowed_kz),
        "commission_rt_usd": commission_rt, "slippage_ticks_stop": costs["slippage_ticks_stop"],
        "respect_no_trade_zones": respect_ntz, "n_news_events": len(ntz),
        "min_rating": min_rating,
    }
    return result
