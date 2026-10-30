"""skills_sync.py plugins with `claude` simulated: no plugin is installed for real."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
_spec = importlib.util.spec_from_file_location("skills_sync", REPO / "scripts" / "skills_sync.py")
ss = importlib.util.module_from_spec(_spec)
sys.modules["skills_sync"] = ss
_spec.loader.exec_module(ss)

FIGMA = "figma@claude-plugins-official"
ROBLOX = "roblox-skills@roblox-skills"
OLD = r"C:\Users\someone\Desktop\roblox-ai-studio"
NOT_INSTALLED = 'Plugin "figma" is enabled in project settings but isn\'t installed'


def entry(pid, path, errors=None):
    e = {"id": pid, "scope": "project", "enabled": True, "projectPath": str(path)}
    if errors:
        e["errors"] = errors
    return e


class FakeClaude:
    """`plugin list` returns `before` until something is installed, then `after`."""

    def __init__(self, before, after=None):
        self.before, self.after = before, after if after is not None else before
        self.installs: list[str] = []

    def json(self, *args):
        if args[:2] == ("plugin", "list"):
            return self.after if self.installs else self.before
        return []  # marketplace list: the sync re-adds them, which run() ignores

    def run(self, cmd, cwd=None, check=True, **_):
        if cmd[1:3] == ["plugin", "install"]:
            self.installs.append(cmd[3])

    def cmd_plugins(self) -> int:
        with mock.patch.object(ss, "claude_exe", lambda: "claude"), \
             mock.patch.object(ss, "claude_json", self.json), \
             mock.patch.object(ss, "run", self.run), \
             mock.patch.object(ss, "el4cteo_plugin_matches", lambda _lock: (True, "pinned")), \
             mock.patch.object(ss, "say", lambda _msg: None):
            return ss.cmd_plugins(ss.load_lock())


class PluginEntryTests(unittest.TestCase):
    def test_prefers_the_install_made_for_this_repo(self):
        plugins = [entry(FIGMA, OLD, [NOT_INSTALLED]), entry(FIGMA, ss.REPO)]
        self.assertTrue(ss.same_path(ss.plugin_entry(plugins, FIGMA)["projectPath"], ss.REPO))
        self.assertIsNone(ss.plugin_problem(ss.plugin_entry(plugins, FIGMA)))

    def test_falls_back_to_another_folder_and_reports_its_errors(self):
        plugins = [entry(FIGMA, OLD, [NOT_INSTALLED])]
        self.assertIn("isn't installed", ss.plugin_problem(ss.plugin_entry(plugins, FIGMA)))
        self.assertEqual(ss.plugin_problem(None), "not installed")
        self.assertEqual(ss.plugin_problem({**entry(FIGMA, ss.REPO), "enabled": False}), "disabled")


class CmdPluginsTests(unittest.TestCase):
    def test_reinstalls_a_plugin_listed_with_errors(self):
        # Regression: the repo moved, `plugin list` still showed the old install and the sync said "ok".
        fake = FakeClaude(before=[entry(FIGMA, OLD, [NOT_INSTALLED]), entry(ROBLOX, OLD)],
                          after=[entry(FIGMA, OLD, [NOT_INSTALLED]), entry(FIGMA, ss.REPO), entry(ROBLOX, OLD)])
        self.assertEqual(fake.cmd_plugins(), 0)
        self.assertEqual(fake.installs, [FIGMA])

    def test_fails_when_the_plugin_still_does_not_work(self):
        broken = [entry(FIGMA, OLD, [NOT_INSTALLED]), entry(ROBLOX, ss.REPO)]
        fake = FakeClaude(before=broken, after=broken)
        self.assertEqual(fake.cmd_plugins(), 1)

    def test_healthy_plugins_are_left_alone(self):
        fake = FakeClaude(before=[entry(FIGMA, ss.REPO), entry(ROBLOX, ss.REPO)])
        self.assertEqual(fake.cmd_plugins(), 0)
        self.assertEqual(fake.installs, [])


if __name__ == "__main__":
    unittest.main()
