---
type: hub
updated: 2026-07-09
---
# Index du wiki

> **PREMIER fichier à lire à chaque session.** Une ligne par page. Après l'index,
> lire `Failed Ideas/ledger.md` avant tout travail nouveau. Maintenu par le LLM.

## Hubs
- [[SCHEMA]] — le règlement : templates de pages, workflows, lint.
- [[log]] — journal chronologique append-only de tout ce qui se passe.
- [[hot]] — état courant AUTO-GÉNÉRÉ (script `update_hot.py`). Ne jamais éditer à la main.
- [[lessons]] — synthèse transversale des leçons apprises.
- [[fiche-route-pc|Fiche de route PC]] — plan d'installation/densification Obsidian ; déclencheur « je suis sur mon PC ».
- [[Failed Ideas/ledger|Failed Ideas]] — tableau des idées abandonnées + raison. **À lire avant tout travail.**

## Expériences (backtests / variantes de stratégie)
- [[experiences/2026-07-preenregistrement-dodgy|Pré-enregistrement Dodgy]] — **CONFIG GELÉE** : clôture inversion + 1 trade/jour ; 25 tr · 40 % WR · +1.38 R · PF 3.21 (24 mois).
- [[experiences/2026-07-sweep-session-vshape|Sweep session + V-shape]] — le modèle utilisateur ; WR 32 % → 47 % sur NQ. **Config retenue.**
- [[experiences/2026-07-entree-inversion-vs-retest|Entrée inversion vs retest]] — l'entrée agressive de Dodgy backteste moins bien que le retest.
- [[experiences/2026-06-scale-out|Prise partielle (scale-out)]] — moitié à +1R → BE ; remonte le WR en restant rentable.

## Concepts
- [[concepts/ifvg|IFVG]] — Inversion Fair Value Gap, le cœur de la stratégie.
- [[concepts/sweep-de-liquidite|Sweep de liquidité]] — swing vs niveau de session (PDH/PDL/overnight).
- [[concepts/v-shape|V-shape]] — renversement franc post-sweep ; le filtre le plus payant à ce jour.
- [[concepts/killzone|Killzone]] — fenêtre 9:30–11:30 NY, seule autorisée.
- [[concepts/walk-forward|Walk-forward]] — validation hors échantillon glissante ; LA stat de référence du dashboard.
- [[concepts/ecole-des-presque|École des presque]] — mesure ce que le socle rejette de peu ; unité de promotion sur évidence, socle jamais touché.
- [[concepts/boucle-auto-ajustement|Boucle d'auto-ajustement]] — feedback quotidien sur les paramètres secondaires, socle gelé, garde-fous durs.
- [[concepts/rating-bougie|Rating de bougie /10]] — note d'inversion (A+..F) ; remplacé par les filtres de contexte.

## Journal (auto-généré — corpus « discrétion »)
- `journal/` — une page par jour tradé (config gelée), annotations « Lecture » en session.

## Recherche (sources externes ingérées)
- [[research/methode-dodgy|Méthode Dodgy (DodgysDD)]] — étude publique de son modèle NQ.
- [[research/sources-news-huss|Sources de news (@huss.trades)]] — 4 sources vidéo → fil macro RSS + météo du risque VIX/or/DXY.
- [[research/pdfs-ict|PDFs ICT du projet]] — Daily Bias, Candle Closure Ratings, IFVG Rating System (voir `knowledge/CONCORDANCE.md`).

## Référence (routeurs — liens seulement, jamais de contenu)
- [[reference/config-strategie|Config stratégie]] — où vit la vérité sur les paramètres.
- [[reference/donnees|Données]] — sources de données et leurs limites.
