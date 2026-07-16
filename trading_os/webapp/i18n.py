"""Bilinguisme FR/EN du dashboard — passe de post-traitement.

Le dashboard est généré en français (langue du projet). Ce module ajoute une
version anglaise SANS toucher aux ~150 sites de rendu de ``build.py`` : il
enveloppe chaque nœud de texte traduisible dans
``<span class="i18n" data-en="English">Français</span>`` et injecte un petit
bouton FR/EN + le JS qui échange le contenu côté client (mémorisé dans
localStorage, auto-détection de la langue du navigateur au premier chargement).

Un seul endroit à maintenir : les tables ``EXACT`` (phrases fixes) et ``RULES``
(fragments avec valeurs dynamiques). Tout nœud non couvert reste en français
(repli gracieux) — jamais de corruption du HTML.
"""

from __future__ import annotations

import html
import re

# ------------------------------------------------------------------ tables

TITLE_FR = "Trading OS — Prémarché"
TITLE_EN = "Trading OS — Premarket"

# Phrases fixes : clé = texte du nœud, espaces internes normalisés (un seul
# espace), sans espaces de bord. Valeur = anglais.
EXACT: dict[str, str] = {
    # -- eyebrows (titres de section) --
    "// Red folders USD — aujourd'hui": "// USD red folders — today",
    "// Prévision news — dernières 24 h": "// News forecast — last 24 h",
    "// Biais & niveaux — D · 4H · 1H": "// Bias & levels — D · 4H · 1H",
    "// Backtest & forward — config gelée style Dodgy · auto-apprentissage":
        "// Backtest & forward — frozen config, Dodgy style · self-learning",
    "// Fenêtre de trading": "// Trading window",
    "// Checklist avant chaque trade": "// Checklist before every trade",
    # -- bannière jour --
    "WEEK-END · marché fermé · réouverture dimanche 18:00 NY":
        "WEEKEND · market closed · reopens Sunday 18:00 NY",
    "Séance du dimanche soir (globex) — patience jusqu'à NY AM":
        "Sunday-evening session (globex) — patience until NY AM",
    "JOUR DE TRADING · fenêtre 9:30–11:30 NY":
        "TRADING DAY · window 9:30–11:30 NY",
    # -- hero « en un coup d'œil » --
    "Marché": "Market",
    "FERMÉ": "CLOSED",
    "week-end / férié": "weekend / holiday",
    "Prochain red folder": "Next red folder",
    "RAS": "ALL CLEAR",
    "journée technique": "technical day",
    "Météo du risque": "Risk weather",
    "RISK-ON": "RISK-ON",
    "RISK-OFF": "RISK-OFF",
    # -- news --
    "· précédent": "· previous",
    "Scénarios": "Scenarios",
    "AU-DESSUS": "ABOVE",
    "EN DESSOUS": "BELOW",
    "EN LIGNE": "IN LINE",
    "✓ Aucun red folder USD aujourd’hui — journée technique pure.":
        "✓ No USD red folder today — pure technical day.",
    "Indices US": "US indices",
    "Classification mécanique par mots-clés — un contexte, pas un signal "
    "d'entrée. Le setup IFVG reste le seul déclencheur.":
        "Mechanical keyword classification — context, not an entry signal. "
        "The IFVG setup stays the only trigger.",
    # -- carte instrument (biais & niveaux) --
    "RÉF. SMT — NON TRADÉ": "SMT REF. — NOT TRADED",
    "Signaux (structure · momentum · FVG · SMT · PDH/PDL)":
        "Signals (structure · momentum · FVG · SMT · PDH/PDL)",
    "FVG non mitigés (du plus proche au plus loin)":
        "Unmitigated FVGs (nearest to farthest)",
    "aucun FVG ouvert proche": "no open FVG nearby",
    "PRIX": "PRICE",
    # -- carte backtest gelée --
    "En attente de données backtest.": "Waiting for backtest data.",
    "Forward — le vrai test (depuis le gel)":
        "Forward — the real test (since freeze)",
    "🔒 Trades depuis le gel": "🔒 Trades since freeze",
    "objectif ≥ 15 pour juger": "target ≥ 15 to judge",
    "R forward": "forward R",
    "hors échantillon pur": "pure out-of-sample",
    "WR forward": "forward WR",
    "vs 40 % attendu": "vs 40% expected",
    "Référence backtest (24 mois, coûts inclus)":
        "Backtest reference (24 months, costs incl.)",
    "Espérance / trade": "Expectancy / trade",
    "R net · 24 mois": "net R · 24 mo",
    "gains/pertes": "wins/losses",
    "Equity (R cumulés)": "Equity (cumulative R)",
    "🧠 Auto-apprentissage : actif, aucun ajustement en cours — la boucle "
    "n'ajuste que sur évidence (≥ 8 trades), le socle gelé reste intouchable.":
        "🧠 Self-learning: active, no adjustment running — the loop only "
        "adjusts on evidence (≥ 8 trades); the frozen base stays untouchable.",
    # -- école des presque --
    "🎓 École des presque (ce que le socle rejette de peu)":
        "🎓 Near-miss school (what the base barely rejects)",
    "critère relâché seul": "criterion relaxed alone",
    "espérance": "expectancy",
    "candidat": "candidate",
    "à surveiller": "to watch",
    # -- fenêtre de trading --
    "Seule fenêtre autorisée par la méthodologie. Pas de trade en dehors, pas "
    "de trade en no-trade-zone news, 1 micro contrat max, démo uniquement.":
        "The only window the methodology allows. No trade outside it, no trade "
        "in a news no-trade-zone, 1 micro contract max, demo only.",
    "Marché fermé aujourd'hui — aucune fenêtre de trading. Profitez-en pour la "
    "revue du journal et la préparation de la semaine.":
        "Market closed today — no trading window. Use it for journal review "
        "and week preparation.",
    # -- checklist --
    "Le biais HTF est-il défini (daily/H4) et mon trade va-t-il dans son sens ?":
        "Is the HTF bias defined (daily/H4) and is my trade aligned with it?",
    "Suis-je dans une killzone autorisée ?": "Am I in an allowed killzone?",
    "Y a-t-il un red folder à moins de 10 min ? Si oui : NO TRADE.":
        "Is there a red folder within 10 min? If so: NO TRADE.",
    "Le FVG a-t-il été invalidé par une clôture franche (pas juste une mèche) ?":
        "Was the FVG invalidated by a clean close (not just a wick)?",
    "Mon stop est-il au-delà de la zone inversée, taille de position calculée "
    "AVANT l'entrée ?":
        "Is my stop beyond the inverted zone, position size computed BEFORE "
        "entry?",
    "Le RR vers la cible (liquidité opposée) est-il d'au moins 2:1 ?":
        "Is the RR to target (opposite liquidity) at least 2:1?",
    "Ai-je déjà pris ma perte max du jour ? Si oui : terminal fermé.":
        "Have I already taken my max daily loss? If so: terminal closed.",
    # -- footer --
    "Rappel : la réaction initiale aux news est souvent piégeuse (judas swing) "
    "— fausse impulsion qui prend la liquidité avant le vrai mouvement.":
        "Reminder: the initial reaction to news is often a trap (judas swing) "
        "— a false push that grabs liquidity before the real move.",
    "Généré automatiquement par Trading OS · données Yahoo Finance "
    "(indicatives, continues) & ForexFactory · aucune prédiction, démo "
    "uniquement.":
        "Auto-generated by Trading OS · Yahoo Finance data (indicative, "
        "continuous) & ForexFactory · no prediction, demo only.",
    # -- bannière jour (repli) --
    "La veille a oscillé entre PDH et PDL sans les déplacer → attendre une "
    "cassure franche ou un failure-to-displace (FTD).":
        "Yesterday ranged between PDH and PDL without displacing them → wait "
        "for a clean break or a failure-to-displace (FTD).",
    "Pas assez d'historique quotidien pour lire un biais.":
        "Not enough daily history to read a bias.",
    # -- signaux multi-TF (structure · momentum · FVG · SMT) --
    "pas assez de swings confirmés": "not enough confirmed swings",
    "HH + HL (structure haussière)": "HH + HL (bullish structure)",
    "LH + LL (structure baissière)": "LH + LL (bearish structure)",
    "structure mixte": "mixed structure",
    "n/d": "n/a",
    "clôture au-dessus du high précédent": "close above the previous high",
    "clôture sous le low précédent": "close below the previous low",
    "pas de déplacement net": "no clear displacement",
    "aucun FVG actif": "no active FVG",
    "pas de comparaison possible": "no comparison possible",
    "pas de divergence ES/NQ nette": "no clear ES/NQ divergence",
    # -- école des presque : libellés de cohortes --
    "V-shape plus mou (12–20 ticks)": "Softer V-shape (12–20 ticks)",
    "RR plus court (1.5–2)": "Shorter RR (1.5–2)",
    "2ᵉ setup du jour": "2nd setup of the day",
    # -- nom de la variante gelée --
    "Sweep session + V-shape (clôture inversion)":
        "Session sweep + V-shape (inversion close)",
    # -- diagnostic (bullet de repli) --
    "Pas d'asymétrie exploitable statistiquement sur 30 j — le modèle "
    "travaille, on n'ajuste rien sans évidence.":
        "No statistically exploitable asymmetry over 30 d — the model is "
        "working, we adjust nothing without evidence.",
}

