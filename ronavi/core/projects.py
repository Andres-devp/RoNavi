"""Games: discover, create, adopt and keep their guards in sync.

A game is a folder directly inside the games home. RoNavi manages the ones that have
`.ronavi/project.json`; other Rojo projects or git repos there are listed as
"sin gestionar" and can be adopted (RoNavi adds its files, never removes anything).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ronavi import __version__
from ronavi.core import templates as T
from ronavi.core.guard import GameScope, GuardError, assert_git_isolated, is_within, real, validate_name
from ronavi.core.paths import GAME_META_DIR, Studio, read_json

Progress = Callable[[str], None]

GUARD_ASSET = Path(__file__).resolve().parent.parent / "assets" / "ronavi_guard.py"
GUARD_REL = ".claude/hooks/ronavi_guard.py"
GUARD_CONFIG_REL = ".claude/ronavi-guard.json"
HOOK_MATCHER = "Write|Edit|MultiEdit|NotebookEdit|Bash|PowerShell"
OPTIONAL_MCP_SERVERS = ["blender-ahujasid", "robloxstudio-runtime"]
# Studio-only allow rules that make no sense inside a game.
STUDIO_ONLY_RULE_MARKERS = ("scripts/doctor.py",)
GAME_MARKERS = ("default.project.json", ".git", "HANDOFF.md", "aftman.toml", "rokit.toml")
RESEARCH_REL = "docs/research"  # where a game keeps the research of the idea it came from


def _noop(_: str) -> None:
    pass


@dataclass
class Game:
    root: Path
    name: str
    slug: str
    genre: str = "other"
    description: str = ""
    created: str | None = None
    managed: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def has_git(self) -> bool:
        return (self.root / ".git").exists()

    @property
    def has_code(self) -> bool:
        return (self.root / "default.project.json").exists()

    @property
    def has_handoff(self) -> bool:
        return (self.root / "HANDOFF.md").exists()

    @property
    def guard_installed(self) -> bool:
        return (self.root / GUARD_REL).exists() and (self.root / ".claude" / "settings.local.json").exists()

    @property
    def modified(self) -> float:
        try:
            return max((p.stat().st_mtime for p in (self.root, self.root / "HANDOFF.md",
                                                     self.root / "src") if p.exists()), default=0.0)
        except OSError:
            return 0.0

    @property
    def stage(self) -> str:
        if self.has_code:
            return "código"
        if self.has_handoff:
            return "plan"
        return "nuevo"

    def git_summary(self) -> str:
        """'limpio', 'N cambios', 'sin git' or 'git ajeno' (never runs git outside the game)."""
        if not self.has_git:
            return "sin git"
        try:
            assert_git_isolated(self.root)
        except GuardError:
            return "git ajeno"
        res = subprocess.run(["git", "status", "--porcelain"], cwd=self.root, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=20)
        if res.returncode != 0:
            return "git con error"
        n = len([line for line in res.stdout.splitlines() if line.strip()])
        return "limpio" if n == 0 else f"{n} cambio{'s' if n != 1 else ''}"


# --------------------------------------------------------------------------- discovery

def load_game(root: Path) -> Game:
    meta = read_json(root / GAME_META_DIR / "project.json", None)
    if isinstance(meta, dict):
        return Game(root=root, name=str(meta.get("name") or root.name), slug=root.name,
                    genre=str(meta.get("genre") or "other"), description=str(meta.get("description") or ""),
                    created=meta.get("created"), managed=True, extra=meta)
    return Game(root=root, name=root.name, slug=root.name, managed=False)


def discover(studio: Studio) -> list[Game]:
    home = studio.games_home
    if not home.is_dir():
        return []
    games = []
    for child in sorted(home.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        if not is_within(child, home):  # a link that leaves the games home is not a game here
            continue
        game = load_game(child)
        if game.managed or any((child / m).exists() for m in GAME_MARKERS):
            games.append(game)
    return games


def find_game(studio: Studio, name: str) -> Game:
    for g in discover(studio):
        if name.lower() in (g.slug.lower(), g.name.lower()):
            return g
    raise GuardError(f"No existe el juego '{name}' en {studio.games_home}.")


def scope_for(studio: Studio, game_root: Path) -> GameScope:
    return GameScope(game_root, studio.root, studio.games_home)


# --------------------------------------------------------------------------- settings merge

def _merge_list(dst: list, items: list) -> bool:
    added = False
    for x in items:
        if x not in dst:
            dst.append(x)
            added = True
    return added


def game_settings(studio: Studio, existing: dict | None) -> dict:
    """The game's tracked .claude/settings.json: the studio's rules, never removing the game's own."""
    src = read_json(studio.root / ".claude" / "settings.json", {}) or {}
    data = json.loads(json.dumps(existing or {}))  # deep copy
    data.setdefault("$schema", src.get("$schema", "https://json.schemastore.org/claude-code-settings.json"))
    perms = data.setdefault("permissions", {})
    for key in ("allow", "ask", "deny"):
        rules = [r for r in src.get("permissions", {}).get(key, [])
                 if not any(m in r for m in STUDIO_ONLY_RULE_MARKERS)]
        _merge_list(perms.setdefault(key, []), rules)
    _merge_list(data.setdefault("enabledMcpjsonServers", []), src.get("enabledMcpjsonServers", []))
    plugins = data.setdefault("enabledPlugins", {})
    for k, v in src.get("enabledPlugins", {}).items():
        plugins.setdefault(k, v)
    markets = data.setdefault("extraKnownMarketplaces", {})
    for k, v in src.get("extraKnownMarketplaces", {}).items():
        markets.setdefault(k, v)
    return data


