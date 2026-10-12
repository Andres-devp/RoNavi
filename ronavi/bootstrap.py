"""Entry point used by ronavi.cmd / ronavi.sh. Standard library only.

1. Checks Python >= 3.11.
2. Creates <studio>/.venv and installs ronavi/requirements.txt there, only when the
   venv is missing or the requirements changed (hash stamp). Nothing goes into the
   user's own Python.
3. Runs `python -m ronavi <args>` with the venv's interpreter.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[1]
VENV = STUDIO / ".venv"
REQUIREMENTS = STUDIO / "ronavi" / "requirements.txt"
STAMP = VENV / ".ronavi-requirements.sha256"
ORANGE, DIM, RESET = "\033[38;2;255;138;61m", "\033[2m", "\033[0m"


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def say(msg: str) -> None:
    print(f"{ORANGE}▌ RoNavi Studio{RESET} {msg}", flush=True)


def ensure_venv() -> Path:
    py = venv_python()
    wanted = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    if py.exists() and STAMP.exists() and STAMP.read_text(encoding="utf-8").strip() == wanted:
        return py
    say("preparando su entorno (solo la primera vez o tras una actualización)…")
    if not py.exists():
        say(f"{DIM}creando {VENV}{RESET}")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    say(f"{DIM}instalando {REQUIREMENTS.name} en el venv{RESET}")
    subprocess.check_call([str(py), "-m", "pip", "install", "--disable-pip-version-check", "--quiet",
                           "-r", str(REQUIREMENTS)])
    STAMP.write_text(wanted + "\n", encoding="utf-8")
    return py


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.version_info < (3, 11):
        print(f"RoNavi Studio necesita Python 3.11 o superior (tienes {sys.version.split()[0]}).")
        print("Windows: winget install Python.Python.3.12   ·   macOS: brew install python")
        return 1
    try:
        py = ensure_venv()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"No se pudo preparar el entorno de RoNavi: {exc}")
        print(f"Prueba a borrar {VENV} y vuelve a ejecutar ronavi. ¿Sin internet? pip necesita descargar Textual.")
        return 1
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(STUDIO), env.get("PYTHONPATH")]))
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        return subprocess.call([str(py), "-m", "ronavi", *argv], env=env)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
