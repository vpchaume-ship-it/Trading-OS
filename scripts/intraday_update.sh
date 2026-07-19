#!/usr/bin/env bash
# Rafraîchissement INTRADAY du dashboard (déclencheurs planifiés toutes les 30 min
# pendant la killzone NY). Léger et idempotent :
#   accumulate (prix frais) -> build --light (réutilise strategy_state.json).
# PAS d'autotune (1×/jour au build du matin, sinon overfitting intraday),
# PAS d'extension deep, PAS de commit (le hook Stop et la routine du matin s'en
# chargent). La republication Artifact reste faite par l'agent.
#
#   bash scripts/intraday_update.sh <chemin_dashboard.html>
set -uo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-dashboard_out.html}"

# Porte DST-proof : n'exécuter que pendant la séance RTH NY (9:25 → 16:20,
# marge incluse pour capter la clôture 16:00) un jour de semaine. Ainsi le
# prix reste frais toute la séance et le dernier build du jour affiche le
# CLOSE — le soir/le week-end, le dashboard montre la clôture, pas le prix du
# matin. Les crons UTC débordent volontairement pour couvrir été (EDT) et
# hiver (EST) ; cette porte fait le tri. TOS_SKIP_GATE=1 force le build.
if [ "${TOS_SKIP_GATE:-0}" != "1" ]; then
  python - << 'PYGATE' || { echo "Hors killzone/séance NY — firing ignoré."; exit 0; }
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
now = datetime.now(ZoneInfo("America/New_York"))
mins = now.hour * 60 + now.minute
ok = now.weekday() < 5 and (9 * 60 + 25) <= mins <= (16 * 60 + 20)
sys.exit(0 if ok else 1)
PYGATE
fi

python -m trading_os.data.accumulate || echo "accumulation KO — on continue avec l'existant"
python -m trading_os.webapp.build "$OUT" --light || { echo "BUILD INTRADAY ÉCHOUÉ"; exit 1; }
echo "Rafraîchissement intraday terminé : $OUT (à republier via l'outil Artifact)."
