#!/usr/bin/env python3
"""Install and update the third-party skills pinned in skills.lock.json.

Shared by scripts/setup.ps1, scripts/setup.sh and scripts/update-skills.*, so the
Windows and POSIX paths run the same logic. Standard library only.

    python scripts/skills_sync.py vendor          # clone/checkout every pinned source into vendor/
    python scripts/skills_sync.py user [--force]  # SyphoDev: run its own installer, then patch agents
    python scripts/skills_sync.py project         # copy project-level skills into .claude/skills/
    python scripts/skills_sync.py plugins         # add marketplaces and install the plugins
    python scripts/skills_sync.py local-settings  # optional MCP servers off by default (settings.local.json)
    python scripts/skills_sync.py all             # all of the above, in order
    python scripts/skills_sync.py update          # show upstream changes, ask, move the pins

Exit codes: 0 ok, 1 error, 3 (update only) skills.lock.json changed, re-run setup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOCK = REPO / "skills.lock.json"
VENDOR = REPO / "vendor"
CLAUDE_HOME = Path.home() / ".claude"
USER_SKILLS = CLAUDE_HOME / "skills"
USER_AGENTS = CLAUDE_HOME / "agents"
LOCAL_SETTINGS = REPO / ".claude" / "settings.local.json"

# Servers declared in .mcp.json that stay off until the user opts in.
OPTIONAL_MCP_SERVERS = ["blender-ahujasid", "robloxstudio-runtime"]

# Files that belong to the user, never compared or overwritten.
HASH_EXCLUDE = {"LOCAL.md", "__pycache__", ".git", ".DS_Store"}

PATCH_COMMENT = (
    "# roblox-ai-studio: only the main thread writes to Studio. Subagents never get the "
    "Studio MCP servers (see CLAUDE.md and docs/decisions.md)."
)

IS_WINDOWS = os.name == "nt"


# --------------------------------------------------------------------------- helpers

def say(msg: str) -> None:
    print(msg, flush=True)


def load_lock() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))


def save_lock(lock: dict) -> None:
    LOCK.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def run(cmd: list[str], cwd: Path | None = None, check: bool = True, capture: bool = False,
        timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, encoding="utf-8", errors="replace",
                          capture_output=capture, timeout=timeout)


def git(*args: str, cwd: Path) -> str:
    return run(["git", *args], cwd=cwd, capture=True).stdout.strip()


def vendor_dir(src: dict) -> Path:
    return VENDOR / src["name"]


def git_sources(lock: dict) -> list[dict]:
    return [s for s in lock["sources"] if s.get("commit")]


def source(lock: dict, name: str) -> dict:
    for s in lock["sources"]:
        if s["name"] == name:
            return s
    raise SystemExit(f"source {name!r} not found in skills.lock.json")


def tree_hash(root: Path) -> str:
    """Content hash of a file or directory tree, ignoring user-owned files."""
    h = hashlib.sha256()
    if root.is_file():
        h.update(root.read_bytes())
        return h.hexdigest()
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if any(part in HASH_EXCLUDE for part in rel.parts) or not p.is_file():
            continue
        h.update(rel.as_posix().encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def claude_exe() -> str | None:
    return shutil.which("claude")


def claude_json(*args: str) -> object | None:
    exe = claude_exe()
    if not exe:
        return None
    res = run([exe, *args], cwd=REPO, capture=True, check=False, timeout=120)
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout)
    except ValueError:
        return None


# --------------------------------------------------------------------------- vendor

def ensure_vendor(src: dict) -> Path:
    dest = vendor_dir(src)
    commit = src["commit"]
    if not (dest / ".git").exists():
        VENDOR.mkdir(exist_ok=True)
        say(f"  clone  {src['repo']} -> vendor/{src['name']}")
        run(["git", "clone", "--quiet", src["url"], str(dest)])
    if run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=dest, check=False,
           capture=True).returncode != 0:
        say(f"  fetch  {src['repo']}")
        run(["git", "fetch", "--quiet", "--tags", "origin"], cwd=dest)
    run(["git", "-c", "advice.detachedHead=false", "checkout", "--quiet", "--force", "--detach", commit],
        cwd=dest)
    head = git("rev-parse", "HEAD", cwd=dest)
    if head != commit:
        raise SystemExit(f"vendor/{src['name']} is at {head}, expected {commit}")
    say(f"  ok     vendor/{src['name']} @ {commit[:7]}")
    return dest


def cmd_vendor(lock: dict) -> int:
    say("[vendor] pinned sources")
    for src in git_sources(lock):
        ensure_vendor(src)
    return 0


# --------------------------------------------------------------------------- agent patch

def patch_agent_text(text: str, extra: list[str]) -> str:
    """Add `extra` to the agent's `disallowedTools` frontmatter key without removing anything.

    Why: this studio has ONE writer to Roblox Studio, the main conversation. Two
    MCP clients writing to the same place race each other (the same failure as two
    Rojo connections), so every SyphoDev subagent is denied both the official
    Studio MCP (`Roblox_Studio`) and the optional runtime server. Subagents work on
    disk and hand results back; the main thread assembles in Studio.

    Per the Claude Code subagent docs, `disallowedTools` takes a comma-separated
    string or a YAML list, and `mcp__<server>` removes every tool of that server.
    """
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    if not lines or lines[0].strip() != "---":
        raise ValueError("agent file has no YAML frontmatter")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration as exc:
        raise ValueError("agent frontmatter is not closed") from exc

    key = next((i for i in range(1, end) if re.match(r"^disallowedTools\s*:", lines[i])), None)
    has_comment = any(lines[i].strip() == PATCH_COMMENT for i in range(1, end))

    if key is None:
        insert = ([] if has_comment else [PATCH_COMMENT]) + [f"disallowedTools: {', '.join(extra)}"]
        lines[end:end] = insert
        return nl.join(lines)

    value = lines[key].split(":", 1)[1].strip()
    if value.startswith("["):  # flow list: [a, b]
        items = [x.strip().strip("'\"") for x in value.strip("[]").split(",") if x.strip()]
        missing = [x for x in extra if x not in items]
        if missing:
            lines[key] = "disallowedTools: [" + ", ".join(items + missing) + "]"
    elif value:  # comma-separated string
        items = [x.strip() for x in value.split(",") if x.strip()]
        missing = [x for x in extra if x not in items]
        if missing:
            lines[key] = "disallowedTools: " + ", ".join(items + missing)
    else:  # block list on the following lines
        j = key + 1
        items = []
        while j < end and re.match(r"^\s+-\s*", lines[j]):
            items.append(re.sub(r"^\s+-\s*", "", lines[j]).strip().strip("'\""))
            j += 1
        indent = re.match(r"^(\s+)-", lines[key + 1]).group(1) if j > key + 1 else "  "
        missing = [x for x in extra if x not in items]
        lines[j:j] = [f"{indent}- {x}" for x in missing]
    if not has_comment:
        lines.insert(key, PATCH_COMMENT)
    return nl.join(lines)


def agent_is_patched(path: Path, extra: list[str]) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
        return patch_agent_text(text, extra) == text
    except (OSError, ValueError):
        return False


def syphodev_agents(src: dict) -> list[Path]:
    return sorted((vendor_dir(src) / "agents").glob("*.md"))


def patch_agents(src: dict) -> None:
    extra = src["install"]["patchAgents"]["disallowedTools"]
    for vendor_agent in syphodev_agents(src):
        target = USER_AGENTS / vendor_agent.name
        if not target.exists():
            say(f"  !!     agent {target.name} not installed")
            continue
        raw = target.read_bytes().decode("utf-8")
        new = patch_agent_text(raw, extra)
        if new != raw:
            target.write_bytes(new.encode("utf-8"))
            say(f"  patch  ~/.claude/agents/{target.name}")
        else:
            say(f"  ok     ~/.claude/agents/{target.name} already patched")


# --------------------------------------------------------------------------- user scope (SyphoDev)

def syphodev_in_sync(src: dict) -> bool:
    vend = vendor_dir(src)
    extra = src["install"]["patchAgents"]["disallowedTools"]
    for skill in sorted(p for p in (vend / "skills").iterdir() if p.is_dir()):
        dest = USER_SKILLS / skill.name
        if not dest.is_dir() or tree_hash(dest) != tree_hash(skill):
            return False
    for agent in syphodev_agents(src):
        dest = USER_AGENTS / agent.name
        if not dest.exists():
            return False
        expected = patch_agent_text(agent.read_bytes().decode("utf-8"), extra)
        if dest.read_bytes().decode("utf-8") != expected:
            return False
    return True


def cmd_user(lock: dict, force: bool) -> int:
    src = source(lock, "syphodev-roblox-ai-skills")
    vend = ensure_vendor(src)
    say("[user] SyphoDev skills and agents -> ~/.claude")
    if not force and syphodev_in_sync(src):
        # Their installer backs up every existing skill on each run; skipping it when
        # nothing changed keeps setup idempotent and ~/.claude free of backup piles.
        say("  ok     already installed at the pinned commit (installer skipped; --force to rerun)")
    else:
        if IS_WINDOWS:
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                   str(vend / src["install"]["installer"]["windows"])]
        else:
            cmd = ["bash", str(vend / src["install"]["installer"]["posix"])]
        say(f"  run    their installer: {Path(cmd[-1]).name}")
        run(cmd, cwd=vend)
    patch_agents(src)
    return 0


# --------------------------------------------------------------------------- project scope

def cmd_project(lock: dict) -> int:
    say("[project] skills -> .claude/skills/")
    skills_root = (REPO / ".claude" / "skills").resolve()
    for src in lock["sources"]:
        inst = src["install"]
        if inst["method"] != "copy":
            continue
        vend = ensure_vendor(src)
        roots = {Path(*Path(c["to"]).parts[:3]) for c in inst["copy"]}
        for root in sorted(roots):
            target = (REPO / root).resolve()
            if target.parent != skills_root:
                raise SystemExit(f"refusing to replace {root}: not a folder directly under .claude/skills")
            if target.exists():
                shutil.rmtree(target)
        for c in inst["copy"]:
            frm, to = vend / c["from"], REPO / c["to"]
            to.parent.mkdir(parents=True, exist_ok=True)
            if frm.is_dir():
                shutil.copytree(frm, to, dirs_exist_ok=True)
            else:
                shutil.copy2(frm, to)
        for root in sorted(roots):
            say(f"  copy   {root.as_posix()}  ({src['repo']} @ {src['commit'][:7]})")
    return 0


# --------------------------------------------------------------------------- plugins

def plugin_sources(lock: dict) -> list[dict]:
    return [s for s in lock["sources"] if s["install"]["method"] == "plugin"]


def same_path(a: str | None, b: Path) -> bool:
    try:
        return bool(a) and Path(a).resolve() == b.resolve()
    except OSError:
        return False


def plugin_entry(plugins: list[dict], pid: str) -> dict | None:
    """The `claude plugin list` entry that applies to this repo.

    A project-scope install is tied to the folder it was made from, so after moving or
    renaming the repo the old entry is still listed (often with errors) next to the new one.
    """
    entries = [p for p in plugins if p.get("id") == pid]
    here = [p for p in entries if p.get("scope") != "project" or same_path(p.get("projectPath"), REPO)]
    return (here or entries or [None])[0]


def plugin_problem(entry: dict | None) -> str | None:
    """Why the plugin does not work here, or None when it does. Same rule as doctor.py."""
    if not entry:
        return "not installed"
    if entry.get("errors"):
        return "; ".join(entry["errors"])
    if not entry.get("enabled", False):
        return "disabled"
    return None


def el4cteo_plugin_matches(lock: dict) -> tuple[bool | None, str]:
    """Compare the installed plugin's skills with vendor/ at the pinned commit."""
    src = source(lock, "el4cteo-roblox-skills")
    plugins = claude_json("plugin", "list", "--json")
    if plugins is None:
        return None, "claude plugin list unavailable"
    entry = plugin_entry(plugins, src["install"]["plugin"])
    if not entry:
        return False, "not installed"
    root = Path(entry.get("readFromFolder") or entry.get("installPath") or "")
    vend = vendor_dir(src) / "skills"
    if not (root / "skills").is_dir() or not vend.is_dir():
        return None, "cannot compare (missing folder)"
    same = tree_hash(root / "skills") == tree_hash(vend)
    return same, f"{src['ref']} = {src['commit'][:7]}" if same else f"differs from {src['commit'][:7]}"


