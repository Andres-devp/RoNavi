"""MCP servers, API keys (as environment variables) and quotas."""

from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ronavi.core.environment import system_python, user_env
from ronavi.core.paths import Studio, read_json, write_json_atomic

SYSTEM = platform.system()

STUDIO_SERVERS = ("Roblox_Studio", "robloxstudio-runtime")  # only one of these at a time (D3)
MCP_SERVERS = [
    ("Roblox_Studio", "MCP oficial de Roblox Studio", "Siempre encendido salvo para depurar en vivo."),
    ("robloxstudio-runtime", "Depuración en vivo (Chrrxs)", "Apaga el oficial mientras lo usas."),
    ("blender-ahujasid", "Blender (ahujasid)", "Opcional: modelar con Blender abierto."),
]


@dataclass
class KeyInfo:
    name: str
    label: str
    secret: bool
    optional: bool = False


KEYS = [
    KeyInfo("ROBLOX_API_KEY", "Roblox Open Cloud (Assets; places y Luau Execution para cloud-test)", True),
    KeyInfo("ROBLOX_USER_ID", "Tu ID de usuario de Roblox (dueño de las subidas)", False),
    KeyInfo("ROBLOX_GROUP_ID", "ID de grupo (en lugar del usuario)", False, optional=True),
    KeyInfo("ROBLOX_TEST_UNIVERSE_ID", "Universo de PRUEBAS para cloud-test (nunca el del juego publicado)", False,
            optional=True),
    KeyInfo("ROBLOX_TEST_PLACE_ID", "Place de PRUEBAS para cloud-test", False, optional=True),
    KeyInfo("CF_ACCOUNT_ID", "Cloudflare Account ID (Workers AI)", False),
    KeyInfo("CF_API_TOKEN", "Cloudflare API token (Workers AI)", True),
    KeyInfo("KAGGLE_API_TOKEN", "Kaggle API token (GPU imagen → 3D)", True),
    KeyInfo("HF_TOKEN", "Hugging Face (respaldo ZeroGPU)", True, optional=True),
    KeyInfo("BLENDER", "Ruta de blender.exe (si no está en el PATH)", False, optional=True),
    KeyInfo("ROBLOX_VFX_LIB", "Carpeta de tu librería de VFX", False, optional=True),
]
KEY_NAMES = {k.name for k in KEYS}


# --------------------------------------------------------------------------- MCP servers

def _settings_files(project: Path) -> tuple[Path, Path]:
    return project / ".claude" / "settings.json", project / ".claude" / "settings.local.json"


def mcp_state(project: Path) -> dict[str, bool]:
    shared, local = (read_json(p, {}) or {} for p in _settings_files(project))
    declared = (read_json(project / ".mcp.json", {}) or {}).get("mcpServers", {})
    on = set(shared.get("enabledMcpjsonServers", [])) | set(local.get("enabledMcpjsonServers", []))
    off = set(shared.get("disabledMcpjsonServers", [])) | set(local.get("disabledMcpjsonServers", []))
    return {name: name in declared and name in on and name not in off for name, _, _ in MCP_SERVERS}


def set_mcp(project: Path, name: str, enabled: bool) -> list[str]:
    """Turn a .mcp.json server on or off in the untracked settings.local.json of `project`.

    Turning one Studio server on turns the other off: two MCP plugins polling the same
    Studio block each other. Returns messages for the user.
    """
    if name not in {n for n, _, _ in MCP_SERVERS}:
        raise ValueError(f"unknown MCP server {name}")
    _, local_path = _settings_files(project)
    data = read_json(local_path, {}) or {}
    enabled_list = data.setdefault("enabledMcpjsonServers", [])
    disabled_list = data.setdefault("disabledMcpjsonServers", [])
    msgs: list[str] = []

    def turn(server: str, on: bool) -> None:
        if on:
            if server in disabled_list:
                disabled_list.remove(server)
            if server not in enabled_list:
                enabled_list.append(server)
        else:
            if server in enabled_list:
                enabled_list.remove(server)
            if server not in disabled_list:
                disabled_list.append(server)

    turn(name, enabled)
    msgs.append(f"{name}: {'encendido' if enabled else 'apagado'}")
    if enabled and name in STUDIO_SERVERS:
        other = next(s for s in STUDIO_SERVERS if s != name)
        if other not in disabled_list:
            turn(other, False)
            msgs.append(f"{other}: apagado (un solo servidor MCP de Studio a la vez)")
    write_json_atomic(local_path, data)
    msgs.append("Reinicia Claude Code para aplicar el cambio.")
    return msgs


