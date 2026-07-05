#!/usr/bin/env bash
# Routine quotidienne Trading OS (appelée par le déclencheur planifié à 9:20 NY).
# Tout est idempotent et sans secret : sûr à relancer, no-op si rien n'a changé.
#
#   bash scripts/daily_update.sh <chemin_dashboard.html>
#
# Étapes : accumulation données Yahoo -> sync journal Tradovate demo (si creds)
# -> build dashboard -> commit/push des fichiers de données persistants.
# La republication de l'Artifact reste faite par l'agent (outil Artifact).
set -uo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-dashboard_out.html}"
BRANCH="claude/trading-os-ifvg-terminal-pize5y"

# Porte pré-ouverture DST-proof. Le cron UTC ne suit pas l'heure d'été de New York :
# un firing à 13:20 UTC vaut 9:20 NY en été (EDT) et 8:20 NY en hiver (EST). On
# accepte donc toute la fenêtre pré-marché 8:00–9:35 NY -> le firing unique tombe
# toujours juste avant l'ouverture, quelle que soit la saison, sans réglage manuel.
# (Si un second firing à 14:20 UTC est ajouté, il donne 9:20 NY pile en hiver ;
#  en été il tomberait à 10:20 NY, hors fenêtre, et serait donc ignoré ici.)
if [ "${TOS_SKIP_GATE:-0}" != "1" ]; then
  python - << 'PYGATE' || { echo "Hors fenêtre pré-ouverture NY — firing ignoré."; exit 0; }
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
now = datetime.now(ZoneInfo("America/New_York"))
mins = now.hour * 60 + now.minute
sys.exit(0 if 8 * 60 <= mins <= 9 * 60 + 35 else 1)
PYGATE
fi

retry() {  # retry <n> <cmd...>
  local n=$1; shift
  for i in $(seq 1 "$n"); do "$@" && return 0; echo "échec ($i/$n), attente 30s…"; sleep 30; done
  return 1
}

git fetch origin "$BRANCH" 2>/dev/null && git checkout "$BRANCH" 2>/dev/null && git pull --ff-only 2>/dev/null || true
pip install -q -r requirements.txt >/dev/null 2>&1 || true

retry 3 python -m trading_os.data.accumulate || echo "accumulation KO — on continue avec l'existant"
python -m trading_os.forward.sync_cli || true          # no-op sans identifiants demo
python -m trading_os.webapp.build "$OUT" || { echo "BUILD ÉCHOUÉ"; exit 1; }

git add data/yahoo_*.csv data/strategy_state.json journal/news/history.csv journal/trades.csv 2>/dev/null || true
if ! git diff --cached --quiet; then
  git commit -q -m "data: accumulation quotidienne + auto-réglage + journal"
  retry 4 git push origin "$BRANCH" || echo "PUSH ÉCHOUÉ"
fi
echo "Routine terminée. Dashboard: $OUT (à republier via l'outil Artifact)."