def cmd_plugins(lock: dict) -> int:
    say("[plugins] marketplaces and plugins")
    exe = claude_exe()
    if not exe:
        say("  skip   claude not on PATH; install Claude Code and rerun setup")
        return 0
    markets = {m["name"]: m for m in (claude_json("plugin", "marketplace", "list", "--json") or [])}
    for src in plugin_sources(lock):
        inst = src["install"]
        name, wanted = inst["marketplace"], inst["marketplaceSource"]
        wanted_ref = wanted.split("#", 1)[1] if "#" in wanted else None
        current = markets.get(name)
        if current and wanted_ref and current.get("ref") != wanted_ref:
            say(f"  repin  marketplace {name}: {current.get('ref') or 'unpinned'} -> {wanted_ref}")
            run([exe, "plugin", "marketplace", "remove", name], cwd=REPO, check=False)
            current = None
        if not current:
            say(f"  add    marketplace {wanted}")
            run([exe, "plugin", "marketplace", "add", wanted], cwd=REPO)
        else:
            say(f"  ok     marketplace {name}")

    installed = claude_json("plugin", "list", "--json") or []
    for src in plugin_sources(lock):
        pid = src["install"]["plugin"]
        entry = plugin_entry(installed, pid)
        problem = plugin_problem(entry)
        if problem is None:
            say(f"  ok     plugin {pid} ({entry.get('scope')})")
            continue
        if entry:
            say(f"  !!     plugin {pid}: {problem}")
        say(f"  install plugin {pid} --scope {src['install']['scope']}")
        run([exe, "plugin", "install", pid, "--scope", src["install"]["scope"]], cwd=REPO)

    # Check again: "installed" must mean what doctor.py and the wizard will see.
    after = claude_json("plugin", "list", "--json") or []
    broken = [(src["install"]["plugin"], plugin_problem(plugin_entry(after, src["install"]["plugin"])))
              for src in plugin_sources(lock)]
    broken = [(pid, problem) for pid, problem in broken if problem]
    for pid, problem in broken:
        say(f"  !!     plugin {pid} still not working: {problem}")

    ok, detail = el4cteo_plugin_matches(lock)
    mark = {True: "ok    ", False: "!!    ", None: "??    "}[ok]
    say(f"  {mark} roblox-skills plugin content vs pinned commit: {detail}")
    return 1 if broken else 0


