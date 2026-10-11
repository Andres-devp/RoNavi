#!/usr/bin/env bash
# Prepara roblox-ai-studio en macOS o Linux. Se puede ejecutar varias veces.
#
#   bash scripts/setup.sh                    # pregunta antes de tocar ROBLOX_GAMES_HOME
#   bash scripts/setup.sh --games-home=no    # sin preguntar
#   bash scripts/setup.sh --force            # reinstala SyphoDev aunque esté al día
#
# Pasos: 1 git/python/claude · 2 vendor/ · 3 SyphoDev + parche de agentes ·
# 4 skills de proyecto · 5 plugins (+ MCP de Studio en macOS) · 6 pip ·
# 7 ROBLOX_GAMES_HOME · 8 doctor.py
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
sync="$repo/scripts/skills_sync.py"
force=""
games_home="ask"
for arg in "$@"; do
  case "$arg" in
    --force) force="--force" ;;
    --games-home=*) games_home="${arg#*=}" ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[36m[%s/8] %s\033[0m\n' "$1" "$2"; }
die() { printf '\033[31mERROR: %s\033[0m\n' "$1" >&2; exit 1; }

cd "$repo"

step 1 "Comprobando git, python y claude"
py=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then py="$cand"; break; fi
done
missing=()
command -v git >/dev/null 2>&1 || missing+=(git)
[ -n "$py" ] || missing+=(python3)
command -v claude >/dev/null 2>&1 || missing+=(claude)
if [ "${#missing[@]}" -gt 0 ]; then
  echo "Faltan: ${missing[*]}"
  echo "  git     -> https://git-scm.com/downloads"
  echo "  python3 -> https://www.python.org/downloads/ (3.11+)"
  echo "  claude  -> https://code.claude.com/docs/en/setup"
  die "Instala lo que falta y vuelve a ejecutar el setup."
fi
"$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || die "Se necesita Python 3.11 o superior."
echo "  ok git, $py, claude"

step 2 "Fuentes fijadas en vendor/"
"$py" "$sync" vendor

step 3 "Skills y agentes de SyphoDev (nivel usuario)"
"$py" "$sync" user $force

step 4 "Skills de proyecto"
"$py" "$sync" project

step 5 "Plugins de Claude Code"
"$py" "$sync" plugins
"$py" "$sync" local-settings
if [ "$(uname -s)" = "Darwin" ]; then
  # .mcp.json carries the Windows launcher. On macOS the same server name is
  # registered in LOCAL scope, which takes precedence over the project entry.
  studio_mcp="/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP"
  if [ -x "$studio_mcp" ]; then
    claude mcp remove --scope local Roblox_Studio >/dev/null 2>&1 || true
    claude mcp add --scope local Roblox_Studio -- "$studio_mcp"
    echo "  ok Roblox_Studio -> $studio_mcp (scope local)"
  else
    echo "  !! no existe $studio_mcp: instala Roblox Studio y vuelve a ejecutar el setup"
  fi
else
  echo "  Roblox Studio no existe para Linux: el MCP de Studio queda sin configurar aquí."
fi

step 6 "Dependencias de Python"
pip_flags=(--user --disable-pip-version-check --no-warn-script-location --quiet)
if "$py" -m pip install "${pip_flags[@]}" -r "$repo/requirements.txt"; then
  echo "  ok requirements.txt"
else
  # Homebrew and Debian Python refuse --user installs (PEP 668). Do not force it:
  # the person chooses between a venv and PIP_BREAK_SYSTEM_PACKAGES=1.
  echo "  !! pip rechazó la instalación (Python gestionado por el sistema, PEP 668)."
  echo "     Opción A: PIP_BREAK_SYSTEM_PACKAGES=1 bash scripts/setup.sh   (instala solo en --user)"
  echo "     Opción B: usa un Python de python.org o pyenv y vuelve a ejecutar el setup."
fi

step 7 "ROBLOX_GAMES_HOME"
target="$repo/games"
case "${SHELL:-}" in
  */zsh) rc="$HOME/.zshrc" ;;
  *) rc="$HOME/.bashrc" ;;
esac
line="export ROBLOX_GAMES_HOME=\"$target\""
if [ -f "$rc" ] && grep -qxF "$line" "$rc"; then
  echo "  ok ya está en $rc"
else
  answer="$games_home"
  if [ "$answer" = "ask" ]; then
    reply=""
    if [ -t 0 ]; then
      read -r -p "  ¿Añadir ROBLOX_GAMES_HOME=$target a $rc? (s/N) " reply || true
    fi
    case "$reply" in s|S|si|sí|y|yes) answer="yes" ;; *) answer="no" ;; esac
  fi
  if [ "$answer" = "yes" ]; then
    printf '\n# roblox-ai-studio\n%s\n' "$line" >> "$rc"
    export ROBLOX_GAMES_HOME="$target"
    echo "  ok añadido a $rc (abre una terminal nueva)"
  else
    echo "  omitido. Para hacerlo luego, añade a $rc:"
    echo "    $line"
  fi
fi

step 8 "Diagnóstico"
doctor_exit=0
"$py" "$repo/scripts/doctor.py" || doctor_exit=$?

cat <<'EOF'

Pasos manuales que quedan:
  1. Roblox Studio: Assistant > ... > Manage MCP Servers > "Enable Studio as MCP server" (indicador verde).
     Script Sync APAGADO. Plugin de Rojo: dentro de un juego, "rokit install" y luego "rojo plugin install".
  2. Abre "claude" en esta carpeta y acepta la confianza del espacio de trabajo.
     /mcp para autenticar figma; /roblox-skills-setup para escribir los LOCAL.md.
  3. Variables de entorno con export en tu ~/.zshrc o ~/.bashrc (nunca en el chat): ver README, sección 3.
  4. Comprueba de nuevo con: python3 scripts/doctor.py
EOF
exit "$doctor_exit"
