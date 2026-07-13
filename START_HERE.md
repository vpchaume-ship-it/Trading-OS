# 🚀 START HERE — Trading OS

Note d'accueil pour démarrer vite, surtout une **session Cowork locale** sur ton PC.

## Toi (humain) — 30 secondes

1. **GitHub Desktop → « Pull origin »** (récupère le dernier état : dashboard, wiki, code).
2. Ouvre ce dossier (`Trading-OS`, la racine) dans **Cowork / Claude local**.
3. Premier message à taper :
   > « Lis le wiki (index + hot + Failed Ideas) et donne-moi l'état du projet, puis dis-moi quoi faire aujourd'hui. »

C'est tout. Claude reprend tout le contexte tout seul (il n'y a rien à réexpliquer).

## Ce qui tourne déjà, sans toi

- **Dashboard 📱** (config gelée style Dodgy, forward, école des presque) : mis à
  jour chaque matin + toutes les 30 min pendant la killzone NY, dans le cloud.
  Lien de l'app : voir `wiki/hot.md`.
- **Cerveau 🧠** (graphe du wiki) : Obsidian en local (`Ctrl+G`), ou la vue
  synapses partageable.
- **Sync git** : automatique via les hooks (`git pull` au démarrage, commit/push
  à l'arrêt). Local ↔ cloud restent alignés.

## La règle à ne pas oublier

La stratégie est **GELÉE** depuis le 2026-07-11. On ne touche pas au socle avant
**≥ 15 trades forward** (le dashboard les compte, section « 🔒 depuis le gel »).
On élargit la cadence par preuves (l'« école des presque »), pas à la main.

## Où est quoi

| Je veux… | Fichier / endroit |
|---|---|
| l'état du projet en un écran | `wiki/hot.md` |
| la carte de tout | `wiki/index.md` |
| pourquoi telle décision | `wiki/log.md`, `wiki/lessons.md` |
| les impasses à éviter | `wiki/Failed Ideas/ledger.md` |
| les paramètres de la stratégie | `config.yaml` (section `ifvg`) |
| le moteur de backtest | `trading_os/backtest/engine.py` |
| lancer les tests | `PYTHONPATH=. python -m pytest tests/ -q` |
| régénérer le dashboard | `python -m trading_os.webapp.build sortie.html` |
