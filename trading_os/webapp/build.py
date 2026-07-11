"""Mobile dashboard builder — self-contained HTML, no MT5 required.

Data: Yahoo Finance (ES=F / NQ=F) + ForexFactory red folders + local journal.
Output: a single HTML file, published as a Claude Artifact for phone access
and regenerated every weekday morning by a scheduled routine.

Usage:  python -m trading_os.webapp.build [output.html]
"""

from __future__ import annotations

import html
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from trading_os.config import load_config
from trading_os.core.fvg import detect_unmitigated_fvgs
from trading_os.core.timeutils import NY
from trading_os.data.loader import resample
from trading_os.data.yahoo import clean_intraday, fetch_daily, fetch_h1
from trading_os.news.calendar import NewsEvent, append_history, fetch_red_folders
from trading_os.news.scenarios import build_card
from trading_os.premarket.bias import daily_bias
from trading_os.premarket.mtf_bias import day_status, instrument_matrix
from trading_os.webapp.insights import (conclusions, run_variants, save_state,
                                        select_strategy)
from trading_os.webapp.stats import dashboard_backtest

FR_DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
FR_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]


def fr_date(dt: datetime) -> str:
    return f"{FR_DAYS[dt.weekday()]} {dt.day} {FR_MONTHS[dt.month - 1]}"


def px(x: float) -> str:
    return f"{x:,.2f}".replace(",", " ")


def md_inline(text: str) -> str:
    """Tiny markdown-to-HTML for the scenario cards (bold + escaping)."""
    out = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)


# ------------------------------------------------------------------ data

def fetch_frames(name: str) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """(daily complet, h1 nettoyé) pour un instrument, None si flux indisponible."""
    try:
        return fetch_daily(name, "6mo"), clean_intraday(fetch_h1(name, "60d"), 60)
    except Exception:
        return None


def _completed_days(daily: pd.DataFrame, now: datetime) -> pd.DataFrame:
    # drop today's partial session so "previous day" is a completed one
    return daily[[d.date() < now.date() for d in daily.index]]


def instrument_data(name: str, cfg: dict,
                    frames: dict[str, tuple | None]) -> dict | None:
    spec = cfg["instruments"][name]
    tick = spec["tick_size"]
    now = datetime.now(NY)
    pair = frames.get(name)
    if pair is None:
        return None
    daily, h1 = pair
    completed = _completed_days(daily, now)
    if len(completed) < 3:
        return None
    last_price = float(h1["close"].iloc[-1]) if len(h1) else float(daily["close"].iloc[-1])
    bias, reason = daily_bias(completed)

    sib_names = [k for k, v in frames.items() if k != name and v is not None]
    sib_h1 = sib_daily = None
    sib_name = "l'autre indice"
    if sib_names:
        sib_name = sib_names[0]
        sib_daily_full, sib_h1 = frames[sib_name]
        sib_daily = _completed_days(sib_daily_full, now)
    matrix = instrument_matrix(h1, completed, tick, cfg["ifvg"]["min_gap_ticks"],
                               sib_h1=sib_h1, sib_daily=sib_daily, sib_name=sib_name)
    prev, prev2 = completed.iloc[-1], completed.iloc[-2]
    week = completed.resample("W-FRI").agg({"high": "max", "low": "min"}).dropna()
    pw = week.iloc[-2] if len(week) >= 2 else None

    levels = [("PDH", float(prev["high"])), ("PDC", float(prev["close"])),
              ("PDL", float(prev["low"]))]
    if pw is not None:
        levels += [("PWH", float(pw["high"])), ("PWL", float(pw["low"]))]

    fvgs = []
    for tf, df_tf, keep in (("H1", h1, 4), ("H4", resample(h1, "4h"), 3),
                            ("D", completed, 2)):
        try:
            zones = detect_unmitigated_fvgs(df_tf, tick, cfg["ifvg"]["min_gap_ticks"])
            for f in zones[-keep:]:
                fvgs.append({"tf": tf, "dir": f.direction.value,
                             "bottom": f.bottom, "top": f.top,
                             "when": f.created_time})
        except Exception:
            pass
    fvgs.sort(key=lambda f: abs((f["bottom"] + f["top"]) / 2 - last_price))

    return {"name": name, "price": last_price, "bias": bias, "reason": reason,
            "matrix": matrix, "levels": levels, "fvgs": fvgs[:6],
            "prev_day": prev.name, "asof": h1.index[-1] if len(h1) else prev.name}


# ------------------------------------------------------------------ html

BIAS_META = {"haussier": ("bull", "▲", "HAUSSIER"),
             "baissier": ("bear", "▼", "BAISSIER"),
             "neutre": ("warn", "◆", "NEUTRE")}


def ladder_html(levels: list[tuple[str, float]], price: float) -> str:
    rows = sorted(levels + [("__now__", price)], key=lambda x: -x[1])
    out = ['<div class="ladder">']
    for label, value in rows:
        if label == "__now__":
            out.append(f'<div class="lrow now"><span class="ltick"></span>'
                       f'<span class="llab">PRIX</span><span class="lval">{px(value)}</span></div>')
        else:
            side = "above" if value > price else "below"
            out.append(f'<div class="lrow {side}"><span class="ltick"></span>'
                       f'<span class="llab">{label}</span><span class="lval">{px(value)}</span></div>')
    out.append("</div>")
    return "".join(out)


def instrument_card(d: dict) -> str:
    # header pill = combined D bias from the multi-TF matrix
    d_bias = next(m for m in d["matrix"] if m.tf == "D")
    cls, glyph, label = BIAS_META[d_bias.bias]

    tf_pills, sig_rows = [], []
    for m in d["matrix"]:
        c, g, lab = BIAS_META[m.bias]
        tf_pills.append(f'<span class="pill tfp {c}">{m.tf} {g} {lab}</span>')
        for s in m.signals:
            arrow = "▲" if s.vote > 0 else ("▼" if s.vote < 0 else "◆")
            sc = "bull" if s.vote > 0 else ("bear" if s.vote < 0 else "warn")
            sig_rows.append(f'<li><span class="stf">{m.tf}</span>'
                            f'<span class="sarrow {sc}">{arrow}</span>'
                            f'<span class="sname">{s.name}</span> — '
                            f'{html.escape(s.detail)}</li>')
    tf_html = (f'<div class="tfrow">{"".join(tf_pills)}</div>'
               f'<details class="sig"><summary>Signaux (structure · momentum · FVG · SMT · PDH/PDL)'
               f'</summary><ul>{"".join(sig_rows)}</ul></details>')

    fvg_rows = "".join(
        f'<tr><td class="tf">{f["tf"]}</td>'
        f'<td><span class="chip {"bull" if f["dir"] == "bullish" else "bear"}">'
        f'{"haussier" if f["dir"] == "bullish" else "baissier"}</span></td>'
        f'<td class="num">{px(f["bottom"])} → {px(f["top"])}</td></tr>'
        for f in d["fvgs"]) or '<tr><td colspan="3" class="empty">aucun FVG ouvert proche</td></tr>'
    return f"""
<section class="card">
  <header class="card-head">
    <h2>{d["name"]}</h2>
    <span class="price num">{px(d["price"])}</span>
    <span class="pill {cls}">{glyph} {label}</span>
  </header>
  {tf_html}
  <p class="reason">{html.escape(d["reason"])}</p>
  {ladder_html(d["levels"], d["price"])}
  <h3>FVG non mitigés (du plus proche au plus loin)</h3>
  <div class="scroll"><table class="fvg"><tbody>{fvg_rows}</tbody></table></div>
</section>"""