# --------------------------------------------------------------------------- local settings

def cmd_local_settings() -> int:
    """Seed .claude/settings.local.json so the optional MCP servers start OFF.

    A `disabledMcpjsonServers` entry in ANY settings file rejects a server, so it
    lives in the untracked local file: each person turns a server on by moving its
    name to `enabledMcpjsonServers` there, without touching the shared settings.
    A name already present in either list is a user decision and is left alone.
    """
    say("[local-settings] optional MCP servers off by default")
    data = {}
    if LOCAL_SETTINGS.exists():
        try:
            data = json.loads(LOCAL_SETTINGS.read_text(encoding="utf-8") or "{}")
        except ValueError:
            say(f"  !!     {LOCAL_SETTINGS.relative_to(REPO)} is not valid JSON; left untouched")
            return 1
    enabled = data.get("enabledMcpjsonServers", [])
    disabled = data.setdefault("disabledMcpjsonServers", [])
    changed = False
    for name in OPTIONAL_MCP_SERVERS:
        if name in enabled or name in disabled:
            say(f"  ok     {name}: {'on' if name in enabled else 'off'} (your choice is kept)")
            continue
        disabled.append(name)
        changed = True
        say(f"  off    {name}")
    if changed:
        LOCAL_SETTINGS.parent.mkdir(exist_ok=True)
        LOCAL_SETTINGS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


