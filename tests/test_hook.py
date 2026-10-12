"""The PreToolUse guard that each game carries: unit decisions and the real script end to end."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from ronavi.core.projects import GUARD_REL, create_game, hook_python
from tests.helpers import StudioTestCase

ASSET = Path(__file__).resolve().parents[1] / "ronavi" / "assets" / "ronavi_guard.py"


def load_guard_module():
    spec = importlib.util.spec_from_file_location("ronavi_guard_under_test", ASSET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class HookTests(StudioTestCase):
    def setUp(self):
        super().setUp()
        self.mod = load_guard_module()
        self.game = create_game(self.studio, "Alpha").root
        self.other = create_game(self.studio, "Beta").root
        cfg = json.loads((self.game / ".claude" / "ronavi-guard.json").read_text(encoding="utf-8"))
        self.guard = self.mod.Guard(cfg)

    def decide(self, tool, **tool_input):
        payload = {"tool_name": tool, "tool_input": tool_input, "cwd": str(self.game)}
        return self.mod.decide(payload, self.guard)

    def test_file_tools(self):
        self.assertIsNone(self.decide("Write", file_path=str(self.game / "src" / "Main.luau")))
        self.assertIsNone(self.decide("Edit", file_path="src/Main.luau"))
        self.assertIsNone(self.decide("Write", file_path=str(self.root / "work" / "quota-ledger.json")))
        self.assertIsNone(self.decide("Write", file_path=str(Path.home() / ".claude" / "skills" / "x" / "LOCAL.md")))
        self.assertIsNotNone(self.decide("Write", file_path=str(self.other / "src" / "x.luau")))
        self.assertIsNotNone(self.decide("Edit", file_path="../Beta/CLAUDE.md"))
        self.assertIsNotNone(self.decide("Edit", file_path=str(self.root / "README.md")))
        self.assertIsNotNone(self.decide("MultiEdit", file_path=str(self.root / "scripts" / "doctor.py")))
        self.assertIsNotNone(self.decide("NotebookEdit", notebook_path=str(self.root / "x.ipynb")))
        self.assertIsNotNone(self.decide("Edit", file_path=str(self.game / GUARD_REL)))  # the guard itself
        self.assertIsNone(self.decide("Read", file_path=str(self.root / "README.md")))

    def test_shell_commands(self):
        blocked = [
            "rm -rf ../Beta",
            "cd .. && rm -rf Beta/src",
            "echo hi > ../Beta/x.txt",
            "cp src/a.luau ../Beta/src/",
            "sed -i s/a/b/ ../../CLAUDE.md",
            "git -C ../Beta commit -am x",
            f'Remove-Item -Recurse -Force "{self.other}"',
            f"Set-Content -Path {self.root / 'README.md'} -Value x",
            f"del {self.root / 'CLAUDE.md'}",
            f"mv {self.root / 'scripts'} /tmp/x",
        ]
        allowed = [
            "rm -rf build",
            "cat ../Beta/README.md",
            "git -C ../Beta log --oneline",
            "git status",
            f"python {self.root / '.claude/skills/quota-guard/scripts/quota.py'} log cloudflare --count 1",
            "rojo build -o build.rbxl",
            "ls ../../docs",
            "curl -s https://example.com/a/b > out.json",
        ]
        for cmd in blocked:
            with self.subTest(blocked=cmd):
                self.assertIsNotNone(self.decide("Bash", command=cmd))
        for cmd in allowed:
            with self.subTest(allowed=cmd):
                self.assertIsNone(self.decide("Bash", command=cmd))
        self.assertIsNotNone(self.decide("PowerShell", command=f"Remove-Item {self.other}\\src -Recurse"))

    def test_git_bash_drive_paths(self):
        if os.name != "nt":
            self.skipTest("Git Bash paths only exist on Windows")
        s = str(self.other).replace("\\", "/")
        gitbash = f"/{s[0].lower()}{s[2:]}"
        self.assertIsNotNone(self.decide("Bash", command=f"rm -rf {gitbash}"))

    def test_installed_script_end_to_end(self):
        script = self.game / GUARD_REL

        def run(payload):
            return subprocess.run([hook_python(), str(script)], input=json.dumps(payload).encode("utf-8"),
                                  capture_output=True, timeout=30)

        bad = run({"tool_name": "Write", "cwd": str(self.game),
                   "tool_input": {"file_path": str(self.other / "x.txt"), "content": "x"}})
        self.assertEqual(bad.returncode, 2, bad.stderr)
        self.assertIn("ronavi-guard", bad.stderr.decode("utf-8", "replace"))
        good = run({"tool_name": "Write", "cwd": str(self.game),
                    "tool_input": {"file_path": str(self.game / "x.txt"), "content": "x"}})
        self.assertEqual(good.returncode, 0, good.stderr)
        # Garbage on stdin must not break the session (fail open, with a warning).
        junk = subprocess.run([hook_python(), str(script)], input=b"not json", capture_output=True, timeout=30)
        self.assertEqual(junk.returncode, 0)

    def test_without_config_protects_siblings(self):
        (self.game / ".claude" / "ronavi-guard.json").unlink()
        script = self.game / GUARD_REL
        payload = {"tool_name": "Edit", "cwd": str(self.game), "tool_input": {"file_path": str(self.other / "a")}}
        res = subprocess.run([sys.executable, str(script)], input=json.dumps(payload).encode(), capture_output=True)
        self.assertEqual(res.returncode, 2)
