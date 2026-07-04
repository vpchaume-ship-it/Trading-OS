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
from trading_os.data.yahoo import fetch_daily, fetch_h1
from trading_os.journal.store import Journal
from trading_os.news.calendar import NewsEvent, append_history, fetch_red_folders
from trading_os.news.scenarios import build_card
from trading_os.premarket.bias import daily_bias

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

def instrument_data(name: str, cfg: dict) -> dict | None:
    spec = cfg["instruments"][name]
    tick = spec["tick_size"]
    now = datetime.now(NY)
    try:
        daily = fetch_daily(name, "6mo")
        h1 = fetch_h1(name, "60d")
    except Exception:
        return None
    # drop today's partial session so "previous day" is a completed one
    completed = daily[[d.date() < now.date() for d in daily.index]]
    if len(completed) < 3:
        return None
    last_price = float(h1["close"].iloc[-1]) if len(h1) else float(daily["close"].iloc[-1])
    bias, reason = daily_bias(completed)
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
            "levels": levels, "fvgs": fvgs[:6],
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
    cls, glyph, label = BIAS_META[d["bias"]]
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


def build_dashboard(cfg: dict, out_path: str | Path) -> Path:
    now = datetime.now(NY)

    cards, asof = [], None
    for name in cfg["premarket"]["instruments"]:
        d = instrument_data(name, cfg)
        if d:
            cards.append(instrument_card(d))
            asof = d["asof"]
    instruments_html = "".join(cards) or \
        '<section class="card"><p class="empty">Données de marché indisponibles.</p></section>'

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
        journal_html = '<p class="empty">Journal vide — vos stats par killzone apparaîtront ici.</p>'
    else:
        rows = "".join(f'<tr><td>{kz}</td><td class="num">{int(r["trades"])}</td>'
                       f'<td class="num">{r["win_rate"]:.0%}</td>'
                       f'<td class="num">{r["avg_r"]:+.2f} R</td></tr>'
                       for kz, r in stats.iterrows())
        journal_html = ('<div class="scroll"><table class="fvg"><thead><tr><th>killzone</th>'
                        '<th>trades</th><th>WR</th><th>R moyen</th></tr></thead>'
                        f'<tbody>{rows}</tbody></table></div>')

    checklist_html = "".join(
        f'<li><label><input type="checkbox" data-k="c{i}"><span>{html.escape(item)}</span></label></li>'
        for i, item in enumerate(cfg["premarket"]["checklist"]))

    kz = cfg["killzones"]["ny_am"]
    asof_txt = f"{asof:%H:%M}" if asof is not None else "--:--"

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

  <div class="eyebrow">// Biais &amp; niveaux</div>
  {instruments_html}

  <div class="eyebrow">// Red folders USD — aujourd'hui</div>
  {news_html}
  {week_html}

  <div class="eyebrow">// Fenêtre de trading</div>
  <section class="card">
    <div class="kzline"><span class="pill bull">NY AM</span>
      <span class="num">{kz["start"]} → {kz["end"]} (heure NY)</span></div>
    <p class="reason">Seule fenêtre autorisée par la méthodologie. Pas de trade en dehors,
    pas de trade en no-trade-zone news, 1 micro contrat max, démo uniquement.</p>
    <h3>Mes stats par killzone (forward test)</h3>
    {journal_html}
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
