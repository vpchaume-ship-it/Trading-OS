"""Scenario cards for red-folder events.

For each event type we describe the TYPICAL historical reaction of ES/NQ when
the print comes ABOVE / BELOW / IN LINE with consensus. These are qualitative
probability maps drawn from well-documented macro relationships — NEVER
certainties. Every card carries the judas-swing warning: the first impulse
after a red folder is frequently a liquidity raid before the true move.
"""

from __future__ import annotations

from dataclasses import dataclass

from trading_os.news.calendar import NewsEvent

JUDAS_WARNING = (
    "⚠️ RAPPEL SYSTÉMATIQUE : la réaction initiale à une news est souvent piégeuse "
    "(judas swing) — une fausse impulsion va chercher la liquidité d'un côté avant "
    "le vrai mouvement. Ne jamais trader l'impulsion des premières minutes ; "
    "respecter la no-trade-zone."
)


@dataclass
class ScenarioCard:
    event: NewsEvent
    above: str      # chiffre au-dessus du consensus
    below: str      # chiffre en dessous
    inline: str     # en ligne
    context: str    # logique macro / historique des réactions


# Chaque entrée : (mots-clés de détection, above, below, inline, contexte)
_LIBRARY: list[tuple[list[str], str, str, str, str]] = [
    (["cpi", "consumer price"],
     "Inflation plus chaude → le marché price des taux plus hauts plus longtemps → "
     "**baissier ES/NQ** (probabilité qualitative : élevée). NQ sous-performe "
     "généralement ES (duration/tech plus sensible aux taux). Historique : les CPI "
     "au-dessus de +0.1pt vs consensus ont produit des ranges de 60-120 pts NQ dans l'heure.",
     "Inflation plus froide → soulagement sur les taux → **haussier ES/NQ** "
     "(probabilité : élevée), NQ surperforme. Attention : si le marché est déjà très "
     "haussier, réaction 'sell the news' possible après le spike initial.",
     "Réaction initiale modérée puis retour au biais technique dominant. Souvent le "
     "scénario le plus piégeux : les deux côtés de la liquidité sont pris avant la direction.",
     "Le CPI est LE chiffre d'inflation dominant du cycle actuel. La composante core "
     "MoM pèse plus que le headline. Regarder aussi le supercore (services hors logement)."),
    (["ppi", "producer price"],
     "Comme CPI mais impact moindre → biais baissier modéré ES/NQ.",
     "Biais haussier modéré, surtout si le CPI de la même semaine confirmait.",
     "Réaction souvent faible, absorbée en 15-30 min.",
     "Le PPI précède parfois le CPI dans la chaîne des prix ; le marché le traite comme "
     "un indice avancé du PCE (certaines composantes PPI entrent dans le calcul PCE)."),
    (["non-farm", "nonfarm", "nfp", "employment change"],
     "Marché du travail fort → taux plus hauts → réaction initiale souvent **baissière**, "
     "MAIS un chiffre fort avec salaires (AHE) contenus peut s'inverser en 'bonne nouvelle "
     "économique' → journée volatile à double mouvement (le NFP est le judas swing classique).",
     "Marché du travail faible → double lecture : baisses de taux plus proches (haussier) "
     "vs peur de récession (baissier). Le contexte décide : en régime 'bad news = good news', "
     "haussier ; en régime peur de croissance, baissier.",
     "Le focus bascule sur le taux de chômage et les salaires horaires (AHE). "
     "Réaction souvent en deux temps sur 90 minutes.",
     "Publié à 8:30 NY un vendredi — killzone NY AM entièrement affectée. "
     "Historiquement le high/low de la journée est souvent posé dans les 30 premières minutes."),
    (["fomc", "federal funds", "rate decision", "press conference", "minutes"],
     "Plus hawkish qu'attendu (taux/dots/discours) → **baissier ES/NQ**, mouvement en "
     "plusieurs vagues : décision 14:00, inversion fréquente pendant la conférence 14:30.",
     "Plus dovish → **haussier**, même structure en vagues. Le mouvement de 14:00 est "
     "inversé pendant la conférence dans une proportion notable de réunions.",
     "Si tout est conforme, le marché trade la conférence de presse, pas le communiqué.",
     "Événement le plus manipulateur du calendrier : le premier mouvement post-communiqué "
     "est statistiquement le plus souvent repris. Ne rien trader avant la fin de la conf."),
    (["gdp", "gross domestic"],
     "Croissance plus forte → généralement haussier ES, mitigé NQ si les taux montent aussi.",
     "Croissance plus faible → baissier si peur de récession, haussier si lecture 'la Fed va couper'.",
     "Peu de réaction durable sauf grosse surprise sur le déflateur.",
     "Chiffre rétrospectif : le marché réagit surtout au déflateur GDP et à la conso personnelle."),
    (["unemployment claims", "jobless"],
     "Plus de demandeurs qu'attendu (marché du travail se dégrade) → lecture dominante "
     "récente : haussier court terme (baisses de taux) sauf si la dégradation est brutale.",
     "Moins de demandeurs (marché du travail solide) → légèrement baissier via les taux.",
     "Quasi aucun impact durable — chiffre hebdomadaire bruité.",
     "Impact faible sauf en période de focus 'croissance'. Publié 8:30 NY chaque jeudi."),
    (["retail sales"],
     "Conso plus forte → haussier ES modéré (croissance) mais peut peser via les taux.",
     "Conso plus faible → baissier modéré, sauf lecture 'Fed dovish'.",
     "Absorbé rapidement en général.",
     "Le control group compte plus que le headline (entre dans le calcul du GDP)."),
    (["pce"],
     "PCE core au-dessus → baissier ES/NQ (mesure d'inflation préférée de la Fed).",
     "PCE core en dessous → haussier, confirmation du chemin de désinflation.",
     "Souvent déjà pricé : les composantes CPI+PPI permettent de prédire le PCE.",
     "Le PCE surprend rarement car il est largement calculable à l'avance — les réactions "
     "fortes signalent un positionnement déséquilibré."),
    (["ism", "pmi"],
     "Au-dessus de 50 / du consensus → haussier modéré (croissance), sauf si prices paid flambe.",
     "En dessous → baissier modéré ; sous 47, peur de récession possible.",
     "Réaction brève ; regarder les sous-indices (emploi, prix payés, nouvelles commandes).",
     "Publié à 10:00 NY — en plein cœur de la killzone NY AM, provoque souvent le judas "
     "swing de milieu de matinée."),
    (["consumer confidence", "sentiment", "uom"],
     "Confiance plus forte → marginalement haussier ; regarder les anticipations d'inflation UoM.",
     "Confiance plus faible → marginalement baissier.",
     "Impact généralement mineur.",
     "Les anticipations d'inflation 1 an / 5-10 ans du rapport UoM peuvent dominer le headline."),
]

