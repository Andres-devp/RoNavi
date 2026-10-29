"""The post-edit hook copied into each game: it must never block or break a session."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ASSET = Path(__file__).resolve().parents[1] / "ronavi" / "assets" / "ronavi_luau_check.py"


class LuauCheckHookTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.game = Path(os.path.realpath(self._tmp.name)) / "Game"
        (self.game / ".claude" / "hooks").mkdir(parents=True)
        (self.game / "src").mkdir()
        self.hook = self.game / ".claude" / "hooks" / ASSET.name
        shutil.copyfile(ASSET, self.hook)

    def tearDown(self):
        self._tmp.cleanup()

    def run_hook(self, payload, path_env=""):
        env = dict(os.environ, PATH=path_env)  # no stylua/selene on PATH unless a test adds them
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run([sys.executable, "-I", str(self.hook)], input=stdin, capture_output=True, text=True,
                              env=env, timeout=60)

    def test_ignores_bad_input_other_files_and_files_outside_the_game(self):
        outside = Path(self._tmp.name) / "Other.luau"
        outside.write_text("local x = 1\n", encoding="utf-8")
        (self.game / "README.md").write_text("hi\n", encoding="utf-8")
        for payload in ("not json", {}, {"tool_input": {}},
                        {"tool_input": {"file_path": str(self.game / "README.md")}},
                        {"tool_input": {"file_path": str(outside)}},
                        {"tool_input": {"file_path": str(self.game / "src" / "Missing.luau")}}):
            res = self.run_hook(payload)
            self.assertEqual((res.returncode, res.stdout), (0, ""), payload)

    def test_missing_tools_let_the_edit_stand(self):
        f = self.game / "src" / "Main.luau"
        f.write_text("local   x  =  1\nreturn x\n", encoding="utf-8")
        res = self.run_hook({"cwd": str(self.game), "tool_input": {"file_path": "src/Main.luau"}})
        self.assertEqual((res.returncode, res.stdout), (0, ""))
        self.assertEqual(f.read_text(encoding="utf-8"), "local   x  =  1\nreturn x\n")


if __name__ == "__main__":
    unittest.main()
