"""Fil macro du prémarché — proxy gratuit des fils Walter Bloomberg /
Financial Juice (source : Google News RSS, rafraîchi à chaque build).

Le dashboard étant reconstruit au prémarché (pas en continu), on ne vise pas
le temps réel : on vise « qu'est-ce qui a bougé ces dernières 24 h que le
calendrier ForexFactory ne montre pas » (déclarations Fed surprises, tarifs,
géopolitique, tech méga-caps qui pèsent sur NQ).
"""

from __future__ import annotations

import html as _html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone

_QUERY = ('(FOMC OR "federal reserve" OR Powell OR CPI OR PPI OR NFP OR tariff '
          'OR "rate cut" OR "rate hike" OR nasdaq OR "S&P 500" OR geopolitics '
          'OR Iran OR OPEC OR Nvidia OR "treasury yields") when:1d')
_URL = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(_QUERY)
        + "&hl=en-US&gl=US&ceid=US:en")

# pondération : ce qui bouge vraiment ES/NQ en priorité
_WEIGHTS = [
    (re.compile(r"\b(fomc|powell|fed(eral reserve)?|rate (cut|hike))\b", re.I), 3),
    (re.compile(r"\b(cpi|ppi|nfp|payrolls|inflation|jobless)\b", re.I), 3),
    (re.compile(r"\b(tariff|trade war|sanction)\b", re.I), 2),
    (re.compile(r"\b(nasdaq|s&p|nvidia|apple|microsoft|treasury|yields?)\b", re.I), 2),
    (re.compile(r"\b(iran|opec|strike|missile|war)\b", re.I), 1),
]


@dataclass
class Headline:
    title: str
    source: str
    when: datetime
    score: int


_NOISE = re.compile(r"\b(obituary|funeral|recipe|horoscope|lottery|movie|album"
                    r"|high school|football|basketball|soccer)\b", re.I)


def _score(title: str) -> int:
    if _NOISE.search(title):
        return 0
    return sum(w for rx, w in _WEIGHTS if rx.search(title))


def fetch_macro_headlines(limit: int = 8, timeout: int = 15) -> list[Headline]:
    """Top headlines macro des dernières 24 h, triées par pertinence puis
    fraîcheur. Liste vide en cas d'erreur réseau (fail-safe pour le build)."""
    try:
        raw = urllib.request.urlopen(_URL, timeout=timeout).read()
        root = ET.fromstring(raw)
    except Exception:
        return []
    out: list[Headline] = []
    seen: set[str] = set()
    for item in root.findall(".//item"):
        title = _html.unescape(item.findtext("title") or "").strip()
        # Google News suffixe " - Source"
        source = ""
        if " - " in title:
            title, source = title.rsplit(" - ", 1)
        key = re.sub(r"\W+", "", title.lower())[:60]
        if not title or key in seen:
            continue
        seen.add(key)
        try:
            when = datetime.strptime(item.findtext("pubDate") or "",
                                     "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc)
        except ValueError:
            when = datetime.now(timezone.utc)
        s = _score(title)
        if s > 0:
            out.append(Headline(title, source, when, s))
    out.sort(key=lambda h: (-h.score, -h.when.timestamp()))
    return out[:limit]
