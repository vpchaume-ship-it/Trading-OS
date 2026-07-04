"""Knowledge base: index the PDFs dropped in knowledge/ and search them.

Purpose: keep the code's ICT definitions (IFVG, killzones, liquidity…) aligned
with YOUR documents. The `concepts` command extracts the passages of your PDFs
mentioning each tracked concept so you can compare them with the implementation
(see the docstring in trading_os/core/fvg.py) and arbitrate any conflict.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def build_index(cfg: dict) -> dict:
    """Extract text per page from every PDF in knowledge/ -> index.json."""
    from pypdf import PdfReader

    kdir = Path(cfg["knowledge"]["directory"])
    kdir.mkdir(exist_ok=True)
    pages: list[dict] = []
    for pdf in sorted(kdir.glob("*.pdf")):
        try:
            reader = PdfReader(str(pdf))
            for i, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append({"file": pdf.name, "page": i, "text": text})
        except Exception as exc:
            pages.append({"file": pdf.name, "page": 0,
                          "text": f"[ERREUR extraction: {exc}]"})
    index = {"n_files": len({p['file'] for p in pages}), "pages": pages}
    Path(cfg["knowledge"]["index_file"]).write_text(
        json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return index


def load_index(cfg: dict) -> dict | None:
    path = Path(cfg["knowledge"]["index_file"])
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def search(cfg: dict, query: str, max_hits: int = 8) -> list[dict]:
    """Simple keyword search, ranked by number of query-term occurrences."""
    index = load_index(cfg)
    if index is None:
        return []
    terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
    hits = []
    for p in index["pages"]:
        low = p["text"].lower()
        score = sum(low.count(t) for t in terms)
        if score > 0:
            hits.append({**p, "score": score})
    hits.sort(key=lambda h: -h["score"])
    return [{**h, "snippet": _snippet(h["text"], terms)} for h in hits[:max_hits]]


def concept_extracts(cfg: dict) -> dict[str, list[dict]]:
    """For each tracked concept, the passages of the PDFs that mention it."""
    index = load_index(cfg)
    out: dict[str, list[dict]] = {}
    if index is None:
        return out
    for concept in cfg["knowledge"]["concepts"]:
        c = concept.lower()
        found = []
        for p in index["pages"]:
            low = p["text"].lower()
            if c in low:
                found.append({"file": p["file"], "page": p["page"],
                              "snippet": _snippet(p["text"], [c])})
        if found:
            out[concept] = found[:5]
    return out


def _snippet(text: str, terms: list[str], width: int = 240) -> str:
    low = text.lower()
    pos = min((low.find(t) for t in terms if low.find(t) >= 0), default=0)
    start = max(0, pos - width // 3)
    return ("…" if start else "") + text[start:start + width].replace("\n", " ") + "…"
