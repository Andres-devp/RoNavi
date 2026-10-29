#!/usr/bin/env python3
"""Start luau-lsp for Claude Code inside a game: Roblox types, API docs and a live sourcemap.

Claude Code runs this through the `ronavi-luau` plugin that RoNavi Studio generates in
.ronavi/plugins/. It keeps the Roblox definition files in .ronavi/cache/luau-lsp/ (refreshed
weekly; a stale copy is used when offline), writes sourcemap.json once so requires resolve,
then hands stdin/stdout to luau-lsp. It leaves no process behind.

Nothing but the language server may write to stdout: everything else goes to stderr.
Standard library only.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[2]  # <studio>/ronavi/assets/this.py
CACHE = STUDIO / ".ronavi" / "cache" / "luau-lsp"
# Same files and security level as the luau-lsp VS Code extension.
DEFINITIONS_URL = "https://luau-lsp.pages.dev/type-definitions/globalTypes.PluginSecurity.d.luau"
DOCS_URL = "https://luau-lsp.pages.dev/api-docs/en-us.json"
MAX_AGE = 7 * 24 * 3600
USER_AGENT = "ronavi-studio-luau-lsp/1.0 (+https://github.com/JohnnyMorganz/luau-lsp)"
SETTINGS = {  # dotted keys, as luau-lsp's --settings expects (VS Code setting names)
    "luau-lsp.platform.type": "roblox",
    "luau-lsp.sourcemap.enabled": True,
    "luau-lsp.sourcemap.autogenerate": False,
}


def log(msg: str) -> None:
    print(f"ronavi-luau: {msg}", file=sys.stderr, flush=True)


def cached(url: str, name: str) -> Path | None:
    """A local copy of `url`, downloaded when missing or older than MAX_AGE. None if never fetched."""
    dest = CACHE / name
    fresh = dest.exists() and time.time() - dest.stat().st_mtime < MAX_AGE
    if not fresh:
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # the default UA gets a 403
            with urllib.request.urlopen(req, timeout=20) as res:  # noqa: S310 (fixed https URL)
                data = res.read()
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, dest)
        except OSError as exc:
            log(f"no se pudo descargar {url} ({exc}); se usa la copia local si existe")
    return dest if dest.exists() else None


def settings_file() -> Path:
    """Defaults the VS Code extension would send: Roblox platform, sourcemap read (we generate it)."""
    path = CACHE / "settings.json"
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(SETTINGS, indent=2), encoding="utf-8")
    return path


def refresh_sourcemap(cwd: Path) -> None:
    """One-shot `rojo sourcemap`, never --watch: a watcher outlives the server when Claude Code kills it
    (and on Windows the rokit shim's child survives terminate()). The post-edit hook refreshes it
    again when Claude creates a .luau file."""
    rojo = shutil.which("rojo")
    if not rojo or not (cwd / "default.project.json").exists():
        return
    try:
        res = subprocess.run([rojo, "sourcemap", "default.project.json", "--output", "sourcemap.json",
                              "--include-non-scripts"], cwd=cwd, stdin=subprocess.DEVNULL,
                             capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        log(f"rojo sourcemap falló ({exc}); los require entre módulos no se resolverán")
        return
    if res.returncode != 0:
        log("rojo sourcemap falló; los require entre módulos no se resolverán")


def main() -> int:
    exe = shutil.which("luau-lsp")
    if not exe:
        log("no se encuentra luau-lsp: en el juego, ejecuta `rokit add JohnnyMorganz/luau-lsp` y `rokit install`")
        return 1
    args = [exe, "lsp", f"--settings={settings_file()}"]
    definitions = cached(DEFINITIONS_URL, "globalTypes.PluginSecurity.d.luau")
    if definitions:
        args.append(f"--definitions:@roblox={definitions}")
    docs = cached(DOCS_URL, "en-us.json")
    if docs:
        args.append(f"--docs={docs}")
    refresh_sourcemap(Path.cwd())
    try:
        return subprocess.call(args)  # inherits stdin/stdout: the LSP channel
    except OSError as exc:
        log(f"luau-lsp no arrancó ({exc})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
