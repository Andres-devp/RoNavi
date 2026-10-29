"""Ideas: research a game before it has a name, a genre or a folder in the games home.

An idea is a folder in <studio>/work/ideas/<id> (git-ignored). It has no git and no Rojo
project, only Claude Code's notes, and the same guard as a game: Claude can write inside
the idea and nowhere in the studio or the games. When the user picks a concept, the idea
becomes a game (`create_game(from_idea=...)`) and its notes are copied to docs/research/.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ronavi import __version__
from ronavi.core import templates as T
from ronavi.core.guard import GameScope, GuardError, is_within, real
from ronavi.core.paths import Studio, read_json
from ronavi.core.projects import (GUARD_REL, RESEARCH_REL, _write_json, game_settings, install_guard,
                                  _read_obj)

IDEA_META = ".ronavi/idea.json"
NOTES = "IDEA.md"
# Never copied into a game: RoNavi's own files for the idea, and anything hidden.
SKIP_TOP = {".claude", ".ronavi", ".git", "CLAUDE.md"}
MAX_COPY_BYTES = 5 * 1024 * 1024


@dataclass
class Idea:
    root: Path
    id: str
    hint: str = ""
    created: str | None = None
    converted_to: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def has_notes(self) -> bool:
        return (self.root / NOTES).is_file()

    @property
    def title(self) -> str:
        """The first heading of IDEA.md, else the hint, else a placeholder."""
        if self.has_notes:
            try:
                for line in (self.root / NOTES).read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("# ") and line[2:].strip():
                        return line[2:].strip()[:60]
            except OSError:
                pass
        return self.hint[:60] if self.hint else "(sin investigar)"

    @property
    def modified(self) -> float:
        try:
            return max(p.stat().st_mtime for p in (self.root, self.root / NOTES) if p.exists())
        except (OSError, ValueError):
            return 0.0


def scope_for_idea(studio: Studio, root: Path) -> GameScope:
    return GameScope(root, studio.root, studio.games_home, container=studio.ideas_home)


def load_idea(studio: Studio, root: Path) -> Idea:
    root = Path(root)
    if not is_within(root, studio.ideas_home) or not (root / IDEA_META).is_file():
        raise GuardError(f"{root} no es una idea de RoNavi.")
    meta = read_json(root / IDEA_META, {})
    meta = meta if isinstance(meta, dict) else {}
    return Idea(root=root, id=root.name, hint=str(meta.get("hint") or ""), created=meta.get("created"),
                converted_to=meta.get("converted_to"), extra=meta)


def discover_ideas(studio: Studio) -> list[Idea]:
    """Newest first."""
    home = studio.ideas_home
    if not home.is_dir():
        return []
    ideas = []
    for child in home.iterdir():
        if child.is_dir() and is_within(child, home) and (child / IDEA_META).is_file():
            ideas.append(load_idea(studio, child))
    return sorted(ideas, key=lambda i: i.id, reverse=True)


def find_idea(studio: Studio, idea_id: str) -> Idea:
    for idea in discover_ideas(studio):
        if idea.id.lower() == idea_id.strip().lower():
            return idea
    raise GuardError(f"No existe la idea '{idea_id}' en {studio.ideas_home}.")


def new_idea_id(home: Path, now: datetime | None = None) -> str:
    base = (now or datetime.now()).strftime("%Y-%m-%d-%H%M")
    taken = {p.name.lower() for p in home.iterdir()} if home.is_dir() else set()
    if base.lower() not in taken:
        return base
    n = 2
    while f"{base}-{n}".lower() in taken:
        n += 1
    return f"{base}-{n}"


def create_idea(studio: Studio, hint: str = "") -> Idea:
    """A new idea folder with its CLAUDE.md, settings and guard. No git, no game."""
    hint = " ".join(hint.split())[:200]
    home = studio.ideas_home
    home.mkdir(parents=True, exist_ok=True)
    root = home / new_idea_id(home)
    scope = scope_for_idea(studio, root)
    root.mkdir()
    _write_json(scope, IDEA_META, {
        "hint": hint,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ronavi_version": __version__,
    })
    scope.write_text("CLAUDE.md", T.idea_claude_md(root.name, hint))
    _write_json(scope, ".claude/settings.json", game_settings(studio, None))
    sync_idea_guard(studio, root)
    return load_idea(studio, root)


def sync_idea_guard(studio: Studio, root: Path) -> None:
    """Writes are allowed in this idea and quota-guard's ledger; a game's guard allows all of work/."""
    scope = scope_for_idea(studio, root)
    install_guard(studio, scope, allowed=[studio.root / "work" / "quota-ledger.json"])


def prepare_idea_launch(studio: Studio, idea: Idea) -> None:
    if not (idea.root / GUARD_REL).exists() or not is_within(idea.root, studio.ideas_home):
        raise GuardError(f"{idea.root} no es una idea de RoNavi.")
    sync_idea_guard(studio, idea.root)


def idea_env(studio: Studio, idea: Idea) -> dict[str, str]:
    env = dict(os.environ)
    env["ROBLOX_GAMES_HOME"] = str(studio.games_home)
    env["RONAVI_STUDIO"] = str(studio.root)
    env["RONAVI_IDEA"] = str(idea.root)
    return env


def research_files(idea: Idea) -> list[Path]:
    """The idea's notes, relative to it: no RoNavi files, nothing hidden, nothing that leaves the idea."""
    root = real(idea.root)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not (rel_dir == Path(".") and d in SKIP_TOP)]
        for name in filenames:
            rel = rel_dir / name
            if name.startswith(".") or (rel_dir == Path(".") and name in SKIP_TOP):
                continue
            path = root / rel
            if not is_within(path, root) or path.stat().st_size > MAX_COPY_BYTES:
                continue
            out.append(rel)
    return sorted(out)


def copy_research(idea: Idea, game_scope: GameScope) -> int:
    """Copy the idea's notes into <game>/docs/research/, through the game's scope."""
    files = research_files(idea)
    for rel in files:
        game_scope.copy_file(idea.root / rel, Path(RESEARCH_REL) / rel)
    return len(files)


def mark_converted(studio: Studio, idea: Idea, slug: str) -> None:
    scope = scope_for_idea(studio, idea.root)
    meta = _read_obj(scope.check(IDEA_META))
    meta["converted_to"] = slug
    _write_json(scope, IDEA_META, meta)
