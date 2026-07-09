---
type: hub
updated: 2026-07-09
---
# SCHEMA — le règlement du wiki

Le wiki est la mémoire persistante du projet, maintenue par le LLM entre les
sessions. Trois couches : sources brutes (immutables : `knowledge/`, `data/`,
le code), le wiki (ce dossier, écrit par le LLM), et ce schéma (les règles).

## 1. Templates de pages

Chaque page commence par un frontmatter YAML avec au minimum `type:` et
`updated:` (date du dernier edit substantiel).

### Entrée d'index (dans `index.md`)
`- [[chemin/page|Titre]] — résumé en une ligne.` Classée dans sa section.

### Expérience (`experiences/YYYY-MM-slug.md`) — l'unité de travail
```
---
type: experience
updated: YYYY-MM-DD
verdict: retenue | rejetée | à confirmer
---
# Titre
**Hypothèse** : ce qu'on teste et pourquoi.
**Implémentation** : fichier(s) + clés de config touchées.
**Résultat** : chiffres (n, WR, espérance R, PF), période et données utilisées.
**Verdict** : décision + réserves (taille d'échantillon, overfitting).
**Voir aussi** : liens.
```

### Concept (`concepts/slug.md`)
```
---
type: concept
updated: YYYY-MM-DD
---
# Terme
Définition opérationnelle (celle du CODE, pas celle des forums), où il vit dans
le code/config, liens vers expériences et sources.
```

### Recherche (`research/slug.md`)
```
---
type: research
updated: YYYY-MM-DD
source: origine de la source externe
---
# Titre
Synthèse de la source + ce que le projet en a retenu/rejeté, avec liens.
```

### Référence (`reference/slug.md`)
Routeur pur : liens vers la page/le fichier qui fait autorité. **Ne jamais
restituer les détails** — c'est ce qui évite les doublons qui divergent.

### Failed Idea (ligne dans `Failed Ideas/ledger.md`)
`| Date | Idée | Raison de l'abandon | Statut |` — statut : abandonnée /
remplacée / réhabilitée (avec lien).

## 2. Workflows

**Début de session (toujours)** : lire `index.md` puis `Failed Ideas/ledger.md`.
`hot.md` donne l'état courant en un écran.

**Après une expérience de backtest** :
1. Créer/mettre à jour sa page `experiences/` depuis le template.
2. Ajouter/mettre à jour sa ligne dans `index.md`.
3. Appendre une ligne au `log.md` (`experience | ... | verdict`).
4. Si abandonnée → ligne dans `Failed Ideas/ledger.md`.
5. Si une leçon se généralise → toucher `lessons.md`.
6. Si un terme nouveau est apparu → page `concepts/`.

**Ingestion d'une source externe** (PDF, vidéo, article) :
1. La source brute reste où elle est (immutable).
2. Page `research/` : synthèse + ce qu'on en retient pour le projet.
3. Mettre à jour les concepts touchés, l'index, le log.

**Décision de config** (changement de défaut dans `config.yaml`) :
log (`decision | ...`) + lien depuis la page d'expérience qui la justifie.

**Fin de session** : pages touchées à jour, ligne(s) de log appendues,
`python wiki/update_hot.py` (le hook Stop le fait aussi automatiquement).

## 3. Lint (auto-contrôle périodique)

À lancer quand le wiki a grossi ou sur demande (`lint` dans le log) :
- **Orphelines** : pages liées depuis nulle part (l'index ne compte pas comme
  seul lien entrant idéal, mais est le minimum obligatoire).
- **Périmées** : `verdict`/chiffres contredits par une expérience plus récente
  → mettre à jour ou marquer « supersédé par [[...]] ».
- **Contradictions** entre pages (les repérer, trancher, logger la décision).
- **Concepts manquants** : terme utilisé dans ≥2 pages sans page propre.
- **Index désynchronisé** : page existante absente de l'index ou lien mort.

## Règle d'immutabilité

Le wiki **LIE** les sources brutes (PDFs, CSVs, code, `CONCORDANCE.md`) et ne
recopie jamais leur contenu comme vérité. Si un chiffre vit dans le code ou la
config, la page wiki pointe dessus au lieu de le figer.
