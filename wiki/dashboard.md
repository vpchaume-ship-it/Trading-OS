---
type: hub
updated: 2026-07-13
---
# 🧭 Dashboard du cerveau (Dataview)

> Requiert le plugin **Dataview** (Réglages → Extensions tierces → installer
> « Dataview »). Sans lui, les blocs ci-dessous s'affichent en code — c'est
> normal. Voir [[hot]] pour l'état auto-généré du système.

## Expériences par verdict
```dataview
TABLE verdict, updated
FROM "wiki/experiences"
SORT updated DESC
```

## Concepts (vocabulaire)
```dataview
LIST
FROM "wiki/concepts"
SORT file.name ASC
```

## Psychologie
```dataview
LIST
FROM "wiki/psychology"
```

## Journal — 10 derniers jours tradés
```dataview
TABLE resultat_r AS "R du jour"
FROM "wiki/journal"
SORT file.name DESC
LIMIT 10
```

## Recherche ingérée
```dataview
LIST
FROM "wiki/research"
```