# --------------------------------------------------------------------------- environment variables

def key_status(info: KeyInfo) -> str:
    """'configurada' / 'falta'. Values are never returned."""
    if info.name == "KAGGLE_API_TOKEN" and not user_env(info.name):
        if (Path.home() / ".kaggle" / "kaggle.json").exists():  # existence only, never read
            return "kaggle.json"
    return "configurada" if user_env(info.name) else "falta"


def can_set_env() -> bool:
    return SYSTEM == "Windows"


def set_user_env(name: str, value: str) -> None:
    """Persist a user environment variable (Windows registry, like setx without its 1024-char cut).

    The value never touches a file, a log or the screen.
    """
    if name not in KEY_NAMES and name != "ROBLOX_GAMES_HOME":
        raise ValueError(f"RoNavi no gestiona la variable {name}")
    if not can_set_env():
        raise OSError("Solo en Windows: en macOS/Linux añade un export en tu ~/.zshrc o ~/.bashrc")
    value = value.strip()
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
        if value:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        else:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
    if value:
        os.environ[name] = value
    else:
        os.environ.pop(name, None)
    _broadcast_env_change()


def path_contains(directory: Path) -> bool:
    value = user_env("Path") if SYSTEM == "Windows" else os.environ.get("PATH", "")
    parts = [p.strip().rstrip("\\/") for p in (value or "").split(os.pathsep) if p.strip()]
    target = os.path.normcase(str(directory).rstrip("\\/"))
    return any(os.path.normcase(os.path.expandvars(p)) == target for p in parts)


def ronavi_on_path(studio: Studio) -> bool:
    """Would a new terminal find this studio's `ronavi`?"""
    if SYSTEM == "Windows":
        return path_contains(studio.root)
    launcher = (studio.root / "ronavi.sh").resolve()
    hit = shutil.which("ronavi")
    if hit and Path(hit).resolve() == launcher:
        return True
    link = Path.home() / ".local" / "bin" / "ronavi"
    return link.is_symlink() and link.resolve() == launcher


def add_to_user_path(directory: Path) -> str:
    """Make `ronavi` available in new terminals. Windows: user PATH; elsewhere: ~/.local/bin link."""
    if SYSTEM == "Windows":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
            try:
                current, kind = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current, kind = "", winreg.REG_EXPAND_SZ
            parts = [p for p in str(current).split(";") if p]
            if any(os.path.normcase(os.path.expandvars(p).rstrip("\\/")) ==
                   os.path.normcase(str(directory).rstrip("\\/")) for p in parts):
                return "ya estaba en tu PATH"
            winreg.SetValueEx(key, "Path", 0, kind, ";".join([*parts, str(directory)]))
        _broadcast_env_change()
        return f"añadido {directory} a tu PATH (abre una terminal nueva)"
    link = Path.home() / ".local" / "bin" / "ronavi"
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        return f"{link} ya existe; no se tocó"
    link.symlink_to(directory / "ronavi.sh")
    return f"creado {link} → {directory / 'ronavi.sh'}"


def _broadcast_env_change() -> None:
    """Tell Explorer (and so new terminals) that the environment changed."""
    try:
        HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001A, 0x0002
        result = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(  # type: ignore[attr-defined]
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 3000, ctypes.byref(result))
    except Exception:
        pass


def export_hint(name: str) -> str:
    if SYSTEM == "Windows":
        return f'setx {name} "<valor>"'
    return f'export {name}="<valor>"   # en ~/.zshrc o ~/.bashrc'


# --------------------------------------------------------------------------- quotas

def quota_status(studio: Studio) -> str:
    script = studio.root / ".claude" / "skills" / "quota-guard" / "scripts" / "quota.py"
    if not script.exists():
        return "quota-guard no está en este estudio."
    try:
        res = subprocess.run([system_python(), str(script), "status"], cwd=studio.root, capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=60,
                             env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    except (OSError, subprocess.SubprocessError) as exc:
        return f"No se pudo leer el cupo: {exc}"
    return (res.stdout or res.stderr).rstrip() or "(sin datos)"


def figma_note() -> str:
    return "Figma se autentica dentro de Claude Code: /mcp → figma → Authenticate."


def dump(obj: object) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)
