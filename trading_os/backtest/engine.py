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
    cur_stop: float = 0.0    # dynamic stop (be/trail modes move it)
    best: float = 0.0        # most favorable price reached (completed bars)
    banked_r: float = 0.0    # R already locked by a partial (scale-out)
    frac: float = 1.0        # remaining position fraction after scaling


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
    skipped_no_sweep: int = 0
    skipped_no_pd: int = 0
    skipped_no_bias: int = 0
    skipped_no_session_sweep: int = 0
    skipped_no_vshape: int = 0
    skipped_entry_window: int = 0


def _load_ntz_intervals(path: str, before_min: int, after_min: int) -> list[tuple]:
    """No-trade-zone intervals from the accumulated news history CSV."""
    import os
    if not path or not os.path.exists(path):
        return []
    hist = pd.read_csv(path)
    if hist.empty:
        return []
    # utc=True handles mixed EDT/EST offsets (-04:00 and -05:00 in one file)
    times = pd.to_datetime(hist["datetime_ny"], utc=True).dt.tz_convert("America/New_York")
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
    # Fenêtre d'entrée restreinte À L'INTÉRIEUR de la killzone (posée par la
    # boucle d'auto-ajustement feedback.py) ; None = killzone entière.
    _ew = icfg.get("entry_window")
    ew_lo = parse_hhmm(_ew["start"]) if _ew else None
    ew_hi = parse_hhmm(_ew["end"]) if _ew else None

    def in_entry_window(ts) -> bool:
        return ew_lo is None or (ew_lo <= ts.time() <= ew_hi)

    ncfg = cfg["news"]["no_trade_zone"]
    ntz = _load_ntz_intervals(bcfg.get("news_history_csv", ""),
                              ncfg["minutes_before"], ncfg["minutes_after"])
    respect_ntz = bcfg.get("respect_no_trade_zones", True)

    target_cfg = icfg["target"]
    use_liquidity = target_cfg["mode"] == "liquidity"
    swing_strength = target_cfg["swing_strength"]
    setup_cfg = icfg.get("setup", {})
    require_sweep = setup_cfg.get("require_sweep", False)
    sweep_lookback = setup_cfg.get("sweep_lookback", 40)
    require_pd = setup_cfg.get("require_pd", False)
    pd_lookback = setup_cfg.get("pd_lookback", 60)
    require_bias = setup_cfg.get("require_bias", False)
    bias_lookback = setup_cfg.get("bias_lookback", 90)
    sweep_mode = setup_cfg.get("sweep_mode", "swing")   # swing | session
    require_vshape = setup_cfg.get("require_vshape", False)
    vshape_max_bars = setup_cfg.get("vshape_max_bars", 8)
    vshape_min_move_ticks = setup_cfg.get("vshape_min_move_ticks", 20)

    # Previous-session liquidity levels per bar (for sweep_mode="session"):
    # prior day's high/low (PDH/PDL) + today's overnight high/low (00:00 -> killzone
    # start = Asia+London). Complete before the NY killzone -> no lookahead.
    pdh_arr = pdl_arr = onh_arr = onl_arr = None
    if sweep_mode == "session":
        import numpy as _np
        kz_start = min(parse_hhmm(z["start"]) for z in cfg["killzones"].values())
        dts = df.index
        dates = _np.array([d.date() for d in dts])
        day_hi = df.groupby(dates)["high"].max()
        day_lo = df.groupby(dates)["low"].min()
        on_mask = _np.array([t < kz_start for t in dts.time])
        on_hi = df["high"][on_mask].groupby(dates[on_mask]).max()
        on_lo = df["low"][on_mask].groupby(dates[on_mask]).min()
        uniq = list(day_hi.index)
        prev = {d: uniq[k - 1] for k, d in enumerate(uniq) if k > 0}
        pdh_arr = _np.array([day_hi.get(prev.get(d), _np.nan) for d in dates])
        pdl_arr = _np.array([day_lo.get(prev.get(d), _np.nan) for d in dates])
        onh_arr = _np.array([on_hi.get(d, _np.nan) for d in dates])
        onl_arr = _np.array([on_lo.get(d, _np.nan) for d in dates])
    # Full swing list precomputed; lookahead is avoided at use time via the
    # confirmation lag inside nearest_liquidity_target() / the sweep check.
    swings = find_swings(df, swing_strength) if (use_liquidity or require_sweep) else []

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
    # "retest" = ordre limite au bord de la zone inversée (attend le retest) ;
    # "inversion_close" = entrée au marché sur la clôture de la bougie qui inverse
    # le FVG (méthode Dodgy, agressive), stop au-delà de cette bougie.
    entry_timing = icfg.get("entry_timing", "retest")
    min_rating = icfg.get("min_rating", 0)
    exit_cfg = icfg.get("exit", {})
    exit_mode = exit_cfg.get("mode", "full")          # full | be | trail
    be_trigger = exit_cfg.get("be_trigger_rr", 1.0)
    trail_rr = exit_cfg.get("trail_rr", 1.0)

    setups: list[PendingSetup] = []
    position: Position | None = None
    rows: list[dict] = []
    result = BacktestResult(trades=pd.DataFrame(), params={}, n_bars=len(df),
                            start=df.index[0], end=df.index[-1])

    o_arr = df["open"].to_numpy(); h_arr = df["high"].to_numpy()
    l_arr = df["low"].to_numpy(); c_arr = df["close"].to_numpy()
    times = df.index

    def swept_liquidity(f: FVG) -> bool:
        """A+ criterion: just before the FVG formed, price raided the most recent
        opposing swing (short after a swing-high sweep, long after a swing-low
        sweep) then reversed. No lookahead: the swing is confirmed before the raid,
        and the sweep must occur inside the lookback window right before the FVG."""
        win_lo = max(0, f.created_idx - sweep_lookback)
        want_high = f.ifvg_direction == Direction.BEARISH   # short -> a high was raided
        kind = "high" if want_high else "low"
        # most recent swing of that kind confirmed before the window starts
        prior = [s for s in swings if s.kind == kind
                 and s.idx + swing_strength <= win_lo]
        if not prior:
            return False
        s = max(prior, key=lambda s: s.idx)
        seg_h = h_arr[win_lo:f.created_idx + 1]
        seg_l = l_arr[win_lo:f.created_idx + 1]
        # liquidity taken (wicked beyond the swing) inside the window
        return seg_h.max() > s.price if want_high else seg_l.min() < s.price

    def swept_session_level(f: FVG) -> bool:
        """User's model: the sweep must take a PREVIOUS-SESSION level, not just any
        swing. For a short (bearish IFVG) price must have wicked above the prior
        day's high (PDH) or today's overnight high within the lookback window right
        before the FVG; for a long, below PDL or the overnight low. No lookahead:
        PDH/PDL are yesterday's, the overnight extremes are complete before the NY
        killzone, and the raid must sit inside the pre-FVG window."""
        import numpy as _np
        win_lo = max(0, f.created_idx - sweep_lookback)
        want_high = f.ifvg_direction == Direction.BEARISH
        if want_high:
            levels = [pdh_arr[f.created_idx], onh_arr[f.created_idx]]
            seg = h_arr[win_lo:f.created_idx + 1]
            return any((not _np.isnan(lv)) and seg.max() > lv for lv in levels)
        levels = [pdl_arr[f.created_idx], onl_arr[f.created_idx]]
        seg = l_arr[win_lo:f.created_idx + 1]
        return any((not _np.isnan(lv)) and seg.min() < lv for lv in levels)

    def v_shape(f: FVG) -> bool:
        """User's model: a sharp V-shape reversal into the inversion, not a slow
        grind. From the swept extreme (the pivot within the lookback window) to the
        inversion bar the counter-move must cover >= vshape_min_move_ticks within
        <= vshape_max_bars. Measured on completed bars up to the inversion -> no
        lookahead."""
        inv = f.inverted_idx if f.inverted_idx is not None else f.created_idx
        win_lo = max(0, inv - (sweep_lookback + vshape_max_bars))
        want_high = f.ifvg_direction == Direction.BEARISH   # short: swept a high, fell
        if want_high:
            pivot = win_lo + int(h_arr[win_lo:inv + 1].argmax())   # extreme high
            move_ticks = (h_arr[pivot] - c_arr[inv]) / tick
        else:
            pivot = win_lo + int(l_arr[win_lo:inv + 1].argmin())   # extreme low
            move_ticks = (c_arr[inv] - l_arr[pivot]) / tick
        bars = inv - pivot
        return 0 < bars <= vshape_max_bars and move_ticks >= vshape_min_move_ticks

    def in_pd(f: FVG, entry: float) -> bool:
        """Long only in the discount half, short only in the premium half of the
        recent range (premium/discount, ICT)."""
        lo = max(0, f.created_idx - pd_lookback)
        hi_r = h_arr[lo:f.created_idx + 1].max()
        lo_r = l_arr[lo:f.created_idx + 1].min()
        if hi_r <= lo_r:
            return True
        mid = (hi_r + lo_r) / 2
        return entry >= mid if f.ifvg_direction == Direction.BEARISH else entry <= mid

    def bias_aligned(f: FVG) -> bool:
        """Trade only with the higher-timeframe drift (Daily Bias PDF): a long
        (bullish IFVG) needs price above where it was bias_lookback bars ago, a
        short needs it below. Uses only bars up to the inversion -> no lookahead."""
        j = f.created_idx - bias_lookback
        if j < 0:
            return False
        drift = c_arr[f.created_idx] - c_arr[j]
        return drift > 0 if f.ifvg_direction == Direction.BULLISH else drift < 0

    def make_setup(f: FVG, idx: int, rating: InversionRating | None = None,
                   inv_ohlc: tuple | None = None) -> PendingSetup | None:
        """inv_ohlc = (o,h,l,c) of the inversion bar, given only for
        entry_timing='inversion_close' (aggressive market entry at that close)."""
        if rating is not None and rating.total < min_rating:
            result.skipped_low_rating += 1
            return None
        if require_bias and not bias_aligned(f):
            result.skipped_no_bias += 1
            return None
        if require_sweep:
            if sweep_mode == "session":
                if not swept_session_level(f):
                    result.skipped_no_session_sweep += 1
                    return None
            elif not swept_liquidity(f):
                result.skipped_no_sweep += 1
                return None
        if require_vshape and not v_shape(f):
            result.skipped_no_vshape += 1
            return None
        if f.ifvg_direction == Direction.BEARISH:
            if inv_ohlc is not None:                 # enter at the inversion close
                entry = inv_ohlc[3]; stop = inv_ohlc[1] + stop_buffer   # stop above inv high
            else:
                edges = {"proximal": f.bottom, "midpoint": (f.top + f.bottom) / 2, "distal": f.top}
                entry = edges[entry_mode]; stop = f.top + stop_buffer
            risk = stop - entry
            if risk <= 0:
                return None
            if use_liquidity:
                tgt = nearest_liquidity_target(swings, idx, swing_strength, entry, "bearish")
                if tgt is None or (entry - tgt) / risk < target_cfg["liquidity_min_rr"]:
                    result.skipped_low_rr += 1
                    return None
            else:
                tgt = entry - target_cfg["fixed_rr"] * risk
        else:
            if inv_ohlc is not None:
                entry = inv_ohlc[3]; stop = inv_ohlc[2] - stop_buffer   # stop below inv low
            else:
                edges = {"proximal": f.top, "midpoint": (f.top + f.bottom) / 2, "distal": f.bottom}
                entry = edges[entry_mode]; stop = f.bottom - stop_buffer
            risk = entry - stop
            if risk <= 0:
                return None
            if use_liquidity:
                tgt = nearest_liquidity_target(swings, idx, swing_strength, entry, "bullish")
                if tgt is None or (tgt - entry) / risk < target_cfg["liquidity_min_rr"]:
                    result.skipped_low_rr += 1
                    return None
            else:
                tgt = entry + target_cfg["fixed_rr"] * risk
        if require_pd and not in_pd(f, entry):
            result.skipped_no_pd += 1
            return None
        return PendingSetup(f, f.ifvg_direction, entry, stop, tgt, risk / tick, rating)

    def close_position(pos: Position, ts, exit_price: float, reason: str):
        s = pos.setup
        sign = 1 if s.direction == Direction.BULLISH else -1
        gained_ticks = sign * (exit_price - s.entry) / tick
        risk_usd = s.risk_ticks * tick_value
        # remaining fraction's result + any R already banked by a partial
        leg_r = gained_ticks / s.risk_ticks
        net_r = pos.banked_r + pos.frac * leg_r
        pnl = net_r * risk_usd - commission_rt
        rows.append({
            "entry_time": pos.entry_time, "exit_time": ts,
            "direction": s.direction.value, "entry": s.entry, "stop": s.stop,
            "target": s.target, "exit_price": exit_price, "exit_reason": reason,
            "risk_ticks": s.risk_ticks,
            "gross_r": pos.banked_r + pos.frac * leg_r,
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
            risk = s.risk_ticks * tick
            take_target = exit_mode != "trail"        # trail mode rides, no target
            if s.direction == Direction.BULLISH:
                if l <= position.cur_stop:
                    close_position(position, ts, position.cur_stop - slip_stop, "stop")
                    position = None
                elif take_target and h >= s.target:
                    close_position(position, ts, s.target, "target"); position = None
                else:
                    # stop moves take effect from the NEXT bar (no lookahead,
                    # conservative on same-bar stop-vs-trigger ambiguity)
                    position.best = max(position.best, h)
                    if exit_mode == "be" and position.best >= s.entry + be_trigger * risk:
                        position.cur_stop = max(position.cur_stop, s.entry)
                    elif exit_mode == "trail" and position.best >= s.entry + trail_rr * risk:
                        position.cur_stop = max(position.cur_stop, position.best - trail_rr * risk)
                    elif (exit_mode == "scale" and position.frac == 1.0
                          and position.best >= s.entry + be_trigger * risk):
                        position.banked_r = 0.5 * be_trigger   # bank half at +1R
                        position.frac = 0.5
                        position.cur_stop = max(position.cur_stop, s.entry)  # runner -> BE
            else:
                if h >= position.cur_stop:
                    close_position(position, ts, position.cur_stop + slip_stop, "stop")
                    position = None
                elif take_target and l <= s.target:
                    close_position(position, ts, s.target, "target"); position = None
                else:
                    position.best = min(position.best, l)
                    if exit_mode == "be" and position.best <= s.entry - be_trigger * risk:
                        position.cur_stop = min(position.cur_stop, s.entry)
                    elif exit_mode == "trail" and position.best <= s.entry - trail_rr * risk:
                        position.cur_stop = min(position.cur_stop, position.best + trail_rr * risk)
                    elif (exit_mode == "scale" and position.frac == 1.0
                          and position.best <= s.entry - be_trigger * risk):
                        position.banked_r = 0.5 * be_trigger
                        position.frac = 0.5
                        position.cur_stop = min(position.cur_stop, s.entry)
            if position is not None and ts.time() >= eod_flat:
                close_position(position, ts, c, "eod_flat"); position = None

        # ---- 2) update FVG state machine on this completed bar ----------
        events = list(tracker.update(i, ts, o, h, l, c))
        retested_now: set[int] = set()
        for ev in events:
            if isinstance(ev, InversionEvent):
                rating = rate_inversion(ev.fvg, o, h, l, c)
                if entry_timing == "inversion_close":
                    # aggressive: enter at market on the inversion bar's close
                    stp = make_setup(ev.fvg, i, rating, inv_ohlc=(o, h, l, c))
                    if stp is None:
                        continue
                    if ts.time() >= eod_flat or not kz.in_any(ts, allowed_kz):
                        continue
                    if not in_entry_window(ts):
                        result.skipped_entry_window += 1
                        continue
                    in_zone_news = _in_ntz(ts, ntz)
                    if respect_ntz and in_zone_news:
                        result.skipped_ntz += 1
                        continue
                    if position is not None:
                        result.skipped_position_busy += 1
                        continue
                    position = Position(stp, ts, i, kz.label(ts), in_zone_news,
                                        cur_stop=stp.stop, best=stp.entry)
                else:
                    stp = make_setup(ev.fvg, i, rating)
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
            if not in_entry_window(ts):
                result.skipped_entry_window += 1
                continue
            in_zone_news = _in_ntz(ts, ntz)
            if respect_ntz and in_zone_news:
                result.skipped_ntz += 1
                continue
            if position is not None:
                result.skipped_position_busy += 1
                continue
            entry_px = stp.entry + (slip_entry if stp.direction == Direction.BULLISH else -slip_entry)
            stp.entry = entry_px
            position = Position(stp, ts, i, kz.label(ts), in_zone_news,
                                cur_stop=stp.stop, best=entry_px)
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
        "min_rating": min_rating, "exit_mode": exit_mode,
    }
    return result
