#!/usr/bin/env python3
"""Diagnose this machine for roblox-ai-studio.

    python scripts/doctor.py           # table with a "how to fix" column
    python scripts/doctor.py --json    # machine-readable

Reads only: installs nothing, changes nothing. Environment variable VALUES are
never read into the output; the report says only "configured" or "missing".
Exit code 1 when something required is missing.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skills_sync as ss  # noqa: E402

HOME = Path.home()
SYSTEM = platform.system()  # Windows | Darwin | Linux
OK, WARN, FAIL = "ok", "warn", "fail"
ICON = {OK: "✅", WARN: "⚠️", FAIL: "❌"}


@dataclass
class Check:
    group: str
    name: str
    status: str
    detail: str
    fix: str = ""
    required: bool = False


CHECKS: list[Check] = []


def add(group: str, name: str, ok: bool, detail: str, fix: str, required: bool, warn_only: bool = False) -> None:
    status = OK if ok else (WARN if warn_only or not required else FAIL)
    CHECKS.append(Check(group, name, status, detail, "" if ok else fix, required))


# --------------------------------------------------------------------------- programs

def extra_dirs() -> list[Path]:
    dirs = [HOME / ".rokit" / "bin", HOME / ".aftman" / "bin", HOME / ".cargo" / "bin", HOME / ".local" / "bin"]
    if SYSTEM == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData" / "Local"))
        dirs += [local / "Microsoft" / "WinGet" / "Links", local / "Programs" / "Microsoft VS Code" / "bin"]
    return dirs


def find(name: str) -> str | None:
    hit = shutil.which(name)
    if hit:
        return hit
    for d in extra_dirs():
        for cand in (d / name, d / f"{name}.exe", d / f"{name}.cmd"):
            if cand.exists():
                return str(cand)
    if SYSTEM == "Windows":
        # winget puts portable packages here and only fixes PATH for NEW shells.
        local = os.environ.get("LOCALAPPDATA", str(HOME / "AppData" / "Local"))
        hits = sorted(glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "*", f"{name}.exe")))
        if hits:
            return hits[-1]
    return None


def find_blender() -> str | None:
    env = os.environ.get("BLENDER")
    if env and Path(env).exists():
        return env
    hit = find("blender")
    if hit:
        return hit
    patterns = {
        "Windows": [os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                                 "Blender Foundation", "Blender*", "blender.exe")],
        "Darwin": ["/Applications/Blender.app/Contents/MacOS/Blender"],
        "Linux": ["/usr/bin/blender", "/snap/bin/blender", "/opt/blender*/blender"],
    }.get(SYSTEM, [])
    found = sorted(p for pat in patterns for p in glob.glob(pat))
    # SyphoDev's skills target Blender 4.x, so a 4.x install wins over a newer one.
    four = [p for p in found if re.search(r"Blender[ -]?4\.", p)]
    return (four or found)[-1] if found else None


def version(exe: str, *args: str) -> str:
    try:
        res = subprocess.run([exe, *(args or ("--version",))], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30)
        out = (res.stdout or res.stderr).strip().splitlines()
        return out[0].strip() if out else "?"
    except (OSError, subprocess.SubprocessError):
        return "?"


def check_programs() -> None:
    g = "Programas"
    winget = SYSTEM == "Windows"

    def how(win: str, other: str) -> str:
        return win if winget else other

    exe = find("git")
    add(g, "git", bool(exe), version(exe) if exe else "no encontrado",
        how("winget install Git.Git", "https://git-scm.com/downloads"), True)

    py = sys.version_info
    add(g, "python ≥ 3.11", py >= (3, 11), f"Python {platform.python_version()}",
        how("winget install Python.Python.3.12", "https://www.python.org/downloads/"), True)

    exe = find("claude")
    add(g, "claude", bool(exe), version(exe) if exe else "no encontrado",
        "https://code.claude.com/docs/en/setup", True)

    exe = find("rokit")
    add(g, "rokit", bool(exe), version(exe) if exe else "no encontrado",
        how("winget install Rojo.Rokit  (luego abre una terminal nueva)",
            "https://github.com/rojo-rbx/rokit#installation"), True)

    exe = find_blender()
    detail = version(exe) if exe else "no encontrado (PATH, BLENDER ni rutas estándar)"
    add(g, "blender", bool(exe), detail,
        how("winget install BlenderFoundation.Blender.LTS.4.5", "https://www.blender.org/download/lts/"), True)
    if exe and re.search(r"Blender (\d+)", detail) and not re.search(r"Blender 4\.", detail):
        add(g, "blender versión 4.x", False, detail,
            "SyphoDev pide 4.x: winget install BlenderFoundation.Blender.LTS.4.5 o define BLENDER", False,
            warn_only=True)

    for tool in ("uv", "uvx"):
        exe = find(tool)
        add(g, tool, bool(exe), version(exe) if exe else "no encontrado",
            how("winget install astral-sh.uv", "curl -LsSf https://astral.sh/uv/install.sh | sh"), True)

    exe = find("code")
    add(g, "VS Code", bool(exe), "encontrado" if exe else "no encontrado",
        how("winget install Microsoft.VisualStudioCode", "https://code.visualstudio.com/"), False)

    for tool, fix in (("node", how("winget install OpenJS.NodeJS.LTS", "https://nodejs.org")),
                      ("npx", how("viene con Node LTS", "viene con Node LTS")),
                      ("ffmpeg", how("winget install Gyan.FFmpeg", "brew install ffmpeg / apt install ffmpeg"))):
        exe = find(tool)
        add(g, f"{tool} (opcional)", bool(exe), version(exe, "-version" if tool == "ffmpeg" else "--version")
            if exe else "no encontrado", fix, False)


# --------------------------------------------------------------------------- studio

def studio_launcher() -> Path | None:
    if SYSTEM == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", HOME / "AppData" / "Local")) / "Roblox" / "mcp.bat"
    if SYSTEM == "Darwin":
        return Path("/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP")
    return None


def check_studio() -> None:
    g = "Studio"
    launcher = studio_launcher()
    if launcher is None:
        add(g, "lanzador MCP de Studio", False, f"Roblox Studio no existe para {SYSTEM}",
            "Usa Windows o macOS para Studio; el resto de la plantilla funciona aquí", False, warn_only=True)
    else:
        add(g, "lanzador MCP de Studio", launcher.exists(), str(launcher),
            "Instala Roblox Studio y ábrelo una vez (https://create.roblox.com/docs/studio/setup)", True)
    add(g, "Script Sync apagado", False, "no se puede comprobar desde fuera de Studio",
        "Manual: en Studio deja Script Sync APAGADO; usamos Rojo", False, warn_only=True)
    add(g, "Interruptor del MCP", False, "no se puede comprobar desde fuera de Studio",
        "Manual: Assistant → … → Manage MCP Servers → Enable Studio as MCP server (revísalo tras cada "
        "actualización); el indicador debe estar verde", False, warn_only=True)


# --------------------------------------------------------------------------- env vars

def env_present(name: str) -> tuple[bool, str]:
    """Presence only. Values are never returned or printed."""
    if os.environ.get(name):
        return True, "configurada"
    if SYSTEM == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                winreg.QueryValueEx(key, name)
            return True, "configurada con setx (abre una terminal nueva para verla)"
        except OSError:
            pass
    return False, "falta"


def set_hint(name: str) -> str:
    return (f'setx {name} "<valor>"  (en una terminal propia, nunca en el chat)' if SYSTEM == "Windows"
            else f'export {name}="<valor>" en tu ~/.zshrc o ~/.bashrc')


def check_env() -> None:
    g = "Variables"
    for name, what in (("ROBLOX_API_KEY", "Open Cloud (Assets)"), ("CF_ACCOUNT_ID", "Cloudflare Workers AI"),
                       ("CF_API_TOKEN", "Cloudflare Workers AI"), ("HF_TOKEN", "Hugging Face (opcional)")):
        ok, detail = env_present(name)
        add(g, name, ok, f"{detail} · {what}", set_hint(name), False)

    user_ok, _ = env_present("ROBLOX_USER_ID")
    group_ok, _ = env_present("ROBLOX_GROUP_ID")
    add(g, "ROBLOX_USER_ID o ROBLOX_GROUP_ID", user_ok or group_ok,
        "configurada" if user_ok or group_ok else "falta · dueño de las subidas de Open Cloud",
        set_hint("ROBLOX_USER_ID"), False)

    tok, _ = env_present("KAGGLE_API_TOKEN")
    kjson = (HOME / ".kaggle" / "kaggle.json").exists()  # existence only, never read
    add(g, "KAGGLE_API_TOKEN o ~/.kaggle/kaggle.json", tok or kjson,
        "configurada" if tok else "kaggle.json presente" if kjson else "falta · GPU de Kaggle (imagen → 3D)",
        set_hint("KAGGLE_API_TOKEN"), False)

    for name in ("BLENDER", "KILN_HOME", "ROBLOX_VFX_LIB"):
        ok, detail = env_present(name)
        add(g, f"{name} (opcional)", ok, detail, set_hint(name), False)


# --------------------------------------------------------------------------- skills and plugins

def syphodev_check_setup() -> dict | None:
    script = ss.USER_SKILLS / "roblox-skills-setup" / "scripts" / "check_setup.py"
    if not script.exists():
        return None
    try:
        res = subprocess.run([sys.executable, str(script), "--json"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60)
        return json.loads(res.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def check_skills() -> None:
    g = "Skills"
    lock = ss.load_lock()
    syph = ss.source(lock, "syphodev-roblox-ai-skills")
    setup_hint = "Ejecuta scripts/setup.ps1 (Windows) o scripts/setup.sh"

    vend = ss.vendor_dir(syph)
    names = sorted(p.name for p in (vend / "skills").iterdir() if p.is_dir()) if (vend / "skills").is_dir() else [
        "create-roblox-game", "roblox-3d-model", "roblox-animation", "roblox-build-orchestrator", "roblox-code",
        "roblox-map", "roblox-sfx", "roblox-skills-setup", "roblox-texture-gen", "roblox-ui", "roblox-vfx"]
    missing = [n for n in names if not (ss.USER_SKILLS / n / "SKILL.md").exists()]
    add(g, f"SyphoDev: {len(names)} skills en ~/.claude/skills", not missing,
        "todas presentes" if not missing else "faltan: " + ", ".join(missing), setup_hint, True)

    report = syphodev_check_setup()
    if report:
        need = [s for s, r in report.get("skills", {}).items()
                if r.get("installed") and r.get("needs_settings") and not r.get("LOCAL.md")]
        add(g, "SyphoDev: LOCAL.md", not need,
            "configurados" if not need else "sin LOCAL.md: " + ", ".join(need),
            "En Claude Code escribe /roblox-skills-setup", False, warn_only=True)
    else:
        add(g, "SyphoDev: LOCAL.md", False, "check_setup.py no disponible", setup_hint, False, warn_only=True)

    extra = syph["install"]["patchAgents"]["disallowedTools"]
    agents = [p.name for p in ss.syphodev_agents(syph)] or [
        "roblox-asset-anim.md", "roblox-asset-map.md", "roblox-asset-mesh.md", "roblox-asset-sfx.md",
        "roblox-asset-ui.md", "roblox-asset-vfx.md", "roblox-market-scout.md"]
    absent = [a for a in agents if not (ss.USER_AGENTS / a).exists()]
    unpatched = [a for a in agents if a not in absent and not ss.agent_is_patched(ss.USER_AGENTS / a, extra)]
    add(g, f"SyphoDev: {len(agents)} agentes parchados", not absent and not unpatched,
        "sin acceso al MCP de Studio" if not absent and not unpatched else
        "; ".join(filter(None, ["faltan: " + ", ".join(absent) if absent else "",
                                "sin parche: " + ", ".join(unpatched) if unpatched else ""])),
        setup_hint, True)

    project = sorted({Path(*Path(c["to"]).parts[:3]).as_posix()
                      for s in lock["sources"] if s["install"]["method"] == "copy" for c in s["install"]["copy"]})
    gone = [p for p in project if not (ss.REPO / p / "SKILL.md").exists()]
    add(g, "Skills de proyecto (terceros)", not gone, ", ".join(Path(p).name for p in project) if not gone
        else "faltan: " + ", ".join(gone), setup_hint, True)

    own = ["studio-doctor", "quota-guard", "own-audio", "own-images", "cloud-test"]
    gone = [n for n in own if not (ss.REPO / ".claude" / "skills" / n / "SKILL.md").exists()]
    add(g, "Skills propias", not gone, ", ".join(own) if not gone else "faltan: " + ", ".join(gone),
        "Restaura .claude/skills/ desde git", True)

    pins = []
    for s in ss.git_sources(lock):
        d = ss.vendor_dir(s)
        if (d / ".git").exists():
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=d, capture_output=True, text=True).stdout.strip()
            if head != s["commit"]:
                pins.append(s["name"])
        else:
            pins.append(s["name"])
    add(g, "vendor/ en los commits fijados", not pins, "todo fijado" if not pins else "distinto: " + ", ".join(pins),
        setup_hint, False)


def check_plugins() -> None:
    g = "Plugins"
    lock = ss.load_lock()
    plugins = ss.claude_json("plugin", "list", "--json")
    if plugins is None:
        add(g, "claude plugin list", False, "no se pudo ejecutar", "Instala Claude Code y ejecuta el setup", True)
        return
    by_id = {p.get("id"): p for p in plugins}
    for src in ss.plugin_sources(lock):
        pid = src["install"]["plugin"]
        p = by_id.get(pid)
        ok = bool(p) and p.get("enabled", False) and not p.get("errors")
        detail = ("no instalado" if not p else "con errores: " + "; ".join(p["errors"]) if p.get("errors")
                  else f"{p.get('scope')} · {'activo' if p.get('enabled') else 'desactivado'}")
        add(g, pid, ok, detail, f"claude plugin install {pid} --scope project (o ejecuta el setup)", True)
    same, detail = ss.el4cteo_plugin_matches(lock)
    if same is not None and detail != "not installed":
        add(g, "roblox-skills fijado", bool(same), detail,
            "Ejecuta el setup: vuelve a fijar el marketplace al tag del lock", False, warn_only=True)


# --------------------------------------------------------------------------- games

def check_games() -> None:
    g = "Juegos"
    expected = ss.REPO / "games"
    value = os.environ.get("ROBLOX_GAMES_HOME")
    if not value and SYSTEM == "Windows":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value = winreg.QueryValueEx(key, "ROBLOX_GAMES_HOME")[0]
        except OSError:
            value = None
    if not value:
        fix = (f'setx ROBLOX_GAMES_HOME "{expected}"' if SYSTEM == "Windows"
               else f'export ROBLOX_GAMES_HOME="{expected}"')
        add(g, "ROBLOX_GAMES_HOME", False, "falta", f"Ejecuta el setup o: {fix}", False)
        return
    path = Path(os.path.expandvars(value)).expanduser()
    # The path itself is not a secret, so it is shown.
    add(g, "ROBLOX_GAMES_HOME", path.is_dir(), f"{path}" + ("" if path.is_dir() else " (no existe)"),
        f"Crea la carpeta o apunta la variable a {expected}", False)
    if path.is_dir() and path.resolve() != expected.resolve():
        add(g, "ROBLOX_GAMES_HOME = <repo>/games", False, f"apunta a {path}",
            f"Recomendado: {expected}", False, warn_only=True)


# --------------------------------------------------------------------------- output

def print_table() -> None:
    w_name = max(len(c.name) for c in CHECKS)
    w_detail = 58
    group = None
    for c in CHECKS:
        if c.group != group:
            group = c.group
            print(f"\n{group}")
            print(f"  {'':2} {'Comprobación'.ljust(w_name)}  {'Detalle'.ljust(w_detail)}  Cómo arreglarlo")
        detail = c.detail if len(c.detail) <= w_detail else c.detail[: w_detail - 1] + "…"
        print(f"  {ICON[c.status]} {c.name.ljust(w_name)}  {detail.ljust(w_detail)}  {c.fix}")
    fails = [c for c in CHECKS if c.status == FAIL]
    warns = [c for c in CHECKS if c.status == WARN]
    print(f"\nResumen: {len(CHECKS) - len(fails) - len(warns)} ✅  {len(warns)} ⚠️  {len(fails)} ❌")
    if fails:
        print("Falta algo obligatorio: arregla las filas ❌ y vuelve a ejecutar python scripts/doctor.py")


STEPS = {
    "Programas": check_programs,
    "Studio": check_studio,
    "Variables": check_env,
    "Skills": check_skills,
    "Plugins": check_plugins,
    "Juegos": check_games,
}


def collect(groups: list[str] | None = None) -> list[Check]:
    """Run the checks of `groups` (all by default) and return them. Used by RoNavi Studio."""
    CHECKS.clear()
    for name, step in STEPS.items():
        if groups is None or name in groups:
            step()
    return list(CHECKS)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print the checks as JSON")
    a = ap.parse_args()
    collect()
    if a.json:
        print(json.dumps({"platform": f"{SYSTEM} {platform.release()}",
                          "checks": [asdict(c) for c in CHECKS]}, indent=2, ensure_ascii=False))
    else:
        print(f"RoNavi Studio doctor · {SYSTEM} {platform.release()} · {ss.REPO}")
        print_table()
    return 1 if any(c.status == FAIL for c in CHECKS) else 0


if __name__ == "__main__":
    sys.exit(main())
