---
type: hub
updated: 2026-07-09
---
# Failed Ideas — registre des impasses

> **À LIRE AVANT DE COMMENCER TOUT TRAVAIL NOUVEAU.** Une ligne par idée essayée
> et abandonnée, avec la raison. Ce fichier empêche de refaire les mêmes
> impasses. On n'en retire jamais une ligne ; si une idée est réhabilitée par de
> nouvelles données, on passe son statut à `réhabilitée` avec un lien.

| Date | Idée | Raison de l'abandon | Statut |
|---|---|---|---|
| 2026-07 | Journal de trading connecté à l'API Tradovate | L'accès API est payant (CID+Secret) ; décision utilisateur « tant pis » | abandonnée |
| 2026-07 | Filtre de biais « dérive du close sur 90 barres » | Tue la stratégie NQ (elle fade la dérive) ; proxy trop grossier | abandonnée (option off par défaut dans le code) |
| 2026-07 | Cibles proches pour monter le win rate | WR monte mais espérance négative après coûts — non viable | abandonnée |
| 2026-07 | Filtre A/A+ par rating de bougie (min_rating 9) comme critère principal | Trop peu de trades (6 sur 120k barres) et moins discriminant que sweep-session + V-shape | remplacée par le modèle contexte |
| 2026-07 | Entrée sur clôture d'inversion comme défaut (méthode Dodgy brute) | Backteste moins bien que le retest (WR 24 % vs 33-47 %) ; l'edge de Dodgy est discrétionnaire | conservée en variante témoin |
| 2026-06 | Filtre multi-timeframe M15+M5+M1 | Jugé non nécessaire, complexité sans gain démontré (arbitrage CONCORDANCE 2026-07-04) | abandonnée |
