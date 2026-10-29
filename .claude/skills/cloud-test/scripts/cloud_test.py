#!/usr/bin/env python3
"""Run a game's specs inside a real Roblox server with Open Cloud Luau Execution.

    python cloud_test.py --game CoinDash          # dry run: builds the test place, shows the plan and quota
    python cloud_test.py --game CoinDash --yes    # publish to the TEST place, run the specs, print results

What --yes does, in order:
    1. rojo build of the game plus ServerStorage.RoNaviCloudTests (tests/ and src/shared/)
    2. POST the .rbxl as a Saved (not Published) version of the TEST place
    3. create a Luau Execution task on that version that runs runner.luau
    4. poll the task, print PASS/FAIL per test and the task logs; exit 1 if anything failed

Environment: ROBLOX_API_KEY (scopes universe-places write, universe.place.luau-execution-session
write) and the TEST place: ROBLOX_TEST_UNIVERSE_ID / ROBLOX_TEST_PLACE_ID, or --universe / --place.
Never point it at the live game: the version it saves replaces what the place opens with.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
QUOTA = REPO / ".claude" / "skills" / "quota-guard" / "scripts" / "quota.py"
RUNNER = Path(__file__).resolve().parent / "runner.luau"

API = "https://apis.roblox.com"
PUBLISH_URL = API + "/universes/v1/{universe}/places/{place}/versions?versionType=Saved"
TASK_URL = API + "/cloud/v2/universes/{universe}/places/{place}/versions/{version}/luau-execution-session-tasks"
TEST_FOLDER = "RoNaviCloudTests"
TASK_TIMEOUT = "300s"  # the documented maximum
POLL_DEADLINE = 420  # seconds: queue time + the 5 minute run
DONE_STATES = {"COMPLETE", "FAILED", "CANCELLED"}


# --------------------------------------------------------------------------- build

def games_home() -> Path:
    env = os.environ.get("ROBLOX_GAMES_HOME")
    return Path(env).expanduser() if env else REPO / "games"


def game_root(game: str) -> Path:
    root = Path(game) if Path(game).is_dir() else games_home() / game
    if not (root / "default.project.json").is_file():
        raise SystemExit(f"{root} has no default.project.json: scaffold the game with roblox-code first")
    return root


def absolutize(node: object, base: Path) -> object:
    """Copy of a Rojo tree whose $path values are absolute, so the project file can live anywhere."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "$path" and isinstance(v, str):
                out[k] = str((base / v).resolve())
            else:
                out[k] = absolutize(v, base)
        return out
    if isinstance(node, list):
        return [absolutize(x, base) for x in node]
    return node


def test_project(root: Path) -> dict:
    """The game's project plus ServerStorage.RoNaviCloudTests mirroring tests/ and src/shared/."""
    project = json.loads((root / "default.project.json").read_text(encoding="utf-8"))
    project = absolutize(project, root)
    tree = project.setdefault("tree", {"$className": "DataModel"})
    storage = tree.setdefault("ServerStorage", {"$className": "ServerStorage"})
    folder: dict = {"$className": "Folder", "tests": {"$path": str((root / "tests").resolve())}}
    if (root / "src" / "shared").is_dir():
        folder["src"] = {"$className": "Folder", "shared": {"$path": str((root / "src" / "shared").resolve())}}
    storage[TEST_FOLDER] = folder
    project["name"] = f"{project.get('name', root.name)} (cloud-test)"
    return project


def count_specs(root: Path) -> int:
    return sum(1 for _ in (root / "tests").rglob("*.spec.luau")) if (root / "tests").is_dir() else 0


def build(root: Path, out_dir: Path) -> Path:
    rojo = shutil.which("rojo", path=os.pathsep.join([str(Path.home() / ".rokit" / "bin"),
                                                      os.environ.get("PATH", "")]))
    if not rojo:
        raise SystemExit("rojo not found: run `rokit install` in the game")
    project_file = out_dir / "cloud-test.project.json"
    project_file.write_text(json.dumps(test_project(root), indent=2), encoding="utf-8")
    place = out_dir / "cloud-test.rbxl"
    res = subprocess.run([rojo, "build", str(project_file), "--output", str(place)], cwd=root,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise SystemExit("rojo build failed:\n" + (res.stdout + res.stderr).strip()[-1500:])
    return place


# --------------------------------------------------------------------------- Open Cloud

class CloudError(RuntimeError):
    pass


def request(method: str, url: str, api_key: str, body: bytes | None = None,
            content_type: str = "application/json") -> dict:
    req = urllib.request.Request(url, data=body, method=method, headers={"x-api-key": api_key})
    if body is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=180) as res:  # noqa: S310 (fixed https host)
            text = res.read().decode("utf-8") or "{}"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:600]
        hint = {401: "check ROBLOX_API_KEY", 403: "the key lacks a scope or the place is not its creator's",
                429: "rate limit: wait a minute (quota-guard: opencloud-luau-exec)"}.get(exc.code, "")
        raise CloudError(f"{method} {url} -> HTTP {exc.code} {hint}\n{detail}") from None
    except urllib.error.URLError as exc:
        raise CloudError(f"{method} {url} -> {exc.reason}") from None
    return json.loads(text)


def publish(place_file: Path, universe: str, place: str, api_key: str) -> int:
    data = request("POST", PUBLISH_URL.format(universe=universe, place=place), api_key,
                   place_file.read_bytes(), "application/octet-stream")
    if "versionNumber" not in data:
        raise CloudError(f"unexpected publish response: {data}")
    return int(data["versionNumber"])


