"""Versions and updates. The studio clone IS the installation (D18).

* A release is a git tag `vX.Y.Z` whose number matches `ronavi.__version__`.
* An installed studio (install.ps1 / install.sh) sits on the newest tag, detached:
  `update` moves it to the newest tag after a fetch.
* A development clone sits on a branch: `update` is `git pull --ff-only`.
* Nothing runs with local changes to tracked files; games/, work/ and .ronavi/ are ignored.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import time
from pathlib import Path
from typing import Callable

from ronavi import __version__
from ronavi.core.guard import git_toplevel, same_path
from ronavi.core.paths import Studio

TAG_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
CHECK_EVERY = 24 * 3600  # seconds between automatic "is there a newer RoNavi?" checks


class UpdateError(RuntimeError):
    """The update did not run; the message says why and what to do."""


def _git(root: Path, *args: str, timeout: float = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def parse_version(text: str) -> tuple[int, int, int] | None:
    m = TAG_RE.match(text.strip())
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def latest_tag(tags: list[str]) -> str | None:
    versions = [(v, t) for t in tags if (v := parse_version(t)) and t.startswith("v")]
    return max(versions)[1] if versions else None


def describe(root: Path | None) -> str:
    """'v0.2.0', 'v0.2.0-3-gabc1234', 'abc1234-dirty'… or '' when it cannot tell."""
    if root is None or not (root / ".git").exists():
        return ""
    try:
        res = _git(root, "describe", "--tags", "--always", "--dirty", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return res.stdout.strip() if res.returncode == 0 else ""


def is_own_repo(root: Path) -> bool:
    top = git_toplevel(root)
    return top is not None and same_path(top, root)


def local_tags(root: Path) -> list[str]:
    res = _git(root, "tag", "--list", "v*")
    return res.stdout.split() if res.returncode == 0 else []


def remote_tags(root: Path, timeout: float = 3) -> list[str]:
    """Tags on origin, or [] when offline, without a remote or slow. Never raises."""
    try:
        res = _git(root, "ls-remote", "--tags", "--refs", "origin", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return []
    if res.returncode != 0:
        return []
    return [line.split("refs/tags/", 1)[1] for line in res.stdout.splitlines() if "refs/tags/" in line]


def current_branch(root: Path) -> str | None:
    res = _git(root, "symbolic-ref", "-q", "--short", "HEAD")
    if res.returncode != 0:  # detached HEAD: an installed release
        return None
    return res.stdout.strip() or None


def tracked_changes(root: Path) -> list[str]:
    res = _git(root, "status", "--porcelain", "--untracked-files=no")
    return [line for line in res.stdout.splitlines() if line.strip()]


def _file_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def update(studio: Studio, progress: Callable[[str], None] = lambda _: None) -> str:
    """Bring the studio to the newest release (on a tag) or the newest commit of its branch."""
    root = studio.root
    if not is_own_repo(root):
        raise UpdateError(f"{root} no es un clon de git de RoNavi Studio: vuelve a instalarlo con install.ps1 "
                          "o install.sh.")
    changes = tracked_changes(root)
    if changes:
        raise UpdateError(f"El estudio tiene {len(changes)} cambio{'s' if len(changes) != 1 else ''} sin guardar "
                          "en archivos de git. Haz commit o guárdalos con git stash y vuelve a intentarlo.")
    lock = root / "skills.lock.json"
    lock_before, before = _file_hash(lock), describe(root)

    progress("git fetch --tags origin")
    res = _git(root, "fetch", "--tags", "--quiet", "origin")
    if res.returncode != 0:
        raise UpdateError("No se pudo descargar de origin: " + (res.stderr or res.stdout).strip()[:300])

    branch = current_branch(root)
    if branch:
        progress(f"rama {branch}: git pull --ff-only")
        res = _git(root, "pull", "--ff-only", "--quiet")
    else:
        tag = latest_tag(local_tags(root))
        if not tag:
            raise UpdateError("No hay ninguna versión publicada (tags vX.Y.Z) en origin.")
        progress(f"versión más reciente: {tag}")
        res = _git(root, "checkout", "--quiet", tag)
    if res.returncode != 0:
        raise UpdateError("git no pudo actualizar: " + (res.stderr or res.stdout).strip()[:300])

    after = describe(root)
    if before == after:
        return f"Ya estabas al día ({after or __version__})."
    msg = f"Actualizado: {before or '?'} → {after}. Cierra y vuelve a abrir ronavi para usar la nueva versión."
    if _file_hash(lock) != lock_before:
        msg += " Cambiaron las skills fijadas: ejecuta Skills → Actualizar (o scripts/update-skills)."
    return msg


def check_for_update(studio: Studio, *, force: bool = False) -> str | None:
    """The newest tag on origin when it is newer than this RoNavi, at most once a day unless forced."""
    now = time.time()
    if not force and now - studio.config.last_update_check < CHECK_EVERY:
        return None
    studio.config.last_update_check = now
    try:
        studio.save()
    except OSError:
        pass
    newest = latest_tag(remote_tags(studio.root))
    mine = parse_version(__version__)
    if newest and mine and (parse_version(newest) or mine) > mine:
        return newest
    return None
