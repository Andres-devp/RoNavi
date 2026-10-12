"""Machine state (through scripts/doctor.py) and the setup steps that fix it.

RoNavi does not duplicate the studio's checks: it imports `scripts/doctor.py` and runs
the same functions the command-line doctor runs. Setup steps reuse the existing
scripts (`install-prereqs.ps1`, `skills_sync.py`, `requirements.txt`).
"""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from ronavi.core.paths import Studio

SYSTEM = platform.system()
OK, WARN, FAIL = "ok", "warn", "fail"


@dataclass
class EnvCheck:
    group: str
    name: str
    status: str
    detail: str
    fix: str = ""
    required: bool = False


def load_doctor(studio: Studio) -> ModuleType:
    path = studio.root / "scripts" / "doctor.py"
    scripts = str(path.parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)  # doctor imports skills_sync from its own folder
    spec = importlib.util.spec_from_file_location("ronavi_studio_doctor", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # @dataclass looks its module up in sys.modules
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


def run_doctor(studio: Studio, groups: list[str] | None = None) -> list[EnvCheck]:
    doctor = load_doctor(studio)
    return [EnvCheck(c.group, c.name, c.status, c.detail, c.fix, c.required) for c in doctor.collect(groups)]


def counts(checks: list[EnvCheck]) -> tuple[int, int, int]:
    return (sum(c.status == OK for c in checks), sum(c.status == WARN for c in checks),
            sum(c.status == FAIL for c in checks))


def group_ok(checks: list[EnvCheck], group: str, required_only: bool = True) -> bool | None:
    rows = [c for c in checks if c.group == group and (c.required or not required_only)]
    if not rows:
        return None
    return all(c.status == OK for c in rows)


# --------------------------------------------------------------------------- probes

def system_python() -> str:
    for name in ("python", "python3"):
        hit = shutil.which(name)
        if hit and "WindowsApps" not in hit:  # the Store stub is not a Python
            return hit
    return getattr(sys, "_base_executable", None) or sys.executable


PY_MODULES = ["PIL", "numpy", "scipy", "cv2", "requests", "kaggle", "gradio_client", "huggingface_hub"]


def python_deps_ok() -> bool:
    code = ("import importlib.util as u, sys; m = %r; "
            "sys.exit(0 if all(u.find_spec(x) for x in m) else 1)") % PY_MODULES
    try:
        return subprocess.run([system_python(), "-c", code], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def claude_logged_in() -> bool | None:
    """Existence check only (the file is never read). None = cannot tell (macOS keychain)."""
    if (Path.home() / ".claude" / ".credentials.json").exists():
        return True
    if SYSTEM == "Darwin":
        return None
    return False


def user_env(name: str) -> str | None:
    """Value of a user environment variable, including ones set with setx after this process started."""
    if os.environ.get(name):
        return os.environ[name]
    if SYSTEM == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                return str(winreg.QueryValueEx(key, name)[0])
        except OSError:
            return None
    return None


def rokit_needs_self_install() -> bool:
    return bool(shutil.which("rokit")) and not (Path.home() / ".rokit" / "bin").exists()


# --------------------------------------------------------------------------- setup steps

@dataclass
class SetupStep:
    key: str
    title: str
    why: str
    kind: str                          # stream | interactive | manual | action
    commands: list[list[str]] = field(default_factory=list)
    manual: list[str] = field(default_factory=list)


def setup_steps(studio: Studio, optional_programs: bool = False) -> list[SetupStep]:
    py = system_python()
    sync = str(studio.root / "scripts" / "skills_sync.py")
    steps: list[SetupStep] = []

    if SYSTEM == "Windows":
        prereqs = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   str(studio.root / "scripts" / "install-prereqs.ps1")]
        if optional_programs:
            prereqs.append("-Optional")
        steps.append(SetupStep(
            "programs", "Programas", "Git, VS Code, Python, Rokit, uv, Blender 4.5, Roblox Studio y Claude Code "
            "con winget. winget te pedirá aceptar cada licencia en la terminal.", "interactive", [prereqs]))
    else:
        steps.append(SetupStep(
            "programs", "Programas", "Instálalos con tu gestor de paquetes; RoNavi comprueba el resultado.",
            "manual", manual=[
                "brew install git python uv ffmpeg node   (macOS)",
                "Rokit: https://github.com/rojo-rbx/rokit#installation",
                "Blender 4.5 LTS: https://www.blender.org/download/lts/",
                "Claude Code: https://code.claude.com/docs/en/setup",
                "Roblox Studio (solo Windows y macOS): https://create.roblox.com/docs/studio/setup",
            ]))

    if rokit_needs_self_install():
        steps.append(SetupStep("rokit", "Rokit", "Crea ~/.rokit/bin (rojo, wally…) y lo añade al PATH.",
                               "stream", [["rokit", "self-install"]]))

    steps.append(SetupStep(
        "login", "Sesión de Claude Code", "Se abre Claude Code: inicia sesión y sal con /exit.",
        "interactive", [["claude"]]))
    steps.append(SetupStep(
        "skills", "Skills y plugins", "Clona las fuentes fijadas en vendor/, instala SyphoDev en ~/.claude, "
        "copia las skills de proyecto e instala los plugins (roblox-skills, figma).", "stream",
        [[py, sync, "vendor"], [py, sync, "user"], [py, sync, "project"], [py, sync, "plugins"],
         [py, sync, "local-settings"]]))
    steps.append(SetupStep(
        "pydeps", "Dependencias de Python", "Paquetes que importan los scripts de las skills (pip --user).",
        "stream", [[py, "-m", "pip", "install", "--user", "--disable-pip-version-check",
                    "--no-warn-script-location", "-r", str(studio.root / "requirements.txt")]]))
    steps.append(SetupStep(
        "gameshome", "Carpeta de juegos", f"ROBLOX_GAMES_HOME = {studio.games_home} para tu usuario "
        "(las skills la usan para encontrar los juegos).", "action"))
    steps.append(SetupStep(
        "studio", "Roblox Studio y servicios", "Pasos que solo puedes hacer tú.", "manual", manual=[
            "Studio: inicia sesión; Assistant → … → Manage MCP Servers → Enable Studio as MCP server.",
            "Studio: deja Script Sync APAGADO (usamos Rojo).",
            "Claude Code: /mcp → figma → autenticar (se abre desde Integraciones).",
            "Claude Code: /roblox-skills-setup para escribir los LOCAL.md (se abre desde Skills).",
            "Claves de API: en Integraciones (se guardan como variables de entorno, nunca en archivos).",
        ]))
    return steps


def step_done(step: SetupStep, studio: Studio, checks: list[EnvCheck]) -> bool | None:
    """True/False when RoNavi can tell, None when it cannot."""
    if step.key == "programs":
        return group_ok(checks, "Programas")
    if step.key == "rokit":
        return not rokit_needs_self_install()
    if step.key == "login":
        return claude_logged_in()
    if step.key == "skills":
        skills, plugins = group_ok(checks, "Skills"), group_ok(checks, "Plugins")
        return None if skills is None and plugins is None else bool(skills) and plugins is not False
    if step.key == "pydeps":
        return python_deps_ok()
    if step.key == "gameshome":
        value = user_env("ROBLOX_GAMES_HOME")
        return bool(value) and Path(os.path.expandvars(value)).expanduser().resolve() == studio.games_home
    if step.key == "studio":
        return "studio" in studio.config.manual_done
    return None
