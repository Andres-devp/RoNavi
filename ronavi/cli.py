"""Command line. Without arguments it opens the TUI; the subcommands are for scripts and tests.

    ronavi                       interfaz (TUI)
    ronavi doctor [--json]       diagnóstico (scripts/doctor.py)
    ronavi list                  juegos
    ronavi new "Coin Dash" --genre obby [--desc "..."] [--no-git] [--no-commit] [--code]
    ronavi open CoinDash [--window] [--prompt "..."]
    ronavi sync-guards           reinstala el guardián de todos los juegos
    ronavi paths                 rutas que usa RoNavi
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from ronavi import APP_NAME, __version__


def _studio():
    from ronavi.core.paths import Studio
    return Studio.load()


def cmd_list(_: argparse.Namespace) -> int:
    from ronavi.core.projects import discover
    studio = _studio()
    games = discover(studio)
    print(f"{studio.games_home}  ({len(games)} juego{'s' if len(games) != 1 else ''})")
    for g in games:
        state = "gestionado" if g.managed else "sin gestionar"
        print(f"  {g.slug:<24} {g.genre:<14} {g.stage:<8} {state:<14} guardián: "
              f"{'sí' if g.guard_installed else 'no'}")
    return 0


def cmd_new(a: argparse.Namespace) -> int:
    from ronavi.core.guard import GuardError
    from ronavi.core.projects import create_game
    try:
        game = create_game(_studio(), a.name, a.genre, a.desc or "", init_git=not a.no_git,
                           commit=not (a.no_git or a.no_commit), scaffold=a.code, progress=print)
    except GuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(game.root)
    return 0


def cmd_open(a: argparse.Namespace) -> int:
    from ronavi.core.guard import GuardError
    from ronavi.core.launcher import claude_command, open_window, prepare_game_launch, run_here
    from ronavi.core.projects import find_game, launch_env
    studio = _studio()
    try:
        game = find_game(studio, a.name)
        prepare_game_launch(studio, game)
        cmd = claude_command(studio, a.prompt)
    except GuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    env = launch_env(studio, game)
    if a.window:
        open_window(cmd, game.root, f"RoNavi · {game.name}", env)
        return 0
    return run_here(cmd, game.root, env)


def cmd_sync(_: argparse.Namespace) -> int:
    from ronavi.core.projects import sync_all_guards
    problems = sync_all_guards(_studio(), print)
    for p in problems:
        print("! " + p, file=sys.stderr)
    return 1 if problems else 0


def cmd_doctor(a: argparse.Namespace) -> int:
    studio = _studio()
    from ronavi.core.environment import system_python
    return subprocess.call([system_python(), str(studio.root / "scripts" / "doctor.py"),
                            *(["--json"] if a.json else [])])


def cmd_paths(_: argparse.Namespace) -> int:
    from ronavi.core.launcher import claude_executable
    studio = _studio()
    print(f"estudio      {studio.root}")
    print(f"juegos       {studio.games_home}")
    print(f"config       {studio.config_file}")
    print(f"claude       {claude_executable() or '(no encontrado)'}")
    print(f"python       {sys.executable}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="ronavi", description=f"{APP_NAME} {__version__}",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = ap.add_subparsers(dest="command")
    sub.add_parser("list", help="lista los juegos").set_defaults(fn=cmd_list)
    p = sub.add_parser("new", help="crea un juego")
    p.add_argument("name")
    p.add_argument("--genre", default="other")
    p.add_argument("--desc", default="")
    p.add_argument("--no-git", action="store_true")
    p.add_argument("--no-commit", action="store_true")
    p.add_argument("--code", action="store_true", help="genera el proyecto con roblox-code (new_project.py)")
    p.set_defaults(fn=cmd_new)
    p = sub.add_parser("open", help="abre Claude Code en un juego")
    p.add_argument("name")
    p.add_argument("--window", action="store_true")
    p.add_argument("--prompt")
    p.set_defaults(fn=cmd_open)
    sub.add_parser("sync-guards", help="reinstala el guardián de todos los juegos").set_defaults(fn=cmd_sync)
    p = sub.add_parser("doctor", help="diagnóstico de la máquina")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_doctor)
    sub.add_parser("paths", help="rutas que usa RoNavi").set_defaults(fn=cmd_paths)
    a = ap.parse_args(argv)
    if not a.command:
        from ronavi.ui.app import run_tui
        return run_tui()
    return a.fn(a)