def posix_rule_path(path: Path) -> str:
    """C:\\Users\\a -> //c/Users/a, /home/a -> //home/a (absolute form of permission rules)."""
    s = str(real(path)).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        s = "/" + s[0].lower() + s[2:]
    return "/" + s


def protected_deny_rules(studio: Studio, game_root: Path) -> list[str]:
    """Edit deny rules for the studio template and every sibling game.

    Deny always wins over allow, so a rule for the whole studio would also block the game
    when the games home lives inside it. The rules therefore list the studio's top-level
    entries (except the games home and work/) and each sibling game one by one; RoNavi
    rewrites them on every sync, and the PreToolUse guard covers anything added later.
    """
    rules: list[str] = []
    home = studio.games_home
    glob_chars = set("*?[]{}()")

    def add(p: Path) -> None:
        rule_path = posix_rule_path(p)
        if glob_chars & set(rule_path):
            return
        rules.append(f"Edit({rule_path}/**)" if p.is_dir() else f"Edit({rule_path})")

    if studio.root.is_dir():
        for entry in sorted(studio.root.iterdir(), key=lambda p: p.name.lower()):
            if entry.name in ("work",) or is_within(home, entry) or is_within(game_root, entry):
                continue
            add(entry)
    if home.is_dir():
        for sibling in sorted(home.iterdir(), key=lambda p: p.name.lower()):
            if sibling.is_dir() and not is_within(game_root, sibling) and not is_within(sibling, game_root):
                add(sibling)
    return rules


def _is_managed_deny(rule: str, studio: Studio) -> bool:
    if not rule.startswith("Edit(//"):
        return False
    roots = [posix_rule_path(studio.root), posix_rule_path(studio.games_home)]
    body = rule[len("Edit("):-1]
    return any(body == r or body.startswith(r + "/") for r in roots)


def _is_guard_hook(entry: dict) -> bool:
    return any("ronavi_guard.py" in " ".join([str(h.get("command", "")), *map(str, h.get("args", []))])
               for h in entry.get("hooks", []))


def hook_python() -> str:
    """A real interpreter for the hook: the venv's base Python survives a deleted .venv."""
    base = getattr(sys, "_base_executable", None) or sys.executable
    return str(Path(base).resolve())


def local_settings(studio: Studio, game_root: Path, existing: dict | None) -> dict:
    """The game's .claude/settings.local.json (untracked): guard hook + absolute deny rules."""
    data = json.loads(json.dumps(existing or {}))
    perms = data.setdefault("permissions", {})
    deny = [r for r in perms.get("deny", []) if not _is_managed_deny(r, studio)]
    perms["deny"] = deny + [r for r in protected_deny_rules(studio, game_root) if r not in deny]

    hooks = data.setdefault("hooks", {})
    pre = [e for e in hooks.get("PreToolUse", []) if not _is_guard_hook(e)]
    pre.insert(0, {
        "matcher": HOOK_MATCHER,
        "hooks": [{
            "type": "command",
            "command": hook_python(),
            "args": [str(real(game_root) / ".claude" / "hooks" / "ronavi_guard.py")],
            "timeout": 15,
        }],
    })
    hooks["PreToolUse"] = pre

    # Optional MCP servers start off, like the studio's own settings.local.json (D9).
    enabled = data.get("enabledMcpjsonServers", [])
    disabled = data.setdefault("disabledMcpjsonServers", [])
    for name in OPTIONAL_MCP_SERVERS:
        if name not in enabled and name not in disabled:
            disabled.append(name)
    return data


