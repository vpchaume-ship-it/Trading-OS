<!-- AUTO-GÉNÉRÉ par wiki/update_hot.py — NE JAMAIS ÉDITER À LA MAIN
     (sauf le bloc "Next Actions", préservé entre régénérations). -->
# État courant — 2026-07-09

## Stratégie auto-réglée
- Auto-réglage du 2026-07-07T13:22:40
- **ES** : Prudence — A/A+ uniquement (défaut) — aucune variante ne passe les garde-fous (≥10 trades, ≥+0.10 R/trade, PF ≥1.20) — collecte en cours
- **NQ** : Sweep session + V-shape (retest + prise partielle) — 30 trades · WR 43% · +0.91 R/trade · PF 2.45

## Wiki (3 experiences · 5 concepts · 2 research · 2 reference)
Entrées récentes du journal :
- [2026-07-09] setup | Création du wiki LLM (hubs, experiences/concepts/research/reference, Failed Ideas, SCHEMA, CLAUDE.md, update_hot.py, hooks, Obsidian) | opérationnel, seedé avec la connaissance du projet
- [2026-07-07] experience | Modèle utilisateur sweep session + IFVG + V-shape codé et backtesté (NQ 120k barres) | WR 32→47 %, +1.58R, PF 3.64 — retenu comme défaut
- [2026-07-07] decision | min_rating 9 → 0 : la qualité du setup vient du contexte (sweep+V-shape), pas de la note de bougie | config.yaml + grille auto-tune refaite
- [2026-07-09] bugfix | Tests des nouveaux filtres (sweep session, V-shape) sur scénarios synthétiques 2 jours | 66/66 passent ; CONCORDANCE.md mis à jour ; Next Actions posées
- [2026-07-13] decision | Ajout du « Professional Trader Mindset » dans CLAUDE.md (règles de raisonnement trader pro, défauts adaptés : MNQ, 1m/HTF, NY AM, 1 % risque) | actif à chaque session
- [2026-07-13] ingest | Vidéo TikTok « second brain Claude+Obsidian » (graphe dense auto-alimenté) analysée image par image | fiche de route PC créée (journal auto-généré = multiplicateur de nœuds à coût token nul)

## Next Actions
<!-- next-actions:start -->
- Laisser l'échantillon grossir : 30 trades NQ sur le modèle sweep+V-shape, re-juger à ~60.
- ES ne passe toujours pas les garde-fous — vérifier si le V-shape aide ES quand plus de données profondes seront accumulées.
- Calibrer `vshape_min_move_ticks`/`vshape_max_bars` (20/8 posés a priori, jamais grid-searchés) — attention overfit.
- Premier lint du wiki quand ~10 pages de plus existeront.
<!-- next-actions:end -->