def create_task(universe: str, place: str, version: int, api_key: str, script: str) -> dict:
    body = json.dumps({"script": script, "timeout": TASK_TIMEOUT}).encode("utf-8")
    return request("POST", TASK_URL.format(universe=universe, place=place, version=version), api_key, body)


def wait_task(task: dict, api_key: str, sleep=time.sleep, clock=time.monotonic) -> dict:
    path = task.get("path")
    if not path:
        raise CloudError(f"task without a path: {task}")
    deadline, delay = clock() + POLL_DEADLINE, 2.0
    while task.get("state") not in DONE_STATES:
        if clock() > deadline:
            raise CloudError(f"task {path} still {task.get('state')} after {POLL_DEADLINE}s")
        sleep(delay)
        delay = min(delay * 1.5, 10.0)
        task = request("GET", f"{API}/cloud/v2/{path}", api_key)
    return task


def task_logs(task: dict, api_key: str) -> list[str]:
    try:
        data = request("GET", f"{API}/cloud/v2/{task['path']}/logs", api_key)
    except CloudError:
        return []
    lines: list[str] = []
    for page in data.get("luauExecutionSessionTaskLogs", []):
        lines += [str(m) for m in page.get("messages", [])]
    return lines


def task_report(task: dict) -> dict:
    """The runner's JSON report from a finished task, or a one-failure report explaining why not."""
    if task.get("state") != "COMPLETE":
        err = task.get("error") or {}
        msg = err.get("message") if isinstance(err, dict) else str(err)
        return {"passed": 0, "failed": 1, "results": [
            {"spec": "(task)", "test": task.get("state", "?"), "ok": False, "err": msg or "no error message"}]}
    output = task.get("output") or {}
    results = output.get("results", output) if isinstance(output, dict) else output
    raw = results[0] if isinstance(results, list) and results else results
    try:
        report = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(report, dict) and "results" in report:
            return report
    except ValueError:
        pass
    return {"passed": 0, "failed": 1, "results": [
        {"spec": "(task)", "test": "output", "ok": False, "err": f"unexpected output: {str(output)[:300]}"}]}


# --------------------------------------------------------------------------- main

def quota(*args: str) -> int:
    sys.stdout.flush()
    return subprocess.run([sys.executable, str(QUOTA), *args]).returncode


def print_report(report: dict) -> None:
    for r in report.get("results", []):
        mark = "PASS" if r.get("ok") else "FAIL"
        print(f"{mark} {r.get('spec')} :: {r.get('test')}")
        if not r.get("ok") and r.get("err"):
            print(f"     {r['err']}")
    print(f"\n{report.get('passed', 0)} passed, {report.get('failed', 0)} failed (in a Roblox server)")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True, help="game name under ROBLOX_GAMES_HOME, or a path")
    ap.add_argument("--universe", default=os.environ.get("ROBLOX_TEST_UNIVERSE_ID"), help="TEST universe id")
    ap.add_argument("--place", default=os.environ.get("ROBLOX_TEST_PLACE_ID"), help="TEST place id")
    ap.add_argument("--yes", action="store_true", help="publish to the test place and run (default: dry run)")
    ap.add_argument("--keep", action="store_true", help="keep the built .rbxl and project file")
    a = ap.parse_args()

    root = game_root(a.game)
    specs = count_specs(root)
    if specs == 0:
        print(f"no tests/**/*.spec.luau in {root}: nothing to run")
        return 0
    out_dir = Path(tempfile.mkdtemp(prefix="cloud-test-"))
    try:
        place_file = build(root, out_dir)
        size = place_file.stat().st_size
        print(f"built {place_file.name}: {size / 1024:.0f} KB, {specs} spec file(s) under ServerStorage.{TEST_FOLDER}")
        if not (a.universe and a.place):
            print("\nset ROBLOX_TEST_UNIVERSE_ID and ROBLOX_TEST_PLACE_ID (a place used only for tests), "
                  "or pass --universe / --place")
            return 0 if not a.yes else 1
        print(f"plan: save a version of TEST place {a.place} (universe {a.universe}), then 1 Luau Execution task")
        quota("estimate", "opencloud-place-publish", "--op", "place-publish")
        if quota("estimate", "opencloud-luau-exec", "--op", "luau-exec-task") == 2:
            print("over the Luau Execution rate limit: wait a minute and retry")
            return 2
        if not a.yes:
            print("\ndry run. Rerun with --yes to publish to the test place and run the specs")
            return 0

        api_key = os.environ.get("ROBLOX_API_KEY")
        if not api_key:
            raise SystemExit("ROBLOX_API_KEY is not set (Open Cloud key: universe-places write and "
                             "universe.place.luau-execution-session write, for the test universe)")
        try:
            version = publish(place_file, a.universe, a.place, api_key)
            quota("log", "opencloud-place-publish", "--op", "place-publish", "--note", f"{root.name} v{version}")
            print(f"saved version {version} of the test place")
            task = create_task(a.universe, a.place, version, api_key, RUNNER.read_text(encoding="utf-8"))
            quota("log", "opencloud-luau-exec", "--op", "luau-exec-task", "--note", f"{root.name} v{version}")
            print(f"task {task.get('path', '?')}: {task.get('state', '?')}")
            task = wait_task(task, api_key)
        except CloudError as exc:
            print(f"\n{exc}")
            return 1
        report = task_report(task)
        logs = task_logs(task, api_key)
        if logs:
            print("--- task logs ---")
            print("\n".join(logs[-60:]))
            print("-----------------")
        print_report(report)
        return 1 if report.get("failed", 0) else 0
    finally:
        if a.keep:
            print(f"kept {out_dir}")
        else:
            shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