def news_card(e: NewsEvent, cfg: dict, now: datetime) -> str:
    ncfg = cfg["news"]["no_trade_zone"]
    a, b = e.no_trade_zone(ncfg["minutes_before"], ncfg["minutes_after"])
    card = build_card(e)
    past = ' past' if e.time_ny < now else ''
    return f"""
<article class="news{past}">
  <div class="news-head">
    <span class="ntime num">{e.time_ny:%H:%M}</span>
    <span class="ntitle">{html.escape(e.title)}</span>
  </div>
  <div class="nmeta">consensus <strong>{html.escape(e.forecast)}</strong> ·
       précédent <strong>{html.escape(e.previous)}</strong></div>
  <div class="ntz">NO&nbsp;TRADE {a:%H:%M}–{b:%H:%M}</div>
  <details><summary>Scénarios</summary>
    <p><span class="tag bull">AU-DESSUS</span> {md_inline(card.above)}</p>
    <p><span class="tag bear">EN DESSOUS</span> {md_inline(card.below)}</p>
    <p><span class="tag warn">EN LIGNE</span> {md_inline(card.inline)}</p>
    <p class="ctx">{md_inline(card.context)}</p>
  </details>
</article>"""


def equity_svg(trades, uid: str, value_col: str = "net_r", unit: str = "R") -> str:
    """Interactive cumulative equity curve as inline SVG (single series)."""
    import json

    cum, pts_meta = [], []
    total = 0.0
    for _, t in trades.iterrows():
        total += t[value_col]
        cum.append(total)
        when = pd.Timestamp(t["exit_time"])
        pts_meta.append(f"#{len(cum)} · {when:%d/%m} · {t[value_col]:+.2f} {unit} "
                        f"· cumul {total:+.1f} {unit}")

    W, H, L, R, T, B = 640, 230, 46, 14, 16, 28
    n = len(cum)
    lo, hi = min(0.0, min(cum)), max(0.0, max(cum))
    if hi - lo < 1e-9:
        hi = lo + 1.0
    pad = (hi - lo) * 0.08
    lo, hi = lo - pad, hi + pad
    xs = [L + (W - L - R) * (i / max(n - 1, 1)) for i in range(n)]
    ys = [T + (H - T - B) * (1 - (v - lo) / (hi - lo)) for v in cum]
    y0 = T + (H - T - B) * (1 - (0 - lo) / (hi - lo))

    # ~4 nice horizontal gridlines
    import math
    step = max(round((hi - lo) / 4), 1)
    grid, labels = [], []
    g = math.ceil(lo / step) * step
    while g <= hi:
        gy = T + (H - T - B) * (1 - (g - lo) / (hi - lo))
        grid.append(f'<line x1="{L}" y1="{gy:.1f}" x2="{W - R}" y2="{gy:.1f}" class="grid"/>')
        labels.append(f'<text x="{L - 7}" y="{gy + 3.5:.1f}" class="ax">{g:+g}</text>')
        g += step

    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"{xs[0]:.1f},{y0:.1f} " + line + f" {xs[-1]:.1f},{y0:.1f}"
    # max-drawdown segment (peak -> trough), the shape a prop-firm evaluator reads first
    dd_mark = ""
    peak_i = trough_i = cur_peak_i = 0
    run_peak, worst = cum[0], 0.0
    for i, v in enumerate(cum):
        if v > run_peak:
            run_peak, cur_peak_i = v, i
        if v - run_peak < worst:
            worst = v - run_peak
            trough_i, peak_i = i, cur_peak_i
    if worst < -1e-9 and trough_i > peak_i:
        dd_mark = (f'<line x1="{xs[peak_i]:.1f}" y1="{ys[peak_i]:.1f}" '
                   f'x2="{xs[trough_i]:.1f}" y2="{ys[trough_i]:.1f}" class="ddline"/>'
                   f'<text x="{(xs[peak_i] + xs[trough_i]) / 2:.1f}" '
                   f'y="{ys[trough_i] + 14:.1f}" class="ddlab" text-anchor="middle">'
                   f'DD max {worst:.1f} {unit}</text>')
    first = pd.Timestamp(trades.iloc[0]["exit_time"])
    last = pd.Timestamp(trades.iloc[-1]["exit_time"])
    pts = [[round(x, 1), round(y, 1), m] for x, y, m in zip(xs, ys, pts_meta)]

    return f"""
<div class="eq" id="eq-{uid}" data-pts='{json.dumps(pts, ensure_ascii=False)}'>
  <svg viewBox="0 0 {W} {H}" role="img" aria-label="Courbe d'equity en R cumulés">
    {''.join(grid)}{''.join(labels)}
    <line x1="{L}" y1="{y0:.1f}" x2="{W - R}" y2="{y0:.1f}" class="zero"/>
    <polygon points="{area}" class="area"/>
    <polyline points="{line}" class="curve"/>
    {dd_mark}
    <circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="4" class="enddot"/>
    <text x="{xs[-1] - 6:.1f}" y="{ys[-1] - 9:.1f}" class="endlab">{cum[-1]:+.1f} {unit}</text>
    <text x="{L}" y="{H - 8}" class="ax" text-anchor="start">{first:%d/%m}</text>
    <text x="{W - R}" y="{H - 8}" class="ax" text-anchor="end">{last:%d/%m}</text>
    <circle r="4.5" class="hoverdot" style="display:none"/>
  </svg>
  <div class="tip" style="display:none"></div>
</div>"""


def stability_line(trades) -> str:
    """Edge first-half vs second-half — the degradation check."""
    from trading_os.backtest.metrics import stability
    st = stability(trades)
    if st is None:
        return ""
    meta = {"stable": ("bull", "EDGE STABLE"), "renforce": ("bull", "EDGE EN RENFORCEMENT"),
            "faiblit": ("warn", "EDGE EN BAISSE"), "degrade": ("bear", "EDGE DÉGRADÉ RÉCEMMENT")}
    cls, lab = meta[st["verdict"]]
    f, s = st["first"], st["second"]
    return (f'<p class="stab"><span class="pill {cls}">{lab}</span> '
            f'1ʳᵉ moitié : WR {f["win_rate"]:.0%} · {f["expectancy_r"]:+.2f} R — '
            f'2ᵉ moitié : WR {s["win_rate"]:.0%} · {s["expectancy_r"]:+.2f} R '
            f'({f["n"]}+{s["n"]} trades)</p>')