# Fragments avec valeurs dynamiques. Appliqués (dans l'ordre) au texte
# normalisé quand aucune correspondance EXACT. Les nombres/dates sont capturés
# et réémis tels quels. L'ordre compte : phrases longues d'abord.
_RULES_SRC: list[tuple[str, str]] = [
    # jour férié (bannière)
    (r"JOUR FÉRIÉ · (.+?) · pas de séance complète",
     r"HOLIDAY · \1 · no full session"),
    # date de l'en-tête : "· maj HH:MM NY · données X"
    (r"· maj ", r"· upd "),
    (r"· données ", r"· data "),
    # hero
    (r"· biais jour", r"· day bias"),
    # prévision news
    (r"(\d+) signaux haussiers · (\d+) baissiers",
     r"\1 bullish signals · \2 bearish"),
    (r"Météo du risque :", r"Risk weather:"),
    # variante gelée (ligne ⚙)
    (r"clôture d'inversion", r"inversion close"),
    (r"sweep session", r"session sweep"),
    (r"cible liquidité", r"liquidity target"),
    (r"1 trade/jour", r"1 trade/day"),
    # pill gelée
    (r"🔒 GELÉE", r"🔒 FROZEN"),
    (r"STYLE DODGY", r"DODGY STYLE"),
    # fallback forward
    (r"🔒 Gelée le (\S+) — 0 trade forward pour l'instant : chaque nouveau "
     r"jour de marché est du VRAI hors-échantillon, le compteur démarre ici\.",
     r"🔒 Frozen on \1 — 0 forward trade yet: every new market day is TRUE "
     r"out-of-sample, the counter starts here."),
    # stabilité de l'edge
    (r"EDGE EN RENFORCEMENT", r"EDGE STRENGTHENING"),
    (r"EDGE EN BAISSE", r"EDGE WEAKENING"),
    (r"EDGE DÉGRADÉ RÉCEMMENT", r"EDGE RECENTLY DEGRADED"),
    (r"1ʳᵉ moitié :", r"1st half:"),
    (r"2ᵉ moitié :", r"2nd half:"),
    # risque / séries
    (r"✓ SÉRIE NORMALE", r"✓ NORMAL STREAK"),
    (r"⚠ SÉRIE ÉLEVÉE", r"⚠ HIGH STREAK"),
    (r"⛔ SÉRIE > P99 — MODÈLE À RE-VALIDER",
     r"⛔ STREAK > P99 — MODEL TO RE-VALIDATE"),
    (r"⛔ série > p99", r"⛔ streak > p99"),
    (r"Risque : ", r"Risk: "),
    (r"série en cours", r"current streak"),
    (r"attendue ≈", r"expected ≈"),
    (r" · réduit ", r" · reduced "),
    # auto-apprentissage (ligne dynamique)
    (r"🧠 Auto-apprentissage :", r"🧠 Self-learning:"),
    (r"ajustement\(s\) actif\(s\)", r"active adjustment(s)"),
    (r"dernier :", r"last:"),
    # note école des presque
    (r"Chaque ligne = les trades AJOUTÉS si on relâchait ce seul critère "
     r"\(les autres restant au niveau gelé\)\. « candidat » = ≥ (\d+) trades "
     r"et espérance positive : à valider en forward avant toute promotion — "
     r"le socle reste gelé\.",
     r"Each row = the trades ADDED if this single criterion were relaxed "
     r"(the others staying frozen). “candidate” = ≥ \1 trades and positive "
     r"expectancy: to confirm forward before any promotion — the base stays "
     r"frozen."),
    # note carte gelée
    (r"Une seule config, gelée le (\S+) \(pré-enregistrement anti-overfitting\)"
     r" : le backtest 24 mois est la référence, le compteur forward est le "
     r"juge\. L'auto-apprentissage n'ajuste que des paramètres secondaires "
     r"bornés, jamais le socle\.",
     r"One config, frozen on \1 (anti-overfitting pre-registration): the "
     r"24-month backtest is the reference, the forward counter is the judge. "
     r"Self-learning only tunes bounded secondary parameters, never the base."),
    # fenêtre de trading
    (r"\(heure NY\)", r"(NY time)"),
    # verdicts de biais (majuscule = pills, minuscule = chips FVG)
    (r"\bHAUSSIER\b", r"BULLISH"),
    (r"\bBAISSIER\b", r"BEARISH"),
    (r"\bNEUTRE\b", r"NEUTRAL"),
    (r"\bHAUSSE\b", r"UP"),
    (r"\bBAISSE\b", r"DOWN"),
    (r"\bhaussier\b", r"bullish"),
    (r"\bbaissier\b", r"bearish"),
    (r"\bneutre\b", r"neutral"),
    # jours / mois (en-tête + « à venir cette semaine »)
    (r"\blundi\b", r"Monday"), (r"\bmardi\b", r"Tuesday"),
    (r"\bmercredi\b", r"Wednesday"), (r"\bjeudi\b", r"Thursday"),
    (r"\bvendredi\b", r"Friday"), (r"\bsamedi\b", r"Saturday"),
    (r"\bdimanche\b", r"Sunday"),
    (r"\bjanvier\b", r"January"), (r"\bfévrier\b", r"February"),
    (r"\bmars\b", r"March"), (r"\bavril\b", r"April"),
    (r"\bmai\b", r"May"), (r"\bjuin\b", r"June"),
    (r"\bjuillet\b", r"July"), (r"\baoût\b", r"August"),
    (r"\bseptembre\b", r"September"), (r"\boctobre\b", r"October"),
    (r"\bnovembre\b", r"November"), (r"\bdécembre\b", r"December"),
    (r"\blun\b", r"Mon"), (r"\bmar\b", r"Tue"), (r"\bmer\b", r"Wed"),
    (r"\bjeu\b", r"Thu"), (r"\bven\b", r"Fri"), (r"\bsam\b", r"Sat"),
    (r"\bdim\b", r"Sun"),
    # « à venir cette semaine »
    (r"À venir cette semaine", r"Coming up this week"),
    # -- raisons de biais quotidien (bias.py), prix entre parenthèses --
    (r"La veille a cassé ET clôturé au-dessus du PDH \(([^)]+)\) → "
     r"continuation attendue vers le prochain pool de liquidité haut\.",
     r"Yesterday broke AND closed above the PDH (\1) → continuation expected "
     r"toward the next upper liquidity pool."),
    (r"La veille a cassé ET clôturé sous le PDL \(([^)]+)\) → continuation "
     r"attendue vers le prochain pool de liquidité bas\.",
     r"Yesterday broke AND closed below the PDL (\1) → continuation expected "
     r"toward the next lower liquidity pool."),
    (r"La veille a balayé le PDL \(([^)]+)\) sans clôturer dessous "
     r"\(liquidité prise, niveau respecté\) → cible : le PDH\.",
     r"Yesterday swept the PDL (\1) without closing below it (liquidity "
     r"taken, level held) → target: the PDH."),
    (r"La veille a balayé le PDH \(([^)]+)\) sans clôturer au-dessus "
     r"\(échec au niveau\) → cible : le PDL\.",
     r"Yesterday swept the PDH (\1) without closing above it (level "
     r"rejection) → target: the PDL."),
    # -- signaux FVG / SMT (zone ou instrument entre parenthèses) --
    (r"prix DANS un FVG haussier", r"price INSIDE a bullish FVG"),
    (r"prix DANS un FVG baissier", r"price INSIDE a bearish FVG"),
    (r"FVG haussier en support sous le prix",
     r"bullish FVG as support below price"),
    (r"FVG baissier en résistance au-dessus",
     r"bearish FVG as resistance above"),
    (r"FVG le plus proche à contre-position",
     r"nearest FVG on the wrong side"),
    (r"divergence haussière :", r"bullish divergence:"),
    (r"divergence baissière :", r"bearish divergence:"),
    (r"le plus bas de", r"the low of"),
    (r"le plus haut de", r"the high of"),
    (r"n'est pas confirmé par l'autre", r"isn't confirmed by the other"),
    (r"\bce marché\b", r"this market"),
    # -- diagnostic (bullets dynamiques) --
    (r"L'edge vient surtout de (\S+) \(([^)]+)\) ; (\S+) traîne \(([^)]+)\)\.",
     r"The edge comes mainly from \1 (\2); \3 lags (\4)."),
    (r"(\d+%) des pertes sont des stops touchés sur la barre d'entrée même — "
     r"signature d'un stop trop près de la zone\.",
     r"\1 of losses are stops hit on the entry bar itself — signature of a "
     r"stop too close to the zone."),
    (r"Les setups visant un RR ≥ 2.5 paient mieux \(PF ([^)]+)\) que les RR "
     r"courts \(PF ([^)]+)\)\.",
     r"Setups targeting RR ≥ 2.5 pay better (PF \1) than short RRs (PF \2)."),
    (r"Drawdown de (\S+) R sur 30 j — période de fragilité, la taille doit se "
     r"réduire, pas l'inverse\.",
     r"Drawdown of \1 R over 30 d — fragile period, size must shrink, not "
     r"the opposite."),
]