_DEFAULT = (
    "Chiffre au-dessus du consensus → interpréter via le prisme dominant du moment "
    "(inflation/taux vs croissance). Vérifier le contexte avant l'événement.",
    "Chiffre en dessous → lecture inverse, même prisme.",
    "En ligne → retour probable au biais technique ; méfiance maximale sur la première impulsion.",
    "Événement non répertorié dans la bibliothèque — faire une recherche manuelle "
    "(consensus, historique des réactions) avant la publication.")


def build_card(event: NewsEvent) -> ScenarioCard:
    title = event.title.lower()
    for keywords, above, below, inline, context in _LIBRARY:
        if any(k in title for k in keywords):
            return ScenarioCard(event, above, below, inline, context)
    return ScenarioCard(event, *_DEFAULT)


def card_markdown(card: ScenarioCard, ntz: tuple) -> str:
    e = card.event
    return "\n".join([
        f"### 🔴 {e.time_ny:%a %d/%m %H:%M} NY — {e.title}",
        f"- Consensus : **{e.forecast}** | Précédent : **{e.previous}**",
        f"- **NO TRADE ZONE : {ntz[0]:%H:%M} → {ntz[1]:%H:%M} NY**",
        "",
        f"**Si AU-DESSUS du consensus** : {card.above}",
        "",
        f"**Si EN DESSOUS** : {card.below}",
        "",
        f"**Si EN LIGNE** : {card.inline}",
        "",
        f"_Contexte : {card.context}_",
        "",
        JUDAS_WARNING,
        "",
    ])