def evolution_block(name: str) -> str:
    """How the self-tuning evolved across builds (from strategy_history.csv)."""
    from trading_os.webapp.insights import load_history
    h = load_history()
    if h is None:
        return ""
    h = h[h["instrument"] == name].tail(10)
    if h.empty:
        return ""
    delta = ""
    if len(h) >= 2:
        cur, prev = h.iloc[-1], h.iloc[-2]
        dw = cur["win_rate"] - prev["win_rate"]
        de = cur["expectancy_r"] - prev["expectancy_r"]
        arrow = lambda v: "▲" if v > 0.005 else ("▼" if v < -0.005 else "◆")
        changed = ("" if cur["variant"] == prev["variant"]
                   else ' · <strong>réglage changé</strong>')
        delta = (f'<p class="evold">vs build précédent : WR {arrow(dw)} {dw:+.0%} · '
                 f'espérance {arrow(de)} {de:+.2f} R{changed}</p>')
    rows = "".join(
        f'<tr><td>{r["date"][5:]}</td><td class="vname">{html.escape(str(r["variant"]))[:34]}</td>'
        f'<td class="num">{int(r["n_trades"])}</td><td class="num">{r["win_rate"]:.0%}</td>'
        f'<td class="num">{r["expectancy_r"]:+.2f}</td></tr>'
        for _, r in h.iloc[::-1].iterrows())
    return (f'<h3>Évolution du réglage auto</h3>{delta}'
            f'<div class="scroll"><table class="fvg"><thead><tr><th>build</th>'
            f'<th>variante</th><th>trades</th><th>WR</th><th>R/trade</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def wf_section(wf: dict, instruments: list[str]) -> str:
    """Vitrine : métriques 100 % OUT-OF-SAMPLE du walk-forward (30 j de
    sélection -> 10 j de test figé, fenêtre glissante). C'est le rendement
    « jamais vu par l'optimisation » — la seule stat qui compte."""
    blocks = []
    for name in instruments:
        r = wf.get(name)
        if not r or r["stats"].get("n_trades", 0) == 0:
            blocks.append(f'<section class="card"><header class="card-head">'
                          f'<h2>{name}</h2></header><p class="empty">Walk-forward : '
                          f'pas encore assez d\'historique pour un pli complet '
                          f'(30 j train + 10 j test) — la fenêtre grandit chaque jour.'
                          f'</p></section>')
            continue
        s = r["stats"]
        def signed(v, fmt):
            cls = "pos" if v > 0 else "neg"
            return f'<span class="kval {cls}">{v:{fmt}}</span>'
        n_folds = len(r["folds"])
        n_traded = sum(1 for f in r["folds"] if not f.get("fallback"))
        kpis = f"""
  <div class="kpis">
    <div class="kpi"><span class="klab">Espérance OOS</span>{signed(s["expectancy_r"], "+.2f")}<span class="ksub">R net / trade</span></div>
    <div class="kpi"><span class="klab">Win rate OOS</span><span class="kval">{s["win_rate"]:.0%}</span><span class="ksub">{s["n_trades"]} trades</span></div>
    <div class="kpi"><span class="klab">Profit factor</span><span class="kval">{min(s["profit_factor"], 99):.2f}</span><span class="ksub">OOS</span></div>
    <div class="kpi"><span class="klab">Total OOS</span>{signed(s["total_r"], "+.1f")}<span class="ksub">DD max {s["max_drawdown_r"]:.1f} R</span></div>
  </div>"""
        eq = equity_svg(r["trades"], f"wf-{name}") if s["n_trades"] >= 2 else ""
        rows = "".join(
            f'<tr><td>{str(f["test_start"])[5:10]}</td>'
            f'<td class="vname">{html.escape(str(f["variant"]))[:34]}</td>'
            f'<td class="num">{f["n_test"]}</td>'
            f'<td class="num">{f["test_total_r"]:+.1f}</td></tr>'
            for f in r["folds"][-8:][::-1])
        folds_html = ('<h3>Plis récents (variante figée → résultat test)</h3>'
                      '<div class="scroll"><table class="fvg"><thead><tr>'
                      '<th>test</th><th>variante (choisie sur train)</th>'
                      '<th>n</th><th>R</th></tr></thead>'
                      f'<tbody>{rows}</tbody></table></div>')
        blocks.append(f"""
<section class="card">
  <header class="card-head"><h2>{name}</h2>
    <span class="price">{n_folds} plis · {n_traded} tradés · sélection 30 j → test 10 j figé</span>
    <span class="pill bull">100 % HORS ÉCHANTILLON</span></header>
  {kpis}
  <h3>Equity out-of-sample (R cumulés, coûts inclus)</h3>
  {eq}
  {folds_html}
</section>""")
    note = ('<p class="empty">Chaque pli : la variante est choisie sur 30 jours '
            'puis appliquée FIGÉE sur les 10 jours suivants — les métriques '
            'ci-dessus n\'ont jamais été vues par la sélection. Les plis '
            '« prudence » (aucune variante défendable sur le train) ne tradent pas.</p>')
    return "".join(blocks) + note


def risk_section(cfg: dict, wf: dict, bt: dict, fb: dict,
                 instruments: list[str]) -> str:
    """Risque profil sniper : maths des séries perdantes au WR réel (OOS)."""
    from trading_os.backtest import risklab
    blocks = []
    rules = cfg.get("propfirm", {})
    budget = float(rules.get("max_loss_limit", 2000))
    for name in instruments:
        r = wf.get(name)
        stats = (r or {}).get("stats", {})
        if stats.get("n_trades", 0) >= 8:
            wr, src = stats["win_rate"], "WR out-of-sample"
        else:
            d = bt.get(name)
            if not d or d["stats"].get("n_trades", 0) < 8:
                continue
            wr, src = d["stats"]["win_rate"], "WR in-sample (OOS trop mince)"
        rec = risklab.recommended_risk_usd(wr, budget)
        scale = fb.get("active", {}).get("risk_scale", 1.0)
        eff = max(risklab.RISK_FLOOR_USD, round(rec["risk_usd"] * scale / 5) * 5)
        live = bt.get(name)
        al = risklab.streak_alert(live["trades"] if live is not None else None, wr)
        meta = {"ok": ("bull", "✓ SÉRIE NORMALE"),
                "attention": ("warn", "⚠ SÉRIE ÉLEVÉE"),
                "alerte": ("bear", "⛔ SÉRIE > P99 — MODÈLE À RE-VALIDER")}[al["level"]]
        blocks.append(f"""
<section class="card">
  <header class="card-head"><h2>{name}</h2>
    <span class="price">{src} : {wr:.0%} · budget {budget:,.0f} $ (MLL)</span>
    <span class="pill {meta[0]}">{meta[1]}</span></header>
  <div class="kpis">
    <div class="kpi"><span class="klab">Risque / trade</span><span class="kval">{eff:,.0f} $</span><span class="ksub">{eff / 50000:.2%} du compte{' · réduit ' + f'{scale:g}×' if scale < 1 else ''}</span></div>
    <div class="kpi"><span class="klab">Série p99 (100 trades)</span><span class="kval">{rec["streak_p99"]}</span><span class="ksub">pertes consécutives</span></div>
    <div class="kpi"><span class="klab">Survie</span><span class="kval">{rec["survives"]}</span><span class="ksub">pertes avant MLL</span></div>
    <div class="kpi"><span class="klab">Série en cours</span><span class="kval">{al["current"]}</span><span class="ksub">attendu ≈ {al["expected_max"]:.0f} · p99 {al["p99"]}</span></div>
  </div>
  <p class="empty">Profil « sniper » assumé : WR bas, gains larges. Le sizing garantit
  d'encaisser ≥ {risklab.SURVIVE_STREAK_MIN} pertes d'affilée en ne consommant que
  {risklab.BUDGET_FRACTION:.0%} du budget — plafond dur {risklab.HARD_RISK_CAP_USD:,.0f} $
  (0.5 %), jamais dépassé.</p>
</section>""".replace(",", " "))
    return "".join(blocks) or ('<section class="card"><p class="empty">Pas assez '
                               'de trades pour calibrer le risque.</p></section>')


FB_LABELS = {"risk_scale": "Taille de position", "entry_window": "Fenêtre d'entrée",
             "stop_buffer_ticks": "Buffer du stop", "liquidity_min_rr": "Plancher RR"}


def _fb_val(key: str, v) -> str:
    if key == "entry_window" and isinstance(v, dict):
        return f'{v["start"]}–{v["end"]}'
    if key == "risk_scale":
        return f"{v:g}×"
    return "—" if v is None else f"{v:g}"


def adjustments_section(fb: dict, review: dict | None,
                        bt_base: dict, bt_adj: dict, instruments: list[str]) -> str:
    """Transparence de la boucle d'auto-ajustement : quoi, pourquoi, depuis
    quand, avec quel effet vs le socle — et le diagnostic du jour."""
    active = fb.get("active", {})
    hist = fb.get("history", [])
    # -- ajustements actifs
    if active:
        rows_a = ""
        for h in reversed(hist):
            if h["status"] == "active" and h["key"] in active:
                rows_a += (f'<li><span class="sarrow warn">⚙</span>'
                           f'<strong>{FB_LABELS.get(h["key"], h["key"])}</strong> : '
                           f'{_fb_val(h["key"], h["from"])} → '
                           f'<strong>{_fb_val(h["key"], h["to"])}</strong> '
                           f'(depuis le {h["date"][5:]}) — {html.escape(h["reason"])}</li>')
        active_html = f'<ul class="conc">{rows_a}</ul>'
    else:
        active_html = ('<p class="empty">Aucun ajustement actif — le socle tourne '
                       'tel quel. La boucle n\'ajuste que sur évidence '
                       '(≥ 8 trades derrière chaque règle), une décision max par jour.</p>')
    # -- comparaison socle vs ajusté
    cmp_html = ""
    if active:
        for name in instruments:
            b, a = bt_base.get(name), bt_adj.get(name)
            if not b or not a or b["stats"]["n_trades"] == 0 or a["stats"]["n_trades"] == 0:
                continue
            bs, as_ = b["stats"], a["stats"]
            cmp_html += (f'<p class="evold"><strong>{name}</strong> — socle : '
                         f'{bs["n_trades"]} trades · WR {bs["win_rate"]:.0%} · '
                         f'{bs["expectancy_r"]:+.2f} R — ajusté : '
                         f'{as_["n_trades"]} trades · WR {as_["win_rate"]:.0%} · '
                         f'{as_["expectancy_r"]:+.2f} R</p>')
    # -- historique des décisions
    hist_html = ""
    if hist:
        rows_h = "".join(
            f'<tr><td>{h["date"][5:]}</td><td class="vname">'
            f'{FB_LABELS.get(h["key"], h["key"])} → {_fb_val(h["key"], h["to"])}</td>'
            f'<td>{"✓ actif" if h["status"] == "active" else h["status"]}</td></tr>'
            for h in list(reversed(hist))[:8])
        hist_html = ('<h3>Historique des décisions</h3><div class="scroll">'
                     '<table class="fvg"><thead><tr><th>date</th><th>décision</th>'
                     f'<th>statut</th></tr></thead><tbody>{rows_h}</tbody></table></div>')
    # -- diagnostic du jour (le POURQUOI)
    diag_html = ""
    if review is not None:
        bullets = "".join(f"<li>{html.escape(b)}</li>" for b in review["bullets"])
        diag_html = f'<h3>Diagnostic (30 j glissants)</h3><ul class="conc">{bullets}</ul>'
    guard = ('<p class="empty">Garde-fous durs (non configurables) : socle IFVG gelé, '
             'risque jamais &gt; 1× (~200 $), réduction seulement en drawdown, stop '
             'obligatoire (buffer 1–6 ticks), RR plancher 1.5–3.0, fenêtre d\'entrée '
             'toujours dans la killzone (≥ 60 min), 1 décision/jour, annulation auto '
             'si l\'espérance ne suit pas après 10 trades.</p>')
    return (f'<section class="card">{active_html}{cmp_html}{hist_html}'
            f'{diag_html}{guard}</section>')


def backtest_section(cfg: dict, state: dict, bt: dict) -> str:
    blocks = []
    for name in cfg["premarket"]["instruments"]:
        sel = state.get(name, {"variant": "défaut", "patch": {}, "reason": ""})
        d = bt.get(name)
        if d is None:
            blocks.append(f'<section class="card"><header class="card-head">'
                          f'<h2>{name}</h2></header><p class="empty">En attente '
                          f'd’accumulation de données — la routine du matin nourrit '
                          f'le dataset jour après jour.</p></section>')
            continue
        s = d["stats"]
        meta = (f'{d.get("source", d["tf"])} · {d["n_bars"]:,} barres · '
                f'{d["start"]:%d/%m/%Y} → {d["end"]:%d/%m/%Y}').replace(",", " ")
        if s["n_trades"] == 0:
            blocks.append(f'<section class="card"><header class="card-head">'
                          f'<h2>{name}</h2><span class="price">{meta}</span></header>'
                          f'<p class="empty">Aucun setup IFVG complet sur la période '
                          f'testée (fenêtre 9:30–11:30 uniquement) — le dataset '
                          f'grandit chaque matin.</p></section>')
            continue

        def signed(v, fmt):
            cls = "pos" if v > 0 else "neg"
            return f'<span class="kval {cls}">{v:{fmt}}</span>'

        kpis = f"""
  <div class="kpis">
    <div class="kpi"><span class="klab">Espérance / trade</span>{signed(s["expectancy_r"], "+.2f")}<span class="ksub">R net</span></div>
    <div class="kpi"><span class="klab">Win rate</span><span class="kval">{s["win_rate"]:.0%}</span><span class="ksub">{s["n_trades"]} trades</span></div>
    <div class="kpi"><span class="klab">Profit factor</span><span class="kval">{s["profit_factor"]:.2f}</span><span class="ksub">gains/pertes</span></div>
    <div class="kpi"><span class="klab">Total</span>{signed(s["total_r"], "+.1f")}<span class="ksub">DD max {s["max_drawdown_r"]:.1f} R</span></div>
  </div>"""

        tables = ""
        for title, bd in (("Par grade d'inversion", d["by_grade"]),
                          ("Par killzone", d["by_kz"])):
            if bd is None or bd.empty:
                continue
            rows = "".join(
                f'<tr><td>{idx}</td><td class="num">{int(r["trades"])}</td>'
                f'<td class="num">{r["win_rate"]:.0%}</td>'
                f'<td class="num">{r["avg_r"]:+.2f}</td></tr>'
                for idx, r in bd.iterrows())
            tables += (f'<h3>{title}</h3><div class="scroll"><table class="fvg">'
                       f'<thead><tr><th></th><th>trades</th><th>WR</th><th>R moy</th>'
                       f'</tr></thead><tbody>{rows}</tbody></table></div>')

        auto_line = (f'<p class="autotune">⚙ Réglage : '
                     f'<strong>{html.escape(sel["variant"])}</strong> — '
                     f'{html.escape(sel["reason"])}</p>')
        reg_on = cfg["backtest"].get("registered_on")
        if reg_on and not d["trades"].empty:
            t = d["trades"]
            fwd = t[pd.to_datetime(t["exit_time"]) >= pd.Timestamp(reg_on, tz="America/New_York")]
            if len(fwd):
                fr = fwd["net_r"]
                auto_line += (f'<p class="autotune">🔒 VRAI hors-échantillon depuis le gel '
                              f'({reg_on}) : {len(fwd)} trades · {fr.sum():+.1f} R · '
                              f'WR {(fr > 0).mean():.0%}</p>')
            else:
                auto_line += (f'<p class="autotune">🔒 Config gelée le {reg_on} — chaque '
                              f'nouveau jour de marché est du VRAI hors-échantillon '
                              f'(0 trade depuis le gel pour l\'instant).</p>')
        blocks.append(f"""
<section class="card">
  <header class="card-head"><h2>{name}</h2><span class="price">{meta}</span></header>
  {auto_line}
  {stability_line(d["trades"])}
  {kpis}
  <h3>Equity (R cumulés, coûts inclus)</h3>
  {equity_svg(d["trades"], name)}
  {evolution_block(name)}
  {tables}
</section>""")
    note = ('<p class="empty">Backtest réel (moteur IFVG, fenêtre 9:30–11:30, coûts '
            'et slippage inclus) sur données Yahoo accumulées quotidiennement, avec '
            'le réglage choisi automatiquement chaque matin par les garde-fous. '
            'Bascule automatique 5m → 1m dès que l’historique 1m accumulé suffit. '
            'Données indicatives en attendant l’export MT5.</p>')
    return "".join(blocks) + note


def insights_section(rows: list[dict], state: dict) -> str:
    chosen = "".join(
        f'<li>⚙ <strong>{inst}</strong> → « {html.escape(sel["variant"])} » '
        f'({html.escape(sel["reason"])})</li>'
        for inst, sel in state.items())
    bullets = chosen + "".join(f"<li>{md_inline(c)}</li>" for c in conclusions(rows))
    table = ""
    if rows:
        body = "".join(
            f'<tr><td>{r["instrument"]}</td><td class="vname">{html.escape(r["variant"])}</td>'
            f'<td class="num">{r["n_trades"]}</td>'
            + (f'<td class="num">{r["win_rate"]:.0%}</td>'
               f'<td class="num">{r["expectancy_r"]:+.2f}</td>'
               f'<td class="num">{r["total_r"]:+.1f}</td>'
               if r["n_trades"] else '<td class="num">—</td><td class="num">—</td><td class="num">—</td>')
            + "</tr>"
            for r in rows)
        table = ('<h3>Comparaison des variantes (période accumulée)</h3>'
                 '<div class="scroll"><table class="fvg"><thead><tr><th></th>'
                 '<th>variante</th><th>trades</th><th>WR</th><th>R/trade</th>'
                 '<th>total R</th></tr></thead><tbody>' + body + "</tbody></table></div>")
    return f'<section class="card"><ul class="conc">{bullets}</ul>{table}</section>'


def build_dashboard(cfg: dict, out_path: str | Path, autotune: bool = True) -> Path:
    """autotune=False = rebuild intraday léger : réutilise strategy_state.json
    du matin (pas de grille de variantes, pas d'append d'historique — l'autotune
    reste strictement quotidien pour éviter l'overfitting intraday)."""
    now = datetime.now(NY)
    day_kind, day_label = day_status(now)

    # instruments tradés + la référence SMT (ES) : fetchée pour la divergence
    # ES/NQ dans instrument_matrix, mais SANS carte ni backtest.
    fetch_names = list(cfg["premarket"]["instruments"])
    smt_ref = cfg["premarket"].get("smt_reference")
    if smt_ref and smt_ref not in fetch_names:
        fetch_names.append(smt_ref)
    frames = {name: fetch_frames(name) for name in fetch_names}
    cards, asof, heros = [], None, []
    for name in cfg["premarket"]["instruments"]:
        d = instrument_data(name, cfg, frames)
        if d:
            cards.append(instrument_card(d))
            asof = d["asof"]
            d_bias = next(m for m in d["matrix"] if m.tf == "D")
            heros.append({"name": name, "price": d["price"], "bias": d_bias.bias})
    instruments_html = "".join(cards) or \
        '<section class="card"><p class="empty">Données de marché indisponibles.</p></section>'
    # auto-tune : la grille complète ne tourne qu'au build QUOTIDIEN ; en
    # intraday on rejoue le choix persisté du matin (anti-overfitting).
    variant_rows: list[dict] = []
    wf: dict[str, dict | None] = {}
    if autotune:
        from trading_os.backtest.walkforward import walk_forward
        from trading_os.webapp.insights import variant_trades
        for name in cfg["premarket"]["instruments"]:
            try:
                rows, streams = variant_trades(cfg, name)
                variant_rows += rows
                wcfg = cfg["backtest"].get("walkforward", {})
                wf[name] = walk_forward(streams, name,
                                        train_days=wcfg.get("train_days", 30),
                                        test_days=wcfg.get("test_days", 10))
            except Exception:
                wf[name] = None
        state = {name: select_strategy(variant_rows, name)
                 for name in cfg["premarket"]["instruments"]}
        # PRÉ-ENREGISTREMENT : la config gelée prime sur la sélection du jour
        # (anti-biais de sélection ; la grille reste calculée pour information).
        reg = cfg["backtest"].get("registered_variant")
        if reg:
            from trading_os.webapp.insights import PATCHES
            for name in state:
                row = next((r for r in variant_rows
                            if r["instrument"] == name and r["variant"] == reg), None)
                why = (f"{row['n_trades']} trades · WR {row['win_rate']:.0%} · "
                       f"{row['expectancy_r']:+.2f} R · PF {min(row['profit_factor'], 99):.2f}"
                       if row and row.get("n_trades") else "")
                state[name] = {"variant": reg, "patch": PATCHES.get(reg, {}),
                               "reason": ("config PRÉ-ENREGISTRÉE le "
                                          f"{cfg['backtest'].get('registered_on', '?')} — "
                                          + why)}
        save_state(state)
        from trading_os.backtest.walkforward import save_results
        save_results(wf)
    else:
        from trading_os.backtest.walkforward import load_results
        from trading_os.webapp.insights import saved_state
        wf = load_results()                       # OOS du matin, affiché tel quel
        state = saved_state(cfg["premarket"]["instruments"])
    # run the auto-tuned backtest ONCE; reused by the backtest section
    bt: dict[str, dict | None] = {}
    for name in cfg["premarket"]["instruments"]:
        try:
            bt[name] = dashboard_backtest(cfg, name, patch=state[name]["patch"])
        except Exception:
            bt[name] = None
    # ---- boucle d'auto-ajustement (paramètres secondaires, socle gelé) ----
    from trading_os.backtest import feedback
    from trading_os.backtest.diagnose import daily_review
    inst0 = cfg["premarket"]["instruments"][0]
    review = daily_review(bt[inst0]["trades"]) if bt.get(inst0) else None
    fb = feedback.load_state()
    if autotune:      # les décisions ne se prennent qu'au build quotidien
        base = {"stop_buffer_ticks": cfg["ifvg"]["stop_buffer_ticks"],
                "liquidity_min_rr": cfg["ifvg"]["target"]["liquidity_min_rr"]}
        try:
            fb, fb_notes = feedback.step(review, fb, base)
            feedback.save_state(fb)
        except Exception:
            fb_notes = []
    # rejouer le backtest avec les overrides actifs (config réellement tradée)
    bt_base = dict(bt)
    overrides = feedback.as_patch(fb.get("active", {}))
    if overrides:
        for name in cfg["premarket"]["instruments"]:
            try:
                bt[name] = dashboard_backtest(
                    cfg, name, patch={**state[name]["patch"], **overrides})
            except Exception:
                pass
        if review is not None and bt.get(inst0):
            review = daily_review(bt[inst0]["trades"]) or review
        # anti-overfit : l'ajusté doit prouver qu'il bat le socle (mesure directe)
        if autotune and bt_base.get(inst0) and bt.get(inst0):
            try:
                fb, rv_notes = feedback.compare_adjusted(
                    fb, bt_base[inst0]["stats"], bt[inst0]["stats"],
                    n_base_now=bt_base[inst0]["stats"].get("n_trades", 0))
                feedback.save_state(fb)
                if rv_notes and not feedback.as_patch(fb.get("active", {})):
                    bt = bt_base      # tous les overrides annulés -> socle
            except Exception:
                pass
    if autotune:
        try:
            from trading_os.webapp.insights import append_history
            append_history(state, bt)      # trace quotidienne de l'auto-réglage
        except Exception:
            pass
        try:                               # corpus « discrétion » (wiki/journal/)
            inst0_ = cfg["premarket"]["instruments"][0]
            if bt.get(inst0_) is not None and not bt[inst0_]["trades"].empty:
                bt[inst0_]["trades"].to_csv("data/trades_current.csv", index=False)
                import subprocess, sys as _sys
                subprocess.run([_sys.executable, "wiki/generate_journal.py"],
                               timeout=60, check=False)
        except Exception:
            pass
    backtest_html = backtest_section(cfg, state, bt)
    wf_html = wf_section(wf, cfg["premarket"]["instruments"])
    risk_html = risk_section(cfg, wf, bt, fb, cfg["premarket"]["instruments"])
    adjust_html = adjustments_section(fb, review, bt_base, bt,
                                      cfg["premarket"]["instruments"])
    if autotune:
        insights_html = insights_section(variant_rows, state)
    else:
        chosen = "".join(f'<li>⚙ <strong>{n}</strong> → « {html.escape(s["variant"])} » '
                         f'({html.escape(s["reason"])})</li>' for n, s in state.items())
        insights_html = ('<section class="card"><ul class="conc">' + chosen +
                         '<li>Rafraîchissement intraday : prix, biais, news et stats '
                         'recalculés — la comparaison des variantes et l\'auto-réglage '
                         'ne tournent qu\'au build du matin (anti-overfitting).</li>'
                         '</ul></section>')

    try:
        events = fetch_red_folders(cfg)
        append_history(events, cfg["backtest"]["news_history_csv"])
    except Exception:
        events = []
    today = [e for e in events if e.time_ny.date() == now.date()]
    week = [e for e in events if e.time_ny.date() > now.date()]
    news_html = "".join(news_card(e, cfg, now) for e in today) or \
        '<p class="allclear">✓ Aucun red folder USD aujourd’hui — journée technique pure.</p>'

    # --- hero « en un coup d'œil » ----------------------------------------
    upcoming = [e for e in today if e.time_ny > now]
    if day_kind == "closed":
        news_tile = ('<div class="htile"><span class="hlab">Marché</span>'
                     '<span class="hval warn">FERMÉ</span>'
                     '<span class="hsub">week-end / férié</span></div>')
    elif upcoming:
        nxt = upcoming[0]
        mins = int((nxt.time_ny - now).total_seconds() // 60)
        cd = f"{mins // 60}h{mins % 60:02d}" if mins >= 60 else f"{mins} min"
        sev = "bear" if mins <= 45 else "warn"
        news_tile = (f'<div class="htile"><span class="hlab">Prochain red folder</span>'
                     f'<span class="hval {sev}">{cd}</span>'
                     f'<span class="hsub">{html.escape(nxt.title[:22])}</span></div>')
    else:
        news_tile = ('<div class="htile"><span class="hlab">News</span>'
                     '<span class="hval bull">RAS</span>'
                     '<span class="hsub">journée technique</span></div>')
    short = {"haussier": "HAUSSE", "baissier": "BAISSE", "neutre": "NEUTRE"}
    hero_tiles = news_tile
    for h in heros:
        c, g, _ = BIAS_META[h["bias"]]
        hero_tiles += (f'<div class="htile"><span class="hlab">{h["name"]} · biais jour</span>'
                       f'<span class="hval {c}">{g} {short[h["bias"]]}</span>'
                       f'<span class="hsub num">{px(h["price"])}</span></div>')
    # météo du risque (VIX/or/DXY) — équivalent lite de la carte Glint
    try:
        from trading_os.premarket.risk import risk_weather
        rw = risk_weather()
    except Exception:
        rw = None
    if rw is not None:
        rmeta = {"risk_on": ("bull", "RISK-ON"), "neutre": ("warn", "NEUTRE"),
                 "risk_off": ("bear", "RISK-OFF")}[rw.verdict]
        hero_tiles += (f'<div class="htile"><span class="hlab">Météo du risque</span>'
                       f'<span class="hval {rmeta[0]}">{rmeta[1]}</span>'
                       f'<span class="hsub num">VIX {rw.vix:.1f} ({rw.vix_chg:+.1f})</span></div>')
    hero_html = f'<div class="hero">{hero_tiles}</div>'

    # prévision news 24 h : verdict directionnel indices (pas de fil brut —
    # décision utilisateur : « je veux juste bullish ou bearish »)
    try:
        from trading_os.news.headlines import fetch_macro_headlines, news_bias
        nb = news_bias(fetch_macro_headlines(limit=14))
    except Exception:
        nb = None
    macro_html = ""
    if nb is not None:
        vmeta = {"bullish": ("bull", "▲ BULLISH"), "bearish": ("bear", "▼ BEARISH"),
                 "neutre": ("warn", "◆ NEUTRE")}[nb["verdict"]]
        drivers = "".join(
            f'<li><span class="sarrow {"bull" if d > 0 else "bear"}">'
            f'{"▲" if d > 0 else "▼"}</span> {html.escape(h.title[:90])}'
            f' <span class="hsrc">{html.escape(h.source[:18])}</span></li>'
            for d, h in nb["drivers"])
        rw_line = (f'<p class="empty">Météo du risque : {html.escape(rw.detail)}</p>'
                   if rw is not None else "")
        macro_html = (
            f'<div class="eyebrow">// Prévision news — dernières 24 h</div>'
            f'<section class="card"><header class="card-head"><h2>Indices US</h2>'
            f'<span class="price">{nb["n_bull"]} signaux haussiers · '
            f'{nb["n_bear"]} baissiers</span>'
            f'<span class="pill {vmeta[0]}">{vmeta[1]}</span></header>'
            f'<ul class="mfeed">{drivers}</ul>{rw_line}'
            f'<p class="empty">Classification mécanique par mots-clés — un contexte, '
            f'pas un signal d\'entrée. Le setup IFVG reste le seul déclencheur.</p>'
            f'</section>')

    week_html = ""
    if week:
        items = "".join(f'<li><span class="num">{FR_DAYS[e.time_ny.weekday()][:3]} '
                        f'{e.time_ny:%H:%M}</span> {html.escape(e.title)}</li>'
                        for e in week[:8])
        week_html = f'<h3>À venir cette semaine</h3><ul class="week">{items}</ul>'

    checklist_html = "".join(
        f'<li><label><input type="checkbox" data-k="c{i}"><span>{html.escape(item)}</span></label></li>'
        for i, item in enumerate(cfg["premarket"]["checklist"]))

    kz = cfg["killzones"]["ny_am"]
    asof_txt = f"{asof:%H:%M}" if asof is not None else "--:--"
    asof_txt = (f"{FR_DAYS[asof.weekday()][:3]} {asof:%H:%M}"
                if asof is not None else asof_txt)
    kz_pill = "bull" if day_kind == "trading" else "warn"
    kz_note = ("Seule fenêtre autorisée par la méthodologie. Pas de trade en dehors, "
               "pas de trade en no-trade-zone news, 1 micro contrat max, démo uniquement."
               if day_kind == "trading" else
               "Marché fermé aujourd'hui — aucune fenêtre de trading. Profitez-en pour "
               "la revue du journal et la préparation de la semaine.")

    page = f"""<title>Trading OS — Prémarché</title>
<style>
:root {{
  --bg:#0a0e14; --surface:#121a24; --raised:#1a2430; --line:#25313f;
  --ink:#e8eef6; --ink2:#8a99ab; --ink3:#556575;
  --bull:#1fbf75; --bear:#f0453f; --warn:#e0a52e; --accent:#3d8bff;
  --bull-ink:#2ee08c; --bear-ink:#ff6b64; --warn-ink:#f0bd54; --accent-ink:#69a8ff;
}}
@media (prefers-color-scheme: light) {{ :root {{
  --bg:#eef1f5; --surface:#ffffff; --raised:#e8edf2; --line:#d5dde6;
  --ink:#0e1621; --ink2:#55636f; --ink3:#8592a0;
  --bull:#0f9d63; --bear:#d63a3a; --warn:#9a6b12; --accent:#1667d6;
  --bull-ink:#0b7a4d; --bear-ink:#bf2e2e; --warn-ink:#7c5510; --accent-ink:#1258bd;
}} }}
:root[data-theme="dark"] {{
  --bg:#0a0e14; --surface:#121a24; --raised:#1a2430; --line:#25313f;
  --ink:#e8eef6; --ink2:#8a99ab; --ink3:#556575;
  --bull:#1fbf75; --bear:#f0453f; --warn:#e0a52e; --accent:#3d8bff;
  --bull-ink:#2ee08c; --bear-ink:#ff6b64; --warn-ink:#f0bd54; --accent-ink:#69a8ff;
}}
:root[data-theme="light"] {{
  --bg:#eef1f5; --surface:#ffffff; --raised:#e8edf2; --line:#d5dde6;
  --ink:#0e1621; --ink2:#55636f; --ink3:#8592a0;
  --bull:#0f9d63; --bear:#d63a3a; --warn:#9a6b12; --accent:#1667d6;
  --bull-ink:#0b7a4d; --bear-ink:#bf2e2e; --warn-ink:#7c5510; --accent-ink:#1258bd;
}}
* {{ box-sizing:border-box }}
body {{ background:var(--bg); color:var(--ink); margin:0;
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
.mono, h1,h2,h3,.num,.pill,.chip,.tag,.eyebrow,.ntime,.ntz,.llab,.lval,.tf
  {{ font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace; }}
.num {{ font-variant-numeric:tabular-nums }}
.wrap {{ max-width:680px; margin:0 auto; padding:0 14px 48px }}
/* -- PC : élargit et met les cartes appairées côte à côte -- */
.grid2 {{ display:grid; gap:14px }}
.grid2 > .card {{ margin-bottom:0 }}
.grid2 > .empty {{ margin:2px 0 0 }}
@media (min-width:860px) {{
  .wrap {{ max-width:1080px; padding-bottom:56px }}
  .grid2 {{ grid-template-columns:1fr 1fr }}
  .grid2 > .empty {{ grid-column:1 / -1 }}
  .hero {{ grid-template-columns:repeat(6,1fr) }}
}}
/* -- top bar -- */
.top {{ position:sticky; top:0; z-index:5; background:var(--bg);
  border-bottom:1px solid var(--line); padding:10px 14px;
  display:flex; align-items:baseline; gap:10px; }}
.top h1 {{ font-size:15px; letter-spacing:.14em; margin:0 }}
.top .date {{ color:var(--ink2); font-size:12.5px; }}
.demo {{ margin-left:auto; font-size:10.5px; letter-spacing:.1em; color:var(--bear-ink);
  border:1px solid var(--bear); padding:2px 7px; border-radius:3px; }}
/* -- day banner -- */
.banner {{ margin-top:14px; padding:8px 14px; border-radius:8px; font-size:12.5px;
  letter-spacing:.08em; font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace }}
.banner.trading {{ color:var(--bull-ink); border:1px solid var(--bull);
  background:color-mix(in srgb, var(--bull) 10%, transparent) }}
.banner.closed {{ color:var(--warn-ink); border:1px solid var(--warn);
  background:color-mix(in srgb, var(--warn) 10%, transparent) }}
/* -- hero « en un coup d'œil » -- */
.hero {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:12px }}
.htile {{ background:var(--surface); border:1px solid var(--line); border-radius:10px;
  padding:11px 12px; display:flex; flex-direction:column; gap:3px; min-width:0 }}
.hlab {{ font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:var(--ink3);
  font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace }}
.hval {{ font-size:16px; font-weight:700; letter-spacing:.02em; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis;
  font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace }}
.hval.bull {{ color:var(--bull-ink) }} .hval.bear {{ color:var(--bear-ink) }}
.hval.warn {{ color:var(--warn-ink) }}
.hsub {{ font-size:11px; color:var(--ink3); white-space:nowrap; overflow:hidden;
  text-overflow:ellipsis }}
/* -- sections -- */
.eyebrow {{ font-size:11px; letter-spacing:.18em; color:var(--ink3);
  text-transform:uppercase; margin:26px 2px 10px; }}
.card {{ background:var(--surface); border:1px solid var(--line); border-radius:10px;
  padding:14px 16px; margin-bottom:14px; min-width:0; }}
.card-head {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 12px; }}
.card-head h2 {{ font-size:19px; margin:0; letter-spacing:.06em }}
.price {{ color:var(--ink2); font-size:15px; min-width:0; overflow-wrap:anywhere }}
.pill {{ margin-left:auto; font-size:11.5px; letter-spacing:.08em; padding:3px 9px;
  border-radius:999px; border:1px solid; }}
.pill.bull {{ color:var(--bull-ink); border-color:var(--bull); background:color-mix(in srgb, var(--bull) 14%, transparent) }}
.pill.bear {{ color:var(--bear-ink); border-color:var(--bear); background:color-mix(in srgb, var(--bear) 14%, transparent) }}
.pill.warn {{ color:var(--warn-ink); border-color:var(--warn); background:color-mix(in srgb, var(--warn) 14%, transparent) }}
.reason {{ color:var(--ink2); font-size:13.5px; margin:8px 0 12px }}
/* -- multi-timeframe bias row -- */
.tfrow {{ display:flex; flex-wrap:wrap; gap:6px; margin:10px 0 2px }}
.pill.tfp {{ margin-left:0; font-size:12px; padding:4px 10px }}
details.sig {{ margin:6px 0 2px }}
details.sig ul {{ list-style:none; padding:0; margin:6px 0 0; font-size:12.5px; color:var(--ink2) }}
details.sig li {{ padding:3px 0; border-bottom:1px solid var(--line) }}
.stf {{ display:inline-block; width:26px; color:var(--ink3);
  font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace; font-size:11px }}
.sarrow {{ margin-right:5px }}
.sarrow.bull {{ color:var(--bull-ink) }} .sarrow.bear {{ color:var(--bear-ink) }}
.sarrow.warn {{ color:var(--warn-ink) }}
.sname {{ font-weight:600 }}
h3 {{ font-size:11px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--ink3); margin:16px 0 8px; font-weight:600 }}
/* -- ladder -- */
.ladder {{ border-left:2px solid var(--line); margin:4px 0 4px 4px }}
.lrow {{ display:flex; align-items:center; gap:10px; padding:3px 0; font-size:13.5px }}
.ltick {{ width:14px; height:0; border-top:1px solid var(--ink3); margin-left:-1px }}
.llab {{ color:var(--ink2); width:44px; font-size:12px; letter-spacing:.08em }}
.lval {{ font-variant-numeric:tabular-nums }}
.lrow.now {{ color:var(--accent-ink); font-weight:700 }}
.lrow.now .ltick {{ border-top:2px solid var(--accent); width:22px }}
.lrow.now .llab {{ color:var(--accent-ink) }}
/* -- tables & chips -- */
.scroll {{ overflow-x:auto }}
table.fvg {{ border-collapse:collapse; width:100%; font-size:13.5px }}
table.fvg td, table.fvg th {{ padding:5px 10px 5px 0; border-bottom:1px solid var(--line);
  text-align:left; white-space:nowrap }}
table.fvg th {{ color:var(--ink3); font-size:11px; letter-spacing:.1em; text-transform:uppercase }}
.tf {{ color:var(--ink2); width:36px }}
.chip {{ font-size:11px; padding:1.5px 8px; border-radius:999px; border:1px solid }}
.chip.bull {{ color:var(--bull-ink); border-color:var(--bull) }}
.chip.bear {{ color:var(--bear-ink); border-color:var(--bear) }}
.empty, .ctx {{ color:var(--ink3); font-size:13px }}
/* -- news -- */
.news {{ background:var(--surface); border:1px solid var(--line); border-left:3px solid var(--bear);
  border-radius:8px; padding:12px 14px; margin-bottom:10px }}
.news.past {{ border-left-color:var(--line); opacity:.62 }}
.news-head {{ display:flex; gap:10px; align-items:baseline }}
.ntime {{ color:var(--bear-ink); font-weight:700 }}
.news.past .ntime {{ color:var(--ink3) }}
.ntitle {{ font-weight:600 }}
.nmeta {{ color:var(--ink2); font-size:13px; margin-top:3px }}
.ntz {{ display:inline-block; margin-top:8px; font-size:11px; letter-spacing:.1em;
  color:var(--warn-ink); border:1px dashed var(--warn); padding:2px 8px; border-radius:4px }}
details {{ margin-top:8px }}
summary {{ cursor:pointer; color:var(--accent-ink); font-size:13px }}
details p {{ font-size:13.5px; margin:8px 0 }}
.tag {{ font-size:10.5px; letter-spacing:.08em; padding:1px 6px; border-radius:3px;
  border:1px solid; margin-right:4px }}
.tag.bull {{ color:var(--bull-ink); border-color:var(--bull) }}
.tag.bear {{ color:var(--bear-ink); border-color:var(--bear) }}
.tag.warn {{ color:var(--warn-ink); border-color:var(--warn) }}
.allclear {{ color:var(--bull-ink); background:color-mix(in srgb, var(--bull) 10%, transparent);
  border:1px solid var(--bull); border-radius:8px; padding:10px 14px; font-size:14px }}
ul.week {{ list-style:none; padding:0; margin:8px 0 0; font-size:13.5px; color:var(--ink2) }}
ul.week li {{ padding:4px 0; border-bottom:1px solid var(--line) }}
ul.week .num {{ color:var(--ink3); margin-right:8px }}
/* -- killzone + checklist -- */
.kzline {{ display:flex; gap:10px; align-items:center; font-size:14px }}
.kzline .pill {{ margin-left:0 }}
ul.check {{ list-style:none; padding:0; margin:0 }}
ul.check li {{ border-bottom:1px solid var(--line) }}
ul.check label {{ display:flex; gap:12px; padding:10px 2px; cursor:pointer; align-items:flex-start }}
ul.check input {{ accent-color:var(--accent); width:18px; height:18px; margin-top:2px; flex:none }}
ul.check input:checked + span {{ color:var(--ink3); text-decoration:line-through }}
ul.check span {{ font-size:14px }}
/* -- backtest KPIs & equity chart -- */
.kpis {{ display:grid; grid-template-columns:repeat(2,1fr); gap:8px; margin:10px 0 4px }}
@media (min-width:560px) {{ .kpis {{ grid-template-columns:repeat(4,1fr) }} }}
.kpi {{ background:var(--raised); border:1px solid var(--line); border-radius:8px;
  padding:9px 11px; display:flex; flex-direction:column; gap:1px }}
.klab {{ font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:var(--ink3);
  font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace }}
.kval {{ font-size:20px; font-weight:700; font-variant-numeric:tabular-nums;
  font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace }}
.kval.pos {{ color:var(--bull-ink) }} .kval.neg {{ color:var(--bear-ink) }}
.ksub {{ font-size:11px; color:var(--ink3) }}
.eq {{ position:relative; margin:4px 0 6px }}
.eq svg {{ width:100%; height:auto; display:block }}
.eq .grid {{ stroke:var(--line); stroke-width:1 }}
.eq .zero {{ stroke:var(--ink3); stroke-width:1; stroke-dasharray:3 4 }}
.eq .ax, .eq .endlab {{ fill:var(--ink3); font-size:11px; text-anchor:end;
  font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace;
  font-variant-numeric:tabular-nums }}
.eq .endlab {{ fill:var(--accent-ink); font-weight:700 }}
.eq .curve {{ fill:none; stroke:var(--accent); stroke-width:2;
  stroke-linejoin:round; stroke-linecap:round }}
.eq .area {{ fill:var(--accent); opacity:.13 }}
.eq .enddot {{ fill:var(--accent) }}
.eq .hoverdot {{ fill:var(--bg); stroke:var(--accent); stroke-width:2 }}
.eq .tip {{ position:absolute; top:6px; left:8px; background:var(--raised);
  border:1px solid var(--line); border-radius:6px; padding:4px 9px; font-size:12px;
  color:var(--ink); pointer-events:none; white-space:nowrap;
  font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace }}
.autotune {{ font-size:12.5px; color:var(--accent-ink); margin:8px 0 2px;
  overflow-wrap:anywhere;
  font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace }}
.eq .ddline {{ stroke:var(--bear, #e5484d); stroke-width:1.5; stroke-dasharray:4 3; opacity:.8 }}
.eq .ddlab {{ fill:var(--bear, #e5484d); font-size:10.5px;
  font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace }}
.stab {{ font-size:12.5px; color:var(--ink2); margin:6px 0 2px; display:flex;
  flex-wrap:wrap; align-items:center; gap:8px;
  font-variant-numeric:tabular-nums }}
.evold {{ font-size:12.5px; color:var(--ink2); margin:2px 0 8px;
  font-variant-numeric:tabular-nums }}
/* -- fil macro -- */
ul.mfeed {{ list-style:none; padding:0; margin:0; font-size:13.5px }}
ul.mfeed li {{ padding:7px 0; border-bottom:1px solid var(--line); overflow-wrap:anywhere }}
ul.mfeed li:last-child {{ border-bottom:none }}
.hsrc {{ color:var(--accent-ink); font-size:11px; letter-spacing:.08em;
  text-transform:uppercase; margin-right:6px;
  font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace }}
/* -- conclusions -- */
ul.conc {{ list-style:none; padding:0; margin:0; font-size:13.5px }}
ul.conc li {{ padding:8px 0 8px 18px; border-bottom:1px solid var(--line); position:relative }}
ul.conc li::before {{ content:"▸"; position:absolute; left:0; color:var(--accent-ink) }}
ul.conc li:last-child {{ border-bottom:none; color:var(--ink3); font-size:12.5px }}
.vname {{ white-space:normal; min-width:150px }}
footer {{ color:var(--ink3); font-size:12px; margin-top:30px; line-height:1.6 }}
a {{ color:var(--accent-ink) }}
input:focus-visible, summary:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px }}
@media (prefers-reduced-motion: no-preference) {{
  details[open] p {{ animation:fade .25s ease }}
  @keyframes fade {{ from {{ opacity:0; transform:translateY(-2px) }} to {{ opacity:1 }} }}
}}
</style>

<div class="top wrap" style="max-width:none">
  <h1>TRADING&nbsp;OS</h1>
  <span class="date">{fr_date(now)} · maj {now:%H:%M} NY · données {asof_txt}</span>
  <span class="demo">DEMO</span>
</div>
<div class="wrap">

  <div class="banner {day_kind}">{day_label}</div>

  {hero_html}

  <div class="eyebrow">// Red folders USD — aujourd'hui</div>
  {news_html}
  {macro_html}
  {week_html}

  <div class="eyebrow">// Biais &amp; niveaux — D · 4H · 1H</div>
  <div class="grid2">{instruments_html}</div>

  <div class="eyebrow">// Validation walk-forward — le rendement HORS échantillon</div>
  <div class="grid2">{wf_html}</div>
  <div class="eyebrow">// Risque — profil sniper (séries perdantes au WR réel)</div>
  <div class="grid2">{risk_html}</div>
  <div class="eyebrow">// Backtest IFVG — config auto-réglée (in-sample, pour contexte)</div>
  <div class="grid2">{backtest_html}</div>

  <div class="eyebrow">// Auto-ajustement — boucle de feedback (socle gelé)</div>
  {adjust_html}
  <div class="eyebrow">// Conclusions du backtest — mises à jour chaque matin</div>
  {insights_html}


  <div class="eyebrow">// Fenêtre de trading</div>
  <section class="card">
    <div class="kzline"><span class="pill {kz_pill}">NY AM</span>
      <span class="num">{kz["start"]} → {kz["end"]} (heure NY)</span></div>
    <p class="reason">{kz_note}</p>
  </section>

  <div class="eyebrow">// Checklist avant chaque trade</div>
  <section class="card"><ul class="check">{checklist_html}</ul></section>

  <footer>
    Rappel : la réaction initiale aux news est souvent piégeuse (judas swing) —
    fausse impulsion qui prend la liquidité avant le vrai mouvement.<br>
    Généré automatiquement par Trading OS · données Yahoo Finance (indicatives, continues)
    &amp; ForexFactory · aucune prédiction, démo uniquement.
  </footer>
</div>

<script>
(function () {{
  // equity-curve hover: nearest point -> dot + tooltip
  document.querySelectorAll(".eq").forEach(function (wrap) {{
    var svg = wrap.querySelector("svg"), tip = wrap.querySelector(".tip"),
        dot = svg.querySelector(".hoverdot"),
        pts = JSON.parse(wrap.dataset.pts || "[]");
    if (!pts.length) return;
    function hide() {{ tip.style.display = "none"; dot.style.display = "none"; }}
    svg.addEventListener("pointerleave", hide);
    svg.addEventListener("pointermove", function (ev) {{
      var r = svg.getBoundingClientRect();
      var vx = (ev.clientX - r.left) / r.width * 640;
      var best = pts[0], bd = 1e9;
      pts.forEach(function (p) {{
        var d = Math.abs(p[0] - vx);
        if (d < bd) {{ bd = d; best = p; }}
      }});
      dot.setAttribute("cx", best[0]); dot.setAttribute("cy", best[1]);
      dot.style.display = "";
      tip.textContent = best[2];
      tip.style.display = "";
      var frac = best[0] / 640;
      tip.style.left = (frac > 0.55 ? 8 : Math.round(frac * r.width) + 12) + "px";
    }});
  }});

  var day = new Date().toISOString().slice(0, 10);
  var stored = {{}};
  try {{ stored = JSON.parse(localStorage.getItem("tos-check") || "{{}}"); }} catch (e) {{}}
  if (stored.day !== day) stored = {{ day: day }};
  document.querySelectorAll("ul.check input").forEach(function (box) {{
    box.checked = !!stored[box.dataset.k];
    box.addEventListener("change", function () {{
      stored[box.dataset.k] = box.checked;
      localStorage.setItem("tos-check", JSON.stringify(stored));
    }});
  }});
}})();
</script>
"""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def main() -> None:
    cfg = load_config()
    args = [a for a in sys.argv[1:] if a != "--light"]
    light = "--light" in sys.argv[1:]   # intraday : réutilise le réglage du matin
    out = args[0] if args else "journal/reports/dashboard.html"
    path = build_dashboard(cfg, out, autotune=not light)
    print(f"Dashboard généré : {path}" + (" (mode intraday, sans autotune)" if light else ""))


if __name__ == "__main__":
    main()
