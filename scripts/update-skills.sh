#!/usr/bin/env bash
# Muestra qué cambió en cada fuente de skills y, si lo apruebas, mueve el commit fijado.
#
#   bash scripts/update-skills.sh
#
# Para cada fuente de skills.lock.json trae el último commit (o el último tag, en el
# plugin de EL4CTEO), muestra "git log --oneline <fijado>..<nuevo>" y el diffstat, y
# pregunta antes de tocar skills.lock.json. Si algo cambió, vuelve a ejecutar setup.sh.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
py="$(command -v python3 || command -v python || true)"
[ -n "$py" ] || { echo "ERROR: falta python3" >&2; exit 1; }

cd "$repo"
code=0
"$py" "$repo/scripts/skills_sync.py" update || code=$?
if [ "$code" -eq 3 ]; then
  printf '\nReinstalando con los commits nuevos...\n'
  code=0
  bash "$repo/scripts/setup.sh" --games-home=no || code=$?
  printf '\nRevisa los cambios y haz commit:  git diff skills.lock.json .claude/settings.json\n'
fi
exit "$code"
