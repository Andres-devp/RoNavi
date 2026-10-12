"""A throwaway studio on disk for tests: same layout as the real one, its own git, no network."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from ronavi.core.paths import Studio

REPO = Path(__file__).resolve().parents[1]
COPY = [
    "skills.lock.json", ".mcp.json", ".gitignore", ".claude/settings.json", "scripts/doctor.py", "scripts/skills_sync.py",
    "ronavi/__init__.py", "README.md", "CLAUDE.md", "docs/quotas.md",
    ".claude/skills/quota-guard/SKILL.md", ".claude/skills/quota-guard/scripts/quota.py",
    ".claude/skills/studio-doctor/SKILL.md", ".claude/skills/own-audio/SKILL.md",
]


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


class StudioTestCase(unittest.TestCase):
    """Builds <tmp>/studio (a git repo with the template files) and isolates git's global config."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ronavi-test-", ignore_cleanup_errors=True)
        self.tmp = Path(os.path.realpath(self._tmp.name))
        self.root = self.tmp / "studio"
        for rel in COPY:
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / rel, dst)
        (self.root / "games").mkdir()
        (self.root / "games" / "README.md").write_text("games\n", encoding="utf-8")
        (self.root / "work").mkdir()

        gitconfig = self.tmp / "gitconfig"
        gitconfig.write_text("[user]\n\tname = RoNavi Test\n\temail = test@example.invalid\n"
                             "[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n", encoding="utf-8")
        self._env = {k: os.environ.get(k) for k in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM",
                                                     "ROBLOX_GAMES_HOME", "RONAVI_STUDIO")}
        os.environ["GIT_CONFIG_GLOBAL"] = str(gitconfig)
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
        os.environ.pop("ROBLOX_GAMES_HOME", None)
        os.environ["RONAVI_STUDIO"] = str(self.root)

        git("init", "-q", "-b", "main", cwd=self.root)
        git("add", "-A", cwd=self.root)
        git("commit", "-q", "-m", "template", cwd=self.root)
        self.studio = Studio.load(self.root)

    def tearDown(self) -> None:
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()

    # ------------------------------------------------------------------ helpers

    def tree_hash(self, root: Path, skip: tuple[str, ...] = ()) -> dict[str, str]:
        out = {}
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root).as_posix()
            if not p.is_file() or rel.startswith(".git/") or any(rel == s or rel.startswith(s + "/") for s in skip):
                continue
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    def template_hash(self) -> dict[str, str]:
        return self.tree_hash(self.root, skip=("games", ".ronavi", "work"))


def make_link(link: Path, target: Path) -> None:
    """Directory link that needs no admin rights: a junction on Windows, a symlink elsewhere."""
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)
