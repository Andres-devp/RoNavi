"""Toolchain versions of the games (D21).

The roblox-code scaffold pins 2024 versions. RoNavi moves the tools that were proven
compatible with it in each game's aftman.toml / rokit.toml, never downgrades, and adds
luau-lsp (for the ronavi-luau plugin). SyphoDev's generator stays untouched.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

Progress = Callable[[str], None]

# Manifest tool name -> (owner/repo, version). Checked on 2026-10-29 by scaffolding a game,
# running `rokit install` and getting check.py green on all four gates.
PINS = {
    "rojo": ("rojo-rbx/rojo", "7.7.1"),
    "selene": ("Kampfkarren/selene", "0.32.0"),
    "stylua": ("JohnnyMorganz/StyLua", "2.6.0"),
    "luau-lsp": ("JohnnyMorganz/luau-lsp", "1.70.1"),
    "asphalt": ("jackTabsCode/asphalt", "2.0.2"),  # only moved where own-images already added it
}
# Lune stays where the scaffold puts it (0.8.9): from 0.9.0 on, require paths must start with
# "./", "../" or "@", and the scaffold's spec runner fails to load every spec (0.9.4, 0.10.5 and 0.11.1 tested).
ADD_IF_MISSING = ("luau-lsp",)
MANIFESTS = ("rokit.toml", "aftman.toml")
TOOL_RE = re.compile(r'^(?P<indent>\s*)(?P<name>[A-Za-z0-9_-]+)(?P<eq>\s*=\s*)"(?P<repo>[^"@]+)@(?P<ver>[^"]+)"'
                     r'(?P<rest>.*)$')
SECTION_RE = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*(#.*)?$")


def _noop(_: str) -> None:
    pass


def parse_version(text: str) -> tuple[int, ...] | None:
    parts = text.strip().lstrip("v").split(".")
    return tuple(int(p) for p in parts) if parts and all(p.isdigit() for p in parts) else None


def manifest_path(game_root: Path) -> Path | None:
    return next((game_root / m for m in MANIFESTS if (game_root / m).is_file()), None)


def upgraded_text(text: str) -> tuple[str, list[str], list[str]]:
    """(new manifest text, changes for people, tools added). Pure: no files, no processes."""
    lines = text.splitlines()
    changes: list[str] = []
    seen: set[str] = set()
    section, last_tool_line = None, None
    for i, line in enumerate(lines):
        sec = SECTION_RE.match(line)
        if sec:
            section = sec["name"].strip()
            continue
        m = TOOL_RE.match(line)
        if section != "tools" or not m:
            continue
        last_tool_line = i
        name = m["name"].lower()
        seen.add(name)
        pin = PINS.get(name)
        if not pin or m["repo"].lower() != pin[0].lower():
            continue
        current, wanted = parse_version(m["ver"]), parse_version(pin[1])
        if current is None or wanted is None or current >= wanted:
            continue
        lines[i] = f'{m["indent"]}{m["name"]}{m["eq"]}"{m["repo"]}@{pin[1]}"{m["rest"]}'
        changes.append(f"{m['name']} {m['ver']} → {pin[1]}")
    added = [t for t in ADD_IF_MISSING if t not in seen]
    if added and last_tool_line is not None:
        new = [f'{t} = "{PINS[t][0]}@{PINS[t][1]}"' for t in added]
        lines[last_tool_line + 1:last_tool_line + 1] = new
        changes += [f"{t} {PINS[t][1]} (nuevo)" for t in added]
    else:
        added = []  # no [tools] table to add to: leave the manifest alone
    end = "\n" if text.endswith("\n") or not text else ""
    return "\n".join(lines) + end, changes, added


def trust(tool_repo: str) -> bool:
    """Rokit refuses to install a tool the user has never trusted; luau-lsp is new to most machines."""
    rokit = shutil.which("rokit")
    if not rokit:
        return False
    try:
        res = subprocess.run([rokit, "trust", tool_repo], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return res.returncode == 0


def upgrade_toolchain(game_root: Path, progress: Progress = _noop) -> list[str]:
    """Move the game's pinned tools to PINS (never down) and add luau-lsp. Returns what changed.

    Writes only the game's own manifest. Run `rokit install` afterwards to download the tools.
    """
    path = manifest_path(game_root)
    if path is None:
        return []
    text = path.read_text(encoding="utf-8")
    new, changes, added = upgraded_text(text)
    if not changes:
        return []
    path.write_text(new, encoding="utf-8")
    for change in changes:
        progress(f"· {path.name}: {change}")
    for tool in added:
        if not trust(PINS[tool][0]):
            progress(f"! no se pudo marcar {PINS[tool][0]} como confiable: ejecuta `rokit trust {PINS[tool][0]}`")
    if any(c.lower().startswith("stylua") for c in changes):
        progress("  si check.py marca formato tras subir StyLua, ejecuta check.py --fix")
    return changes
