#!/usr/bin/env sh
# RoNavi Studio launcher for macOS and Linux:  sh ronavi.sh  (or ./ronavi.sh after chmod +x)
# Finds Python 3.11+, prepares .venv on first run and opens the TUI.
self=$0
while [ -h "$self" ]; do
  dir=$(cd "$(dirname "$self")" && pwd)
  link=$(readlink "$self")
  case $link in
    /*) self=$link ;;
    *) self=$dir/$link ;;
  esac
done
here=$(cd "$(dirname "$self")" && pwd)
for py in python3 python; do
  if command -v "$py" >/dev/null 2>&1; then
    exec "$py" "$here/ronavi/bootstrap.py" "$@"
  fi
done
echo "RoNavi Studio necesita Python 3.11 o superior: https://www.python.org/downloads/ (o brew install python)." >&2
exit 1
