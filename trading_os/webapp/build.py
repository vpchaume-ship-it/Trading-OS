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
from trading_os.journal.store import Journal
from trading_os.news.calendar import NewsEvent, append_history, fetch_red_folders
from trading_os.news.scenarios import build_card
from trading_os.premarket.bias import daily_bias
from trading_os.premarket.mtf_bias import day_status, instrument_matrix
from trading_os.journal.store import Journal
from trading_os.webapp.insights import (conclusions, run_variants, save_state,
                                        select_strategy)
from trading_os.webapp.propsim import simulate
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
    <circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="4" class="enddot"/>
    <text x="{xs[-1] - 6:.1f}" y="{ys[-1] - 9:.1f}" class="endlab">{cum[-1]:+.1f} {unit}</text>
    <text x="{L}" y="{H - 8}" class="ax" text-anchor="start">{first:%d/%m}</text>
    <text x="{W - R}" y="{H - 8}" class="ax" text-anchor="end">{last:%d/%m}</text>
    <circle r="4.5" class="hoverdot" style="display:none"/>
  </svg>
  <div class="tip" style="display:none"></div>
</div>"""


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
        meta = (f'{d["tf"]} · {d["n_bars"]:,} barres · '
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

        auto_line = (f'<p class="autotune">⚙ Réglage auto : '
                     f'<strong>{html.escape(sel["variant"])}</strong> — '
                     f'{html.escape(sel["reason"])}</p>')
        blocks.append(f"""
<section class="card">
  <header class="card-head"><h2>{name}</h2><span class="price">{meta}</span></header>
  {auto_line}
  {kpis}
  <h3>Equity (R cumulés, coûts inclus)</h3>
  {equity_svg(d["trades"], name)}
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


def journal_section(cfg: dict) -> str:
    df = Journal(cfg["journal"]["directory"]).load()
    if df.empty:
        return ('<section class="card"><p class="empty">Journal vide pour l\'instant. '
                'La synchronisation Tradovate demo est automatique chaque matin dès que '
                'vos identifiants demo (TRADOVATE_USERNAME, TRADOVATE_PASSWORD, '
                'TRADOVATE_CID, TRADOVATE_SECRET) sont configurés dans '
                'l\'environnement cloud — vos trades, win rate et courbe de PnL '
                'apparaîtront ici tout seuls.</p></section>')
    df = df.sort_values("exit_time").reset_index(drop=True)
    pnl = df["pnl_usd"]
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    pf = wins.sum() / -losses.sum() if losses.sum() < 0 else float("inf")

    def signed(v, fmt):
        cls = "pos" if v > 0 else "neg"
        return f'<span class="kval {cls}">{v:{fmt}}</span>'

    kpis = f"""
  <div class="kpis">
    <div class="kpi"><span class="klab">Win rate</span><span class="kval">{len(wins) / len(df):.0%}</span><span class="ksub">{len(df)} trades</span></div>
    <div class="kpi"><span class="klab">PnL total</span>{signed(pnl.sum(), "+,.0f")}<span class="ksub">USD (demo)</span></div>
    <div class="kpi"><span class="klab">Profit factor</span><span class="kval">{pf:.2f}</span><span class="ksub">gains/pertes $</span></div>
    <div class="kpi"><span class="klab">Trade moyen</span>{signed(pnl.mean(), "+,.0f")}<span class="ksub">meilleur {pnl.max():+,.0f} / pire {pnl.min():+,.0f}</span></div>
  </div>""".replace(",", " ")

    by_kz = df.groupby("killzone")["pnl_usd"]
    kz_rows = "".join(
        f'<tr><td>{kz}</td><td class="num">{len(g)}</td>'
        f'<td class="num">{(g > 0).mean():.0%}</td>'
        f'<td class="num">{g.sum():+,.0f} $</td></tr>'.replace(",", " ")
        for kz, g in by_kz)
    last_rows = "".join(
        f'<tr><td class="num">{pd.Timestamp(t["exit_time"]):%d/%m %H:%M}</td>'
        f'<td>{html.escape(str(t["symbol"]))}</td><td>{t["direction"]}</td>'
        f'<td class="num" style="color:var(--{"bull" if t["pnl_usd"] > 0 else "bear"}-ink)">'
        f'{t["pnl_usd"]:+,.0f} $</td></tr>'.replace(",", " ")
        for _, t in df.tail(8).iloc[::-1].iterrows())

    return f"""
<section class="card">
  {kpis}
  <h3>PnL cumulé (USD, demo)</h3>
  {equity_svg(df, "journal", value_col="pnl_usd", unit="$")}
  <h3>Par killzone</h3>
  <div class="scroll"><table class="fvg"><thead><tr><th></th><th>trades</th><th>WR</th>
  <th>PnL</th></tr></thead><tbody>{kz_rows}</tbody></table></div>
  <h3>Derniers trades</h3>
  <div class="scroll"><table class="fvg"><thead><tr><th>sortie</th><th>symbole</th>
  <th>sens</th><th>PnL</th></tr></thead><tbody>{last_rows}</tbody></table></div>
  <p class="empty">Synchronisé automatiquement depuis Tradovate DEMO chaque matin
  (fills reconstruits en round trips FIFO).</p>
</section>"""


