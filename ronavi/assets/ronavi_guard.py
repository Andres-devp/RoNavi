#!/usr/bin/env python3
"""RoNavi Studio guard: a Claude Code PreToolUse hook installed in every game.

It blocks (exit code 2) any Write / Edit / MultiEdit / NotebookEdit outside this game
that lands in the studio template or in another game, and any Bash / PowerShell
command that would change files there (rm, mv, cp, redirections, Remove-Item, git
commit...). Reading is never blocked.

Configuration: .claude/ronavi-guard.json next to this script, written by RoNavi
(`ronavi sync-guards`). Without it, the game is this script's grandparent folder and
the protected zone is the folder that contains the game (its sibling games).

Standard library only: it is copied into each game and must run anywhere.
Managed by RoNavi Studio: changes are overwritten on the next sync.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
CONFIG_FILE = HERE.parent.parent / "ronavi-guard.json"

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}

MUTATING = {
    # POSIX / Git Bash
    "rm", "rmdir", "unlink", "mv", "cp", "touch", "mkdir", "tee", "truncate", "chmod", "chown",
    "ln", "install", "dd", "shred", "rsync",
    # cmd.exe
    "del", "erase", "rd", "move", "copy", "xcopy", "robocopy", "ren", "rename", "md",
    # PowerShell cmdlets and aliases
    "remove-item", "move-item", "copy-item", "rename-item", "new-item", "set-content",
    "add-content", "out-file", "clear-content", "ri", "mi", "ci", "rni", "ni", "sc", "ac",
}
IN_PLACE = {"sed", "perl"}  # mutate only with -i
GIT_MUTATING = {
    "add", "commit", "reset", "checkout", "switch", "restore", "clean", "rm", "mv", "push", "pull",
    "merge", "rebase", "stash", "init", "apply", "am", "cherry-pick", "revert", "tag", "branch",
    "worktree", "submodule", "config", "gc", "prune", "fetch", "clone",
}
DRIVE_RE = re.compile(r"^[A-Za-z]:([\\/]|$)")
GITBASH_DRIVE_RE = re.compile(r"^/([A-Za-z])(/|$)")


# --------------------------------------------------------------------------- paths

def _real(path: str | Path) -> Path:
    return Path(os.path.realpath(str(path)))


def _key(path: Path) -> str:
    return os.path.normcase(str(_real(path))).rstrip("\\/")


def is_within(child: Path, parent: Path) -> bool:
    c, p = _key(child), _key(parent)
    return c == p or c.startswith(p + os.sep)


def to_path(raw: str, cwd: Path) -> Path:
    """Turn a token as Claude wrote it into an absolute path."""
    s = raw.strip().strip("'\"")
    if s.startswith("~"):
        s = os.path.expanduser(s)
    if os.name == "nt":
        m = GITBASH_DRIVE_RE.match(s)  # Git Bash: /c/Users/... -> C:/Users/...
        if m:
            s = f"{m.group(1).upper()}:/{s[m.end():]}"
    p = Path(s)
    if not p.is_absolute():
        p = cwd / p
    return _real(p)


def looks_like_path(token: str) -> bool:
    t = token.strip("'\"")
    if not t or "://" in t:
        return False
    return ("/" in t or "\\" in t or t.startswith(("~", ".")) or bool(DRIVE_RE.match(t)))


# --------------------------------------------------------------------------- config

def load_config() -> dict:
    game = HERE.parent.parent.parent
    cfg = {"game_root": str(game), "protected": [str(game.parent)], "allowed": []}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            cfg.update({k: data[k] for k in ("game_root", "protected", "allowed") if k in data})
    except (OSError, ValueError):
        pass
    return cfg


class Guard:
    def __init__(self, cfg: dict):
        self.game = _real(cfg["game_root"])
        self.protected = [_real(p) for p in cfg.get("protected", [])]
        self.allowed = [self.game, *(_real(p) for p in cfg.get("allowed", []))]
        self.self_files = [_real(HERE), _real(CONFIG_FILE), self.game / ".claude" / "hooks" / "ronavi_guard.py",
                           self.game / ".claude" / "ronavi-guard.json"]

    def path_problem(self, path: Path) -> str | None:
        """None if writing `path` is fine, else the reason it is not."""
        if any(_key(path) == _key(f) for f in self.self_files):
            return f"{path} es el guardián de RoNavi; solo RoNavi lo actualiza."
        if any(is_within(path, a) for a in self.allowed):
            return None
        for zone in self.protected:
            if is_within(path, zone):
                return (f"{path} está fuera de este juego ({self.game.name}) y dentro de una zona protegida "
                        f"({zone}): la plantilla del estudio u otro juego.")
        return None

    # ------------------------------------------------------------------ tools

    def check_write(self, tool_input: dict, cwd: Path) -> str | None:
        raw = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path")
        if not raw:
            return None
        return self.path_problem(to_path(str(raw), cwd))

    def check_command(self, command: str, cwd: Path) -> str | None:
        tokens = tokenize(command)
        if not is_mutating(tokens):
            return None
        for tok in tokens:
            for part in split_assignment(tok):
                if looks_like_path(part):
                    problem = self.path_problem(to_path(part, cwd))
                    if problem:
                        return problem + " El comando cambia archivos (si solo lee, sepáralo en otro comando)."
        return None


def tokenize(command: str) -> list[str]:
    # posix=False keeps Windows backslashes intact; quotes are stripped afterwards.
    try:
        lex = shlex.shlex(command, posix=False, punctuation_chars=True)
        lex.whitespace_split = True
        return [t.strip("'\"") for t in lex]
    except ValueError:
        return [t.strip("'\"") for t in command.split()]


def split_assignment(token: str) -> list[str]:
    """'--dir=../x' -> ['--dir=../x', '../x']; '-Path:C:\\x' is left whole (drive colon)."""
    if "=" in token:
        return [token, token.split("=", 1)[1]]
    return [token]


def _verb(token: str) -> str:
    name = re.split(r"[\\/]", token)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def is_mutating(tokens: list[str]) -> bool:
    verbs = [_verb(t) for t in tokens]
    if any(v in MUTATING for v in verbs):
        return True
    if any(t in (">", ">>", ">|", "&>") or t.endswith(">") and set(t) <= set("0123456789&>|")
           for t in tokens):
        return True
    for i, v in enumerate(verbs):
        if v in IN_PLACE and any(t == "-i" or t.startswith("-i") for t in tokens[i + 1:]):
            return True
        if v == "git":
            rest = [t for t in tokens[i + 1:] if not t.startswith("-")]
            if rest and rest[0].lower() in GIT_MUTATING:
                return True
            # `git -C path commit`: the first non-flag word after -C's argument
            if "-C" in tokens[i + 1:] and any(t.lower() in GIT_MUTATING for t in tokens[i + 1:]):
                return True
    return False


def decide(payload: dict, guard: Guard) -> str | None:
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    cwd = Path(payload.get("cwd") or guard.game)
    if tool in WRITE_TOOLS:
        return guard.check_write(tool_input, cwd)
    if tool in SHELL_TOOLS:
        return guard.check_command(str(tool_input.get("command", "")), cwd)
    return None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
        problem = decide(payload, Guard(load_config()))
    except Exception as exc:  # a broken guard must not brick the session; say so loudly
        sys.stderr.write(f"[ronavi-guard] aviso: el guardián falló y no comprobó esta acción: {exc}\n")
        return 0
    if problem:
        sys.stderr.write(f"[ronavi-guard] Bloqueado: {problem}\n"
                         "Este juego solo puede modificar archivos dentro de su propia carpeta. Si de verdad "
                         "hace falta tocar la plantilla u otro juego, pídeselo al usuario para que lo haga "
                         "desde RoNavi Studio o a mano.\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