RULES: list[tuple[re.Pattern, str]] = [(re.compile(p), r) for p, r in _RULES_SRC]

_WS = re.compile(r"\s+")
_HAS_ALPHA = re.compile(r"[A-Za-zÀ-ÿ]")
_SKIP_BLOCK = re.compile(r"<(script|style|title)\b[^>]*>.*?</\1>", re.S | re.I)
_TEXT_NODE = re.compile(r"(>)([^<>]+)(<)")


def translate_text(text: str) -> str:
    """FR → EN pour un nœud de texte. Renvoie ``text`` inchangé si rien ne
    correspond (repli : reste en français)."""
    # html.unescape : les apostrophes/esperluettes rendues par build.py via
    # html.escape (&#x27; &amp;) doivent redevenir ' & pour matcher les tables.
    norm = _WS.sub(" ", html.unescape(text)).strip()
    if norm in EXACT:
        return EXACT[norm]
    en = norm
    for pat, repl in RULES:
        en = pat.sub(repl, en)
    return en if en != norm else text


def bilingualize(page: str) -> str:
    """Enveloppe les nœuds traduisibles + injecte le bouton FR/EN et son JS."""
    # 1) protéger <script>/<style>/<title> du remplacement de nœuds
    stash: list[str] = []

    def _protect(m: re.Match) -> str:
        stash.append(m.group(0))
        return f"\x00{len(stash) - 1}\x00"

    body = _SKIP_BLOCK.sub(_protect, page)

    # 2) envelopper chaque nœud de texte traduit
    def _node(m: re.Match) -> str:
        pre, text, post = m.group(1), m.group(2), m.group(3)
        if not _HAS_ALPHA.search(text):
            return m.group(0)
        en = translate_text(text)
        if en == text:
            return m.group(0)
        esc = html.escape(en, quote=True)
        return f'{pre}<span class="i18n" data-en="{esc}">{text}</span>{post}'

    body = _TEXT_NODE.sub(_node, body)

    # 3) restaurer les blocs protégés
    body = re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], body)

    # 4) injecter le bouton dans la barre du haut + le JS/CSS du toggle
    button = ('<button id="lang" class="langtog" type="button" '
              'aria-label="Language / Langue">EN</button>')
    body = body.replace('<span class="demo">DEMO</span>',
                        f'{button}<span class="demo">DEMO</span>', 1)
    body = body.replace("</style>", _TOGGLE_CSS + "</style>", 1)
    script = _TOGGLE_JS.replace("__TITLE_FR__", html.escape(TITLE_FR)) \
                       .replace("__TITLE_EN__", html.escape(TITLE_EN))
    body = body.replace("</script>", "</script>\n" + script, 1)
    return body


