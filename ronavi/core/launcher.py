"""Open Claude Code (and other tools) in the right folder, never anywhere else."""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
from pathlib import Path

from ronavi.core.guard import GuardError, assert_git_isolated, is_within, same_path
from ronavi.core.paths import Studio
from ronavi.core.projects import Game, launch_env, sync_guard
from ronavi.core.templates import sanitize_prompt

SYSTEM = platform.system()


def claude_executable() -> str | None:
    """The real Claude Code binary. npm's claude.cmd shim is skipped: .cmd files re-parse arguments."""
    hit = shutil.which("claude")
    if not hit:
        for cand in (Path.home() / ".local" / "bin" / "claude.exe", Path.home() / ".local" / "bin" / "claude",
                     Path.home() / ".claude" / "local" / "claude"):
            if cand.exists():
                return str(cand)
        return None
    p = Path(hit)
    if p.suffix.lower() in (".cmd", ".bat", ".ps1", ""):
        exe = p.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        if SYSTEM == "Windows" and exe.exists():
            return str(exe)
        if SYSTEM == "Windows" and p.suffix == "":
            cmd = p.with_suffix(".cmd")
            return str(cmd) if cmd.exists() else hit
    return hit


def claude_command(studio: Studio, prompt: str | None = None, extra: list[str] | None = None) -> list[str]:
    exe = claude_executable()
    if not exe:
        raise GuardError("No se encuentra Claude Code (claude). Instálalo desde Herramientas.")
    cmd = [exe, "--add-dir", str(studio.root), *(extra or [])]
    if prompt:
        cmd.append(sanitize_prompt(prompt))
    return cmd


def prepare_game_launch(studio: Studio, game: Game) -> None:
    """Checks that run before Claude Code opens in a game."""
    if not is_within(game.root, studio.games_home) or not same_path(game.root.parent, studio.games_home):
        raise GuardError(f"{game.root} no está en la carpeta de juegos.")
    if not game.managed:
        raise GuardError(f"{game.slug} no está gestionado por RoNavi: adóptalo primero.")
    if game.has_git:
        assert_git_isolated(game.root)
    sync_guard(studio, game)


def run_here(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> int:
    """Run in this terminal (the TUI must be suspended by the caller)."""
    try:
        return subprocess.call(cmd, cwd=cwd, env=env)
    except OSError as exc:
        print(f"No se pudo ejecutar {cmd[0]}: {exc}")
        return 127


def open_window(cmd: list[str], cwd: Path, title: str, env: dict[str, str] | None = None) -> None:
    """Run `cmd` in a new terminal window that starts in `cwd`."""
    if SYSTEM == "Windows":
        # CREATE_NEW_CONSOLE (not `wt new-tab`): the process is ours, so it gets exactly this env;
        # Windows 11 still shows it in the default terminal app.
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(cmd, cwd=cwd, env=env, creationflags=flags)
        return
    line = f"cd {shlex.quote(str(cwd))} && " + " ".join(shlex.quote(c) for c in cmd)
    if SYSTEM == "Darwin":
        script = f'tell application "Terminal" to do script "{line.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}"'
        subprocess.Popen(["osascript", "-e", script, "-e", 'tell application "Terminal" to activate'], env=env)
        return
    for term in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm"):
        exe = shutil.which(term)
        if exe:
            args = [exe, "--", "bash", "-lc", line] if term == "gnome-terminal" else [exe, "-e", "bash", "-lc", line]
            subprocess.Popen(args, env=env)
            return
    raise GuardError("No se encontró un emulador de terminal para abrir una ventana nueva.")


def open_folder(path: Path) -> None:
    if SYSTEM == "Windows":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif SYSTEM == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def open_vscode(path: Path) -> None:
    code = shutil.which("code")
    if not code:
        raise GuardError("VS Code (code) no está en el PATH.")
    subprocess.Popen([code, str(path)], shell=False)


def game_env(studio: Studio, game: Game) -> dict[str, str]:
    return launch_env(studio, game)