def guard_config(studio: Studio, game_root: Path, allowed: list[Path] | None = None) -> dict:
    protected = [str(studio.root)]
    if not is_within(studio.games_home, studio.root):
        protected.append(str(studio.games_home))
    return {
        "version": 1,
        "managed_by": f"RoNavi Studio {__version__}",
        "game_root": str(real(game_root)),
        "protected": protected,
        "allowed": [str(p) for p in (allowed if allowed is not None else [studio.root / "work"])],
    }


# --------------------------------------------------------------------------- writing a game

def _write_json(scope: GameScope, rel: str, data: object) -> None:
    scope.write_text(rel, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _read_obj(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except FileNotFoundError:
        return {}
    except ValueError as exc:
        raise GuardError(f"{path} no es JSON válido; arréglalo a mano antes de sincronizar ({exc}).") from exc
    if not isinstance(data, dict):
        raise GuardError(f"{path} no contiene un objeto JSON.")
    return data


def install_guard(studio: Studio, scope: GameScope, allowed: list[Path] | None = None) -> None:
    """Hook, its config and the deny rules, inside `scope` only. Shared by games and ideas."""
    scope.copy_file(GUARD_ASSET, GUARD_REL)
    _write_json(scope, GUARD_CONFIG_REL, guard_config(studio, scope.root, allowed))
    local_path = scope.check(".claude/settings.local.json")
    _write_json(scope, ".claude/settings.local.json", local_settings(studio, scope.root, _read_obj(local_path)))


def sync_guard(studio: Studio, game: Game, progress: Progress = _noop) -> None:
    """Install or refresh the guard of one game. Touches only files inside that game."""
    install_guard(studio, scope_for(studio, game.root))
    progress(f"guardián al día en {game.slug}")


def sync_all_guards(studio: Studio, progress: Progress = _noop) -> list[str]:
    """Refresh every managed game's guard (sibling lists change when a game is added)."""
    problems = []
    for g in discover(studio):
        if not g.managed:
            continue
        try:
            sync_guard(studio, g, progress)
        except (GuardError, OSError) as exc:
            problems.append(f"{g.slug}: {exc}")
    return problems


def apply_ronavi_files(studio: Studio, scope: GameScope, meta: dict, progress: Progress = _noop) -> None:
    root = scope.root
    name, slug = meta["name"], root.name
    genre, desc = meta.get("genre", "other"), meta.get("description", "")

    meta_path = scope.check(f"{GAME_META_DIR}/project.json")
    if not meta_path.exists():
        _write_json(scope, f"{GAME_META_DIR}/project.json", meta)
        progress("· .ronavi/project.json")

    claude_md = scope.check("CLAUDE.md")
    old = claude_md.read_text(encoding="utf-8") if claude_md.exists() else None
    scope.write_text("CLAUDE.md", T.upsert_block(old, T.claude_block(name, slug, genre, desc)))
    progress("· CLAUDE.md (instrucciones para Claude Code)")

    if not scope.check("README.md").exists():
        scope.write_text("README.md", T.readme(name, genre, desc))
        progress("· README.md")

    gi = scope.check(".gitignore")
    current = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    missing = [line for line in T.GITIGNORE_LINES if line and not line.startswith("#") and line not in current]
    if missing or not gi.exists():
        block = T.GITIGNORE_LINES if not current else ["", "# Added by RoNavi Studio", *missing]
        scope.write_text(".gitignore", "\n".join([*current, *block]).strip("\n") + "\n")
        progress("· .gitignore")

    mcp = studio.root / ".mcp.json"
    if mcp.exists() and not scope.check(".mcp.json").exists():
        scope.copy_file(mcp, ".mcp.json")
        progress("· .mcp.json (MCP de Roblox Studio)")

    settings_path = scope.check(".claude/settings.json")
    _write_json(scope, ".claude/settings.json", game_settings(studio, _read_obj(settings_path)))
    progress("· .claude/settings.json (permisos, MCP y plugins)")


def git_init(scope: GameScope, progress: Progress = _noop) -> None:
    root = scope.root
    if not (root / ".git").exists():
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True, capture_output=True, text=True)
        progress("· git init (repositorio propio)")
    assert_git_isolated(root)


def git_identity_ok(root: Path) -> bool:
    res = subprocess.run(["git", "config", "user.email"], cwd=root, capture_output=True, text=True)
    return res.returncode == 0 and bool(res.stdout.strip())


def initial_commit(scope: GameScope, name: str, progress: Progress = _noop) -> bool:
    root = scope.root
    assert_git_isolated(root)
    if not git_identity_ok(root):
        progress("! commit inicial omitido: configura git user.name y user.email")
        return False
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True, text=True)
    res = subprocess.run(["git", "commit", "-q", "-m", f"chore: scaffold {name} with RoNavi Studio"],
                         cwd=root, capture_output=True, text=True)
    if res.returncode != 0:
        progress("! commit inicial falló: " + (res.stderr or res.stdout).strip()[:200])
        return False
    progress("· commit inicial")
    return True


