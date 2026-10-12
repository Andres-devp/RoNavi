"""Path and name guards. Every write RoNavi makes to a game goes through `GameScope`.

The rules:

* A game is a direct child of the games home, never the studio root, never the games
  home itself, and never an ancestor of the studio.
* A write is allowed only when the path, with symlinks and junctions resolved, stays
  inside the game that the operation was opened for.
* Git commands only run in a game whose `git rev-parse --show-toplevel` is the game
  itself: without its own `.git`, git would walk up and act on the studio repository.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 _-]{1,39}$")
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
                    *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class GuardError(RuntimeError):
    """An operation was refused to protect the studio or another game."""


# --------------------------------------------------------------------------- names

def slugify(name: str) -> str:
    """'coin dash' -> 'CoinDash', 'obby_rush-2' -> 'ObbyRush2'."""
    parts = [p for p in re.split(r"[\s_-]+", name.strip()) if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


def validate_name(name: str) -> tuple[str, str]:
    """Return (display name, folder name) or raise GuardError with a message for the user."""
    display = " ".join(name.split())
    if not NAME_RE.match(display):
        raise GuardError("El nombre debe tener 2–40 caracteres, empezar por una letra y usar solo "
                         "letras sin acentos, números, espacios, '-' o '_'.")
    slug = slugify(display)
    if len(slug) < 2:
        raise GuardError("El nombre es demasiado corto.")
    if slug.upper() in WINDOWS_RESERVED:
        raise GuardError(f"'{slug}' es un nombre reservado de Windows.")
    return display, slug


# --------------------------------------------------------------------------- paths

def real(path: Path | str) -> Path:
    """Absolute path with symlinks and Windows junctions resolved (the tail may not exist)."""
    return Path(os.path.realpath(os.path.expanduser(str(path))))


def _key(path: Path) -> str:
    return os.path.normcase(str(real(path))).rstrip("\\/")


def same_path(a: Path | str, b: Path | str) -> bool:
    return _key(Path(a)) == _key(Path(b))


def is_within(child: Path | str, parent: Path | str) -> bool:
    """True when `child` is `parent` or below it, after resolving links, case-insensitive on Windows."""
    c, p = _key(Path(child)), _key(Path(parent))
    return c == p or c.startswith(p + os.sep)


class GameScope:
    """The only door through which RoNavi writes inside a game."""

    def __init__(self, game_root: Path, studio_root: Path, games_home: Path):
        self.root = real(game_root)
        self.studio_root = real(studio_root)
        self.games_home = real(games_home)
        if same_path(self.games_home, self.studio_root) or is_within(self.studio_root, self.games_home):
            raise GuardError(f"La carpeta de juegos ({self.games_home}) no puede ser ni contener el estudio.")
        if not same_path(self.root.parent, self.games_home):
            raise GuardError(f"{self.root} no está directamente dentro de la carpeta de juegos {self.games_home}.")
        if is_within(self.studio_root, self.root):
            raise GuardError(f"{self.root} contiene el estudio: operación rechazada.")

    def check(self, path: Path | str) -> Path:
        """Return the resolved absolute path, or raise if it escapes the game."""
        p = Path(path)
        target = real(p if p.is_absolute() else self.root / p)
        if not is_within(target, self.root):
            raise GuardError(f"Escritura rechazada: {target} está fuera del juego {self.root.name}.")
        return target

    def mkdir(self, rel: str | Path) -> Path:
        target = self.check(rel)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def write_text(self, rel: str | Path, text: str) -> Path:
        target = self.check(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
        return target

    def copy_file(self, src: Path, rel: str | Path) -> Path:
        target = self.check(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        return target


# --------------------------------------------------------------------------- git

def git_toplevel(path: Path) -> Path | None:
    try:
        res = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path, capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    out = res.stdout.strip()
    return Path(out) if res.returncode == 0 and out else None


def assert_git_isolated(game_root: Path) -> None:
    """Refuse git work in a game that does not own its repository."""
    top = git_toplevel(game_root)
    if top is None:
        raise GuardError(f"{game_root.name} no tiene repositorio git propio (falta {game_root / '.git'}).")
    if not same_path(top, game_root):
        raise GuardError(f"git en {game_root.name} actuaría sobre otro repositorio ({top}): operación rechazada.")
