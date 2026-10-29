#!/usr/bin/env python3
"""Run the same checks as .github/workflows/validate.yml, locally.

    python scripts/validate.py            # all checks; shellcheck/pwsh are skipped if missing
    python scripts/validate.py --strict   # missing shellcheck/pwsh count as failures (CI uses this)

The RoNavi Studio unit tests run with this interpreter; the TUI tests are skipped when
Textual is missing (run `.venv/Scripts/python scripts/validate.py` to include them).
"""

from __future__ import annotations

import argparse
import json
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", "vendor", "games", "work", "node_modules", "__pycache__", ".venv", ".ronavi"}
OWN_SKILLS = ["studio-doctor", "quota-guard", "own-audio"]
SHELL_SCRIPTS = ["scripts/setup.sh", "scripts/update-skills.sh", "ronavi.sh", "install.sh"]


def tracked(pattern: str) -> list[Path]:
    return sorted(p for p in REPO.rglob(pattern)
                  if not any(part in SKIP_DIRS for part in p.relative_to(REPO).parts))


def check_json() -> list[str]:
    errors = []
    for p in tracked("*.json"):
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(f"{p.relative_to(REPO)}: {exc}")
    print(f"json        {len(tracked('*.json'))} files")
    return errors


def check_python() -> list[str]:
    files = sorted((REPO / "scripts").glob("*.py"))
    for s in OWN_SKILLS:
        files += sorted((REPO / ".claude" / "skills" / s).rglob("*.py"))
    files += tracked("ronavi/**/*.py") + tracked("tests/*.py")
    errors = []
    for p in files:
        try:
            py_compile.compile(str(p), doraise=True, cfile=None)
        except py_compile.PyCompileError as exc:
            errors.append(str(exc))
    print(f"py_compile  {len(files)} files")
    return errors


def check_shell(strict: bool) -> list[str]:
    exe = shutil.which("shellcheck")
    if not exe:
        print("shellcheck  not installed" + (" (FAIL)" if strict else " (skipped)"))
        return ["shellcheck not installed"] if strict else []
    res = subprocess.run([exe, *SHELL_SCRIPTS], cwd=REPO, capture_output=True, text=True)
    print(f"shellcheck  {len(SHELL_SCRIPTS)} files")
    return [res.stdout + res.stderr] if res.returncode else []


def check_powershell(strict: bool) -> list[str]:
    exe = shutil.which("pwsh") or (shutil.which("powershell") if sys.platform == "win32" else None)
    if not exe:
        print("pwsh parse  not installed" + (" (FAIL)" if strict else " (skipped)"))
        return ["pwsh not installed"] if strict else []
    script = (
        "$bad = 0; @(Get-ChildItem -Recurse -Filter *.ps1 -Path scripts) + @(Get-Item install.ps1) | ForEach-Object { "
        "$t = $null; $e = $null; "
        "[void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$t, [ref]$e); "
        "foreach ($x in $e) { Write-Output \"$($_.Name):$($x.Extent.StartLineNumber): $($x.Message)\"; $bad++ } }; "
        "exit $bad")
    res = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", script], cwd=REPO,
                         capture_output=True, text=True)
    print(f"pwsh parse  scripts/*.ps1 and install.ps1 with {Path(exe).name}")
    return [res.stdout + res.stderr] if res.returncode else []


def check_tests() -> list[str]:
    res = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=REPO,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    summary = [line for line in res.stderr.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    print("unittest    " + " · ".join(summary))
    return [res.stderr[-4000:]] if res.returncode else []


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    errors = check_json() + check_python() + check_shell(a.strict) + check_powershell(a.strict) + check_tests()
    if errors:
        print("\nFAIL")
        for e in errors:
            print(" -", e.strip())
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
