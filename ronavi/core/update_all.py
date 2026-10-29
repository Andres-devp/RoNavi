""""Actualizar todo": RoNavi, skills, plugins, the games' guards and the games' toolchains, in that order.

Every step runs even when an earlier one failed, and each one ends in a StepResult (✔ / ✘ / … pending).
The skills step is interactive (it asks before moving each pinned commit), so the caller decides how to
hand it the terminal: `run_here` in the CLI, `app.run_interactive` in the TUI.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ronavi.core import environment as envmod
from ronavi.core import updates
from ronavi.core.launcher import claude_executable
from ronavi.core.paths import Studio
from ronavi.core.projects import discover, launch_env, sync_all_guards

Progress = Callable[[str], None]
Interactive = Callable[[list[str], Path], int]  # runs cmd in cwd with the user's terminal, returns its exit code

OK, FAIL, PENDING = "ok", "fail", "pending"
MARK = {OK: "✔", FAIL: "✘", PENDING: "…"}
TOOLCHAIN_FILES = ("rokit.toml", "aftman.toml", "foreman.toml")


class StepFailed(Exception):
    """The step ran and did not finish its job; the message says what is left."""


class StepPending(Exception):
    """The step did what it could, but part of it is not available yet."""


@dataclass
class StepResult:
    title: str
    status: str
    detail: str = ""

    def line(self) -> str:
        return f"{MARK[self.status]} {self.title}" + (f": {self.detail}" if self.detail else "")


@dataclass
class Step:
    title: str
    func: Callable[[Progress], str]
    interactive: bool = False  # needs the terminal: the TUI runs it suspended, not in a TaskScreen


def _noop(_: str) -> None:
    pass


def _run(cmd: list[str], cwd: Path, progress: Progress, env: dict[str, str] | None = None) -> int:
    """Stream a command's output to `progress`. Never reads stdin, so it cannot hang on a prompt."""
    progress("$ " + " ".join(cmd))
    run_env = dict(env or os.environ)
    run_env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        proc = subprocess.Popen(cmd, cwd=cwd, env=run_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        progress(f"No se pudo ejecutar {cmd[0]}: {exc}")
        return 127
    assert proc.stdout is not None
    for line in proc.stdout:
        progress(line.rstrip("\r\n"))
    return proc.wait()


def _json(cmd: list[str], cwd: Path) -> object | None:
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                             stdin=subprocess.DEVNULL, timeout=120)
        return json.loads(res.stdout) if res.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


# ---------------------------------------------------------------------------- steps

def ronavi_step(studio: Studio, progress: Progress) -> str:
    return updates.update(studio, progress)  # UpdateError (e.g. uncommitted changes) marks the step ✘


def skills_command(studio: Studio) -> list[str]:
    """scripts/update-skills: shows what changed upstream and asks before moving each pin."""
    if envmod.SYSTEM == "Windows":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(studio.root / "scripts" / "update-skills.ps1")]
    return ["bash", str(studio.root / "scripts" / "update-skills.sh")]


def skills_step(studio: Studio, interactive: Interactive) -> str:
    code = interactive(skills_command(studio), studio.root)
    if code != 0:
        raise StepFailed(f"update-skills terminó con código {code}")
    return "revisadas; solo se mueven los commits que aprobaste"


def plugin_sources(studio: Studio) -> list[dict]:
    lock = json.loads((studio.root / "skills.lock.json").read_text(encoding="utf-8"))
    return [s["install"] for s in lock["sources"] if s["install"]["method"] == "plugin"]


