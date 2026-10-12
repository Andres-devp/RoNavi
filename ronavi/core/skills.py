"""Inventory of the studio's skills, read from skills.lock.json and the folders they install to."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ronavi.core.paths import Studio

OWN_SKILLS = ["studio-doctor", "quota-guard", "own-audio"]
SYPHODEV_FALLBACK = [
    "create-roblox-game", "roblox-3d-model", "roblox-animation", "roblox-build-orchestrator", "roblox-code",
    "roblox-map", "roblox-sfx", "roblox-skills-setup", "roblox-texture-gen", "roblox-ui", "roblox-vfx"]


@dataclass
class SkillInfo:
    name: str
    source: str        # who made it
    scope: str         # proyecto | usuario | plugin
    installed: bool
    description: str = ""
    path: Path | None = None


def describe(skill_md: Path, limit: int = 140) -> str:
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    desc = m.group(1).strip().strip("'\"") if m else ""
    return desc if len(desc) <= limit else desc[: limit - 1] + "…"


def inventory(studio: Studio) -> list[SkillInfo]:
    lock = json.loads((studio.root / "skills.lock.json").read_text(encoding="utf-8"))
    out: list[SkillInfo] = []
    project_skills = studio.root / ".claude" / "skills"

    for name in OWN_SKILLS:
        md = project_skills / name / "SKILL.md"
        out.append(SkillInfo(name, "RoNavi Studio", "proyecto", md.exists(), describe(md), md.parent))

    for src in lock["sources"]:
        inst = src["install"]
        if inst["method"] == "copy":
            names = sorted({Path(c["to"]).parts[2] for c in inst["copy"]})
            for name in names:
                md = project_skills / name / "SKILL.md"
                out.append(SkillInfo(name, src["repo"].split("/")[0], "proyecto", md.exists(), describe(md),
                                     md.parent))
        elif inst["method"] == "vendor-installer":
            vend = studio.root / "vendor" / src["name"] / "skills"
            names = sorted(p.name for p in vend.iterdir() if p.is_dir()) if vend.is_dir() else SYPHODEV_FALLBACK
            user = Path.home() / ".claude" / "skills"
            for name in names:
                md = user / name / "SKILL.md"
                out.append(SkillInfo(name, "SyphoDev", "usuario", md.exists(), describe(md), md.parent))
        elif inst["method"] == "plugin":
            out.append(SkillInfo(inst["plugin"], src["repo"].split("/")[0], "plugin", False,
                                 "Plugin de Claude Code (estado en la tabla de diagnóstico)."))
    return out