def scaffold_script() -> Path:
    return Path.home() / ".claude" / "skills" / "roblox-code" / "scripts" / "new_project.py"


def system_python() -> str:
    return shutil.which("python") or shutil.which("python3") or hook_python()


def create_game(studio: Studio, name: str, genre: str = "other", description: str = "", *,
                init_git: bool = True, commit: bool = True, scaffold: bool = False,
                from_idea: Path | None = None, progress: Progress = _noop) -> Game:
    from ronavi.core import ideas  # ideas imports this module

    display, slug = validate_name(name)
    if genre not in T.GENRE_LABELS:
        raise GuardError(f"Género desconocido: {genre}")
    description = " ".join(description.split())[:200]
    idea = ideas.load_idea(studio, from_idea) if from_idea is not None else None
    home = studio.games_home
    if is_within(home, studio.root) and not is_within(home, studio.default_games_home):
        progress(f"! la carpeta de juegos está dentro del estudio pero no es games/: {home}")
    home.mkdir(parents=True, exist_ok=True)
    root = home / slug
    scope = scope_for(studio, root)
    clash = [p.name for p in home.iterdir() if p.name.lower() == slug.lower()]
    if clash:
        raise GuardError(f"Ya existe {home / clash[0]}. Elige otro nombre o adopta esa carpeta.")
    progress(f"Creando {display} en {root}")

    if scaffold:
        script = scaffold_script()
        if not script.exists():
            progress("! roblox-code no está instalada: se crea el juego sin código (instala las skills)")
        else:
            progress("· generando el proyecto de código con roblox-code (new_project.py)")
            res = subprocess.run([system_python(), str(script), display, "--dir", str(root)],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            for line in (res.stdout + res.stderr).splitlines()[-8:]:
                progress("  " + line)
            if res.returncode != 0:
                progress("! new_project.py falló; se continúa sin código")
            scope.check(root)  # the generator must not have written anywhere else
    root.mkdir(exist_ok=True)

    meta = {
        "name": display,
        "genre": genre,
        "description": description,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ronavi_version": __version__,
    }
    if idea:
        meta["from_idea"] = idea.id
    apply_ronavi_files(studio, scope, meta, progress)
    if idea:
        n = ideas.copy_research(idea, scope)
        progress(f"· {RESEARCH_REL}/ ({n} archivo{'s' if n != 1 else ''} de la idea {idea.id})")
    game = load_game(root)
    sync_guard(studio, game, progress)
    if idea:
        ideas.mark_converted(studio, idea, slug)
    if init_git:
        git_init(scope, progress)
        if commit:
            initial_commit(scope, display, progress)
    for problem in sync_all_guards(studio):
        progress("! " + problem)
    progress(f"Listo: {display}")
    return load_game(root)


def adopt_game(studio: Studio, game: Game, genre: str = "other", *, init_git: bool = True,
               progress: Progress = _noop) -> Game:
    """Bring an existing folder under RoNavi: add its files and guard, keep everything it had."""
    scope = scope_for(studio, game.root)
    meta = {
        "name": game.name if game.managed else game.root.name,
        "genre": game.genre if game.managed else genre,
        "description": game.description,
        "created": game.created or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ronavi_version": __version__,
        "adopted": True,
    }
    apply_ronavi_files(studio, scope, meta, progress)
    sync_guard(studio, load_game(game.root), progress)
    if init_git:
        git_init(scope, progress)
    for problem in sync_all_guards(studio):
        progress("! " + problem)
    return load_game(game.root)


def launch_env(studio: Studio, game: Game) -> dict[str, str]:
    env = dict(os.environ)
    env["ROBLOX_GAMES_HOME"] = str(studio.games_home)
    env["RONAVI_STUDIO"] = str(studio.root)
    env["RONAVI_GAME"] = str(game.root)
    return env