def plugins_step(studio: Studio, progress: Progress) -> str:
    """Refresh each marketplace and plugin. A marketplace pinned to a tag stays on that tag: moving it is
    update-skills' job (it asks first), so a pin that does not match skills.lock.json is reported, not fixed."""
    exe = claude_executable()
    if not exe:
        raise StepFailed("Claude Code no está instalado (Herramientas → Instalar programas)")
    listed = _json([exe, "plugin", "marketplace", "list", "--json"], studio.root)
    if not isinstance(listed, list):
        raise StepFailed("claude plugin marketplace list no respondió")
    markets = {m.get("name"): m for m in listed if isinstance(m, dict)}
    done, problems = [], []
    for inst in plugin_sources(studio):
        name, plugin = inst["marketplace"], inst["plugin"]
        wanted = inst["marketplaceSource"]
        ref = wanted.split("#", 1)[1] if "#" in wanted else None
        current = markets.get(name)
        if current is None:
            problems.append(f"falta el marketplace {name} (Skills → Instalar / sincronizar)")
            continue
        if ref and current.get("ref") != ref:
            problems.append(f"{name} está en {current.get('ref') or 'sin fijar'} y no en {ref} "
                            "(Skills → Instalar / sincronizar lo vuelve a fijar)")
            continue
        if _run([exe, "plugin", "marketplace", "update", name], studio.root, progress) != 0:
            problems.append(f"no se pudo actualizar el marketplace {name}")
            continue
        if _run([exe, "plugin", "update", plugin, "--scope", inst["scope"]], studio.root, progress) != 0:
            problems.append(f"no se pudo actualizar {plugin}")
            continue
        done.append(plugin + (f" ({ref})" if ref else ""))
    if problems:
        raise StepFailed("; ".join(problems))
    return ", ".join(done) + " al día; reinicia Claude Code para usarlos" if done else "no hay plugins"


def guards_step(studio: Studio, progress: Progress) -> str:
    problems = sync_all_guards(studio, progress)
    if problems:
        raise StepFailed("; ".join(problems))
    n = sum(1 for g in discover(studio) if g.managed)
    return f"{n} juego{'s' if n != 1 else ''} con el guardián al día"


def toolchain_step(studio: Studio, progress: Progress) -> str:
    """Raise each game's pinned tool versions (ronavi.core.toolchain) and install them with rokit."""
    try:
        from ronavi.core.toolchain import upgrade_toolchain
    except ImportError:  # not shipped yet: still install what each game already pins
        upgrade_toolchain = None
        progress("ronavi.core.toolchain no está disponible todavía: solo rokit install")
    games = [g for g in discover(studio) if any((g.root / f).is_file() for f in TOOLCHAIN_FILES)]
    failed, changed = [], 0
    for g in games:
        progress(f"· {g.slug}")
        if upgrade_toolchain is not None:
            try:
                changes = upgrade_toolchain(g.root, progress)
            except Exception as exc:  # one game never stops the rest
                failed.append(f"{g.slug}: {exc}")
                continue
            for c in changes:
                progress(f"  {c}")
            changed += bool(changes)
        code = _run(["rokit", "install"], g.root, progress, env=launch_env(studio, g))
        if code != 0:
            failed.append(f"{g.slug}: rokit install terminó con código {code}")
    summary = f"{len(games)} juego{'s' if len(games) != 1 else ''} con rokit install"
    if upgrade_toolchain is not None:
        summary += f", {changed} con versiones nuevas"
    if failed:
        raise StepFailed("; ".join(failed))
    if upgrade_toolchain is None:
        raise StepPending(f"{summary}; subir versiones queda pendiente (falta ronavi.core.toolchain)")
    return summary


# ---------------------------------------------------------------------------- driver

def steps(studio: Studio, interactive: Interactive) -> list[Step]:
    return [
        Step("RoNavi", lambda p: ronavi_step(studio, p)),
        Step("Skills de terceros", lambda _p: skills_step(studio, interactive), interactive=True),
        Step("Plugins de Claude Code", lambda p: plugins_step(studio, p)),
        Step("Guardianes de los juegos", lambda p: guards_step(studio, p)),
        Step("Toolchain de los juegos", lambda p: toolchain_step(studio, p)),
    ]


def run_step(step: Step, progress: Progress = _noop) -> StepResult:
    """Run one step; any exception becomes ✘ (or … pending) with its message, never a crash."""
    try:
        result = StepResult(step.title, OK, step.func(progress))
    except StepPending as exc:
        result = StepResult(step.title, PENDING, str(exc))
    except Exception as exc:  # shown in the summary, never swallowed
        result = StepResult(step.title, FAIL, str(exc) or type(exc).__name__)
    progress(result.line())
    return result


def update_all(studio: Studio, interactive: Interactive, progress: Progress = _noop) -> list[StepResult]:
    plan = steps(studio, interactive)
    results = []
    for i, step in enumerate(plan, 1):
        progress(f"\n▸ [{i}/{len(plan)}] {step.title}")
        results.append(run_step(step, progress))
    return results


def summary(results: list[StepResult]) -> str:
    return "\n".join(r.line() for r in results)
