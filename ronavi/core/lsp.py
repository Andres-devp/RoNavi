"""The `ronavi-luau` plugin: luau-lsp inside Claude Code, so Claude sees type errors after each edit.

RoNavi generates a one-plugin marketplace in <studio>/.ronavi/plugins/ (machine-specific: the
interpreter path goes into .lsp.json), each game's settings.local.json registers it as a
`directory` marketplace and enables the plugin, and the first launch of a game installs it there
with `claude plugin install --scope local`. Claude Code reads the plugin in place, so later
changes need no reinstall. The server itself is ronavi/assets/luau_lsp_server.py.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from ronavi import __version__
from ronavi.core.paths import Studio

MARKETPLACE = "ronavi-studio"
PLUGIN = "ronavi-luau"
PLUGIN_ID = f"{PLUGIN}@{MARKETPLACE}"
SERVER_ASSET = Path(__file__).resolve().parent.parent / "assets" / "luau_lsp_server.py"


def plugins_root(studio: Studio) -> Path:
    return studio.root / ".ronavi" / "plugins"


def lsp_command(python: str) -> str:
    """`command` in .lsp.json may not contain spaces unless it starts with '/'."""
    if " " not in python or python.startswith("/"):
        return python
    return "python" if os.name == "nt" else "python3"


def plugin_files(python: str) -> dict[str, dict]:
    """Relative path under plugins_root -> JSON content."""
    return {
        ".claude-plugin/marketplace.json": {
            "name": MARKETPLACE,
            "owner": {"name": "RoNavi Studio"},
            "description": "Plugins locales de RoNavi Studio (generados en cada sincronización).",
            "plugins": [{"name": PLUGIN, "source": f"./{PLUGIN}",
                         "description": "luau-lsp con tipos de Roblox: diagnósticos tras cada edición."}],
        },
        f"{PLUGIN}/.claude-plugin/plugin.json": {
            "name": PLUGIN,
            "displayName": "RoNavi Luau",
            "description": "luau-lsp con tipos de Roblox, documentación de la API y sourcemap de Rojo.",
            "version": __version__,
            "author": {"name": "RoNavi Studio"},
            "license": "MIT",
            "metadata": {"generatedBy": f"RoNavi Studio {__version__}"},
        },
        f"{PLUGIN}/.lsp.json": {
            "luau": {
                "command": lsp_command(python),
                "args": [str(SERVER_ASSET)],
                "extensionToLanguage": {".luau": "luau", ".lua": "luau"},
                "startupTimeout": 120000,  # first start downloads ~8 MB of Roblox definitions and docs
                "maxRestarts": 2,
            },
        },
    }


def write_plugin(studio: Studio, python: str) -> Path:
    """(Re)write the marketplace, touching only files whose content changed. Returns its root."""
    root = plugins_root(studio)
    for rel, data in plugin_files(python).items():
        path = root / rel
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        try:
            if path.read_text(encoding="utf-8") == text:
                continue
        except OSError:
            pass
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def settings_entries(studio: Studio) -> tuple[dict, dict]:
    """(extraKnownMarketplaces entry, enabledPlugins entry) for a game's settings.local.json."""
    source = {"source": {"source": "directory", "path": str(plugins_root(studio))}}
    return {MARKETPLACE: source}, {PLUGIN_ID: True}


def installed_for(game_root: Path) -> bool:
    """Best effort: does Claude Code's plugin registry list the plugin for this game?

    `enabledPlugins` alone does not install a plugin; `claude plugin install --scope local`
    does, once per game. The registry is Claude Code's own file, so any surprise means "no".
    """
    registry = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    try:
        entries = json.loads(registry.read_text(encoding="utf-8")).get("plugins", {}).get(PLUGIN_ID, [])
        target = os.path.normcase(os.path.realpath(game_root))
        return any(os.path.normcase(os.path.realpath(e.get("projectPath", ""))) == target
                   for e in entries if e.get("scope") == "local")
    except (OSError, ValueError, AttributeError, TypeError):
        return False


def ensure_installed(studio: Studio, game_root: Path, claude: str | None, python: str) -> str | None:
    """Install the plugin for one game if needed. Returns a problem to show, or None. Never raises."""
    write_plugin(studio, python)
    if installed_for(game_root):
        return None
    if not claude:
        return "no se encuentra Claude Code: el plugin de luau-lsp se instalará la próxima vez"
    cmd = [claude, "plugin", "install", PLUGIN, "--marketplace", str(plugins_root(studio)), "--scope", "local"]
    try:
        res = subprocess.run(cmd, cwd=game_root, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"no se pudo instalar el plugin de luau-lsp ({exc})"
    if res.returncode != 0:
        return "no se pudo instalar el plugin de luau-lsp: " + (res.stderr or res.stdout).strip()[-300:]
    return None