def propfirm_section(cfg: dict, bt: dict) -> str:
    rules = cfg.get("propfirm", {})
    blocks = []
    for name, d in bt.items():
        if not d or d["trades"] is None or d["trades"].empty:
            continue
        sim = simulate(d["trades"], cfg["instruments"][name], rules)
        if sim is None:
            continue
        cls, glyph, lab = {"reussie": ("bull", "✓", "ÉVAL RÉUSSIE"),
                           "echouee": ("bear", "✗", "ÉVAL ÉCHOUÉE"),
                           "en_cours": ("warn", "…", "EN COURS")}[sim.status]
        blocks.append(f"""
<section class="card">
  <header class="card-head"><h2>{name}</h2>
    <span class="price">{sim.days} jour(s) · ~{sim.avg_micros:.0f} micros/trade</span>
    <span class="pill {cls}">{glyph} {lab}</span></header>
  <p class="reason">{html.escape(sim.detail)}.</p>
  <div class="kpis">
    <div class="kpi"><span class="klab">PnL simulé</span><span class="kval {'pos' if sim.final_pnl > 0 else 'neg'}">{sim.final_pnl:+,.0f}</span><span class="ksub">USD</span></div>
    <div class="kpi"><span class="klab">Meilleur jour</span><span class="kval">{sim.best_day:+,.0f}</span><span class="ksub">consistance {'OK' if sim.consistency_ok else 'NON'}</span></div>
    <div class="kpi"><span class="klab">Pire jour</span><span class="kval">{sim.worst_day:+,.0f}</span><span class="ksub">USD</span></div>
    <div class="kpi"><span class="klab">Trades</span><span class="kval">{sim.trades}</span><span class="ksub">{d["tf"]}</span></div>
  </div>
</section>""".replace(",", " "))
    if not blocks:
        return ('<section class="card"><p class="empty">Pas encore assez de trades '
                'backtestés pour simuler l\'éval.</p></section>')
    note = (f'<p class="empty">Règles simulées « {rules.get("name", "Lucid 50K Flex")} » : '
            f'objectif {rules.get("profit_target", 3000):,.0f} $, Max Loss Limit '
            f'{rules.get("max_loss_limit", 2000):,.0f} $ en trailing EOD, minimum '
            f'{rules.get("min_days", 2)} jours, consistance {rules.get("consistency_pct", 50)} %, '
            f'sizing ~{rules.get("risk_per_trade_usd", 200):,.0f} $ de risque/trade en micros. '
            'Simulation indicative sur le backtest auto-réglé — vérifiez toujours les règles '
            'officielles Lucid avant une éval réelle.</p>').replace(",", " ")
    return "".join(blocks) + note


