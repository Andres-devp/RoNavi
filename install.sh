#!/usr/bin/env sh
# RoNavi Studio installer for macOS and Linux. Run it again to update.
#
#   curl -fsSL https://raw.githubusercontent.com/Andres-devp/roblox-ai-studio/main/install.sh | sh
#
# 1. Checks git and Python 3.11+.
# 2. Clones the studio into $RONAVI_HOME (default: ~/RoNavi) at the newest release tag
#    (vX.Y.Z), or runs "ronavi update" when it is already there.
# 3. Links ~/.local/bin/ronavi and opens RoNavi Studio (the setup wizard does the rest).
#
# Optional: RONAVI_HOME (folder), RONAVI_REPO (git URL), RONAVI_NO_START=1,
# RONAVI_NO_PATH=1 (portable install: PATH untouched, nothing is started).
set -eu

repo=${RONAVI_REPO:-https://github.com/Andres-devp/roblox-ai-studio.git}
target=${RONAVI_HOME:-$HOME/RoNavi}

say() { printf '\033[38;2;255;138;61m▌ RoNavi Studio\033[0m %s\n' "$1"; }
fail() { printf 'RoNavi Studio: %s\n' "$1" >&2; exit 1; }

command -v git >/dev/null 2>&1 ||
  fail "hace falta git (macOS: xcode-select --install o brew install git; Linux: tu gestor de paquetes)."

py=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 &&
    "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    py=$candidate
    break
  fi
done
[ -n "$py" ] || fail "hace falta Python 3.11 o superior (macOS: brew install python; Linux: tu gestor de paquetes)."

is_studio() {
  [ -f "$1/skills.lock.json" ] && [ -f "$1/scripts/doctor.py" ] && [ -f "$1/ronavi/__init__.py" ]
}
boot=$target/ronavi/bootstrap.py

if is_studio "$target"; then
  say "ya estaba instalado en $target: buscando una versión nueva…"
  "$py" "$boot" update || say "no se pudo actualizar; se mantiene la versión instalada."
elif [ -e "$target" ] && [ -n "$(ls -A "$target" 2>/dev/null)" ]; then
  fail "$target ya existe y no es RoNavi Studio. Elige otra carpeta: RONAVI_HOME=/otra/carpeta"
else
  say "descargando en $target"
  git clone --quiet "$repo" "$target"
  tag=$(git -C "$target" tag --list 'v*' --sort=-v:refname | head -n 1)
  if [ -n "$tag" ]; then
    say "versión $tag"
    git -C "$target" -c advice.detachedHead=false checkout --quiet "$tag"
  else
    say "aún no hay versiones publicadas: se usa la rama main."
  fi
fi

if [ -n "${RONAVI_NO_PATH:-}" ]; then
  say "PATH sin tocar (RONAVI_NO_PATH). Arranca con: sh $target/ronavi.sh"
  exit 0
fi
"$py" "$boot" path add
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) say "añade ~/.local/bin a tu PATH (en ~/.zshrc o ~/.bashrc): export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac
say "listo. En cualquier terminal nueva escribe: ronavi"

# "curl | sh" gives this script the pipe as stdin: the TUI needs the real terminal.
if [ -z "${RONAVI_NO_START:-}" ] && [ -t 1 ] && [ -r /dev/tty ]; then
  exec "$py" "$boot" </dev/tty
fi
