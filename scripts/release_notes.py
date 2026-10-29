#!/usr/bin/env python3
"""Print the CHANGELOG.md notes of a release tag, after checking it matches RoNavi's version.

    python scripts/release_notes.py v0.2.0 > notes.md

Fails (exit 1) when the tag is not vX.Y.Z, differs from ronavi/__init__.py __version__, or
CHANGELOG.md has no "## [X.Y.Z]" section. .github/workflows/release.yml runs it on every tag.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def ronavi_version() -> str:
    text = (REPO / "ronavi" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("ronavi/__init__.py has no __version__")
    return m[1]


def notes(changelog: str, version: str) -> str | None:
    """The body of '## [version] ...' up to the next '## ' heading."""
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |\Z)", changelog, re.M | re.S)
    return m[1].strip() if m else None


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) != 1 or not re.fullmatch(r"v\d+\.\d+\.\d+", argv[0]):
        print("usage: release_notes.py vX.Y.Z", file=sys.stderr)
        return 1
    version = argv[0][1:]
    if version != ronavi_version():
        print(f"tag {argv[0]} does not match ronavi.__version__ {ronavi_version()}", file=sys.stderr)
        return 1
    body = notes((REPO / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    if not body:
        print(f"CHANGELOG.md has no '## [{version}]' section", file=sys.stderr)
        return 1
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
