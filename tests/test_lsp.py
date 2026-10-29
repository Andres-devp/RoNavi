import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from ronavi.core import lsp
from tests.helpers import StudioTestCase


class PluginFilesTests(StudioTestCase):
    def test_write_plugin_creates_a_valid_marketplace_and_is_quiet_when_unchanged(self):
        root = lsp.write_plugin(self.studio, "C:/Python/python.exe")
        market = json.loads((root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(market["name"], lsp.MARKETPLACE)
        self.assertEqual(market["plugins"][0]["source"], f"./{lsp.PLUGIN}")
        server = json.loads((root / lsp.PLUGIN / ".lsp.json").read_text(encoding="utf-8"))["luau"]
        self.assertEqual(server["command"], "C:/Python/python.exe")
        self.assertEqual(server["args"], [str(lsp.SERVER_ASSET)])
        self.assertEqual(server["extensionToLanguage"][".luau"], "luau")
        self.assertTrue(lsp.SERVER_ASSET.is_file())

        stamp = (root / lsp.PLUGIN / ".lsp.json").stat().st_mtime_ns
        lsp.write_plugin(self.studio, "C:/Python/python.exe")
        self.assertEqual((root / lsp.PLUGIN / ".lsp.json").stat().st_mtime_ns, stamp)
        self.assertEqual(self.template_hash(), self.template_hash())  # .ronavi/ is not the template

    def test_command_never_has_spaces(self):
        self.assertEqual(lsp.lsp_command("C:/Python/python.exe"), "C:/Python/python.exe")
        self.assertEqual(lsp.lsp_command("/opt/my python/bin/python3"), "/opt/my python/bin/python3")
        self.assertIn(lsp.lsp_command("C:/Program Files/Python/python.exe"), ("python", "python3"))


class EnsureInstalledTests(StudioTestCase):
    def setUp(self):
        super().setUp()
        self.game = self.root / "games" / "Alpha"
        self.game.mkdir()
        self.calls = []

    def fake_run(self, code=0):
        def run(cmd, **kw):
            self.calls.append((cmd, kw.get("cwd")))
            return subprocess.CompletedProcess(cmd, code, "", "boom" if code else "")
        return run

    def test_installs_at_local_scope_in_the_game_once(self):
        with mock.patch.object(lsp, "installed_for", lambda root: False), \
                mock.patch.object(lsp.subprocess, "run", self.fake_run()):
            self.assertIsNone(lsp.ensure_installed(self.studio, self.game, "claude", "python"))
        cmd, cwd = self.calls[0]
        self.assertEqual(cmd[:4], ["claude", "plugin", "install", lsp.PLUGIN])
        self.assertEqual(cmd[cmd.index("--scope") + 1], "local")
        self.assertEqual(cmd[cmd.index("--marketplace") + 1], str(lsp.plugins_root(self.studio)))
        self.assertEqual(cwd, self.game)

        self.calls.clear()
        with mock.patch.object(lsp, "installed_for", lambda root: True), \
                mock.patch.object(lsp.subprocess, "run", self.fake_run()):
            self.assertIsNone(lsp.ensure_installed(self.studio, self.game, "claude", "python"))
        self.assertEqual(self.calls, [])

    def test_problems_are_reported_not_raised(self):
        with mock.patch.object(lsp, "installed_for", lambda root: False):
            self.assertIn("Claude Code", lsp.ensure_installed(self.studio, self.game, None, "python"))
            with mock.patch.object(lsp.subprocess, "run", self.fake_run(code=1)):
                self.assertIn("boom", lsp.ensure_installed(self.studio, self.game, "claude", "python"))

    def test_installed_for_reads_the_registry_defensively(self):
        home = self.tmp / "home"
        registry = home / ".claude" / "plugins" / "installed_plugins.json"
        registry.parent.mkdir(parents=True)
        with mock.patch.object(Path, "home", lambda: home):
            self.assertFalse(lsp.installed_for(self.game))  # no registry
            registry.write_text("not json", encoding="utf-8")
            self.assertFalse(lsp.installed_for(self.game))
            registry.write_text(json.dumps({"plugins": {lsp.PLUGIN_ID: [
                {"scope": "local", "projectPath": str(self.game)}]}}), encoding="utf-8")
            self.assertTrue(lsp.installed_for(self.game))
            self.assertFalse(lsp.installed_for(self.root / "games" / "Beta"))


if __name__ == "__main__":
    unittest.main()
