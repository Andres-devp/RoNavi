#!/usr/bin/env python3
"""RoNavi Studio post-edit check: a Claude Code PostToolUse hook installed in every game.

After Claude writes or edits a .luau/.lua file inside the game, it formats that file with
StyLua and lints it with Selene, both from the game's own toolchain (rokit/aftman). Selene
findings go back to Claude so it fixes them before `check.py`; formatting is silent.

Never blocks work: a missing tool, a timeout or an internal error just lets the edit stand.
Standard library only: it is copied into each game and must run anywhere.
Managed by RoNavi Studio: changes are overwritten on the next sync.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
GAME_ROOT = HERE.parent.parent.parent  # <game>/.claude/hooks/this.py
LUAU_SUFFIXES = {".luau", ".lua"}
TIMEOUT = 30
MAX_REPORT = 3000  # characters of Selene output handed back to Claude


def _key(path: Path) -> str:
    return os.path.normcase(os.path.realpath(str(path))).rstrip("\\/")


def is_within(child: Path, parent: Path) -> bool:
    c, p = _key(child), _key(parent)
    return c == p or c.startswith(p + os.sep)


def edited_file(event: dict) -> Path | None:
    """The .luau/.lua file this tool call wrote, when it is inside the game."""
    raw = (event.get("tool_input") or {}).get("file_path")
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(event.get("cwd") or GAME_ROOT) / path
    if path.suffix.lower() not in LUAU_SUFFIXES or not path.is_file() or not is_within(path, GAME_ROOT):
        return None
    return path


def run(tool: str, args: list[str]) -> subprocess.CompletedProcess | None:
    exe = shutil.which(tool)
    if not exe:
        return None
    try:
        return subprocess.run([exe, *args], cwd=GAME_ROOT, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None


def refresh_sourcemap(event: dict) -> None:
    """A new module must appear in sourcemap.json for luau-lsp to resolve requires to it."""
    if event.get("tool_name") == "Write" and (GAME_ROOT / "default.project.json").exists():
        run("rojo", ["sourcemap", "default.project.json", "--output", "sourcemap.json", "--include-non-scripts"])


def check(path: Path) -> str | None:
    """Format, then lint. Returns the Selene report when it found something."""
    run("stylua", [str(path)])
    res = run("selene", ["--display-style", "quiet", str(path)])
    if res is None or res.returncode == 0:
        return None
    out = (res.stdout + res.stderr).strip()
    if not out or "Failed to find tool" in out:  # rokit shim outside a manifest: not this file's fault
        return None
    return out[:MAX_REPORT]


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    path = edited_file(event)
    if path is None:
        return 0
    refresh_sourcemap(event)
    report = check(path)
    if report:
        rel = path.relative_to(GAME_ROOT) if is_within(path, GAME_ROOT) else path
        print(json.dumps({
            "decision": "block",
            "reason": f"Selene encontró problemas en {rel.as_posix()}; corrígelos antes de seguir:\n{report}",
        }))  # ASCII escapes: the console code page cannot garble the accents
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a broken check must never break the session
        print(f"ronavi_luau_check: error interno, se omite la revisión ({exc})", file=sys.stderr)
        sys.exit(0)
