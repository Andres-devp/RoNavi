"""Where the studio, its games and RoNavi's own state live."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

# Files that identify the studio root (this repository).
STUDIO_MARKERS = ("skills.lock.json", "scripts/doctor.py", "ronavi/__init__.py")
STATE_DIR = ".ronavi"          # inside the studio: config.json (untracked)
GAME_META_DIR = ".ronavi"      # inside a game: project.json (tracked by the game's git)
LAUNCH_MODES = ("here", "window")


class StudioNotFound(RuntimeError):
    pass


def is_studio_root(path: Path) -> bool:
    return all((path / m).exists() for m in STUDIO_MARKERS)


def find_studio_root() -> Path:
    """The studio is the repository that contains this package. RONAVI_STUDIO overrides it (tests)."""
    env = os.environ.get("RONAVI_STUDIO")
    candidates = [Path(env)] if env else [Path(__file__).resolve().parents[2]]
    for cand in candidates:
        cand = cand.expanduser().resolve()
        if is_studio_root(cand):
            return cand
    raise StudioNotFound(f"no se encontró la raíz del estudio (se buscó en {', '.join(map(str, candidates))})")


def write_json_atomic(path: Path, data: object) -> None:
    """Write JSON through a temp file + replace, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_json(path: Path, default: object = None) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8") or "null")
    except FileNotFoundError:
        return default


@dataclass
class Config:
    """RoNavi preferences for this machine, in <studio>/.ronavi/config.json (git-ignored)."""

    games_home: str | None = None      # None = ROBLOX_GAMES_HOME or <studio>/games
    launch_mode: str = "here"          # here = suspend the TUI; window = new terminal window
    animations: bool = True
    setup_done: bool = False           # the first-run wizard was completed (or skipped) once
    last_game: str | None = None
    manual_done: list[str] = field(default_factory=list)  # manual wizard steps the user ticked

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        known = {f.name for f in fields(cls)}
        cfg = cls(**{k: v for k, v in (data or {}).items() if k in known})
        if cfg.launch_mode not in LAUNCH_MODES:
            cfg.launch_mode = "here"
        return cfg


@dataclass
class Studio:
    """The studio repository plus RoNavi's view of it."""

    root: Path
    config: Config

    @classmethod
    def load(cls, root: Path | None = None) -> "Studio":
        root = (root or find_studio_root()).resolve()
        data = read_json(root / STATE_DIR / "config.json", {})
        return cls(root, Config.from_dict(data if isinstance(data, dict) else {}))

    @property
    def state_dir(self) -> Path:
        return self.root / STATE_DIR

    @property
    def config_file(self) -> Path:
        return self.state_dir / "config.json"

    @property
    def default_games_home(self) -> Path:
        return self.root / "games"

    @property
    def games_home(self) -> Path:
        value = self.config.games_home or os.environ.get("ROBLOX_GAMES_HOME")
        path = Path(os.path.expandvars(value)).expanduser() if value else self.default_games_home
        return path.resolve()

    @property
    def is_first_run(self) -> bool:
        return not self.config.setup_done

    def save(self) -> None:
        write_json_atomic(self.config_file, asdict(self.config))