_TOGGLE_CSS = """
.langtog { margin-left:auto; margin-right:8px; font:600 11px/1
  ui-monospace,"SF Mono",Menlo,Consolas,monospace; letter-spacing:.12em;
  color:var(--accent-ink); background:transparent; border:1px solid var(--accent);
  border-radius:3px; padding:3px 9px; cursor:pointer; }
.langtog:hover { background:color-mix(in srgb, var(--accent) 14%, transparent); }
.top .demo { margin-left:0; }
"""

_TOGGLE_JS = """<script>
(function () {
  var TITLES = { fr: "__TITLE_FR__", en: "__TITLE_EN__" };
  var nodes = document.querySelectorAll(".i18n");
  function apply(lang) {
    document.documentElement.lang = lang;
    nodes.forEach(function (el) {
      if (el.dataset.fr === undefined) el.dataset.fr = el.textContent;
      el.textContent = (lang === "en") ? el.dataset.en : el.dataset.fr;
    });
    if (TITLES[lang]) document.title = TITLES[lang];
    var b = document.getElementById("lang");
    if (b) b.textContent = (lang === "en") ? "FR" : "EN";
  }
  var saved = null;
  try { saved = localStorage.getItem("tos-lang"); } catch (e) {}
  var init = saved
    || (((navigator.language || "").slice(0, 2) === "fr") ? "fr" : "en");
  apply(init);
  var btn = document.getElementById("lang");
  if (btn) btn.addEventListener("click", function () {
    var next = (document.documentElement.lang === "en") ? "fr" : "en";
    try { localStorage.setItem("tos-lang", next); } catch (e) {}
    apply(next);
  });
})();
</script>"""