def build_dashboard(cfg: dict, out_path: str | Path) -> Path:
    now = datetime.now(NY)
    day_kind, day_label = day_status(now)

    frames = {name: fetch_frames(name) for name in cfg["premarket"]["instruments"]}
    cards, asof = [], None
    for name in cfg["premarket"]["instruments"]:
        d = instrument_data(name, cfg, frames)
        if d:
            cards.append(instrument_card(d))
            asof = d["asof"]
    instruments_html = "".join(cards) or \
        '<section class="card"><p class="empty">Données de marché indisponibles.</p></section>'
    # auto-tune: run the variant grid, pick per-instrument settings, persist them
    variant_rows: list[dict] = []
    for name in cfg["premarket"]["instruments"]:
        try:
            variant_rows += run_variants(cfg, name)
        except Exception:
            pass
    state = {name: select_strategy(variant_rows, name)
             for name in cfg["premarket"]["instruments"]}
    save_state(state)
    # run the auto-tuned backtest ONCE; reused by backtest + prop-firm sections
    bt: dict[str, dict | None] = {}
    for name in cfg["premarket"]["instruments"]:
        try:
            bt[name] = dashboard_backtest(cfg, name, patch=state[name]["patch"])
        except Exception:
            bt[name] = None
    backtest_html = backtest_section(cfg, state, bt)
    insights_html = insights_section(variant_rows, state)
    journal_html = journal_section(cfg)
    propfirm_html = propfirm_section(cfg, bt)

    try:
        events = fetch_red_folders(cfg)
        append_history(events, cfg["backtest"]["news_history_csv"])
    except Exception:
        events = []
    today = [e for e in events if e.time_ny.date() == now.date()]
    week = [e for e in events if e.time_ny.date() > now.date()]
    news_html = "".join(news_card(e, cfg, now) for e in today) or \
        '<p class="allclear">✓ Aucun red folder USD aujourd’hui — journée technique pure.</p>'
    week_html = ""
    if week:
        items = "".join(f'<li><span class="num">{FR_DAYS[e.time_ny.weekday()][:3]} '
                        f'{e.time_ny:%H:%M}</span> {html.escape(e.title)}</li>'
                        for e in week[:8])
        week_html = f'<h3>À venir cette semaine</h3><ul class="week">{items}</ul>'

    stats = Journal(cfg["journal"]["directory"]).killzone_stats()
    if stats.empty:
        kz_stats_html = '<p class="empty">Journal vide — vos stats par killzone apparaîtront ici.</p>'
    else:
        rows = "".join(f'<tr><td>{kz}</td><td class="num">{int(r["trades"])}</td>'
                       f'<td class="num">{r["win_rate"]:.0%}</td>'
                       f'<td class="num">{r["avg_r"]:+.2f} R</td></tr>'
                       for kz, r in stats.iterrows())
        kz_stats_html = ('<div class="scroll"><table class="fvg"><thead><tr><th>killzone</th>'
                         '<th>trades</th><th>WR</th><th>R moyen</th></tr></thead>'
                         f'<tbody>{rows}</tbody></table></div>')

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
  --bg:#101418; --surface:#1a2026; --raised:#232b33; --line:#2c363f;
  --ink:#e8edf2; --ink2:#98a6b3; --ink3:#5f6d7a;
  --bull:#1e9066; --bear:#da4560; --warn:#b37f26; --accent:#1e93a9;
  --bull-ink:#5ecfa2; --bear-ink:#f2879a; --warn-ink:#dfb267; --accent-ink:#5cc6da;
}}
@media (prefers-color-scheme: light) {{ :root {{
  --bg:#f5f7f9; --surface:#ffffff; --raised:#eef2f5; --line:#dce3e9;
  --ink:#16202a; --ink2:#5a6875; --ink3:#8a97a3;
  --bull:#1f9d6b; --bear:#c93a52; --warn:#a8761f; --accent:#0e93ac;
  --bull-ink:#177550; --bear-ink:#a92f44; --warn-ink:#865e18; --accent-ink:#0b7285;
}} }}
:root[data-theme="dark"] {{
  --bg:#101418; --surface:#1a2026; --raised:#232b33; --line:#2c363f;
  --ink:#e8edf2; --ink2:#98a6b3; --ink3:#5f6d7a;
  --bull:#1e9066; --bear:#da4560; --warn:#b37f26; --accent:#1e93a9;
  --bull-ink:#5ecfa2; --bear-ink:#f2879a; --warn-ink:#dfb267; --accent-ink:#5cc6da;
}}
:root[data-theme="light"] {{
  --bg:#f5f7f9; --surface:#ffffff; --raised:#eef2f5; --line:#dce3e9;
  --ink:#16202a; --ink2:#5a6875; --ink3:#8a97a3;
  --bull:#1f9d6b; --bear:#c93a52; --warn:#a8761f; --accent:#0e93ac;
  --bull-ink:#177550; --bear-ink:#a92f44; --warn-ink:#865e18; --accent-ink:#0b7285;
}}
* {{ box-sizing:border-box }}
body {{ background:var(--bg); color:var(--ink); margin:0;
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }}
.mono, h1,h2,h3,.num,.pill,.chip,.tag,.eyebrow,.ntime,.ntz,.llab,.lval,.tf
  {{ font-family:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,monospace; }}
.num {{ font-variant-numeric:tabular-nums }}
.wrap {{ max-width:680px; margin:0 auto; padding:0 14px 48px }}
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
/* -- sections -- */
.eyebrow {{ font-size:11px; letter-spacing:.18em; color:var(--ink3);
  text-transform:uppercase; margin:26px 2px 10px; }}
.card {{ background:var(--surface); border:1px solid var(--line); border-radius:10px;
  padding:14px 16px; margin-bottom:14px; }}
.card-head {{ display:flex; align-items:baseline; gap:12px; }}
.card-head h2 {{ font-size:19px; margin:0; letter-spacing:.06em }}
.price {{ color:var(--ink2); font-size:15px }}
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

  <div class="eyebrow">// Red folders USD — aujourd'hui</div>
  {news_html}
  {week_html}

  <div class="eyebrow">// Biais &amp; niveaux — D · 4H · 1H</div>
  {instruments_html}

  <div class="eyebrow">// Backtest IFVG — stats évolutives (setups A/A+ uniquement)</div>
  {backtest_html}

  <div class="eyebrow">// Conclusions du backtest — mises à jour chaque matin</div>
  {insights_html}

  <div class="eyebrow">// Éval prop firm — simulation Lucid 50K Flex</div>
  {propfirm_html}

  <div class="eyebrow">// Journal Tradovate DEMO — win rate &amp; PnL</div>
  {journal_html}

  <div class="eyebrow">// Fenêtre de trading</div>
  <section class="card">
    <div class="kzline"><span class="pill {kz_pill}">NY AM</span>
      <span class="num">{kz["start"]} → {kz["end"]} (heure NY)</span></div>
    <p class="reason">{kz_note}</p>
    <h3>Mes stats par killzone (forward test)</h3>
    {kz_stats_html}
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
    out = sys.argv[1] if len(sys.argv) > 1 else "journal/reports/dashboard.html"
    path = build_dashboard(cfg, out)
    print(f"Dashboard généré : {path}")


if __name__ == "__main__":
    main()