# --------------------------------------------------------------------------- update

def ask(question: str) -> bool:
    if not sys.stdin.isatty():
        say(f"{question} [y/N] (no terminal: answering no)")
        return False
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes", "s", "si", "sí")


def cmd_update(lock: dict) -> int:
    changed = False
    for src in git_sources(lock):
        dest = ensure_vendor(src)
        run(["git", "fetch", "--quiet", "--tags", "--force", "origin"], cwd=dest)
        pinned = src["commit"]
        tag = None
        if src["install"]["method"] == "plugin" and src.get("ref"):
            # A marketplace can only be pinned to a branch or tag, so plugins move tag to tag.
            tag = git("describe", "--tags", "--abbrev=0", f"origin/{src['branch']}", cwd=dest)
            new = git("rev-list", "-n", "1", tag, cwd=dest)
        else:
            new = git("rev-parse", f"origin/{src['branch']}", cwd=dest)
        say(f"\n== {src['repo']}  pinned {pinned[:7]}{' (' + src['ref'] + ')' if src.get('ref') else ''}"
            f"  latest {new[:7]}{' (' + tag + ')' if tag else ''}")
        if new == pinned:
            say("   up to date")
            continue
        log = git("log", "--oneline", f"{pinned}..{new}", cwd=dest)
        stat = git("diff", "--stat", pinned, new, cwd=dest)
        say(log or "   (no commits ahead: the pin is not an ancestor of the new commit)")
        say(stat)
        if not ask(f"Move {src['name']} to {new[:7]}?"):
            continue
        src["commit"] = new
        if tag:
            src["ref"] = tag
            src["install"]["marketplaceSource"] = f"{src['repo']}#{tag}"
            settings = REPO / ".claude" / "settings.json"
            s = json.loads(settings.read_text(encoding="utf-8"))
            s["extraKnownMarketplaces"][src["install"]["marketplace"]]["source"]["ref"] = tag
            settings.write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8", newline="\n")
        changed = True
    if changed:
        save_lock(lock)
        say("\nskills.lock.json updated. Setup will now reinstall from the new pins.")
        return 3
    say("\nNo pins changed.")
    return 0


# --------------------------------------------------------------------------- main

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["vendor", "user", "project", "plugins", "local-settings", "all",
                                        "update"])
    ap.add_argument("--force", action="store_true", help="user: rerun SyphoDev's installer even if in sync")
    a = ap.parse_args()
    lock = load_lock()
    try:
        if a.command == "vendor":
            return cmd_vendor(lock)
        if a.command == "user":
            return cmd_user(lock, a.force)
        if a.command == "project":
            return cmd_project(lock)
        if a.command == "plugins":
            return cmd_plugins(lock)
        if a.command == "local-settings":
            return cmd_local_settings()
        if a.command == "update":
            return cmd_update(lock)
        for step in (lambda: cmd_vendor(lock), lambda: cmd_user(lock, a.force), lambda: cmd_project(lock),
                     lambda: cmd_plugins(lock), cmd_local_settings):
            step()
        return 0
    except subprocess.CalledProcessError as exc:
        say(f"error: command failed ({exc.returncode}): {' '.join(map(str, exc.cmd))}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
