"""Command line. Without arguments it opens the TUI; the subcommands are for scripts and tests.

    ronavi                       interfaz (TUI)
    ronavi doctor [--json]       diagnóstico (scripts/doctor.py)
    ronavi list                  juegos
    ronavi new "Coin Dash" --genre obby [--desc "..."] [--no-git] [--no-commit] [--code] [--from-idea ID]
    ronavi open CoinDash [--window] [--prompt "..."]
    ronavi idea [--hint "..."] [--no-open] [--window]   investiga sin nombre ni género (work/ideas/)
    ronavi idea 2026-10-29-1530  reabre una idea
    ronavi ideas                 ideas guardadas
    ronavi sync-guards           reinstala el guardián de todos los juegos
    ronavi update [--check]      pasa a la última versión (tag) o hace pull de tu rama
    ronavi path [add]            ¿se puede escribir "ronavi" en cualquier terminal? add lo arregla
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


def _studio_root_or_none():
    from ronavi.core.paths import StudioNotFound, find_studio_root
    try:
        return find_studio_root()
    except StudioNotFound:
        return None


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
    from ronavi.core.ideas import find_idea
    from ronavi.core.projects import create_game
    studio = _studio()
    try:
        idea = find_idea(studio, a.from_idea) if a.from_idea else None
        game = create_game(studio, a.name, a.genre, a.desc or "", init_git=not a.no_git,
                           commit=not (a.no_git or a.no_commit), scaffold=a.code,
                           from_idea=idea.root if idea else None, progress=print)
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


def cmd_idea(a: argparse.Namespace) -> int:
    from ronavi.core import templates as T
    from ronavi.core.guard import GuardError
    from ronavi.core.ideas import create_idea, find_idea, idea_env, prepare_idea_launch
    from ronavi.core.launcher import claude_command, open_window, run_here
    studio = _studio()
    try:
        if a.id:
            idea = find_idea(studio, a.id)
            prompt = None if idea.has_notes else T.idea_prompt(idea.hint)
        else:
            idea = create_idea(studio, a.hint or "")
            prompt = T.idea_prompt(idea.hint)
            print(idea.root)
        if a.no_open:
            return 0
        prepare_idea_launch(studio, idea)
        cmd = claude_command(studio, prompt)
    except GuardError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    env = idea_env(studio, idea)
    if a.window:
        open_window(cmd, idea.root, f"RoNavi · idea {idea.id}", env)
        return 0
    return run_here(cmd, idea.root, env)


def cmd_ideas(_: argparse.Namespace) -> int:
    from ronavi.core.ideas import discover_ideas
    studio = _studio()
    ideas = discover_ideas(studio)
    print(f"{studio.ideas_home}  ({len(ideas)} idea{'s' if len(ideas) != 1 else ''})")
    for i in ideas:
        state = f"→ {i.converted_to}" if i.converted_to else ("IDEA.md" if i.has_notes else "sin investigar")
        print(f"  {i.id:<20} {state:<20} {i.title}")
    return 0


def cmd_update(a: argparse.Namespace) -> int:
    from ronavi.core.updates import UpdateError, check_for_update, update
    studio = _studio()
    try:
        if a.check:
            newer = check_for_update(studio, force=True)
            print(f"Hay una versión nueva: {newer}" if newer else f"Estás al día ({__version__}).")
            return 0
        print(update(studio, progress=print))
    except UpdateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_path(a: argparse.Namespace) -> int:
    from ronavi.core.integrations import add_to_user_path, ronavi_on_path
    studio = _studio()
    if a.action == "add":
        print(add_to_user_path(studio.root))
        return 0
    on = ronavi_on_path(studio)
    print("'ronavi' ya funciona en cualquier terminal nueva." if on else
          "'ronavi' no está en tu PATH: ejecuta  ronavi path add")
    return 0 if on else 1


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
    print(f"ideas        {studio.ideas_home}")
    print(f"config       {studio.config_file}")
    print(f"claude       {claude_executable() or '(no encontrado)'}")
    print(f"python       {sys.executable}")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="ronavi", description=f"{APP_NAME} {__version__}",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--version", action="store_true", help="muestra la versión y sale")
    sub = ap.add_subparsers(dest="command")
    sub.add_parser("list", help="lista los juegos").set_defaults(fn=cmd_list)
    p = sub.add_parser("new", help="crea un juego")
    p.add_argument("name")
    p.add_argument("--genre", default="other")
    p.add_argument("--desc", default="")
    p.add_argument("--no-git", action="store_true")
    p.add_argument("--no-commit", action="store_true")
    p.add_argument("--code", action="store_true", help="genera el proyecto con roblox-code (new_project.py)")
    p.add_argument("--from-idea", metavar="ID", help="copia la investigación de una idea a docs/research/")
    p.set_defaults(fn=cmd_new)
    p = sub.add_parser("open", help="abre Claude Code en un juego")
    p.add_argument("name")
    p.add_argument("--window", action="store_true")
    p.add_argument("--prompt")
    p.set_defaults(fn=cmd_open)
    p = sub.add_parser("idea", help="investiga una idea sin crear un juego (sin nombre ni género)")
    p.add_argument("id", nargs="?", help="reabre esta idea en vez de crear otra")
    p.add_argument("--hint", default="", help="punto de partida opcional")
    p.add_argument("--no-open", action="store_true", help="solo crea la carpeta, sin abrir Claude Code")
    p.add_argument("--window", action="store_true")
    p.set_defaults(fn=cmd_idea)
    sub.add_parser("ideas", help="lista las ideas guardadas").set_defaults(fn=cmd_ideas)
    p = sub.add_parser("update", help="actualiza RoNavi Studio (git)")
    p.add_argument("--check", action="store_true", help="solo comprueba si hay una versión nueva")
    p.set_defaults(fn=cmd_update)
    p = sub.add_parser("path", help="'ronavi' en cualquier terminal")
    p.add_argument("action", nargs="?", choices=["add"])
    p.set_defaults(fn=cmd_path)
    sub.add_parser("sync-guards", help="reinstala el guardián de todos los juegos").set_defaults(fn=cmd_sync)
    p = sub.add_parser("doctor", help="diagnóstico de la máquina")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_doctor)
    sub.add_parser("paths", help="rutas que usa RoNavi").set_defaults(fn=cmd_paths)
    a = ap.parse_args(argv)
    if a.version:
        from ronavi.core.updates import describe
        rev = describe(_studio_root_or_none())
        print(f"{APP_NAME} {__version__}" + (f" ({rev})" if rev else ""))
        return 0
    if not a.command:
        from ronavi.ui.app import run_tui
        return run_tui()
    return a.fn(a)
