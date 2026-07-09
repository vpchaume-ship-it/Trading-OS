---
type: hub
updated: 2026-07-13
statut: en attente du signal « je suis sur mon PC »
---
# Fiche de route — prise en main de l'Obsidian (jour PC)

Objectif : reproduire le « second brain » de la vidéo (graphe dense de
centaines de nœuds, recherche et stratégies auto-construites) à partir du wiki
existant. **Déclencheur : l'utilisateur écrit « je suis sur mon PC ».**
Exécuter les phases dans l'ordre ; il voit le graphe se densifier en direct.

## Phase 0 — L'utilisateur (10 min, une seule fois)
1. Installer **Obsidian** (obsidian.md) et **GitHub Desktop**.
2. GitHub Desktop → Clone repository → `vpchaume-ship-it/Trading-OS` (branche main).
3. Obsidian → **Open folder as vault** → la **racine** du clone.
4. `Ctrl+G` : le graphe s'affiche, couleurs par dossier déjà configurées.
5. Ensuite : un clic « Pull » dans GitHub Desktop = vault à jour. C'est tout.

## Phase 1 — Le journal auto-généré (moi ; le multiplicateur de nœuds)
Écrire `wiki/generate_journal.py` (stdlib + pandas) :
- Rejoue le backtest auto-réglé sur les données accumulées et crée **une page
  par jour de trading** dans `wiki/journal/` : trades du jour (heure, sens,
  R, grade), contexte (killzone, news), et wikilinks vers les
  [[concepts/ifvg|concepts]] et l'[[experiences/2026-07-sweep-session-vshape|expérience active]].
- Régénéré par la routine quotidienne → **le graphe grossit tout seul chaque
  matin, coût en tokens : zéro** (c'est un script, pas moi qui rédige).
- Ajouter un groupe de couleur `wiki/journal` dans `.obsidian/graph.json`
  (Obsidian FERMÉ pendant l'édition).

## Phase 2 — Densifier le savoir (moi)
- Compléter `concepts/` : order block, BOS/CHoCH, judas sweep, SMT,
  premium/discount, EQH/EQL, displacement, killzones secondaires… une page
  courte chacun, tissée de liens (≈ +12 nœuds fortement connectés).
- Une page `research/` par source déjà étudiée non encore fichée.
- Lint (SCHEMA §3) après coup : zéro orpheline.

## Phase 3 — Confort Obsidian (l'utilisateur, guidé par moi, 5 min)
- Plugin **Dataview** (facultatif) : tableaux dynamiques sur le frontmatter
  (ex. toutes les expériences `verdict: retenue`).
- Épingler `wiki/hot.md` en onglet de démarrage : l'état courant en un écran.

## Phase 4 — Vérification en direct (ensemble)
- `Ctrl+G` : constater le graphe dense ; comparer avec la vue synapses 🧠.
- Tester le cycle complet : je modifie une page → push → il Pull → Obsidian
  se rafraîchit sous ses yeux.

## Garde-fous
- Pas de pages de remplissage pour « faire joli » : chaque nœud doit porter
  une information réelle (trade, concept, source, décision).
- Les chiffres restent sourcés (données, période, coûts) — mindset pro
  (CLAUDE.md) et règle d'immutabilité (SCHEMA).
